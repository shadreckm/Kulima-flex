import sqlite3
import json
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / 'founders.db'
if not DB.exists():
    print('No DB at', DB)
    raise SystemExit(0)

conn = sqlite3.connect(str(DB))
cur = conn.cursor()
cur.execute('SELECT id, created_at, founder_name, startup_name, executive_summary, payload_json FROM intelligence_runs ORDER BY id DESC LIMIT 20')
rows = cur.fetchall()
print('Checked DB:', DB)
for r in rows:
    id_, created_at, founder, startup, exec_sum, payload = r
    flags = []
    if payload and ('&lt;' in payload or '&gt;' in payload or '&amp;' in payload):
        flags.append('escaped_entities_in_payload')
    if payload and ('<div' in payload or '<span' in payload or '<br' in payload):
        flags.append('contains_html_tags_in_payload')
    if exec_sum and ('&lt;' in exec_sum or '&gt;' in exec_sum):
        flags.append('escaped_entities_in_exec_sum')
    if exec_sum and ('<div' in exec_sum or '<span' in exec_sum or '<br' in exec_sum):
        flags.append('contains_html_tags_in_exec_sum')
    if flags:
        print(f'RUN {id_} {created_at} {founder} / {startup} FLAGS: {flags}')
        if payload:
            print('payload sample:', payload[:1000])
        if exec_sum:
            print('exec summary:', exec_sum[:1000])
    else:
        print(f'RUN {id_} OK {id_} {founder} / {startup}')

conn.close()
