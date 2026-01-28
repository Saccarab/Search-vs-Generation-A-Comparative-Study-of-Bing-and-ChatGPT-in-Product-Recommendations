import pandas as pd
import os

# Paths
MASTER_XLSX = 'geo_final.xlsx'
APPEND_CSV = 'data/ingest/deep_hunt_grounded_deduped_strict.csv'
BACKUP_XLSX = 'geo_final_backup_before_deep_append_v2.xlsx'

def main():
    if not os.path.exists(MASTER_XLSX):
        print(f"Error: {MASTER_XLSX} not found.")
        return
    
    # 1. Backup
    print(f"Creating backup: {BACKUP_XLSX}")
    import shutil
    shutil.copy2(MASTER_XLSX, BACKUP_XLSX)
    
    # 2. Load data
    print("Loading master Excel...")
    with pd.ExcelWriter(MASTER_XLSX, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
        # We need to read the existing bing_results sheet
        df_master = pd.read_excel(MASTER_XLSX, sheet_name='bing_results')
        df_append = pd.read_csv(APPEND_CSV)
        
        print(f"Current master rows: {len(df_master)}")
        print(f"Rows to append: {len(df_append)}")
        
        # 3. Combine
        # Ensure column alignment
        df_combined = pd.concat([df_master, df_append], ignore_index=True)
        
        # 4. Deduplicate just in case
        df_combined = df_combined.drop_duplicates(subset=['run_id', 'url'])
        
        print(f"New total rows: {len(df_combined)}")
        
        # 5. Write back to the same sheet
        df_combined.to_excel(writer, sheet_name='bing_results', index=False)
        
    print("Successfully appended grounded Deep Hunt results to geo_final.xlsx")

if __name__ == "__main__":
    main()
