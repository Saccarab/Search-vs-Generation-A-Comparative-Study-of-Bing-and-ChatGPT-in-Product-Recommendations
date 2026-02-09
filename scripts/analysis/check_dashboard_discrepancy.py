import sqlite3

def check_dashboard_counts():
    db = sqlite3.connect('geo_fresh.db')
    db.row_factory = sqlite3.Row
    
    acct = 'personal'
    # Dashboard logic uses chatgpt_run_id join
    # But wait, let's check the citations table run_id vs google_results chatgpt_run_id
    
    print("--- DASHBOARD LOGIC (JOIN ON chatgpt_run_id) ---")
    sql_dash = """
        SELECT g.page_num, g.position, COUNT(DISTINCT c.id) as match_count
        FROM google_results g
        JOIN citations c ON g.chatgpt_run_id = REPLACE(c.run_id, '_personal', '')
          AND c.url_normalized = g.url_normalized
        WHERE g.account_type = 'personal'
          AND c.citation_type = 'cited'
          AND g.result_type = 'organic'
        GROUP BY 1, 2 ORDER BY 1, 2 LIMIT 10
    """
    for r in db.execute(sql_dash).fetchall():
        print(f"p{r['page_num']}_pos{r['position']}: {r['match_count']}")

    print("\n--- GLOBAL RANK LOGIC (JOIN ON global_position) ---")
    sql_global = """
        SELECT g.global_position, COUNT(DISTINCT c.id) as match_count
        FROM google_results g
        JOIN citations c ON g.chatgpt_run_id = REPLACE(c.run_id, '_personal', '')
          AND c.url_normalized = g.url_normalized
        WHERE g.account_type = 'personal'
          AND c.citation_type = 'cited'
          AND g.result_type = 'organic'
        GROUP BY 1 ORDER BY 1 LIMIT 10
    """
    for r in db.execute(sql_global).fetchall():
        print(f"Rank {r['global_position']}: {r['match_count']}")

    db.close()

if __name__ == "__main__":
    check_dashboard_counts()
