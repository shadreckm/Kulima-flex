"""Sub-Task 2 regression tests — Trust Layer database migration.

Validates:
1. initialize() on a brand-new database creates both columns.
2. initialize() on an existing DB without the columns adds them (migration path).
3. initialize() on a DB that already has the columns is a no-op (idempotent).
4. save_brief() with evidence_integrity=None writes NULL to both new columns.
5. save_brief() with a full EvidenceIntegrityReport writes correct values.
6. recent_runs() returns integrity_score and integrity_grade in each row dict.
7. load_brief() on a run saved before migration returns a valid brief with
   evidence_integrity=None (backward compatibility guarantee).
8. load_brief() on a run saved after migration returns a brief with the full
   EvidenceIntegrityReport reconstructed from payload_json.

All tests use in-memory or temporary SQLite databases — no production DB touched.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from kulima.db import IntelligenceRepository
from kulima.models import (
    EvidenceIntegrityReport,
    IntegrityGrade,
    EvidenceDepth,
    ConsistencyStatus,
    InvestmentBrief,
    Recommendation,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _tmp_repo() -> tuple[IntelligenceRepository, Path]:
    """Return a fresh repository backed by a temporary file DB."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    path = Path(tmp.name)
    repo = IntelligenceRepository(db_path=str(path))
    return repo, path


def _minimal_brief(
    founder: str = "Ada Obi",
    startup: str = "PayFast NG",
) -> InvestmentBrief:
    return InvestmentBrief(
        founder_name=founder,
        startup_name=startup,
        sector="Fintech",
        geography="Nigeria",
        stage="Seed",
        overall_score=72.0,
        founder_score=68.0,
        startup_score=74.0,
        market_score=70.0,
        trust_score=65.0,
        risk_score=28.0,
        confidence=0.71,
        recommendation=Recommendation.OBSERVE,
    )


def _brief_with_integrity(
    score: float = 63.0,
    grade: IntegrityGrade = IntegrityGrade.C,
) -> InvestmentBrief:
    brief = _minimal_brief()
    brief.evidence_integrity = EvidenceIntegrityReport(
        integrity_score=score,
        integrity_grade=grade,
        evidence_depth=EvidenceDepth.MODERATE,
        consistency_status=ConsistencyStatus.CONFLICTS,
        sparse_mode=False,
        claim_count=8,
        source_count=6,
        high_authority_count=3,
        integrity_summary="Moderate OSINT coverage with one funding conflict.",
        confidence_adjusted=0.68,
        confidence_delta=-0.03,
    )
    return brief


def _column_names(db_path: str) -> set[str]:
    """Return the set of column names for intelligence_runs."""
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("PRAGMA table_info(intelligence_runs)").fetchall()
        return {row[1] for row in rows}
    finally:
        conn.close()


# ── Test 1 — fresh DB has both columns ───────────────────────────────────────

def test_initialize_creates_both_columns_on_fresh_db() -> None:
    """initialize() on a brand-new database must create integrity_score and
    integrity_grade columns."""
    repo, path = _tmp_repo()
    cols = _column_names(str(path))
    assert "integrity_score" in cols, "integrity_score column must exist after initialize()"
    assert "integrity_grade" in cols, "integrity_grade column must exist after initialize()"


# ── Test 2 — migration on existing DB without columns ────────────────────────

def test_initialize_adds_columns_to_existing_db_without_them() -> None:
    """initialize() on an existing database that was created before the migration
    (no integrity columns) must add both columns without data loss."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name

    # Simulate a pre-migration database: create the schema without the new columns
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS intelligence_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            founder_name TEXT NOT NULL,
            startup_name TEXT NOT NULL,
            sector TEXT,
            geography TEXT,
            stage TEXT,
            overall_score REAL,
            founder_score REAL,
            startup_score REAL,
            market_score REAL,
            trust_score REAL,
            risk_score REAL,
            growth_potential REAL,
            investment_readiness REAL,
            confidence REAL,
            recommendation TEXT,
            executive_summary TEXT,
            payload_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS founders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            founder_name TEXT,
            startup_name TEXT,
            founder_score INTEGER,
            trust_score INTEGER
        );
        CREATE TABLE IF NOT EXISTS run_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            user_name TEXT NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT,
            created_at TEXT NOT NULL
        );
    """)
    # Insert a pre-migration row directly
    conn.execute(
        """INSERT INTO intelligence_runs
           (created_at, founder_name, startup_name, overall_score,
            founder_score, startup_score, market_score, trust_score,
            risk_score, growth_potential, investment_readiness, confidence,
            recommendation, executive_summary, payload_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "2024-01-01T00:00:00+00:00", "Kofi Mensah", "AgriLink GH",
            72.5, 68.0, 74.0, 70.0, 65.0, 28.0, 60.0, 55.0, 0.71,
            "Observe", "Strong agritech play.",
            json.dumps({
                "founder_name": "Kofi Mensah",
                "startup_name": "AgriLink GH",
            }),
        ),
    )
    conn.commit()
    conn.close()

    # Now open via IntelligenceRepository — this triggers initialize() → _migrate_schema()
    repo = IntelligenceRepository(db_path=db_path)

    cols = _column_names(db_path)
    assert "integrity_score" in cols
    assert "integrity_grade" in cols

    # Pre-migration row must still be readable and its new columns must be NULL
    row = repo.get_run(1)
    assert row is not None
    assert row["founder_name"] == "Kofi Mensah"
    assert row["integrity_score"] is None
    assert row["integrity_grade"] is None


# ── Test 3 — idempotent: second initialize() is a no-op ──────────────────────

def test_initialize_is_idempotent() -> None:
    """Calling initialize() twice (i.e. _migrate_schema runs twice) must not
    raise an error and must not duplicate columns."""
    repo, path = _tmp_repo()

    # Call initialize() a second time explicitly
    repo.initialize()

    # Column set must be unchanged — no duplicates, no errors
    cols = _column_names(str(path))
    assert "integrity_score" in cols
    assert "integrity_grade" in cols

    # SQLite does not allow duplicate column names — the fact that it didn't
    # raise is the primary assertion here; double-check via PRAGMA count
    conn = sqlite3.connect(str(path))
    try:
        rows = conn.execute("PRAGMA table_info(intelligence_runs)").fetchall()
        col_names = [r[1] for r in rows]
    finally:
        conn.close()
    assert col_names.count("integrity_score") == 1
    assert col_names.count("integrity_grade") == 1


# ── Test 4 — save_brief with evidence_integrity=None writes NULL ──────────────

def test_save_brief_without_integrity_writes_null() -> None:
    """save_brief() with a brief that has evidence_integrity=None must write
    NULL to both new columns."""
    repo, path = _tmp_repo()
    brief = _minimal_brief()
    assert brief.evidence_integrity is None

    run_id = repo.save_brief(brief)
    row = repo.get_run(run_id)

    assert row is not None
    assert row["integrity_score"] is None
    assert row["integrity_grade"] is None
    # Core fields untouched
    assert row["founder_name"] == "Ada Obi"
    assert row["overall_score"] == pytest.approx(72.0)


# ── Test 5 — save_brief with full EvidenceIntegrityReport writes values ───────

def test_save_brief_with_integrity_writes_correct_values() -> None:
    """save_brief() with a full EvidenceIntegrityReport must persist the flat
    integrity_score and integrity_grade columns correctly."""
    repo, path = _tmp_repo()
    brief = _brief_with_integrity(score=63.0, grade=IntegrityGrade.C)

    run_id = repo.save_brief(brief)
    row = repo.get_run(run_id)

    assert row is not None
    assert row["integrity_score"] == pytest.approx(63.0)
    assert row["integrity_grade"] == "C"


def test_save_brief_grade_a_writes_correctly() -> None:
    """Grade A report (score=92) must persist 92.0 / 'A'."""
    repo, path = _tmp_repo()
    brief = _brief_with_integrity(score=92.0, grade=IntegrityGrade.A)

    run_id = repo.save_brief(brief)
    row = repo.get_run(run_id)

    assert row["integrity_score"] == pytest.approx(92.0)
    assert row["integrity_grade"] == "A"


# ── Test 6 — recent_runs() returns integrity columns ─────────────────────────

def test_recent_runs_returns_integrity_columns() -> None:
    """recent_runs() must include integrity_score and integrity_grade in every
    returned row dict."""
    repo, path = _tmp_repo()

    # Save one brief without integrity and one with
    repo.save_brief(_minimal_brief(founder="Alice N", startup="Startup A"))
    repo.save_brief(_brief_with_integrity())

    rows = repo.recent_runs(limit=10)
    assert len(rows) == 2

    for row in rows:
        assert "integrity_score" in row, "integrity_score key must be present"
        assert "integrity_grade" in row, "integrity_grade key must be present"

    # The brief with integrity should have values; the one without should have NULL
    # recent_runs returns newest first
    assert rows[0]["integrity_score"] == pytest.approx(63.0)
    assert rows[0]["integrity_grade"] == "C"
    assert rows[1]["integrity_score"] is None
    assert rows[1]["integrity_grade"] is None

    # Existing keys must still be present (no regression)
    for row in rows:
        for key in ("id", "created_at", "founder_name", "startup_name",
                    "overall_score", "founder_score", "trust_score",
                    "recommendation", "confidence"):
            assert key in row, f"existing key '{key}' must still be present"


# ── Test 7 — load_brief on pre-migration row returns brief with None ──────────

def test_load_brief_on_pre_migration_row_returns_brief_with_none() -> None:
    """A brief saved before the migration (no evidence_integrity in payload_json)
    must load cleanly with evidence_integrity=None."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name

    # Build a legacy payload that has no evidence_integrity key at all
    legacy_payload = {
        "founder_name": "Wanjiru M",
        "startup_name": "MobiCash KE",
        "sector": "Fintech",
        "overall_score": 74.0,
        "founder_score": 70.0,
        "startup_score": 76.0,
        "market_score": 72.0,
        "trust_score": 67.0,
        "risk_score": 25.0,
        "confidence": 0.74,
        "recommendation": "Invest",
        # Deliberately no "evidence_integrity" key
    }

    # Write directly into the database bypassing IntelligenceRepository
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS intelligence_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            founder_name TEXT NOT NULL,
            startup_name TEXT NOT NULL,
            sector TEXT, geography TEXT, stage TEXT,
            overall_score REAL, founder_score REAL, startup_score REAL,
            market_score REAL, trust_score REAL, risk_score REAL,
            growth_potential REAL, investment_readiness REAL, confidence REAL,
            recommendation TEXT, executive_summary TEXT,
            payload_json TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS founders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            founder_name TEXT, startup_name TEXT,
            founder_score INTEGER, trust_score INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS run_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            user_name TEXT NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute(
        """INSERT INTO intelligence_runs
           (created_at, founder_name, startup_name, overall_score,
            founder_score, startup_score, market_score, trust_score,
            risk_score, growth_potential, investment_readiness, confidence,
            recommendation, executive_summary, payload_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "2024-06-01T00:00:00+00:00",
            legacy_payload["founder_name"],
            legacy_payload["startup_name"],
            legacy_payload["overall_score"],
            legacy_payload["founder_score"],
            legacy_payload["startup_score"],
            legacy_payload["market_score"],
            legacy_payload["trust_score"],
            legacy_payload["risk_score"],
            0.0, 0.0,
            legacy_payload["confidence"],
            legacy_payload["recommendation"],
            "",
            json.dumps(legacy_payload),
        ),
    )
    conn.commit()
    conn.close()

    # Open via IntelligenceRepository (triggers migration)
    repo = IntelligenceRepository(db_path=db_path)

    brief = repo.load_brief(1)
    assert brief is not None
    assert brief.founder_name == "Wanjiru M"
    assert brief.overall_score == pytest.approx(74.0)
    # The critical backward-compat assertion
    assert brief.evidence_integrity is None


# ── Test 8 — load_brief on post-migration row returns full report ─────────────

def test_load_brief_on_post_migration_row_returns_full_report() -> None:
    """A brief saved after the migration with a full EvidenceIntegrityReport must
    reconstruct the full report from payload_json on load."""
    repo, path = _tmp_repo()
    brief_saved = _brief_with_integrity(score=78.5, grade=IntegrityGrade.B)

    run_id = repo.save_brief(brief_saved)
    brief_loaded = repo.load_brief(run_id)

    assert brief_loaded is not None
    assert brief_loaded.evidence_integrity is not None
    ei = brief_loaded.evidence_integrity
    assert ei.integrity_score == pytest.approx(78.5)
    assert ei.integrity_grade == IntegrityGrade.B
    assert ei.evidence_depth == EvidenceDepth.MODERATE
    assert ei.consistency_status == ConsistencyStatus.CONFLICTS
    assert ei.sparse_mode is False
    assert ei.source_count == 6


# ── Test 9 — archive/reopen/delete and feedback capture ───────────────────────

def test_archive_reopen_delete_and_feedback() -> None:
    repo, path = _tmp_repo()
    brief = _minimal_brief(founder="Pilot Founder", startup="Pilot Startup")
    run_id = repo.save_brief(brief)

    assert repo.archive_run(run_id) is True
    archived = repo.get_run(run_id)
    assert archived is not None and archived["archived_at"] is not None

    active_rows = repo.recent_runs(limit=10)
    assert all(r["id"] != run_id for r in active_rows)

    reopened = repo.reopen_run(run_id)
    assert reopened is True
    reopened_row = repo.get_run(run_id)
    assert reopened_row is not None and reopened_row["archived_at"] is None

    feedback_id = repo.save_feedback(run_id, "A. Pilot", 5, "Strong pilot-ready output.")
    assert feedback_id > 0
    conn = sqlite3.connect(str(path))
    try:
        row = conn.execute("SELECT run_id, user_name, rating, comment FROM run_feedback WHERE id = ?", (feedback_id,)).fetchone()
    finally:
        conn.close()
    assert row == (run_id, "A. Pilot", 5, "Strong pilot-ready output.")

    assert repo.delete_run(run_id) is True
    assert repo.get_run(run_id) is None
