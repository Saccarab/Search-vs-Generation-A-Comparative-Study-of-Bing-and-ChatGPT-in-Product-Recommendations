import pandas as pd
from openpyxl import load_workbook

def export_missing_content_report(xlsx_path, out_csv):
    print(f"Generating missing content report for {xlsx_path}...")
    
    # Load urls sheet
    df_urls = pd.read_excel(xlsx_path, sheet_name='urls')
    
    # Filter for anything without a content_path
    missing_df = df_urls[df_urls['content_path'].isna() | (df_urls['content_path'].astype(str).str.strip() == "")].copy()
    
    if missing_df.empty:
        print("No missing content found in the workbook.")
        return

    # Select relevant columns for the user to review
    cols = ['url', 'domain', 'missing_reason', 'page_title', 'meta_description']
    cols = [c for c in cols if c in missing_df.columns]
    
    missing_df = missing_df[cols].sort_values(by=['missing_reason', 'domain'])
    
    missing_df.to_csv(out_csv, index=False)
    print(f"Exported {len(missing_df)} missing URLs to {out_csv}")
    
    # Print summary by reason
    print("\nMissing Reason Summary:")
    print(missing_df['missing_reason'].value_counts())

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--xlsx", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    export_missing_content_report(args.xlsx, args.out)
