"""Platform-administrator authorization for the internal Admin Console.

Two planes of identity, deliberately never mixed
-------------------------------------------------
**Organization plane** — ``Role`` (owner / admin / reviewer / contributor /
viewer) on ``organization_members``. Written by customers through
member-management endpoints. Governs exactly one workspace.

**Platform plane** — the ``PLATFORM_ADMIN`` role in the ``platform_admins``
table (``kulima.core.orgs.platform_admins``). Provisioned from configuration and
grantable only by an existing platform administrator. Never written by a
customer-facing code path, and never a value in the organization ``Role`` enum:
if it were, the endpoint that re-roles a colleague would also grant
cross-workspace visibility.

Resolution order
----------------
1. the stored ``PLATFORM_ADMIN`` role, matched on identifiers the *session*
   proves (JWT ``sub``, or the provider-verified ``email`` claim minted by our
   own auth chain);
2. ``KULIMA_ADMIN_EMAILS`` / ``KULIMA_PLATFORM_ADMIN_USER_IDS`` as break-glass,
   for when the role store is unreachable or an operator must be recovered from
   the deployment environment. A break-glass grant is labelled ``via`` in the
   session payload and in every audit event, so it is never mistaken for the
   stored role.

Fail-closed: if neither the store nor the environment names anyone, nobody
reaches the console. An unconfigured environment must never default to
"everyone is a platform admin".

What is never consulted: ``organization_members.email``, ``display_name`` or
``organizations.created_by``. Those are rows an organization Admin can write
(inviting a member lets them type any address), so trusting them would let a
customer grant themselves platform access by listing an operator's address
against their own user id.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

from fastapi import Depends, HTTPException, status

from kulima.config import get_settings
from kulima.core.orgs.platform_admins import (
    PLATFORM_ADMIN_ROLE,
    PLATFORM_ADMIN_ROLE_LABEL,
    PlatformCapability,
    capability_labels,
    coerce_capability,
    get_repo,
)

from .auth import OrgContext, get_current_org

_log = logging.getLogger(__name__)

REASON_GRANTED = "granted"
REASON_NOT_CONFIGURED = "not_configured"
REASON_NOT_ALLOWLISTED = "not_allowlisted"

#: How a grant was obtained. ``platform_role`` is the stored role;
#: ``env_allow_list`` is break-glass and is reported as such everywhere.
VIA_PLATFORM_ROLE = "platform_role"
VIA_ENV_ALLOW_LIST = "env_allow_list"


@dataclass(frozen=True)
class AdminDecision:
    allowed: bool
    reason: str
    # Identifier kind that matched ('session_subject' | 'verified_email') — never
    # the allow-list or the roster itself, so the console cannot enumerate who
    # else holds the role.
    matched_via: str | None = None
    checked: tuple[str, ...] = ()
    allow_list_size: int = 0
    granted_by: str | None = None
    role: str | None = None
    role_label: str | None = None
    capabilities: tuple[str, ...] = ()
    admin_count: int = 0
    store_configured: bool = False

    def holds(self, capability: PlatformCapability | str | None) -> bool:
        if capability is None:
            return self.allowed
        cap = coerce_capability(capability)
        return self.allowed and cap is not None and cap.value in self.capabilities

    def to_payload(self) -> dict:
        return {
            "isPlatformAdmin": self.allowed,
            "reason": self.reason,
            "matchedVia": self.matched_via,
            "identifiersChecked": list(self.checked),
            "allowListConfigured": self.allow_list_size > 0,
            "allowListSize": self.allow_list_size,
            "grantedBy": self.granted_by,
            "platformRole": self.role if self.allowed else None,
            "roleLabel": self.role_label if self.allowed else None,
            "capabilities": list(self.capabilities) if self.allowed else [],
            "capabilityLabels": capability_labels(self.capabilities) if self.allowed else [],
            "roleStoreConfigured": self.store_configured,
            "adminCount": self.admin_count,
        }


def allow_list() -> set[str]:
    """Break-glass identities from the environment (not the stored role)."""
    settings = get_settings()
    entries = {str(e).strip().lower() for e in settings.admin_emails if str(e).strip()}
    entries |= {str(e).strip().lower() for e in settings.platform_admin_user_ids if str(e).strip()}
    return entries


def identity_candidates(
    *, user_id: str, verified_email: str | None = None,
) -> list[tuple[str, str]]:
    """Identifiers the *session itself* proves, tagged by kind.

    * ``session_subject`` — the JWT ``sub``. NextAuth sets it from the identity
      provider's account id (or the provider-verified email), so a user cannot
      choose it. See the jwt callback in ``app/api/auth/[...nextauth]/route.ts``.
    * ``verified_email`` — the ``email`` claim the /api/v1 proxy mints from the
      encrypted NextAuth JWT (Google / Azure AD verify address ownership). It is
      what lets the role be provisioned for an address before that person has
      ever signed in and their ``sub`` is unknown.
    """
    pairs: list[tuple[str, str]] = [("session_subject", user_id)]
    if verified_email:
        pairs.append(("verified_email", verified_email))
    return pairs


def _role_lookup(identifiers: Iterable[tuple[str, str]]):
    """Resolve the stored role. A broken store denies access; it never grants."""
    user_id = email = None
    for kind, value in identifiers:
        if kind == "session_subject":
            user_id = value
        elif kind == "verified_email":
            email = value
    try:
        repo = get_repo()
        admin = repo.resolve(user_id=user_id, email=email)
        count = repo.count_active()
        configured = count > 0
    except Exception as exc:  # noqa: BLE001 — fail closed, fall back to break-glass
        _log.warning("platform admin role lookup failed; falling back to break-glass: %s", exc)
        return None, 0, False, None
    matched_kind = "session_subject"
    if admin is not None and admin.user_id and str(admin.user_id) == str(user_id):
        matched_kind = "session_subject"
    elif admin is not None and email and str(admin.email or "").lower() == str(email).lower():
        matched_kind = "verified_email"
    return admin, count, configured, matched_kind


def evaluate(identifiers: Iterable[tuple[str, str]]) -> AdminDecision:
    pairs = list(identifiers)
    checked = tuple(v for _, v in pairs if v)
    admin, admin_count, store_configured, matched_kind = _role_lookup(pairs)

    if admin is not None and admin.is_active:
        # A bootstrap row provisioned for an address can arrive with no subject
        # linked. Linking it on first verified-email access grants nothing new —
        # the same session already matched on that email — it just makes the
        # binding survive environments where the email claim is later absent.
        if admin.user_id is None:
            _link_subject(pairs)
        return AdminDecision(
            allowed=True,
            reason=REASON_GRANTED,
            matched_via=matched_kind,
            checked=checked,
            allow_list_size=len(allow_list()),
            granted_by=VIA_PLATFORM_ROLE,
            role=PLATFORM_ADMIN_ROLE,
            role_label=PLATFORM_ADMIN_ROLE_LABEL,
            capabilities=tuple(sorted(c.value for c in admin.capabilities)),
            admin_count=admin_count,
            store_configured=store_configured,
        )

    allow = allow_list()
    if not allow and not store_configured:
        return AdminDecision(
            allowed=False,
            reason=REASON_NOT_CONFIGURED,
            checked=checked,
            allow_list_size=0,
            admin_count=admin_count,
            store_configured=store_configured,
        )
    matched_via: str | None = None
    for kind, value in pairs:
        if not value:
            continue
        if matched_via is None and str(value).strip().lower() in allow:
            matched_via = kind
    all_caps = tuple(sorted(c.value for c in PlatformCapability))
    if matched_via is not None:
        return AdminDecision(
            allowed=True,
            reason=REASON_GRANTED,
            matched_via=matched_via,
            checked=checked,
            allow_list_size=len(allow),
            granted_by=VIA_ENV_ALLOW_LIST,
            role=PLATFORM_ADMIN_ROLE,
            role_label=f"{PLATFORM_ADMIN_ROLE_LABEL} (break-glass)",
            capabilities=all_caps,
            admin_count=admin_count,
            store_configured=store_configured,
        )
    return AdminDecision(
        allowed=False,
        reason=REASON_NOT_ALLOWLISTED,
        checked=checked,
        allow_list_size=len(allow),
        admin_count=admin_count,
        store_configured=store_configured,
    )


def _link_subject(pairs: list[tuple[str, str]]) -> None:
    user_id = next((v for k, v in pairs if k == "session_subject"), None)
    email = next((v for k, v in pairs if k == "verified_email"), None)
    if not user_id or not email:
        return
    try:
        repo = get_repo()
        row = repo.find(email=email)
        if row is not None and row.user_id is None:
            repo.attach_subject(principal=row.principal, user_id=user_id)
    except Exception as exc:  # noqa: BLE001 — a convenience link must never break a request
        _log.warning("platform admin subject link failed: %s", exc)


def decision_for(current: OrgContext) -> AdminDecision:
    return evaluate(identity_candidates(
        user_id=current.user_id,
        verified_email=getattr(current, "verified_email", None),
    ))


def _denial(status_code: int, code: str, message: str, decision: AdminDecision,
            current: OrgContext, capability: str | None = None) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "error": True,
            "code": code,
            "message": message,
            "reason": decision.reason,
            "role": current.role.value,
            "platformRole": decision.role,
            "requiredCapability": capability,
        },
    )


async def _authorize(current: OrgContext, capability: PlatformCapability | None) -> OrgContext:
    """The one check behind every platform route: role first, capability second."""
    decision = decision_for(current)
    if decision.allowed and decision.holds(capability):
        # Stashed on the request so the audit entry can record *how* access was
        # obtained — a break-glass mutation must not look like a role mutation.
        current.admin_decision = decision  # type: ignore[attr-defined]
        return current
    if not decision.allowed:
        if decision.reason == REASON_NOT_CONFIGURED:
            raise _denial(
                status.HTTP_403_FORBIDDEN,
                "PLATFORM_ADMIN_NOT_CONFIGURED",
                (
                    "The platform operations console is disabled: no platform "
                    "administrators are provisioned and no break-glass identities are "
                    "configured. Set KULIMA_PLATFORM_ADMIN_EMAILS (role) or "
                    "KULIMA_PLATFORM_ADMIN_USER_IDS / KULIMA_ADMIN_EMAILS (break-glass) "
                    "on the backend."
                ),
                decision,
                current,
            )
        raise _denial(
            status.HTTP_403_FORBIDDEN,
            "PLATFORM_ADMIN_REQUIRED",
            (
                "This area is restricted to the PLATFORM_ADMIN role. Your "
                "organization role does not grant cross-workspace visibility."
            ),
            decision,
            current,
            capability.value if capability else None,
        )
    raise _denial(
        status.HTTP_403_FORBIDDEN,
        "PLATFORM_CAPABILITY_REQUIRED",
        (
            "Your platform role does not include the "
            f"'{capability.value if capability else 'unknown'}' capability."
        ),
        decision,
        current,
        capability.value if capability else None,
    )


async def require_platform_admin(current: OrgContext = Depends(get_current_org)) -> OrgContext:
    """Route dependency: allow platform administrators, 403 everyone else."""
    return await _authorize(current, None)


def require_platform_capability(capability: PlatformCapability | str):
    """Dependency factory: gate a route on one platform capability.

    Enforced at the router layer, the same way organization permissions are, so
    no screen has to be trusted to hide a control it should not expose. The
    capability is a dependency argument, never a query parameter — a client must
    not be able to choose which capability it is checked against.
    """
    cap = coerce_capability(capability)

    async def _dependency(current: OrgContext = Depends(get_current_org)) -> OrgContext:
        return await _authorize(current, cap)

    return _dependency


def decision_of(current: OrgContext) -> AdminDecision:
    """The decision recorded by the gate, for audit metadata."""
    cached = getattr(current, "admin_decision", None)
    return cached if isinstance(cached, AdminDecision) else decision_for(current)
