import pandas as pd
import subprocess
import os

def run_fetcher_in_batches():
    csv_path = 'data/ingest/final_strict_grounded_deep_urls.csv'
    df = pd.read_csv(csv_path)
    urls = df['url'].tolist()
    
    batch_size = 50
    content_root = r'C:\Users\User\Documents\thesis\node_content'
    xlsx_path = 'geo-fresh.xlsx'
    
    for i in range(0, len(urls), batch_size):
        batch = urls[i:i + batch_size]
        print(f"Processing batch {i//batch_size + 1} ({len(batch)} URLs)...")
        
        cmd = [
            'node', 
            'scripts/ingest/fetch_urls_to_thesis_node.js', 
            '--xlsx', xlsx_path, 
            '--content-root', content_root, 
            '--overwrite', 
            '--include-additional-only', 
            '--concurrency', '5'
        ]
        
        for url in batch:
            cmd.extend(['--only-url', url])
            
        subprocess.run(cmd)

if __name__ == "__main__":
    run_fetcher_in_batches()
