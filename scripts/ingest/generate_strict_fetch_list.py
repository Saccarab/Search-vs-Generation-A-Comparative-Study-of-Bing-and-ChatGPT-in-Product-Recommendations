import pandas as pd
import sqlite3
from urllib.parse import urlparse

def generate_strict_list():
    conn = sqlite3.connect('geo_fresh.db')
    
    # 1. Get ONLY Exact URL Matches from Deep Hunt (Rank > 30)
    query = '''
    SELECT DISTINCT c.url
    FROM citations c
    JOIN bing_deep_hunt b ON c.run_id = b.run_id AND c.url = b.url
    WHERE b.absolute_rank > 30
    '''
    df_grounded_deep = pd.read_sql_query(query, conn)
    
    # 2. Define platform domains to exclude
    platforms = [
        'apple.com', 
        'google.com', 
        'microsoft.com', 
        'chrome.google.com', 
        'play.google.com', 
        'apps.apple.com',
        'amazon.com' # Adding Amazon as it's a marketplace/platform
    ]
    
    def is_platform(url):
        try:
            netloc = urlparse(str(url)).netloc.lower()
            return any(plat in netloc for plat in platforms)
        except:
            return False

    # 3. Filter out platforms
    df_filtered = df_grounded_deep[~df_grounded_deep['url'].apply(is_platform)].copy()
    
    # 4. Save to CSV
    output_path = 'data/ingest/final_strict_grounded_deep_urls.csv'
    df_filtered.to_csv(output_path, index=False)
    
    print(f"Total Strict Grounded Deep URLs (Rank > 30): {len(df_grounded_deep)}")
    print(f"After removing Platforms/Stores: {len(df_filtered)}")
    print(f"Saved to {output_path}")
    
    conn.close()

if __name__ == "__main__":
    generate_strict_list()
