import pandas as pd
import os
import hashlib

def short_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]

def ingest_browser_results():
    xlsx_path = 'geo-fresh.xlsx'
    browser_csv = 'data/ingest/url_content_2026-01-24-22-05-03.csv'
    content_root = r'C:\Users\User\Documents\thesis\node_content'
    run_label = 'browser_fetch_2026-01-24'
    out_dir = os.path.join(content_root, run_label)
    
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    print(f"Reading browser results from {browser_csv}...")
    df_browser = pd.read_csv(browser_csv)
    
    print(f"Reading {xlsx_path}...")
    df_urls = pd.read_excel(xlsx_path, sheet_name='urls')
    
    # Create a mapping for quick lookup
    browser_map = df_browser.set_index('url').to_dict('index')
    
    updated_count = 0
    
    for idx, row in df_urls.iterrows():
        url = str(row['url'])
        if url in browser_map:
            b_data = browser_map[url]
            
            # Only update if status is 200 and we have content
            if b_data.get('status') == 200 and pd.notna(b_data.get('content')):
                content_text = str(b_data['content'])
                
                # Generate file path
                fname = f"{short_hash(url)}.txt"
                fpath = os.path.join(out_dir, fname)
                
                # Write content to disk
                with open(fpath, 'w', encoding='utf-8') as f:
                    f.write(content_text)
                
                # Update Excel row
                df_urls.at[idx, 'content_path'] = fpath
                df_urls.at[idx, 'content_word_count'] = len(content_text.split())
                df_urls.at[idx, 'page_title'] = b_data.get('page_title', '')
                df_urls.at[idx, 'meta_description'] = b_data.get('meta_description', '')
                df_urls.at[idx, 'fetched_at'] = '2026-01-24T22:05:00Z'
                
                updated_count += 1
                print(f"Updated: {url}")

    if updated_count > 0:
        print(f"\nSaving {updated_count} updates to {xlsx_path}...")
        with pd.ExcelWriter(xlsx_path, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
            df_urls.to_excel(writer, sheet_name='urls', index=False)
        print("Done!")
    else:
        print("No updates found matching the browser results.")

if __name__ == "__main__":
    ingest_browser_results()
