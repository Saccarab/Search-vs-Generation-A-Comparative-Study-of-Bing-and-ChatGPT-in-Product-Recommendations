import pandas as pd
from openpyxl import load_workbook

def export_suspicious_urls(xlsx_path, out_csv):
    df_urls = pd.read_excel(xlsx_path, sheet_name='urls')
    
    # Define which reasons we want to retry
    retry_reasons = [
        "Failed: Fetch Error (403/429/Timeout)",
        "Failed: Thin Content (<100 words)",
        "Pending Fetch (High Priority)",
        "Pending Fetch (Uncategorized)"
    ]
    
    # Filter the dataframe
    suspicious_df = df_urls[df_urls['missing_reason'].isin(retry_reasons)].copy()
    
    if suspicious_df.empty:
        print("No suspicious URLs found matching the retry criteria.")
        return

    # Add some context for the user (Title/Snippet if available)
    # These might be in the sheet already or we can pull them
    cols_to_keep = ['url', 'domain', 'missing_reason', 'page_title', 'meta_description', 'content_word_count']
    # Filter to only keep columns that actually exist
    cols_to_keep = [c for c in cols_to_keep if c in suspicious_df.columns]
    
    suspicious_df = suspicious_df[cols_to_keep]
    
    # Sort by domain to help the user identify patterns (e.g. all YouTube failing)
    suspicious_df = suspicious_df.sort_values(by='domain')
    
    suspicious_df.to_csv(out_csv, index=False)
    print(f"Exported {len(suspicious_df)} suspicious URLs to {out_csv}")
    
    # Print a summary of counts by domain
    print("\nTop Domains for Retry:")
    print(suspicious_df['domain'].value_counts().head(20))

if __name__ == "__main__":
    export_suspicious_urls('geo-fresh.xlsx', 'data/ingest/suspicious_urls_for_retry.csv')
