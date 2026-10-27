"""Conversations API — assessment-aware AI Analyst conversation workspace.

Routes (all workspace-scoped, Phase 4 isolation):

    GET    /api/v1/conversations/history                 Phase 5 assessment history
    GET    /api/v1/conversations/{assessmentId}          Phase 2 sidebar list
    POST   /api/v1/conversations/{assessmentId}          Phase 6 create new chat
    GET    /api/v1/conversations/{assessmentId}/{cid}    messages of one conversation
    PATCH  /api/v1/conversations/{cid}                   Phase 6 rename
    DELETE /api/v1/conversations/{cid}                   Phase 6 delete
    POST   /api/v1/conversations/{cid}/messages          Phase 1 append message

The Ask IC / Ask Signals endpoints remain authoritative for generating
answers; this router persists conversation-scoped history and provides the
sidebar/management surface.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Body, Depends, HTTPException

from ..core.auth import OrgContext, require_permission
from ..core.rate_limit import check_rate_limit
from ..schemas.dtos import ConversationCreateRequest, ConversationRenameRequest
from ..services import conversation_service
from ..services.conversation_service import ConversationError
from kulima.core.billing.service import (
    BillingBlocked,
    assessment_history_window_days,
    assert_feature,
)
from kulima.core.orgs.models import Permission

_log = logging.getLogger(__name__)
router = APIRouter()


def _handle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ConversationError):
        code = exc.code
        status = 404 if code in {"conversation_not_found", "assessment_not_found"} else 400
        return HTTPException(status_code=status, detail={"error": True, "message": str(exc)})
    return HTTPException(status_code=500, detail={"error": True, "message": str(exc)})


def _raise_billing_block(exc: BillingBlocked) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.to_detail())


def _raise_conversation_gate(org_id: str) -> None:
    """Conversation history is a Professional+ feature (no-op while billing
    enforcement is disabled — pilot experience unchanged)."""
    try:
        assert_feature(org_id, "conversation_history")
    except BillingBlocked as exc:
        _raise_billing_block(exc)


@router.get("/history")
async def get_assessment_history(
    limit: int = 50,
    current: OrgContext = Depends(require_permission(Permission.VIEW)),
):
    """Phase 5: assessment history sidebar — name, type, trust score, date,
    conversation count. Reopenable. Starter is limited to a 30-day window."""
    check_rate_limit(current.user_id, "conversations:history")
    try:
        data = conversation_service.assessment_history(current.user_id, current.org_id, limit)
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc)
    # Plan history window (Starter = 30 days, paid plans = unlimited).
    window = assessment_history_window_days(current.org_id)
    if window and isinstance(data, dict):
        cutoff = datetime.now(timezone.utc) - timedelta(days=window)
        kept = []
        for item in data.get("assessments", []):
            raw = item.get("createdAt") if isinstance(item, dict) else None
            try:
                created = datetime.fromisoformat(str(raw))
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                if created >= cutoff:
                    kept.append(item)
            except (TypeError, ValueError):
                kept.append(item)  # unparseable dates stay visible — never hide data by accident
        data = {**data, "assessments": kept, "historyWindowDays": window}
    return data


@router.get("/{assessment_id}")
async def list_conversations(
    assessment_id: str,
    current: OrgContext = Depends(require_permission(Permission.VIEW)),
):
    """Phase 2: conversation list for ONE assessment (auto-provisions Chat 1)."""
    check_rate_limit(current.user_id, "conversations:list")
    _raise_conversation_gate(current.org_id)
    try:
        return conversation_service.list_conversations(
            assessment_id, current.user_id, current.org_id
        )
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc)


@router.post("/{assessment_id}")
async def create_conversation(
    assessment_id: str,
    payload: ConversationCreateRequest = Body(default=ConversationCreateRequest()),
    current: OrgContext = Depends(require_permission(Permission.ASSESS)),
):
    """Phase 6: + New Conversation inside an assessment."""
    check_rate_limit(current.user_id, "conversations:create")
    _raise_conversation_gate(current.org_id)
    try:
        return conversation_service.create_conversation(
            assessment_id, current.user_id, current.org_id, payload.title
        )
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc)


@router.get("/{assessment_id}/{conversation_id}")
async def get_conversation_messages(
    assessment_id: str,
    conversation_id: str,
    current: OrgContext = Depends(require_permission(Permission.VIEW)),
):
    """Messages of ONE conversation — cross-assessment reads are blocked."""
    check_rate_limit(current.user_id, "conversations:messages")
    _raise_conversation_gate(current.org_id)
    try:
        result = conversation_service.get_conversation_messages(
            conversation_id, current.user_id, current.org_id
        )
        conv = result.get("conversation") or {}
        if conv.get("assessment_id") != assessment_id:
            raise ConversationError("conversation_not_found", "Conversation does not belong to this assessment.")
        return result
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc)


@router.patch("/{conversation_id}")
async def rename_conversation(
    conversation_id: str,
    payload: ConversationRenameRequest,
    current: OrgContext = Depends(require_permission(Permission.ASSESS)),
):
    """Phase 6: rename chat."""
    check_rate_limit(current.user_id, "conversations:rename")
    try:
        return conversation_service.rename_conversation(
            conversation_id, payload.title, current.user_id, current.org_id
        )
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc)


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current: OrgContext = Depends(require_permission(Permission.ASSESS)),
):
    """Phase 6: delete chat (and its messages)."""
    check_rate_limit(current.user_id, "conversations:delete")
    try:
        return conversation_service.delete_conversation(
            conversation_id, current.user_id, current.org_id
        )
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc)


@router.post("/{conversation_id}/messages")
async def append_message(
    conversation_id: str,
    payload: dict = Body(...),
    current: OrgContext = Depends(require_permission(Permission.ASSESS)),
):
    """Phase 1: persist one message into a conversation."""
    check_rate_limit(current.user_id, "conversations:append")
    role = str(payload.get("role") or "user")
    content = str(payload.get("content") or "")
    try:
        message_id = conversation_service.append_message(
            conversation_id, role, content, current.user_id, current.org_id
        )
        return {"conversationId": conversation_id, "messageId": message_id, "ok": message_id is not None}
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc)


@router.post("/{conversation_id}/feedback")
async def save_conversation_feedback(
    conversation_id: str,
    payload: dict = Body(...),
    current: OrgContext = Depends(require_permission(Permission.ASSESS)),
):
    """Phase 10: Submit feedback linked to an AI Analyst conversation."""
    check_rate_limit(current.user_id, "conversations:feedback_save")
    try:
        conv_info = conversation_service.get_conversation_messages(
            conversation_id, current.user_id, current.org_id
        )
        conv = conv_info.get("conversation") or {}
        assessment_id = conv.get("assessment_id")
        if not assessment_id:
            raise ConversationError("assessment_not_found", "Conversation is not bound to an assessment.")

        rating = int(payload.get("rating", 5))
        comment = str(payload.get("comment") or "")
        user_name = str(payload.get("userName") or current.user_id or "AI Analyst Reviewer")

        from ..services import assessment_adapter
        feedback_id = assessment_adapter.save_feedback_for_assessment(
            assessment_id,
            user_name,
            rating,
            f"[Chat: {conv.get('title', 'AI Analyst')}] {comment}".strip(),
            user_id=current.user_id,
            org_id=current.org_id,
        )
        return {
            "ok": True,
            "conversationId": conversation_id,
            "assessmentId": assessment_id,
            "rating": rating,
            "feedbackId": feedback_id,
        }
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc)


@router.get("/{conversation_id}/feedback")
async def get_conversation_feedback(
    conversation_id: str,
    current: OrgContext = Depends(require_permission(Permission.VIEW)),
):
    """Phase 10: Retrieve feedback linked to an AI Analyst conversation."""
    check_rate_limit(current.user_id, "conversations:feedback_get")
    try:
        conv_info = conversation_service.get_conversation_messages(
            conversation_id, current.user_id, current.org_id
        )
        conv = conv_info.get("conversation") or {}
        assessment_id = conv.get("assessment_id")
        if not assessment_id:
            return {"feedback": [], "total": 0, "conversationId": conversation_id}

        from ..services import assessment_adapter
        records = assessment_adapter.get_feedback_for_assessment(
            assessment_id, user_id=current.user_id, org_id=current.org_id
        )
        # Filter records mentioning this conversation
        prefix = f"[Chat: {conv.get('title', '')}"
        conv_records = [
            r for r in records
            if prefix in str(r.get("comment", ""))
        ] or records
        return {
            "feedback": conv_records,
            "total": len(conv_records),
            "conversationId": conversation_id,
            "assessmentId": assessment_id,
        }
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc)

