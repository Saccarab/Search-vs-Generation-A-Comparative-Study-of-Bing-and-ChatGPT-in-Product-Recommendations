import sqlite3
db = sqlite3.connect('geo_fresh.db')
db.row_factory = sqlite3.Row

print("Query distribution for first 10 personal runs:")
runs = db.execute("SELECT DISTINCT chatgpt_run_id FROM google_results WHERE account_type = 'personal' LIMIT 10").fetchall()

for run in runs:
    rid = run['chatgpt_run_id']
    queries = db.execute("SELECT query, COUNT(*) as cnt FROM google_results WHERE chatgpt_run_id = ? AND account_type = 'personal' GROUP BY query", (rid,)).fetchall()
    print(f"\nRun: {rid}")
    for q in queries:
        print(f"  - {q['cnt']:2} results: {q['query']}")
