"""Platform-operator gate for the internal Admin Console (platform ops only).

A platform operator is **not** an organization role. RBAC (Owner / Admin /
Reviewer / Contributor / Viewer) governs one workspace; the console reads
aggregates across *every* workspace, so it is gated by an explicit allow-list
and never by a role check. An Org Owner must not be able to see other
customers' data just because they are an Owner.

Fail-closed: if no allow-list is configured, nobody reaches the console.
An unconfigured environment must never default to "everyone is an operator".

Allow-list sources (all optional, case-insensitive):
  * ``KULIMA_ADMIN_EMAILS``            — reused from the existing config
  * ``KULIMA_PLATFORM_ADMIN_USER_IDS`` — user ids (the JWT ``sub`` claim)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from fastapi import Depends, HTTPException, status

from kulima.config import get_settings

from .auth import OrgContext, get_current_org

REASON_GRANTED = "granted"
REASON_NOT_CONFIGURED = "not_configured"
REASON_NOT_ALLOWLISTED = "not_allowlisted"


@dataclass(frozen=True)
class AdminDecision:
    allowed: bool
    reason: str
    matched_via: str | None = None
    # Identifiers that were checked (never the allow-list itself, so the
    # console cannot be used to enumerate who else is an operator).
    checked: tuple[str, ...] = ()
    allow_list_size: int = 0

    def to_payload(self) -> dict:
        return {
            "isPlatformAdmin": self.allowed,
            "reason": self.reason,
            "matchedVia": self.matched_via,
            "identifiersChecked": list(self.checked),
            "allowListConfigured": self.allow_list_size > 0,
            "allowListSize": self.allow_list_size,
        }


def allow_list() -> set[str]:
    settings = get_settings()
    entries = {str(e).strip().lower() for e in settings.admin_emails if str(e).strip()}
    entries |= {str(e).strip().lower() for e in settings.platform_admin_user_ids if str(e).strip()}
    return entries


def identity_candidates(
    *, user_id: str, verified_email: str | None = None,
) -> list[tuple[str, str]]:
    """Identifiers the *session itself* proves, tagged by kind.

    Only claims minted by the auth chain are eligible:
      * ``session_subject`` — the JWT ``sub``. NextAuth sets it from the
        identity provider's account id (or the provider-verified email), so a
        user cannot choose it. See the jwt callback in
        ``app/api/auth/[...nextauth]/route.ts``.
      * ``verified_email`` — reserved for an email claim minted by the proxy.
        It is currently absent from backend tokens, so it never matches.

    What is deliberately **not** consulted: ``organization_members.email``,
    ``display_name`` or ``organizations.created_by``. Those are database rows
    an organization Admin can write (inviting a member lets them type any
    email or name), so trusting them would let a customer grant themselves
    platform access by listing an operator's address against their own user id.
    """
    pairs: list[tuple[str, str]] = [("session_subject", user_id)]
    if verified_email:
        pairs.append(("verified_email", verified_email))
    return pairs


def evaluate(identifiers: Iterable[tuple[str, str]]) -> AdminDecision:
    allow = allow_list()
    checked: list[str] = []
    if not allow:
        return AdminDecision(
            allowed=False,
            reason=REASON_NOT_CONFIGURED,
            checked=tuple(v for _, v in identifiers if v),
            allow_list_size=0,
        )
    matched_via: str | None = None
    for kind, value in identifiers:
        if not value:
            continue
        checked.append(value)
        if matched_via is None and str(value).strip().lower() in allow:
            matched_via = kind
    if matched_via is not None:
        return AdminDecision(
            allowed=True,
            reason=REASON_GRANTED,
            matched_via=matched_via,
            checked=tuple(checked),
            allow_list_size=len(allow),
        )
    return AdminDecision(
        allowed=False,
        reason=REASON_NOT_ALLOWLISTED,
        checked=tuple(checked),
        allow_list_size=len(allow),
    )


def decision_for(current: OrgContext) -> AdminDecision:
    return evaluate(identity_candidates(user_id=current.user_id))


async def require_platform_admin(current: OrgContext = Depends(get_current_org)) -> OrgContext:
    """Route dependency: allow platform operators, 403 everyone else."""
    decision = decision_for(current)
    if decision.allowed:
        return current
    if decision.reason == REASON_NOT_CONFIGURED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": True,
                "code": "PLATFORM_ADMIN_NOT_CONFIGURED",
                "message": (
                    "The platform operations console is disabled: no operators are "
                    "configured. Set KULIMA_PLATFORM_ADMIN_USER_IDS or KULIMA_ADMIN_EMAILS "
                    "on the backend to grant access."
                ),
                "reason": decision.reason,
            },
        )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": True,
            "code": "PLATFORM_ADMIN_REQUIRED",
            "message": (
                "This console is restricted to configured platform operators. Your "
                "organization role does not grant cross-workspace visibility."
            ),
            "reason": decision.reason,
            "role": current.role.value,
        },
    )
