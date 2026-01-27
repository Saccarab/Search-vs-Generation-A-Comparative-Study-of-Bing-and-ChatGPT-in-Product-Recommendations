import pandas as pd
import sys

def generate_histogram(xlsx_path):
    try:
        df_c = pd.read_excel(xlsx_path, sheet_name='citations')
        df_b = pd.read_excel(xlsx_path, sheet_name='bing_results')
        
        def norm(u):
            return str(u).lower().strip().split('?')[0].rstrip('/') if pd.notna(u) else ''
            
        df_c['u'] = df_c['url'].apply(norm)
        df_b['u'] = df_b['url'].apply(norm)
        
        # Merge to find ranks
        m = df_c.merge(df_b[['run_id', 'u', 'result_rank']], on=['run_id', 'u'], how='left')
        
        # Count occurrences per rank
        rc = m['result_rank'].value_counts().sort_index()
        total = len(df_c)
        
        print(f"Total Citations in geo-fresh: {total}")
        print("-" * 30)
        print(f"{'Rank':<5} | {'Count':<6} | {'Percentage'}")
        print("-" * 30)
        
        for r in range(1, 31):
            count = int(rc.get(r, 0))
            pct = (count / total) * 100
            print(f"{r:<5} | {count:<6} | {pct:5.2f}%")
            
        t10 = rc.loc[1:10].sum()
        t30 = rc.loc[1:30].sum()
        
        print("-" * 30)
        print(f"Top 10 Overlap: {(t10/total)*100:5.2f}%")
        print(f"Top 30 Overlap: {(t30/total)*100:5.2f}%")
        print(f"Invisible (Not in Top 30): {((total-t30)/total)*100:5.2f}%")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    generate_histogram('geo-fresh.xlsx')
