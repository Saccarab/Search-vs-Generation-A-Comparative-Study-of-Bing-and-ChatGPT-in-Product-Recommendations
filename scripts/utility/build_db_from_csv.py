"""
Build SQLite Database directly from CSV files.
Orders: Enterprise first, then Personal.
"""

import sqlite3
import pandas as pd
import json
import os
import glob

DB_PATH = 'geo_fresh.db'

# Enterprise data
ENTERPRISE_CHATGPT = 'datapass/chatgpt_results_2026-01-27T11-23-04-enterprise.csv'
ENTERPRISE_BING_CSV = 'datapass/parital-2-enterprise.csv'
ENTERPRISE_BING_JSON = 'datapass/partial_scraping_results-enterprise.json'

# Personal data
PERSONAL_CHATGPT = 'datapass/personal_data_run/chatgpt_results_2026-01-28T02-25-34.csv'
PERSONAL_BING_PART1 = 'datapass/personal_data_run/bing_partial_2026-perso-part1-01-28T09-17-18.csv'
PERSONAL_BING_PART2 = 'datapass/personal_data_run/bing_results_2026-perso-part2-01-28T19-24-52.csv'

def normalize_url(url):
    if not url or pd.isna(url):
        return ""
    url = str(url).lower().strip()
    url = url.replace('https://', '').replace('http://', '').replace('www.', '')
    if '?' in url:
        url = url.split('?')[0]
    if '#' in url:
        url = url.split('#')[0]
    if url.endswith('/'):
        url = url[:-1]
    return url

def extract_domain(url):
    if not url:
        return ""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url if url.startswith('http') else f'https://{url}')
        return parsed.netloc.replace('www.', '')
    except:
        return ""

def main():
    print('Building Database from CSVs...\n')
    
    # Remove existing DB
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create schema
    print('Creating schema...')
    
    cursor.execute('''
        CREATE TABLE prompts (
            prompt_id TEXT PRIMARY KEY,
            prompt TEXT,
            category TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE runs (
            run_id TEXT PRIMARY KEY,
            prompt_id TEXT,
            run_number INTEGER,
            query TEXT,
            generated_search_query TEXT,
            web_search_triggered TEXT,
            web_search_forced TEXT,
            items_count INTEGER,
            items_with_citations_count INTEGER,
            hidden_queries TEXT,
            items_json TEXT,
            response_text TEXT,
            search_result_groups_json TEXT,
            sources_cited_json TEXT,
            sources_additional_json TEXT,
            sources_all_json TEXT,
            sonic_classification_json TEXT,
            hidden_queries_json TEXT,
            account_type TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE citations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            prompt_id TEXT,
            run_number INTEGER,
            citation_type TEXT,
            position INTEGER,
            url TEXT,
            url_normalized TEXT,
            title TEXT,
            domain TEXT,
            account_type TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE bing_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            query TEXT,
            position INTEGER,
            page_num INTEGER,
            title TEXT,
            url TEXT,
            url_normalized TEXT,
            domain TEXT,
            snippet TEXT,
            account_type TEXT
        )
    ''')
    
    # ========== LOAD ENTERPRISE DATA ==========
    print('\n--- ENTERPRISE DATA ---')
    
    # Enterprise ChatGPT
    print('Loading Enterprise ChatGPT...')
    ent_chatgpt = pd.read_csv(ENTERPRISE_CHATGPT, low_memory=False)
    print(f'   {len(ent_chatgpt)} rows')
    
    # Insert prompts (unique prompt_id + query)
    prompts_inserted = set()
    for _, row in ent_chatgpt.iterrows():
        pid = row['prompt_id']
        if pid not in prompts_inserted:
            cursor.execute('INSERT OR IGNORE INTO prompts VALUES (?, ?, ?)', 
                          (pid, row['query'], None))
            prompts_inserted.add(pid)
    print(f'   Inserted {len(prompts_inserted)} prompts')
    
    for _, row in ent_chatgpt.iterrows():
        run_id = f"{row['prompt_id']}_r{row['run_number']}"
        
        # Parse hidden queries for display
        hidden_queries = ''
        try:
            hq = json.loads(row.get('hidden_queries_json') or '[]')
            if hq:
                if isinstance(hq[0], dict):
                    hidden_queries = ' | '.join([q.get('query', '') for q in hq])
                else:
                    hidden_queries = ' | '.join(hq)
        except:
            pass
        
        cursor.execute('''
            INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            run_id,
            row['prompt_id'],
            row['run_number'],
            row['query'],
            row.get('generated_search_query'),
            row.get('web_search_triggered'),
            row.get('web_search_forced'),
            row.get('items_count'),
            row.get('items_with_citations_count'),
            hidden_queries,
            row.get('items_json'),
            row.get('response_text'),
            row.get('search_result_groups_json'),
            row.get('sources_cited_json'),
            row.get('sources_additional_json'),
            row.get('sources_all_json'),
            row.get('sonic_classification_json'),
            row.get('hidden_queries_json'),
            'enterprise'
        ))
        
        # Extract citations
        try:
            cited = json.loads(row.get('sources_cited_json') or '[]')
            for i, src in enumerate(cited):
                cursor.execute('''
                    INSERT INTO citations (run_id, prompt_id, run_number, citation_type, position, url, url_normalized, title, domain, account_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (run_id, row['prompt_id'], row['run_number'], 'cited', i+1, src.get('url'), normalize_url(src.get('url')), src.get('title'), extract_domain(src.get('url')), 'enterprise'))
        except:
            pass
        
        try:
            additional = json.loads(row.get('sources_additional_json') or '[]')
            for i, src in enumerate(additional):
                cursor.execute('''
                    INSERT INTO citations (run_id, prompt_id, run_number, citation_type, position, url, url_normalized, title, domain, account_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (run_id, row['prompt_id'], row['run_number'], 'additional', i+1, src.get('url'), normalize_url(src.get('url')), src.get('title'), extract_domain(src.get('url')), 'enterprise'))
        except:
            pass
    
    # Enterprise Bing (CSV + JSON combined)
    print('Loading Enterprise Bing...')
    ent_bing = pd.read_csv(ENTERPRISE_BING_CSV, low_memory=False)
    print(f'   CSV: {len(ent_bing)} rows')
    
    # Also load JSON
    with open(ENTERPRISE_BING_JSON, 'r', encoding='utf-8') as f:
        ent_bing_json = json.load(f)
    print(f'   JSON: {len(ent_bing_json)} rows')
    
    # Insert CSV
    for _, row in ent_bing.iterrows():
        cursor.execute('''
            INSERT INTO bing_results (run_id, query, position, page_num, title, url, url_normalized, domain, snippet, account_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (row.get('run_id'), row.get('query'), row.get('position'), row.get('page_num'), row.get('title'), row.get('url'), normalize_url(row.get('url')), extract_domain(row.get('url')), row.get('snippet'), 'enterprise'))
    
    # Insert JSON (only queries not in CSV)
    csv_queries = set(ent_bing['query'].unique())
    json_added = 0
    for row in ent_bing_json:
        if row.get('query') not in csv_queries:
            cursor.execute('''
                INSERT INTO bing_results (run_id, query, position, page_num, title, url, url_normalized, domain, snippet, account_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (row.get('run_id'), row.get('query'), row.get('position'), row.get('page_num'), row.get('title'), row.get('url'), normalize_url(row.get('url')), extract_domain(row.get('url')), row.get('snippet'), 'enterprise'))
            json_added += 1
    print(f'   JSON-only added: {json_added}')
    
    # ========== LOAD PERSONAL DATA ==========
    print('\n--- PERSONAL DATA ---')
    
    # Personal ChatGPT
    print('Loading Personal ChatGPT...')
    pers_chatgpt = pd.read_csv(PERSONAL_CHATGPT, low_memory=False)
    print(f'   {len(pers_chatgpt)} rows')
    
    for _, row in pers_chatgpt.iterrows():
        run_id = f"{row['prompt_id']}_r{row['run_number']}_personal"
        
        # Parse hidden queries for display
        hidden_queries = ''
        try:
            hq = json.loads(row.get('hidden_queries_json') or '[]')
            if hq:
                if isinstance(hq[0], dict):
                    hidden_queries = ' | '.join([q.get('query', '') for q in hq])
                else:
                    hidden_queries = ' | '.join(hq)
        except:
            pass
        
        cursor.execute('''
            INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            run_id,
            row['prompt_id'],
            row['run_number'],
            row['query'],
            row.get('generated_search_query'),
            row.get('web_search_triggered'),
            row.get('web_search_forced'),
            row.get('items_count'),
            row.get('items_with_citations_count'),
            hidden_queries,
            row.get('items_json'),
            row.get('response_text'),
            row.get('search_result_groups_json'),
            row.get('sources_cited_json'),
            row.get('sources_additional_json'),
            row.get('sources_all_json'),
            row.get('sonic_classification_json'),
            row.get('hidden_queries_json'),
            'personal'
        ))
        
        # Extract citations
        try:
            cited = json.loads(row.get('sources_cited_json') or '[]')
            for i, src in enumerate(cited):
                cursor.execute('''
                    INSERT INTO citations (run_id, prompt_id, run_number, citation_type, position, url, url_normalized, title, domain, account_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (run_id, row['prompt_id'], row['run_number'], 'cited', i+1, src.get('url'), normalize_url(src.get('url')), src.get('title'), extract_domain(src.get('url')), 'personal'))
        except:
            pass
        
        try:
            additional = json.loads(row.get('sources_additional_json') or '[]')
            for i, src in enumerate(additional):
                cursor.execute('''
                    INSERT INTO citations (run_id, prompt_id, run_number, citation_type, position, url, url_normalized, title, domain, account_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (run_id, row['prompt_id'], row['run_number'], 'additional', i+1, src.get('url'), normalize_url(src.get('url')), src.get('title'), extract_domain(src.get('url')), 'personal'))
        except:
            pass
    
    # Personal Bing
    print('Loading Personal Bing...')
    pers_bing1 = pd.read_csv(PERSONAL_BING_PART1, low_memory=False)
    pers_bing2 = pd.read_csv(PERSONAL_BING_PART2, low_memory=False)
    print(f'   Part 1: {len(pers_bing1)} rows')
    print(f'   Part 2: {len(pers_bing2)} rows')
    
    for _, row in pers_bing1.iterrows():
        run_id_orig = row.get('run_id') or ''
        run_id = f"{run_id_orig}_personal" if run_id_orig else ''
        cursor.execute('''
            INSERT INTO bing_results (run_id, query, position, page_num, title, url, url_normalized, domain, snippet, account_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (run_id, row.get('query'), row.get('position'), row.get('page_num'), row.get('title'), row.get('url'), normalize_url(row.get('url')), extract_domain(row.get('url')), row.get('snippet'), 'personal'))
    
    for _, row in pers_bing2.iterrows():
        run_id_orig = row.get('run_id') or ''
        run_id = f"{run_id_orig}_personal" if run_id_orig else ''
        cursor.execute('''
            INSERT INTO bing_results (run_id, query, position, page_num, title, url, url_normalized, domain, snippet, account_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (run_id, row.get('query'), row.get('position'), row.get('page_num'), row.get('title'), row.get('url'), normalize_url(row.get('url')), extract_domain(row.get('url')), row.get('snippet'), 'personal'))
    
    # Create indexes
    print('\nCreating indexes...')
    cursor.execute('CREATE INDEX idx_runs_account ON runs(account_type)')
    cursor.execute('CREATE INDEX idx_citations_run ON citations(run_id)')
    cursor.execute('CREATE INDEX idx_citations_url ON citations(url_normalized)')
    cursor.execute('CREATE INDEX idx_citations_account ON citations(account_type)')
    cursor.execute('CREATE INDEX idx_bing_run ON bing_results(run_id)')
    cursor.execute('CREATE INDEX idx_bing_url ON bing_results(url_normalized)')
    cursor.execute('CREATE INDEX idx_bing_query ON bing_results(query)')
    cursor.execute('CREATE INDEX idx_bing_account ON bing_results(account_type)')
    
    conn.commit()
    
    # Summary
    cursor.execute('SELECT account_type, COUNT(*) FROM runs GROUP BY account_type')
    runs_counts = cursor.fetchall()
    cursor.execute('SELECT account_type, COUNT(*) FROM citations GROUP BY account_type')
    cit_counts = cursor.fetchall()
    cursor.execute('SELECT account_type, COUNT(*) FROM bing_results GROUP BY account_type')
    bing_counts = cursor.fetchall()
    
    print('\n=== SUMMARY ===')
    print('Runs:', dict(runs_counts))
    print('Citations:', dict(cit_counts))
    print('Bing Results:', dict(bing_counts))
    print(f'\nDatabase saved: {DB_PATH}')
    
    conn.close()

if __name__ == '__main__':
    main()
