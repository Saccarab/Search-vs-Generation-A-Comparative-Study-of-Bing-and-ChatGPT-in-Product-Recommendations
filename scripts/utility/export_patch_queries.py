import pandas as pd
import os

def export_subset_queries(results_csv, output_csv):
    # These are the run_ids we just ingested into geo-fresh.xlsx
    # based on the incrementing logic.
    # P021: r3, r4
    # P002, P026, P034, P076, P009, P011, P029: r4
    # P031, P035, P046, P071, P048, P060: r3
    
    # Actually, a safer way is to just read the results file provided by the user
    # and map them to what we just put in Excel.
    
    df = pd.read_csv(results_csv, engine="python")
    
    # We'll use a simplified version of the logic in our ingest script to 
    # generate the same run_ids.
    patch_ids = []
    max_runs = {
        'P001': 3, 'P002': 3, 'P003': 3, 'P005': 3, 'P007': 3, 'P008': 3, 'P009': 3, 'P010': 3, 
        'P011': 3, 'P012': 3, 'P014': 3, 'P015': 3, 'P017': 3, 'P018': 3, 'P019': 3, 'P020': 3, 
        'P021': 2, 'P022': 3, 'P023': 3, 'P024': 3, 'P025': 3, 'P026': 3, 'P027': 3, 'P028': 3, 
        'P029': 3, 'P030': 3, 'P031': 2, 'P032': 3, 'P033': 3, 'P034': 3, 'P035': 2, 'P037': 3, 
        'P038': 3, 'P039': 3, 'P040': 3, 'P041': 3, 'P042': 3, 'P043': 3, 'P044': 3, 'P046': 2, 
        'P047': 3, 'P048': 2, 'P049': 3, 'P050': 3, 'P051': 3, 'P052': 3, 'P053': 3, 'P054': 3, 
        'P055': 3, 'P057': 3, 'P058': 3, 'P060': 2, 'P061': 3, 'P063': 3, 'P064': 3, 'P065': 3, 
        'P066': 3, 'P068': 3, 'P069': 3, 'P070': 3, 'P071': 2, 'P072': 3, 'P073': 3, 'P074': 3, 
        'P075': 3, 'P076': 3, 'P077': 3, 'P078': 3, 'P079': 3, 'P080': 3, 'P081': 3
    }
    
    rows = []
    for _, r in df.iterrows():
        pid = str(r['prompt_id'])
        query = str(r.get('generated_search_query', '')).strip()
        if not query or query.lower() == 'nan' or query.lower() == 'n/a':
            continue
            
        next_num = max_runs.get(pid, 0) + 1
        max_runs[pid] = next_num
        run_id = f"{pid}_r{next_num}"
        rows.append({"run_id": run_id, "query": query})
        
    output_df = pd.DataFrame(rows)
    output_df.to_csv(output_csv, index=False)
    print(f"Successfully exported {len(output_df)} patch queries to {output_csv}")

if __name__ == "__main__":
    export_subset_queries("data/ingest/chatgpt_results_2026-01-18T01-25-10.csv", "data/ingest/rewritten_queries_patches.csv")
