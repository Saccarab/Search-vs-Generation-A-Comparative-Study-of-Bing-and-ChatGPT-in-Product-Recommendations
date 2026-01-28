import pandas as pd
import sqlite3
import os

def update_strict_flags():
    xlsx_path = 'geo-fresh.xlsx'
    db_path = 'geo_fresh.db'
    
    if not os.path.exists(xlsx_path):
        print(f"Error: {xlsx_path} not found.")
        return

    print(f"Reading {xlsx_path} and Database...")
    conn = sqlite3.connect(db_path)
    
    # Load the URLs tab
    df_urls = pd.read_excel(xlsx_path, sheet_name='urls')
    
    # Get all unique EXACT matches from citations (any type) and bing results (any rank)
    # 1. All Citation URLs
    cit_urls = pd.read_sql_query("SELECT DISTINCT url FROM citations", conn)['url'].tolist()
    # 2. All Bing Top 30 URLs
    bing_top30_urls = pd.read_sql_query("SELECT DISTINCT url FROM bing_results", conn)['url'].tolist()
    # 3. All Bing Deep Hunt URLs
    bing_deep_urls = pd.read_sql_query("SELECT DISTINCT url FROM bing_deep_hunt", conn)['url'].tolist()
    
    # Combine all "Valid" targets (Exact URLs we actually care about)
    valid_exact_urls = set(cit_urls + bing_top30_urls + bing_deep_urls)
    
    print(f"Found {len(valid_exact_urls)} unique exact URLs across Citations and Bing Results.")

    # Mark the flags
    # is_strict_match: The URL in the sheet is an EXACT match to something ChatGPT cited or Bing found
    df_urls['is_strict_match'] = df_urls['url'].isin(valid_exact_urls)
    
    # is_grounded_deep: Specifically for the Rank 31-150 results that are EXACT matches to citations
    # We'll re-calculate this to be sure it's strict
    query_strict_deep = '''
    SELECT DISTINCT c.url
    FROM citations c
    JOIN bing_deep_hunt b ON c.run_id = b.run_id AND c.url = b.url
    WHERE b.absolute_rank > 30
    '''
    strict_deep_urls = set(pd.read_sql_query(query_strict_deep, conn)['url'].tolist())
    df_urls['is_grounded_deep'] = df_urls['url'].isin(strict_deep_urls)

    # Count the results
    strict_count = df_urls['is_strict_match'].sum()
    domain_only_count = len(df_urls) - strict_count
    
    print(f"\n--- FLAG UPDATE SUMMARY ---")
    print(f"Total URLs in sheet: {len(df_urls)}")
    print(f"Strict Matches (Keep): {strict_count}")
    print(f"Domain-Only Matches (Noise): {domain_only_count}")
    print(f"Strict Grounded Deep (Rank 31-150): {df_urls['is_grounded_deep'].sum()}")

    # Save back to Excel
    print(f"\nSaving updates to {xlsx_path}...")
    with pd.ExcelWriter(xlsx_path, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
        df_urls.to_excel(writer, sheet_name='urls', index=False)
    
    print("Done!")
    conn.close()

if __name__ == "__main__":
    update_strict_flags()
