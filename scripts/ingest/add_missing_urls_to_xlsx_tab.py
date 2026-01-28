import pandas as pd
import os
from urllib.parse import urlparse

# Paths
MASTER_XLSX = 'geo_final.xlsx'
MISSING_CSV = 'data/ingest/final_missing_grounded_urls.csv'

def extract_domain(url):
    try:
        domain = urlparse(str(url)).netloc
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except:
        return ''

def main():
    if not os.path.exists(MASTER_XLSX):
        print(f"Error: {MASTER_XLSX} not found.")
        return
    
    print(f"Loading missing URLs from {MISSING_CSV}...")
    df_missing = pd.read_csv(MISSING_CSV)
    
    print(f"Loading existing URLs from {MASTER_XLSX}...")
    df_urls = pd.read_excel(MASTER_XLSX, sheet_name='urls')
    
    # Create new rows for the 'urls' tab
    new_rows = pd.DataFrame({'url': df_missing['url']})
    new_rows['domain'] = new_rows['url'].apply(extract_domain)
    
    print(f"Adding {len(new_rows)} new URLs to the 'urls' tab...")
    
    # Combine and deduplicate
    df_updated_urls = pd.concat([df_urls, new_rows], ignore_index=True)
    df_updated_urls = df_updated_urls.drop_duplicates(subset=['url'], keep='first')
    
    # Write back to Excel
    with pd.ExcelWriter(MASTER_XLSX, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
        df_updated_urls.to_excel(writer, sheet_name='urls', index=False)
        
    print(f"Successfully updated 'urls' tab. New total: {len(df_updated_urls)} rows.")

if __name__ == "__main__":
    main()
