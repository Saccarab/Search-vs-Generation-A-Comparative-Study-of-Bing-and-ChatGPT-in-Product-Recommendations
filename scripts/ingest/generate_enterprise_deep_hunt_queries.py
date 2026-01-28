import pandas as pd
import json
import os

INPUT_CSV = 'data/ingest/chatgpt_results_2026-01-27T11-23-04.csv'
OUTPUT_QUERIES = 'data/ingest/queries_for_deep_hunt_enterprise.csv'

def generate():
    print(f"Reading {INPUT_CSV}...")
    df = pd.read_csv(INPUT_CSV)
    
    all_queries = []
    seen = set()
    
    for idx, row in df.iterrows():
        p_id = row['prompt_id'] if pd.notna(row['prompt_id']) else f"Q{row['query_index']}"
        run_num = int(row['run_number'])
        run_id = f"{p_id}_r{run_num}"
        
        # 1. Main query - SKIPPED (User only wants actual search engine queries)
        # if pd.notna(row['query']):
        #     q = row['query'].strip()
        #     ...
            
        # 2. Generated search query (The one visible in UI)
        if pd.notna(row['generated_search_query']) and row['generated_search_query'] != 'N/A':
            q = row['generated_search_query'].strip()
            if (run_id, q) not in seen:
                all_queries.append({'run_id': run_id, 'query': q})
                seen.add((run_id, q))
            
        # 3. Hidden queries (The ones from the API metadata)
        try:
            hidden = json.loads(row['hidden_queries_json'])
            for q in hidden:
                if q:
                    q = q.strip()
                    if (run_id, q) not in seen:
                        all_queries.append({'run_id': run_id, 'query': q})
                        seen.add((run_id, q))
        except:
            continue
            
    # Convert to DataFrame and save
    df_out = pd.DataFrame(all_queries)
    df_out.to_csv(OUTPUT_QUERIES, index=False)
    print(f"Generated {len(df_out)} unique run_id + query pairs (excluding prompts) in {OUTPUT_QUERIES}")

if __name__ == "__main__":
    generate()
