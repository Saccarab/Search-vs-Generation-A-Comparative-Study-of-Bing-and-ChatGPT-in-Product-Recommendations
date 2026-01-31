import sqlite3
conn=sqlite3.connect('geo_fresh.db')
cur=conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name")
rows=cur.fetchall()
print('\n'.join([r[0] for r in rows]))
