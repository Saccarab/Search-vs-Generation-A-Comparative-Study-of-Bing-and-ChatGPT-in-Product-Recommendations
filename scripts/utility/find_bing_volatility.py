"""
Find Bing Volatility Cases

Identifies URLs that are:
- Cited by ChatGPT across multiple runs of the same prompt
- But appear in Bing results for some runs and NOT others

This reveals the "disappearing results" bug in Bing pagination.
"""

import sqlite3
import pandas as pd
from collections import defaultdict

DB_PATH = 'geo_fresh.db'

def main():
    print('🔍 Finding Bing Volatility Cases...\n')
    
    conn = sqlite3.connect(DB_PATH)
    
    # Get all citations grouped by prompt_id
    citations = pd.read_sql('''
        SELECT c.prompt_id, c.run_number, c.url_normalized, c.url, c.domain,
               (SELECT MIN(b.position) FROM bing_results b WHERE b.url_normalized = c.url_normalized AND b.run_id = c.run_id) as bing_rank,
               c.run_id
        FROM citations c
        ORDER BY c.prompt_id, c.url_normalized, c.run_number
    ''', conn)
    
    print(f'Total citations: {len(citations)}')
    
    # Group by prompt_id and url
    volatility_cases = []
    
    for prompt_id in citations['prompt_id'].unique():
        prompt_cits = citations[citations['prompt_id'] == prompt_id]
        
        # Get all unique URLs cited in any run of this prompt
        for url_norm in prompt_cits['url_normalized'].unique():
            url_cits = prompt_cits[prompt_cits['url_normalized'] == url_norm]
            
            # Check if this URL is cited in multiple runs
            if len(url_cits) >= 2:
                has_bing = url_cits[url_cits['bing_rank'].notna()]
                no_bing = url_cits[url_cits['bing_rank'].isna()]
                
                # VOLATILITY: Same URL, cited in multiple runs, but Bing match varies
                if len(has_bing) > 0 and len(no_bing) > 0:
                    volatility_cases.append({
                        'prompt_id': prompt_id,
                        'url': url_cits.iloc[0]['url'],
                        'domain': url_cits.iloc[0]['domain'],
                        'runs_with_bing': list(has_bing['run_id'].values),
                        'runs_without_bing': list(no_bing['run_id'].values),
                        'bing_ranks': list(has_bing['bing_rank'].values)
                    })
    
    print(f'\n🚨 Found {len(volatility_cases)} volatility cases!\n')
    print('=' * 80)
    
    for case in volatility_cases[:20]:  # Show first 20
        print(f"\n📍 Prompt: {case['prompt_id']}")
        print(f"   Domain: {case['domain']}")
        print(f"   URL: {case['url'][:60]}...")
        print(f"   ✓ IN BING: {case['runs_with_bing']} (Ranks: {case['bing_ranks']})")
        print(f"   ✗ NOT IN BING: {case['runs_without_bing']}")
    
    # Summary stats
    print('\n' + '=' * 80)
    print('\n📊 SUMMARY:')
    print(f'   Total volatility cases: {len(volatility_cases)}')
    
    # Count by domain
    domain_counts = defaultdict(int)
    for case in volatility_cases:
        domain_counts[case['domain']] += 1
    
    print(f'\n   Top volatile domains:')
    for domain, count in sorted(domain_counts.items(), key=lambda x: -x[1])[:10]:
        print(f'      {domain}: {count} cases')
    
    conn.close()

if __name__ == '__main__':
    main()
