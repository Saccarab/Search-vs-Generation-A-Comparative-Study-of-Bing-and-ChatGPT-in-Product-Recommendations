import pandas as pd
import sqlite3
import os

def verify_excel_state():
    xlsx_path = 'geo-fresh.xlsx'
    if not os.path.exists(xlsx_path):
        print(f"Error: {xlsx_path} not found.")
        return

    print(f"Reading {xlsx_path}...")
    # Load only necessary columns to save memory/time
    df_urls = pd.read_excel(xlsx_path, sheet_name='urls')
    df_cit = pd.read_excel(xlsx_path, sheet_name='citations')
    
    print(f"\n--- EXCEL SHEET OVERALL STATS ---")
    print(f"Total rows in 'urls' tab: {len(df_urls)}")
    has_content_mask = df_urls['content_path'].notna() & (df_urls['content_path'] != '')
    print(f"URLs with content_path: {has_content_mask.sum()}")
    print(f"URLs missing content_path: {(~has_content_mask).sum()}")

    print(f"\n--- CITATION COVERAGE ---")
    cit_urls = set(df_cit['url'].unique())
    urls_in_tab = set(df_urls['url'].unique())
    missing_cit = [u for u in cit_urls if u not in urls_in_tab]
    
    print(f"Total unique citation URLs: {len(cit_urls)}")
    print(f"Citation URLs missing from 'urls' tab: {len(missing_cit)}")
    if missing_cit:
        print(f"  Example missing: {missing_cit[:3]}")

    print(f"\n--- CONTENT STATUS BY CITATION TYPE ---")
    # Merge to see content status for each citation
    df_cit_status = df_cit[['url', 'citation_type']].drop_duplicates().merge(
        df_urls[['url', 'content_path']], on='url', how='left'
    )
    
    for ctype in df_cit['citation_type'].unique():
        sub = df_cit_status[df_cit_status['citation_type'] == ctype]
        total = len(sub)
        has_content = (sub['content_path'].notna() & (sub['content_path'] != '')).sum()
        perc = (has_content / total * 100) if total > 0 else 0
        print(f"Type '{ctype}': {has_content}/{total} unique URLs have content ({perc:.1f}%)")

    print(f"\n--- DEEP HUNT (RANK > 30) STATUS ---")
    if 'is_grounded_deep' in df_urls.columns:
        grounded_deep = df_urls[df_urls['is_grounded_deep'] == True]
        total_deep = len(grounded_deep)
        has_content_deep = (grounded_deep['content_path'].notna() & (grounded_deep['content_path'] != '')).sum()
        perc_deep = (has_content_deep / total_deep * 100) if total_deep > 0 else 0
        print(f"Grounded Deep URLs (Rank > 30): {has_content_deep}/{total_deep} have content ({perc_deep:.1f}%)")
    else:
        print("Column 'is_grounded_deep' not found in 'urls' tab.")

    print(f"\n--- NON-OVERLAPPING CITATIONS (The 'Invisible' Core) ---")
    # Citations that are NOT in bing_results or bing_deep_hunt (based on URL)
    # This is a rough check based on what's in the 'urls' tab vs what we know is grounded
    non_grounded_cit = df_cit_status[df_cit_status['content_path'].isna()]
    print(f"Total Citations still missing content (potentially invisible): {len(non_grounded_cit)}")

if __name__ == "__main__":
    verify_excel_state()
