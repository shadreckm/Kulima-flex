"""One-time cleanup: remove seeded OSTX/pilot demo rows from the database.

The auto-seeder (kulima.db._auto_seed_demo_data) inserted shared demo cases
(AgriNova, GreenLink, SolarHarvest, pilot-* rows) with user_id NULL, which the
run resolver treats as visible to everyone — the "Demo Mode / AgriNova" leak.
This script deletes them. The seeder itself is disabled in kulima/db.py.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3

from kulima.config import get_settings

conn = sqlite3.connect(get_settings().db_path)
conn.row_factory = sqlite3.Row

# 1. Delete demo brief payloads (OSTX seed rows are ids 1–5).
demo_rows = [r["id"] for r in conn.execute("SELECT id FROM intelligence_runs WHERE id <= 5")]
if demo_rows:
    conn.executemany("DELETE FROM intelligence_runs WHERE id=?", [(i,) for i in demo_rows])
    print("deleted seeded demo brief rows:", demo_rows)

# 2. Delete shared demo api_runs (user_id NULL).
conn.execute("DELETE FROM api_runs WHERE user_id IS NULL")
conn.commit()
print("remaining NULL-user api_runs:", conn.execute(
    "SELECT COUNT(*) FROM api_runs WHERE user_id IS NULL").fetchone()[0])
print("DEMO_DATA_PURGED")
