"""Check the status of the E2E validation run."""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kulima.config import get_settings

RUN_PREFIX = sys.argv[1] if len(sys.argv) > 1 else "26bcf7f4"

conn = sqlite3.connect(get_settings().db_path)
conn.row_factory = sqlite3.Row
r = conn.execute(
    "SELECT * FROM api_runs WHERE run_id LIKE ?", (RUN_PREFIX + "%",)
).fetchone()
if r is None:
    print("RUN_NOT_FOUND")
    raise SystemExit(0)
print("status:", r["status"], "| error:", r["error_message"],
      "| completed_at:", r["completed_at"], "| db_id:", r["db_id"])
