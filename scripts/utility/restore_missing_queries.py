import pandas as pd
import glob
import os

def find_queries_in_history(run_ids, ingest_dir="data/ingest"):
    results = {}
    csv_files = glob.glob(os.path.join(ingest_dir, "chatgpt_results*.csv"))
    
    for file in csv_files:
        try:
            df = pd.read_csv(file, engine="python")
            if 'prompt_id' not in df.columns or 'run_number' not in df.columns:
                continue
            
            df['run_id'] = df['prompt_id'].astype(str) + "_r" + df['run_number'].astype(str)
            
            for rid in run_ids:
                if rid in results: continue
                
                matches = df[df['run_id'] == rid]
                if not matches.empty:
                    query = str(matches.iloc[0].get('generated_search_query', '')).strip()
                    if query and query.lower() != 'nan':
                        results[rid] = query
        except Exception as e:
            print(f"Error reading {file}: {e}")
            
    return results

if __name__ == "__main__":
    high_priority_rids = [
        "P002_r2", "P021_r1", "P021_r3", "P026_r1", "P031_r3", 
        "P034_r2", "P035_r3", "P046_r3", "P071_r3", "P076_r1"
    ]
    
    found = find_queries_in_history(high_priority_rids)
    
    print("Found following queries in history:")
    for rid, q in found.items():
        print(f"  - {rid}: {q}")
        
    missing = [rid for rid in high_priority_rids if rid not in found]
    if missing:
        print("\nStill missing (no query found in history):")
        for rid in missing:
            print(f"  - {rid}")
