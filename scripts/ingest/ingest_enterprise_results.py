import pandas as pd
import json
import os
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows

# Paths
INPUT_CSV = 'data/ingest/chatgpt_results_2026-01-27T11-23-04.csv'
OUTPUT_XLSX = 'geo-enterprise.xlsx'

def ingest():
    print(f"Reading {INPUT_CSV}...")
    df = pd.read_csv(INPUT_CSV)
    
    # 1. Process Sonic Classification (Probabilities)
    print("Processing Sonic probabilities...")
    def parse_sonic(x):
        try:
            data = json.loads(x)
            if not data: return pd.Series([None]*4)
            return pd.Series([
                data.get('simple_search_prob'),
                data.get('complex_search_prob'),
                data.get('no_search_prob'),
                data.get('simple_search_threshold')
            ])
        except:
            return pd.Series([None]*4)

    sonic_cols = ['simple_search_prob', 'complex_search_prob', 'no_search_prob', 'simple_search_threshold']
    df[sonic_cols] = df['sonic_classification_json'].apply(parse_sonic)

    # 2. Prepare 'runs' sheet
    # We include forensics here
    runs_cols = [
        'query_index', 'run_number', 'prompt_id', 'query', 'generated_search_query',
        'web_search_triggered', 'simple_search_prob', 'complex_search_prob', 
        'no_search_prob', 'simple_search_threshold', 'hidden_queries_json', 
        'content_references_json', 'items_count', 'response_text'
    ]
    df_runs = df[runs_cols].copy()
    
    # Add run_id in the format P001_r1
    df_runs['run_id'] = df_runs.apply(lambda x: f"{x['prompt_id']}_r{int(x['run_number'])}", axis=1)
    
    # Reorder to put run_id near the start
    cols = ['run_id'] + [c for c in df_runs.columns if c != 'run_id']
    df_runs = df_runs[cols]

    # 3. Prepare 'citations' sheet (Long format)
    print("Extracting citations...")
    citation_rows = []
    for idx, row in df.iterrows():
        run_id = f"{row['prompt_id']}_r{int(row['run_number'])}"
        try:
            # We use sources_all_json which contains the unique union of cited + additional
            sources = json.loads(row['sources_all_json'])
            for s in sources:
                citation_rows.append({
                    'run_id': run_id,
                    'query_index': row['query_index'],
                    'run_number': row['run_number'],
                    'prompt_id': row['prompt_id'],
                    'url': s.get('url'),
                    'domain': s.get('domain'),
                    'title': s.get('title'),
                    'source_type': 'all'
                })
        except:
            continue
    df_citations = pd.DataFrame(citation_rows)

    # 4. Prepare 'urls' sheet (Unique URLs for enrichment)
    print("Preparing unique URLs for enrichment...")
    if not df_citations.empty:
        df_urls = df_citations[['url', 'domain']].drop_duplicates(subset=['url'])
    else:
        df_urls = pd.DataFrame(columns=['url', 'domain'])

    # 5. Write to Excel
    print(f"Writing to {OUTPUT_XLSX}...")
    with pd.ExcelWriter(OUTPUT_XLSX, engine='openpyxl') as writer:
        df_runs.to_excel(writer, sheet_name='runs', index=False)
        df_citations.to_excel(writer, sheet_name='citations', index=False)
        df_urls.to_excel(writer, sheet_name='urls', index=False)
        
        # Create empty placeholder sheets for DNA analysis
        pd.DataFrame(columns=['url', 'product_name', 'position', 'is_host']).to_excel(writer, sheet_name='listicle_products', index=False)

    print("Ingestion complete.")

if __name__ == "__main__":
    ingest()
