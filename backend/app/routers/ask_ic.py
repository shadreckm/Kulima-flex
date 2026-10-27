from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from ..schemas.dtos import AskRequest, AskResponse
from ..services.orchestrator_adapter import ask_ic, get_brief_for_run, get_run_status
from ..services import assessment_adapter
from ..core.auth import OrgContext, require_permission
from ..core.rate_limit import check_rate_limit
from ..services.demo_chat import doc_intelligence_ask_ic_answer
from ..services.conversation_service import ConversationError
from kulima.core.billing.service import BillingBlocked, assert_feature
from kulima.core.orgs.models import Permission
import asyncio
import json
import logging
import random

_log = logging.getLogger(__name__)

router = APIRouter()


def _enforce_ask_ic_feature(current: OrgContext) -> None:
    """Ask IC is a PRO/Enterprise feature (pass-through when enforcement is off)."""
    try:
        assert_feature(current.org_id, "ask_ic")
    except BillingBlocked as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail())


def _resolve_conversation_history(
    req: AskRequest,
    current: OrgContext,
) -> tuple[list[dict], str | None]:
    """Phase 4 context isolation for Ask IC.

    When the request carries a conversationId, the conversation's assessment
    must match the run's assessment. History is then loaded from the
    conversation store (server-side, authoritative) instead of trusting the
    client payload. Returns (history, conversation_id).
    """
    conversation_id = getattr(req, "conversationId", None)
    if not conversation_id:
        return (req.history or []), None
    try:
        from ..services import conversation_service

        result = conversation_service.get_conversation_messages(
            conversation_id, current.user_id, current.org_id
        )
        conv = result.get("conversation") or {}
        messages = result.get("messages") or []

        # The run must belong to the conversation's assessment.
        req_assessment = getattr(req, "assessmentId", None)
        if req_assessment and conv.get("assessment_id") != req_assessment:
            raise ConversationError(
                "context_mismatch",
                "Conversation does not belong to this assessment.",
            )

        # Persist the new user question into the conversation.
        conversation_service.append_message(
            conversation_id, "user", req.question, current.user_id, current.org_id
        )

        history = [
            {"role": m["role"], "content": m["content"]}
            for m in messages
            if m.get("role") in ("user", "assistant")
        ]
        return history, conversation_id
    except ConversationError as conv_exc:
        raise HTTPException(status_code=404, detail={"error": True, "message": str(conv_exc)})
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — isolation failure must not kill the answer
        _log.warning("Conversation history resolution failed (%s); using client history.", exc)
        return (req.history or []), None


def _persist_assistant_answer(conversation_id: str | None, answer: str, current: OrgContext) -> None:
    if not conversation_id:
        return
    try:
        from ..services import conversation_service

        conversation_service.append_message(
            conversation_id, "assistant", answer, current.user_id, current.org_id
        )
    except Exception as exc:  # noqa: BLE001
        _log.warning("Assistant answer persistence failed: %s", exc)

_DOC_INTEL_WAIT_ANSWER = (
    "**📄 Document Intelligence Mode**\n\n"
    "*The evaluation is still processing. This answer is being prepared from available "
    "document evidence, trust scores, and stored signals. Please check back in a moment "
    "or refresh the workspace.*\n\n"
    "If this persists, the evaluation run may have encountered an issue. "
    "Open the **Runs** workspace to check status or start a new evaluation."
)


def _make_doc_intel_fallback(
    run_id: str,
    question: str,
    user_id: str | None,
    org_id: str | None = None,
) -> str:
    """Build a Document Intelligence Mode answer from stored evaluation data.

    Tries to load the stored InvestmentBrief and answer deterministically.
    Never raises — always returns a human-readable string.
    """
    try:
        brief_json = get_brief_for_run(run_id, user_id=user_id, org_id=org_id)
        if brief_json is None:
            return _DOC_INTEL_WAIT_ANSWER
        from kulima.models import InvestmentBrief
        brief = InvestmentBrief.model_validate(brief_json) if isinstance(brief_json, dict) else brief_json
        assessment = assessment_adapter.resolve_assessment_for_brief(
            brief.founder_name,
            brief.startup_name,
            run_id=run_id,
            user_id=user_id,
            org_id=org_id,
        )
        assessment_payload = assessment_adapter.serialize_context(assessment) if assessment else None
        # Outcome Layer V1: pass the stored 30-day follow-up so post-decision
        # questions are answered from the record instead of guessed.
        outcome_record = None
        if run_id.isdigit():
            try:
                from kulima.db import IntelligenceRepository
                outcome_record = IntelligenceRepository().ensure_decision_record(int(run_id))
            except Exception:  # noqa: BLE001 — outcome grounding is additive
                outcome_record = None
        return doc_intelligence_ask_ic_answer(
            brief,
            question,
            assessment_context=assessment_payload,
            outcome=outcome_record,
        )
    except Exception as exc:  # noqa: BLE001
        _log.warning("doc_intelligence_ask_ic_answer fallback also failed: %s", exc)
        return _DOC_INTEL_WAIT_ANSWER


@router.post("/ic", response_model=AskResponse)
async def post_ask_ic(req: AskRequest, current: OrgContext = Depends(require_permission(Permission.VIEW))):
    # Rate limit hook (no-op in pre-beta)
    check_rate_limit(current.user_id, "ask_ic:post")
    _enforce_ask_ic_feature(current)

    info = get_run_status(req.runId, current.user_id, org_id=current.org_id)
    if not info:
        raise HTTPException(status_code=401, detail={"error": True, "message": "Unauthorized"})

    # Run still processing — return Document Intelligence Mode answer from whatever is stored
    if info.get("status") != "completed":
        answer = _make_doc_intel_fallback(req.runId, req.question, current.user_id, current.org_id)
        history, conversation_id = _resolve_conversation_history(req, current)
        _persist_assistant_answer(conversation_id, answer, current)
        return {"answer": answer}

    history, conversation_id = _resolve_conversation_history(req, current)
    try:
        answer = ask_ic(req.runId, req.question, history, user_id=current.user_id)
    except Exception as exc:
        _log.warning("ask_ic live failed in router (%s) — activating Document Intelligence Mode.", exc)
        answer = _make_doc_intel_fallback(req.runId, req.question, current.user_id, current.org_id)
    _persist_assistant_answer(conversation_id, answer, current)
    return {"answer": answer}


@router.post('/ic/stream')
async def post_ask_ic_stream(req: AskRequest, current: OrgContext = Depends(require_permission(Permission.VIEW))):
    # Rate limit hook (no-op in pre-beta)
    check_rate_limit(current.user_id, "ask_ic:stream")
    _enforce_ask_ic_feature(current)

    info = get_run_status(req.runId, current.user_id, org_id=current.org_id)
    if not info:
        raise HTTPException(status_code=401, detail={"error": True, "message": "Unauthorized"})

    # Run still processing — stream Document Intelligence Mode answer
    if info.get('status') != 'completed':
        answer = _make_doc_intel_fallback(req.runId, req.question, current.user_id, current.org_id)
        history, conversation_id = _resolve_conversation_history(req, current)
        _persist_assistant_answer(conversation_id, answer, current)
    else:
        history, conversation_id = _resolve_conversation_history(req, current)
        try:
            answer = ask_ic(req.runId, req.question, history, user_id=current.user_id)
        except Exception as exc:
            _log.warning("ask_ic live failed in stream router (%s) — activating Document Intelligence Mode.", exc)
            answer = _make_doc_intel_fallback(req.runId, req.question, current.user_id, current.org_id)
        _persist_assistant_answer(conversation_id, answer, current)

    async def event_stream():
        # Simple tokenizer by words + spaces to keep whitespace
        import re

        tokens = re.findall(r"\S+|\s+", answer)

        i = 0
        n = len(tokens)
        while i < n:
            # chunk size behavior
            if random.random() < 0.05:
                chunk_size = 0
            else:
                chunk_size = max(1, int(random.random() * 5) + 1)
            chunk = ''.join(tokens[i:i+chunk_size])
            i += chunk_size
            data = json.dumps({"text": chunk})
            yield "event: delta\n"
            yield f"data: {data}\n\n"
            # variable delay
            await asyncio.sleep(random.uniform(0.02, 0.18))
            if random.random() < 0.08:
                await asyncio.sleep(random.uniform(0.2, 0.8))
        # complete
        yield 'event: complete\n'
        yield 'data: {}\n\n'

    return StreamingResponse(event_stream(), media_type='text/event-stream')
