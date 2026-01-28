import pandas as pd
import os

def get_remaining():
    xlsx_path = 'geo-fresh.xlsx'
    model = 'gemini-3-flash-preview'
    platforms = [
        'apps.apple.com', 
        'play.google.com', 
        'microsoft.com/store', 
        'chrome.google.com', 
        'wikipedia.org'
    ]

    print(f"Loading {xlsx_path}...")
    df = pd.read_excel(xlsx_path, sheet_name='urls')
    
    # Filter logic matching the Node.js script
    def should_skip(url):
        u = str(url).lower()
        return any(p in u for p in platforms)

    # 1. Must have content_path
    # 2. Must not be labeled by Gemini
    # 3. Must not be a platform store/wikipedia
    mask = (
        df['content_path'].notnull() & 
        (df['labeled_by_model'] != model) & 
        (~df['url'].apply(should_skip))
    )
    
    remaining = df[mask]
    
    print(f"\nTotal URLs remaining to process: {len(remaining)}")
    
    output_csv = 'remaining_enrichment_urls.csv'
    remaining[['url']].to_csv(output_csv, index=False)
    print(f"Full list saved to {output_csv}")
    
    print("\nFirst 20 URLs:")
    for url in remaining['url'].head(20):
        print(f"- {url}")

if __name__ == "__main__":
    get_remaining()
