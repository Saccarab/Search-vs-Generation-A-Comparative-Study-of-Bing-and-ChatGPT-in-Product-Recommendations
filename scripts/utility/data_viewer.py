import sqlite3
import pandas as pd
from flask import Flask, render_template_string, request
import json
import os

app = Flask(__name__)
app.jinja_env.add_extension('jinja2.ext.do')
DB_PATH = 'geo_fresh.db'
# Combined legit results from 01-17 and 01-18
RAW_CSV_PATH = r'data/ingest/chatgpt_results_viewer_combined.csv'

# Load the raw CSV once at startup
print(f"Loading raw data from {RAW_CSV_PATH}...")
try:
    df_raw = pd.read_csv(RAW_CSV_PATH, low_memory=False)
    if 'run_id' not in df_raw.columns:
        df_raw['run_id'] = df_raw['prompt_id'].astype(str) + '_r' + df_raw['run_number'].astype(str)
    df_raw = df_raw.set_index('run_id')
    print(f"Successfully loaded {len(df_raw)} runs from CSV.")
except Exception as e:
    print(f"Error loading CSV: {e}")
    df_raw = pd.DataFrame()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>GEO Data Consistency Viewer (Deep Hunt Edition)</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; display: flex; height: 100vh; margin: 0; background: #f4f4f9; }
        #sidebar { width: 280px; background: #202123; color: white; overflow-y: auto; padding: 15px; flex-shrink: 0; }
        #content { flex-grow: 1; overflow-y: auto; padding: 40px; display: flex; flex-direction: column; gap: 30px; }
        .prompt-item { padding: 8px; cursor: pointer; border-radius: 5px; margin-bottom: 5px; font-size: 13px; border-left: 4px solid transparent; }
        .prompt-item:hover { background: #343541; }
        .prompt-item.active { background: #444654; font-weight: bold; border-left-color: #10a37f; }
        
        .card { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
        .header { margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }
        .query-pill { background: #e7f3ff; color: #007bff; padding: 5px 15px; border-radius: 20px; font-size: 14px; font-weight: bold; display: inline-block; }
        
        .mode-toggle { display: flex; gap: 10px; margin-bottom: 20px; }
        .mode-btn { padding: 8px 16px; border-radius: 5px; border: 1px solid #ddd; background: #fff; cursor: pointer; font-weight: bold; }
        .mode-btn.active { background: #10a37f; color: white; border-color: #10a37f; }

        .comparison-container { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .source-label { font-size: 12px; font-weight: bold; color: #888; text-transform: uppercase; margin-bottom: 10px; display: block; }
        
        .chatgpt-items { margin: 0; padding: 0; list-style: none; }
        .chatgpt-item { margin-bottom: 15px; line-height: 1.6; font-size: 14px; position: relative; padding-left: 20px; }
        .chatgpt-item::before { content: "•"; position: absolute; left: 0; color: #10a37f; font-weight: bold; }
        .item-name { font-weight: bold; color: #000; }
        
        .chip-group { display: inline-flex; gap: 4px; margin-left: 8px; vertical-align: middle; flex-wrap: wrap; }
        .citation-pill { background: #f0f0f0; border: 1px solid #e0e0e0; border-radius: 12px; padding: 1px 8px; font-size: 10px; color: #666; text-decoration: none; display: inline-block; white-space: nowrap; }
        
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th { text-align: left; background: #f8f9fa; padding: 12px; border-bottom: 2px solid #dee2e6; }
        td { padding: 12px; border-bottom: 1px solid #eee; font-size: 13px; vertical-align: top; }
        .rank-badge { background: #6e6e80; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; }
        .match-row { background: #fff9c4 !important; }
        a { color: #10a37f; text-decoration: none; }
        
        .raw-text-box { 
            white-space: pre-wrap; font-family: monospace; font-size: 12px; color: #555; background: #f8f9fa; padding: 15px; border-radius: 5px; border: 1px solid #eee; max-height: 300px; overflow-y: auto; margin-top: 20px;
        }
    </style>
</head>
<body>
    <div id="sidebar">
        <h3>Runs</h3>
        {% for rid in run_ids %}
        <a href="/?run_id={{ rid }}&mode={{ mode }}" style="text-decoration:none; color:inherit;">
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
                <div>
                    <div class="query-pill">Query: {{ run_raw.query }}</div>
                    <div class="query-pill" style="background:#fef3c7; color:#d97706; margin-left:10px;">Bing: {{ run_raw.generated_search_query }}</div>
                </div>
                <h2 style="margin:0;">Consistency Check</h2>
            </div>

            <div class="mode-toggle">
                <a href="/?run_id={{ active_run_id }}&mode=standard" class="mode-btn {{ 'active' if mode == 'standard' else '' }}">Standard (Top 30)</a>
                <a href="/?run_id={{ active_run_id }}&mode=deep" class="mode-btn {{ 'active' if mode == 'deep' else '' }}">Deep Hunt (Rank 150)</a>
            </div>

            <div class="comparison-container">
                <div style="border-right: 1px solid #eee; padding-right: 20px;">
                    <span class="source-label">Source: Raw ChatGPT Response</span>
                    <div class="chatgpt-items">
                        {% if items_raw %}
                            {% for item in items_raw %}
                            <div class="chatgpt-item">
                                <span class="item-name">{{ item.item_name }}</span>
                                <p style="margin: 4px 0;">{{ item.item_text }}</p>
                                <div class="chip-group">
                                    {% for group in item.chip_groups %}
                                        {% for link in group.links %}
                                        <a href="{{ link }}" class="citation-pill" target="_blank">Source</a>
                                        {% endfor %}
                                    {% endfor %}
                                </div>
                            </div>
                            {% endfor %}
                        {% else %}
                            <div style="white-space: pre-wrap; font-size: 13px;">{{ run_raw.response_text }}</div>
                        {% endif %}
                    </div>
                </div>

                <div style="padding-left: 10px;">
                    <span class="source-label">Citations In Excel ({{ cit_db|length }} found)</span>
                    <div class="excel-citation-list">
                        {% for c in cit_db %}
                        <div style="margin-bottom: 8px; border-bottom: 1px dashed #eee; padding-bottom: 4px;">
                            <div style="font-weight:bold; color:#10a37f;">
                                [{{ c.citation_type }}] {{ c.item_entity_name or c.item_name or 'N/A' }}
                                {% set found_rank = [] %}
                                {% for b in bing %}
                                    {% if b.url == c.url or b.result_domain == c.citation_domain %}
                                        {% do found_rank.append(b.result_rank or b.absolute_rank) %}
                                    {% endif %}
                                {% endfor %}
                                {% if found_rank %}
                                    <a href="#rank-{{ found_rank[0] }}" style="margin-left:10px; background:#fff9c4; color:#d97706; padding:1px 6px; border-radius:4px; font-size:10px; border:1px solid #d97706;">RANK {{ found_rank[0] }}</a>
                                {% else %}
                                    <span style="margin-left:10px; background:#fee2e2; color:#b91c1c; padding:1px 6px; border-radius:4px; font-size:10px; border:1px solid #b91c1c;">NOT IN TOP 150</span>
                                {% endif %}
                            </div>
                            <div style="font-size:11px; color:#666;">{{ c.url }}</div>
                        </div>
                        {% endfor %}
                    </div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="header">
                <h2 style="margin:0;">Bing Results ({{ mode.upper() }} Mode)</h2>
            </div>
            <table>
                <thead>
                    <tr>
                        <th style="width: 50px;">Rank</th>
                        <th>Title & URL</th>
                        <th>Domain Match</th>
                    </tr>
                </thead>
                <tbody>
                    {% for b in bing %}
                    <tr id="rank-{{ b.result_rank or b.absolute_rank }}" class="{{ 'match-row' if b.is_cited else '' }}">
                        <td>
                            <span class="rank-badge">{{ b.result_rank or b.absolute_rank }}</span>
                            <div style="font-size: 9px; color: #888; margin-top: 2px;">Pg {{ b.page_num or ((((b.absolute_rank|int) - 1) // 10) + 1) }}</div>
                        </td>
                        <td>
                            <div style="font-weight:bold;"><a href="{{ b.url }}" target="_blank">{{ b.result_title or b.title or b.url }}</a></div>
                            <div style="font-size:11px; color:#666;">{{ b.url }}</div>
                        </td>
                        <td>
                            <span style="font-weight:500;">{{ b.result_domain }}</span>
                            {% if b.is_cited %}<br><b style="color:#d97706; font-size:10px;">[CITED]</b>{% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% else %}
        <div style="text-align:center; margin-top:100px; color:#888;">
            <h1>Select a run from the sidebar</h1>
        </div>
        {% endif %}
    </div>
</body>
</html>
"""

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    run_id = request.args.get('run_id')
    mode = request.args.get('mode', 'standard')
    db = get_db()
    
    run_ids = [r['run_id'] for r in db.execute('SELECT run_id FROM runs ORDER BY prompt_id, run_id').fetchall()]
    
    run_raw = None
    items_raw = []
    cit_db = []
    bing_results = []
    
    if run_id:
        if run_id in df_raw.index:
            row_raw = df_raw.loc[run_id]
            if isinstance(row_raw, pd.DataFrame): row_raw = row_raw.iloc[0]
            run_raw = {
                'query': row_raw.get('query', ''),
                'generated_search_query': row_raw.get('generated_search_query', ''),
                'response_text': row_raw.get('response_text', '')
            }
            try:
                items_raw = json.loads(row_raw.get('items_json', '[]'))
            except:
                items_raw = []
        else:
            run_raw = {'query': 'N/A', 'generated_search_query': 'N/A', 'response_text': 'Run not found in CSV'}

        cit_db = db.execute('SELECT * FROM citations WHERE run_id = ?', (run_id,)).fetchall()
        
        if mode == 'deep':
            # Query the new bing_deep_hunt table
            bing_results = db.execute('''
                SELECT *, 
                EXISTS(SELECT 1 FROM citations c WHERE c.run_id = b.run_id AND (c.url = b.url OR c.citation_domain = b.result_domain)) as is_cited,
                (absolute_rank > 30) as is_deep_match
                FROM bing_deep_hunt b 
                WHERE run_id = ? 
                ORDER BY absolute_rank ASC
            ''', (run_id,)).fetchall()
        else:
            # Standard Top 30
            bing_results = db.execute('''
                SELECT *, 
                EXISTS(SELECT 1 FROM citations c WHERE c.run_id = b.run_id AND (c.url = b.url OR c.citation_domain = b.result_domain)) as is_cited,
                0 as is_deep_match
                FROM bing_results b 
                WHERE run_id = ? 
                ORDER BY result_rank ASC
            ''', (run_id,)).fetchall()

    return render_template_string(HTML_TEMPLATE, 
                                 run_ids=run_ids, 
                                 active_run_id=run_id,
                                 run_raw=run_raw,
                                 items_raw=items_raw,
                                 cit_db=cit_db,
                                 bing=bing_results,
                                 mode=mode)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
