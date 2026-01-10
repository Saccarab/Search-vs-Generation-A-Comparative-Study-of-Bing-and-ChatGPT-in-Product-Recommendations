import pandas as pd
from openpyxl import load_workbook

INPUT_FILE = 'GEO_Data_v2.xlsx'
OUTPUT_FILE = 'GEO_Data_v3.xlsx'

def add_final_columns():
    print(f"Reading {INPUT_FILE}...")
    try:
        xls = pd.ExcelFile(INPUT_FILE)
        sheet_map = {sheet: pd.read_excel(xls, sheet) for sheet in xls.sheet_names}
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    # Define final updates
    # We are adding to 'bing_results' only
    final_updates = {
        'bing_results': [
            'promotional_intensity_score', # 1-10 rating of "flashy language"
            'authority_claim_count',       # Count of "Best", "#1", "Leader"
            'functionality_match_score',   # 1-5 rating of relevance to prompt
            'missing_features'             # Why it wasn't perfect (e.g. "Paid only")
        ]
    }

    for sheet_name, new_cols in final_updates.items():
        if sheet_name in sheet_map:
            df = sheet_map[sheet_name]
            existing_cols = set(df.columns)
            for col in new_cols:
                if col not in existing_cols:
                    df[col] = None
            sheet_map[sheet_name] = df
            print(f"Added final columns to '{sheet_name}'")

    # Save
    print(f"Saving to {OUTPUT_FILE}...")
    with pd.ExcelWriter(OUTPUT_FILE, engine='openpyxl') as writer:
        for sheet_name, df in sheet_map.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            
    print("Success! GEO_Data_v3.xlsx is ready.")

if __name__ == "__main__":
    add_final_columns()


