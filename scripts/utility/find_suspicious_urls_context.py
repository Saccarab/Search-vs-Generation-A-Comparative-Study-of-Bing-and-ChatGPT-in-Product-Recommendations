import pandas as pd

def find_citation_context(xlsx_path, suspicious_csv, out_csv):
    # Load data
    df_runs = pd.read_excel(xlsx_path, sheet_name='runs')
    df_citations = pd.read_excel(xlsx_path, sheet_name='citations')
    df_bing = pd.read_excel(xlsx_path, sheet_name='bing_results')
    df_suspicious = pd.read_csv(suspicious_csv)

    suspicious_urls = set(df_suspicious['url'].unique())

    # 1. Find Citations
    cit_matches = df_citations[df_citations['url'].isin(suspicious_urls)].copy()
    # Join with runs to get the prompt query
    cit_matches = cit_matches.merge(df_runs[['run_id', 'prompt_id', 'rewritten_query']], on='run_id', how='left')

    # 2. Find Bing Results
    bing_matches = df_bing[df_bing['url'].isin(suspicious_urls)].copy()
    bing_matches = bing_matches.merge(df_runs[['run_id', 'prompt_id', 'rewritten_query']], on='run_id', how='left')

    # Combine into a report
    report_rows = []

    for url in suspicious_urls:
        # Get missing reason from the suspicious list
        reason = df_suspicious[df_suspicious['url'] == url]['missing_reason'].iloc[0]
        
        # Citations
        url_cits = cit_matches[cit_matches['url'] == url]
        for _, row in url_cits.iterrows():
            report_rows.append({
                'url': url,
                'type': 'Citation (' + str(row['citation_type']) + ')',
                'run_id': row['run_id'],
                'prompt_id': row['prompt_id'],
                'query': row['rewritten_query'],
                'rank/pos': row.get('citation_group_index', ''),
                'missing_reason': reason
            })
            
        # Bing
        url_bing = bing_matches[bing_matches['url'] == url]
        for _, row in url_bing.iterrows():
            report_rows.append({
                'url': url,
                'type': 'Bing Result',
                'run_id': row['run_id'],
                'prompt_id': row['prompt_id'],
                'query': row['rewritten_query'],
                'rank/pos': row['result_rank'],
                'missing_reason': reason
            })

    report_df = pd.DataFrame(report_rows)
    if not report_df.empty:
        report_df = report_df.sort_values(by=['type', 'prompt_id'])
        report_df.to_csv(out_csv, index=False)
        print(f"Report generated: {out_csv} with {len(report_df)} matches.")
        
        # Print a small summary for the user
        print("\nSummary of Citations with Missing/Thin Content:")
        inline_cits = report_df[report_df['type'].str.contains('Citation', na=False)]
        if not inline_cits.empty:
            print(inline_cits[['prompt_id', 'url', 'type', 'missing_reason']].head(15).to_string())
        else:
            print("No high-priority citations found in the suspicious list.")
    else:
        print("No matches found in citations or bing results for these URLs.")

if __name__ == "__main__":
    find_citation_context('geo-fresh.xlsx', 'data/ingest/suspicious_urls_for_retry.csv', 'data/ingest/suspicious_urls_context.csv')
