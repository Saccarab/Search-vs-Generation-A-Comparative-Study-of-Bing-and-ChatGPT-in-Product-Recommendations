import pandas as pd
import os

def generate_detailed_histograms(xlsx_path):
    print(f"Loading {xlsx_path}...")
    try:
        # Load data
        df_c = pd.read_excel(xlsx_path, sheet_name='citations')
        df_b = pd.read_excel(xlsx_path, sheet_name='bing_results')
        
        def norm(u):
            return str(u).lower().strip().split('?')[0].rstrip('/') if pd.notna(u) else ''
            
        df_c['u'] = df_c['url'].apply(norm)
        df_b['u'] = df_b['url'].apply(norm)
        
        # Merge to find matches
        m = df_c.merge(df_b[['run_id', 'u', 'result_rank', 'page_num']], on=['run_id', 'u'], how='left')
        
        total_citations = len(df_c)
        
        # 1. Rank-by-Rank Histogram (1-30)
        rank_counts = m['result_rank'].value_counts().sort_index()
        
        print("\n" + "="*50)
        print(f"{'RANK-BY-RANK OVERLAP (1-30)':^50}")
        print("="*50)
        print(f"{'Rank':<6} | {'Count':<8} | {'% of Total Citations'}")
        print("-" * 50)
        
        for r in range(1, 31):
            count = int(rank_counts.get(r, 0))
            pct = (count / total_citations) * 100
            print(f"{r:<6} | {count:<8} | {pct:6.2f}%")
            
        # 2. Page-by-Page Histogram
        # Note: page_num might be NaN for non-matches
        page_counts = m['page_num'].value_counts().sort_index()
        
        print("\n" + "="*50)
        print(f"{'PAGE-BY-PAGE OVERLAP':^50}")
        print("="*50)
        print(f"{'Page':<6} | {'Count':<8} | {'% of Total Citations'}")
        print("-" * 50)
        
        # We'll show pages found in the data
        for p in sorted(page_counts.index.unique()):
            if pd.isna(p): continue
            count = int(page_counts.get(p, 0))
            pct = (count / total_citations) * 100
            print(f"Page {int(p):<1} | {count:<8} | {pct:6.2f}%")

        # Summary Metrics
        t10 = rank_counts.loc[1:10].sum()
        t30 = rank_counts.loc[1:30].sum()
        
        print("\n" + "="*50)
        print(f"{'SUMMARY':^50}")
        print("="*50)
        print(f"Total Citations: {total_citations}")
        print(f"Top 10 Overlap:  {t10:>6} ({(t10/total_citations)*100:5.2f}%)")
        print(f"Top 30 Overlap:  {t30:>6} ({(t30/total_citations)*100:5.2f}%)")
        print(f"Invisible:       {total_citations - t30:>6} ({((total_citations-t30)/total_citations)*100:5.2f}%)")
        print("="*50)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    generate_detailed_histograms('geo-fresh.xlsx')
