#!/usr/bin/env python3
"""
Ingest Google SERP results from SerpAPI JSON files into the database.
Then analyze overlap with ChatGPT citations, especially for URLs Bing missed.
"""

import sqlite3
import json
import os
from urllib.parse import urlparse
from collections import defaultdict

DB_PATH = 'geo_fresh.db'
GOOGLE_RESULTS_DIR = 'data/serpapi_google_results'
ACCOUNT_FILTER = os.environ.get('GOOGLE_INGEST_ACCOUNT_FILTER', 'personal')  # personal|enterprise|all

def normalize_url(url):
    """Normalize URL for comparison (remove trailing slashes, www, etc.)"""
    if not url:
        return ''
    url = url.lower().strip()
    if url.endswith('/'):
        url = url[:-1]
    # Remove www. prefix
    parsed = urlparse(url)
    netloc = parsed.netloc.replace('www.', '')
    return f"{parsed.scheme}://{netloc}{parsed.path}"

def get_domain(url):
    """Extract domain from URL"""
    if not url:
        return ''
    try:
        parsed = urlparse(url)
        return parsed.netloc.replace('www.', '').lower()
    except:
        return ''

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # Check existing tables
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    print(f"Existing tables: {tables}")
    
    # Create google_results table with page_num for pagination
    # NOTE: we do NOT drop the table; we may ingest personal and enterprise in separate passes.
    conn.execute('''
        CREATE TABLE IF NOT EXISTS google_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            chatgpt_run_id TEXT,
            prompt_id TEXT,
            account_type TEXT,
            query TEXT,
            query_type TEXT,
            page_num INTEGER,
            position INTEGER,
            global_position INTEGER,
            url TEXT,
            domain TEXT,
            title TEXT,
            snippet TEXT,
            result_type TEXT,
            collected_at TEXT
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_google_chatgpt_run ON google_results(chatgpt_run_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_google_domain ON google_results(domain)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_google_account ON google_results(account_type)')
    conn.commit()
    
    # Clear existing data for this ingest pass (keeps other account_type data)
    if ACCOUNT_FILTER == 'all':
        conn.execute('DELETE FROM google_results')
    else:
        conn.execute('DELETE FROM google_results WHERE account_type = ?', (ACCOUNT_FILTER,))
    conn.commit()
    
    # Load all Google results
    files = [f for f in os.listdir(GOOGLE_RESULTS_DIR) if f.endswith('.json')]
    print(f"\nLoading {len(files)} Google result files...")
    
    personal_count = 0
    enterprise_count = 0
    total_urls = 0
    
    for filename in files:
        filepath = os.path.join(GOOGLE_RESULTS_DIR, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            query_info = data.get('_query_info', {})
            account_type = query_info.get('account_type', 'unknown')
            query_type = query_info.get('query_type', '')

            # Ingest account filter
            if ACCOUNT_FILTER != 'all' and account_type != ACCOUNT_FILTER:
                continue
            if query_type != 'hidden_query':
                continue
            
            # Extract page number from search_parameters.start (0=page1, 10=page2, etc.)
            search_params = data.get('search_parameters', {})
            start = int(search_params.get('start', 0) or 0)
            page_num = (start // 10) + 1
            
            # Track counts
            if account_type == 'personal':
                personal_count += 1
            else:
                enterprise_count += 1
            
            # Insert organic results
            for result in data.get('organic_results', []):
                url = result.get('link', '')
                pos = result.get('position') or 0
                global_pos = (page_num - 1) * 10 + pos
                conn.execute('''
                    INSERT INTO google_results 
                    (run_id, chatgpt_run_id, prompt_id, account_type, query, query_type,
                     page_num, position, global_position, url, domain, title, snippet, result_type, collected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    query_info.get('run_id'),
                    query_info.get('chatgpt_run_id'),
                    query_info.get('prompt_id'),
                    account_type,
                    query_info.get('query'),
                    query_info.get('query_type'),
                    page_num,
                    pos,
                    global_pos,
                    url,
                    get_domain(url),
                    result.get('title'),
                    result.get('snippet'),
                    'organic',
                    query_info.get('collected_at')
                ))
                total_urls += 1
            
            # Also insert video results (valuable!)
            for result in data.get('inline_videos', []):
                url = result.get('link', '')
                pos = result.get('position') or 0
                global_pos = (page_num - 1) * 10 + pos
                conn.execute('''
                    INSERT INTO google_results 
                    (run_id, chatgpt_run_id, prompt_id, account_type, query, query_type,
                     page_num, position, global_position, url, domain, title, snippet, result_type, collected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    query_info.get('run_id'),
                    query_info.get('chatgpt_run_id'),
                    query_info.get('prompt_id'),
                    account_type,
                    query_info.get('query'),
                    query_info.get('query_type'),
                    page_num,
                    pos,
                    global_pos,
                    url,
                    get_domain(url),
                    result.get('title'),
                    None,
                    'video',
                    query_info.get('collected_at')
                ))
                total_urls += 1

            # Insert related questions (PAA) that have links
            paa_idx = 0
            for result in data.get('related_questions', []):
                url = result.get('link', '')
                if not url:
                    continue
                paa_idx += 1
                conn.execute('''
                    INSERT INTO google_results 
                    (run_id, chatgpt_run_id, prompt_id, account_type, query, query_type,
                     page_num, position, global_position, url, domain, title, snippet, result_type, collected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    query_info.get('run_id'),
                    query_info.get('chatgpt_run_id'),
                    query_info.get('prompt_id'),
                    account_type,
                    query_info.get('query'),
                    query_info.get('query_type'),
                    page_num,
                    paa_idx,  # Use index as position for PAA
                    0,  # global_position not meaningful for PAA
                    url,
                    get_domain(url),
                    result.get('question') or result.get('title'),
                    result.get('snippet'),
                    'related_question',
                    query_info.get('collected_at')
                ))
                total_urls += 1

            # Insert discussions and forums
            disc_idx = 0
            for result in data.get('discussions_and_forums', []):
                url = result.get('link', '')
                if not url:
                    continue
                disc_idx += 1
                conn.execute('''
                    INSERT INTO google_results 
                    (run_id, chatgpt_run_id, prompt_id, account_type, query, query_type,
                     page_num, position, global_position, url, domain, title, snippet, result_type, collected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    query_info.get('run_id'),
                    query_info.get('chatgpt_run_id'),
                    query_info.get('prompt_id'),
                    account_type,
                    query_info.get('query'),
                    query_info.get('query_type'),
                    page_num,
                    disc_idx,  # Use index as position for discussions
                    0,  # global_position not meaningful for discussions
                    url,
                    get_domain(url),
                    result.get('title'),
                    result.get('snippet'),
                    'discussion',
                    query_info.get('collected_at')
                ))
                total_urls += 1
                
        except Exception as e:
            print(f"  Error loading {filename}: {e}")
    
    conn.commit()
    print(f"\n[OK] Ingested {total_urls} URLs from {len(files)} files")
    print(f"   Personal queries: {personal_count}")
    print(f"   Enterprise queries: {enterprise_count}")
    
    # Deduplicate by URL (keep first occurrence per query+url+result_type)
    before_dedup = conn.execute('SELECT COUNT(*) FROM google_results').fetchone()[0]
    conn.execute('''
        DELETE FROM google_results 
        WHERE rowid NOT IN (
            SELECT MIN(rowid) 
            FROM google_results 
            GROUP BY chatgpt_run_id, account_type, query, url, result_type
        )
    ''')
    conn.commit()
    after_dedup = conn.execute('SELECT COUNT(*) FROM google_results').fetchone()[0]
    print(f"   Deduped: {before_dedup} -> {after_dedup} ({before_dedup - after_dedup} duplicates removed)")
    
    # ========== ANALYSIS: Google vs ChatGPT Citations (Personal Only) ==========
    print("\n" + "="*60)
    print("GOOGLE OVERLAP ANALYSIS (Personal Runs Only)")
    print("="*60)
    
    # Get all ChatGPT cited URLs for personal runs
    cited_urls = {}
    for row in conn.execute('''
        SELECT DISTINCT c.url, c.run_id, c.prompt_id
        FROM citations c
        JOIN runs r ON c.run_id = r.run_id
        WHERE r.account_type = 'personal' AND c.citation_type = 'cited'
    '''):
        url = normalize_url(row[0])
        if url:
            if url not in cited_urls:
                cited_urls[url] = []
            cited_urls[url].append({'run_id': row[1], 'prompt_id': row[2]})
    
    print(f"\nTotal unique cited URLs (Personal): {len(cited_urls)}")
    
    # Get all Google URLs for personal runs
    google_urls = set()
    for row in conn.execute('''
        SELECT DISTINCT url FROM google_results WHERE account_type = 'personal'
    '''):
        url = normalize_url(row[0])
        if url:
            google_urls.add(url)
    
    print(f"Total unique Google URLs (Personal): {len(google_urls)}")
    
    # Get all Bing URLs for personal runs
    bing_urls = set()
    for row in conn.execute('''
        SELECT DISTINCT b.url 
        FROM bing_results b
        JOIN runs r ON b.run_id = r.run_id
        WHERE r.account_type = 'personal'
    '''):
        url = normalize_url(row[0])
        if url:
            bing_urls.add(url)
    
    print(f"Total unique Bing URLs (Personal): {len(bing_urls)}")
    
    # Calculate overlaps
    cited_in_google = set(cited_urls.keys()) & google_urls
    cited_in_bing = set(cited_urls.keys()) & bing_urls
    cited_not_in_bing = set(cited_urls.keys()) - bing_urls
    
    # THE KEY QUESTION: Of citations Bing missed, how many does Google have?
    bing_missed_but_google_has = cited_not_in_bing & google_urls
    truly_invisible = cited_not_in_bing - google_urls
    
    print("\n--- OVERLAP RESULTS ---")
    print(f"Cited URLs found in Bing:   {len(cited_in_bing):>4} ({100*len(cited_in_bing)/len(cited_urls):.1f}%)")
    print(f"Cited URLs found in Google: {len(cited_in_google):>4} ({100*len(cited_in_google)/len(cited_urls):.1f}%)")
    
    print(f"\n--- THE KEY INSIGHT ---")
    print(f"Citations Bing MISSED:      {len(cited_not_in_bing):>4} ({100*len(cited_not_in_bing)/len(cited_urls):.1f}%)")
    print(f"  -> Found in Google:       {len(bing_missed_but_google_has):>4} ({100*len(bing_missed_but_google_has)/len(cited_not_in_bing):.1f}% of Bing misses)")
    print(f"  -> Truly Invisible:       {len(truly_invisible):>4} ({100*len(truly_invisible)/len(cited_not_in_bing):.1f}% of Bing misses)")
    
    # Combined coverage
    found_in_either = cited_in_bing | cited_in_google
    print(f"\n--- COMBINED COVERAGE ---")
    print(f"Found in Bing OR Google:    {len(found_in_either):>4} ({100*len(found_in_either)/len(cited_urls):.1f}%)")
    print(f"Not found in either:        {len(set(cited_urls.keys()) - found_in_either):>4} ({100*len(set(cited_urls.keys()) - found_in_either)/len(cited_urls):.1f}%)")
    
    # Show some examples of "Bing missed but Google has"
    if bing_missed_but_google_has:
        print(f"\n--- EXAMPLES: URLs Bing missed but Google found ---")
        for url in list(bing_missed_but_google_has)[:10]:
            domain = get_domain(url)
            print(f"  - {domain}")
    
    # Show some examples of "Truly Invisible"
    if truly_invisible:
        print(f"\n--- EXAMPLES: Truly Invisible (neither Bing nor Google) ---")
        for url in list(truly_invisible)[:10]:
            domain = get_domain(url)
            print(f"  - {domain}")
    
    conn.close()
    print("\n[DONE] Analysis complete!")

if __name__ == '__main__':
    main()
