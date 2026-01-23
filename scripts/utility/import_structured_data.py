import pandas as pd
import sqlite3
import glob
import os
import json

def main():
    db_path = 'geo_fresh.db'
    conn = sqlite3.connect(db_path)
    csv_files = glob.glob('data/ingest/chatgpt_results_*.csv')
    
    all_dfs = []
    for f in csv_files:
        try:
            df = pd.read_csv(f, low_memory=False)
            if 'items_json' in df.columns:
                if 'run_id' not in df.columns:
                    df['run_id'] = df['prompt_id'].astype(str) + '_r' + df['run_number'].astype(str)
                all_dfs.append(df[['run_id', 'items_json', 'response_text']])
        except: pass
    
    mapping = pd.concat(all_dfs).drop_duplicates('run_id')
    cursor = conn.cursor()
    
    # Add columns if missing
    cursor.execute("PRAGMA table_info(runs)")
    cols = [c[1] for c in cursor.fetchall()]
    if 'items_json' not in cols:
        cursor.execute('ALTER TABLE runs ADD COLUMN items_json TEXT')
    if 'response_text' not in cols:
        cursor.execute('ALTER TABLE runs ADD COLUMN response_text TEXT')

    mapping.to_sql('temp_responses', conn, if_exists='replace', index=False)
    cursor.execute('UPDATE runs SET items_json = (SELECT items_json FROM temp_responses WHERE temp_responses.run_id = runs.run_id)')
    cursor.execute('UPDATE runs SET response_text = (SELECT response_text FROM temp_responses WHERE temp_responses.run_id = runs.run_id)')
    cursor.execute('DROP TABLE temp_responses')
    
    conn.commit()
    conn.close()
    print(f"Imported structured items for {len(mapping)} runs.")

if __name__ == "__main__":
    main()
