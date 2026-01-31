import os
import json
import glob
import pandas as pd

def check_status():
    mapping_dir = 'datapass/citation_mappings'
    results_dir = 'data/serpapi_google_results'
    
    # 1. Get all expected runs from mapping files
    mapping_files = glob.glob(os.path.join(mapping_dir, '*.json'))
    expected_queries = []
    
    for f in mapping_files:
        try:
            with open(f, 'r', encoding='utf-8') as j:
                data = json.load(j)
                run_id = data.get('run_id')
                account_type = data.get('account_type', 'unknown')
                
                # Main query
                main_q = data.get('prompt')
                if main_q:
                    expected_queries.append({
                        'run_id': run_id,
                        'account': account_type,
                        'type': 'main',
                        'query': main_q
                    })
                
                # Hidden queries
                hidden = data.get('metadata', {}).get('hidden_queries', [])
                for i, q in enumerate(hidden):
                    if q and str(q).strip().lower() != 'n/a':
                        expected_queries.append({
                            'run_id': run_id,
                            'account': account_type,
                            'type': f'Q{i+1}',
                            'query': q
                        })
        except Exception as e:
            print(f"Error reading {f}: {e}")

    # 2. Get all existing result files
    result_files = os.listdir(results_dir)
    
    status_report = []
    
    for item in expected_queries:
        rid = item['run_id']
        acc = item['account']
        q_type = item['type']
        query = item['query']
        
        found = False
        for f in result_files:
            # Check if file starts with run_id and contains the query type
            if f.startswith(rid) and f'_{q_type}_' in f:
                # If it has an account label, it must match
                if '_enterprise_' in f:
                    if acc == 'enterprise':
                        found = True
                        break
                elif '_personal_' in f:
                    if acc == 'personal':
                        found = True
                        break
                else:
                    # No account label - treat as a match for the expected account
                    found = True
                    break
        
        status_report.append({
            'Run ID': rid,
            'Account': acc,
            'Type': q_type,
            'Status': 'DONE' if found else 'MISSING',
            'Query': query[:50] + '...' if len(query) > 50 else query
        })

    df = pd.DataFrame(status_report)
    
    # Summarize
    summary = df.groupby(['Account', 'Status']).size().unstack(fill_value=0)
    
    # Write to text file
    with open('serpapi_status_summary.txt', 'w', encoding='utf-8') as f:
        f.write("=== SERPAPI COLLECTION STATUS SUMMARY ===\n\n")
        f.write(summary.to_string())
        f.write("\n\n=== DETAILED MISSING QUERIES ===\n")
        missing = df[df['Status'] == 'MISSING']
        if missing.empty:
            f.write("No missing queries found!\n")
        else:
            f.write(missing[['Run ID', 'Account', 'Type', 'Query']].to_string(index=False))

    print("Summary written to serpapi_status_summary.txt")

if __name__ == "__main__":
    check_status()
