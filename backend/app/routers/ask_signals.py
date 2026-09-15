from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from ..schemas.dtos import AskRequest, AskResponse
from ..services.orchestrator_adapter import ask_signals, get_brief_for_run, get_run_status
from ..core.auth import get_current_user, AuthenticatedUser
from ..core.rate_limit import check_rate_limit
from ..services.demo_chat import doc_intelligence_ask_signals_answer
import asyncio
import json
import logging
import random

_log = logging.getLogger(__name__)

router = APIRouter()

_DOC_INTEL_SIGNALS_WAIT = (
    "**📄 Document Intelligence Mode**\n\n"
    "*The evaluation is still processing. Signal analysis is not yet available. "
    "Please check back in a moment or refresh the Signals workspace.*\n\n"
    "If this persists, open the **Runs** workspace to check evaluation status."
)


def _make_signals_doc_intel_fallback(run_id: str, question: str, user_id: str | None) -> str:
    """Build a Document Intelligence Mode signals answer from stored data. Never raises."""
    try:
        brief_json = get_brief_for_run(run_id, user_id=user_id)
        if brief_json is None:
            return _DOC_INTEL_SIGNALS_WAIT
        from kulima.models import InvestmentBrief
        from kulima.core.cases.adapters import from_investment_brief
        from kulima.signals.orchestrator import SignalsOrchestrator
        brief = InvestmentBrief.model_validate(brief_json) if isinstance(brief_json, dict) else brief_json
        case = from_investment_brief(brief, case_id=run_id)
        signals = SignalsOrchestrator().generate(case, sort=True)
        return doc_intelligence_ask_signals_answer(case, signals, question)
    except Exception as exc:  # noqa: BLE001
        _log.warning("signals doc_intelligence fallback failed: %s", exc)
        return _DOC_INTEL_SIGNALS_WAIT


@router.post("/signals", response_model=AskResponse)
async def post_ask_signals(req: AskRequest, user: AuthenticatedUser = Depends(get_current_user)):
    # Rate limit hook (no-op in pre-beta)
    check_rate_limit(user.user_id, "ask_signals:post")

    info = get_run_status(req.runId, user.user_id)
    if not info:
        raise HTTPException(status_code=401, detail={"error": True, "message": "Unauthorized"})

    if info.get("status") != "completed":
        answer = _make_signals_doc_intel_fallback(req.runId, req.question, user.user_id)
        return {"answer": answer}

    try:
        answer = ask_signals(req.runId, req.question, req.history, user_id=user.user_id)
    except Exception as exc:
        _log.warning("ask_signals live failed in router (%s) — activating Document Intelligence Mode.", exc)
        answer = _make_signals_doc_intel_fallback(req.runId, req.question, user.user_id)
    return {"answer": answer}


@router.post('/signals/stream')
async def post_ask_signals_stream(req: AskRequest, user: AuthenticatedUser = Depends(get_current_user)):
    # Rate limit hook (no-op in pre-beta)
    check_rate_limit(user.user_id, "ask_signals:stream")

    info = get_run_status(req.runId, user.user_id)
    if not info:
        raise HTTPException(status_code=401, detail={"error": True, "message": "Unauthorized"})

    if info.get('status') != 'completed':
        answer = _make_signals_doc_intel_fallback(req.runId, req.question, user.user_id)
    else:
        try:
            answer = ask_signals(req.runId, req.question, req.history, user_id=user.user_id)
        except Exception as exc:
            _log.warning("ask_signals live failed in stream router (%s) — activating Document Intelligence Mode.", exc)
            answer = _make_signals_doc_intel_fallback(req.runId, req.question, user.user_id)

    async def event_stream():
        import re
        tokens = re.findall(r"\S+|\s+", answer)
        i = 0
        n = len(tokens)
        while i < n:
            if random.random() < 0.05:
                chunk_size = 0
            else:
                chunk_size = max(1, int(random.random() * 5) + 1)
            chunk = ''.join(tokens[i:i+chunk_size])
            i += chunk_size
            data = json.dumps({"text": chunk})
            yield "event: delta\n"
            yield f"data: {data}\n\n"
            await asyncio.sleep(random.uniform(0.02, 0.18))
            if random.random() < 0.08:
                await asyncio.sleep(random.uniform(0.2, 0.8))
        yield 'event: complete\n'
        yield 'data: {}\n\n'

    return StreamingResponse(event_stream(), media_type='text/event-stream')
