import pandas as pd
import os

file_path = 'datapass/geo-enterprise-master.xlsx'
if not os.path.exists(file_path):
    print(f"File not found: {file_path}")
else:
    try:
        df = pd.read_excel(file_path, sheet_name='urls')
        print(f"Total URLs in {file_path}: {len(df)}")
        if 'content_path' in df.columns:
            missing = df['content_path'].isna().sum()
            print(f"Missing content_path: {missing}")
        else:
            print("Column 'content_path' not found.")
        print(f"Columns: {df.columns.tolist()}")
    except Exception as e:
        print(f"Error: {e}")
