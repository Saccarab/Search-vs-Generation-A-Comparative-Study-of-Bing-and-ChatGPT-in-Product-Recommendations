import pandas as pd
import sqlite3
import glob
import os

def main():
    db_path = 'geo_fresh.db'
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    csv_files = glob.glob('data/ingest/chatgpt_results_*.csv')
    
    all_dfs = []
    for f in csv_files:
        try:
            # Some CSVs might have different encoding or issues, use low_memory=False
            df = pd.read_csv(f, low_memory=False)
            if 'response_text' in df.columns:
                if 'run_id' not in df.columns:
                    if 'prompt_id' in df.columns and 'run_number' in df.columns:
                        df['run_id'] = df['prompt_id'].astype(str) + '_r' + df['run_number'].astype(str)
                    else:
                        continue
                all_dfs.append(df[['run_id', 'response_text']])
        except Exception as e:
            print(f"Skipping {f}: {e}")
    
    if not all_dfs:
        print("No response_text found in CSVs.")
        return

    mapping = pd.concat(all_dfs).drop_duplicates('run_id')
    print(f"Found {len(mapping)} unique responses in CSVs.")

    cursor = conn.cursor()
    # Check if column exists
    cursor.execute("PRAGMA table_info(runs)")
    cols = [c[1] for c in cursor.fetchall()]
    if 'response_text' not in cols:
        print("Adding response_text column to runs table...")
        cursor.execute('ALTER TABLE runs ADD COLUMN response_text TEXT')

    mapping.to_sql('temp_responses', conn, if_exists='replace', index=False)
    
    print("Updating runs table...")
    cursor.execute('''
        UPDATE runs 
        SET response_text = (
            SELECT response_text 
            FROM temp_responses 
            WHERE temp_responses.run_id = runs.run_id
        )
    ''')
    
    cursor.execute('DROP TABLE temp_responses')
    conn.commit()
    conn.close()
    print("Done.")

if __name__ == "__main__":
    main()
