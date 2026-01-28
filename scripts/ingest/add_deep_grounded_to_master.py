import sqlite3
import pandas as pd
from urllib.parse import urlparse
import os

DB_PATH = 'geo_fresh.db'
XLSX_PATH = 'geo-fresh.xlsx'

def extract_domain(url):
    try:
        d = urlparse(str(url)).netloc
        if d.startswith('www.'):
            d = d[4:]
        return d
    except:
        return ''

def main():
    if not os.path.exists(XLSX_PATH):
        print(f"Error: {XLSX_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    
    # 1. Get unique grounded URLs from Deep Hunt (Rank 31-150)
    query = '''
    SELECT DISTINCT b.url 
    FROM bing_deep_hunt b
    JOIN citations c ON b.run_id = c.run_id AND (b.url = c.url OR b.result_domain = c.norm_domain)
    WHERE b.absolute_rank > 30
    '''
    df_grounded_deep = pd.read_sql_query(query, conn)
    
    # 2. Load existing URLs from Excel
    print("Loading existing URLs from Excel...")
    df_excel = pd.read_excel(XLSX_PATH, sheet_name='urls')
    existing_urls = set(df_excel['url'].dropna().unique())
    
    # 3. Filter for completely new URLs
    missing_urls = df_grounded_deep[~df_grounded_deep['url'].isin(existing_urls)].copy()
    
    if len(missing_urls) == 0:
        print("No new URLs to add.")
        return

    print(f"Adding {len(missing_urls)} new URLs...")
    
    # 4. Prepare new rows
    missing_urls['domain'] = missing_urls['url'].apply(extract_domain)
    missing_urls['is_grounded_deep'] = True
    
    # 5. Combine and save
    df_updated = pd.concat([df_excel, missing_urls], ignore_index=True)
    
    with pd.ExcelWriter(XLSX_PATH, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
        df_updated.to_excel(writer, sheet_name='urls', index=False)
        
    print(f"Successfully added {len(missing_urls)} new URLs to {XLSX_PATH} with 'is_grounded_deep' flag.")

if __name__ == "__main__":
    main()
