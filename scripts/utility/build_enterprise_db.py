"""
Build SQLite Database from geo-enterprise-master.xlsx + ChatGPT CSVs

This creates the database structure expected by data_viewer.py
Supports both Enterprise and Personal account data.
"""

import sqlite3
import pandas as pd
from openpyxl import load_workbook
import json
import os

EXCEL_PATH = 'datapass/geo-enterprise-master.xlsx'
# Enterprise ChatGPT CSV (for rich data like items_json, hidden_queries_json)
CHATGPT_CSV_ENTERPRISE = 'datapass/chatgpt_results_2026-01-27T11-23-04-enterprise.csv'
# Personal ChatGPT CSV
CHATGPT_CSV_PERSONAL = 'datapass/personal_data_run/chatgpt_results_2026-01-28T02-25-34.csv'
DB_PATH = 'geo_fresh.db'

def normalize_url(url):
    """Normalize URL for matching - strips protocol, www, query params, trailing slash"""
    if not url or pd.isna(url):
        return ""
    url = str(url).lower().strip()
    url = url.replace('https://', '').replace('http://', '').replace('www.', '')
    # Strip query parameters
    if '?' in url:
        url = url.split('?')[0]
    # Strip fragment
    if '#' in url:
        url = url.split('#')[0]
    if url.endswith('/'):
        url = url[:-1]
    return url

def main():
    print('📦 Building Enterprise Database...\n')
    
    # Load Excel sheets
    print('📖 Reading Excel workbook...')
    wb = load_workbook(EXCEL_PATH, read_only=True, data_only=True)
    
    prompts_df = pd.DataFrame(wb['prompts_updated'].values)
    prompts_df.columns = prompts_df.iloc[0]
    prompts_df = prompts_df[1:]
    
    runs_df = pd.DataFrame(wb['runs'].values)
    runs_df.columns = runs_df.iloc[0]
    runs_df = runs_df[1:]
    
    citations_df = pd.DataFrame(wb['citations'].values)
    citations_df.columns = citations_df.iloc[0]
    citations_df = citations_df[1:]
    
    bing_df = pd.DataFrame(wb['bing_results'].values)
    bing_df.columns = bing_df.iloc[0]
    bing_df = bing_df[1:]
    
    urls_df = pd.DataFrame(wb['urls'].values)
    urls_df.columns = urls_df.iloc[0]
    urls_df = urls_df[1:]
    
    print(f'   Prompts: {len(prompts_df)}')
    print(f'   Runs: {len(runs_df)}')
    print(f'   Citations: {len(citations_df)}')
    print(f'   Bing Results: {len(bing_df)}')
    print(f'   URLs: {len(urls_df)}')
    
    # Create database
    print('\n🔨 Creating database schema...')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Prompts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prompts (
            prompt_id TEXT PRIMARY KEY,
            prompt TEXT,
            category TEXT
        )
    ''')
    
    # Runs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            prompt_id TEXT,
            run_number INTEGER,
            query TEXT,
            generated_search_query TEXT,
            web_search_triggered TEXT,
            web_search_forced TEXT,
            items_count INTEGER,
            items_with_citations_count INTEGER,
            sources_cited_count INTEGER,
            sources_all_count INTEGER,
            domains_cited TEXT,
            hidden_queries TEXT,
            items_json TEXT,
            response_text TEXT,
            search_result_groups_json TEXT,
            sources_cited_json TEXT,
            sources_additional_json TEXT,
            sources_all_json TEXT,
            sonic_classification_json TEXT,
            hidden_queries_json TEXT,
            account_type TEXT DEFAULT 'enterprise',
            FOREIGN KEY (prompt_id) REFERENCES prompts(prompt_id)
        )
    ''')
    
    # Citations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS citations (
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
            account_type TEXT DEFAULT 'enterprise',
            FOREIGN KEY (run_id) REFERENCES runs(run_id)
        )
    ''')
    
    # Bing results table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bing_results (
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
            has_content TEXT,
            content_length INTEGER,
            account_type TEXT DEFAULT 'enterprise'
        )
    ''')
    
    # URLs enrichment table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS url_enrichment (
            url TEXT PRIMARY KEY,
            url_normalized TEXT,
            type TEXT,
            domain TEXT,
            content_word_count INTEGER,
            tone TEXT,
            has_tables TEXT,
            has_pros_cons TEXT,
            expertise_signal_score REAL,
            readability_score REAL
        )
    ''')
    
    print('✅ Schema created')
    
    # Insert data
    print('\n📥 Inserting data...')
    
    # Insert prompts (note: column is 'prompt_text' not 'prompt')
    prompts_data = []
    for _, row in prompts_df.iterrows():
        prompts_data.append((
            row.get('prompt_id'),
            row.get('prompt_text'),  # Fixed column name
            row.get('prompt_intent_type')  # Use intent type as category
        ))
    cursor.executemany('INSERT OR IGNORE INTO prompts VALUES (?, ?, ?)', prompts_data)
    print(f'   Prompts: {len(prompts_data)}')
    
    # Load ChatGPT CSVs for rich data (both enterprise and personal)
    print('   Loading ChatGPT CSVs for rich data...')
    chatgpt_map = {}
    
    # Enterprise CSV
    if os.path.exists(CHATGPT_CSV_ENTERPRISE):
        chatgpt_df = pd.read_csv(CHATGPT_CSV_ENTERPRISE, low_memory=False)
        for _, row in chatgpt_df.iterrows():
            run_id = f"{row.get('prompt_id')}_r{row.get('run_number')}"
            chatgpt_map[run_id] = {
                'items_json': row.get('items_json'),
                'response_text': row.get('response_text'),
                'hidden_queries_json': row.get('hidden_queries_json'),
                'web_search_forced': row.get('web_search_forced'),
                'web_search_triggered': row.get('web_search_triggered'),
                'items_count': row.get('items_count'),
                'items_with_citations_count': row.get('items_with_citations_count'),
                'search_result_groups_json': row.get('search_result_groups_json'),
                'sources_cited_json': row.get('sources_cited_json'),
                'sources_additional_json': row.get('sources_additional_json'),
                'sources_all_json': row.get('sources_all_json'),
                'sonic_classification_json': row.get('sonic_classification_json')
            }
        print(f'      Enterprise CSV: {len(chatgpt_df)} rows')
    
    # Personal CSV
    if os.path.exists(CHATGPT_CSV_PERSONAL):
        personal_df = pd.read_csv(CHATGPT_CSV_PERSONAL, low_memory=False)
        for _, row in personal_df.iterrows():
            run_id = f"{row.get('prompt_id')}_r{row.get('run_number')}_personal"
            chatgpt_map[run_id] = {
                'items_json': row.get('items_json'),
                'response_text': row.get('response_text'),
                'hidden_queries_json': row.get('hidden_queries_json'),
                'web_search_forced': row.get('web_search_forced'),
                'web_search_triggered': row.get('web_search_triggered'),
                'items_count': row.get('items_count'),
                'items_with_citations_count': row.get('items_with_citations_count'),
                'search_result_groups_json': row.get('search_result_groups_json'),
                'sources_cited_json': row.get('sources_cited_json'),
                'sources_additional_json': row.get('sources_additional_json'),
                'sources_all_json': row.get('sources_all_json'),
                'sonic_classification_json': row.get('sonic_classification_json')
            }
        print(f'      Personal CSV: {len(personal_df)} rows')
    
    # Insert runs with all rich data from CSV (from Excel which has account_type)
    runs_data = []
    for _, row in runs_df.iterrows():
        run_id = row.get('run_id')
        if not run_id:
            run_id = f"{row.get('prompt_id')}_r{row.get('run_number')}"
        
        csv_data = chatgpt_map.get(run_id, {})
        account_type = row.get('account_type') or 'enterprise'
        
        # Parse hidden queries from JSON
        hidden_queries = row.get('hidden_queries') or ''
        hq_json = csv_data.get('hidden_queries_json')
        if not hidden_queries and hq_json:
            try:
                hq = json.loads(str(hq_json))
                # Handle both formats: array of strings and array of objects
                if hq and isinstance(hq, list):
                    if isinstance(hq[0], str):
                        hidden_queries = ' | '.join(hq)
                    elif isinstance(hq[0], dict):
                        hidden_queries = ' | '.join([q.get('query', '') for q in hq])
            except:
                pass
        
        runs_data.append((
            run_id,
            row.get('prompt_id'),
            row.get('run_number'),
            row.get('query'),
            row.get('generated_search_query'),
            csv_data.get('web_search_triggered') or row.get('web_search_triggered'),
            csv_data.get('web_search_forced'),
            csv_data.get('items_count') or row.get('items_count'),
            csv_data.get('items_with_citations_count'),
            row.get('sources_cited_count'),
            row.get('sources_all_count'),
            row.get('domains_cited'),
            hidden_queries,
            csv_data.get('items_json'),
            csv_data.get('response_text'),
            csv_data.get('search_result_groups_json'),
            csv_data.get('sources_cited_json'),
            csv_data.get('sources_additional_json'),
            csv_data.get('sources_all_json'),
            csv_data.get('sonic_classification_json'),
            str(hq_json) if hq_json else None,
            account_type
        ))
    cursor.executemany('''INSERT OR REPLACE INTO runs 
        (run_id, prompt_id, run_number, query, generated_search_query, web_search_triggered, 
         web_search_forced, items_count, items_with_citations_count, sources_cited_count, 
         sources_all_count, domains_cited, hidden_queries, items_json, response_text, 
         search_result_groups_json, sources_cited_json, sources_additional_json, sources_all_json,
         sonic_classification_json, hidden_queries_json, account_type) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', runs_data)
    print(f'   Runs: {len(runs_data)}')
    
    # Insert citations (with account_type from Excel)
    citations_data = []
    for _, row in citations_df.iterrows():
        run_id = row.get('run_id')
        if not run_id:
            run_id = f"{row.get('prompt_id')}_r{row.get('run_number')}"
        url = row.get('url')
        account_type = row.get('account_type') or 'enterprise'
        citations_data.append((
            run_id,
            row.get('prompt_id'),
            row.get('run_number'),
            row.get('citation_type'),
            row.get('position'),
            url,
            normalize_url(url),
            row.get('title'),
            row.get('domain'),
            account_type
        ))
    cursor.executemany('INSERT INTO citations (run_id, prompt_id, run_number, citation_type, position, url, url_normalized, title, domain, account_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', citations_data)
    print(f'   Citations: {len(citations_data)}')
    
    # Insert Bing results (with account_type from Excel)
    bing_data = []
    for _, row in bing_df.iterrows():
        url = row.get('url')
        account_type = row.get('account_type') or 'enterprise'
        bing_data.append((
            row.get('run_id'),
            row.get('query'),
            row.get('position'),
            row.get('page_num'),
            row.get('title'),
            url,
            normalize_url(url),
            row.get('domain'),
            row.get('snippet'),
            row.get('has_content'),
            row.get('content_length'),
            account_type
        ))
    cursor.executemany('INSERT INTO bing_results (run_id, query, position, page_num, title, url, url_normalized, domain, snippet, has_content, content_length, account_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', bing_data)
    print(f'   Bing Results: {len(bing_data)}')
    
    # Insert URL enrichment
    enrichment_data = []
    for _, row in urls_df.iterrows():
        url = row.get('url')
        enrichment_data.append((
            url,
            normalize_url(url),
            row.get('type'),
            row.get('domain'),
            row.get('content_word_count'),
            row.get('tone'),
            row.get('has_tables'),
            row.get('has_pros_cons'),
            row.get('expertise_signal_score'),
            row.get('readability_score')
        ))
    cursor.executemany('INSERT OR REPLACE INTO url_enrichment VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', enrichment_data)
    print(f'   URL Enrichments: {len(enrichment_data)}')
    
    # Create indexes for faster queries
    print('\n🔗 Creating indexes...')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_citations_run ON citations(run_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_citations_url_norm ON citations(url_normalized)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_citations_account ON citations(account_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_bing_run ON bing_results(run_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_bing_url_norm ON bing_results(url_normalized)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_bing_account ON bing_results(account_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_runs_account ON runs(account_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_enrichment_url_norm ON url_enrichment(url_normalized)')
    
    conn.commit()
    conn.close()
    
    print(f'\n✨ Database created successfully: {DB_PATH}')
    print(f'   Total size: {pd.read_sql("SELECT COUNT(*) as count FROM citations", sqlite3.connect(DB_PATH)).iloc[0]["count"]} citations')
    print(f'   Bing coverage: {pd.read_sql("SELECT COUNT(*) as count FROM bing_results", sqlite3.connect(DB_PATH)).iloc[0]["count"]} results')

if __name__ == '__main__':
    main()
