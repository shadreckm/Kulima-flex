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

    def _worker(rid: str, founder: str, startup: str, owner_id: str | None) -> None:
        try:
            _log.info("Orchestrator: starting analysis for %s / %s", founder, startup)
            brief: InvestmentBrief = _orchestrator.analyze(founder, startup, user_id=owner_id)
            # Persist to DB (synchronous)
            db_id = _repo.save_brief(brief, user_id=owner_id)
            # Mark run completed in persistent store
            _run_repo.update_run_completed(rid, db_id=db_id)
            _log.info("Orchestrator: analysis complete — run_id=%s db_id=%s", rid, db_id)
        except Exception as exc:  # noqa: BLE001
            _log.warning("Orchestrator live analysis failed (%s) — activating offline demo fallback.", exc)
            try:
                brief = _get_offline_fallback_brief(founder, startup)
                db_id = _repo.save_brief(brief, user_id=owner_id)
                _run_repo.update_run_completed(rid, db_id=db_id)
                _log.info("Orchestrator: offline fallback complete — run_id=%s db_id=%s", rid, db_id)
            except Exception as fallback_exc:  # noqa: BLE001
                _log.exception("Orchestrator fallback also failed: %s", fallback_exc)
                _run_repo.update_run_failed(rid, error_message=str(exc))

    t = threading.Thread(target=_worker, args=(run_id, founder, startup, user_id), daemon=True)
    t.start()
    return run_id


def _get_offline_fallback_brief(founder: str, startup: str) -> InvestmentBrief:
    """Return a demo brief adapted from the OSTX seed dataset for offline mode.

    Picks the closest existing demo run from the DB (by sector/stage heuristic)
    and patches the founder/startup name + prepends the offline-mode banner to
    the executive_summary so the IC workflow can continue end-to-end.
    """
    import copy

    # Pull all completed runs; prefer the INVEST-grade one as the default demo.
    recent = _repo.recent_runs(limit=50)
    demo_run: dict | None = None
    for row in recent:
        # Prefer AgriNova Malawi (INVEST) as the flagship fallback demo.
        if "agrinova" in str(row.get("startup_name", "")).lower():
            demo_run = dict(row)
            break
    if demo_run is None and recent:
        demo_run = dict(recent[0])

    if demo_run is not None:
        db_id = demo_run.get("id")
        base_brief = _repo.load_brief(db_id) if db_id else None
    else:
        base_brief = None

    if base_brief is None:
        # Last-resort: import fresh from seed module
        from scripts.seed_demo_data import build_agrinova_malawi_brief  # noqa: PLC0415
        base_brief = build_agrinova_malawi_brief()

    # Deep-copy and patch names + offline banner
    brief_data = base_brief.model_dump(mode="json")
    brief_data["founder_name"] = founder
    brief_data["startup_name"] = startup
    offline_banner = (
        "⚡ Demo Analysis Generated — Offline Intelligence Mode Active. "
        "Live OSINT and LLM APIs are currently unavailable. "
        "The following analysis is based on the OSTX Validation Dataset template.\n\n"
    )
    brief_data["executive_summary"] = offline_banner + str(brief_data.get("executive_summary", ""))
    return InvestmentBrief.model_validate(brief_data)



def _resolve_run_record(run_id: str, user_id: str | None = None) -> Optional[Dict[str, Any]]:
    """Resolve a live api_runs row, including shared demo rows (user_id NULL)."""
    info = _run_repo.get_run(run_id, user_id=user_id)
    if info is None and user_id is not None:
        legacy = _run_repo.get_run(run_id)
        if legacy is not None and legacy.get("user_id") is None:
            info = legacy
    if info is not None:
        return info

    # Allow Flex/Signals URL sync with stored intelligence run integer IDs.
    if str(run_id).isdigit():
        db_id = int(run_id)
        row = _repo.get_run(db_id, user_id=user_id)
        if row is None and user_id is not None:
            legacy_row = _repo.get_run(db_id)
            if legacy_row is not None and legacy_row.get("user_id") is None:
                row = legacy_row
        if row is not None:
            return {
                "run_id": str(run_id),
                "status": "completed",
                "created_at": row.get("created_at"),
                "completed_at": row.get("created_at"),
                "db_id": db_id,
                "error_message": None,
                "user_id": row.get("user_id"),
            }
    return None


def get_run_status(run_id: str, user_id: str | None = None) -> Optional[Dict[str, Any]]:
    return _resolve_run_record(run_id, user_id=user_id)


def get_brief_for_run(run_id: str, user_id: str | None = None) -> Optional[InvestmentBrief | dict]:
    info = _resolve_run_record(run_id, user_id=user_id)
    if not info:
        return None
    db_id = info.get("db_id")
    if db_id:
        brief = _repo.load_brief(int(db_id))
        if brief:
            try:
                return brief.model_dump(mode="json")
            except Exception:
                return None
    return None


def ask_ic(
    run_id: str,
    question: str,
    history: list[dict] | None = None,
    user_id: str | None = None,
) -> str:
    # Lazy-load brief
    brief_json = get_brief_for_run(run_id, user_id=user_id)
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

    return answer_ask_ic_question(brief, question, history, run_id=None, user_id=user_id)


def ask_signals(
    run_id: str,
    question: str,
    history: list[dict] | None = None,
    user_id: str | None = None,
) -> str:
    # Signals handler mirrors ask_ic but routes to signals logic.
    # Rebuild the Case envelope expected by the SIGNALS analyst from the
    # stored InvestmentBrief without changing the signal methodology.
    brief_json = get_brief_for_run(run_id, user_id=user_id)
    if brief_json is None:
        raise RuntimeError("Run not complete or not found")

    if isinstance(brief_json, dict):
        brief = InvestmentBrief.model_validate(brief_json)
    else:
        brief = brief_json

    case = from_investment_brief(brief, case_id=run_id)
    signals = _signals_orchestrator.generate(case, sort=True)
    return answer_ask_signals_question(case, signals, question, history, user_id=user_id)
