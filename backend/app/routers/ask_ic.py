from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from ..schemas.dtos import AskRequest, AskResponse
from ..services.orchestrator_adapter import ask_ic, get_brief_for_run, get_run_status
from ..core.auth import OrgContext, require_permission
from ..core.rate_limit import check_rate_limit
from ..services.demo_chat import doc_intelligence_ask_ic_answer
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

_DOC_INTEL_WAIT_ANSWER = (
    "**📄 Document Intelligence Mode**\n\n"
    "*The evaluation is still processing. This answer is being prepared from available "
    "document evidence, trust scores, and stored signals. Please check back in a moment "
    "or refresh the workspace.*\n\n"
    "If this persists, the evaluation run may have encountered an issue. "
    "Open the **Runs** workspace to check status or start a new evaluation."
)


def _make_doc_intel_fallback(run_id: str, question: str, user_id: str | None) -> str:
    """Build a Document Intelligence Mode answer from stored evaluation data.

    Tries to load the stored InvestmentBrief and answer deterministically.
    Never raises — always returns a human-readable string.
    """
    try:
        brief_json = get_brief_for_run(run_id, user_id=user_id)
        if brief_json is None:
            return _DOC_INTEL_WAIT_ANSWER
        from kulima.models import InvestmentBrief
        brief = InvestmentBrief.model_validate(brief_json) if isinstance(brief_json, dict) else brief_json
        return doc_intelligence_ask_ic_answer(brief, question)
    except Exception as exc:  # noqa: BLE001
        _log.warning("doc_intelligence_ask_ic_answer fallback also failed: %s", exc)
        return _DOC_INTEL_WAIT_ANSWER


@router.post("/ic", response_model=AskResponse)
async def post_ask_ic(req: AskRequest, current: OrgContext = Depends(require_permission(Permission.VIEW))):
    # Rate limit hook (no-op in pre-beta)
    check_rate_limit(current.user_id, "ask_ic:post")
    _enforce_ask_ic_feature(current)

    info = get_run_status(req.runId, current.user_id)
    if not info:
        raise HTTPException(status_code=401, detail={"error": True, "message": "Unauthorized"})

    # Run still processing — return Document Intelligence Mode answer from whatever is stored
    if info.get("status") != "completed":
        answer = _make_doc_intel_fallback(req.runId, req.question, current.user_id)
        return {"answer": answer}

    try:
        answer = ask_ic(req.runId, req.question, req.history, user_id=current.user_id)
    except Exception as exc:
        _log.warning("ask_ic live failed in router (%s) — activating Document Intelligence Mode.", exc)
        answer = _make_doc_intel_fallback(req.runId, req.question, current.user_id)
    return {"answer": answer}


@router.post('/ic/stream')
async def post_ask_ic_stream(req: AskRequest, current: OrgContext = Depends(require_permission(Permission.VIEW))):
    # Rate limit hook (no-op in pre-beta)
    check_rate_limit(current.user_id, "ask_ic:stream")
    _enforce_ask_ic_feature(current)

    info = get_run_status(req.runId, current.user_id)
    if not info:
        raise HTTPException(status_code=401, detail={"error": True, "message": "Unauthorized"})

    # Run still processing — stream Document Intelligence Mode answer
    if info.get('status') != 'completed':
        answer = _make_doc_intel_fallback(req.runId, req.question, current.user_id)
    else:
        try:
            answer = ask_ic(req.runId, req.question, req.history, user_id=current.user_id)
        except Exception as exc:
            _log.warning("ask_ic live failed in stream router (%s) — activating Document Intelligence Mode.", exc)
            answer = _make_doc_intel_fallback(req.runId, req.question, current.user_id)

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
