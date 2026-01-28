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
        <a href="/">← Back to Consistency Viewer</a>
    </div>
    <h1>GEO Research Dashboard</h1>
    
    <div class="grid">
        <div class="card">
            <h2>Overall Coverage (Standard + Deep Hunt)</h2>
            <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:15px;">
                <!-- All Citations -->
                <div style="background:#f9fafb; padding:15px; border-radius:8px; text-align:center;">
                    <div class="stat-label">Combined (All)</div>
                    <div class="stat-big">{{ "%.1f"|format(matched_all_strict / total_all * 100) }}% <span style="font-size:12px; color:#666;">(Strict)</span></div>
                    <div class="stat-big" style="font-size:18px; color:#999;">{{ "%.1f"|format(matched_all_domain / total_all * 100) }}% <span style="font-size:10px;">(Domain)</span></div>
                </div>
                
                <!-- Main Citations -->
                <div style="background:#ecfdf5; padding:15px; border-radius:8px; text-align:center;">
                    <div class="stat-label" style="color:#065f46; font-weight:bold;">Core Recommendations</div>
                    <div class="stat-big" style="color:#059669;">{{ "%.1f"|format(matched_main_strict / total_main * 100) }}% <span style="font-size:12px;">(Strict)</span></div>
                    <div class="stat-big" style="font-size:18px; color:#059669; opacity:0.6;">{{ "%.1f"|format(matched_main_domain / total_main * 100) }}% <span style="font-size:10px;">(Domain)</span></div>
                </div>

                <!-- Additional Citations -->
                <div style="background:#f3f4f6; padding:15px; border-radius:8px; text-align:center;">
                    <div class="stat-label">"Additional" Links</div>
                    <div class="stat-big" style="color:#4b5563;">{{ "%.1f"|format(matched_add_strict / total_add * 100) }}% <span style="font-size:12px;">(Strict)</span></div>
                    <div class="stat-big" style="font-size:18px; color:#4b5563; opacity:0.6;">{{ "%.1f"|format(matched_add_domain / total_add * 100) }}% <span style="font-size:10px;">(Domain)</span></div>
                </div>
            </div>
            
            <div style="margin-top:20px; padding-top:15px; border-top:1px solid #eee;">
                <h3 style="font-size:14px; margin:0 0 10px 0; color:#666;">Standard Top 30 vs Deep Hunt (All Citations)</h3>
                <div style="display:flex; gap:20px;">
                    <div>
                        <span style="font-weight:bold; color:#d97706;">{{ "%.1f"|format(matched_top30 / total_all * 100) }}%</span>
                        <span style="font-size:12px; color:#666;">Top 30 Only</span>
                    </div>
                    <div>
                        <span style="font-weight:bold; color:#10a37f;">{{ "%.1f"|format(matched_deep / total_all * 100) }}%</span>
                        <span style="font-size:12px; color:#666;">Deep Hunt Only</span>
                    </div>
                </div>
            </div>
        </div>

        <div class="card" style="grid-column: span 2;">
            <h2>Citation Matches by Bing Page (The "Page 2 Slump")</h2>
            <table>
                <thead>
                    <tr>
                        <th style="width:60px;">Page</th>
                        <th style="width:100px;">Matches</th>
                        <th>Distribution</th>
                    </tr>
                </thead>
                <tbody>
                    {% set max_matches = page_data|map(attribute='match_count')|max %}
                    {% for p in page_data %}
                    <tr>
                        <td><b>Pg {{ p.page_num|int }}</b></td>
                        <td>{{ p.match_count }}</td>
                        <td>
                            <div class="bar-container">
                                <div class="bar {{ 'slump' if p.page_num == 2 else '' }}" style="width: {{ (p.match_count / max_matches * 100) }}%"></div>
                            </div>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            <p style="font-size:12px; color:#666; margin-top:15px;">
                * Note how Page 2 (red) drops significantly compared to Page 1, while Page 3 and 4 often recover.
            </p>
        </div>

        <div class="card">
            <h2>Top "Invisible" Domains</h2>
            <p style="font-size:12px; color:#666;">Citations never found in Top 150</p>
            <div style="max-height: 500px; overflow-y: auto;">
                <table>
                    <thead>
                        <tr>
                            <th>Domain</th>
                            <th>Count</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for d in invisible_domains %}
                        <tr>
                            <td>{{ d.citation_domain }}</td>
                            <td>{{ d.count }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>
"""

PROMPT_LIST_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Prompt Analysis List</title>
    <style>
        body { font-family: -apple-system, sans-serif; background: #f4f4f9; padding: 40px; }
        .nav { margin-bottom: 30px; }
        .nav a { text-decoration: none; color: #10a37f; font-weight: bold; margin-right: 20px; }
        .card { background: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
        table { width: 100%; border-collapse: collapse; }
        th, td { text-align: left; padding: 12px; border-bottom: 1px solid #eee; }
        tr:hover { background: #f9fafb; }
        .stability-high { color: #059669; font-weight: bold; }
        .stability-low { color: #dc2626; font-weight: bold; }
    </style>
</head>
<body>
    <div class="nav">
        <a href="/">← Back to Consistency Viewer</a>
    </div>
    <h1>Prompt Analysis</h1>
    <div class="card">
        <table>
            <thead>
                <tr>
                    <th>Prompt ID</th>
                    <th>Total Unique Citations</th>
                    <th>Stability (3+ Runs)</th>
                    <th>Stability %</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                {% for p in prompts %}
                <tr>
                    <td><b>{{ p.prompt_id }}</b></td>
                    <td>{{ p.unique_citations }}</td>
                    <td>{{ p.stable_citations_3plus }}</td>
                    <td class="{{ 'stability-high' if p.stability_pct > 50 else ('stability-low' if p.stability_pct < 25 else '') }}">
                        {{ "%.1f"|format(p.stability_pct) }}%
                    </td>
                    <td><a href="/prompt/{{ p.prompt_id }}" style="color:#3b82f6; font-weight:bold;">Analyze Drift →</a></td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</body>
</html>
"""

PROMPT_DETAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Prompt Detail: {{ prompt_id }}</title>
    <style>
        body { font-family: -apple-system, sans-serif; background: #f4f4f9; padding: 40px; }
        .nav { margin-bottom: 30px; }
        .nav a { text-decoration: none; color: #10a37f; font-weight: bold; margin-right: 20px; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .card { background: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); margin-bottom: 20px; }
        h2 { margin-top: 0; color: #333; font-size: 18px; border-bottom: 2px solid #f0f0f0; padding-bottom: 10px; }
        .query-box { background: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #3b82f6; margin-bottom: 10px; }
        .run-label { font-size: 11px; font-weight: bold; color: #666; text-transform: uppercase; }
        .url-list { font-size: 13px; }
        .url-item { padding: 4px 0; border-bottom: 1px solid #f0f0f0; display: flex; justify-content: space-between; }
        .stable-badge { background: #d1fae5; color: #065f46; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; }
        .oneoff-badge { background: #f3f4f6; color: #6b7280; padding: 2px 6px; border-radius: 4px; font-size: 10px; }
        .invisible-badge { background: #fee2e2; color: #b91c1c; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; }
    </style>
</head>
<body>
    <div class="nav">
        <a href="/prompts">← Back to Prompt List</a>
    </div>
    <h1>Analysis for {{ prompt_id }}</h1>
    
    <div class="card">
        <h2>Rewritten Query Drift</h2>
        {% for run in runs %}
        <div class="query-box">
            <div class="run-label">{{ run.run_id }}</div>
            <div style="font-size: 15px; margin-top: 5px;">{{ run.rewritten_query or 'NO REWRITTEN QUERY' }}</div>
        </div>
        {% endfor %}
    </div>

    <div class="card">
        <h2>Citation Stability & Visibility</h2>
        <div class="url-list">
            <div class="url-item" style="font-weight:bold; background:#f9fafb; padding:8px;">
                <span>URL</span>
                <span>Status</span>
            </div>
            {% for c in citations %}
            <div class="url-item">
                <span style="max-width: 70%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                    <a href="{{ c.url }}" target="_blank">{{ c.url }}</a>
                </span>
                <div style="display:flex; gap:5px;">
                    {% if c.run_count >= 3 %}
                        <span class="stable-badge">STABLE ({{ c.run_count }} Runs)</span>
                    {% else %}
                        <span class="oneoff-badge">{{ c.run_count }} Runs</span>
                    {% endif %}
                    
                    {% if c.in_bing == 0 %}
                        <span class="invisible-badge">INVISIBLE</span>
                    {% endif %}
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
"""

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
        .domain-match-row { background: #f0fdf4 !important; }
        .duplicate-rank { color: #ef4444; font-weight: bold; font-size: 10px; margin-top: 2px; }
        .citation-type-badge { font-size: 10px; padding: 2px 6px; border-radius: 4px; text-transform: uppercase; font-weight: bold; margin-right: 6px; display: inline-block; }
        .citation-type-badge.cited { background: #d1fae5; color: #065f46; border: 1px solid #a7f3d0; }
        .citation-type-badge.inline { background: #dbeafe; color: #1e40af; border: 1px solid #bfdbfe; }
        .citation-type-badge.additional { background: #f3f4f6; color: #4b5563; border: 1px solid #e5e7eb; }
        a { color: #10a37f; text-decoration: none; }
        
        .raw-text-box { 
            white-space: pre-wrap; font-family: monospace; font-size: 12px; color: #555; background: #f8f9fa; padding: 15px; border-radius: 5px; border: 1px solid #eee; max-height: 300px; overflow-y: auto; margin-top: 20px;
        }
    </style>
</head>
<body>
    <div id="sidebar">
        <div style="margin-bottom: 20px; padding: 10px; background: #10a37f; border-radius: 5px; text-align: center;">
            <a href="/dashboard" style="text-decoration:none; color:white; font-weight:bold;">📊 VIEW DASHBOARD</a>
        </div>
        <div style="margin-bottom: 20px; padding: 10px; background: #3b82f6; border-radius: 5px; text-align: center;">
            <a href="/prompts" style="text-decoration:none; color:white; font-weight:bold;">🔍 PROMPT ANALYSIS</a>
        </div>
        <h3>Runs</h3>
        {% for rid in run_ids %}
        <a href="/?run_id={{ rid }}&mode={{ mode }}" style="text-decoration:none; color:inherit;" onclick="sessionStorage.setItem('sidebarScroll', document.getElementById('sidebar').scrollTop);">
            <div id="item-{{ rid }}" class="prompt-item {{ 'active' if rid == active_run_id else '' }}">
                {{ rid }}
            </div>
        </a>
        {% endfor %}
    </div>
    
    <script>
        // Restore sidebar scroll position
        window.onload = function() {
            var scrollPos = sessionStorage.getItem('sidebarScroll');
            if (scrollPos) {
                document.getElementById('sidebar').scrollTop = scrollPos;
            }
            // Also scroll the active item into view
            var activeItem = document.querySelector('.prompt-item.active');
            if (activeItem) {
                activeItem.scrollIntoView({ block: 'nearest' });
            }
        };
    </script>
    
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
                <a href="/?run_id={{ active_run_id }}&mode=combined" class="mode-btn {{ 'active' if mode == 'combined' else '' }}">Combined (All)</a>
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
                        {% endif %}
                        
                        <div class="source-label" style="margin-top: 20px;">Full Response Text</div>
                        <div class="raw-text-box">{{ run_raw.response_text }}</div>
                    </div>
                </div>

                <div style="padding-left: 10px;">
                    <span class="source-label">Citations In Excel ({{ cit_db|length }} found)</span>
                    <div class="excel-citation-list">
                        {% for c in cit_db %}
                        <div style="margin-bottom: 8px; border-bottom: 1px dashed #eee; padding-bottom: 4px;">
                            <div style="font-weight:bold; color:#333;">
                                <span class="citation-type-badge {{ c.citation_type }}">{{ c.citation_type }}</span>
                                {{ c.item_entity_name or c.item_name or 'N/A' }}
                                {% set found_rank = [] %}
                                {% set is_exact = [] %}
                                {% for b in bing %}
                                    {% if b.url == c.url %}
                                        {% do found_rank.append(b.result_rank or b.absolute_rank) %}
                                        {% do is_exact.append(True) %}
                                    {% elif b.result_domain == c.citation_domain %}
                                        {% do found_rank.append(b.result_rank or b.absolute_rank) %}
                                        {% do is_exact.append(False) %}
                                    {% endif %}
                                {% endfor %}
                                {% if found_rank %}
                                    {% if is_exact[0] %}
                                        <a href="#rank-{{ found_rank[0] }}" style="margin-left:10px; background:#fff9c4; color:#d97706; padding:1px 6px; border-radius:4px; font-size:10px; border:1px solid #d97706;">RANK {{ found_rank[0] }} (EXACT)</a>
                                    {% else %}
                                        <a href="#rank-{{ found_rank[0] }}" style="margin-left:10px; background:#f0fdf4; color:#166534; padding:1px 6px; border-radius:4px; font-size:10px; border:1px solid #166534;">RANK {{ found_rank[0] }} (DOMAIN)</a>
                                    {% endif %}
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
                    {% set displayed_ranks = [] %}
                    {% for b in bing %}
                    <tr id="rank-{{ b.result_rank or b.absolute_rank }}" class="{{ 'match-row' if b.is_cited else ('domain-match-row' if b.is_domain_match else '') }}">
                        <td>
                            <span class="rank-badge">{{ b.result_rank or b.absolute_rank }}</span>
                            {% if (b.result_rank or b.absolute_rank) in displayed_ranks %}
                                <div class="duplicate-rank">DUPLICATE</div>
                            {% endif %}
                            {% do displayed_ranks.append(b.result_rank or b.absolute_rank) %}
                            <div style="font-size: 9px; color: #888; margin-top: 2px;">Pg {{ b.page_num or ((((b.absolute_rank|int) - 1) // 10) + 1) }}</div>
                        </td>
                        <td>
                            <div style="font-weight:bold;"><a href="{{ b.url }}" target="_blank">{{ b.result_title or b.title or b.url }}</a></div>
                            <div style="font-size:11px; color:#666;">{{ b.url }}</div>
                        </td>
                        <td>
                            <span style="font-weight:500;">{{ b.result_domain }}</span>
                            {% if b.is_cited %}<br><b style="color:#d97706; font-size:10px;">[EXACT MATCH]</b>
                            {% elif b.is_domain_match %}<br><b style="color:#166534; font-size:10px;">[DOMAIN MATCH]</b>{% endif %}
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
        platforms_list = ['apple.com', 'google.com', 'microsoft.com', 'chrome.google.com', 'play.google.com', 'apps.apple.com', 'amazon.com']
        platforms = "('apple.com', 'google.com', 'microsoft.com', 'chrome.google.com', 'play.google.com', 'apps.apple.com', 'amazon.com')"
        # Normalize run_id for lookup
        df_raw['temp_run_id'] = df_raw.index.astype(str)
        
        # Check both the generated index and the prompt_id/run_number combo
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
            # Try matching by building the ID if index lookup failed
            df_raw['temp_id'] = df_raw['prompt_id'].astype(str) + '_r' + df_raw['run_number'].astype(str)
            if run_id in df_raw['temp_id'].values:
                row_raw = df_raw[df_raw['temp_id'] == run_id].iloc[0]
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
                # FALLBACK: If not in CSV, try to get from the database 'runs' table joined with prompts
                # Note: DB uses 'rewritten_query' instead of 'generated_search_query' and 'prompt_text' in prompts table
                db_run = db.execute('''
                    SELECT p.prompt_text as query, r.rewritten_query as generated_search_query, r.response_text, r.items_json 
                    FROM runs r
                    LEFT JOIN prompts_updated p ON r.prompt_id = p.prompt_id
                    WHERE r.run_id = ?
                ''', (run_id,)).fetchone()
                
                if db_run:
                    run_raw = {
                        'query': db_run['query'] or 'N/A',
                        'generated_search_query': db_run['generated_search_query'] or 'N/A',
                        'response_text': db_run['response_text'] or ''
                    }
                    try:
                        items_raw = json.loads(db_run['items_json'] or '[]')
                    except:
                        items_raw = []
                else:
                    run_raw = {'query': 'N/A', 'generated_search_query': 'N/A', 'response_text': f'Run {run_id} not found in CSV or DB'}
                    items_raw = []

        cit_db = db.execute('SELECT * FROM citations WHERE run_id = ?', (run_id,)).fetchall()
        
        if mode == 'deep':
            # Query the new bing_deep_hunt table
            bing_results = db.execute(f'''
                SELECT *, 
                EXISTS(SELECT 1 FROM citations c WHERE c.run_id = b.run_id AND c.url = b.url) as is_cited,
                (
                    b.result_domain NOT IN {platforms}
                    AND EXISTS(SELECT 1 FROM citations c WHERE c.run_id = b.run_id AND c.citation_domain = b.result_domain AND c.url != b.url)
                ) as is_domain_match,
                (absolute_rank > 30) as is_deep_match
                FROM bing_deep_hunt b 
                WHERE run_id = ? 
                ORDER BY absolute_rank ASC
            ''', (run_id,)).fetchall()
        elif mode == 'combined':
            # Factor in BOTH Standard (Top 30) and Deep Hunt (Top 150)
            bing_results = db.execute(f'''
                WITH Combined AS (
                    SELECT url, result_rank as absolute_rank, 1 as page_num, result_domain, result_title as title, run_id
                    FROM bing_results 
                    WHERE run_id = ?
                    UNION ALL
                    SELECT url, absolute_rank, page_num, result_domain, url as title, run_id
                    FROM bing_deep_hunt 
                    WHERE run_id = ?
                ),
                Ranked AS (
                    SELECT *, 
                    ROW_NUMBER() OVER (PARTITION BY url ORDER BY absolute_rank ASC) as rn
                    FROM Combined
                )
                SELECT *,
                EXISTS(SELECT 1 FROM citations c WHERE c.run_id = r.run_id AND c.url = r.url) as is_cited,
                (
                    r.result_domain NOT IN {platforms}
                    AND EXISTS(SELECT 1 FROM citations c WHERE c.run_id = r.run_id AND c.citation_domain = r.result_domain AND c.url != r.url)
                ) as is_domain_match,
                (absolute_rank > 30) as is_deep_match
                FROM Ranked r
                WHERE rn = 1
                ORDER BY absolute_rank ASC
            ''', (run_id, run_id)).fetchall()
        else:
            # Standard Top 30
            bing_results = db.execute(f'''
                SELECT *, 
                EXISTS(SELECT 1 FROM citations c WHERE c.run_id = b.run_id AND c.url = b.url) as is_cited,
                (
                    b.result_domain NOT IN {platforms}
                    AND EXISTS(SELECT 1 FROM citations c WHERE c.run_id = b.run_id AND c.citation_domain = b.result_domain AND c.url != b.url)
                ) as is_domain_match,
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

@app.route('/dashboard')
def dashboard():
    db = get_db()
    
    # 1. Page-based distribution
    page_data = db.execute('''
        SELECT b.page_num, COUNT(DISTINCT c.rowid) as match_count
        FROM bing_deep_hunt b
        JOIN citations c ON b.run_id = c.run_id 
          AND (b.url = c.url OR b.result_domain = c.norm_domain)
        GROUP BY b.page_num
        ORDER BY b.page_num
    ''').fetchall()
    
    # 2. Coverage Stats
    platforms = "('apple.com', 'google.com', 'microsoft.com', 'chrome.google.com', 'play.google.com', 'apps.apple.com', 'amazon.com')"
    
    match_sql_strict = "(EXISTS (SELECT 1 FROM bing_results b WHERE b.run_id = c.run_id AND b.url = c.url) OR EXISTS (SELECT 1 FROM bing_deep_hunt d WHERE d.run_id = c.run_id AND d.url = c.url))"
    
    # Domain match SQL: Allow domain matching ONLY if the domain is NOT a platform domain
    match_sql_domain = f"""(
        {match_sql_strict} 
        OR 
        (
            c.norm_domain NOT IN {platforms}
            AND (
                EXISTS (SELECT 1 FROM bing_results b WHERE b.run_id = c.run_id AND b.result_domain = c.norm_domain)
                OR 
                EXISTS (SELECT 1 FROM bing_deep_hunt d WHERE d.run_id = c.run_id AND d.result_domain = c.norm_domain)
            )
        )
    )"""

    # All Citations
    total_all = db.execute('SELECT COUNT(*) FROM citations').fetchone()[0]
    matched_all_strict = db.execute(f'SELECT COUNT(DISTINCT c.rowid) FROM citations c WHERE {match_sql_strict}').fetchone()[0]
    matched_all_domain = db.execute(f'SELECT COUNT(DISTINCT c.rowid) FROM citations c WHERE {match_sql_domain}').fetchone()[0]

    # Main Citations (Cited + Inline)
    total_main = db.execute("SELECT COUNT(*) FROM citations WHERE citation_type != 'additional'").fetchone()[0]
    matched_main_strict = db.execute(f"SELECT COUNT(DISTINCT c.rowid) FROM citations c WHERE citation_type != 'additional' AND {match_sql_strict}").fetchone()[0]
    matched_main_domain = db.execute(f"SELECT COUNT(DISTINCT c.rowid) FROM citations c WHERE citation_type != 'additional' AND {match_sql_domain}").fetchone()[0]

    # Additional Citations
    total_add = db.execute("SELECT COUNT(*) FROM citations WHERE citation_type = 'additional'").fetchone()[0]
    matched_add_strict = db.execute(f"SELECT COUNT(DISTINCT c.rowid) FROM citations c WHERE citation_type = 'additional' AND {match_sql_strict}").fetchone()[0]
    matched_add_domain = db.execute(f"SELECT COUNT(DISTINCT c.rowid) FROM citations c WHERE citation_type = 'additional' AND {match_sql_domain}").fetchone()[0]

    # Legacy Stats for Comparison
    matched_top30 = db.execute(f'''
        SELECT COUNT(DISTINCT c.rowid)
        FROM citations c
        WHERE (EXISTS (SELECT 1 FROM bing_results b WHERE b.run_id = c.run_id AND b.url = c.url))
        OR (
            c.norm_domain NOT IN {platforms}
            AND EXISTS (SELECT 1 FROM bing_results b WHERE b.run_id = c.run_id AND b.result_domain = c.norm_domain)
        )
    ''').fetchone()[0]
    
    matched_deep = db.execute(f'''
        SELECT COUNT(DISTINCT c.rowid)
        FROM citations c
        WHERE (EXISTS (SELECT 1 FROM bing_deep_hunt b WHERE b.run_id = c.run_id AND b.url = c.url))
        OR (
            c.norm_domain NOT IN {platforms}
            AND EXISTS (SELECT 1 FROM bing_deep_hunt b WHERE b.run_id = c.run_id AND b.result_domain = c.norm_domain)
        )
    ''').fetchone()[0]

    # 3. Top Invisible Domains
    invisible_domains = db.execute(f'''
        SELECT norm_domain as citation_domain, COUNT(*) as count
        FROM citations c
        WHERE NOT (
            (EXISTS (SELECT 1 FROM bing_deep_hunt b WHERE b.run_id = c.run_id AND b.url = c.url))
            OR (
                c.norm_domain NOT IN {platforms}
                AND EXISTS (SELECT 1 FROM bing_deep_hunt b WHERE b.run_id = c.run_id AND b.result_domain = c.norm_domain)
            )
        )
        GROUP BY norm_domain
        ORDER BY count DESC
        LIMIT 100
    ''').fetchall()

    return render_template_string(DASHBOARD_TEMPLATE, 
                                 page_data=page_data,
                                 total_all=total_all,
                                 matched_all_strict=matched_all_strict,
                                 matched_all_domain=matched_all_domain,
                                 total_main=total_main,
                                 matched_main_strict=matched_main_strict,
                                 matched_main_domain=matched_main_domain,
                                 total_add=total_add,
                                 matched_add_strict=matched_add_strict,
                                 matched_add_domain=matched_add_domain,
                                 matched_top30=matched_top30,
                                 matched_deep=matched_deep,
                                 invisible_domains=invisible_domains)

@app.route('/prompts')
def prompts_list():
    # Load the consistency report we just generated
    report_path = 'data/metrics/cross_run_consistency_report.csv'
    if not os.path.exists(report_path):
        return "Consistency report not found. Please run scripts/metrics/analyze_cross_run_consistency.py first."
    
    df = pd.read_csv(report_path)
    prompts = df.to_dict('records')
    return render_template_string(PROMPT_LIST_TEMPLATE, prompts=prompts)

@app.route('/prompt/<prompt_id>')
def prompt_detail(prompt_id):
    db = get_db()
    
    # 1. Get rewritten queries for all runs of this prompt
    runs = db.execute('''
        SELECT run_id, rewritten_query 
        FROM runs 
        WHERE prompt_id = ? 
        ORDER BY run_id
    ''', (prompt_id,)).fetchall()
    
    # 2. Get citation stability and visibility for this prompt
    citations = db.execute('''
        SELECT c.url, 
               COUNT(DISTINCT c.run_id) as run_count,
               (SELECT COUNT(*) FROM bing_results b WHERE b.run_id = r.run_id AND b.url = c.url) as in_bing
        FROM citations c
        JOIN runs r ON c.run_id = r.run_id
        WHERE r.prompt_id = ?
        GROUP BY c.url
        ORDER BY run_count DESC, c.url ASC
    ''', (prompt_id,)).fetchall()
    
    return render_template_string(PROMPT_DETAIL_TEMPLATE, 
                                 prompt_id=prompt_id, 
                                 runs=runs, 
                                 citations=citations)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
