"""Conversation service — assessment-aware AI Analyst conversations.

Wires the ConversationRepository into the API layer with ownership checks,
context isolation (Phase 4) and fresh-assessment default conversations
(Phase 3). Called by the ``/api/v1/conversations`` router.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .conversation_repository import ConversationRepository

_log = logging.getLogger(__name__)

_repo: ConversationRepository | None = None


def get_conversation_repository() -> ConversationRepository:
    global _repo
    if _repo is None:
        _repo = ConversationRepository()
    return _repo


class ConversationError(Exception):
    def __init__(self, code: str, message: str = ""):
        self.code = code
        super().__init__(message or code)


# ── Phase 3: fresh assessment → fresh default conversation ────────────────

def ensure_assessment_conversation(
    assessment_id: str,
    *,
    run_id: str | None = None,
    user_id: str | None = None,
    org_id: str | None = None,
) -> dict:
    """The default AI Analyst conversation for ONE assessment.

    Called when a new assessment completes. Creates a fresh default
    conversation scoped to that assessment — previous assessments' chats are
    never loaded into it.
    """
    if not assessment_id:
        raise ConversationError("assessment_required", "assessmentId is required")
    repo = get_conversation_repository()
    return repo.ensure_default_conversation(
        assessment_id, run_id=run_id, user_id=user_id, org_id=org_id
    )


def _conversation_visible(
    conv: dict,
    user_id: str | None,
    org_id: str | None,
) -> bool:
    conv_org = conv.get("org_id")
    conv_user = conv.get("user_id")
    if org_id is not None:
        return conv_org == org_id or conv_org is None
    if user_id is not None:
        return conv_user == user_id or conv_user is None
    return True


def _assert_access(
    conversation_id: str,
    user_id: str | None,
    org_id: str | None,
) -> dict:
    repo = get_conversation_repository()
    conv = repo.get_conversation(
        conversation_id, user_id=user_id, org_id=org_id, assessment_id=None
    )
    if conv is None or not _conversation_visible(conv, user_id, org_id):
        raise ConversationError("conversation_not_found", "Conversation not found or not accessible.")
    return conv


def _assert_assessment_access(
    assessment_id: str,
    user_id: str | None,
    org_id: str | None,
) -> None:
    """Phase 4: the caller must be able to see the assessment itself."""
    try:
        from kulima.core.assessment.repository import AssessmentRepository
        ctx = AssessmentRepository().get(assessment_id, user_id=user_id, org_id=org_id)
    except Exception:  # noqa: BLE001 — legacy assessments may not load cleanly
        ctx = None
    if ctx is None:
        # Not found in the org/user scope → cross-assessment read blocked.
        raise ConversationError("assessment_not_found", "Assessment not found or not accessible.")


# ── Conversation CRUD (Phase 6) ─────────────────────────────────────────────

def create_conversation(
    assessment_id: str,
    user_id: str | None,
    org_id: str | None,
    title: str | None = None,
) -> dict:
    _assert_assessment_access(assessment_id, user_id, org_id)
    repo = get_conversation_repository()
    try:
        from kulima.core.assessment.repository import AssessmentRepository
        ctx = AssessmentRepository().get(assessment_id, user_id=user_id, org_id=org_id)
        run_id = ctx.run_id if ctx else None
    except Exception:  # noqa: BLE001
        run_id = None
    return repo.create_conversation(
        assessment_id, run_id=run_id, user_id=user_id, org_id=org_id, title=title
    )


def list_conversations(
    assessment_id: str,
    user_id: str | None,
    org_id: str | None,
) -> dict:
    """Phase 2/4: sidebar history for ONE assessment — never another's."""
    _assert_assessment_access(assessment_id, user_id, org_id)
    repo = get_conversation_repository()
    conversations = repo.list_conversations(assessment_id, user_id=user_id, org_id=org_id)
    if not conversations:
        # Phase 3: first open of an assessment auto-provisions Chat 1.
        default = ensure_assessment_conversation(
            assessment_id, user_id=user_id, org_id=org_id
        )
        conversations = [default]
    return {"assessmentId": assessment_id, "conversations": conversations}


def get_conversation_messages(
    conversation_id: str,
    user_id: str | None,
    org_id: str | None,
) -> dict:
    conv = _assert_access(conversation_id, user_id, org_id)
    repo = get_conversation_repository()
    messages = repo.get_messages(conversation_id)
    return {"conversation": conv, "messages": messages}


def rename_conversation(
    conversation_id: str,
    title: str,
    user_id: str | None,
    org_id: str | None,
) -> dict:
    _assert_access(conversation_id, user_id, org_id)
    repo = get_conversation_repository()
    ok = repo.rename_conversation(conversation_id, title)
    if not ok:
        raise ConversationError("conversation_not_found", "Conversation not found.")
    return {"conversationId": conversation_id, "title": title.strip()[:120]}


def delete_conversation(
    conversation_id: str,
    user_id: str | None,
    org_id: str | None,
) -> dict:
    """Delete a chat end-to-end (Conversation UX, Problem 4).

    Audit trail covers: conversation id, assessment id, owner validation and
    the delete outcome. The delete is verified row-by-row (messages + row)
    and the outcome is recorded in the audit log so a silent no-op can never
    produce a later 404.
    """
    repo = get_conversation_repository()
    conv = repo.get_conversation(
        conversation_id, user_id=user_id, org_id=org_id, assessment_id=None
    )
    if conv is None:
        # Distinguish already-deleted (idempotent success) from inaccessible.
        any_row = repo.get_conversation(conversation_id, user_id=None, org_id=None)
        if any_row is None:
            # Already gone — deleting twice is a no-op success for the client.
            return {"conversationId": conversation_id, "deleted": True, "alreadyDeleted": True}
        raise ConversationError(
            "conversation_not_found",
            "Conversation not found or not accessible.",
        )
    if not _conversation_visible(conv, user_id, org_id):
        raise ConversationError(
            "conversation_not_found",
            "Conversation not found or not accessible.",
        )

    assessment_id = str(conv.get("assessment_id") or "")
    removed = repo.delete_conversation(conversation_id)

    # Audit the delete (conversation id + assessment id + owner + outcome).
    try:
        from kulima.core.audit import record_event

        record_event(
            "conversation.deleted",
            org_id=org_id,
            user_id=user_id,
            assessment_id=assessment_id or None,
            metadata={
                "conversationId": conversation_id,
                "assessmentId": assessment_id,
                "ownerUserId": conv.get("user_id"),
                "deleted": bool(removed),
            },
        )
    except Exception:  # noqa: BLE001 — audit must never block deletion
        pass

    return {"conversationId": conversation_id, "deleted": bool(removed)}


# ── Message persistence + Phase 4 context isolation ────────────────────────

def append_message(
    conversation_id: str,
    role: str,
    content: str,
    user_id: str | None,
    org_id: str | None,
) -> int | None:
    conv = _assert_access(conversation_id, user_id, org_id)
    repo = get_conversation_repository()
    return repo.append_message(conversation_id, role, content)


def assessment_history(user_id: str | None, org_id: str | None, limit: int = 50) -> dict:
    """Phase 5: assessment history for the sidebar (name, type, trust score,
    date, conversation count)."""
    repo = get_conversation_repository()
    rows = repo.assessment_history(org_id=org_id, user_id=user_id, limit=limit)
    return {"assessments": rows}
