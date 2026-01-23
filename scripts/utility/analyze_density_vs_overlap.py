import pandas as pd

def analyze_density_vs_overlap(xlsx_path):
    print(f"Analyzing {xlsx_path}...")
    try:
        df_c = pd.read_excel(xlsx_path, sheet_name='citations')
        df_b = pd.read_excel(xlsx_path, sheet_name='bing_results')
        
        def norm(u):
            return str(u).lower().strip().split('?')[0].rstrip('/') if pd.notna(u) else ''
            
        df_c['u'] = df_c['url'].apply(norm)
        df_b['u'] = df_b['url'].apply(norm)
        
        # 1. Calculate Page 1 Size for each run
        p1_sizes = df_b[df_b['page_num'] == 1].groupby('run_id').size().reset_index(name='p1_size')
        
        # 2. Find Top 10 Overlap for each run
        # Merge citations with bing results (limited to Top 10)
        m = df_c.merge(df_b[df_b['result_rank'] <= 10][['run_id', 'u', 'result_rank']], on=['run_id', 'u'], how='left')
        m['is_match'] = m['result_rank'].notna()
        
        # Group by run to get overlap count
        run_overlap = m.groupby('run_id')['is_match'].sum().reset_index(name='overlap_count')
        run_total_cites = m.groupby('run_id').size().reset_index(name='total_cites')
        
        # Combine everything
        analysis = p1_sizes.merge(run_overlap, on='run_id').merge(run_total_cites, on='run_id')
        analysis['overlap_pct'] = (analysis['overlap_count'] / analysis['total_cites']) * 100
        
        # 3. Compare "Low Density" (P1 Size <= 4) vs "High Density" (P1 Size > 4)
        low_density = analysis[analysis['p1_size'] <= 4]
        high_density = analysis[analysis['p1_size'] > 4]
        
        print("\n" + "="*60)
        print(f"{'PAGE 1 DENSITY VS TOP 10 OVERLAP':^60}")
        print("="*60)
        
        print(f"{'Group':<25} | {'N Runs':<8} | {'Avg P1 Size':<10} | {'Avg Top 10 Overlap %'}")
        print("-" * 60)
        
        print(f"{'Low Density (P1 <= 4)':<25} | {len(low_density):<8} | {low_density['p1_size'].mean():<10.2f} | {low_density['overlap_pct'].mean():.2f}%")
        print(f"{'High Density (P1 > 4)':<25} | {len(high_density):<8} | {high_density['p1_size'].mean():<10.2f} | {high_density['overlap_pct'].mean():.2f}%")
        
        # 4. Even more granular breakdown
        print("\n" + "="*60)
        print(f"{'GRANULAR BREAKDOWN':^60}")
        print("="*60)
        print(f"{'P1 Size':<10} | {'N Runs':<8} | {'Avg Top 10 Overlap %'}")
        print("-" * 60)
        for size in sorted(analysis['p1_size'].unique()):
            sub = analysis[analysis['p1_size'] == size]
            print(f"{size:<10} | {len(sub):<8} | {sub['overlap_pct'].mean():.2f}%")
            
        print("\nConclusion: If High Density has higher overlap, Bing's UI is suppressing your metrics.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze_density_vs_overlap('geo-fresh.xlsx')
