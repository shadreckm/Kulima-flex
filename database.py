import sqlite3

conn = sqlite3.connect("founders.db")

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS founders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    founder_name TEXT,
    startup_name TEXT,
    founder_score INTEGER,
    trust_score INTEGER
)
""")

conn.commit()
conn.close()

print("Database recreated successfully")