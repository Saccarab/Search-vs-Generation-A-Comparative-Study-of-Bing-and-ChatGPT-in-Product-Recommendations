import sqlite3
import pandas as pd
from flask import Flask, render_template_string, request
import json
import os

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>GEO Research Dashboard</title>
    <style>
        body { font-family: -apple-system, sans-serif; background: #f4f4f9; margin: 0; padding: 40px; }
        .nav { margin-bottom: 30px; }
        .nav a { text-decoration: none; color: #10a37f; font-weight: bold; margin-right: 20px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .card { background: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
        h2 { margin-top: 0; color: #333; font-size: 18px; border-bottom: 2px solid #f0f0f0; padding-bottom: 10px; }
        .stat-big { font-size: 36px; font-weight: bold; color: #10a37f; }
        .stat-label { color: #666; font-size: 14px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { text-align: left; padding: 8px; border-bottom: 1px solid #eee; font-size: 13px; }
        .bar-container { background: #eee; height: 20px; border-radius: 10px; overflow: hidden; margin-top: 5px; }
        .bar { background: #10a37f; height: 100%; }
        .slump { background: #f87171 !important; }
    </style>
</head>
<body>
    <div class="nav">
        <a href="/">← Back to Run Viewer</a>
    </div>
    <h1>GEO Research Dashboard - Enterprise</h1>
    
    <div class="grid">
        <div class="card">
            <h2>Overall Coverage (Deep Hunt Top 200)</h2>
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:15px;">
                <div style="background:#f9fafb; padding:15px; border-radius:8px; text-align:center;">
                    <div class="stat-label">All Citations</div>
                    <div class="stat-big">{{ "%.1f"|format(matched_all / total_all * 100 if total_all > 0 else 0) }}%</div>
                    <div style="font-size:11px; color:#666;">{{ matched_all }} / {{ total_all }}</div>
                </div>
                <div style="background:#ecfdf5; padding:15px; border-radius:8px; text-align:center;">
                    <div class="stat-label" style="color:#065f46; font-weight:bold;">Cited Only</div>
                    <div class="stat-big" style="color:#059669;">{{ "%.1f"|format(matched_main / total_main * 100 if total_main > 0 else 0) }}%</div>
                    <div style="font-size:11px; color:#065f46;">{{ matched_main }} / {{ total_main }}</div>
                </div>
            </div>
        </div>
        
        <div class="card">
            <h2>Top Invisible Domains (Not in Bing)</h2>
            <table>
                <tr><th>Domain</th><th>Count</th></tr>
                {% for row in invisible_domains[:15] %}
                <tr><td>{{ row[0] }}</td><td>{{ row[1] }}</td></tr>
                {% endfor %}
            </table>
        </div>
        
        <div class="card">
            <h2>Page Distribution of Matches</h2>
            <table>
                <tr><th>Page</th><th>Matches</th></tr>
                {% for row in page_data %}
                <tr><td>Page {{ row[0] }}</td><td>{{ row[1] }}</td></tr>
                {% endfor %}
            </table>
        </div>
    </div>
</body>
</html>
"""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>ChatGPT + Bing Enterprise Viewer</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; display: flex; height: 100vh; margin: 0; background: #f4f4f9; }
        #sidebar { width: 280px; background: #202123; color: white; overflow-y: auto; padding: 15px; flex-shrink: 0; }
        #content { flex-grow: 1; overflow-y: auto; padding: 40px; display: flex; flex-direction: column; gap: 30px; }
        .prompt-item { padding: 8px; cursor: pointer; border-radius: 5px; margin-bottom: 5px; font-size: 13px; border-left: 4px solid transparent; }
        .prompt-item:hover { background: #343541; }
        .prompt-item.active { background: #444654; font-weight: bold; border-left-color: #10a37f; }
        
        .card { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
        .header { margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 10px; }
        .query-pill { background: #e7f3ff; color: #007bff; padding: 5px 15px; border-radius: 20px; font-size: 14px; font-weight: bold; display: inline-block; margin-right: 10px; margin-bottom: 5px; }
        .hidden-queries { background: #fef3c7; color: #d97706; padding: 5px 15px; border-radius: 20px; font-size: 12px; display: inline-block; margin-bottom: 5px; }

        .comparison-container { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .source-label { font-size: 12px; font-weight: bold; color: #888; text-transform: uppercase; margin-bottom: 10px; display: block; }
        
        .citation-item { margin-bottom: 12px; padding: 10px; background: #f9fafb; border-radius: 8px; border-left: 4px solid #10a37f; }
        .citation-item.additional { border-left-color: #6b7280; }
        .citation-type { font-size: 10px; padding: 2px 6px; border-radius: 4px; text-transform: uppercase; font-weight: bold; margin-right: 6px; }
        .citation-type.cited { background: #d1fae5; color: #065f46; }
        .citation-type.additional { background: #f3f4f6; color: #6b7280; }
        .citation-title { font-weight: bold; color: #111; font-size: 14px; }
        .citation-url { font-size: 12px; color: #10a37f; word-break: break-all; }
        .bing-rank { background: #10a37f; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; margin-left: 8px; }
        .bing-rank.not-found { background: #ef4444; }
        
        .bing-item { padding: 10px; border-bottom: 1px solid #eee; }
        .bing-item.matched { background: #fef9c3; }
        .bing-rank-num { background: #6b7280; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; margin-right: 10px; }
        .bing-title { font-weight: bold; color: #111; font-size: 13px; }
        .bing-url { font-size: 11px; color: #10a37f; word-break: break-all; }
        .bing-snippet { font-size: 12px; color: #666; margin-top: 4px; }
        
        .raw-text-box { 
            white-space: pre-wrap; font-family: monospace; font-size: 12px; color: #555; 
            background: #f8f9fa; padding: 15px; border-radius: 5px; border: 1px solid #eee; 
            max-height: 400px; overflow-y: auto; margin-top: 10px;
        }
        a { color: #10a37f; text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div id="sidebar">
        <div style="margin-bottom: 20px; padding: 10px; background: #10a37f; border-radius: 5px; text-align: center;">
            <a href="/dashboard" style="text-decoration:none; color:white; font-weight:bold;">📊 VIEW DASHBOARD</a>
        </div>
        <h3 style="color:#888; font-size:12px;">RUNS ({{ run_ids|length }})</h3>
        {% for rid in run_ids %}
        <a href="/?run_id={{ rid }}" style="text-decoration:none; color:inherit;">
            <div class="prompt-item {{ 'active' if rid == active_run_id else '' }}">
                {{ rid }}
            </div>
        </a>
        {% endfor %}
    </div>
    
    <div id="content">
        {% if run_raw %}
        <div class="card">
            <div class="header">
                <h2 style="margin:0 0 10px 0;">{{ active_run_id }}</h2>
                <div class="query-pill">Prompt: {{ run_raw.query }}</div>
                {% if run_raw.hidden_queries %}
                <div class="hidden-queries">🔍 Hidden Queries: {{ run_raw.hidden_queries }}</div>
                {% endif %}
            </div>
            
            <!-- Stats Bar -->
            <div style="display: flex; gap: 15px; margin-bottom: 15px; flex-wrap: wrap;">
                <div style="background: {{ '#d1fae5' if run_raw.web_search_triggered == 'True' or run_raw.web_search_triggered == True else '#fee2e2' }}; padding: 6px 12px; border-radius: 6px; font-size: 12px;">
                    <strong>Web Search:</strong> {{ '✓ Triggered' if run_raw.web_search_triggered == 'True' or run_raw.web_search_triggered == True else '✗ Not Triggered' }}
                </div>
                {% if run_raw.web_search_forced %}
                <div style="background: #fef3c7; padding: 6px 12px; border-radius: 6px; font-size: 12px;">
                    <strong>Forced:</strong> {{ run_raw.web_search_forced }}
                </div>
                {% endif %}
                <div style="background: #e0e7ff; padding: 6px 12px; border-radius: 6px; font-size: 12px;">
                    <strong>Items:</strong> {{ run_raw.items_count or 0 }}
                </div>
                <div style="background: #f3e8ff; padding: 6px 12px; border-radius: 6px; font-size: 12px;">
                    <strong>With Citations:</strong> {{ run_raw.items_with_citations_count or 0 }}
                </div>
                <div style="background: #f3f4f6; padding: 6px 12px; border-radius: 6px; font-size: 12px;">
                    <strong>Total Sources:</strong> {{ cit_db|length }}
                </div>
            </div>

            <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 20px;">
                <!-- LEFT: Unified ChatGPT Response Feed -->
                <div>
                    <span class="source-label">ChatGPT Response</span>
                    
                    <!-- Unified Response Feed -->
                    <div style="background: #f7f7f8; border-radius: 12px; padding: 20px; margin-top: 10px;">
                        {% if items_raw %}
                            {% for item in items_raw %}
                            {% set link_count = namespace(value=0) %}
                            {% if item.chip_groups %}
                                {% for g in item.chip_groups %}
                                    {% set link_count.value = link_count.value + (g.links|length if g.links else 0) %}
                                {% endfor %}
                            {% endif %}
                            <div style="margin-bottom: 20px;">
                                <div style="font-size: 14px; color: #111; line-height: 1.7;">
                                    <strong style="color: #10a37f;">{{ item.item_position }}. {{ item.item_name or '' }}</strong>
                                    {% if item.item_text %} – {{ item.item_text }}{% endif %}
                                </div>
                                {% if item.chip_groups %}
                                <div style="margin-top: 8px; display: flex; flex-wrap: wrap; gap: 6px;">
                                    {% for group in item.chip_groups %}
                                        {% for link in group.links %}
                                        {% set clean_url = link.replace('?utm_source=chatgpt.com', '').replace('https://', '').replace('http://', '').replace('www.', '').split('?')[0].rstrip('/') %}
                                        {% set bing_match = namespace(found=false, rank=None, q_num=None) %}
                                        {% for cit in cit_db %}
                                            {% set cit_url_clean = (cit.url or '').replace('https://', '').replace('http://', '').replace('www.', '').split('?')[0].rstrip('/') %}
                                            {% if clean_url == cit_url_clean or clean_url in cit_url_clean or cit_url_clean in clean_url %}
                                                {% if cit.bing_rank %}
                                                    {% set bing_match.found = true %}
                                                    {% set bing_match.rank = cit.bing_rank %}
                                                    {% set bing_match.q_num = cit.bing_query_num %}
                                                {% endif %}
                                            {% endif %}
                                        {% endfor %}
                                        <a href="{{ link }}" target="_blank" style="font-size: 11px; background: {{ '#d1fae5' if bing_match.found else '#fee2e2' }}; color: {{ '#065f46' if bing_match.found else '#991b1b' }}; padding: 4px 10px; border-radius: 15px; text-decoration: none; display: inline-flex; align-items: center; gap: 4px;">
                                            {{ clean_url[:35] }}{% if clean_url|length > 35 %}...{% endif %}
                                            {% if bing_match.found %}
                                            <span style="background: #10a37f; color: white; padding: 1px 5px; border-radius: 8px; font-size: 9px; font-weight: bold;">
                                                #{{ bing_match.rank }} Q{{ bing_match.q_num }}
                                            </span>
                                            {% endif %}
                                        </a>
                                        {% endfor %}
                                    {% endfor %}
                                </div>
                                {% endif %}
                            </div>
                            {% endfor %}
                        {% else %}
                            <div style="color: #888; font-style: italic;">Loading response...</div>
                        {% endif %}
                        
                        <!-- All Citations Summary -->
                        <div style="border-top: 1px solid #ddd; margin-top: 15px; padding-top: 15px;">
                            <div style="font-size: 11px; color: #666; font-weight: bold; margin-bottom: 8px;">ALL SOURCES ({{ cit_db|length }})</div>
                            <div style="display: flex; flex-wrap: wrap; gap: 4px;">
                            {% for cit in cit_db %}
                                <div style="font-size: 10px; background: {{ '#d1fae5' if cit.bing_rank else '#fee2e2' }}; color: {{ '#065f46' if cit.bing_rank else '#991b1b' }}; padding: 3px 8px; border-radius: 10px;">
                                    {{ cit.domain }}
                                    {% if cit.bing_rank %}
                                    <span style="font-weight: bold;">#{{ cit.bing_rank }}</span>
                                    {% else %}
                                    <span style="font-weight: bold;">✗</span>
                                    {% endif %}
                                </div>
                            {% endfor %}
                            </div>
                        </div>
                    </div>
                    
                    <!-- Raw Response (collapsible) -->
                    <details style="margin-top: 15px;">
                        <summary style="cursor: pointer; font-size: 12px; color: #666; font-weight: bold;">RAW RESPONSE TEXT</summary>
                        <div class="raw-text-box" style="margin-top: 10px;">{{ run_raw.response_text or 'No response text available' }}</div>
                    </details>

                    {% if prompt_volatility %}
                    <div style="margin-top: 20px; padding: 12px; background: #fff1f2; border: 1px solid #fda4af; border-radius: 8px;">
                        <h3 style="margin-top:0; color: #9f1239; font-size: 13px;">🚨 BING VOLATILITY ({{ prompt_volatility|length }} cases)</h3>
                        <div style="max-height: 150px; overflow-y: auto;">
                            {% for case in prompt_volatility %}
                            <div style="margin-bottom: 8px; padding: 6px; background: white; border-radius: 4px; font-size: 10px; border-left: 2px solid #f43f5e;">
                                <strong>{{ case.domain }}</strong><br>
                                <span style="color: #059669;">✓ Found in: {{ case.in_bing|join(', ') }}</span><br>
                                <span style="color: #dc2626;">✗ Missing in: {{ case.not_in_bing|join(', ') }}</span>
                            </div>
                            {% endfor %}
                        </div>
                    </div>
                    {% endif %}
                </div>
                
                <!-- RIGHT: Bing Results -->
                <div>
                    <div style="display: flex; flex-direction: column; gap: 8px; margin-bottom: 10px;">
                        <span class="source-label" style="margin-bottom:0;">Bing Results ({{ bing_results|length }})</span>
                        <div id="query-filters" style="font-size: 10px;">
                            {% for q_text in unique_queries %}
                            <label style="cursor:pointer; display: flex; align-items: center; gap: 4px; background: #f3f4f6; padding: 3px 6px; border-radius: 4px; margin-bottom: 4px;">
                                <input type="checkbox" class="query-toggle" data-query="{{ q_text }}" checked> 
                                <strong style="color:#007bff;">Q{{ loop.index }}:</strong> <span style="color:#555;">{{ q_text[:40] }}...</span>
                            </label>
                            {% endfor %}
                        </div>
                    </div>
                    
                    <div id="bing-results-container" style="max-height: 700px; overflow-y: auto;">
                    {% for b in bing_results %}
                    {% set q_num = '?' %}
                    {% if b['query'] in unique_queries %}
                        {% set q_num = unique_queries.index(b['query']) + 1 %}
                    {% endif %}
                    <div class="bing-item {{ 'matched' if b['is_cited'] else '' }}" data-query-text="{{ b['query'] }}" style="padding: 8px; border-bottom: 1px solid #eee; font-size: 12px;">
                        <span class="bing-rank-num" style="font-size: 10px;">#{{ b['position'] }}</span>
                        <span style="background:#e0e7ff; color:#3730a3; padding:1px 4px; border-radius:3px; font-size:9px; font-weight:bold;">Q{{ q_num }}</span>
                        <span style="background:#f3f4f6; color:#666; padding:1px 4px; border-radius:3px; font-size:9px; margin-left:4px;">Pg {{ b['page_num'] or '?' }}</span>
                        {% if b['is_cited'] %}<span style="color:#10a37f; font-size:10px; font-weight:bold;">✓</span>{% endif %}
                        <div style="font-weight: bold; color: #111; font-size: 11px; margin-top: 2px;">{{ (b['title'] or 'No title')[:50] }}...</div>
                        <div style="font-size: 10px; color: #10a37f;">{{ b['domain'] }}</div>
                    </div>
                    {% endfor %}
                    </div>
                </div>
            </div>
        </div>

        <script>
            document.querySelectorAll('.query-toggle').forEach(checkbox => {
                checkbox.addEventListener('change', function() {
                    const queryText = this.getAttribute('data-query');
                    const isVisible = this.checked;
                    
                    document.querySelectorAll(`.bing-item[data-query-text="${queryText}"]`).forEach(item => {
                        item.style.display = isVisible ? 'block' : 'none';
                    });
                });
            });
        </script>
        
        {% else %}
        <div class="card">
            <h2>Welcome to ChatGPT + Bing Enterprise Viewer</h2>
            <p>Select a run from the sidebar to view its citations and Bing results.</p>
            <p><strong>Stats:</strong></p>
            <ul>
                <li>{{ run_ids|length }} total runs</li>
                <li>86,938 Bing Deep Hunt results</li>
                <li>4,457 ChatGPT citations</li>
            </ul>
        </div>
        {% endif %}
    </div>
</body>
</html>
"""

app = Flask(__name__)

DB_PATH = 'geo_fresh.db'

# Load the raw CSV once at startup
print(f"Loading raw data from {DB_PATH} (Database Only Mode)...")
df_raw = pd.DataFrame() # We are using the DB for everything now

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    run_id = request.args.get('run_id')
    db = get_db()
    
    run_ids = [r['run_id'] for r in db.execute('SELECT run_id FROM runs ORDER BY prompt_id, run_number').fetchall()]
    
    run_raw = None
    cit_db = []
    bing_results = []
    items_raw = []
    unique_queries = []
    prompt_volatility = []
    
    if run_id:
        # Get run data from database
        db_run = db.execute('''
            SELECT p.prompt as query, r.generated_search_query, r.response_text, r.hidden_queries, r.items_json,
                   r.web_search_triggered, r.web_search_forced, r.items_count, r.items_with_citations_count
            FROM runs r
            LEFT JOIN prompts p ON r.prompt_id = p.prompt_id
            WHERE r.run_id = ?
        ''', (run_id,)).fetchone()
        
        if db_run:
            run_raw = {
                'query': db_run['query'] or 'N/A',
                'generated_search_query': db_run['generated_search_query'] or 'N/A',
                'response_text': db_run['response_text'] or '',
                'hidden_queries': db_run['hidden_queries'] or '',
                'web_search_triggered': db_run['web_search_triggered'],
                'web_search_forced': db_run['web_search_forced'],
                'items_count': db_run['items_count'],
                'items_with_citations_count': db_run['items_with_citations_count']
            }
            # Parse items_json for structured display
            try:
                items_raw = json.loads(db_run['items_json'] or '[]')
            except:
                items_raw = []
        else:
            run_raw = {'query': 'N/A', 'generated_search_query': 'N/A', 'response_text': f'Run {run_id} not found', 'hidden_queries': '', 'web_search_triggered': None, 'web_search_forced': None, 'items_count': 0, 'items_with_citations_count': 0}

        # Get citations with Bing rank AND which query it came from
        cit_rows = db.execute('''
            SELECT c.*, 
                   (SELECT MIN(b.position) FROM bing_results b WHERE b.url_normalized = c.url_normalized AND b.run_id = c.run_id) as bing_rank,
                   (SELECT b.query FROM bing_results b WHERE b.url_normalized = c.url_normalized AND b.run_id = c.run_id ORDER BY b.position ASC LIMIT 1) as bing_query
            FROM citations c 
            WHERE c.run_id = ?
            ORDER BY c.citation_type, c.position
        ''', (run_id,)).fetchall()
        
        cit_db = [dict(row) for row in cit_rows]
        
        # Map query text to Q1/Q2 number
        query_to_num = {q: i+1 for i, q in enumerate(sorted(list(set(b['query'] for b in db.execute('SELECT DISTINCT query FROM bing_results WHERE run_id = ?', (run_id,)).fetchall()))))}
        for cit in cit_db:
            if cit.get('bing_query'):
                cit['bing_query_num'] = query_to_num.get(cit['bing_query'], '?')
        
        # Get Bing results with citation match flag
        bing_rows = db.execute('''
            SELECT b.*, 
                   EXISTS(SELECT 1 FROM citations c WHERE c.run_id = b.run_id AND c.url_normalized = b.url_normalized) as is_cited
            FROM bing_results b 
            WHERE b.run_id = ? 
            ORDER BY b.position ASC
        ''', (run_id,)).fetchall()
        
        bing_results = [dict(row) for row in bing_rows]

        # Get unique queries for this run to power the checkboxes
        unique_queries = sorted(list(set(b['query'] for b in bing_results)))

        # Get volatility cases for this prompt
        if db_run:
            volatility_cases = db.execute('''
                SELECT c.url_normalized, c.domain, 
                       GROUP_CONCAT(DISTINCT r.run_id) as cited_runs
                FROM citations c
                JOIN runs r ON c.run_id = r.run_id
                WHERE c.prompt_id = ?
                GROUP BY c.url_normalized
                HAVING COUNT(DISTINCT c.run_id) >= 2
            ''', (db_run['prompt_id'],)).fetchall()
            
            for case in volatility_cases:
                url_norm = case['url_normalized']
                bing_status = db.execute('''
                    SELECT r.run_id, b.position, b.page_num
                    FROM runs r
                    LEFT JOIN bing_results b ON r.run_id = b.run_id AND b.url_normalized = ?
                    WHERE r.prompt_id = ?
                ''', (url_norm, db_run['prompt_id'])).fetchall()
                
                has_bing = [r for r in bing_status if r['position'] is not None]
                no_bing = [r for r in bing_status if r['position'] is None]
                
                if has_bing and no_bing:
                    prompt_volatility.append({
                        'domain': case['domain'],
                        'url_norm': url_norm,
                        'in_bing': [f"{r['run_id']} (Rank #{r['position']} Pg {r['page_num']})" for r in has_bing],
                        'not_in_bing': [r['run_id'] for r in no_bing]
                    })

    return render_template_string(HTML_TEMPLATE, 
                                 run_ids=run_ids, 
                                 active_run_id=run_id,
                                 run_raw=run_raw,
                                 cit_db=cit_db,
                                 bing_results=bing_results,
                                 unique_queries=unique_queries if run_id else [],
                                 items_raw=items_raw,
                                 prompt_volatility=prompt_volatility)

@app.route('/dashboard')
def dashboard():
    db = get_db()
    
    # Page-based distribution
    page_data = db.execute('''
        SELECT b.page_num, COUNT(DISTINCT c.id) as match_count
        FROM bing_results b
        JOIN citations c ON c.url_normalized = b.url_normalized AND c.run_id = b.run_id
        WHERE b.page_num IS NOT NULL
        GROUP BY b.page_num
        ORDER BY b.page_num
    ''').fetchall()
    
    # Coverage Stats
    match_sql = """
        EXISTS (SELECT 1 FROM bing_results b WHERE b.run_id = c.run_id AND b.url_normalized = c.url_normalized)
    """

    # All Citations
    total_all = db.execute('SELECT COUNT(*) FROM citations').fetchone()[0]
    matched_all = db.execute(f'SELECT COUNT(DISTINCT c.id) FROM citations c WHERE {match_sql}').fetchone()[0]

    # Main Citations (cited type)
    total_main = db.execute("SELECT COUNT(*) FROM citations WHERE citation_type = 'cited'").fetchone()[0]
    matched_main = db.execute(f"SELECT COUNT(DISTINCT c.id) FROM citations c WHERE citation_type = 'cited' AND {match_sql}").fetchone()[0]

    # Top Invisible Domains (not in Bing results)
    invisible_domains = db.execute('''
        SELECT domain, COUNT(*) as count
        FROM citations c
        WHERE NOT EXISTS (
            SELECT 1 FROM bing_results b 
            WHERE b.run_id = c.run_id 
              AND b.url_normalized = c.url_normalized
        )
        GROUP BY domain
        ORDER BY count DESC
        LIMIT 100
    ''').fetchall()

    return render_template_string(DASHBOARD_TEMPLATE, 
                                 page_data=page_data,
                                 total_all=total_all,
                                 matched_all=matched_all,
                                 total_main=total_main,
                                 matched_main=matched_main,
                                 invisible_domains=invisible_domains)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
