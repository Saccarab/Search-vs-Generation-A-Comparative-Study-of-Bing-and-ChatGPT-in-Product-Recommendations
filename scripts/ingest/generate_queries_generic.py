import pandas as pd
import json
import sys
import os

def generate(input_path, output_path):
    print(f"Reading {input_path}...")
    df = pd.read_csv(input_path)
    
    all_queries = []
    seen = set()
    
    for idx, row in df.iterrows():
        p_id = row['prompt_id'] if pd.notna(row['prompt_id']) else f"Q{row['query_index']}"
        run_num = int(row['run_number'])
        run_id = f"{p_id}_r{run_num}"
        
        # 1. Generated search query (The one visible in UI)
        if pd.notna(row['generated_search_query']) and row['generated_search_query'] != 'N/A':
            q = row['generated_search_query'].strip()
            if (run_id, q) not in seen:
                all_queries.append({'run_id': run_id, 'query': q})
                seen.add((run_id, q))
            
        # 2. Hidden queries (The ones from the API metadata)
        try:
            hidden_str = row['hidden_queries_json']
            if pd.notna(hidden_str):
                hidden = json.loads(hidden_str)
                for q in hidden:
                    if q:
                        q = q.strip()
                        if (run_id, q) not in seen:
                            all_queries.append({'run_id': run_id, 'query': q})
                            seen.add((run_id, q))
        except Exception as e:
            # print(f"Error parsing hidden queries at row {idx}: {e}")
            continue
            
    # Convert to DataFrame and save
    df_out = pd.DataFrame(all_queries)
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    df_out.to_csv(output_path, index=False)
    print(f"Generated {len(df_out)} unique run_id + query pairs (excluding prompts) in {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python generate_queries.py <input_csv> <output_csv>")
        sys.exit(1)
    
    input_csv = sys.argv[1]
    output_csv = sys.argv[2]
    generate(input_csv, output_csv)
