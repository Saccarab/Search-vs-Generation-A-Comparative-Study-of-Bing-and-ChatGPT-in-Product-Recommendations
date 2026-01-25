import sqlite3
import pandas as pd
import numpy as np
from collections import Counter

DB_PATH = 'geo_fresh.db'

def analyze_consistency():
    conn = sqlite3.connect(DB_PATH)
    
    # 1. Get all runs and their RAG status
    runs_df = pd.read_sql_query('''
        SELECT run_id, prompt_id, rewritten_query, citation_count
        FROM runs
        ORDER BY prompt_id, run_id
    ''', conn)
    
    # Define RAG as having a rewritten query or a non-zero citation count
    runs_df['has_rag'] = (runs_df['citation_count'] > 0) | (runs_df['rewritten_query'].notnull() & (runs_df['rewritten_query'] != ''))
    
    # 2. Get Citations per run (joining with runs to get prompt_id)
    citations_df = pd.read_sql_query('''
        SELECT r.prompt_id, c.run_id, c.url 
        FROM citations c
        JOIN runs r ON c.run_id = r.run_id
    ''', conn)
    
    results = []
    
    for prompt_id, group in runs_df.groupby('prompt_id'):
        total_runs = len(group)
        rag_runs = group['has_rag'].sum()
        
        # Citation Analysis
        prompt_citations = citations_df[citations_df['prompt_id'] == prompt_id]
        unique_urls = prompt_citations['url'].unique()
        
        if len(unique_urls) > 0:
            url_counts = prompt_citations['url'].value_counts()
            # We look for "Stable" as appearing in at least 3 runs
            # If a prompt only has 3 runs, it must be in all 3.
            stable_urls = (url_counts >= 3).sum()
            partial_urls = (url_counts == 2).sum()
            one_off_urls = (url_counts == 1).sum()
            
            stability_score = stable_urls / len(unique_urls) if len(unique_urls) > 0 else 0
        else:
            stable_urls = partial_urls = one_off_urls = 0
            stability_score = 0
            
        results.append({
            'prompt_id': prompt_id,
            'total_runs': total_runs,
            'rag_runs': rag_runs,
            'rag_failure_rate': (total_runs - rag_runs) / total_runs,
            'unique_citations': len(unique_urls),
            'stable_citations_3plus': stable_urls,
            'one_off_citations': one_off_urls,
            'stability_pct': stability_score * 100
        })
        
    summary_df = pd.DataFrame(results)
    
    print("\n=== Cross-Run Consistency Summary ===")
    print(f"Total Prompts Analyzed: {len(summary_df)}")
    print(f"Average RAG Failure Rate: {summary_df['rag_failure_rate'].mean()*100:.2f}%")
    print(f"Average Citation Stability (3+ runs): {summary_df['stability_pct'].mean():.2f}%")
    
    # Identify prompts with high RAG inconsistency
    inconsistent_rag = summary_df[(summary_df['rag_runs'] > 0) & (summary_df['rag_runs'] < summary_df['total_runs'])]
    print(f"\nPrompts with Stochastic RAG (Some runs failed RAG): {len(inconsistent_rag)}")
    if len(inconsistent_rag) > 0:
        print(inconsistent_rag[['prompt_id', 'total_runs', 'rag_runs']].head(10).to_string(index=False))
    
    summary_df.to_csv('data/metrics/cross_run_consistency_report.csv', index=False)
    print("\nFull report saved to data/metrics/cross_run_consistency_report.csv")

if __name__ == "__main__":
    analyze_consistency()
