import sqlite3
import pandas as pd
from flask import Flask, render_template_string, request
import json
import os

DOMAIN_EXPLORER_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Domain Explorer - GEO Research</title>
    <style>
        body { font-family: -apple-system, sans-serif; background: #f4f4f9; margin: 0; padding: 20px; }
        .nav { margin-bottom: 20px; }
        .nav a { text-decoration: none; color: #10a37f; font-weight: bold; margin-right: 20px; }
        .filters { background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); display: flex; gap: 15px; align-items: center; flex-wrap: wrap; }
        .filters label { font-weight: bold; font-size: 13px; color: #555; }
        .filters select, .filters input { padding: 8px 12px; border: 1px solid #ddd; border-radius: 5px; font-size: 13px; }
        .filters input[type=text] { width: 200px; }
        .filters button { background: #10a37f; color: white; border: none; padding: 8px 16px; border-radius: 5px; cursor: pointer; font-weight: bold; }
        .filters button:hover { background: #0d8a6a; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
        h2 { margin-top: 0; color: #333; font-size: 16px; border-bottom: 2px solid #f0f0f0; padding-bottom: 10px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { text-align: left; padding: 8px; border-bottom: 1px solid #eee; font-size: 12px; }
        th { background: #f8f8f8; font-weight: bold; }
        .domain-link { color: #10a37f; text-decoration: none; font-weight: 500; }
        .domain-link:hover { text-decoration: underline; }
        .tag { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: bold; margin-left: 5px; }
        .tag-cited { background: #dcfce7; color: #166534; }
        .tag-additional { background: #fef3c7; color: #92400e; }
        .tag-enterprise { background: #dbeafe; color: #1e40af; }
        .tag-personal { background: #fef9c3; color: #854d0e; }
        .tag-invisible { background: #fee2e2; color: #991b1b; }
        .tag-visible { background: #d1fae5; color: #065f46; }
        .tag-google-only { background: #fef3c7; color: #92400e; font-weight: bold; }
        .tag-bing-only { background: #dbeafe; color: #1e40af; }
        .tag-both { background: #d1fae5; color: #065f46; }
        .tag-neither { background: #fee2e2; color: #991b1b; }
        .drilldown { margin-top: 20px; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
        .url-cell { max-width: 350px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .url-cell a { color: #0369a1; text-decoration: none; font-size: 11px; }
        .url-cell a:hover { text-decoration: underline; }
        .prompt-link { color: #6366f1; text-decoration: none; font-weight: 500; }
        .prompt-link:hover { text-decoration: underline; }
        .stats-row { display: flex; gap: 30px; margin-bottom: 20px; }
        .stat-box { background: #f8f9fa; padding: 15px 20px; border-radius: 8px; text-align: center; }
        .stat-num { font-size: 28px; font-weight: bold; color: #10a37f; }
        .stat-label { font-size: 12px; color: #666; }
    </style>
</head>
<body>
    <div class="nav">
        <a href="/">← Run Viewer</a>
        <a href="/dashboard">📊 Dashboard</a>
        <a href="/domains" style="color: #6366f1;">🔍 Domain Explorer</a>
        <a href="/invisible" style="color: #ef4444;">🕳️ Truly Invisible</a>
    </div>
    <h1>🔍 Domain Explorer</h1>
    
    <div class="stats-row">
        <div class="stat-box">
            <div class="stat-num">{{ total_domains }}</div>
            <div class="stat-label">Unique Domains</div>
        </div>
        <div class="stat-box">
            <div class="stat-num">{{ total_citations }}</div>
            <div class="stat-label">Total Citations</div>
        </div>
        <div class="stat-box" style="background: #fef3c7;">
            <div class="stat-num" style="color: #92400e;">{{ google_only_count }}</div>
            <div class="stat-label">Google-Only URLs</div>
        </div>
        <div class="stat-box" style="background: #dbeafe;">
            <div class="stat-num" style="color: #1e40af;">{{ bing_only_count }}</div>
            <div class="stat-label">Bing-Only URLs</div>
        </div>
        <div class="stat-box" style="background: #fee2e2;">
            <div class="stat-num" style="color: #991b1b;">{{ neither_count }}</div>
            <div class="stat-label">Truly Invisible</div>
        </div>
    </div>
    
    <form class="filters" method="GET" action="/domains">
        <label>Search Domain:</label>
        <input type="text" name="search" placeholder="e.g. reddit, arxiv..." value="{{ search_query }}">
        
        <label>Account:</label>
        <select name="account">
            <option value="all" {{ 'selected' if account_filter == 'all' else '' }}>All</option>
            <option value="enterprise" {{ 'selected' if account_filter == 'enterprise' else '' }}>Enterprise</option>
            <option value="personal" {{ 'selected' if account_filter == 'personal' else '' }}>Personal</option>
        </select>
        
        <label>Type:</label>
        <select name="type">
            <option value="all" {{ 'selected' if type_filter == 'all' else '' }}>All</option>
            <option value="cited" {{ 'selected' if type_filter == 'cited' else '' }}>Cited Only</option>
            <option value="additional" {{ 'selected' if type_filter == 'additional' else '' }}>Additional Only</option>
        </select>
        
        <label>Visibility:</label>
        <select name="visibility">
            <option value="all" {{ 'selected' if visibility_filter == 'all' else '' }}>All</option>
            <option value="invisible" {{ 'selected' if visibility_filter == 'invisible' else '' }}>Invisible (Not in Bing)</option>
            <option value="visible" {{ 'selected' if visibility_filter == 'visible' else '' }}>Visible (In Bing)</option>
        </select>
        
        <label>Source:</label>
        <select name="source">
            <option value="all" {{ 'selected' if source_filter == 'all' else '' }}>All Sources</option>
            <option value="google_only" {{ 'selected' if source_filter == 'google_only' else '' }}>Google Only (Not in Bing)</option>
            <option value="bing_only" {{ 'selected' if source_filter == 'bing_only' else '' }}>Bing Only (Not in Google)</option>
            <option value="both" {{ 'selected' if source_filter == 'both' else '' }}>Both Bing & Google</option>
            <option value="neither" {{ 'selected' if source_filter == 'neither' else '' }}>Neither (Truly Invisible)</option>
        </select>
        
        <button type="submit">Search</button>
    </form>
    
    <div class="card">
        <h2>Domain Results ({{ domains|length }} shown)</h2>
        <table>
            <tr>
                <th>Domain</th>
                <th>Source</th>
                <th>Ent. Cited</th>
                <th>Ent. Add.</th>
                <th>Pers. Cited</th>
                <th>Pers. Add.</th>
                <th>Total</th>
                <th>Actions</th>
            </tr>
            {% for d in domains %}
            <tr>
                <td><strong>{{ d.domain }}</strong></td>
                <td>
                    {% if d.in_google and d.in_bing %}
                    <span class="tag tag-both">Bing+Google</span>
                    {% elif d.in_google and not d.in_bing %}
                    <span class="tag tag-google-only">GOOGLE ONLY</span>
                    {% elif d.in_bing and not d.in_google %}
                    <span class="tag tag-bing-only">Bing Only</span>
                    {% else %}
                    <span class="tag tag-neither">Neither</span>
                    {% endif %}
                </td>
                <td>{{ d.ent_cited }}</td>
                <td>{{ d.ent_additional }}</td>
                <td>{{ d.pers_cited }}</td>
                <td>{{ d.pers_additional }}</td>
                <td><strong>{{ d.total }}</strong></td>
                <td><a class="domain-link" href="/domains?search={{ d.domain }}&drilldown=1">View URLs</a></td>
            </tr>
            {% endfor %}
        </table>
    </div>
    
    {% if drilldown_domain %}
    <div class="drilldown">
        <h2>URLs for: <strong>{{ drilldown_domain }}</strong> ({{ drilldown_urls|length }} results)</h2>
        <table>
            <tr>
                <th>Prompt</th>
                <th>Run</th>
                <th>Account</th>
                <th>Type</th>
                <th>Source</th>
                <th>URL</th>
                <th>Title</th>
            </tr>
            {% for u in drilldown_urls %}
            <tr>
                <td><a class="prompt-link" href="/?run_id={{ u.run_id }}&account={{ u.account_type }}">{{ u.prompt_id }}</a></td>
                <td>{{ u.run_number }}</td>
                <td><span class="tag tag-{{ u.account_type }}">{{ u.account_type }}</span></td>
                <td><span class="tag tag-{{ u.citation_type }}">{{ u.citation_type }}</span></td>
                <td>
                    {% if u.in_google and u.in_bing %}
                    <span class="tag tag-both">Both</span>
                    {% elif u.in_google and not u.in_bing %}
                    <span class="tag tag-google-only">Google</span>
                    {% elif u.in_bing and not u.in_google %}
                    <span class="tag tag-bing-only">Bing</span>
                    {% else %}
                    <span class="tag tag-neither">None</span>
                    {% endif %}
                </td>
                <td class="url-cell"><a href="{{ u.url }}" target="_blank" title="{{ u.url }}">{{ u.url[:60] }}...</a></td>
                <td style="max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="{{ u.title }}">{{ u.title[:40] if u.title else '-' }}...</td>
            </tr>
            {% endfor %}
        </table>
    </div>
    {% endif %}
</body>
</html>
"""

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>GEO Research Dashboard</title>
    <style>
        body { font-family: -apple-system, sans-serif; background: #f4f4f9; margin: 0; padding: 40px; }
        .nav { margin-bottom: 30px; }
        .nav a { text-decoration: none; color: #10a37f; font-weight: bold; margin-right: 20px; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 30px; }
        .card { background: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
        .full-width { grid-column: 1 / -1; }
        h2 { margin-top: 0; color: #333; font-size: 18px; border-bottom: 2px solid #f0f0f0; padding-bottom: 10px; }
        .stat-big { font-size: 36px; font-weight: bold; }
        .stat-label { color: #666; font-size: 14px; }
        .stat-sub { font-size: 11px; color: #888; margin-top: 4px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { text-align: left; padding: 8px; border-bottom: 1px solid #eee; font-size: 13px; }
        .enterprise { border-left: 4px solid #3b82f6; }
        .personal { border-left: 4px solid #f59e0b; }
    </style>
</head>
<body>
    <div class="nav">
        <a href="/">← Back to Run Viewer</a>
        <a href="/domains" style="color: #6366f1;">🔍 Domain Explorer</a>
        <a href="/invisible" style="color: #ef4444;">🕳️ Truly Invisible</a>
    </div>
    <h1>GEO Research Dashboard</h1>
    
    <!-- Global Stats -->
    <div class="grid">
        <div class="card full-width" style="display: flex; justify-content: space-around; background: #1e293b; color: white;">
            <div style="text-align: center;">
                <div class="stat-label" style="color: #cbd5e1;">Total Citations</div>
                <div class="stat-big" style="color: #38bdf8;">{{ ent_total_main + pers_total_main }}</div>
                <div class="stat-sub">Explicitly attributed</div>
                </div>
            <div style="text-align: center;">
                <div class="stat-label" style="color: #cbd5e1;">Total Additional</div>
                <div class="stat-big" style="color: #fbbf24;">{{ ent_total_add + pers_total_add }}</div>
                <div class="stat-sub">Shortlisted but not cited</div>
            </div>
            <div style="text-align: center;">
                <div class="stat-label" style="color: #cbd5e1;">Total Rejected</div>
                <div class="stat-big" style="color: #fca5a5;">{{ total_rejected_global }}</div>
                <div class="stat-sub">In Bing but ignored</div>
            </div>
            <div style="text-align: center; border-left: 1px solid #475569; padding-left: 40px;">
                <div class="stat-label" style="color: #94a3b8; font-weight: bold;">TOTAL CONSIDERED</div>
                <div class="stat-big" style="color: #ffffff;">{{ ent_total_main + pers_total_main + ent_total_add + pers_total_add + total_rejected_global }}</div>
                <div class="stat-sub">Sum of all unique links</div>
            </div>
            <div style="text-align: center;">
                <div class="stat-label" style="color: #cbd5e1;">Unique Domains</div>
                <div class="stat-big" style="color: #34d399;">{{ total_unique_domains }}</div>
                <div class="stat-sub">Across all runs</div>
            </div>
            <div style="text-align: center;">
                <div class="stat-label" style="color: #cbd5e1;">Total Coverage (Cited)</div>
                <div class="stat-big" style="color: #0f766e;">{{ "%.1f"|format(all_combined_cited_pct) }}%</div>
                <div class="stat-sub">Bing ∪ Google (personal)</div>
            </div>
            <div style="text-align: center;">
                <div class="stat-label" style="color: #cbd5e1;">Missing (Cited)</div>
                <div class="stat-big" style="color: #fca5a5;">{{ "%.1f"|format(all_missing_cited_pct) }}%</div>
                <div class="stat-sub">Not in either</div>
            </div>
        </div>
                </div>

    <div class="grid">
        <!-- Enterprise Stats -->
        <div class="card enterprise">
            <h2 style="color: #3b82f6;">🏢 Enterprise Account</h2>
            <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:15px; margin-bottom: 15px;">
                <div style="background:#eff6ff; padding:15px; border-radius:8px; text-align:center;">
                    <div class="stat-label">Cited</div>
                    <div class="stat-big" style="color:#3b82f6;">{{ ent_total_main }}</div>
                </div>
                <div style="background:#fef3c7; padding:15px; border-radius:8px; text-align:center;">
                    <div class="stat-label">Additional</div>
                    <div class="stat-big" style="color:#d97706;">{{ ent_total_add }}</div>
                </div>
                <div style="background:#fee2e2; padding:15px; border-radius:8px; text-align:center;">
                    <div class="stat-label">Rejected</div>
                    <div class="stat-big" style="color:#991b1b;">{{ ent_total_rejected }}</div>
                </div>
            </div>
            <div style="background: #f8fafc; padding: 10px; border-radius: 8px; text-align: center; margin-bottom: 15px; border: 1px dashed #cbd5e1;">
                <div class="stat-label" style="font-weight: bold; color: #475569;">TOTAL CONSIDERED: {{ ent_total_main + ent_total_add + ent_total_rejected }}</div>
            </div>
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:15px; margin-bottom: 15px;">
                <div style="background:#eef2ff; padding:12px; border-radius:8px; text-align:center;">
                    <div class="stat-label">Bing Cited Overlap</div>
                    <div class="stat-big" style="color:#4338ca;">{{ "%.1f"|format(ent_bing_overlap_pct) }}%</div>
                </div>
                <div style="background:#fef3c7; padding:12px; border-radius:8px; text-align:center;">
                    <div class="stat-label">Bing Add. Overlap</div>
                    <div class="stat-big" style="color:#d97706;">{{ "%.1f"|format(ent_bing_add_overlap_pct) }}%</div>
                </div>
            </div>
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:15px; margin-bottom: 15px;">
                <div style="background:#fff7ed; padding:12px; border-radius:8px; text-align:center;">
                    <div class="stat-label">Google Cited Overlap (control)</div>
                    <div class="stat-big" style="color:#92400e;">{{ "%.1f"|format(ent_google_overlap_pct) }}%</div>
                </div>
                <div style="background:#fffaf0; padding:12px; border-radius:8px; text-align:center;">
                    <div class="stat-label">Google Add. Overlap (control)</div>
                    <div class="stat-big" style="color:#c2410c;">{{ "%.1f"|format(ent_google_add_overlap_pct) }}%</div>
                </div>
            </div>
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:15px; margin-bottom: 15px;">
                <div style="background:#f0f9ff; padding:12px; border-radius:8px; text-align:center;">
                    <div class="stat-label">Q1 Overlap</div>
                    <div class="stat-big" style="color:#0369a1;">{{ "%.1f"|format(ent_q1_overlap_pct) }}%</div>
                </div>
                <div style="background:#f0fdf4; padding:12px; border-radius:8px; text-align:center;">
                    <div class="stat-label">Q2 Overlap</div>
                    <div class="stat-big" style="color:#166534;">{{ "%.1f"|format(ent_q2_overlap_pct) }}%</div>
                </div>
            </div>
            <div style="font-size: 12px; color: #666;">
                <strong>Runs:</strong> {{ ent_runs }} | <strong>Bing Results:</strong> {{ ent_bing }}
                </div>
            </div>
            
        <!-- Personal Stats -->
        <div class="card personal">
            <h2 style="color: #f59e0b;">👤 Personal Account</h2>
            <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:15px; margin-bottom: 15px;">
                <div style="background:#fffbeb; padding:15px; border-radius:8px; text-align:center;">
                    <div class="stat-label">Cited</div>
                    <div class="stat-big" style="color:#f59e0b;">{{ pers_total_main }}</div>
                    </div>
                <div style="background:#fff7ed; padding:15px; border-radius:8px; text-align:center;">
                    <div class="stat-label">Additional</div>
                    <div class="stat-big" style="color:#c2410c;">{{ pers_total_add }}</div>
                    </div>
                <div style="background:#fef2f2; padding:15px; border-radius:8px; text-align:center;">
                    <div class="stat-label">Rejected</div>
                    <div class="stat-big" style="color:#b91c1c;">{{ pers_total_rejected }}</div>
                </div>
            </div>
            <div style="background: #fffaf5; padding: 10px; border-radius: 8px; text-align: center; margin-bottom: 15px; border: 1px dashed #fed7aa;">
                <div class="stat-label" style="font-weight: bold; color: #9a3412;">TOTAL CONSIDERED: {{ pers_total_main + pers_total_add + pers_total_rejected }}</div>
            </div>
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:15px; margin-bottom: 15px;">
                <div style="background:#fff7ed; padding:12px; border-radius:8px; text-align:center;">
                    <div class="stat-label">Bing Cited Overlap</div>
                    <div class="stat-big" style="color:#c2410c;">{{ "%.1f"|format(pers_bing_overlap_pct) }}%</div>
                </div>
                <div style="background:#fffbeb; padding:12px; border-radius:8px; text-align:center;">
                    <div class="stat-label">Bing Add. Overlap</div>
                    <div class="stat-big" style="color:#f59e0b;">{{ "%.1f"|format(pers_bing_add_overlap_pct) }}%</div>
                </div>
            </div>
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:15px; margin-bottom: 15px;">
                <div style="background:#fef3c7; padding:12px; border-radius:8px; text-align:center;">
                    <div class="stat-label">Google Cited Overlap</div>
                    <div class="stat-big" style="color:#92400e;">{{ "%.1f"|format(pers_google_overlap_pct) }}%</div>
                </div>
                <div style="background:#fff7ed; padding:12px; border-radius:8px; text-align:center;">
                    <div class="stat-label">Google Add. Overlap</div>
                    <div class="stat-big" style="color:#c2410c;">{{ "%.1f"|format(pers_google_add_overlap_pct) }}%</div>
                </div>
            </div>
            <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:15px; margin-bottom: 15px;">
                <div style="background:#fffaf0; padding:12px; border-radius:8px; text-align:center;">
                    <div class="stat-label">Total Coverage (Bing+Google)</div>
                    <div class="stat-big" style="color:#0f766e;">{{ "%.1f"|format(pers_combined_overlap_pct) }}%</div>
                </div>
                <div style="background:#fffbeb; padding:12px; border-radius:8px; text-align:center;">
                    <div class="stat-label">Google-only Coverage</div>
                    <div class="stat-big" style="color:#f97316;">{{ "%.1f"|format(pers_google_only_overlap_pct) }}%</div>
                </div>
                <div style="background:#fef2f2; padding:12px; border-radius:8px; text-align:center;">
                    <div class="stat-label">Missing (not in either)</div>
                    <div class="stat-big" style="color:#b91c1c;">{{ "%.1f"|format(pers_missing_overlap_pct) }}%</div>
                </div>
            </div>
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:15px; margin-bottom: 15px;">
                <div style="background:#fff7ed; padding:12px; border-radius:8px; text-align:center;">
                    <div class="stat-label">Q1 Overlap</div>
                    <div class="stat-big" style="color:#c2410c;">{{ "%.1f"|format(pers_q1_overlap_pct) }}%</div>
                </div>
                <div style="background:#f0fdf4; padding:12px; border-radius:8px; text-align:center;">
                    <div class="stat-label">Q2 Overlap</div>
                    <div class="stat-big" style="color:#166534;">{{ "%.1f"|format(pers_q2_overlap_pct) }}%</div>
                </div>
            </div>
            <div style="font-size: 12px; color: #666;">
                <strong>Runs:</strong> {{ pers_runs }} | <strong>Bing Results:</strong> {{ pers_bing }}
                </div>
            </div>
        </div>

    <div class="grid">
        <div class="card enterprise">
            <h2>Enterprise - Top Invisible Domains</h2>
            <table>
                <tr><th>Domain</th><th>Count</th></tr>
                {% for row in ent_invisible[:10] %}
                <tr><td>{{ row[0] }}</td><td>{{ row[1] }}</td></tr>
                {% endfor %}
            </table>
                            </div>
        
        <div class="card personal">
            <h2>Personal - Top Invisible Domains</h2>
            <table>
                <tr><th>Domain</th><th>Count</th></tr>
                {% for row in pers_invisible[:10] %}
                <tr><td>{{ row[0] }}</td><td>{{ row[1] }}</td></tr>
                    {% endfor %}
            </table>
        </div>
        </div>

    <div class="grid">
        <div class="card enterprise">
            <h2>Enterprise - Page Distribution</h2>
                <table>
                <tr><th>Page</th><th>Matches</th></tr>
                {% for row in ent_page_data %}
                <tr><td>Page {{ row[0] }}</td><td>{{ row[1] }}</td></tr>
                        {% endfor %}
                </table>
            </div>
        
        <div class="card personal">
            <h2>Personal - Page Distribution</h2>
            <table>
                <tr><th>Page</th><th>Matches</th></tr>
                {% for row in pers_page_data %}
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
        
        <!-- Account Type Filter -->
        <div style="margin-bottom: 15px; padding: 8px; background: #343541; border-radius: 5px;">
            <div style="font-size: 10px; color: #888; margin-bottom: 5px;">FILTER BY ACCOUNT</div>
            <div style="display: flex; gap: 5px;">
                <a href="/?filter=all" style="flex:1; text-align:center; padding: 4px; border-radius: 3px; font-size: 11px; text-decoration:none; {{ 'background:#10a37f; color:white;' if account_filter == 'all' else 'background:#444654; color:#ccc;' }}">All</a>
                <a href="/?filter=enterprise" style="flex:1; text-align:center; padding: 4px; border-radius: 3px; font-size: 11px; text-decoration:none; {{ 'background:#3b82f6; color:white;' if account_filter == 'enterprise' else 'background:#444654; color:#ccc;' }}">Enterprise</a>
                <a href="/?filter=personal" style="flex:1; text-align:center; padding: 4px; border-radius: 3px; font-size: 11px; text-decoration:none; {{ 'background:#f59e0b; color:white;' if account_filter == 'personal' else 'background:#444654; color:#ccc;' }}">Personal</a>
            </div>
        </div>
        
        <h3 style="color:#888; font-size:12px;">RUNS ({{ run_ids|length }})</h3>
        {% for rid in run_ids %}
        {% set is_personal = '_personal' in rid %}
        <a href="/?run_id={{ rid }}&filter={{ account_filter }}" style="text-decoration:none; color:inherit;">
            <div class="prompt-item {{ 'active' if rid == active_run_id else '' }}" style="border-left-color: {{ '#f59e0b' if is_personal else '#3b82f6' }};">
                <span style="font-size: 9px; padding: 1px 4px; border-radius: 2px; margin-right: 4px; {{ 'background:#f59e0b; color:white;' if is_personal else 'background:#3b82f6; color:white;' }}">{{ 'P' if is_personal else 'E' }}</span>
                {{ rid.replace('_personal', '') }}
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
                {% set search_triggered = run_raw.web_search_triggered in ['1', 'true', 'True', True, 1] %}
                <div style="background: {{ '#d1fae5' if search_triggered else '#fee2e2' }}; padding: 6px 12px; border-radius: 6px; font-size: 12px;">
                    <strong>Web Search:</strong> {{ '✓ Triggered' if search_triggered else '✗ Not Triggered' }}
                </div>
                <div style="background: #e0e7ff; padding: 6px 12px; border-radius: 6px; font-size: 12px;">
                    <strong>Items:</strong> {{ run_raw.items_count or 0 }}
                </div>
                <div style="background: #f3e8ff; padding: 6px 12px; border-radius: 6px; font-size: 12px;">
                    <strong>With Citations:</strong> {{ run_raw.items_with_citations_count or 0 }}
                </div>
                <div style="background: #f3f4f6; padding: 6px 12px; border-radius: 6px; font-size: 12px;">
                    <strong>Total Sources:</strong> {{ cit_db|length }}
                </div>
                {% if run_raw.bing_overlap %}
                <div style="background: #ecfeff; padding: 6px 12px; border-radius: 6px; font-size: 12px;">
                    <strong>Bing overlap:</strong>
                    {{ "%.1f"|format(run_raw.bing_overlap.overall_pct) }}%
                    ({{ run_raw.bing_overlap.overall_matched }}/{{ run_raw.bing_overlap.total_cited }} cited)
                    {% if run_raw.bing_overlap.by_query %}
                    <div style="font-size: 10px; color: #155e75; margin-top: 3px;">
                        {% for q in run_raw.bing_overlap.by_query %}
                            <span style="display:inline-block; margin-right:8px;">
                                <strong>Q{{ q.q_num }}:</strong> {{ "%.0f"|format(q.pct) }}% ({{ q.matched }}/{{ q.total_cited }})
                            </span>
                        {% endfor %}
                    </div>
                    {% endif %}
                </div>
                {% endif %}
                {% if run_raw.double_overlap_cited is not none %}
                <div style="background: #f5f3ff; padding: 6px 12px; border-radius: 6px; font-size: 12px;">
                    <strong>Double-overlap cited:</strong> {{ run_raw.double_overlap_cited }}
                </div>
                {% endif %}
                <div style="background: #dbeafe; padding: 6px 12px; border-radius: 6px; font-size: 12px;">
                    <strong>Search Prob:</strong> Simple {{ run_raw.simple_search_prob }}% | Complex {{ run_raw.complex_search_prob }}% | None {{ run_raw.no_search_prob }}%
                </div>
                {% if run_raw.rejected_sources %}
                <div style="background: #fef2f2; padding: 6px 12px; border-radius: 6px; font-size: 12px;">
                    <strong>Rejected:</strong> {{ run_raw.rejected_sources|length }} sources
                </div>
                {% endif %}
                {% if run_raw.google_coverage %}
                <div style="background: #fff7ed; padding: 6px 12px; border-radius: 6px; font-size: 12px;">
                    <strong>Google coverage:</strong> {{ "%.1f"|format(run_raw.google_coverage.google_pct) }}% ({{ run_raw.google_coverage.google_matched }}/{{ run_raw.google_coverage.total_cited }})
                    &nbsp;|&nbsp;<strong>Total (Bing+Google):</strong> {{ "%.1f"|format(run_raw.google_coverage.combined_pct) }}%
                    &nbsp;|&nbsp;<strong>Missing:</strong> {{ "%.1f"|format(run_raw.google_coverage.missing_pct) }}%
                    <br>
                    <span style="color:#92400e; font-size: 11px;">
                        Google-only (not in Bing): {{ "%.1f"|format(run_raw.google_coverage.google_only_not_bing_pct) }}% ({{ run_raw.google_coverage.google_only_not_bing }})
                    </span>
                </div>
                {% endif %}
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
                            {% if run_raw.response_text %}
                            <div style="font-size: 13px; color: #333; line-height: 1.7;">
                                {{ run_raw.formatted_response|safe }}
                            </div>
                            {% else %}
                            <div style="color: #888; font-style: italic;">No response data available</div>
                            {% endif %}
                        {% endif %}
                        
                        <!-- Cited Sources -->
                        <div style="border-top: 1px solid #ddd; margin-top: 15px; padding-top: 15px;">
                            {% set cited_sources = cit_db|selectattr('citation_type', 'equalto', 'cited')|list %}
                            {% set additional_sources = cit_db|selectattr('citation_type', 'equalto', 'additional')|list %}
                            
                            <div style="font-size: 11px; color: #065f46; font-weight: bold; margin-bottom: 8px;">✅ CITED SOURCES ({{ cited_sources|length }})</div>
                            <div style="display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 15px;">
                            {% for cit in cited_sources %}
                                <a href="{{ cit.url }}" target="_blank" style="text-decoration: none;">
                                    <div style="font-size: 10px; background: {{ '#d1fae5' if cit.bing_rank else ('#fef3c7' if cit.in_google else '#fee2e2') }}; color: {{ '#065f46' if cit.bing_rank else ('#92400e' if cit.in_google else '#991b1b') }}; padding: 3px 8px; border-radius: 10px;">
                                        {{ cit.domain }} 🔗
                                        {% if cit.bing_rank %}
                                        <span style="font-weight: bold;">
                                            #{{ cit.bing_rank }}
                                            {% if cit.bing_query_nums_str %}{{ cit.bing_query_nums_str }}{% else %}Q{{ cit.bing_query_num }}{% endif %}
                                            {% if cit.double_overlap %}<span style="margin-left:6px; background:#7c3aed; color:white; padding:1px 5px; border-radius:8px; font-size:9px;">Q1+Q2</span>{% endif %}
                                        </span>
                                        {% elif cit.in_google %}
                                        <span style="font-weight: bold;">G</span>
                                        {% else %}
                                        <span style="font-weight: bold;">✗</span>
                                        {% endif %}
                                        {% if cit.in_google %}<span style="margin-left:4px; background:#f97316; color:white; padding:1px 5px; border-radius:8px; font-size:9px;">G</span>{% endif %}
                    </div>
                                </a>
                            {% endfor %}
                </div>

                            {% if additional_sources %}
                            <div style="font-size: 11px; color: #6b7280; font-weight: bold; margin-bottom: 8px;">➕ ADDITIONAL SOURCES ({{ additional_sources|length }})</div>
                            <div style="display: flex; flex-wrap: wrap; gap: 4px;">
                            {% for cit in additional_sources %}
                                <a href="{{ cit.url }}" target="_blank" style="text-decoration: none;">
                                    <div style="font-size: 10px; background: {{ '#e0f2fe' if cit.bing_rank else ('#fff7ed' if cit.in_google else '#f3f4f6') }}; color: {{ '#0369a1' if cit.bing_rank else ('#92400e' if cit.in_google else '#6b7280') }}; padding: 3px 8px; border-radius: 10px;">
                                        {{ cit.domain }} 🔗
                                        {% if cit.bing_rank %}
                                        <span style="font-weight: bold;">
                                            #{{ cit.bing_rank }}
                                            {% if cit.bing_query_nums_str %}{{ cit.bing_query_nums_str }}{% else %}{% if cit.bing_query_num %}Q{{ cit.bing_query_num }}{% endif %}{% endif %}
                                            {% if cit.double_overlap %}<span style="margin-left:6px; background:#7c3aed; color:white; padding:1px 5px; border-radius:8px; font-size:9px;">Q1+Q2</span>{% endif %}
                                        </span>
                                        {% elif cit.in_google %}
                                        <span style="font-weight: bold;">G</span>
                                        {% else %}
                                        <span style="font-weight: bold;">✗</span>
                                    {% endif %}
                                        {% if cit.in_google %}<span style="margin-left:4px; background:#f97316; color:white; padding:1px 5px; border-radius:8px; font-size:9px;">G</span>{% endif %}
                                    </div>
                                </a>
                                {% endfor %}
                            </div>
                                {% endif %}
                            </div>
                        
                        <!-- Rejected Sources (retrieved but not cited) -->
                        {% if run_raw.rejected_sources %}
                        <div style="border-top: 1px solid #fca5a5; margin-top: 15px; padding-top: 15px; background: #fef2f2; margin: 15px -15px -15px; padding: 15px; border-radius: 0 0 8px 8px;">
                            <div style="font-size: 11px; color: #991b1b; font-weight: bold; margin-bottom: 8px;">🚫 REJECTED SOURCES ({{ run_raw.rejected_sources|length }})</div>
                            <div style="font-size: 10px; color: #666; margin-bottom: 10px;">Retrieved by ChatGPT but NOT used in response</div>
                            {% for src in run_raw.rejected_sources %}
                            <div style="margin-bottom: 8px; padding: 8px; background: white; border-radius: 4px; border-left: 3px solid #ef4444;">
                                <div style="font-weight: bold; font-size: 11px; color: #111;">
                                    <a href="{{ src.url }}" target="_blank" style="text-decoration: none; color: #111;">{{ src.domain }} 🔗</a>
                                </div>
                                <div style="font-size: 10px; color: #555;">{{ src.title[:60] }}{% if src.title|length > 60 %}...{% endif %}</div>
                                <div style="font-size: 9px; color: #888; margin-top: 4px;">{{ src.snippet }}...</div>
                        </div>
                        {% endfor %}
                    </div>
                        {% endif %}
                </div>
                    
                    <!-- Raw Network Data (collapsible) -->
                    <details style="margin-top: 15px;">
                        <summary style="cursor: pointer; font-size: 12px; color: #666; font-weight: bold;">📡 RAW NETWORK DATA</summary>
                        <div style="margin-top: 10px;">
                            <div style="margin-bottom: 10px;">
                                <strong style="font-size: 11px;">Hidden Queries:</strong>
                                <pre style="background: #f8f9fa; padding: 8px; border-radius: 4px; font-size: 10px; overflow-x: auto; white-space: pre-wrap;">{{ run_raw.hidden_queries_json or '[]' }}</pre>
            </div>
                            <div style="margin-bottom: 10px;">
                                <strong style="font-size: 11px;">Search Result Groups:</strong>
                                <pre style="background: #f8f9fa; padding: 8px; border-radius: 4px; font-size: 10px; max-height: 200px; overflow: auto; white-space: pre-wrap;">{{ run_raw.search_result_groups_json or '[]' }}</pre>
        </div>
                            <div style="margin-bottom: 10px;">
                                <strong style="font-size: 11px;">Sources Cited:</strong>
                                <pre style="background: #f8f9fa; padding: 8px; border-radius: 4px; font-size: 10px; max-height: 150px; overflow: auto; white-space: pre-wrap;">{{ run_raw.sources_cited_json or '[]' }}</pre>
                            </div>
                            <div style="margin-bottom: 10px;">
                                <strong style="font-size: 11px;">Sources All:</strong>
                                <pre style="background: #f8f9fa; padding: 8px; border-radius: 4px; font-size: 10px; max-height: 150px; overflow: auto; white-space: pre-wrap;">{{ run_raw.sources_all_json or '[]' }}</pre>
                            </div>
                            <div style="margin-bottom: 10px;">
                                <strong style="font-size: 11px;">Sonic Classification (Search Probabilities):</strong>
                                <pre style="background: #f8f9fa; padding: 8px; border-radius: 4px; font-size: 10px; max-height: 200px; overflow: auto; white-space: pre-wrap;">{{ run_raw.sonic_classification_json or '{}' }}</pre>
                            </div>
                        </div>
                    </details>

                    <!-- Raw Response (collapsible) -->
                    <details style="margin-top: 15px;">
                        <summary style="cursor: pointer; font-size: 12px; color: #666; font-weight: bold;">📝 RAW RESPONSE TEXT</summary>
                        <div class="raw-text-box" style="margin-top: 10px;">{{ run_raw.response_text or 'No response text available' }}</div>
                    </details>

            </div>
                
                <!-- RIGHT: SERP Results (Tabbed: Bing | Google) -->
                <div>
                    <!-- Tab Headers -->
                    <div style="display: flex; gap: 0; margin-bottom: 10px; border-bottom: 2px solid #e5e7eb;">
                        <button id="tab-bing" onclick="showTab('bing')" style="flex:1; padding: 8px 12px; border: none; background: #3b82f6; color: white; font-weight: bold; font-size: 12px; cursor: pointer; border-radius: 6px 6px 0 0;">
                            Bing ({{ bing_results|length }})
                        </button>
                        <button id="tab-google" onclick="showTab('google')" style="flex:1; padding: 8px 12px; border: none; background: #e5e7eb; color: #666; font-weight: bold; font-size: 12px; cursor: pointer; border-radius: 6px 6px 0 0;">
                            Google ({{ google_results|length }})
                        </button>
                    </div>
                    
                    <!-- BING TAB -->
                    <div id="panel-bing">
                        <div id="query-filters" style="font-size: 10px; margin-bottom: 8px;">
                            {% for q_text in unique_queries %}
                            <label style="cursor:pointer; display: flex; align-items: center; gap: 4px; background: #f3f4f6; padding: 3px 6px; border-radius: 4px; margin-bottom: 4px;">
                                <input type="checkbox" class="query-toggle" data-query="{{ q_text }}" checked> 
                                <strong style="color:#007bff;">Q{{ loop.index }}:</strong> <span style="color:#555;">{{ q_text[:40] }}...</span>
                            </label>
                    {% endfor %}
                        </div>
                        
                        <div id="bing-results-container" style="max-height: 600px; overflow-y: auto;">
                        {% for b in bing_results %}
                        {% set q_num = '?' %}
                        {% if b['query'] in unique_queries %}
                            {% set q_num = unique_queries.index(b['query']) + 1 %}
                        {% endif %}
                        <div class="bing-item {{ 'matched' if b['is_cited'] else '' }}" data-query-text="{{ b['query'] }}" style="padding: 8px; border-bottom: 1px solid #eee; font-size: 12px;">
                            <span class="bing-rank-num" style="font-size: 10px;">#{{ b['position'] }}</span>
                            <span style="background:#e0e7ff; color:#3730a3; padding:1px 4px; border-radius:3px; font-size:9px; font-weight:bold;">Q{{ q_num }}</span>
                            <span style="background:#f3f4f6; color:#666; padding:1px 4px; border-radius:3px; font-size:9px; margin-left:4px;">Pg {{ b['page_num'] or '?' }}</span>
                            {% if b.get('in_google') %}<span style="background:#f97316; color:white; padding:1px 4px; border-radius:3px; font-size:9px; font-weight:bold; margin-left:4px;">G</span>{% endif %}
                            {% if b['is_cited'] %}<span style="color:#10a37f; font-size:10px; font-weight:bold; margin-left:4px;">CITED</span>{% endif %}
                            <div style="font-weight: bold; color: #111; font-size: 11px; margin-top: 2px;">
                                <a href="{{ b['url'] }}" target="_blank" style="text-decoration: none; color: #111;" title="{{ b['title'] or 'No title' }}">{{ (b['title'] or 'No title')[:50] }}...</a>
                            </div>
                            <div style="font-size: 10px; color: #10a37f;">{{ b['domain'] }}</div>
                        </div>
                        {% endfor %}
                        </div>
                    </div>
                    
                    <!-- GOOGLE TAB -->
                    <div id="panel-google" style="display: none;">
                        {% if google_results %}
                        <div style="font-size: 10px; margin-bottom: 8px; background: #fef3c7; padding: 6px 10px; border-radius: 4px; color: #92400e;">
                            Google Top 20 for queries from this run (collected via SerpAPI)
                        </div>
                        <div id="google-query-filters" style="font-size: 10px; margin-bottom: 8px;">
                            {% for q_text in google_unique_queries %}
                            {% set q_num = loop.index %}
                            <label style="cursor:pointer; display: flex; align-items: center; gap: 4px; background: #fff7ed; padding: 3px 6px; border-radius: 4px; margin-bottom: 4px;">
                                <input type="checkbox" class="google-query-toggle" data-query="{{ q_text }}" checked>
                                <strong style="color:#f97316;">Q{{ q_num }}:</strong>
                                <span style="color:#92400e;" title="{{ q_text }}">{{ q_text[:40] }}{% if q_text|length > 40 %}...{% endif %}</span>
                            </label>
                            {% endfor %}
                        </div>
                        <div id="google-results-container" style="max-height: 600px; overflow-y: auto;">
                        {% for g in google_results %}
                        <div class="google-item {{ 'matched' if g['is_used'] else '' }}" data-query-text="{{ g['query'] }}" style="padding: 8px; border-bottom: 1px solid #eee; font-size: 12px; {{ 'background: #fef9c3;' if g['is_used'] else '' }}">
                            <span style="background: #f97316; color: white; padding:1px 6px; border-radius:3px; font-size: 10px; font-weight:bold;">#{{ g['position'] }}{% if g['page_num'] and g['page_num'] > 1 %} (Pg {{ g['page_num'] }}){% endif %}</span>
                            <span style="background:#fef3c7; color:#92400e; padding:1px 4px; border-radius:3px; font-size:9px; font-weight:bold; margin-left:4px;">{{ g['query_label'] }}</span>
                            {% if g['result_type'] == 'video' %}
                            <span style="background:#fde68a; color:#92400e; padding:1px 4px; border-radius:3px; font-size:9px; font-weight:bold; margin-left:4px;">VIDEO</span>
                            {% elif g['result_type'] == 'discussion' %}
                            <span style="background:#e0e7ff; color:#3730a3; padding:1px 4px; border-radius:3px; font-size:9px; font-weight:bold; margin-left:4px;">DISCUSSION</span>
                            {% elif g['result_type'] == 'related_question' %}
                            <span style="background:#dcfce7; color:#166534; padding:1px 4px; border-radius:3px; font-size:9px; font-weight:bold; margin-left:4px;">PAA</span>
                            {% endif %}
                            {% if g['is_cited'] %}<span style="color:#10a37f; font-size:10px; font-weight:bold; margin-left:4px;">CITED</span>{% endif %}
                            {% if g['is_additional'] %}<span style="color:#6b7280; font-size:10px; font-weight:bold; margin-left:4px;">ADDITIONAL</span>{% endif %}
                            {% if g['is_used'] and not g['in_bing'] %}<span style="background:#fef3c7; color:#92400e; font-size:9px; font-weight:bold; padding:1px 4px; border-radius:3px; margin-left:4px;">GOOGLE ONLY</span>{% endif %}
                            <div style="font-weight: bold; color: #111; font-size: 11px; margin-top: 2px;">
                                <a href="{{ g['url'] }}" target="_blank" style="text-decoration: none; color: #111;" title="{{ g['title'] or 'No title' }}">{{ (g['title'] or 'No title')[:50] }}{% if (g['title'] or '')|length > 50 %}...{% endif %}</a>
                            </div>
                            <div style="font-size: 10px; color: #f97316;">{{ g['domain'] }}</div>
                        </div>
                        {% endfor %}
                        </div>
                        {% else %}
                        <div style="padding: 20px; text-align: center; color: #888;">
                            No Google results collected for this run yet.
                        </div>
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>

        <script>
            // Tab switching
            function showTab(tab) {
                document.getElementById('panel-bing').style.display = tab === 'bing' ? 'block' : 'none';
                document.getElementById('panel-google').style.display = tab === 'google' ? 'block' : 'none';
                
                document.getElementById('tab-bing').style.background = tab === 'bing' ? '#3b82f6' : '#e5e7eb';
                document.getElementById('tab-bing').style.color = tab === 'bing' ? 'white' : '#666';
                document.getElementById('tab-google').style.background = tab === 'google' ? '#f97316' : '#e5e7eb';
                document.getElementById('tab-google').style.color = tab === 'google' ? 'white' : '#666';
            }
            
            // Query toggle checkboxes (Bing)
            document.querySelectorAll('.query-toggle').forEach(checkbox => {
                checkbox.addEventListener('change', function() {
                    const queryText = this.getAttribute('data-query');
                    const isVisible = this.checked;
                    
                    document.querySelectorAll(`.bing-item[data-query-text="${queryText}"]`).forEach(item => {
                        item.style.display = isVisible ? 'block' : 'none';
                    });
                });
            });

            // Query toggle checkboxes (Google)
            document.querySelectorAll('.google-query-toggle').forEach(checkbox => {
                checkbox.addEventListener('change', function() {
                    const queryText = this.getAttribute('data-query');
                    const isVisible = this.checked;
                    
                    document.querySelectorAll(`.google-item[data-query-text="${queryText}"]`).forEach(item => {
                        item.style.display = isVisible ? 'block' : 'none';
                    });
                });
            });

            // Sidebar scroll persistence
            (function() {
                const sidebar = document.getElementById('sidebar');
                const savedPos = localStorage.getItem('sidebarScrollPos');
                
                if (savedPos) {
                    sidebar.scrollTop = parseInt(savedPos);
                } else {
                    // First load - scroll to active item
                    const active = document.querySelector('.prompt-item.active');
                    if (active) {
                        active.scrollIntoView({ block: 'center' });
                    }
                }

                // Save scroll on any sidebar link click
                sidebar.querySelectorAll('a').forEach(link => {
                    link.addEventListener('click', function() {
                        localStorage.setItem('sidebarScrollPos', sidebar.scrollTop);
                    });
                });
            })();
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

# Cache for raw network data
_raw_data_cache = None

def get_raw_network_data(run_id):
    """Load raw network data from CSV/JSON for a specific run."""
    global _raw_data_cache
    
    if _raw_data_cache is None:
        import csv
        import json as json_module
        import sys
        
        # Increase CSV field size limit for large response fields
        csv.field_size_limit(sys.maxsize)
        
        _raw_data_cache = {}
        
        # Load enterprise data
        csv_path = 'datapass/chatgpt_results_2026-01-27T11-23-04-enterprise.csv'
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rid = f"{row['prompt_id']}_r{row['run_number']}"
                    _raw_data_cache[rid] = {
                        'hidden_queries_json': row.get('hidden_queries_json', '[]'),
                        'search_result_groups_json': row.get('search_result_groups_json', '[]'),
                        'content_references_json': row.get('content_references_json', '[]'),
                        'sources_cited_json': row.get('sources_cited_json', '[]'),
                        'sources_all_json': row.get('sources_all_json', '[]'),
                        'sources_additional_json': row.get('sources_additional_json', '[]'),
                        'sonic_classification_json': row.get('sonic_classification_json', '{}')
                    }
        except Exception as e:
            print(f"Error loading enterprise CSV: {e}")
        
        # Load personal data
        personal_csv = 'datapass/personal_data_run/chatgpt_results_2026-01-28T02-25-34.csv'
        try:
            with open(personal_csv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rid = f"{row['prompt_id']}_r{row['run_number']}_personal"
                    _raw_data_cache[rid] = {
                        'hidden_queries_json': row.get('hidden_queries_json', '[]'),
                        'search_result_groups_json': row.get('search_result_groups_json', '[]'),
                        'content_references_json': row.get('content_references_json', '[]'),
                        'sources_cited_json': row.get('sources_cited_json', '[]'),
                        'sources_all_json': row.get('sources_all_json', '[]'),
                        'sources_additional_json': row.get('sources_additional_json', '[]'),
                        'sonic_classification_json': row.get('sonic_classification_json', '{}')
                    }
        except Exception as e:
            print(f"Error loading personal CSV: {e}")
    
    return _raw_data_cache.get(run_id, {})

@app.route('/')
def index():
    run_id = request.args.get('run_id')
    account_filter = request.args.get('filter', 'all')
    db = get_db()
    
    import re

    def _estimate_counts_from_text(text: str):
        """Heuristic fallback when runs.items_count fields are missing/0."""
        if not text:
            return 0, 0
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

        # Count list-like lines as "items" candidates
        list_like = 0
        for ln in lines:
            if re.match(r'^(\d+[\.\)]|[-*•])\s+', ln):
                list_like += 1

        # Find [https://...] tags and count unique line buckets that contain at least one URL
        url_matches = list(re.finditer(r'\[(https?:\/\/[^\]\s]+)\]', text))
        if not url_matches:
            return max(list_like, 0), 0

        line_buckets = set()
        for m in url_matches:
            # Bucket by line number (0-based)
            line_buckets.add(text.count('\n', 0, m.start()))

        with_citations = len(line_buckets) if line_buckets else len(url_matches)
        items = max(list_like, with_citations)
        return items, with_citations
    
    # Get runs ordered: enterprise first (sorted by prompt_id, run_number), then personal
    if account_filter == 'enterprise':
        run_ids = [r['run_id'] for r in db.execute(
            "SELECT run_id FROM runs WHERE account_type = 'enterprise' ORDER BY prompt_id, run_number"
        ).fetchall()]
    elif account_filter == 'personal':
        run_ids = [r['run_id'] for r in db.execute(
            "SELECT run_id FROM runs WHERE account_type = 'personal' ORDER BY prompt_id, run_number"
        ).fetchall()]
    else:
        # All: Enterprise first, then Personal
        run_ids = [r['run_id'] for r in db.execute(
            "SELECT run_id FROM runs ORDER BY account_type DESC, prompt_id, run_number"
        ).fetchall()]
    
    run_raw = None
    cit_db = []
    bing_results = []
    google_results = []
    google_unique_queries = []
    items_raw = []
    unique_queries = []
    
    if run_id:
        # Get run data from database
        db_run = db.execute('''
            SELECT p.prompt as query, r.generated_search_query, r.response_text, r.hidden_queries, r.items_json,
                   r.web_search_triggered, r.web_search_forced, r.items_count, r.items_with_citations_count,
                   r.search_result_groups_json, r.account_type
            FROM runs r
            LEFT JOIN prompts p ON r.prompt_id = p.prompt_id
            WHERE r.run_id = ?
        ''', (run_id,)).fetchone()
        
        if db_run:
            # Load extra raw data from CSV
            extra_data = get_raw_network_data(run_id)
            print(f"DEBUG: extra_data keys for {run_id}: {list(extra_data.keys())}")
            
            run_raw = {
                'query': db_run['query'] or 'N/A',
                'generated_search_query': db_run['generated_search_query'] or 'N/A',
                'response_text': db_run['response_text'] or '',
                'hidden_queries': db_run['hidden_queries'] or '',
                'web_search_triggered': db_run['web_search_triggered'],
                'web_search_forced': db_run['web_search_forced'],
                'items_count': db_run['items_count'],
                'items_with_citations_count': db_run['items_with_citations_count'],
                'hidden_queries_json': extra_data.get('hidden_queries_json', '[]'),
                'search_result_groups_json': extra_data.get('search_result_groups_json', '[]'),
                'content_references_json': extra_data.get('content_references_json', '[]'),
                'sources_cited_json': extra_data.get('sources_cited_json', '[]'),
                'sources_all_json': extra_data.get('sources_all_json', '[]'),
                'sources_additional_json': extra_data.get('sources_additional_json', '[]'),
                'sonic_classification_json': extra_data.get('sonic_classification_json', '{}')
            }
            
            # Parse sonic classification for search probabilities
            try:
                sonic = json.loads(run_raw['sonic_classification_json'] or '{}')
                run_raw['simple_search_prob'] = round(sonic.get('simple_search_prob', 0) * 100, 1)
                run_raw['complex_search_prob'] = round(sonic.get('complex_search_prob', 0) * 100, 1)
                run_raw['no_search_prob'] = round(sonic.get('no_search_prob', 0) * 100, 1)
            except:
                run_raw['simple_search_prob'] = 0
                run_raw['complex_search_prob'] = 0
                run_raw['no_search_prob'] = 0
            
            # Calculate rejected sources (retrieved but not cited/additional)
            try:
                srg = json.loads(run_raw['search_result_groups_json'] or '[]')
                cited = set(s['url'] for s in json.loads(run_raw['sources_cited_json'] or '[]'))
                additional = set(s['url'] for s in json.loads(run_raw['sources_additional_json'] or '[]'))
                all_used = cited | additional
                
                rejected = []
                for group in srg:
                    for entry in group.get('entries', []):
                        if entry.get('url') and entry['url'] not in all_used:
                            rejected.append({
                                'url': entry['url'],
                                'title': entry.get('title', ''),
                                'domain': group.get('domain', ''),
                                'snippet': (entry.get('snippet') or '')[:100]
                            })
                run_raw['rejected_sources'] = rejected
                print(f"DEBUG: Found {len(rejected)} rejected sources for {run_id}")
            except Exception as e:
                print(f"ERROR calculating rejected: {e}")
                run_raw['rejected_sources'] = []
            
            # Parse items_json for structured display
            try:
                items_raw = json.loads(db_run['items_json'] or '[]')
            except:
                items_raw = []

            # If no structured items, format response_text with inline citation chips
            if not items_raw and run_raw.get('response_text'):
                import re
                import html
                
                response_text = run_raw['response_text']
                
                # Build Bing rank lookup for this run
                bing_lookup = {}
                bing_rows = db.execute('''
                    SELECT url_normalized, MIN(position) as rank, query
                    FROM bing_results 
                    WHERE run_id = ?
                    GROUP BY url_normalized
                ''', (run_id,)).fetchall()
                for br in bing_rows:
                    bing_lookup[br['url_normalized']] = {'rank': br['rank'], 'query': br['query']}
                
                # Build Google URL lookup for this run (for Google-only badges)
                base_run_id_for_google = run_id.replace('_personal', '')
                run_account_type_for_google = db_run['account_type'] if db_run and db_run['account_type'] else None
                google_url_lookup = set()
                google_rows_early = db.execute('''
                    SELECT LOWER(REPLACE(REPLACE(REPLACE(url, 'https://', ''), 'http://', ''), 'www.', '')) as url_norm
                    FROM google_results
                    WHERE chatgpt_run_id = ? AND (? IS NULL OR account_type = ?)
                ''', (base_run_id_for_google, run_account_type_for_google, run_account_type_for_google)).fetchall()
                for gr in google_rows_early:
                    url_norm = (gr['url_norm'] or '').split('?')[0].rstrip('/')
                    if url_norm:
                        google_url_lookup.add(url_norm)
                
                def normalize_url(url):
                    if not url: return ""
                    url = url.lower().replace('https://', '').replace('http://', '').replace('www.', '')
                    if '?' in url: url = url.split('?')[0]
                    return url.rstrip('/')
                
                # === RECONSTRUCTOR: Build ref_index -> URL lookup from search_result_groups_json ===
                ref_index_to_url = {}
                try:
                    srg_json_str = extra_data.get('search_result_groups_json', '[]') or '[]'
                    srg = json.loads(srg_json_str)
                    for group in srg:
                        # Handle groups with 'entries'
                        if isinstance(group, dict) and 'entries' in group:
                            for entry in group.get('entries', []):
                                ref_id = entry.get('ref_id', {})
                                if ref_id and 'ref_index' in ref_id:
                                    ref_index_to_url[int(ref_id['ref_index'])] = {
                                        'url': entry.get('url', ''),
                                        'title': entry.get('title', ''),
                                        'domain': group.get('domain', entry.get('attribution', ''))
                                    }
                        # Handle direct entries (not in a group)
                        elif isinstance(group, dict) and group.get('ref_id') and 'ref_index' in group.get('ref_id', {}):
                            ref_index_to_url[int(group['ref_id']['ref_index'])] = {
                                'url': group.get('url', ''),
                                'title': group.get('title', ''),
                                'domain': group.get('attribution', '')
                            }
                    print(f"DEBUG: Built ref_index lookup with {len(ref_index_to_url)} entries")
                except Exception as e:
                    print(f"ERROR building ref_index lookup: {e}")
                
                # === Parse content_references_json to find multi-chip tokens ===
                multi_chips_list = [] # List of {start_idx, matched_text, urls}
                multi_chips_map = {} # start_idx -> urls
                try:
                    refs_json_str = extra_data.get('content_references_json', '[]') or '[]'
                    refs_json = json.loads(refs_json_str)
                    for ref in refs_json:
                        if isinstance(ref, dict) and ref.get('matched_text'):
                            matched = ref['matched_text']
                            # Multi-chip heuristics:
                            # - multiple turn0search indices in matched_text (classic "+1")
                            # - OR multiple items with urls (sometimes matched_text only references one token, but items carry the rest)
                            search_indices = re.findall(r'turn0search(\d+)', matched)
                            direct_items = ref.get('items', []) if isinstance(ref.get('items', []), list) else []

                            is_multi = (len(search_indices) > 1) or (len([it for it in direct_items if isinstance(it, dict) and it.get('url')]) > 1)
                            if not is_multi:
                                continue

                            urls_for_chip = []
                            # 1) From turn0search indices -> search_result_groups lookup
                            for idx_str in search_indices:
                                try:
                                    idx = int(idx_str)
                                except Exception:
                                    continue
                                if idx in ref_index_to_url and ref_index_to_url[idx].get('url'):
                                    urls_for_chip.append(ref_index_to_url[idx])

                            # 2) From direct items (as a fallback / supplement)
                            for it in direct_items:
                                if not isinstance(it, dict):
                                    continue
                                u = it.get('url')
                                if u:
                                    urls_for_chip.append({
                                        'url': u,
                                        'title': it.get('title', ''),
                                        'domain': it.get('attribution', it.get('domain', ''))
                                    })

                            # Deduplicate by normalized URL
                            dedup = []
                            seen = set()
                            for uinfo in urls_for_chip:
                                u = uinfo.get('url', '')
                                un = normalize_url(u)
                                if not un or un in seen:
                                    continue
                                seen.add(un)
                                dedup.append(uinfo)
                            urls_for_chip = dedup

                            if urls_for_chip:
                                mc_data = {
                                    'start_idx': ref.get('start_idx', 0),
                                    'matched_text': matched,
                                    'urls': urls_for_chip
                                }
                                multi_chips_list.append(mc_data)
                                multi_chips_map[ref.get('start_idx', 0)] = urls_for_chip
                    print(f"DEBUG: Found {len(multi_chips_list)} multi-chip citations")
                except Exception as e:
                    print(f"ERROR parsing content_references_json: {e}")
                
                # Build a map of all cited URLs for this run
                all_cited_urls = []
                try:
                    cited_json = json.loads(run_raw.get('sources_cited_json', '[]') or '[]')
                    for s in cited_json:
                        if s.get('url'):
                            all_cited_urls.append(s.get('url'))
                    
                    # Also look in content_references_json for raw URLs
                    refs_json_str = extra_data.get('content_references_json', '[]') or '[]'
                    refs_json = json.loads(refs_json_str)
                    for r in refs_json:
                        if isinstance(r, str) and r.startswith('http'):
                            all_cited_urls.append(r)
                except:
                    pass

                # Deduplicate while preserving order
                seen_urls = set()
                unique_cited = []
                for u in all_cited_urls:
                    if u not in seen_urls:
                        unique_cited.append(u)
                        seen_urls.add(u)
                all_cited_urls = unique_cited
                
                # Track which URLs we've already placed chips for
                used_urls = set()

                def replace_url(match):
                    url = match.group(1)
                    start_pos = match.start()
                    url_norm = normalize_url(url)
                    
                    # Check if this position corresponds to a known multi-chip
                    # We look for a multi-chip that starts near this [URL] tag
                    # ChatGPT usually puts the [URL] right after the multi-chip token
                    multi_chip_urls = None
                    for idx_pos, urls in multi_chips_map.items():
                        if abs(idx_pos - start_pos) < 50: # Close proximity
                            multi_chip_urls = urls
                            break
                    
                    if multi_chip_urls:
                        chips_html = []
                        for u_info in multi_chip_urls:
                            u = u_info['url']
                            u_norm = normalize_url(u)
                            used_urls.add(u_norm)
                            
                            clean_u = u.replace('https://', '').replace('http://', '').replace('www.', '').split('?')[0].rstrip('/')
                            domain = clean_u.split('/')[0] if '/' in clean_u else clean_u
                            
                            bing_info = bing_lookup.get(u_norm, {})
                            bing_rank = bing_info.get('rank')
                            
                            in_google = u_norm in google_url_lookup
                            g_badge = ' <span style="background:#f97316;color:white;padding:1px 4px;border-radius:6px;font-size:9px;font-weight:bold;">G</span>' if in_google else ''
                            if bing_rank:
                                chips_html.append(f'<a href="{html.escape(u)}" target="_blank" style="display:inline-block; font-size:11px; background:#d1fae5; color:#065f46; padding:2px 8px; border-radius:12px; text-decoration:none; margin:2px 2px;">{html.escape(domain)} <span style="background:#10a37f;color:white;padding:1px 4px;border-radius:6px;font-size:9px;font-weight:bold;">#{bing_rank}</span>{g_badge}</a>')
                            elif in_google:
                                chips_html.append(f'<a href="{html.escape(u)}" target="_blank" style="display:inline-block; font-size:11px; background:#fef3c7; color:#92400e; padding:2px 8px; border-radius:12px; text-decoration:none; margin:2px 2px;">{html.escape(domain)} <span style="background:#f97316;color:white;padding:1px 4px;border-radius:6px;font-size:9px;font-weight:bold;">G</span></a>')
                            else:
                                chips_html.append(f'<a href="{html.escape(u)}" target="_blank" style="display:inline-block; font-size:11px; background:#fee2e2; color:#991b1b; padding:2px 8px; border-radius:12px; text-decoration:none; margin:2px 2px;">{html.escape(domain)} <span style="font-weight:bold;">✗</span></a>')
                        return "".join(chips_html)
                    
                    # Fallback to single chip
                    used_urls.add(url_norm)
                    clean_url = url.replace('https://', '').replace('http://', '').replace('www.', '').split('?')[0].rstrip('/')
                    domain = clean_url.split('/')[0] if '/' in clean_url else clean_url
                    
                    bing_info = bing_lookup.get(url_norm, {})
                    bing_rank = bing_info.get('rank')
                    in_google = url_norm in google_url_lookup
                    g_badge = ' <span style="background:#f97316;color:white;padding:1px 4px;border-radius:6px;font-size:9px;font-weight:bold;">G</span>' if in_google else ''
                    
                    if bing_rank:
                        return f'<a href="{html.escape(url)}" target="_blank" style="display:inline-block; font-size:11px; background:#d1fae5; color:#065f46; padding:2px 8px; border-radius:12px; text-decoration:none; margin:2px 0;">{html.escape(domain)} <span style="background:#10a37f;color:white;padding:1px 4px;border-radius:6px;font-size:9px;font-weight:bold;">#{bing_rank}</span>{g_badge}</a>'
                    elif in_google:
                        return f'<a href="{html.escape(url)}" target="_blank" style="display:inline-block; font-size:11px; background:#fef3c7; color:#92400e; padding:2px 8px; border-radius:12px; text-decoration:none; margin:2px 0;">{html.escape(domain)} <span style="background:#f97316;color:white;padding:1px 4px;border-radius:6px;font-size:9px;font-weight:bold;">G</span></a>'
                    else:
                        return f'<a href="{html.escape(url)}" target="_blank" style="display:inline-block; font-size:11px; background:#fee2e2; color:#991b1b; padding:2px 8px; border-radius:12px; text-decoration:none; margin:2px 0;">{html.escape(domain)} <span style="font-weight:bold;">✗</span></a>'
                
                # 1. Replace [URL] patterns first (now with multi-chip reconstruction)
                # We use a while loop or finditer to handle indices correctly as we modify the string
                formatted = response_text
                
                # Sort multi-chips by start_idx descending so we don't break indices of earlier ones
                sorted_multi_indices = sorted(multi_chips_map.keys(), reverse=True)
                
                # Track used URLs for the "Recovered" section at the bottom
                used_urls = set()

                # First, handle the multi-chips by looking for the [URL] tags that follow them
                # ChatGPT usually outputs: [Token][URL]
                for mc_start in sorted_multi_indices:
                    # Find the [URL] tag that immediately follows this multi-chip token
                    # We look within a reasonable range after the token
                    search_range = formatted[mc_start:mc_start+200]
                    match = re.search(r'\[([^\]]+)\]', search_range)
                    
                    if match:
                        match_start_in_formatted = mc_start + match.start()
                        match_end_in_formatted = mc_start + match.end()
                        
                        urls_data = multi_chips_map[mc_start]
                        chips_html = []
                        for u_info in urls_data:
                            u = u_info['url']
                            u_norm = normalize_url(u)
                            used_urls.add(u_norm)
                            
                            clean_u = u.replace('https://', '').replace('http://', '').replace('www.', '').split('?')[0].rstrip('/')
                            domain = clean_u.split('/')[0] if '/' in clean_u else clean_u
                            
                            bing_info = bing_lookup.get(u_norm, {})
                            bing_rank = bing_info.get('rank')
                            in_google = u_norm in google_url_lookup
                            g_badge = ' <span style="background:#f97316;color:white;padding:1px 4px;border-radius:6px;font-size:9px;font-weight:bold;">G</span>' if in_google else ''
                            
                            if bing_rank:
                                chips_html.append(f'<a href="{html.escape(u)}" target="_blank" style="display:inline-block; font-size:11px; background:#d1fae5; color:#065f46; padding:2px 8px; border-radius:12px; text-decoration:none; margin:2px 2px;">{html.escape(domain)} <span style="background:#10a37f;color:white;padding:1px 4px;border-radius:6px;font-size:9px;font-weight:bold;">#{bing_rank}</span>{g_badge}</a>')
                            elif in_google:
                                chips_html.append(f'<a href="{html.escape(u)}" target="_blank" style="display:inline-block; font-size:11px; background:#fef3c7; color:#92400e; padding:2px 8px; border-radius:12px; text-decoration:none; margin:2px 2px;">{html.escape(domain)} <span style="background:#f97316;color:white;padding:1px 4px;border-radius:6px;font-size:9px;font-weight:bold;">G</span></a>')
                            else:
                                chips_html.append(f'<a href="{html.escape(u)}" target="_blank" style="display:inline-block; font-size:11px; background:#fee2e2; color:#991b1b; padding:2px 8px; border-radius:12px; text-decoration:none; margin:2px 2px;">{html.escape(domain)} <span style="font-weight:bold;">✗</span></a>')
                        
                        # Replace the [URL] tag with our multiple chips
                        formatted = formatted[:match_start_in_formatted] + "".join(chips_html) + formatted[match_end_in_formatted:]

                # Now handle any remaining single [URL] tags
                def replace_single_url(match):
                    url = match.group(1)
                    url_norm = normalize_url(url)
                    
                    # If this URL was already part of a multi-chip, we might want to skip it 
                    # but usually they are distinct in the text.
                    used_urls.add(url_norm)
                    
                    clean_url = url.replace('https://', '').replace('http://', '').replace('www.', '').split('?')[0].rstrip('/')
                    domain = clean_url.split('/')[0] if '/' in clean_url else clean_url
                    
                    bing_info = bing_lookup.get(url_norm, {})
                    bing_rank = bing_info.get('rank')
                    in_google = url_norm in google_url_lookup
                    g_badge = ' <span style="background:#f97316;color:white;padding:1px 4px;border-radius:6px;font-size:9px;font-weight:bold;">G</span>' if in_google else ''
                    
                    if bing_rank:
                        return f'<a href="{html.escape(url)}" target="_blank" style="display:inline-block; font-size:11px; background:#d1fae5; color:#065f46; padding:2px 8px; border-radius:12px; text-decoration:none; margin:2px 0;">{html.escape(domain)} <span style="background:#10a37f;color:white;padding:1px 4px;border-radius:6px;font-size:9px;font-weight:bold;">#{bing_rank}</span>{g_badge}</a>'
                    elif in_google:
                        return f'<a href="{html.escape(url)}" target="_blank" style="display:inline-block; font-size:11px; background:#fef3c7; color:#92400e; padding:2px 8px; border-radius:12px; text-decoration:none; margin:2px 0;">{html.escape(domain)} <span style="background:#f97316;color:white;padding:1px 4px;border-radius:6px;font-size:9px;font-weight:bold;">G</span></a>'
                    else:
                        return f'<a href="{html.escape(url)}" target="_blank" style="display:inline-block; font-size:11px; background:#fee2e2; color:#991b1b; padding:2px 8px; border-radius:12px; text-decoration:none; margin:2px 0;">{html.escape(domain)} <span style="font-weight:bold;">✗</span></a>'

                formatted = re.sub(r'\[([^\]]+)\]', replace_single_url, formatted)
                
                # 2. Find any cited URLs that weren't in the [URL] text and add them as chips
                # This handles any remaining URLs that didn't get matched to a chip
                remaining_chips = []
                # Also avoid duplicating URLs that were already explained as part of a multi-chip
                multi_chip_url_norms = set()
                try:
                    for urls in multi_chips_map.values():
                        for uinfo in urls:
                            multi_chip_url_norms.add(normalize_url(uinfo.get('url', '')))
                except:
                    pass
                for url in all_cited_urls:
                    url_norm = normalize_url(url)
                    if url_norm not in used_urls and url_norm not in multi_chip_url_norms:
                        clean_url = url.replace('https://', '').replace('http://', '').replace('www.', '').split('?')[0].rstrip('/')
                        domain = clean_url.split('/')[0] if '/' in clean_url else clean_url
                        bing_info = bing_lookup.get(url_norm, {})
                        bing_rank = bing_info.get('rank')
                        in_google = url_norm in google_url_lookup
                        g_badge = ' <span style="background:#f97316;color:white;padding:1px 4px;border-radius:6px;font-size:9px;font-weight:bold;">G</span>' if in_google else ''
                        
                        chip_html = ""
                        if bing_rank:
                            chip_html = f'<a href="{html.escape(url)}" target="_blank" style="display:inline-block; font-size:11px; background:#d1fae5; color:#065f46; padding:2px 8px; border-radius:12px; text-decoration:none; margin:2px 0; margin-left:5px;">{html.escape(domain)} <span style="background:#10a37f;color:white;padding:1px 4px;border-radius:6px;font-size:9px;font-weight:bold;">#{bing_rank}</span>{g_badge}</a>'
                        elif in_google:
                            chip_html = f'<a href="{html.escape(url)}" target="_blank" style="display:inline-block; font-size:11px; background:#fef3c7; color:#92400e; padding:2px 8px; border-radius:12px; text-decoration:none; margin:2px 0; margin-left:5px;">{html.escape(domain)} <span style="background:#f97316;color:white;padding:1px 4px;border-radius:6px;font-size:9px;font-weight:bold;">G</span></a>'
                        else:
                            chip_html = f'<a href="{html.escape(url)}" target="_blank" style="display:inline-block; font-size:11px; background:#fee2e2; color:#991b1b; padding:2px 8px; border-radius:12px; text-decoration:none; margin:2px 0; margin-left:5px;">{html.escape(domain)} <span style="font-weight:bold;">✗</span></a>'
                        remaining_chips.append(chip_html)
                        used_urls.add(url_norm)

                # Append missing chips to the end of the response
                if remaining_chips:
                    formatted += '<div style="margin-top:10px; padding-top:10px; border-top:1px dashed #ddd;"><span style="font-size:11px; color:#666; font-weight:bold;">RECOVERED HIDDEN CITATIONS (FROM NETWORK DATA):</span><br>' + " ".join(remaining_chips) + '</div>'

                # === Display Multi-Chip Analysis (the "+1" breakdown) ===
                if multi_chips_list:
                    multi_chip_html = '<div style="margin-top:15px; padding:12px; background:#fef3c7; border:1px solid #f59e0b; border-radius:8px;"><span style="font-size:12px; color:#92400e; font-weight:bold;">🔗 MULTI-CHIP CITATIONS ANALYSIS ("+1" Breakdown)</span><br>'
                    multi_chip_html += '<span style="font-size:10px; color:#78350f;">ChatGPT combined multiple sources into single citation chips. Here are the hidden links:</span><br><br>'
                    
                    for i, mc in enumerate(multi_chips_list):
                        multi_chip_html += f'<div style="margin-bottom:10px; padding:8px; background:white; border-radius:4px;">'
                        multi_chip_html += f'<span style="font-size:10px; color:#666;">Token: <code>{html.escape(mc["matched_text"][:50])}...</code></span><br>'
                        multi_chip_html += f'<span style="font-size:11px; font-weight:bold;">Links ({len(mc["urls"])}):</span><br>'
                        
                        for url_info in mc['urls']:
                            url = url_info['url']
                            url_norm = normalize_url(url)
                            domain = url_info['domain'] or url.split('/')[2] if '/' in url else url
                            bing_info = bing_lookup.get(url_norm, {})
                            bing_rank = bing_info.get('rank')
                            in_google = url_norm in google_url_lookup
                            g_badge = ' <span style="background:#f97316;color:white;padding:1px 3px;border-radius:4px;font-size:8px;font-weight:bold;">G</span>' if in_google else ''
                            
                            if bing_rank:
                                multi_chip_html += f'<a href="{html.escape(url)}" target="_blank" style="display:inline-block; font-size:10px; background:#d1fae5; color:#065f46; padding:2px 6px; border-radius:10px; text-decoration:none; margin:2px;">{html.escape(domain)} <span style="background:#10a37f;color:white;padding:1px 3px;border-radius:4px;font-size:8px;font-weight:bold;">#{bing_rank}</span>{g_badge}</a>'
                            elif in_google:
                                multi_chip_html += f'<a href="{html.escape(url)}" target="_blank" style="display:inline-block; font-size:10px; background:#fef3c7; color:#92400e; padding:2px 6px; border-radius:10px; text-decoration:none; margin:2px;">{html.escape(domain)} <span style="background:#f97316;color:white;padding:1px 3px;border-radius:4px;font-size:8px;font-weight:bold;">G</span></a>'
                            else:
                                multi_chip_html += f'<a href="{html.escape(url)}" target="_blank" style="display:inline-block; font-size:10px; background:#fee2e2; color:#991b1b; padding:2px 6px; border-radius:10px; text-decoration:none; margin:2px;">{html.escape(domain)} ✗</a>'
                        
                        multi_chip_html += '</div>'
                    
                    multi_chip_html += '</div>'
                    formatted += multi_chip_html

                # Replace newlines with <br>
                formatted = formatted.replace('\n', '<br>')
                run_raw['formatted_response'] = formatted
            else:
                run_raw['formatted_response'] = ''
        else:
            run_raw = {'query': 'N/A', 'generated_search_query': 'N/A', 'response_text': f'Run {run_id} not found', 'hidden_queries': '', 'web_search_triggered': None, 'web_search_forced': None, 'items_count': 0, 'items_with_citations_count': 0, 'hidden_queries_json': '[]', 'search_result_groups_json': '[]', 'sources_cited_json': '[]', 'sources_all_json': '[]', 'simple_search_prob': 0, 'complex_search_prob': 0, 'no_search_prob': 0, 'rejected_sources': []}

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

        # ---- Badge counts fallback (esp. personal runs) ----
        # If the DB stored 0 for items_count fields, derive counts from items_json, citations, and/or response_text.
        if run_raw:
            try:
                stored_items = int(run_raw.get('items_count') or 0)
            except:
                stored_items = 0
            try:
                stored_with = int(run_raw.get('items_with_citations_count') or 0)
            except:
                stored_with = 0

            derived_items = stored_items
            derived_with = stored_with

            if derived_with <= 0:
                derived_with = len([c for c in cit_db if c.get('citation_type') == 'cited'])
                if derived_with <= 0:
                    _, derived_with = _estimate_counts_from_text(run_raw.get('response_text') or '')

            if derived_items <= 0:
                if items_raw:
                    derived_items = len(items_raw)
                else:
                    derived_items, _ = _estimate_counts_from_text(run_raw.get('response_text') or '')
                if derived_items <= 0 and derived_with > 0:
                    derived_items = derived_with
            else:
                # Common personal-run pattern: the whole answer is one "paragraph" (no newlines),
                # but it contains many cited products. In that case, line-based heuristics undercount.
                if stored_items <= 0 and not items_raw and derived_with > 0 and derived_items < derived_with:
                    derived_items = derived_with

            run_raw['items_count'] = derived_items
            run_raw['items_with_citations_count'] = derived_with
        
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
        
        # Build set of Bing URL norms for quick lookup
        bing_url_norms = set(b.get('url_normalized', '') for b in bing_results)
        
        # Get Google results for this run (via chatgpt_run_id link)
        # Use account_type to avoid mixing personal/enterprise results
        base_run_id = run_id.replace('_personal', '')
        run_account_type = db_run['account_type'] if db_run and db_run['account_type'] else None
        google_rows = db.execute('''
            SELECT g.*
            FROM google_results g
            WHERE g.chatgpt_run_id = ? AND (? IS NULL OR g.account_type = ?)
            ORDER BY g.query, g.result_type, g.page_num ASC, g.position ASC
        ''', (base_run_id, run_account_type, run_account_type)).fetchall()
        
        cited_url_norms = set(
            (c.get('url_normalized') or '').lower()
            for c in cit_db
            if c.get('citation_type') == 'cited' and c.get('url_normalized')
        )
        additional_url_norms = set(
            (c.get('url_normalized') or '').lower()
            for c in cit_db
            if c.get('citation_type') == 'additional' and c.get('url_normalized')
        )

        google_results = []
        for row in google_rows:
            g = dict(row)
            query_text = (g.get('query') or '').strip()
            if not query_text or query_text.lower() == 'n/a':
                continue
            if g.get('query_type') == 'generated_search_query':
                continue  # Only show Q1/Q2 (hidden queries) to match Bing
            # Check if this Google URL is also in Bing
            url_norm = (g.get('url') or '').lower().replace('https://', '').replace('http://', '').replace('www.', '').split('?')[0].rstrip('/')
            g['in_bing'] = url_norm in bing_url_norms
            g['is_cited'] = url_norm in cited_url_norms
            g['is_additional'] = url_norm in additional_url_norms
            g['is_used'] = g['is_cited'] or g['is_additional']
            google_results.append(g)

        # Build Google query list (for toggles) and labels
        google_unique_queries = list(dict.fromkeys([g.get('query') for g in google_results if g.get('query')]))
        google_query_to_num = {q: i + 1 for i, q in enumerate(google_unique_queries)}
        for g in google_results:
            q_text = g.get('query') or ''
            q_num = google_query_to_num.get(q_text, '?')
            g['query_label'] = f"Q{q_num}" if q_num != '?' else 'Q?'

        # Build Google URL norms for this run (for Google-only tagging on left panel)
        google_url_norms = set()
        for g in google_results:
            gu = (g.get('url') or '').lower().replace('https://', '').replace('http://', '').replace('www.', '').split('?')[0].rstrip('/')
            if gu:
                google_url_norms.add(gu)

        # Add in_google flag to Bing results
        for b in bing_results:
            b_url_norm = (b.get('url_normalized') or '').lower()
            b['in_google'] = b_url_norm in google_url_norms

        # Get unique queries for this run to power the checkboxes
        # preserve order of appearance (matches how queries were executed)
        unique_queries = list(dict.fromkeys([b['query'] for b in bing_results if b.get('query')]))

        # Map query text to Q1/Q2 number using this preserved order
        query_to_num = {q: i + 1 for i, q in enumerate(unique_queries)}
        for cit in cit_db:
            if cit.get('bing_query'):
                cit['bing_query_num'] = query_to_num.get(cit['bing_query'], '?')

        # For each URL, track all query numbers where it appeared (to detect Q1+Q2 "double overlap")
        url_norm_to_qnums = {}
        for b in bing_results:
            un = b.get('url_normalized')
            q = b.get('query')
            if not un or not q:
                continue
            qn = query_to_num.get(q)
            if not qn:
                continue
            url_norm_to_qnums.setdefault(un, set()).add(qn)

        double_overlap_cited = 0
        for cit in cit_db:
            qnums = sorted(list(url_norm_to_qnums.get(cit.get('url_normalized'), set())))
            cit['bing_query_nums'] = qnums
            if qnums:
                cit['bing_query_nums_str'] = ''.join([f"Q{n}" if i == 0 else f"+Q{n}" for i, n in enumerate(qnums)])
            else:
                cit['bing_query_nums_str'] = ''

            cit['double_overlap'] = (1 in qnums and 2 in qnums)
            if cit.get('citation_type') == 'cited' and cit['double_overlap']:
                double_overlap_cited += 1

            # Google-only tag: found in Google results but not in Bing
            url_norm = (cit.get('url_normalized') or '').lower()
            cit['in_google'] = url_norm in google_url_norms
            cit['google_only'] = cit['in_google'] and not cit.get('bing_rank')

        if run_raw is not None:
            run_raw['double_overlap_cited'] = double_overlap_cited

        # ---- Per-run Bing overlap (overall + by hidden query) ----
        if run_raw is not None:
            cited_norms = set(
                c.get('url_normalized')
                for c in cit_db
                if c.get('citation_type') == 'cited' and c.get('url_normalized')
            )
            total_cited = len(cited_norms)
            all_bing_norms = set(b.get('url_normalized') for b in bing_results if b.get('url_normalized'))
            overall_matched = len(cited_norms & all_bing_norms) if total_cited else 0
            overall_pct = (overall_matched / total_cited * 100.0) if total_cited else 0.0

            by_query = []
            for q in unique_queries:
                q_norms = set(
                    b.get('url_normalized')
                    for b in bing_results
                    if b.get('query') == q and b.get('url_normalized')
                )
                matched = len(cited_norms & q_norms) if total_cited else 0
                pct = (matched / total_cited * 100.0) if total_cited else 0.0
                by_query.append({
                    'q_num': query_to_num.get(q, '?'),
                    'query': q,
                    'matched': matched,
                    'total_cited': total_cited,
                    'pct': pct
                })

            run_raw['bing_overlap'] = {
                'overall_matched': overall_matched,
                'total_cited': total_cited,
                'overall_pct': overall_pct,
                'by_query': by_query
            }

            # ---- Per-run Google coverage ----
            # Note: "Google coverage" means "found in Google" (regardless of Bing).
            # We also track "Google-only (not in Bing)" separately.
            google_matched = len(cited_norms & google_url_norms) if total_cited else 0
            google_pct = (google_matched / total_cited * 100.0) if total_cited else 0.0
            google_only_not_bing = len((cited_norms & google_url_norms) - all_bing_norms) if total_cited else 0
            google_only_not_bing_pct = (google_only_not_bing / total_cited * 100.0) if total_cited else 0.0
            combined_matched = len(cited_norms & (all_bing_norms | google_url_norms)) if total_cited else 0
            combined_pct = (combined_matched / total_cited * 100.0) if total_cited else 0.0
            missing = (total_cited - combined_matched) if total_cited else 0
            missing_pct = (missing / total_cited * 100.0) if total_cited else 0.0

            run_raw['google_coverage'] = {
                'google_matched': google_matched,
                'total_cited': total_cited,
                'google_pct': google_pct,
                'google_only_not_bing': google_only_not_bing,
                'google_only_not_bing_pct': google_only_not_bing_pct,
                'combined_matched': combined_matched,
                'combined_pct': combined_pct,
                'missing': missing,
                'missing_pct': missing_pct,
            }


    return render_template_string(HTML_TEMPLATE, 
                                 run_ids=run_ids, 
                                 active_run_id=run_id,
                                 run_raw=run_raw,
                                 cit_db=cit_db,
                                 bing_results=bing_results,
                                 google_results=google_results,
                                 google_unique_queries=google_unique_queries,
                                 unique_queries=unique_queries if run_id else [],
                                 items_raw=items_raw,
                                 account_filter=account_filter)

@app.route('/dashboard')
def dashboard():
    db = get_db()
    
    match_sql = "EXISTS (SELECT 1 FROM bing_results b WHERE b.run_id = c.run_id AND b.url_normalized = c.url_normalized)"
    
    # ===== ENTERPRISE STATS =====
    ent_runs = db.execute("SELECT COUNT(*) FROM runs WHERE account_type = 'enterprise'").fetchone()[0]
    ent_bing = db.execute("SELECT COUNT(*) FROM bing_results WHERE account_type = 'enterprise'").fetchone()[0]
    
    ent_total_all = db.execute("SELECT COUNT(*) FROM citations WHERE account_type = 'enterprise'").fetchone()[0]
    ent_matched_all = db.execute(f"SELECT COUNT(DISTINCT c.id) FROM citations c WHERE account_type = 'enterprise' AND {match_sql}").fetchone()[0]
    
    ent_total_main = db.execute("SELECT COUNT(*) FROM citations WHERE account_type = 'enterprise' AND citation_type = 'cited'").fetchone()[0]
    ent_total_add = db.execute("SELECT COUNT(*) FROM citations WHERE account_type = 'enterprise' AND citation_type = 'additional'").fetchone()[0]
    ent_matched_main = db.execute(f"SELECT COUNT(DISTINCT c.id) FROM citations c WHERE account_type = 'enterprise' AND citation_type = 'cited' AND {match_sql}").fetchone()[0]
    ent_bing_overlap_pct = (ent_matched_main / ent_total_main * 100.0) if ent_total_main else 0.0
    
    ent_matched_add = db.execute(f"SELECT COUNT(DISTINCT c.id) FROM citations c WHERE account_type = 'enterprise' AND citation_type = 'additional' AND {match_sql}").fetchone()[0]
    ent_bing_add_overlap_pct = (ent_matched_add / ent_total_add * 100.0) if ent_total_add else 0.0

    # Enterprise Google overlap (control group; depends on whether enterprise Google SERP was collected+ingested)
    try:
        ent_google_matched_main = db.execute('''
            SELECT COUNT(DISTINCT c.id)
            FROM citations c
            WHERE c.account_type = 'enterprise' AND c.citation_type = 'cited' AND EXISTS (
                SELECT 1 FROM google_results g
                WHERE g.account_type = 'enterprise'
                  AND RTRIM(
                        LOWER(
                          REPLACE(
                            REPLACE(
                              REPLACE(
                                SUBSTR(g.url, 1, CASE WHEN INSTR(g.url, '?') > 0 THEN INSTR(g.url, '?') - 1 ELSE LENGTH(g.url) END),
                                'https://', ''
                              ),
                              'http://', ''
                            ),
                            'www.', ''
                          )
                        ),
                        '/'
                      ) = c.url_normalized
            )
        ''').fetchone()[0]
    except Exception:
        ent_google_matched_main = 0
    ent_google_overlap_pct = (ent_google_matched_main / ent_total_main * 100.0) if ent_total_main else 0.0

    try:
        ent_google_matched_add = db.execute('''
            SELECT COUNT(DISTINCT c.id)
            FROM citations c
            WHERE c.account_type = 'enterprise' AND c.citation_type = 'additional' AND EXISTS (
                SELECT 1 FROM google_results g
                WHERE g.account_type = 'enterprise'
                  AND RTRIM(
                        LOWER(
                          REPLACE(
                            REPLACE(
                              REPLACE(
                                SUBSTR(g.url, 1, CASE WHEN INSTR(g.url, '?') > 0 THEN INSTR(g.url, '?') - 1 ELSE LENGTH(g.url) END),
                                'https://', ''
                              ),
                              'http://', ''
                            ),
                            'www.', ''
                          )
                        ),
                        '/'
                      ) = c.url_normalized
            )
        ''').fetchone()[0]
    except Exception:
        ent_google_matched_add = 0
    ent_google_add_overlap_pct = (ent_google_matched_add / ent_total_add * 100.0) if ent_total_add else 0.0

    # Calculate "Rejected" (Level 3: In Bing but not in Cited or Additional)
    def _get_rejected_count(account_type: str):
        return db.execute(f'''
            SELECT COUNT(*) FROM (
                SELECT DISTINCT b.run_id, b.url_normalized 
                FROM bing_results b
                WHERE b.account_type = ?
                EXCEPT
                SELECT DISTINCT c.run_id, c.url_normalized
                FROM citations c
                WHERE c.account_type = ?
            )
        ''', (account_type, account_type)).fetchone()[0]

    ent_total_rejected = _get_rejected_count('enterprise')
    
    ent_invisible = db.execute('''
        SELECT domain, COUNT(*) as count
        FROM citations c
        WHERE account_type = 'enterprise' AND NOT EXISTS (
            SELECT 1 FROM bing_results b WHERE b.run_id = c.run_id AND b.url_normalized = c.url_normalized
        )
        GROUP BY domain ORDER BY count DESC LIMIT 15
    ''').fetchall()
    
    ent_page_data = db.execute('''
        SELECT b.page_num, COUNT(DISTINCT c.id) as match_count
        FROM bing_results b
        JOIN citations c ON c.url_normalized = b.url_normalized AND c.run_id = b.run_id
        WHERE b.page_num IS NOT NULL AND b.account_type = 'enterprise'
        GROUP BY b.page_num ORDER BY b.page_num
    ''').fetchall()

    def _aggregate_q_overlap(account_type: str):
        """Aggregate Q1/Q2 overlap across runs using Bing query order (min bing_results.id per query)."""
        run_ids = [r[0] for r in db.execute("SELECT run_id FROM runs WHERE account_type = ?", (account_type,)).fetchall()]
        total_cited_urls = 0
        q1_matched = 0
        q2_matched = 0

        for rid in run_ids:
            cited_norms = set(
                r[0]
                for r in db.execute(
                    "SELECT DISTINCT url_normalized FROM citations WHERE run_id = ? AND citation_type = 'cited' AND url_normalized != ''",
                    (rid,),
                ).fetchall()
            )
            if not cited_norms:
                continue

            # Determine query order for this run via insertion order in bing_results
            q_rows = db.execute(
                "SELECT query, MIN(id) as min_id FROM bing_results WHERE run_id = ? AND query IS NOT NULL GROUP BY query ORDER BY min_id",
                (rid,),
            ).fetchall()
            queries = [qr[0] for qr in q_rows if qr[0]]
            if not queries:
                continue

            q1_query = queries[0] if len(queries) >= 1 else None
            q2_query = queries[1] if len(queries) >= 2 else None

            q1_norms = set(
                r[0]
                for r in db.execute(
                    "SELECT DISTINCT url_normalized FROM bing_results WHERE run_id = ? AND query = ? AND url_normalized != ''",
                    (rid, q1_query),
                ).fetchall()
            ) if q1_query else set()
            q2_norms = set(
                r[0]
                for r in db.execute(
                    "SELECT DISTINCT url_normalized FROM bing_results WHERE run_id = ? AND query = ? AND url_normalized != ''",
                    (rid, q2_query),
                ).fetchall()
            ) if q2_query else set()

            total_cited_urls += len(cited_norms)
            if q1_norms:
                q1_matched += len(cited_norms & q1_norms)
            if q2_norms:
                q2_matched += len(cited_norms & q2_norms)

        q1_pct = (q1_matched / total_cited_urls * 100.0) if total_cited_urls else 0.0
        q2_pct = (q2_matched / total_cited_urls * 100.0) if total_cited_urls else 0.0
        return total_cited_urls, q1_matched, q2_matched, q1_pct, q2_pct

    ent_total_cited_urls, ent_q1_matched, ent_q2_matched, ent_q1_overlap_pct, ent_q2_overlap_pct = _aggregate_q_overlap('enterprise')
    
    # ===== PERSONAL STATS =====
    pers_runs = db.execute("SELECT COUNT(*) FROM runs WHERE account_type = 'personal'").fetchone()[0]
    pers_bing = db.execute("SELECT COUNT(*) FROM bing_results WHERE account_type = 'personal'").fetchone()[0]
    
    pers_total_all = db.execute("SELECT COUNT(*) FROM citations WHERE account_type = 'personal'").fetchone()[0]
    pers_matched_all = db.execute(f"SELECT COUNT(DISTINCT c.id) FROM citations c WHERE account_type = 'personal' AND {match_sql}").fetchone()[0]
    
    pers_total_main = db.execute("SELECT COUNT(*) FROM citations WHERE account_type = 'personal' AND citation_type = 'cited'").fetchone()[0]
    pers_total_add = db.execute("SELECT COUNT(*) FROM citations WHERE account_type = 'personal' AND citation_type = 'additional'").fetchone()[0]
    pers_total_rejected = _get_rejected_count('personal')
    pers_matched_main = db.execute(f"SELECT COUNT(DISTINCT c.id) FROM citations c WHERE account_type = 'personal' AND citation_type = 'cited' AND {match_sql}").fetchone()[0]
    pers_bing_overlap_pct = (pers_matched_main / pers_total_main * 100.0) if pers_total_main else 0.0
    
    pers_matched_add = db.execute(f"SELECT COUNT(DISTINCT c.id) FROM citations c WHERE account_type = 'personal' AND citation_type = 'additional' AND {match_sql}").fetchone()[0]
    pers_bing_add_overlap_pct = (pers_matched_add / pers_total_add * 100.0) if pers_total_add else 0.0

    # Personal Google overlap (cited URLs found in Google results)
    pers_google_matched_main = 0
    try:
        pers_google_matched_main = db.execute('''
            SELECT COUNT(DISTINCT c.id)
            FROM citations c
            WHERE c.account_type = 'personal' AND c.citation_type = 'cited' AND EXISTS (
                SELECT 1 FROM google_results g
                WHERE g.account_type = 'personal'
                  AND RTRIM(
                        LOWER(
                          REPLACE(
                            REPLACE(
                              REPLACE(
                                SUBSTR(g.url, 1, CASE WHEN INSTR(g.url, '?') > 0 THEN INSTR(g.url, '?') - 1 ELSE LENGTH(g.url) END),
                                'https://', ''
                              ),
                              'http://', ''
                            ),
                            'www.', ''
                          )
                        ),
                        '/'
                      ) = c.url_normalized
            )
        ''').fetchone()[0]
    except Exception:
        pers_google_matched_main = 0
    pers_google_overlap_pct = (pers_google_matched_main / pers_total_main * 100.0) if pers_total_main else 0.0

    # Personal Google overlap (additional URLs found in Google results)
    pers_google_matched_add = 0
    try:
        pers_google_matched_add = db.execute('''
            SELECT COUNT(DISTINCT c.id)
            FROM citations c
            WHERE c.account_type = 'personal' AND c.citation_type = 'additional' AND EXISTS (
                SELECT 1 FROM google_results g
                WHERE g.account_type = 'personal'
                  AND RTRIM(
                        LOWER(
                          REPLACE(
                            REPLACE(
                              REPLACE(
                                SUBSTR(g.url, 1, CASE WHEN INSTR(g.url, '?') > 0 THEN INSTR(g.url, '?') - 1 ELSE LENGTH(g.url) END),
                                'https://', ''
                              ),
                              'http://', ''
                            ),
                            'www.', ''
                          )
                        ),
                        '/'
                      ) = c.url_normalized
            )
        ''').fetchone()[0]
    except Exception:
        pers_google_matched_add = 0
    pers_google_add_overlap_pct = (pers_google_matched_add / pers_total_add * 100.0) if pers_total_add else 0.0

    # Personal combined coverage (Bing OR Google) and Google-only
    try:
        pers_combined_matched_main = db.execute('''
            SELECT COUNT(DISTINCT c.id)
            FROM citations c
            WHERE c.account_type = 'personal' AND c.citation_type = 'cited'
              AND (
                EXISTS (SELECT 1 FROM bing_results b WHERE b.run_id = c.run_id AND b.url_normalized = c.url_normalized)
                OR EXISTS (
                    SELECT 1 FROM google_results g
                    WHERE g.account_type = 'personal'
                      AND RTRIM(
                            LOWER(
                              REPLACE(
                                REPLACE(
                                  REPLACE(
                                    SUBSTR(g.url, 1, CASE WHEN INSTR(g.url, '?') > 0 THEN INSTR(g.url, '?') - 1 ELSE LENGTH(g.url) END),
                                    'https://', ''
                                  ),
                                  'http://', ''
                                ),
                                'www.', ''
                              )
                            ),
                            '/'
                          ) = c.url_normalized
                )
              )
        ''').fetchone()[0]
    except Exception:
        pers_combined_matched_main = 0
    pers_combined_overlap_pct = (pers_combined_matched_main / pers_total_main * 100.0) if pers_total_main else 0.0
    pers_missing_overlap_pct = 100.0 - pers_combined_overlap_pct if pers_total_main else 0.0

    try:
        pers_google_only_matched_main = db.execute('''
            SELECT COUNT(DISTINCT c.id)
            FROM citations c
            WHERE c.account_type = 'personal' AND c.citation_type = 'cited'
              AND NOT EXISTS (SELECT 1 FROM bing_results b WHERE b.run_id = c.run_id AND b.url_normalized = c.url_normalized)
              AND EXISTS (
                    SELECT 1 FROM google_results g
                    WHERE g.account_type = 'personal'
                      AND RTRIM(
                            LOWER(
                              REPLACE(
                                REPLACE(
                                  REPLACE(
                                    SUBSTR(g.url, 1, CASE WHEN INSTR(g.url, '?') > 0 THEN INSTR(g.url, '?') - 1 ELSE LENGTH(g.url) END),
                                    'https://', ''
                                  ),
                                  'http://', ''
                                ),
                                'www.', ''
                              )
                            ),
                            '/'
                          ) = c.url_normalized
              )
        ''').fetchone()[0]
    except Exception:
        pers_google_only_matched_main = 0
    pers_google_only_overlap_pct = (pers_google_only_matched_main / pers_total_main * 100.0) if pers_total_main else 0.0

    # ===== OVERALL (ALL ACCOUNTS) CITED COVERAGE =====
    total_cited_all = db.execute("SELECT COUNT(*) FROM citations WHERE citation_type = 'cited'").fetchone()[0]
    # Bing coverage across all cited (enterprise + personal)
    all_bing_matched_cited = db.execute(f"""
        SELECT COUNT(DISTINCT c.id)
        FROM citations c
        WHERE c.citation_type = 'cited' AND {match_sql}
    """).fetchone()[0]
    all_bing_cited_pct = (all_bing_matched_cited / total_cited_all * 100.0) if total_cited_all else 0.0

    # Combined coverage for ALL cited: (Bing) OR (Google for personal)
    try:
        all_combined_matched_cited = db.execute('''
            SELECT COUNT(DISTINCT c.id)
            FROM citations c
            WHERE c.citation_type = 'cited'
              AND (
                EXISTS (SELECT 1 FROM bing_results b WHERE b.run_id = c.run_id AND b.url_normalized = c.url_normalized)
                OR (
                    c.account_type = 'personal'
                    AND EXISTS (
                        SELECT 1 FROM google_results g
                        WHERE g.account_type = 'personal'
                          AND RTRIM(
                                LOWER(
                                  REPLACE(
                                    REPLACE(
                                      REPLACE(
                                        SUBSTR(g.url, 1, CASE WHEN INSTR(g.url, '?') > 0 THEN INSTR(g.url, '?') - 1 ELSE LENGTH(g.url) END),
                                        'https://', ''
                                      ),
                                      'http://', ''
                                    ),
                                    'www.', ''
                                  )
                                ),
                                '/'
                              ) = c.url_normalized
                    )
                )
              )
        ''').fetchone()[0]
    except Exception:
        all_combined_matched_cited = 0
    all_combined_cited_pct = (all_combined_matched_cited / total_cited_all * 100.0) if total_cited_all else 0.0
    all_missing_cited_pct = 100.0 - all_combined_cited_pct if total_cited_all else 0.0
    
    total_unique_domains = db.execute("SELECT COUNT(DISTINCT domain) FROM citations WHERE domain != ''").fetchone()[0]
    total_rejected_global = ent_total_rejected + pers_total_rejected

    pers_invisible = db.execute('''
        SELECT domain, COUNT(*) as count
        FROM citations c
        WHERE account_type = 'personal' AND NOT EXISTS (
            SELECT 1 FROM bing_results b WHERE b.run_id = c.run_id AND b.url_normalized = c.url_normalized
        )
        GROUP BY domain ORDER BY count DESC LIMIT 15
    ''').fetchall()
    
    pers_page_data = db.execute('''
        SELECT b.page_num, COUNT(DISTINCT c.id) as match_count
        FROM bing_results b
        JOIN citations c ON c.url_normalized = b.url_normalized AND c.run_id = b.run_id
        WHERE b.page_num IS NOT NULL AND b.account_type = 'personal'
        GROUP BY b.page_num ORDER BY b.page_num
    ''').fetchall()

    pers_total_cited_urls, pers_q1_matched, pers_q2_matched, pers_q1_overlap_pct, pers_q2_overlap_pct = _aggregate_q_overlap('personal')

    return render_template_string(DASHBOARD_TEMPLATE, 
                                 ent_runs=ent_runs, ent_bing=ent_bing,
                                 ent_total_all=ent_total_all, ent_matched_all=ent_matched_all,
                                 ent_total_main=ent_total_main, ent_total_add=ent_total_add,
                                 ent_total_rejected=ent_total_rejected,
                                 ent_matched_main=ent_matched_main,
                                 ent_bing_overlap_pct=ent_bing_overlap_pct,
                                 ent_bing_add_overlap_pct=ent_bing_add_overlap_pct,
                                 ent_google_overlap_pct=ent_google_overlap_pct,
                                 ent_google_add_overlap_pct=ent_google_add_overlap_pct,
                                 ent_invisible=ent_invisible, ent_page_data=ent_page_data,
                                 ent_total_cited_urls=ent_total_cited_urls,
                                 ent_q1_matched=ent_q1_matched, ent_q2_matched=ent_q2_matched,
                                 ent_q1_overlap_pct=ent_q1_overlap_pct, ent_q2_overlap_pct=ent_q2_overlap_pct,
                                 pers_runs=pers_runs, pers_bing=pers_bing,
                                 pers_total_all=pers_total_all, pers_matched_all=pers_matched_all,
                                 pers_total_main=pers_total_main, pers_total_add=pers_total_add,
                                 pers_total_rejected=pers_total_rejected,
                                 pers_matched_main=pers_matched_main,
                                 pers_bing_overlap_pct=pers_bing_overlap_pct,
                                 pers_bing_add_overlap_pct=pers_bing_add_overlap_pct,
                                 pers_google_overlap_pct=pers_google_overlap_pct,
                                 pers_google_add_overlap_pct=pers_google_add_overlap_pct,
                                 pers_combined_overlap_pct=pers_combined_overlap_pct,
                                 pers_missing_overlap_pct=pers_missing_overlap_pct,
                                 pers_google_only_overlap_pct=pers_google_only_overlap_pct,
                                 total_cited_all=total_cited_all,
                                 all_bing_cited_pct=all_bing_cited_pct,
                                 all_combined_cited_pct=all_combined_cited_pct,
                                 all_missing_cited_pct=all_missing_cited_pct,
                                 total_unique_domains=total_unique_domains,
                                 total_rejected_global=total_rejected_global,
                                 pers_invisible=pers_invisible, pers_page_data=pers_page_data,
                                 pers_total_cited_urls=pers_total_cited_urls,
                                 pers_q1_matched=pers_q1_matched, pers_q2_matched=pers_q2_matched,
                                 pers_q1_overlap_pct=pers_q1_overlap_pct, pers_q2_overlap_pct=pers_q2_overlap_pct)

@app.route('/domains')
def domain_explorer():
    db = get_db()
    
    # Get filters from query params
    search_query = request.args.get('search', '').strip().lower()
    account_filter = request.args.get('account', 'all')
    type_filter = request.args.get('type', 'all')
    visibility_filter = request.args.get('visibility', 'all')
    source_filter = request.args.get('source', 'all')
    drilldown = request.args.get('drilldown', '0') == '1'
    
    # Build Google URL sets (normalized) for quick lookup, split by account_type
    google_urls_by_account = {'personal': set(), 'enterprise': set()}
    try:
        google_rows = db.execute("SELECT DISTINCT account_type, url FROM google_results WHERE url IS NOT NULL").fetchall()
        for row in google_rows:
            acc = row[0] or 'personal'
            url = row[1]
            if url and acc in google_urls_by_account:
                url_norm = url.lower().replace('https://', '').replace('http://', '').replace('www.', '').split('?')[0].rstrip('/')
                if url_norm:
                    google_urls_by_account[acc].add(url_norm)
    except:
        pass  # google_results table might not exist yet
    
    # Build domain aggregation query
    domain_data = {}
    
    # Get all citations with their Bing match status
    citations = db.execute('''
        SELECT c.domain, c.account_type, c.citation_type, c.url, c.title, c.run_id, c.url_normalized,
               EXISTS(SELECT 1 FROM bing_results b WHERE b.run_id = c.run_id AND b.url_normalized = c.url_normalized) as in_bing
        FROM citations c
        WHERE c.domain IS NOT NULL AND c.domain != ''
    ''').fetchall()
    
    # Stats counters
    google_only_count = 0
    bing_only_count = 0
    neither_count = 0
    both_count = 0
    
    for row in citations:
        domain, account, ctype, url, title, run_id, url_normalized, in_bing = row
        domain_lower = domain.lower()
        
        # Check if URL is in Google results
        url_norm_check = (url_normalized or '').lower()
        acc = row['account_type']
        in_google = url_norm_check in google_urls_by_account.get(acc, set())
        
        # Apply filters
        if search_query and search_query not in domain_lower:
            continue
        if account_filter != 'all' and account != account_filter:
            continue
        if type_filter != 'all' and ctype != type_filter:
            continue
        if visibility_filter == 'invisible' and in_bing:
            continue
        if visibility_filter == 'visible' and not in_bing:
            continue
        
        # Source filter
        if source_filter == 'google_only' and not (in_google and not in_bing):
            continue
        if source_filter == 'bing_only' and not (in_bing and not in_google):
            continue
        if source_filter == 'both' and not (in_bing and in_google):
            continue
        if source_filter == 'neither' and not (not in_bing and not in_google):
            continue
        
        if domain not in domain_data:
            domain_data[domain] = {
                'domain': domain,
                'ent_cited': 0, 'ent_additional': 0,
                'pers_cited': 0, 'pers_additional': 0,
                'total': 0,
                'in_bing': False,
                'in_google': False,
                'urls': []
            }
        
        d = domain_data[domain]
        d['total'] += 1
        
        # Track if any URL from this domain is in Bing or Google
        if in_bing:
            d['in_bing'] = True
        if in_google:
            d['in_google'] = True
        
        if account == 'enterprise':
            if ctype == 'cited':
                d['ent_cited'] += 1
            else:
                d['ent_additional'] += 1
        else:
            if ctype == 'cited':
                d['pers_cited'] += 1
            else:
                d['pers_additional'] += 1
        
        # Parse run_id to get prompt_id and run_number
        parts = run_id.split('_') if run_id else ['', '']
        prompt_id = parts[0] if len(parts) > 0 else ''
        run_number = parts[1] if len(parts) > 1 else ''
        
        d['urls'].append({
            'url': url,
            'title': title,
            'account_type': account,
            'citation_type': ctype,
            'run_id': run_id,
            'prompt_id': prompt_id,
            'run_number': run_number,
            'in_bing': in_bing,
            'in_google': in_google
        })
    
    # Sort by total count
    domains = sorted(domain_data.values(), key=lambda x: x['total'], reverse=True)
    
    # Calculate stats (across ALL domains, not just filtered)
    total_domains = len(domains)
    total_citations = sum(d['total'] for d in domains)
    
    # Count unique URLs by source coverage
    for d in domains:
        for u in d['urls']:
            if u['in_google'] and not u['in_bing']:
                google_only_count += 1
            elif u['in_bing'] and not u['in_google']:
                bing_only_count += 1
            elif u['in_bing'] and u['in_google']:
                both_count += 1
            else:
                neither_count += 1
    
    # Drilldown data
    drilldown_domain = None
    drilldown_urls = []
    if drilldown and search_query and len(domains) == 1:
        drilldown_domain = domains[0]['domain']
        drilldown_urls = domains[0]['urls']
    
    # Limit to top 100 for display
    domains = domains[:100]
    
    return render_template_string(DOMAIN_EXPLORER_TEMPLATE,
                                 domains=domains,
                                 search_query=search_query,
                                 account_filter=account_filter,
                                 type_filter=type_filter,
                                 visibility_filter=visibility_filter,
                                 source_filter=source_filter,
                                 total_domains=total_domains,
                                 total_citations=total_citations,
                                 google_only_count=google_only_count,
                                 bing_only_count=bing_only_count,
                                 neither_count=neither_count,
                                 drilldown_domain=drilldown_domain,
                                 drilldown_urls=drilldown_urls)


# =========================
# Truly Invisible (Bing+Google absent) - Personal only
# =========================
INVISIBLE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <title>Truly Invisible - GEO Research</title>
  <style>
    body { font-family: -apple-system, sans-serif; background: #f4f4f9; margin: 0; padding: 20px; }
    .nav { margin-bottom: 18px; }
    .nav a { margin-right: 12px; text-decoration: none; color: #111; font-weight: 600; }
    .card { background: white; padding: 16px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
    table { width: 100%; border-collapse: collapse; }
    th, td { text-align: left; padding: 8px; border-bottom: 1px solid #eee; font-size: 12px; }
    th { font-size: 11px; color: #555; }
    .pill { display:inline-block; padding:2px 8px; border-radius: 999px; font-size: 11px; font-weight: 700; }
    .pill-red { background:#fee2e2; color:#991b1b; }
    .pill-gray { background:#f3f4f6; color:#374151; }
    .filters { display:flex; gap:10px; flex-wrap: wrap; margin: 10px 0 16px; }
    select { padding: 6px 8px; border-radius: 8px; border: 1px solid #ddd; }
    .muted { color:#666; font-size: 12px; }
  </style>
</head>
<body>
  <div class="nav">
    <a href="/">← Run Viewer</a>
    <a href="/dashboard">📊 Dashboard</a>
    <a href="/domains">🔍 Domain Explorer</a>
    <a href="/invisible" style="color:#ef4444;">🕳️ Truly Invisible</a>
  </div>

  <h1 style="margin: 0 0 6px;">🕳️ Invisible Links (by engine)</h1>
  <div class="muted">Filters are evaluated per-run using that run’s Bing results and (if collected) Google SERP for the same account type.</div>

  <div class="card" style="margin-top:14px;">
    <form method="get" class="filters">
      <label class="muted">
        Account:
        <select name="account" onchange="this.form.submit()">
          <option value="personal" {{ 'selected' if account_filter=='personal' else '' }}>Personal</option>
          <option value="enterprise" {{ 'selected' if account_filter=='enterprise' else '' }}>Enterprise</option>
          <option value="all" {{ 'selected' if account_filter=='all' else '' }}>All</option>
        </select>
      </label>
      <label class="muted">
        Type:
        <select name="type" onchange="this.form.submit()">
          <option value="cited" {{ 'selected' if type_filter=='cited' else '' }}>Cited</option>
          <option value="additional" {{ 'selected' if type_filter=='additional' else '' }}>Additional</option>
          <option value="all" {{ 'selected' if type_filter=='all' else '' }}>Cited + Additional</option>
        </select>
      </label>
      <label class="muted">
        Invisible on:
        <select name="vis" onchange="this.form.submit()">
          <option value="both" {{ 'selected' if vis_filter=='both' else '' }}>Bing + Google</option>
          <option value="bing" {{ 'selected' if vis_filter=='bing' else '' }}>Bing</option>
          <option value="google" {{ 'selected' if vis_filter=='google' else '' }}>Google</option>
        </select>
      </label>
      <label class="muted">
        Group by:
        <select name="group" onchange="this.form.submit()">
          <option value="url" {{ 'selected' if group_by=='url' else '' }}>URL</option>
          <option value="domain" {{ 'selected' if group_by=='domain' else '' }}>Domain</option>
        </select>
      </label>
      <label class="muted">
        Limit:
        <select name="limit" onchange="this.form.submit()">
          <option value="100" {{ 'selected' if limit==100 else '' }}>100</option>
          <option value="250" {{ 'selected' if limit==250 else '' }}>250</option>
          <option value="500" {{ 'selected' if limit==500 else '' }}>500</option>
          <option value="1000" {{ 'selected' if limit==1000 else '' }}>1000</option>
        </select>
      </label>
    </form>

    {% if vis_filter in ['google','both'] and google_data_count == 0 %}
      <div style="background:#fff7ed; border:1px solid #fed7aa; color:#9a3412; padding:10px 12px; border-radius:10px; font-size:12px; margin: 6px 0 12px;">
        <strong>Note:</strong> No Google SERP data is currently ingested for <strong>{{ account_filter }}</strong>.
        “Invisible on Google” will be misleading until you collect+ingest Google results for that account.
      </div>
    {% endif %}

    <div style="display:flex; gap:14px; flex-wrap: wrap; margin: 8px 0 14px;">
      <div class="pill pill-red">Invisible: {{ invisible_count }}</div>
      <div class="pill pill-gray">Total {{ type_label }}: {{ total_count }}</div>
      <div class="pill pill-gray">Invisible %: {{ "%.1f"|format(invisible_pct) }}%</div>
    </div>

    {% if group_by == 'domain' %}
      <table>
        <thead>
          <tr><th>Domain</th><th>Count</th></tr>
        </thead>
        <tbody>
          {% for r in rows %}
          <tr>
            <td>{{ r['domain'] }}</td>
            <td>{{ r['cnt'] }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    {% else %}
      <table>
        <thead>
          <tr><th>Domain</th><th>URL</th><th>Runs</th></tr>
        </thead>
        <tbody>
          {% for r in rows %}
          <tr>
            <td>{{ r['domain'] }}</td>
            <td><a href="{{ r['url'] }}" target="_blank">{{ r['url'] }}</a></td>
            <td class="muted">{{ r['run_count'] }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    {% endif %}
  </div>
</body>
</html>
"""


@app.route('/invisible')
def invisible_links():
    db = get_db()
    account_filter = request.args.get('account', 'personal')
    type_filter = request.args.get('type', 'cited')
    vis_filter = request.args.get('vis', 'both')
    group_by = request.args.get('group', 'url')
    try:
        limit = int(request.args.get('limit', '250'))
    except Exception:
        limit = 250

    if type_filter not in ('cited', 'additional', 'all'):
        type_filter = 'cited'
    if account_filter not in ('personal', 'enterprise', 'all'):
        account_filter = 'personal'
    if vis_filter not in ('both', 'bing', 'google'):
        vis_filter = 'both'
    if group_by not in ('url', 'domain'):
        group_by = 'url'

    account_where = "c.account_type = ?" if account_filter != 'all' else "1=1"
    account_params = (account_filter,) if account_filter != 'all' else tuple()

    # Google data availability (for warnings / interpreting "invisible on Google")
    if account_filter == 'all':
        google_data_count = db.execute("SELECT COUNT(*) FROM google_results").fetchone()[0]
    else:
        google_data_count = db.execute(
            "SELECT COUNT(*) FROM google_results WHERE account_type = ?",
            (account_filter,),
        ).fetchone()[0]

    if type_filter == 'all':
        type_label = "Cited+Additional"
        total_count = db.execute(
            f"SELECT COUNT(*) FROM citations c WHERE {account_where} AND c.citation_type IN ('cited','additional')",
            account_params,
        ).fetchone()[0]
    else:
        type_label = type_filter.capitalize()
        total_count = db.execute(
            f"SELECT COUNT(*) FROM citations c WHERE {account_where} AND c.citation_type = ?",
            account_params + (type_filter,),
        ).fetchone()[0]

    url_eq_sql = """
      RTRIM(
        LOWER(
          REPLACE(
            REPLACE(
              REPLACE(
                SUBSTR(g.url, 1, CASE WHEN INSTR(g.url, '?') > 0 THEN INSTR(g.url, '?') - 1 ELSE LENGTH(g.url) END),
                'https://', ''
              ),
              'http://', ''
            ),
            'www.', ''
          )
        ),
        '/'
      ) = c.url_normalized
    """

    # Visibility predicate
    bing_pred = """
      NOT EXISTS (
        SELECT 1 FROM bing_results b
        WHERE b.run_id = c.run_id AND b.url_normalized = c.url_normalized
      )
    """
    google_pred = f"""
      NOT EXISTS (
        SELECT 1 FROM google_results g
        WHERE g.account_type = c.account_type
          AND g.chatgpt_run_id = REPLACE(c.run_id, '_personal', '')
          AND {url_eq_sql}
      )
    """
    if vis_filter == 'bing':
        vis_sql = bing_pred
    elif vis_filter == 'google':
        vis_sql = google_pred
    else:
        vis_sql = f"({bing_pred}) AND ({google_pred})"

    if group_by == 'domain':
        if type_filter == 'all':
            rows = db.execute(f'''
                SELECT c.domain as domain, COUNT(*) as cnt
                FROM citations c
                WHERE {account_where}
                  AND c.citation_type IN ('cited','additional')
                  AND {vis_sql}
                  AND c.domain IS NOT NULL AND c.domain != ''
                GROUP BY c.domain
                ORDER BY cnt DESC
                LIMIT ?
            ''', account_params + (limit,)).fetchall()
        else:
            rows = db.execute(f'''
                SELECT c.domain as domain, COUNT(*) as cnt
                FROM citations c
                WHERE {account_where}
                  AND c.citation_type = ?
                  AND {vis_sql}
                  AND c.domain IS NOT NULL AND c.domain != ''
                GROUP BY c.domain
                ORDER BY cnt DESC
                LIMIT ?
            ''', account_params + (type_filter, limit)).fetchall()

        invisible_count = sum(int(r['cnt']) for r in rows) if rows else 0
        invisible_pct = (invisible_count / total_count * 100.0) if total_count else 0.0

    else:
        if type_filter == 'all':
            rows = db.execute(f'''
                SELECT c.domain as domain, c.url as url, COUNT(DISTINCT c.run_id) as run_count
                FROM citations c
                WHERE {account_where}
                  AND c.citation_type IN ('cited','additional')
                  AND {vis_sql}
                  AND c.url IS NOT NULL AND c.url != ''
                GROUP BY c.url
                ORDER BY run_count DESC
                LIMIT ?
            ''', account_params + (limit,)).fetchall()
            invisible_count = len(rows)
        else:
            rows = db.execute(f'''
                SELECT c.domain as domain, c.url as url, COUNT(DISTINCT c.run_id) as run_count
                FROM citations c
                WHERE {account_where}
                  AND c.citation_type = ?
                  AND {vis_sql}
                  AND c.url IS NOT NULL AND c.url != ''
                GROUP BY c.url
                ORDER BY run_count DESC
                LIMIT ?
            ''', account_params + (type_filter, limit)).fetchall()
            invisible_count = len(rows)

        invisible_pct = (invisible_count / total_count * 100.0) if total_count else 0.0

    return render_template_string(
        INVISIBLE_TEMPLATE,
        account_filter=account_filter,
        type_filter=type_filter,
        vis_filter=vis_filter,
        group_by=group_by,
        limit=limit,
        rows=rows,
        invisible_count=invisible_count,
        total_count=total_count,
        invisible_pct=invisible_pct,
        type_label=type_label,
        google_data_count=google_data_count,
    )

if __name__ == '__main__':
    app.run(debug=True, port=5000)

