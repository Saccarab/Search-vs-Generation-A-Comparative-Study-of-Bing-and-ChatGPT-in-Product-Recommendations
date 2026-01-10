import pandas as pd

# Update with your actual filename
INPUT_FILE = r"c:\Users\User\Downloads\bing_results_2025-12-25T01-42-00.csv"
OUTPUT_FILE = "bing_results_us_clean.csv"

def clean_bing_data():
    print(f"Reading {INPUT_FILE}...")
    try:
        df = pd.read_csv(INPUT_FILE)
        # normalize columns
        df.columns = [c.strip() for c in df.columns]
    except Exception as e:
        print(f"Error: {e}")
        return

    cleaned_rows = []
    
    # Group by Query
    grouped = df.groupby('query', sort=False)
    
    print(f"Found {len(grouped)} unique queries.")
    
    for query, group in grouped:
        seen_urls = set()
        rank_counter = 1
        
        # Iterate through rows in original order
        for idx, row in group.iterrows():
            url = row.get('url', '')
            
            if pd.isna(url) or url == '':
                continue
                
            # Duplicate Check
            if url in seen_urls:
                continue
            
            seen_urls.add(url)
            
            # Create Clean Row
            clean_row = row.copy()
            clean_row['position'] = rank_counter
            cleaned_rows.append(clean_row)
            
            rank_counter += 1
            
            # Stop at 30
            if rank_counter > 30:
                break
    
    # Create new DF
    clean_df = pd.DataFrame(cleaned_rows)
    
    # Save
    clean_df.to_csv(OUTPUT_FILE, index=False)
    print(f"\nSuccess! Cleaned data saved to {OUTPUT_FILE}")
    print(f"Total Rows: {len(clean_df)} (Should be roughly 30 * Queries)")

if __name__ == "__main__":
    clean_bing_data()

