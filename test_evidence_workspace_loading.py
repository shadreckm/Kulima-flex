from __future__ import annotations

import tempfile
from pathlib import Path

from backend.app.routers import intelligence as intelligence_router
from kulima.db import IntelligenceRepository
from test_db_trust_layer import _minimal_brief


def test_load_brief_model_loads_stored_run_without_live_mapping() -> None:
    tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    tmp.close()
    db_path = Path(tmp.name)

    repo = IntelligenceRepository(db_path=str(db_path))
    brief = _minimal_brief(founder='Amina K', startup='Atlas Health')
    run_id = repo.save_brief(brief, user_id='user-a')

    original_brief_repo = intelligence_router._brief_repo
    original_get_brief_for_run = intelligence_router.get_brief_for_run
    try:
        intelligence_router._brief_repo = repo
        intelligence_router.get_brief_for_run = lambda *args, **kwargs: None

        loaded = intelligence_router._load_brief_model(run_id, user_id='user-a')
        assert loaded is not None
        assert loaded.founder_name == 'Amina K'
        assert loaded.startup_name == 'Atlas Health'
    finally:
        intelligence_router._brief_repo = original_brief_repo
        intelligence_router.get_brief_for_run = original_get_brief_for_run
