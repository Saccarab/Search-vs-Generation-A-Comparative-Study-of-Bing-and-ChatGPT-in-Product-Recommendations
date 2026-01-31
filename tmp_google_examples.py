import sqlite3
conn = sqlite3.connect('geo_fresh.db')
conn.row_factory = sqlite3.Row
q = """
SELECT c.domain, c.url, c.run_id
FROM citations c
JOIN runs r ON r.run_id = c.run_id
LEFT JOIN bing_results b ON b.run_id = c.run_id AND b.url_normalized = c.url_normalized
JOIN google_results g ON g.chatgpt_run_id = REPLACE(c.run_id,'_personal','')
  AND g.account_type = r.account_type
  AND LOWER(REPLACE(REPLACE(REPLACE(g.url,'https://',''),'http://',''),'www.','')) = c.url_normalized
WHERE r.account_type = 'personal'
  AND c.citation_type = 'cited'
  AND b.url_normalized IS NULL
GROUP BY c.url
LIMIT 12
"""
rows = conn.execute(q).fetchall()
print('Examples (Google-only vs Bing) personal cited:')
for r in rows:
    print(f"- {r['domain']} | {r['url']} | {r['run_id']}")
conn.close()
