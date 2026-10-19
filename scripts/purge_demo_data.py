"""One-time cleanup: remove seeded OSTX/pilot demo rows from all databases.

The auto-seeder previously inserted shared demo cases
(AgriNova, GreenLink, SolarHarvest, pilot-* rows) with user_id NULL.
This script thoroughly purges them from both root founders.db and backend/founders.db.
"""
from __future__ import annotations

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEMO_KEYWORDS = [
    "agrinova",
    "ostx",
    "greenlink",
    "solarharvest",
    "nilepay",
    "farmstack",
]

TARGET_DBS = ["founders.db", "backend/founders.db"]

for db_rel in TARGET_DBS:
    db_path = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), db_rel))
    if not os.path.exists(db_path):
        continue
    print(f"\n--- Purging demo data from {db_path} ---")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Delete by IDs <= 5
    cur = conn.cursor()
    cur.execute("DELETE FROM intelligence_runs WHERE id <= 5")
    print(f"Deleted {cur.rowcount} legacy low-id rows from intelligence_runs")

    # Delete any runs mentioning demo entities in startup_name or founder_name
    for kw in DEMO_KEYWORDS:
        cur.execute("DELETE FROM intelligence_runs WHERE LOWER(startup_name) LIKE ? OR LOWER(founder_name) LIKE ?", (f"%{kw}%", f"%{kw}%"))
        if cur.rowcount:
            print(f"Deleted {cur.rowcount} rows matching '{kw}' from intelligence_runs")

    # Delete shared demo api_runs
    cur.execute("DELETE FROM api_runs WHERE user_id IS NULL")
    print(f"Deleted {cur.rowcount} NULL-user api_runs")
    for kw in DEMO_KEYWORDS:
        cur.execute("DELETE FROM api_runs WHERE LOWER(run_id) LIKE ?", (f"%{kw}%",))
        if cur.rowcount:
            print(f"Deleted {cur.rowcount} rows matching '{kw}' from api_runs")

    # Delete demo assessment contexts if any
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='assessment_contexts'")
    if cur.fetchone():
        for kw in DEMO_KEYWORDS:
            cur.execute("DELETE FROM assessment_contexts WHERE LOWER(assessment_id) LIKE ? OR LOWER(payload_json) LIKE ?", (f"%{kw}%", f"%{kw}%"))
            if cur.rowcount:
                print(f"Deleted {cur.rowcount} rows matching '{kw}' from assessment_contexts")

    # Delete demo feedback if any
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='run_feedback'")
    if cur.fetchone():
        cur.execute("DELETE FROM run_feedback WHERE run_id <= 5")
        if cur.rowcount:
            print(f"Deleted {cur.rowcount} low-id rows from run_feedback")

    conn.commit()
    conn.close()

print("\nALL_DEMO_DATA_PURGED_SUCCESSFULLY")
