from __future__ import annotations

import threading
import uuid
import logging
from typing import Dict, Any, Optional

from kulima.agents.orchestrator import IntelligenceOrchestrator
from kulima.core.cases.adapters import from_investment_brief
from kulima.db import IntelligenceRepository
from kulima.models import InvestmentBrief
from kulima.signals.ask_signals import answer_ask_signals_question
from kulima.signals.orchestrator import SignalsOrchestrator
from .run_repository import RunRepository

_log = logging.getLogger(__name__)

_orchestrator = IntelligenceOrchestrator()
_signals_orchestrator = SignalsOrchestrator()
_repo = IntelligenceRepository()
_run_repo = RunRepository()


def start_intelligence_run(founder: str, startup: str, user_id: str | None = None) -> str:
    run_id = str(uuid.uuid4())
    # Persist run record so it survives restarts
    _run_repo.create_run(run_id, status="running", user_id=user_id)

    def _worker(rid: str, founder: str, startup: str) -> None:
        try:
            _log.info("Orchestrator: starting analysis for %s / %s", founder, startup)
            brief: InvestmentBrief = _orchestrator.analyze(founder, startup)
            # Persist to DB (synchronous)
            db_id = _repo.save_brief(brief)
            # Mark run completed in persistent store
            _run_repo.update_run_completed(rid, db_id=db_id)
            _log.info("Orchestrator: analysis complete — run_id=%s db_id=%s", rid, db_id)
        except Exception as exc:  # pragma: no cover - surface errors
            _log.exception("Orchestrator worker failed: %s", exc)
            _run_repo.update_run_failed(rid, error_message=str(exc))

    t = threading.Thread(target=_worker, args=(run_id, founder, startup), daemon=True)
    t.start()
    return run_id


def get_run_status(run_id: str) -> Optional[Dict[str, Any]]:
    # Return persistent run record
    return _run_repo.get_run(run_id)


def get_brief_for_run(run_id: str) -> Optional[InvestmentBrief | dict]:
    info = _run_repo.get_run(run_id)
    if not info:
        return None
    db_id = info.get("db_id")
    if db_id:
        brief = _repo.load_brief(db_id)
        if brief:
            try:
                return brief.model_dump(mode="json")
            except Exception:
                return None
    return None


def ask_ic(run_id: str, question: str, history: list[dict] | None = None) -> str:
    # Lazy-load brief
    brief_json = get_brief_for_run(run_id)
    if brief_json is None:
        raise RuntimeError("Run not complete or not found")
    # Rehydrate into InvestmentBrief if needed
    from kulima.models import InvestmentBrief

    if isinstance(brief_json, dict):
        brief = InvestmentBrief.model_validate(brief_json)
    else:
        # If already an InvestmentBrief object (unlikely), return directly
        brief = brief_json
    from kulima.ask_ic import answer_ask_ic_question

    return answer_ask_ic_question(brief, question, history)


def ask_signals(run_id: str, question: str, history: list[dict] | None = None) -> str:
    # Signals handler mirrors ask_ic but routes to signals logic.
    # Rebuild the Case envelope expected by the SIGNALS analyst from the
    # stored InvestmentBrief without changing the signal methodology.
    brief_json = get_brief_for_run(run_id)
    if brief_json is None:
        raise RuntimeError("Run not complete or not found")

    if isinstance(brief_json, dict):
        brief = InvestmentBrief.model_validate(brief_json)
    else:
        brief = brief_json

    case = from_investment_brief(brief, case_id=run_id)
    signals = _signals_orchestrator.generate(case, sort=True)
    return answer_ask_signals_question(case, signals, question, history)
