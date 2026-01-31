import sqlite3
db = sqlite3.connect('geo_fresh.db')
rows = db.execute("SELECT query, page_num, COUNT(*) FROM google_results WHERE chatgpt_run_id = 'P001_r1' AND account_type = 'personal' GROUP BY query, page_num").fetchall()
for r in rows:
    print(f"Query: {r[0][:30]}... | Page: {r[1]} | Count: {r[2]}")
