import sqlite3
import json

def get_bing_google_alignment():
    db = sqlite3.connect('geo_fresh.db')
    db.row_factory = sqlite3.Row
    
    results = {}
    
    for acct in ['enterprise', 'personal']:
        rid_sql = "REPLACE(b.run_id, '_personal', '')" if acct == 'personal' else "b.run_id"
        
        # Query: For all URLs on Bing Page 1, what is their Google Rank?
        sql = f"""
            SELECT g.global_position, COUNT(*) as count
            FROM bing_results b
            JOIN google_results g ON g.chatgpt_run_id = {rid_sql} 
              AND g.url_normalized = b.url_normalized
            WHERE b.account_type = ? 
              AND g.account_type = ?
              AND g.result_type = 'organic'
              AND b.page_num = 1
            GROUP BY g.global_position
            ORDER BY g.global_position
        """
        
        rows = db.execute(sql, (acct, acct)).fetchall()
        results[acct] = {r['global_position']: r['count'] for r in rows}
    
    db.close()
    return results

if __name__ == "__main__":
    data = get_bing_google_alignment()
    ent = data['enterprise']
    pers = data['personal']
    
    all_ranks = sorted(set(list(ent.keys()) + list(pers.keys())))
    
    print("| Google Rank | Enterprise (Bing P1 URLs) | Personal (Bing P1 URLs) |")
    print("| :--- | ---: | ---: |")
    for r in all_ranks:
        if r > 30: break
        print(f"| Rank {r} | {ent.get(r, 0):,} | {pers.get(r, 0):,} |")
