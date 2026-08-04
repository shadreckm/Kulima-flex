from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from ..schemas.dtos import AskRequest, AskResponse
from ..services.orchestrator_adapter import ask_signals, get_run_status
from ..core.auth import get_current_user, AuthenticatedUser
from ..core.rate_limit import check_rate_limit
import asyncio
import json
import random

router = APIRouter()


@router.post("/signals", response_model=AskResponse)
async def post_ask_signals(req: AskRequest, user: AuthenticatedUser = Depends(get_current_user)):
    # Rate limit hook (no-op in pre-beta)
    check_rate_limit(user.user_id, "ask_signals:post")

    info = get_run_status(req.runId, user.user_id)
    if not info:
        raise HTTPException(status_code=401, detail={"error": True, "message": "Unauthorized"})
    if info.get("status") != "completed":
        raise HTTPException(status_code=409, detail="run not completed yet")
    try:
        answer = ask_signals(req.runId, req.question, req.history, user_id=user.user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"answer": answer}


@router.post('/signals/stream')
async def post_ask_signals_stream(req: AskRequest, user: AuthenticatedUser = Depends(get_current_user)):
    # Rate limit hook (no-op in pre-beta)
    check_rate_limit(user.user_id, "ask_signals:stream")

    info = get_run_status(req.runId, user.user_id)
    if not info:
        raise HTTPException(status_code=401, detail={"error": True, "message": "Unauthorized"})
    if info.get('status') != 'completed':
        raise HTTPException(status_code=409, detail='run not completed yet')

    try:
        answer = ask_signals(req.runId, req.question, req.history, user_id=user.user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

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
            yield f"event: delta\n"
            yield f"data: {data}\n\n"
            await asyncio.sleep(random.uniform(0.02, 0.18))
            if random.random() < 0.08:
                await asyncio.sleep(random.uniform(0.2, 0.8))
        yield 'event: complete\n'
        yield 'data: {}\n\n'

    return StreamingResponse(event_stream(), media_type='text/event-stream')
