import pandas as pd
import os
import shutil

def backup_and_copy_labels():
    xlsx_path = 'geo-fresh.xlsx'
    backup_path = 'geo-fresh_before_full_gemini_enrichment.xlsx'
    
    if not os.path.exists(xlsx_path):
        print(f"Error: {xlsx_path} not found.")
        return

    # 1. Physical Backup
    shutil.copy(xlsx_path, backup_path)
    print(f"Physical backup created: {backup_path}")

    # 2. Internal Sheet Backup
    print(f"Reading {xlsx_path} to backup current labels...")
    
    # Load all sheets to preserve them
    all_sheets = pd.read_excel(xlsx_path, sheet_name=None)
    
    # Create the backup sheet from the current 'urls' data
    if 'urls' in all_sheets:
        all_sheets['urls_gpt_backup'] = all_sheets['urls'].copy()
        print("Created 'urls_gpt_backup' from current 'urls' sheet.")
    else:
        print("Error: 'urls' sheet not found.")
        return

    # 3. Save back to the same file
    print(f"Saving updated workbook with backup sheet...")
    with pd.ExcelWriter(xlsx_path, engine='openpyxl') as writer:
        for sheet_name, df in all_sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    
    print("Success! Your GPT data is safe in the 'urls_gpt_backup' sheet.")

if __name__ == "__main__":
    backup_and_copy_labels()
