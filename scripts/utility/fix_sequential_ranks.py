import sqlite3
import pandas as pd

DB_PATH = 'geo_fresh.db'

def fix_ranks():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("Starting rank normalization for bing_results and bing_deep_hunt...")

    # 1. Fix bing_results (Top 30)
    # We'll use rowid as a tie-breaker to ensure stable sorting
    runs = [r[0] for r in cursor.execute("SELECT DISTINCT run_id FROM bing_results").fetchall()]
    print(f"Processing {len(runs)} runs in bing_results...")
    
    for run_id in runs:
        results = cursor.execute("""
            SELECT rowid, page_num, result_rank 
            FROM bing_results 
            WHERE run_id = ? 
            ORDER BY page_num ASC, result_rank ASC, rowid ASC
        """, (run_id,)).fetchall()
        
        for i, (rowid, page_num, old_rank) in enumerate(results, start=1):
            new_rank = i
            if new_rank != old_rank:
                cursor.execute("UPDATE bing_results SET result_rank = ? WHERE rowid = ?", (new_rank, rowid))

    # 2. Fix bing_deep_hunt (Top 150)
    runs_deep = [r[0] for r in cursor.execute("SELECT DISTINCT run_id FROM bing_deep_hunt").fetchall()]
    print(f"Processing {len(runs_deep)} runs in bing_deep_hunt...")
    
    for run_id in runs_deep:
        results = cursor.execute("""
            SELECT rowid, page_num, absolute_rank 
            FROM bing_deep_hunt 
            WHERE run_id = ? 
            ORDER BY page_num ASC, absolute_rank ASC, rowid ASC
        """, (run_id,)).fetchall()
        
        for i, (rowid, page_num, old_rank) in enumerate(results, start=1):
            new_rank = i
            if new_rank != old_rank:
                cursor.execute("UPDATE bing_deep_hunt SET absolute_rank = ? WHERE rowid = ?", (new_rank, rowid))

    conn.commit()
    conn.close()
    print("Rank normalization complete. All ranks are now strictly sequential (1, 2, 3...) per run.")

if __name__ == "__main__":
    fix_ranks()
