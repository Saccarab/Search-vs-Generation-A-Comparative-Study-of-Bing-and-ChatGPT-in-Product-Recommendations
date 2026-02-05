import sqlite3
import pandas as pd
from flask import Flask, render_template_string, request, send_from_directory, abort
import json
import os
import html as html_module

DOMAIN_EXPLORER_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Domain Explorer - GEO Research</title>
    <style>
        body { font-family: -apple-system, sans-serif; background: #f4f4f9; margin: 0; padding: 20px; }
        
    .nav { 
        display: flex; 
        gap: 2px; 
        margin-bottom: 20px; 
        border-bottom: 1px solid #e5e7eb; 
        padding-bottom: 0;
    }
    .nav a { 
        text-decoration: none !important; 
        color: #6b7280 !important; 
        font-weight: 600 !important; 
        padding: 10px 20px !important; 
        border-radius: 8px 8px 0 0 !important;
        font-size: 14px !important;
        transition: all 0.2s !important;
        border: 1px solid transparent !important;
        border-bottom: none !important;
        margin-bottom: -1px !important;
        margin-right: 0 !important;
    }
    .nav a:hover { 
        background: #f3f4f6 !important; 
        color: #111827 !important; 
    }
    .nav a.active { 
        background: white !important; 
        color: #10a37f !important; 
        border-color: #e5e7eb !important;
        border-bottom: 1px solid white !important;
    }

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
        <a href="/" class="{{ 'active' if active_tab == 'viewer' else '' }}">🤖 Run Viewer</a>
        <a href="/dashboard" class="{{ 'active' if active_tab == 'dashboard' else '' }}">📊 Dashboard</a>
        <a href="/urls" class="{{ 'active' if active_tab == 'urls' else '' }}">🔗 URL Breakdown</a>
        <a href="/domains" class="{{ 'active' if active_tab == 'domains' else '' }}">🔍 Domain Explorer</a>
        <a href="/invisible" class="{{ 'active' if active_tab == 'invisible' else '' }}">🕳️ Truly Invisible</a>
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
            <option value="rejected" {{ 'selected' if type_filter == 'rejected' else '' }}>Rejected Only</option>
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
                {% if type_filter == 'rejected' %}
                <th>Ent. Rej.</th>
                {% else %}
                <th>Ent. Add.</th>
                {% endif %}
                <th>Pers. Cited</th>
                {% if type_filter == 'rejected' %}
                <th>Pers. Rej.</th>
                {% else %}
                <th>Pers. Add.</th>
                {% endif %}
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
                {% if type_filter == 'rejected' %}
                <td>{{ d.ent_rejected }}</td>
                {% else %}
                <td>{{ d.ent_additional }}</td>
                {% endif %}
                <td>{{ d.pers_cited }}</td>
                {% if type_filter == 'rejected' %}
                <td>{{ d.pers_rejected }}</td>
                {% else %}
                <td>{{ d.pers_additional }}</td>
                {% endif %}
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
        
    .nav { 
        display: flex; 
        gap: 2px; 
        margin-bottom: 20px; 
        border-bottom: 1px solid #e5e7eb; 
        padding-bottom: 0;
    }
    .nav a { 
        text-decoration: none !important; 
        color: #6b7280 !important; 
        font-weight: 600 !important; 
        padding: 10px 20px !important; 
        border-radius: 8px 8px 0 0 !important;
        font-size: 14px !important;
        transition: all 0.2s !important;
        border: 1px solid transparent !important;
        border-bottom: none !important;
        margin-bottom: -1px !important;
        margin-right: 0 !important;
    }
    .nav a:hover { 
        background: #f3f4f6 !important; 
        color: #111827 !important; 
    }
    .nav a.active { 
        background: white !important; 
        color: #10a37f !important; 
        border-color: #e5e7eb !important;
        border-bottom: 1px solid white !important;
    }

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
        <a href="/" class="{{ 'active' if active_tab == 'viewer' else '' }}">🤖 Run Viewer</a>
        <a href="/dashboard" class="{{ 'active' if active_tab == 'dashboard' else '' }}">📊 Dashboard</a>
        <a href="/urls" class="{{ 'active' if active_tab == 'urls' else '' }}">🔗 URL Breakdown</a>
        <a href="/domains" class="{{ 'active' if active_tab == 'domains' else '' }}">🔍 Domain Explorer</a>
        <a href="/invisible" class="{{ 'active' if active_tab == 'invisible' else '' }}">🕳️ Truly Invisible</a>
    </div>
    <div style="margin: 8px 0 18px; font-size: 12px;">
        <span class="stat-label" style="font-weight: bold;">Mode:</span>
        <a href="/dashboard" style="margin-left: 10px; text-decoration:none; color: {{ '#10a37f' if not enriched_only else '#64748b' }}; font-weight: bold;">All URLs</a>
        <a href="/dashboard?enriched=1" style="margin-left: 10px; text-decoration:none; color: {{ '#10a37f' if enriched_only else '#64748b' }}; font-weight: bold;">Enriched Only</a>
        <a href="/dashboard?labels=1" style="margin-left: 16px; text-decoration:none; color: {{ '#10a37f' if show_labels and not enriched_only else '#64748b' }}; font-weight: bold;">Show Labels</a>
    </div>
    {% if enriched_only %}
    <div class="card full-width" style="background: #fff7ed; border: 1px solid #fed7aa;">
        <div class="stat-label" style="font-weight: bold; color: #9a3412;">
            Enriched-only mode is ON. All counts below exclude URLs without LLM labels.
        </div>
    </div>
    {% endif %}
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

    {% if show_labels %}
    <div class="grid">
        <div class="card full-width">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                <h2 style="margin:0;">Enrichment Coverage & Label Distribution</h2>
                <form method="get" style="display:inline-flex; gap:8px; align-items:center;">
                    <input type="hidden" name="labels" value="1">
                    <label style="font-size:12px; color:#666;">Filter:</label>
                    <select name="breakdown_account" onchange="this.form.submit()" style="padding:4px 8px; border-radius:6px; border:1px solid #ddd; font-size:12px;">
                        <option value="all" {{ 'selected' if breakdown_account=='all' else '' }}>All Accounts</option>
                        <option value="enterprise" {{ 'selected' if breakdown_account=='enterprise' else '' }}>Enterprise</option>
                        <option value="personal" {{ 'selected' if breakdown_account=='personal' else '' }}>Personal</option>
                    </select>
                </form>
            </div>
            <div style="display:flex; gap:20px; flex-wrap:wrap; margin-bottom:10px;">
                <div class="stat-label">
                    Enriched URLs: <strong>{{ enriched_citation_count }}</strong> / {{ enrichment_total_citations }}
                    ({{ "%.1f"|format(enrichment_pct) }}%)
                </div>
                <div class="stat-label">Unlabeled URLs: <strong>{{ unlabeled_citation_count }}</strong></div>
                {% if breakdown_account != 'all' %}
                <div class="stat-label" style="color:#f97316; font-weight:bold;">
                    Filtered: {{ breakdown_account|title }}
                </div>
                {% endif %}
            </div>
            <div class="grid" style="grid-template-columns: 1fr 1fr; margin-top: 10px;">
                <div>
                    <h2 style="font-size: 14px;">Type (Enriched)</h2>
                    <table>
                        <tr><th>Type</th><th>Count</th><th>%</th></tr>
                        {% for row in label_type_counts %}
                        <tr>
                            <td>{{ row.label }}</td>
                            <td>{{ row.count }}</td>
                            <td>{{ "%.1f"|format(row.pct) }}%</td>
                        </tr>
                        {% endfor %}
                    </table>
                </div>
                <div>
                    <h2 style="font-size: 14px;">Tone (Enriched)</h2>
                    <table>
                        <tr><th>Tone</th><th>Count</th><th>%</th></tr>
                        {% for row in label_tone_counts %}
                        <tr>
                            <td>{{ row.label }}</td>
                            <td>{{ row.count }}</td>
                            <td>{{ "%.1f"|format(row.pct) }}%</td>
                        </tr>
                        {% endfor %}
                    </table>
                </div>
            </div>
        </div>
    </div>

    <div class="grid">
        <div class="card full-width">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px; margin-bottom:10px; flex-wrap:wrap;">
                <div>
                    <h2 style="margin:0;">Selection Lift (Drift Analysis)</h2>
                    <div class="stat-sub" style="margin-top:6px;">
                        Percentage Point (PP) shift from search results to LLM selection. Positive = LLM "hunts" for this; Negative = LLM "avoids" this.
                    </div>
                </div>
                <form method="get" style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
                    <input type="hidden" name="labels" value="1">
                    <label style="font-size:12px; color:#666;">Account:</label>
                    <select name="breakdown_account" onchange="this.form.submit()" style="padding:4px 8px; border-radius:6px; border:1px solid #ddd; font-size:12px;">
                        <option value="all" {{ 'selected' if breakdown_account=='all' else '' }}>All</option>
                        <option value="enterprise" {{ 'selected' if breakdown_account=='enterprise' else '' }}>Enterprise</option>
                        <option value="personal" {{ 'selected' if breakdown_account=='personal' else '' }}>Personal</option>
                    </select>
                </form>
            </div>

            <table class="data-table">
                <thead>
                    <tr>
                        <th>Feature</th>
                        <th style="text-align:center;">Inline (Cited) Lift</th>
                        <th style="text-align:center;">Sidebar (Additional) Lift</th>
                        <th>Behavioral Interpretation</th>
                    </tr>
                </thead>
                <tbody>
                    {% set lift_map = {
                        'all': {
                            'content_format:landing_page': {'inline': 0.7, 'sidebar': -18.4},
                            'content_format:best_of_list': {'inline': -10.5, 'sidebar': 8.9},
                            'has_tables:1': {'inline': -0.8, 'sidebar': 5.6},
                            'has_authorship:1': {'inline': -4.3, 'sidebar': 8.3},
                            'has_pros_cons:1': {'inline': -5.5, 'sidebar': 5.2},
                            'has_bullet_points:1': {'inline': -11.8, 'sidebar': -6.5}
                        },
                        'enterprise': {
                            'content_format:landing_page': {'inline': -1.3, 'sidebar': -19.3},
                            'content_format:best_of_list': {'inline': -4.8, 'sidebar': 20.5},
                            'has_tables:1': {'inline': 1.8, 'sidebar': 9.6},
                            'has_authorship:1': {'inline': 0.8, 'sidebar': 14.0},
                            'has_pros_cons:1': {'inline': -2.1, 'sidebar': 10.4},
                            'has_bullet_points:1': {'inline': -8.2, 'sidebar': 3.7}
                        },
                        'personal': {
                            'content_format:landing_page': {'inline': 2.4, 'sidebar': -17.8},
                            'content_format:best_of_list': {'inline': -15.7, 'sidebar': 1.5},
                            'has_tables:1': {'inline': -3.1, 'sidebar': 2.9},
                            'has_authorship:1': {'inline': -8.9, 'sidebar': 4.7},
                            'has_pros_cons:1': {'inline': -8.5, 'sidebar': 1.9},
                            'has_bullet_points:1': {'inline': -15.1, 'sidebar': -13.0}
                        }
                    } %}
                    
                    {% set lift_data = [
                        {'feat': 'content_format:landing_page', 'label': 'Direct Product Pages', 'desc': 'Preference for primary sources'},
                        {'feat': 'content_format:best_of_list', 'label': 'Best-of Listicles', 'desc': 'Avoidance of aggregators inline'},
                        {'feat': 'has_tables:1', 'label': 'Structured Tables', 'desc': 'Data density preference'},
                        {'feat': 'has_authorship:1', 'label': 'Clear Authorship', 'desc': 'Editorial authority signal'},
                        {'feat': 'has_pros_cons:1', 'label': 'Pros/Cons Sections', 'desc': 'Explicit evaluation signal'},
                        {'feat': 'has_bullet_points:1', 'label': 'High Readability', 'desc': 'Scannability preference'}
                    ] %}
                    
                    {% for item in lift_data %}
                        {% set current_lift = lift_map[breakdown_account][item.feat] %}
                        {% set inline_val = current_lift['inline'] %}
                        {% set sidebar_val = current_lift['sidebar'] %}
                        
                        <tr>
                            <td><strong>{{ item.label }}</strong></td>
                            <td style="text-align:center; font-weight:bold; color: {{ '#10a37f' if inline_val > 0 else '#ef4444' }};">
                                {{ '+' if inline_val > 0 }}{{ inline_val }}%
                            </td>
                            <td style="text-align:center; font-weight:bold; color: {{ '#10a37f' if sidebar_val > 0 else '#ef4444' }};">
                                {{ '+' if sidebar_val > 0 }}{{ sidebar_val }}%
                            </td>
                            <td class="stat-sub">{{ item.desc }}</td>
                        </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    {% endif %}

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
            <div style="background: #fff1f2; padding: 10px; border-radius: 8px; text-align: center; margin-bottom: 15px; border: 1px dashed #fecaca;">
                <div class="stat-label" style="font-weight: bold; color: #991b1b;">REJECTED OVERLAP: 
                    Bing {{ "%.1f"|format(ent_rejected_bing_overlap_pct) }}% | 
                    Google {{ "%.1f"|format(ent_rejected_google_overlap_pct) }}% (control)
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
            <div style="background: #fff1f2; padding: 10px; border-radius: 8px; text-align: center; margin-bottom: 15px; border: 1px dashed #fecaca;">
                <div class="stat-label" style="font-weight: bold; color: #991b1b;">REJECTED OVERLAP: 
                    Bing {{ "%.1f"|format(pers_rejected_bing_overlap_pct) }}% | 
                    Google {{ "%.1f"|format(pers_rejected_google_overlap_pct) }}%
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

    <div class="grid">
        <div class="card enterprise">
            <h2>Enterprise - Google Position Distribution</h2>
            <table>
                <tr><th>Bucket</th><th>Matches</th></tr>
                {% for row in ent_google_pos_data %}
                <tr><td>{{ row[0] }}</td><td>{{ row[1] }}</td></tr>
                {% endfor %}
            </table>
        </div>

        <div class="card personal">
            <h2>Personal - Google Position Distribution</h2>
            <table>
                <tr><th>Bucket</th><th>Matches</th></tr>
                {% for row in pers_google_pos_data %}
                <tr><td>{{ row[0] }}</td><td>{{ row[1] }}</td></tr>
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

        /* Mic toggle (looping background audio) */
        #mic-toggle {
            position: fixed;
            top: 14px;
            right: 14px;
            z-index: 9999;
            width: 42px;
            height: 42px;
            border-radius: 999px;
            border: 1px solid rgba(0,0,0,0.12);
            background: rgba(255,255,255,0.92);
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            box-shadow: 0 6px 18px rgba(0,0,0,0.12);
            user-select: none;
        }
        #mic-toggle:hover { filter: brightness(0.98); }
        #mic-toggle svg { width: 18px; height: 18px; }
        #mic-toggle .muted-slash {
            stroke: #ef4444;
            stroke-width: 2.5;
            stroke-linecap: round;
            display: none;
        }
        #mic-toggle.off .muted-slash { display: block; }

        #mic-status {
            position: fixed;
            top: 60px;
            right: 14px;
            z-index: 9999;
            max-width: 260px;
            padding: 8px 10px;
            border-radius: 10px;
            background: rgba(17,24,39,0.92);
            color: #fff;
            font-size: 11px;
            line-height: 1.35;
            display: none;
            box-shadow: 0 10px 24px rgba(0,0,0,0.18);
        }
    
    .nav { 
        display: flex; 
        gap: 2px; 
        margin-bottom: 20px; 
        border-bottom: 1px solid #e5e7eb; 
        padding-bottom: 0;
    }
    .nav a { 
        text-decoration: none !important; 
        color: #6b7280 !important; 
        font-weight: 600 !important; 
        padding: 10px 20px !important; 
        border-radius: 8px 8px 0 0 !important;
        font-size: 14px !important;
        transition: all 0.2s !important;
        border: 1px solid transparent !important;
        border-bottom: none !important;
        margin-bottom: -1px !important;
        margin-right: 0 !important;
    }
    .nav a:hover { 
        background: #f3f4f6 !important; 
        color: #111827 !important; 
    }
    .nav a.active { 
        background: white !important; 
        color: #10a37f !important; 
        border-color: #e5e7eb !important;
        border-bottom: 1px solid white !important;
    }

    </style>
</head>
<body>
    <!-- Looping audio (starts on user click due to browser autoplay policy) -->
    <audio id="bg-audio" src="/media/Sheer_Belly_Dancin_128k.mp3" loop preload="none"></audio>
    <div id="mic-toggle" class="off" title="Toggle background audio">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M12 14a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v5a3 3 0 0 0 3 3Z" stroke="#111827" stroke-width="1.6"/>
            <path d="M5 11a7 7 0 0 0 14 0" stroke="#111827" stroke-width="1.6" stroke-linecap="round"/>
            <path d="M12 18v3" stroke="#111827" stroke-width="1.6" stroke-linecap="round"/>
            <path d="M8.5 21h7" stroke="#111827" stroke-width="1.6" stroke-linecap="round"/>
            <path class="muted-slash" d="M6 6l12 12"/>
        </svg>
    </div>
    <div id="mic-status"></div>
    <div id="sidebar">
        <div style="margin-bottom: 20px; display: flex; flex-direction: column; gap: 8px;">
            <a href="/" style="text-decoration:none; color:white; font-weight:bold; background: #10a37f; padding: 10px; border-radius: 5px; text-align: center;">🤖 RUN VIEWER</a>
            <a href="/dashboard" style="text-decoration:none; color:white; font-weight:bold; background: #3b82f6; padding: 10px; border-radius: 5px; text-align: center;">📊 DASHBOARD</a>
            <a href="/urls" style="text-decoration:none; color:white; font-weight:bold; background: #0f766e; padding: 10px; border-radius: 5px; text-align: center;">🔗 URL BREAKDOWN</a>
            <a href="/domains" style="text-decoration:none; color:white; font-weight:bold; background: #6366f1; padding: 10px; border-radius: 5px; text-align: center;">🔍 DOMAIN EXPLORER</a>
            <a href="/invisible" style="text-decoration:none; color:white; font-weight:bold; background: #ef4444; padding: 10px; border-radius: 5px; text-align: center;">🕳️ TRULY INVISIBLE</a>
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
                <div style="margin-top: 8px; font-size: 11px;">
                    <strong>Raw details:</strong> ON
                </div>
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
                                        {% set m = namespace(bing_found=false, bing_rank=None, bing_q_num=None, google_found=false, google_rank=None, google_q_num=None) %}
                                        {% for cit in cit_db %}
                                            {% set cit_url_clean = (cit.url or '').replace('https://', '').replace('http://', '').replace('www.', '').split('?')[0].rstrip('/') %}
                                            {% if clean_url == cit_url_clean or clean_url in cit_url_clean or cit_url_clean in clean_url %}
                                                {% if cit.bing_rank %}
                                                    {% set m.bing_found = true %}
                                                    {% set m.bing_rank = cit.bing_rank %}
                                                    {% set m.bing_q_num = cit.bing_query_num %}
                                                {% endif %}
                                                {% if cit.google_rank %}
                                                    {% set m.google_found = true %}
                                                    {% set m.google_rank = cit.google_rank %}
                                                    {% set m.google_q_num = cit.google_query_num %}
                                                {% elif cit.in_google %}
                                                    {% set m.google_found = true %}
                                                    {% set m.google_rank = None %}
                                                    {% set m.google_q_num = cit.google_query_num %}
                                                {% endif %}
                                            {% endif %}
                                        {% endfor %}
                                        <a href="{{ link }}" target="_blank" style="font-size: 11px; background: {{ '#d1fae5' if m.bing_found else ('#fef3c7' if m.google_found else '#fee2e2') }}; color: {{ '#065f46' if m.bing_found else ('#92400e' if m.google_found else '#991b1b') }}; padding: 4px 10px; border-radius: 15px; text-decoration: none; display: inline-flex; align-items: center; gap: 4px;">
                                            {{ clean_url[:35] }}{% if clean_url|length > 35 %}...{% endif %}
                                            {% if m.bing_found %}
                                            <span style="background: #10a37f; color: white; padding: 1px 5px; border-radius: 8px; font-size: 9px; font-weight: bold;">
                                                #{{ m.bing_rank }} Q{{ m.bing_q_num }}
                                            </span>
                                            {% endif %}
                                            {% if m.google_found %}
                                            <span style="background:#f97316; color:white; padding:1px 5px; border-radius:8px; font-size:9px; font-weight:bold;">
                                                G{% if m.google_rank %}#{{ m.google_rank }}{% endif %}{% if m.google_q_num %} Q{{ m.google_q_num }}{% endif %}
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
                                        {% elif cit.google_rank %}
                                        <span style="font-weight: bold;">
                                            G#{{ cit.google_rank }}
                                            {% if cit.google_query_num %}Q{{ cit.google_query_num }}{% endif %}
                                        </span>
                                        {% elif cit.in_google %}
                                        <span style="font-weight: bold;">G</span>
                                        {% else %}
                                        <span style="font-weight: bold;">✗</span>
                                        {% endif %}
                                        {% if cit.google_rank and cit.bing_rank %}<span style="margin-left:4px; background:#f97316; color:white; padding:1px 5px; border-radius:8px; font-size:9px;">G#{{ cit.google_rank }}</span>{% endif %}
                                        {% if cit.in_google and not cit.google_rank %}<span style="margin-left:4px; background:#f97316; color:white; padding:1px 5px; border-radius:8px; font-size:9px;">G</span>{% endif %}
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
                                        {% elif cit.google_rank %}
                                        <span style="font-weight: bold;">
                                            G#{{ cit.google_rank }}
                                            {% if cit.google_query_num %}Q{{ cit.google_query_num }}{% endif %}
                                        </span>
                                        {% elif cit.in_google %}
                                        <span style="font-weight: bold;">G</span>
                                        {% else %}
                                        <span style="font-weight: bold;">✗</span>
                                    {% endif %}
                                        {% if cit.google_rank and cit.bing_rank %}<span style="margin-left:4px; background:#f97316; color:white; padding:1px 5px; border-radius:8px; font-size:9px;">G#{{ cit.google_rank }}</span>{% endif %}
                                        {% if cit.in_google and not cit.google_rank %}<span style="margin-left:4px; background:#f97316; color:white; padding:1px 5px; border-radius:8px; font-size:9px;">G</span>{% endif %}
                                    </div>
                                </a>
                                {% endfor %}
                            </div>
                                {% endif %}
                            </div>
                        
                        <!-- Rejected Sources (retrieved but not cited) -->
                        {% set rejected_sources = cit_db|selectattr('citation_type', 'equalto', 'rejected')|list %}
                        {% if rejected_sources %}
                        <div style="border-top: 1px solid #fca5a5; margin-top: 15px; padding-top: 15px; background: #fef2f2; margin: 15px -15px -15px; padding: 15px; border-radius: 0 0 8px 8px;">
                            <div style="font-size: 11px; color: #991b1b; font-weight: bold; margin-bottom: 8px;">🚫 REJECTED SOURCES ({{ rejected_sources|length }})</div>
                            <div style="font-size: 10px; color: #666; margin-bottom: 10px;">Retrieved by ChatGPT but NOT used in response</div>
                            
                            <div style="display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 15px;">
                            {% for cit in rejected_sources %}
                                <a href="{{ cit.url }}" target="_blank" style="text-decoration: none;">
                                    <div style="font-size: 10px; background: {{ '#fee2e2' if cit.bing_rank else ('#fff1f2' if cit.in_google else '#f9fafb') }}; color: {{ '#991b1b' if cit.bing_rank else ('#be123c' if cit.in_google else '#6b7280') }}; padding: 3px 8px; border-radius: 10px;">
                                        {{ cit.domain }} 🔗
                                        {% if cit.bing_rank %}
                                        <span style="font-weight: bold;">
                                            #{{ cit.bing_rank }}
                                            {% if cit.bing_query_nums_str %}{{ cit.bing_query_nums_str }}{% else %}Q{{ cit.bing_query_num }}{% endif %}
                                        </span>
                                        {% elif cit.google_rank %}
                                        <span style="font-weight: bold;">
                                            G#{{ cit.google_rank }}
                                            {% if cit.google_query_num %}Q{{ cit.google_query_num }}{% endif %}
                                        </span>
                                        {% elif cit.in_google %}
                                        <span style="font-weight: bold;">G</span>
                                        {% else %}
                                        <span style="font-weight: bold;">✗</span>
                                        {% endif %}
                                        {% if cit.google_rank and cit.bing_rank %}<span style="margin-left:4px; background:#f97316; color:white; padding:1px 5px; border-radius:8px; font-size:9px;">G#{{ cit.google_rank }}</span>{% endif %}
                                        {% if cit.in_google and not cit.google_rank %}<span style="margin-left:4px; background:#f97316; color:white; padding:1px 5px; border-radius:8px; font-size:9px;">G</span>{% endif %}
                                    </div>
                                </a>
                            {% endfor %}
                            </div>

                            <details>
                                <summary style="font-size: 10px; color: #991b1b; cursor: pointer; font-weight: bold;">View Details (Snippets)</summary>
                                <div style="margin-top: 10px;">
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
                            </details>
                        </div>
                        {% endif %}

                        {% if run_raw.claim_segmentation_html %}
                        <details open style="margin-top: 15px;">
                            <summary style="cursor:pointer; font-size: 12px; color:#444; font-weight: bold;">🎨 Claim segmentation + extraction</summary>
                            <div style="margin-top:10px;">{{ run_raw.claim_segmentation_html|safe }}</div>
                        </details>
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
                        <div class="bing-item {{ 'matched' if b['is_used'] or b['is_rejected'] else '' }}" data-query-text="{{ b['query'] }}" style="padding: 8px; border-bottom: 1px solid #eee; font-size: 12px; {{ 'background: #dcfce7;' if b['is_cited'] else ('background: #e0f2fe;' if b['is_additional'] else ('background: #fef2f2;' if b['is_rejected'] else '')) }}">
                            <span class="bing-rank-num" style="font-size: 10px;">#{{ b['position'] }}</span>
                            <span style="background:#e0e7ff; color:#3730a3; padding:1px 4px; border-radius:3px; font-size:9px; font-weight:bold;">Q{{ q_num }}</span>
                            <span style="background:#f3f4f6; color:#666; padding:1px 4px; border-radius:3px; font-size:9px; margin-left:4px;">Pg {{ b['page_num'] or '?' }}</span>
                            {% if b.get('in_google') %}<span style="background:#f97316; color:white; padding:1px 4px; border-radius:3px; font-size:9px; font-weight:bold; margin-left:4px;">G</span>{% endif %}
                            {% if b['is_cited'] %}<span style="color:#10a37f; font-size:10px; font-weight:bold; margin-left:4px;">CITED</span>{% endif %}
                            {% if b['is_additional'] %}<span style="color:#0369a1; font-size:10px; font-weight:bold; margin-left:4px;">ADDITIONAL</span>{% endif %}
                            {% if b['is_rejected'] %}<span style="color:#dc2626; font-size:10px; font-weight:bold; margin-left:4px;">REJECTED</span>{% endif %}
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
                        <div class="google-item {{ 'matched' if g['is_used'] or g['is_rejected'] else '' }}" data-query-text="{{ g['query'] }}" style="padding: 8px; border-bottom: 1px solid #eee; font-size: 12px; {{ 'background: #fef9c3;' if g['is_used'] else ('background: #fef2f2;' if g['is_rejected'] else '') }}">
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
                            {% if g['is_rejected'] %}<span style="color:#dc2626; font-size:10px; font-weight:bold; margin-left:4px;">REJECTED</span>{% endif %}
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

    <script>
        (function () {
            const audio = document.getElementById('bg-audio');
            const btn = document.getElementById('mic-toggle');
            const status = document.getElementById('mic-status');
            if (!audio || !btn) return;

            function setStatus(msg, isError) {
                if (!status) return;
                status.textContent = msg || '';
                status.style.display = msg ? 'block' : 'none';
                status.style.background = isError ? 'rgba(127,29,29,0.92)' : 'rgba(17,24,39,0.92)';
                if (msg) window.setTimeout(() => { status.style.display = 'none'; }, 3500);
            }

            async function toggle() {
                // If already playing: just mute/unmute (do NOT reset time)
                if (!audio.paused && !audio.ended) {
                    audio.muted = !audio.muted;
                    btn.classList.toggle('off', audio.muted);
                    setStatus(audio.muted ? 'Muted' : 'Playing (loop)', false);
                    return;
                }

                // If paused: start playback (loop attribute is set on the <audio>)
                try {
                    audio.loop = true;
                    audio.muted = false;
                    audio.volume = 1.0;
                    await audio.play();
                    btn.classList.remove('off');
                    setStatus('Playing (loop)', false);
                } catch (e) {
                    btn.classList.add('off');
                    const msg = (e && (e.name || e.message)) ? (e.name || e.message) : String(e);
                    setStatus('Could not start audio: ' + msg + '. Open DevTools Console for details.', true);
                    try { console.error('Audio play failed', e); } catch (err) {}
                }
            }

            // Helpful error visibility if the file 404s or can’t decode
            audio.addEventListener('error', function () {
                const code = audio.error ? audio.error.code : 0;
                setStatus('Audio load/decode error (code ' + code + '). Check that /media/Sheer_Belly_Dancin_128k.mp3 returns 200.', true);
            });

            btn.addEventListener('click', toggle);
        })();
    </script>
</body>
</html>
"""

app = Flask(__name__)

# --- Local media serving (restricted) ---
@app.route('/media/<path:filename>')
def media(filename: str):
    # Only allow a known-safe file (absolute path so it works regardless of cwd)
    if filename != 'Sheer_Belly_Dancin_128k.mp3':
        abort(404)

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    candidate_dirs = [
        os.path.join(repo_root, 'src', 'media'),
        os.path.join(repo_root, 'data'),
    ]
    for d in candidate_dirs:
        try:
            if os.path.exists(os.path.join(d, filename)):
                return send_from_directory(d, filename)
        except Exception:
            continue
    abort(404)

DB_PATH = 'geo_fresh.db'

# Load the raw CSV once at startup
print(f"Loading raw data from {DB_PATH} (Database Only Mode)...")
df_raw = pd.DataFrame() # We are using the DB for everything now

_db_initialized = False

def get_db():
    global _db_initialized
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Speed up read-heavy workload (safe for local analytics viewer)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA cache_size=-20000;")  # ~20MB
    except Exception:
        pass

    # One-time indexes to keep UI fast (does not change data semantics)
    if not _db_initialized:
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_citations_run_url ON citations(run_id, url_normalized);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_citations_account_type_type ON citations(account_type, citation_type);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bing_run_url ON bing_results(run_id, url_normalized);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bing_account_type ON bing_results(account_type);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_account_type ON runs(account_type);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_google_acc_run ON google_results(account_type, chatgpt_run_id);")
            
            # Pre-calculate normalized URLs for Google results to speed up overlap checks
            try:
                conn.execute("ALTER TABLE google_results ADD COLUMN url_normalized TEXT;")
            except Exception:
                pass # Already exists
            
            conn.execute("""
                UPDATE google_results 
                SET url_normalized = RTRIM(LOWER(REPLACE(REPLACE(REPLACE(
                    SUBSTR(url, 1, CASE WHEN INSTR(url, '?') > 0 THEN INSTR(url, '?') - 1 ELSE LENGTH(url) END),
                    'https://', ''), 'http://', ''), 'www.', '')), '/')
                WHERE url_normalized IS NULL;
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_google_url_norm ON google_results(url_normalized);")
            
            conn.commit()
        except Exception:
            pass
        _db_initialized = True
    return conn

# Enrichment cache (LLM labels)
_enriched_url_norms = None
_enriched_label_index = None
_enriched_sources = [
    'datapass/page_labels_combined_v2.5.jsonl',
    'datapass/page_labels_gemini_v2.5.jsonl',
    'datapass/page_labels_control_gpt5_mini.jsonl',
]

def _normalize_url_basic(url: str) -> str:
    if not url:
        return ''
    url = url.lower().replace('https://', '').replace('http://', '').replace('www.', '')
    url = url.split('?', 1)[0].rstrip('/')
    return url

def _load_enrichment_index():
    global _enriched_url_norms, _enriched_label_index
    if _enriched_url_norms is not None and _enriched_label_index is not None:
        return _enriched_url_norms, _enriched_label_index

    norms = set()
    labels = {}
    for path in _enriched_sources:
        if not os.path.exists(path):
            continue
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except Exception:
                        continue
                    if not data.get('ok'):
                        continue
                    url = data.get('url')
                    if not url:
                        url = (data.get('response') or {}).get('urls', {}).get('url')
                    url_norm = _normalize_url_basic(url)
                    if not url_norm:
                        continue
                    norms.add(url_norm)
                    label = (data.get('response') or {}).get('urls')
                    if label and url_norm not in labels:
                        labels[url_norm] = label
        except Exception:
            continue

    _enriched_url_norms = norms
    _enriched_label_index = labels
    return norms, labels

# Deterministic labels for known domains (used when LLM labels not available)
_DETERMINISTIC_DOMAIN_LABELS = {
    'wikipedia.org': {'type': 'reference', 'tone': 'neutral_informational', 'content_format': 'wiki', 'primary_intent': 'informational', '_auto': True},
    'en.wikipedia.org': {'type': 'reference', 'tone': 'neutral_informational', 'content_format': 'wiki', 'primary_intent': 'informational', '_auto': True},
    'arxiv.org': {'type': 'reference', 'tone': 'academic_technical', 'content_format': 'academic_paper', 'primary_intent': 'informational', '_auto': True},
    'reddit.com': {'type': 'forum_ugc', 'tone': 'opinionated', 'content_format': 'discussion_thread', 'primary_intent': 'informational', '_auto': True},
    'apps.apple.com': {'type': 'app_store_listing', 'tone': 'promotional', 'content_format': 'product_listing', 'primary_intent': 'transactional', '_auto': True},
    'play.google.com': {'type': 'app_store_listing', 'tone': 'promotional', 'content_format': 'product_listing', 'primary_intent': 'transactional', '_auto': True},
    'github.com': {'type': 'repository', 'tone': 'neutral_informational', 'content_format': 'code_repo', 'primary_intent': 'informational', '_auto': True},
    'youtube.com': {'type': 'video', 'tone': 'promotional', 'content_format': 'video', 'primary_intent': 'commercial', '_auto': True},
    'facebook.com': {'type': 'forum_ugc', 'tone': 'promotional', 'content_format': 'social_post', 'primary_intent': 'commercial', '_auto': True},
    'twitter.com': {'type': 'forum_ugc', 'tone': 'opinionated', 'content_format': 'social_post', 'primary_intent': 'informational', '_auto': True},
    'x.com': {'type': 'forum_ugc', 'tone': 'opinionated', 'content_format': 'social_post', 'primary_intent': 'informational', '_auto': True},
    'linkedin.com': {'type': 'forum_ugc', 'tone': 'promotional', 'content_format': 'social_post', 'primary_intent': 'commercial', '_auto': True},
    'medium.com': {'type': 'editorial_article', 'tone': 'opinionated', 'content_format': 'blog_post', 'primary_intent': 'informational', '_auto': True},
    'quora.com': {'type': 'forum_ugc', 'tone': 'neutral_informational', 'content_format': 'q_and_a', 'primary_intent': 'informational', '_auto': True},
    'stackoverflow.com': {'type': 'forum_ugc', 'tone': 'academic_technical', 'content_format': 'q_and_a', 'primary_intent': 'informational', '_auto': True},
    'support.microsoft.com': {'type': 'documentation', 'tone': 'neutral_informational', 'content_format': 'help_article', 'primary_intent': 'informational', '_auto': True},
    'support.google.com': {'type': 'documentation', 'tone': 'neutral_informational', 'content_format': 'help_article', 'primary_intent': 'informational', '_auto': True},
    'support.apple.com': {'type': 'documentation', 'tone': 'neutral_informational', 'content_format': 'help_article', 'primary_intent': 'informational', '_auto': True},
    'docs.google.com': {'type': 'documentation', 'tone': 'neutral_informational', 'content_format': 'help_article', 'primary_intent': 'informational', '_auto': True},
    'learn.microsoft.com': {'type': 'documentation', 'tone': 'neutral_informational', 'content_format': 'help_article', 'primary_intent': 'informational', '_auto': True},
}

def _get_deterministic_label(url_norm):
    """Return deterministic label for known domains, or None."""
    if not url_norm:
        return None
    # Extract domain from normalized URL
    domain = url_norm.split('/')[0] if '/' in url_norm else url_norm
    # Check exact domain match first
    if domain in _DETERMINISTIC_DOMAIN_LABELS:
        return _DETERMINISTIC_DOMAIN_LABELS[domain]
    # Check parent domain (e.g., en.wikipedia.org -> wikipedia.org)
    parts = domain.split('.')
    if len(parts) >= 2:
        parent = '.'.join(parts[-2:])
        if parent in _DETERMINISTIC_DOMAIN_LABELS:
            return _DETERMINISTIC_DOMAIN_LABELS[parent]
    return None

def get_label_for_url(url_norm, label_index=None):
    """Get label for URL - first from LLM labels, then deterministic."""
    if label_index and url_norm in label_index:
        return label_index[url_norm]
    return _get_deterministic_label(url_norm)

def _ensure_enriched_temp_table(db, url_norms):
    db.execute("DROP TABLE IF EXISTS temp_enriched_urls")
    db.execute("CREATE TEMP TABLE temp_enriched_urls (url_normalized TEXT PRIMARY KEY)")
    if not url_norms:
        return
    rows = [(u,) for u in url_norms]
    chunk_size = 500
    for i in range(0, len(rows), chunk_size):
        db.executemany(
            "INSERT OR IGNORE INTO temp_enriched_urls (url_normalized) VALUES (?)",
            rows[i:i + chunk_size],
        )

# Cache for raw network data
_raw_data_cache = None

# Cache expensive render outputs (keeps UI responsive on refresh / navigation)
_render_cache = {}
_CACHE_TTL_SEC = 20

def _citation_mapping_path_candidates(run_id: str, account_type: str | None):
    """Plausible mapping file paths for a run (best-effort; naming differs by account)."""
    rid = (run_id or '').strip()
    if not rid:
        return []
    base = rid
    cands = [
        os.path.join('datapass', 'citation_mappings', f'{base}_mapping.json'),
        os.path.join('datapass', 'citation_mappings', f'{base}_personal_mapping.json'),
        os.path.join('datapass', 'citation_mappings', f'{base}_enterprise_mapping.json'),
    ]
    if base.endswith('_personal'):
        cands.extend([
            os.path.join('datapass', 'citation_mappings', f'{base.replace("_personal","")}_personal_mapping.json'),
            os.path.join('datapass', 'citation_mappings', f'{base.replace("_personal","")}_mapping.json'),
        ])
    if account_type == 'enterprise':
        pref = [cands[2], cands[0], cands[1]] + cands[3:]
        return pref
    if account_type == 'personal':
        pref = [cands[0], cands[1], cands[2]] + cands[3:]
        return pref
    return cands

def _extract_claim_items_from_mapping_json(obj):
    """Return list[dict] items containing claim_text + citation_token + inline_url from mapping JSON."""
    if isinstance(obj, dict):
        for key in ('citations', 'mappings', 'items'):
            v = obj.get(key)
            if isinstance(v, list) and v and isinstance(v[0], dict) and ('claim_text' in v[0]):
                return v
        for v in obj.values():
            out = _extract_claim_items_from_mapping_json(v)
            if out:
                return out
    if isinstance(obj, list):
        if obj and isinstance(obj[0], dict) and ('claim_text' in obj[0]):
            return obj
        for v in obj:
            out = _extract_claim_items_from_mapping_json(v)
            if out:
                return out
    return []

def build_claim_segmentation_html(run_id: str, account_type: str | None):
    """
    Inline visualization of pipeline-extracted claim_text segments per citation.
    Note: this is *not* a native ChatGPT 'claim span' artifact; it is reconstructed.
    """
    for path in _citation_mapping_path_candidates(run_id, account_type):
        if not path or not os.path.exists(path):
            continue
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            items = _extract_claim_items_from_mapping_json(data) or []
            if not items:
                return ''

            # Build a ref_index -> url lookup from this run's raw search_result_groups_json,
            # so we can recover missing "+1" links when mapping JSON only stored one URL.
            ref_index_to_url = {}
            try:
                import re
                extra = get_raw_network_data(run_id) or {}
                srg_str = (extra.get('search_result_groups_json') or '[]') if isinstance(extra, dict) else '[]'
                srg = json.loads(srg_str) if isinstance(srg_str, str) else []
                if isinstance(srg, list):
                    for group in srg:
                        if isinstance(group, dict) and 'entries' in group and isinstance(group.get('entries'), list):
                            for entry in group.get('entries', []):
                                if not isinstance(entry, dict):
                                    continue
                                ref_id = entry.get('ref_id') or {}
                                try:
                                    idx = int(ref_id.get('ref_index')) if isinstance(ref_id, dict) else None
                                except Exception:
                                    idx = None
                                url = entry.get('url')
                                if idx is not None and url:
                                    ref_index_to_url[idx] = url
                        elif isinstance(group, dict):
                            ref_id = group.get('ref_id') or {}
                            try:
                                idx = int(ref_id.get('ref_index')) if isinstance(ref_id, dict) else None
                            except Exception:
                                idx = None
                            url = group.get('url')
                            if idx is not None and url:
                                ref_index_to_url[idx] = url
            except Exception:
                ref_index_to_url = {}

            def _tok_start(it):
                try:
                    tp = it.get('token_position') or {}
                    return int(tp.get('start_idx') or 0)
                except Exception:
                    return 0

            items = sorted(items, key=_tok_start)
            palette = [
                ('#dcfce7', '#166534'),
                ('#dbeafe', '#1e40af'),
                ('#fef3c7', '#92400e'),
                ('#f3e8ff', '#6b21a8'),
                ('#fee2e2', '#991b1b'),
                ('#ecfeff', '#155e75'),
            ]

            parts = []
            parts.append(
                '<div style="font-size:12px;color:#666;margin-bottom:8px;">'
                '<strong>Note:</strong> segments are <em>pipeline-extracted</em> claim spans associated to citation markers.'
                '</div>'
            )
            parts.append('<div style="line-height:1.9; white-space:pre-wrap; font-size:13px; background:#fafafa; border:1px solid #eee; padding:12px; border-radius:10px;">')
            for i, it in enumerate(items):
                claim = (it.get('claim_text') or '').strip()
                token = (it.get('citation_token') or '').strip()
                url = (it.get('inline_url') or '').strip()
                if not claim:
                    continue
                bg, fg = palette[i % len(palette)]
                safe_claim = html_module.escape(claim)
                safe_url = html_module.escape(url)
                safe_token = html_module.escape(token)
                badge = (
                    f'<span style="font-size:10px; vertical-align:super; margin-left:4px; padding:1px 5px; border-radius:6px; background:rgba(0,0,0,0.08); color:#333;">{safe_token}</span>'
                    if safe_token else ''
                )
                link_open = (
                    f'<a href="{safe_url}" target="_blank" style="text-decoration:none; color:inherit;" title="{safe_url}">'
                    if safe_url else '<span>'
                )
                link_close = '</a>' if safe_url else '</span>'
                parts.append(
                    f'{link_open}<span style="display:inline; padding:2px 6px; border-radius:6px; background:{bg}; color:{fg};">{safe_claim}{badge}</span>{link_close} '
                )
            parts.append('</div>')

            # Table view (the "Extraction Data" component)
            parts.append(
                '<details open style="margin-top:12px;">'
                '<summary style="cursor:pointer; font-size:12px; font-weight:700; color:#111;">Extraction Data (table)</summary>'
                '<div style="margin-top:10px; overflow-x:auto;">'
                '<table style="width:100%; border-collapse:collapse; font-size:12px;">'
                '<thead><tr style="background:#f3f4f6;">'
                '<th style="text-align:left; padding:8px; border:1px solid #e5e7eb;">#</th>'
                '<th style="text-align:left; padding:8px; border:1px solid #e5e7eb;">Token</th>'
                '<th style="text-align:left; padding:8px; border:1px solid #e5e7eb;">Claim Text (Extracted)</th>'
                '<th style="text-align:left; padding:8px; border:1px solid #e5e7eb;">Target URL</th>'
                '<th style="text-align:left; padding:8px; border:1px solid #e5e7eb;">start_idx</th>'
                '<th style="text-align:left; padding:8px; border:1px solid #e5e7eb;">end_idx</th>'
                '</tr></thead><tbody>'
            )
            for i, it in enumerate(items):
                claim = (it.get('claim_text') or '').strip()
                token = (it.get('citation_token') or '').strip()
                # Multi-chip: prefer all URLs in chip when present
                urls = []
                try:
                    raw_all = it.get('all_urls_in_chip')
                    if isinstance(raw_all, list):
                        urls = [u for u in raw_all if isinstance(u, str) and u.strip()]
                except Exception:
                    urls = []
                if not urls:
                    try:
                        srcs = it.get('sources')
                        if isinstance(srcs, list):
                            urls = [s.get('url') for s in srcs if isinstance(s, dict) and s.get('url')]
                    except Exception:
                        urls = []
                if not urls:
                    u = (it.get('inline_url') or '').strip()
                    if u:
                        urls = [u]

                # If token indicates multiple refs but mapping only provided one URL, try to infer the missing ones.
                # Example: token contains "turn0search10 turn0search23" but sources list only has one URL.
                try:
                    import re
                    search_idxs = re.findall(r'turn\d+search(\d+)', token)
                    for idx_str in search_idxs:
                        try:
                            idx = int(idx_str)
                        except Exception:
                            continue
                        inferred = ref_index_to_url.get(idx)
                        if inferred and inferred not in urls:
                            urls.append(inferred)
                except Exception:
                    pass

                tp = it.get('token_position') or {}
                sidx = tp.get('start_idx')
                eidx = tp.get('end_idx')
                safe_claim = html_module.escape(claim)
                safe_token = html_module.escape(token)
                if urls:
                    url_links = []
                    for u in urls:
                        su = html_module.escape(u)
                        url_links.append(f'<a href="{su}" target="_blank">{su}</a>')
                    url_cell = '<br>'.join(url_links)
                else:
                    url_cell = '—'
                parts.append(
                    '<tr>'
                    f'<td style="padding:8px; border:1px solid #e5e7eb; color:#666;">{i+1}</td>'
                    f'<td style="padding:8px; border:1px solid #e5e7eb;"><code style="background:#f3f4f6; padding:2px 4px; border-radius:4px;">{safe_token}</code></td>'
                    f'<td style="padding:8px; border:1px solid #e5e7eb;">{safe_claim}</td>'
                    f'<td style="padding:8px; border:1px solid #e5e7eb;">{url_cell}</td>'
                    f'<td style="padding:8px; border:1px solid #e5e7eb; color:#666;">{html_module.escape(str(sidx)) if sidx is not None else "—"}</td>'
                    f'<td style="padding:8px; border:1px solid #e5e7eb; color:#666;">{html_module.escape(str(eidx)) if eidx is not None else "—"}</td>'
                    '</tr>'
                )
            parts.append('</tbody></table></div></details>')
            parts.append(f'<div style="margin-top:8px;font-size:11px;color:#888;">Source: <code>{html_module.escape(path)}</code></div>')
            return ''.join(parts)
        except Exception:
            return ''
    return ''

def _cache_get(key):
    try:
        import time
        entry = _render_cache.get(key)
        if not entry:
            return None
        ts, val = entry
        if time.time() - ts > _CACHE_TTL_SEC:
            _render_cache.pop(key, None)
            return None
        return val
    except Exception:
        return None

def _cache_set(key, val):
    try:
        import time
        _render_cache[key] = (time.time(), val)
    except Exception:
        pass

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
    cache_key = ('run', request.query_string.decode('utf-8', errors='ignore'))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
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
        # Always load full detail (fast-view toggle removed)
        raw_enabled = True
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
            # Load extra raw data from CSV (required for "complete" view)
            extra_data = get_raw_network_data(run_id) or {}
            
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
                'sonic_classification_json': extra_data.get('sonic_classification_json', '{}'),
                'raw_enabled': raw_enabled,
                'claim_segmentation_html': build_claim_segmentation_html(run_id, db_run['account_type']),
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
            except Exception:
                run_raw['rejected_sources'] = []
            
            # Parse items_json for structured display
            try:
                items_raw = json.loads(db_run['items_json'] or '[]')
            except:
                items_raw = []

            # If no structured items, format response_text with inline citation chips
            # Always run this - basic formatting uses DB lookups; advanced multi-chip uses extra_data (optional)
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
                # Fast path: skip heavy reconstruction
                import html
                response_text = run_raw.get('response_text') or ''
                run_raw['formatted_response'] = html.escape(response_text).replace('\n', '<br>') if response_text else ''
        else:
            run_raw = {'query': 'N/A', 'generated_search_query': 'N/A', 'response_text': f'Run {run_id} not found', 'hidden_queries': '', 'web_search_triggered': None, 'web_search_forced': None, 'items_count': 0, 'items_with_citations_count': 0, 'hidden_queries_json': '[]', 'search_result_groups_json': '[]', 'sources_cited_json': '[]', 'sources_all_json': '[]', 'simple_search_prob': 0, 'complex_search_prob': 0, 'no_search_prob': 0, 'rejected_sources': []}

        # Get citations with Bing rank AND which query it came from
        # NOTE: google rank/query must be computed per-run (chatgpt_run_id), otherwise it will drift / appear to disappear.
        base_run_id = run_id.replace('_personal', '')
        cit_rows = db.execute('''
            SELECT c.*, 
                   (SELECT MIN(b.position) FROM bing_results b WHERE b.url_normalized = c.url_normalized AND b.run_id = c.run_id) as bing_rank,
                   (SELECT b.query FROM bing_results b WHERE b.url_normalized = c.url_normalized AND b.run_id = c.run_id ORDER BY b.position ASC LIMIT 1) as bing_query,
                   (SELECT MIN(g.position) FROM google_results g
                        WHERE g.chatgpt_run_id = ? AND g.account_type = c.account_type AND g.url_normalized = c.url_normalized) as google_rank,
                   (SELECT g.query FROM google_results g
                        WHERE g.chatgpt_run_id = ? AND g.account_type = c.account_type AND g.url_normalized = c.url_normalized
                        ORDER BY g.position ASC LIMIT 1) as google_query
            FROM citations c 
            WHERE c.run_id = ?
            ORDER BY c.citation_type, c.position
        ''', (base_run_id, base_run_id, run_id)).fetchall()
        
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
        
        # Also map Google queries (per-run, Q1/Q2 only, preserve order of appearance)
        google_unique_queries_all = list(dict.fromkeys([
            r[0] for r in db.execute(
                "SELECT query FROM google_results WHERE chatgpt_run_id = ? AND account_type = ? AND query IS NOT NULL AND query != '' AND query_type != 'generated_search_query' ORDER BY id ASC",
                (base_run_id, db_run['account_type'] if db_run else 'personal')
            ).fetchall() if r[0]
        ]))
        google_query_to_num_all = {q: i+1 for i, q in enumerate(google_unique_queries_all)}

        for cit in cit_db:
            if cit.get('bing_query'):
                cit['bing_query_num'] = query_to_num.get(cit['bing_query'], '?')
            if cit.get('google_query'):
                cit['google_query_num'] = google_query_to_num_all.get(cit['google_query'], '?')
        
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
        rejected_url_norms = set(
            (c.get('url_normalized') or '').lower()
            for c in cit_db
            if c.get('citation_type') == 'rejected' and c.get('url_normalized')
        )

        # Build "in Google" set from the full per-run set (do NOT depend on UI filtering)
        google_url_norms_all = set()
        for row in google_rows:
            g = dict(row)
            un = (g.get('url_normalized') or '').strip().lower()
            if un:
                google_url_norms_all.add(un)

        google_results = []
        for row in google_rows:
            g = dict(row)
            query_text = (g.get('query') or '').strip()
            if not query_text or query_text.lower() == 'n/a':
                continue
            if g.get('query_type') == 'generated_search_query':
                continue  # Only show Q1/Q2 (hidden queries) to match Bing
            # Check if this Google URL is also in Bing
            url_norm = (g.get('url_normalized') or '').lower()
            if not url_norm:
                url_norm = (g.get('url') or '').lower().replace('https://', '').replace('http://', '').replace('www.', '').split('?')[0].rstrip('/')
            g['in_bing'] = url_norm in bing_url_norms
            g['is_cited'] = url_norm in cited_url_norms
            g['is_additional'] = url_norm in additional_url_norms
            g['is_rejected'] = url_norm in rejected_url_norms
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
        # Use the full set, not UI-filtered subset, so badges never "disappear" due to view filters.
        google_url_norms = google_url_norms_all

        # Add in_google flag to Bing results
        for b in bing_results:
            b_url_norm = (b.get('url_normalized') or '').lower()
            b['in_google'] = b_url_norm in google_url_norms
            b['is_cited'] = b_url_norm in cited_url_norms
            b['is_additional'] = b_url_norm in additional_url_norms
            b['is_rejected'] = b_url_norm in rejected_url_norms
            b['is_used'] = b['is_cited'] or b['is_additional']

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


    html = render_template_string(HTML_TEMPLATE, active_tab='viewer', 
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
    _cache_set(cache_key, html)
    return html

@app.route('/dashboard')
def dashboard():
    cache_key = ('dashboard', request.query_string.decode('utf-8', errors='ignore'))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    db = get_db()
    enriched_only = request.args.get('enriched', '0') in ('1', 'true', 'yes', 'enriched')
    # Default ON: labels are shown unless explicitly disabled (labels=0/false/no/off)
    show_labels = request.args.get('labels', '1') in ('1', 'true', 'yes', 'on') or enriched_only
    enriched_url_norms = set()
    label_index = {}
    if enriched_only:
        enriched_url_norms, label_index = _load_enrichment_index()
        _ensure_enriched_temp_table(db, enriched_url_norms)

    citations_enriched_clause = " AND c.url_normalized IN (SELECT url_normalized FROM temp_enriched_urls)" if enriched_only else ""
    citations_enriched_clause_no_alias = " AND url_normalized IN (SELECT url_normalized FROM temp_enriched_urls)" if enriched_only else ""
    
    match_sql = "EXISTS (SELECT 1 FROM bing_results b WHERE b.run_id = c.run_id AND b.url_normalized = c.url_normalized)"
    
    # ===== ENTERPRISE STATS =====
    ent_runs = db.execute("SELECT COUNT(*) FROM runs WHERE account_type = 'enterprise'").fetchone()[0]
    ent_bing = db.execute("SELECT COUNT(*) FROM bing_results WHERE account_type = 'enterprise'").fetchone()[0]
    
    # Use faster count queries
    ent_total_all = db.execute(
        f"SELECT COUNT(*) FROM citations WHERE account_type = 'enterprise'{citations_enriched_clause_no_alias}"
    ).fetchone()[0]
    ent_matched_all = db.execute(
        f"SELECT COUNT(*) FROM citations c WHERE account_type = 'enterprise'{citations_enriched_clause} AND {match_sql}"
    ).fetchone()[0]
    
    ent_total_main = db.execute(
        f"SELECT COUNT(*) FROM citations WHERE account_type = 'enterprise' AND citation_type = 'cited'{citations_enriched_clause_no_alias}"
    ).fetchone()[0]
    ent_total_add = db.execute(
        f"SELECT COUNT(*) FROM citations WHERE account_type = 'enterprise' AND citation_type = 'additional'{citations_enriched_clause_no_alias}"
    ).fetchone()[0]
    ent_matched_main = db.execute(
        f"SELECT COUNT(*) FROM citations c WHERE account_type = 'enterprise' AND citation_type = 'cited'{citations_enriched_clause} AND {match_sql}"
    ).fetchone()[0]
    ent_bing_overlap_pct = (ent_matched_main / ent_total_main * 100.0) if ent_total_main else 0.0
    
    ent_matched_add = db.execute(
        f"SELECT COUNT(*) FROM citations c WHERE account_type = 'enterprise' AND citation_type = 'additional'{citations_enriched_clause} AND {match_sql}"
    ).fetchone()[0]
    ent_bing_add_overlap_pct = (ent_matched_add / ent_total_add * 100.0) if ent_total_add else 0.0

    # Enterprise Google overlap (control group; depends on whether enterprise Google SERP was collected+ingested)
    try:
        ent_google_matched_main = db.execute(f'''
            SELECT COUNT(*)
            FROM citations c
            WHERE c.account_type = 'enterprise' AND c.citation_type = 'cited'{citations_enriched_clause} AND EXISTS (
                SELECT 1 FROM google_results g
                WHERE g.account_type = 'enterprise'
                  AND g.url_normalized = c.url_normalized
            )
        ''').fetchone()[0]
    except Exception:
        ent_google_matched_main = 0
    ent_google_overlap_pct = (ent_google_matched_main / ent_total_main * 100.0) if ent_total_main else 0.0

    try:
        ent_google_matched_add = db.execute(f'''
            SELECT COUNT(*)
            FROM citations c
            WHERE c.account_type = 'enterprise' AND c.citation_type = 'additional'{citations_enriched_clause} AND EXISTS (
                SELECT 1 FROM google_results g
                WHERE g.account_type = 'enterprise'
                  AND g.url_normalized = c.url_normalized
            )
        ''').fetchone()[0]
    except Exception:
        ent_google_matched_add = 0
    ent_google_add_overlap_pct = (ent_google_matched_add / ent_total_add * 100.0) if ent_total_add else 0.0

    # "Rejected" sources = sources_all - (cited ∪ additional)
    # Stored as citations.citation_type = 'rejected' by build_db_from_csv.py
    def _get_rejected_total(account_type: str) -> int:
        try:
            return db.execute(
                f"SELECT COUNT(*) FROM citations WHERE account_type = ? AND citation_type = 'rejected'{citations_enriched_clause_no_alias}",
                (account_type,),
            ).fetchone()[0]
        except Exception:
            return 0

    def _get_rejected_bing_matched(account_type: str) -> int:
        try:
            return db.execute(
                f"""
                SELECT COUNT(*)
                FROM citations c
                WHERE c.account_type = ?
                  AND c.citation_type = 'rejected'
                  {citations_enriched_clause}
                  AND EXISTS (
                    SELECT 1 FROM bing_results b
                    WHERE b.run_id = c.run_id
                      AND b.url_normalized = c.url_normalized
                  )
                """,
                (account_type,),
            ).fetchone()[0]
        except Exception:
            return 0

    def _get_rejected_google_matched(account_type: str) -> int:
        try:
            return db.execute(
                f"""
                SELECT COUNT(*)
                FROM citations c
                WHERE c.account_type = ?
                  AND c.citation_type = 'rejected'
                  {citations_enriched_clause}
                  AND EXISTS (
                    SELECT 1 FROM google_results g
                    WHERE g.account_type = ?
                      AND g.url_normalized = c.url_normalized
                  )
                """,
                (account_type, account_type),
            ).fetchone()[0]
        except Exception:
            return 0
        except Exception:
            return 0

    ent_total_rejected = _get_rejected_total('enterprise')
    ent_rejected_bing_matched = _get_rejected_bing_matched('enterprise')
    ent_rejected_google_matched = _get_rejected_google_matched('enterprise')
    ent_rejected_bing_overlap_pct = (ent_rejected_bing_matched / ent_total_rejected * 100.0) if ent_total_rejected else 0.0
    ent_rejected_google_overlap_pct = (ent_rejected_google_matched / ent_total_rejected * 100.0) if ent_total_rejected else 0.0
    
    ent_invisible = db.execute(f'''
        SELECT domain, COUNT(*) as count
        FROM citations c
        WHERE account_type = 'enterprise' AND NOT EXISTS (
            SELECT 1 FROM bing_results b WHERE b.run_id = c.run_id AND b.url_normalized = c.url_normalized
        )
        {citations_enriched_clause}
        GROUP BY domain ORDER BY count DESC LIMIT 15
    ''').fetchall()
    
    ent_page_data = db.execute(f'''
        SELECT b.page_num, COUNT(DISTINCT c.id) as match_count
        FROM bing_results b
        JOIN citations c ON c.url_normalized = b.url_normalized AND c.run_id = b.run_id
        WHERE b.page_num IS NOT NULL AND b.account_type = 'enterprise'
          {citations_enriched_clause}
        GROUP BY b.page_num ORDER BY b.page_num
    ''').fetchall()

    def _get_google_pos_data(account_type: str):
        # Dynamic WHERE clause based on checkboxes
        g_selected_groups = []
        if request.args.get('inc_cited') == '1': g_selected_groups.append('cited')
        if request.args.get('inc_additional') == '1': g_selected_groups.append('additional')
        if request.args.get('inc_rejected') == '1': g_selected_groups.append('rejected')
        
        if not g_selected_groups:
            # If nothing selected, default to 'cited' for this specific view to avoid empty tables on first load
            # unless the form was actually submitted with nothing.
            if request.args.get('group_filter') == '1':
                return []
            g_selected_groups = ['cited']

        placeholders = ', '.join(['?'] * len(g_selected_groups))
        
        rows = db.execute(f'''
            SELECT
              g.result_type as result_type,
              CASE WHEN g.result_type = 'organic' THEN g.page_num ELSE NULL END as page_key,
              g.position as position,
              COUNT(DISTINCT c.id) as match_count
            FROM google_results g
            JOIN citations c
              ON c.run_id = g.chatgpt_run_id
             AND c.url_normalized = g.url_normalized
            WHERE g.account_type = ?
              AND g.result_type IN ('organic', 'video', 'discussion', 'related_question')
              AND g.position IS NOT NULL
              AND g.position > 0
              AND c.citation_type IN ({placeholders})
              {citations_enriched_clause}
            GROUP BY g.result_type, page_key, g.position
        ''', (account_type, *g_selected_groups)).fetchall()

        # Aggregate into buckets (single total for the selected citation types)
        buckets = {}  # bucket -> total_count
        order_map = {}
        
        for rt, page_key, pos, cnt in rows:
            try: pos_i = int(pos or 0)
            except: pos_i = 0
            
            if rt == 'organic':
                try: page_i = int(page_key or 0)
                except: page_i = 0
                bucket = f"organic_p{page_i}_{pos_i}"
                order_key = (0, page_i, pos_i)
            elif rt == 'related_question':
                bucket = f"paa{pos_i}"
                order_key = (1, 0, pos_i)
            elif rt == 'video':
                bucket = f"video{pos_i}"
                order_key = (2, 0, pos_i)
            elif rt == 'discussion':
                bucket = f"discussion{pos_i}"
                order_key = (3, 0, pos_i)
            else:
                bucket = f"{rt}{pos_i}"
                order_key = (9, 0, pos_i)
            
            if bucket not in buckets:
                buckets[bucket] = 0
                order_map[bucket] = order_key
            
            buckets[bucket] += int(cnt or 0)

        sorted_buckets = sorted(buckets.keys(), key=lambda x: order_map[x])
        return [(b, buckets[b]) for b in sorted_buckets]

    ent_google_pos_data = _get_google_pos_data('enterprise')

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
                    f"SELECT DISTINCT c.url_normalized FROM citations c WHERE c.run_id = ? AND c.citation_type = 'cited' AND c.url_normalized != ''{citations_enriched_clause}",
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
    
    pers_total_all = db.execute(
        f"SELECT COUNT(*) FROM citations WHERE account_type = 'personal'{citations_enriched_clause_no_alias}"
    ).fetchone()[0]
    pers_matched_all = db.execute(
        f"SELECT COUNT(*) FROM citations c WHERE account_type = 'personal'{citations_enriched_clause} AND {match_sql}"
    ).fetchone()[0]
    
    pers_total_main = db.execute(
        f"SELECT COUNT(*) FROM citations WHERE account_type = 'personal' AND citation_type = 'cited'{citations_enriched_clause_no_alias}"
    ).fetchone()[0]
    pers_total_add = db.execute(
        f"SELECT COUNT(*) FROM citations WHERE account_type = 'personal' AND citation_type = 'additional'{citations_enriched_clause_no_alias}"
    ).fetchone()[0]
    pers_total_rejected = _get_rejected_total('personal')
    pers_rejected_bing_matched = _get_rejected_bing_matched('personal')
    pers_rejected_google_matched = _get_rejected_google_matched('personal')
    pers_rejected_bing_overlap_pct = (pers_rejected_bing_matched / pers_total_rejected * 100.0) if pers_total_rejected else 0.0
    pers_rejected_google_overlap_pct = (pers_rejected_google_matched / pers_total_rejected * 100.0) if pers_total_rejected else 0.0
    pers_matched_main = db.execute(
        f"SELECT COUNT(*) FROM citations c WHERE account_type = 'personal' AND citation_type = 'cited'{citations_enriched_clause} AND {match_sql}"
    ).fetchone()[0]
    pers_bing_overlap_pct = (pers_matched_main / pers_total_main * 100.0) if pers_total_main else 0.0
    
    pers_matched_add = db.execute(
        f"SELECT COUNT(*) FROM citations c WHERE account_type = 'personal' AND citation_type = 'additional'{citations_enriched_clause} AND {match_sql}"
    ).fetchone()[0]
    pers_bing_add_overlap_pct = (pers_matched_add / pers_total_add * 100.0) if pers_total_add else 0.0

    # Personal Google overlap (cited URLs found in Google results)
    pers_google_matched_main = 0
    try:
        pers_google_matched_main = db.execute(f'''
            SELECT COUNT(*)
            FROM citations c
            WHERE c.account_type = 'personal' AND c.citation_type = 'cited'{citations_enriched_clause} AND EXISTS (
                SELECT 1 FROM google_results g
                WHERE g.account_type = 'personal'
                  AND g.url_normalized = c.url_normalized
            )
        ''').fetchone()[0]
    except Exception:
        pers_google_matched_main = 0
    pers_google_overlap_pct = (pers_google_matched_main / pers_total_main * 100.0) if pers_total_main else 0.0

    # Personal Google overlap (additional URLs found in Google results)
    pers_google_matched_add = 0
    try:
        pers_google_matched_add = db.execute(f'''
            SELECT COUNT(*)
            FROM citations c
            WHERE c.account_type = 'personal' AND c.citation_type = 'additional'{citations_enriched_clause} AND EXISTS (
                SELECT 1 FROM google_results g
                WHERE g.account_type = 'personal'
                  AND g.url_normalized = c.url_normalized
            )
        ''').fetchone()[0]
    except Exception:
        pers_google_matched_add = 0
    pers_google_add_overlap_pct = (pers_google_matched_add / pers_total_add * 100.0) if pers_total_add else 0.0

    # Personal combined coverage (Bing OR Google) and Google-only
    try:
        pers_combined_matched_main = db.execute(f'''
            SELECT COUNT(*)
            FROM citations c
            WHERE c.account_type = 'personal' AND c.citation_type = 'cited'{citations_enriched_clause}
              AND (
                EXISTS (SELECT 1 FROM bing_results b WHERE b.run_id = c.run_id AND b.url_normalized = c.url_normalized)
                OR EXISTS (
                    SELECT 1 FROM google_results g
                    WHERE g.account_type = 'personal'
                      AND g.url_normalized = c.url_normalized
                )
              )
        ''').fetchone()[0]
    except Exception:
        pers_combined_matched_main = 0
    pers_combined_overlap_pct = (pers_combined_matched_main / pers_total_main * 100.0) if pers_total_main else 0.0
    pers_missing_overlap_pct = 100.0 - pers_combined_overlap_pct if pers_total_main else 0.0

    try:
        pers_google_only_matched_main = db.execute(f'''
            SELECT COUNT(*)
            FROM citations c
            WHERE c.account_type = 'personal' AND c.citation_type = 'cited'{citations_enriched_clause}
              AND NOT EXISTS (SELECT 1 FROM bing_results b WHERE b.run_id = c.run_id AND b.url_normalized = c.url_normalized)
              AND EXISTS (
                    SELECT 1 FROM google_results g
                    WHERE g.account_type = 'personal'
                      AND g.url_normalized = c.url_normalized
                )
        ''').fetchone()[0]
    except Exception:
        pers_google_only_matched_main = 0
    pers_google_only_overlap_pct = (pers_google_only_matched_main / pers_total_main * 100.0) if pers_total_main else 0.0

    # ===== OVERALL (ALL ACCOUNTS) CITED COVERAGE =====
    total_cited_all = db.execute(
        f"SELECT COUNT(*) FROM citations WHERE citation_type = 'cited'{citations_enriched_clause_no_alias}"
    ).fetchone()[0]
    # Bing coverage across all cited (enterprise + personal)
    all_bing_matched_cited = db.execute(f"""
        SELECT COUNT(DISTINCT c.id)
        FROM citations c
        WHERE c.citation_type = 'cited'{citations_enriched_clause} AND {match_sql}
    """).fetchone()[0]
    all_bing_cited_pct = (all_bing_matched_cited / total_cited_all * 100.0) if total_cited_all else 0.0

    # Combined coverage for ALL cited: (Bing) OR (Google for personal)
    try:
        all_combined_matched_cited = db.execute(f'''
            SELECT COUNT(DISTINCT c.id)
            FROM citations c
            WHERE c.citation_type = 'cited'{citations_enriched_clause}
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
    
    total_unique_domains = db.execute(
        f"SELECT COUNT(DISTINCT domain) FROM citations WHERE domain != ''{citations_enriched_clause_no_alias}"
    ).fetchone()[0]
    total_rejected_global = ent_total_rejected + pers_total_rejected

    pers_invisible = db.execute(f'''
        SELECT domain, COUNT(*) as count
        FROM citations c
        WHERE account_type = 'personal' AND NOT EXISTS (
            SELECT 1 FROM bing_results b WHERE b.run_id = c.run_id AND b.url_normalized = c.url_normalized
        )
        {citations_enriched_clause}
        GROUP BY domain ORDER BY count DESC LIMIT 15
    ''').fetchall()
    
    pers_page_data = db.execute(f'''
        SELECT b.page_num, COUNT(DISTINCT c.id) as match_count
        FROM bing_results b
        JOIN citations c ON c.url_normalized = b.url_normalized AND c.run_id = b.run_id
        WHERE b.page_num IS NOT NULL AND b.account_type = 'personal'
          {citations_enriched_clause}
        GROUP BY b.page_num ORDER BY b.page_num
    ''').fetchall()

    pers_google_pos_data = _get_google_pos_data('personal')

    pers_total_cited_urls, pers_q1_matched, pers_q2_matched, pers_q1_overlap_pct, pers_q2_overlap_pct = _aggregate_q_overlap('personal')

    # ===== ENRICHMENT COVERAGE & LABEL DISTRIBUTION =====
    breakdown_account = request.args.get('breakdown_account', 'all')
    if breakdown_account not in ('all', 'enterprise', 'personal'):
        breakdown_account = 'all'

    # Citation group filters for the "Cited / Additional / Rejected" breakdown
    # Default: include all on first load. Once the form is submitted (group_filter=1),
    # treat unchecked boxes as False (even if all are unchecked).
    group_filter_active = (request.args.get('group_filter') == '1')
    if group_filter_active:
        inc_cited = (request.args.get('inc_cited') == '1')
        inc_additional = (request.args.get('inc_additional') == '1')
        inc_rejected = (request.args.get('inc_rejected') == '1')
    else:
        inc_cited = True
        inc_additional = True
        inc_rejected = True
    selected_groups = []
    if inc_cited:
        selected_groups.append('cited')
    if inc_additional:
        selected_groups.append('additional')
    if inc_rejected:
        selected_groups.append('rejected')
    enrichment_total_citations = 0
    enriched_citation_count = 0
    unlabeled_citation_count = 0
    enrichment_pct = 0.0
    label_type_rows = []
    label_tone_rows = []
    if show_labels:
        if not enriched_only:
            enriched_url_norms, label_index = _load_enrichment_index()
        breakdown_account_clause = f" AND c.account_type = '{breakdown_account}'" if breakdown_account != 'all' else ""
        citation_rows = db.execute(
            f"SELECT c.url_normalized, c.citation_type FROM citations c WHERE c.url_normalized != ''{citations_enriched_clause}{breakdown_account_clause}"
        ).fetchall()
        enrichment_total_citations = len(citation_rows)
        label_type_counts = {}
        label_tone_counts = {}
        # Selected-group counts (checkbox-driven)
        label_type_counts_selected = {}
        label_tone_counts_selected = {}
        selected_total = 0
        selected_enriched = 0
        # Per-group breakdowns (by citation_type)
        label_type_counts_by_group = {'cited': {}, 'additional': {}, 'rejected': {}}
        label_tone_counts_by_group = {'cited': {}, 'additional': {}, 'rejected': {}}
        enriched_counts_by_group = {'cited': 0, 'additional': 0, 'rejected': 0}
        totals_by_group = {'cited': 0, 'additional': 0, 'rejected': 0}
        for row in citation_rows:
            url_norm = row[0]
            ctype = row[1] or ''
            if ctype in totals_by_group:
                totals_by_group[ctype] += 1
            if ctype in selected_groups:
                selected_total += 1
            if not url_norm:
                continue
            # Use LLM label first, fallback to deterministic label for known domains
            label = get_label_for_url(url_norm, label_index)
            has_label = url_norm in enriched_url_norms or (label is not None)
            if has_label:
                enriched_citation_count += 1
                label = label or {}
                label_type = label.get('type') or 'unknown'
                label_tone = label.get('tone') or 'unknown'
                label_type_counts[label_type] = label_type_counts.get(label_type, 0) + 1
                label_tone_counts[label_tone] = label_tone_counts.get(label_tone, 0) + 1
                if ctype in selected_groups:
                    selected_enriched += 1
                    label_type_counts_selected[label_type] = label_type_counts_selected.get(label_type, 0) + 1
                    label_tone_counts_selected[label_tone] = label_tone_counts_selected.get(label_tone, 0) + 1
                if ctype in enriched_counts_by_group:
                    enriched_counts_by_group[ctype] += 1
                    d1 = label_type_counts_by_group[ctype]
                    d1[label_type] = d1.get(label_type, 0) + 1
                    d2 = label_tone_counts_by_group[ctype]
                    d2[label_tone] = d2.get(label_tone, 0) + 1

        unlabeled_citation_count = max(enrichment_total_citations - enriched_citation_count, 0)
        enrichment_pct = (enriched_citation_count / enrichment_total_citations * 100.0) if enrichment_total_citations else 0.0

        def _build_label_rows(counts):
            total = sum(counts.values())
            rows = []
            for label, count in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10]:
                pct = (count / total * 100.0) if total else 0.0
                rows.append({'label': label, 'count': count, 'pct': pct})
            return rows

        label_type_rows = _build_label_rows(label_type_counts)
        label_tone_rows = _build_label_rows(label_tone_counts)
        label_type_rows_by_group = {g: _build_label_rows(d) for g, d in label_type_counts_by_group.items()}
        label_tone_rows_by_group = {g: _build_label_rows(d) for g, d in label_tone_counts_by_group.items()}
        enrichment_pct_by_group = {}
        unlabeled_by_group = {}
        for g in ('cited', 'additional', 'rejected'):
            tot = totals_by_group.get(g, 0) or 0
            enr = enriched_counts_by_group.get(g, 0) or 0
            enrichment_pct_by_group[g] = (enr / tot * 100.0) if tot else 0.0
            unlabeled_by_group[g] = max(tot - enr, 0)

        # Selected-group summary for the combined breakdown
        selected_unlabeled = max(selected_total - selected_enriched, 0)
        selected_enrichment_pct = (selected_enriched / selected_total * 100.0) if selected_total else 0.0
        label_type_rows_selected = _build_label_rows(label_type_counts_selected)
        label_tone_rows_selected = _build_label_rows(label_tone_counts_selected)

    html = render_template_string(DASHBOARD_TEMPLATE, active_tab='dashboard', 
                                 ent_runs=ent_runs, ent_bing=ent_bing,
                                 ent_total_all=ent_total_all, ent_matched_all=ent_matched_all,
                                 ent_total_main=ent_total_main, ent_total_add=ent_total_add,
                                 ent_total_rejected=ent_total_rejected,
                                 ent_rejected_bing_overlap_pct=ent_rejected_bing_overlap_pct,
                                 ent_rejected_google_overlap_pct=ent_rejected_google_overlap_pct,
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
                                 pers_rejected_bing_overlap_pct=pers_rejected_bing_overlap_pct,
                                 pers_rejected_google_overlap_pct=pers_rejected_google_overlap_pct,
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
                                 ent_google_pos_data=ent_google_pos_data,
                                 pers_google_pos_data=pers_google_pos_data,
                                 pers_total_cited_urls=pers_total_cited_urls,
                                 pers_q1_matched=pers_q1_matched, pers_q2_matched=pers_q2_matched,
                                 pers_q1_overlap_pct=pers_q1_overlap_pct, pers_q2_overlap_pct=pers_q2_overlap_pct,
                                 enriched_only=enriched_only,
                                 show_labels=show_labels,
                                 enriched_citation_count=enriched_citation_count,
                                 enrichment_total_citations=enrichment_total_citations,
                                 enrichment_pct=enrichment_pct,
                                 unlabeled_citation_count=unlabeled_citation_count,
                                 label_type_counts=label_type_rows,
                                 label_tone_counts=label_tone_rows,
                                 label_type_counts_by_group=label_type_rows_by_group if show_labels else {},
                                 label_tone_counts_by_group=label_tone_rows_by_group if show_labels else {},
                                 enrichment_pct_by_group=enrichment_pct_by_group if show_labels else {},
                                 unlabeled_by_group=unlabeled_by_group if show_labels else {},
                                 totals_by_group=totals_by_group if show_labels else {},
                                 enriched_counts_by_group=enriched_counts_by_group if show_labels else {},
                                 breakdown_account=breakdown_account,
                                 # Checkbox state + selected-group outputs
                                 inc_cited=inc_cited,
                                 inc_additional=inc_additional,
                                 inc_rejected=inc_rejected,
                                 selected_groups=selected_groups,
                                 selected_total=selected_total if show_labels else 0,
                                 selected_enriched=selected_enriched if show_labels else 0,
                                 selected_unlabeled=selected_unlabeled if show_labels else 0,
                                 selected_enrichment_pct=selected_enrichment_pct if show_labels else 0.0,
                                 label_type_counts_selected=label_type_rows_selected if show_labels else [],
                                 label_tone_counts_selected=label_tone_rows_selected if show_labels else [])
    _cache_set(cache_key, html)
    return html

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
                'ent_cited': 0, 'ent_additional': 0, 'ent_rejected': 0,
                'pers_cited': 0, 'pers_additional': 0, 'pers_rejected': 0,
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
            elif ctype == 'additional':
                d['ent_additional'] += 1
            elif ctype == 'rejected':
                d['ent_rejected'] += 1
        else:
            if ctype == 'cited':
                d['pers_cited'] += 1
            elif ctype == 'additional':
                d['pers_additional'] += 1
            elif ctype == 'rejected':
                d['pers_rejected'] += 1
        
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
    
    return render_template_string(DOMAIN_EXPLORER_TEMPLATE, active_tab='domains',
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
    
    .nav { 
        display: flex; 
        gap: 2px; 
        margin-bottom: 20px; 
        border-bottom: 1px solid #e5e7eb; 
        padding-bottom: 0;
    }
    .nav a { 
        text-decoration: none !important; 
        color: #6b7280 !important; 
        font-weight: 600 !important; 
        padding: 10px 20px !important; 
        border-radius: 8px 8px 0 0 !important;
        font-size: 14px !important;
        transition: all 0.2s !important;
        border: 1px solid transparent !important;
        border-bottom: none !important;
        margin-bottom: -1px !important;
        margin-right: 0 !important;
    }
    .nav a:hover { 
        background: #f3f4f6 !important; 
        color: #111827 !important; 
    }
    .nav a.active { 
        background: white !important; 
        color: #10a37f !important; 
        border-color: #e5e7eb !important;
        border-bottom: 1px solid white !important;
    }

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
        <a href="/" class="{{ 'active' if active_tab == 'viewer' else '' }}">🤖 Run Viewer</a>
        <a href="/dashboard" class="{{ 'active' if active_tab == 'dashboard' else '' }}">📊 Dashboard</a>
        <a href="/urls" class="{{ 'active' if active_tab == 'urls' else '' }}">🔗 URL Breakdown</a>
        <a href="/domains" class="{{ 'active' if active_tab == 'domains' else '' }}">🔍 Domain Explorer</a>
        <a href="/invisible" class="{{ 'active' if active_tab == 'invisible' else '' }}">🕳️ Truly Invisible</a>
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
          <option value="rejected" {{ 'selected' if type_filter=='rejected' else '' }}>Rejected</option>
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

# =========================
# URL Breakdown (Enriched vs Unlabeled, by cited/additional/rejected)
# =========================
URL_BREAKDOWN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <title>URL Breakdown - GEO Research</title>
  <style>
    body { font-family: -apple-system, sans-serif; background: #f4f4f9; margin: 0; padding: 20px; }
    
    .nav { 
        display: flex; 
        gap: 2px; 
        margin-bottom: 20px; 
        border-bottom: 1px solid #e5e7eb; 
        padding-bottom: 0;
    }
    .nav a { 
        text-decoration: none !important; 
        color: #6b7280 !important; 
        font-weight: 600 !important; 
        padding: 10px 20px !important; 
        border-radius: 8px 8px 0 0 !important;
        font-size: 14px !important;
        transition: all 0.2s !important;
        border: 1px solid transparent !important;
        border-bottom: none !important;
        margin-bottom: -1px !important;
        margin-right: 0 !important;
    }
    .nav a:hover { 
        background: #f3f4f6 !important; 
        color: #111827 !important; 
    }
    .nav a.active { 
        background: white !important; 
        color: #10a37f !important; 
        border-color: #e5e7eb !important;
        border-bottom: 1px solid white !important;
    }

    .nav a { margin-right: 12px; text-decoration: none; color: #111; font-weight: 600; }
    .card { background: white; padding: 16px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
    table { width: 100%; border-collapse: collapse; }
    th, td { text-align: left; padding: 8px; border-bottom: 1px solid #eee; font-size: 12px; }
    th { font-size: 11px; color: #555; }
    .filters { display:flex; gap:10px; flex-wrap: wrap; margin: 10px 0 16px; align-items: end; }
    select { padding: 6px 8px; border-radius: 8px; border: 1px solid #ddd; }
    .muted { color:#666; font-size: 12px; }
    .pill { display:inline-block; padding:2px 8px; border-radius: 999px; font-size: 11px; font-weight: 700; }
    .pill-green { background:#dcfce7; color:#166534; }
    .pill-gray { background:#f3f4f6; color:#374151; }
    .pill-red { background:#fee2e2; color:#991b1b; }
    .pill-amber { background:#fef3c7; color:#92400e; }
    .pill-orange { background:#ffedd5; color:#9a3412; }
    a.url { color:#0369a1; text-decoration:none; }
    a.url:hover { text-decoration:underline; }
  </style>
</head>
<body>
  
    <div class="nav">
        <a href="/" class="{{ 'active' if active_tab == 'viewer' else '' }}">🤖 Run Viewer</a>
        <a href="/dashboard" class="{{ 'active' if active_tab == 'dashboard' else '' }}">📊 Dashboard</a>
        <a href="/urls" class="{{ 'active' if active_tab == 'urls' else '' }}">🔗 URL Breakdown</a>
        <a href="/domains" class="{{ 'active' if active_tab == 'domains' else '' }}">🔍 Domain Explorer</a>
        <a href="/invisible" class="{{ 'active' if active_tab == 'invisible' else '' }}">🕳️ Truly Invisible</a>
    </div>

  <h1 style="margin: 0 0 6px;">🔗 URL Breakdown</h1>
  <div class="muted">Filter to see which specific URLs are enriched vs unlabeled, split by citation group (cited/additional/rejected).</div>

  <div class="card" style="margin-top:14px;">
    <form method="get" class="filters">
      <label class="muted">
        Account:
        <select name="account">
          <option value="all" {{ 'selected' if account_filter=='all' else '' }}>All</option>
          <option value="personal" {{ 'selected' if account_filter=='personal' else '' }}>Personal</option>
          <option value="enterprise" {{ 'selected' if account_filter=='enterprise' else '' }}>Enterprise</option>
        </select>
      </label>
      <label class="muted">
        Group:
        <select name="group">
          <option value="all" {{ 'selected' if group_filter=='all' else '' }}>All</option>
          <option value="cited" {{ 'selected' if group_filter=='cited' else '' }}>Cited</option>
          <option value="additional" {{ 'selected' if group_filter=='additional' else '' }}>Additional</option>
          <option value="rejected" {{ 'selected' if group_filter=='rejected' else '' }}>Rejected</option>
        </select>
      </label>
      <label class="muted">
        Visibility:
        <select name="vis">
          <option value="all" {{ 'selected' if vis_filter=='all' else '' }}>All</option>
          <option value="bing" {{ 'selected' if vis_filter=='bing' else '' }}>Invisible on Bing</option>
          <option value="google" {{ 'selected' if vis_filter=='google' else '' }}>Invisible on Google</option>
          <option value="both" {{ 'selected' if vis_filter=='both' else '' }}>Truly Invisible (Bing+Google)</option>
        </select>
      </label>
      <label class="muted">
        Labels:
        <select name="labels">
          <option value="all" {{ 'selected' if labels_filter=='all' else '' }}>All</option>
          <option value="enriched" {{ 'selected' if labels_filter=='enriched' else '' }}>Enriched only</option>
          <option value="unlabeled" {{ 'selected' if labels_filter=='unlabeled' else '' }}>Unlabeled only</option>
        </select>
      </label>
      <label class="muted">
        Enrichment field:
        <select name="efield">
          <option value="" {{ 'selected' if not efield else '' }}>—</option>
          <option value="__source" {{ 'selected' if efield=='__source' else '' }}>label_source (llm/auto/unlabeled)</option>
          <option value="type" {{ 'selected' if efield=='type' else '' }}>type</option>
          <option value="tone" {{ 'selected' if efield=='tone' else '' }}>tone</option>
          <option value="content_format" {{ 'selected' if efield=='content_format' else '' }}>content_format</option>
          <option value="primary_intent" {{ 'selected' if efield=='primary_intent' else '' }}>primary_intent</option>
          <option value="has_tables" {{ 'selected' if efield=='has_tables' else '' }}>has_tables</option>
          <option value="has_numbered_lists" {{ 'selected' if efield=='has_numbered_lists' else '' }}>has_numbered_lists</option>
          <option value="has_bullet_points" {{ 'selected' if efield=='has_bullet_points' else '' }}>has_bullet_points</option>
          <option value="has_pros_cons" {{ 'selected' if efield=='has_pros_cons' else '' }}>has_pros_cons</option>
          <option value="is_vendor_owned" {{ 'selected' if efield=='is_vendor_owned' else '' }}>is_vendor_owned</option>
          <option value="is_current_year_2026" {{ 'selected' if efield=='is_current_year_2026' else '' }}>is_current_year_2026</option>
          <option value="expertise_signal_score" {{ 'selected' if efield=='expertise_signal_score' else '' }}>expertise_signal_score</option>
          <option value="freshness_cue_strength" {{ 'selected' if efield=='freshness_cue_strength' else '' }}>freshness_cue_strength</option>
          <option value="readability_score" {{ 'selected' if efield=='readability_score' else '' }}>readability_score</option>
        </select>
      </label>
      <label class="muted">
        Value:
        <select name="evalue">
          <option value="" {{ 'selected' if not evalue else '' }}>—</option>
          {% for v in evalue_options %}
          <option value="{{ v }}" {{ 'selected' if evalue==v else '' }}>{{ v }}</option>
          {% endfor %}
        </select>
      </label>
      <label class="muted">
        Limit:
        <select name="limit">
          <option value="100" {{ 'selected' if limit==100 else '' }}>100</option>
          <option value="250" {{ 'selected' if limit==250 else '' }}>250</option>
          <option value="500" {{ 'selected' if limit==500 else '' }}>500</option>
          <option value="1000" {{ 'selected' if limit==1000 else '' }}>1000</option>
        </select>
      </label>
      <button type="submit" style="padding:7px 10px; border-radius:10px; border:1px solid #ddd; background:#111827; color:#fff; font-size:12px; cursor:pointer;">
        Apply
      </button>
    </form>

    <div style="display:flex; gap:14px; flex-wrap: wrap; margin: 8px 0 14px;">
      <div class="pill pill-green">Enriched URLs: {{ enriched_urls_count }}</div>
      <div class="pill pill-red">Unlabeled URLs: {{ unlabeled_urls_count }}</div>
      <div class="pill pill-gray">Total URLs: {{ total_urls_count }}</div>
    </div>

    <details style="margin: 10px 0 14px; padding: 10px 12px; border: 1px solid #eee; border-radius: 12px; background: #fafafa;">
      <summary style="cursor:pointer; font-weight:700; color:#111; font-size: 12px;">🕳️ Invisible</summary>
      <div class="muted" style="margin: 8px 0 10px;">
        Visibility is evaluated <strong>per-run</strong>: a URL is “invisible on Bing/Google” if it does not appear in that run’s Bing/Google SERP capture.
        <a href="/invisible?account={{ account_filter }}&type={{ invisible_type_param }}&vis={{ 'both' if vis_filter=='all' else vis_filter }}&group=url&limit=250" style="margin-left:6px; color:#ef4444; text-decoration:none; font-weight:600;">Open full invisible explorer →</a>
      </div>
      <div style="display:flex; gap:10px; flex-wrap: wrap; margin: 6px 0 10px;">
        <div class="pill pill-amber">Invisible on Bing: {{ invisible_on_bing_urls_count }}</div>
        <div class="pill pill-orange">Invisible on Google: {{ invisible_on_google_urls_count }}</div>
        <div class="pill pill-red">Truly Invisible (Bing+Google): {{ truly_invisible_urls_count }}</div>
      </div>
      {% if truly_invisible_rows and truly_invisible_rows|length > 0 %}
      <div class="muted" style="margin: 6px 0 8px; font-size: 11px;">Top truly-invisible URLs (by distinct run count) under the current filters:</div>
      <table>
        <thead>
          <tr>
            <th>Domain</th>
            <th>URL</th>
            <th>Group</th>
            <th>Runs</th>
            <th>Occurrences</th>
          </tr>
        </thead>
        <tbody>
          {% for r in truly_invisible_rows %}
          <tr>
            <td>{{ r['domain'] }}</td>
            <td><a class="url" href="{{ r['url'] }}" target="_blank">{{ r['url'] }}</a></td>
            <td class="muted">{{ r['group'] }}</td>
            <td class="muted">{{ r['run_count'] }}</td>
            <td class="muted">{{ r['occurrences'] }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
      {% else %}
      <div class="muted" style="margin-top:8px; font-size: 11px;">No truly-invisible URLs under the current filters.</div>
      {% endif %}
    </details>

    <table>
      <thead>
        <tr>
          <th>Domain</th>
          <th>URL</th>
          <th>Group</th>
          <th>Runs</th>
          <th>Occurrences</th>
          <th>Type</th>
          <th>Tone</th>
          <th>Format</th>
          <th>Intent</th>
          <th>Features</th>
          <th>Scores</th>
        </tr>
      </thead>
      <tbody>
        {% for r in rows %}
        <tr>
          <td>{{ r['domain'] }}</td>
          <td><a class="url" href="{{ r['url'] }}" target="_blank">{{ r['url'] }}</a></td>
          <td>{{ r['group'] }}</td>
          <td class="muted">{{ r['run_count'] }}</td>
          <td class="muted">{{ r['occurrences'] }}</td>
          <td>{{ r.get('label_type','') }}{% if r.get('is_auto_label') %}<span style="color:#f97316;font-size:9px;margin-left:2px;">⚡</span>{% endif %}</td>
          <td>{{ r.get('label_tone','') }}</td>
          <td>{{ r.get('label_content_format','') }}</td>
          <td>{{ r.get('label_primary_intent','') }}</td>
          <td>
            <div style="display:flex; flex-wrap:wrap; gap:2px; max-width:150px;">
              {% if r.get('label_has_tables') %}<span class="pill pill-gray" style="font-size:9px; padding:1px 4px;">📊 Table</span>{% endif %}
              {% if r.get('label_has_numbered_lists') %}<span class="pill pill-gray" style="font-size:9px; padding:1px 4px;">1. List</span>{% endif %}
              {% if r.get('label_has_pros_cons') %}<span class="pill pill-gray" style="font-size:9px; padding:1px 4px;">⚖️ Pros</span>{% endif %}
              {% if r.get('label_is_vendor_owned') %}<span class="pill pill-gray" style="font-size:9px; padding:1px 4px;">🏢 Vend</span>{% endif %}
              {% if r.get('label_is_current_year_2026') %}<span class="pill pill-gray" style="font-size:9px; padding:1px 4px;">📅 2026</span>{% endif %}
            </div>
          </td>
          <td class="muted" style="font-size:10px;">
            Exp: {{ r.get('label_expertise_signal_score','-') }}<br>
            Frsh: {{ r.get('label_freshness_cue_strength','-') }}
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  <div class="muted" style="margin-top:12px;font-size:11px;">
    <span style="color:#f97316;">⚡</span> = auto-labeled (known domain, not LLM enriched)
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

    if type_filter not in ('cited', 'additional', 'rejected', 'all'):
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


@app.route('/urls')
def url_breakdown():
    db = get_db()
    account_filter = request.args.get('account', 'all')
    group_filter = request.args.get('group', 'all')
    labels_filter = request.args.get('labels', 'all')  # all | enriched | unlabeled
    vis_filter = request.args.get('vis', 'all')  # all | bing | google | both
    efield = request.args.get('efield', '').strip()
    evalue = request.args.get('evalue', '').strip()
    try:
        limit = int(request.args.get('limit', '250'))
    except Exception:
        limit = 250

    if account_filter not in ('personal', 'enterprise', 'all'):
        account_filter = 'all'
    if group_filter not in ('cited', 'additional', 'rejected', 'all'):
        group_filter = 'all'
    if labels_filter not in ('all', 'enriched', 'unlabeled'):
        labels_filter = 'all'
    if vis_filter not in ('all', 'bing', 'google', 'both'):
        vis_filter = 'all'
    if limit not in (100, 250, 500, 1000):
        limit = 250
    if efield not in ('', '__source', 'type', 'tone', 'content_format', 'primary_intent'):
        efield = ''
    if not efield:
        evalue = ''

    enriched_url_norms, label_index = _load_enrichment_index()
    _ensure_enriched_temp_table(db, enriched_url_norms)

    def _get_evalue_options(field: str):
        if not field:
            return []
        if field == '__source':
            return ['llm', 'auto', 'unlabeled']
        # collect unique categorical values from LLM labels + deterministic labels
        vals = set()
        for lbl in (label_index or {}).values():
            try:
                v = (lbl or {}).get(field)
                if v:
                    vals.add(str(v))
            except Exception:
                pass
        for lbl in _DETERMINISTIC_DOMAIN_LABELS.values():
            try:
                v = (lbl or {}).get(field)
                if v:
                    vals.add(str(v))
            except Exception:
                pass
        return sorted(vals)

    evalue_options = _get_evalue_options(efield)

    account_where = "c.account_type = ?" if account_filter != 'all' else "1=1"
    params = (account_filter,) if account_filter != 'all' else tuple()

    if group_filter == 'all':
        group_where = "c.citation_type IN ('cited','additional','rejected')"
        group_params = tuple()
    else:
        group_where = "c.citation_type = ?"
        group_params = (group_filter,)

    if labels_filter == 'enriched':
        labels_where = "EXISTS (SELECT 1 FROM temp_enriched_urls t WHERE t.url_normalized = c.url_normalized)"
    elif labels_filter == 'unlabeled':
        labels_where = "NOT EXISTS (SELECT 1 FROM temp_enriched_urls t WHERE t.url_normalized = c.url_normalized)"
    else:
        labels_where = "1=1"

    # Visibility predicates (per-run)
    bing_invis_pred = """
      NOT EXISTS (
        SELECT 1 FROM bing_results b
        WHERE b.run_id = c.run_id AND b.url_normalized = c.url_normalized
      )
    """
    google_invis_pred = """
      NOT EXISTS (
        SELECT 1 FROM google_results g
        WHERE g.account_type = c.account_type
          AND g.chatgpt_run_id = REPLACE(c.run_id, '_personal', '')
          AND g.url_normalized = c.url_normalized
      )
    """
    if vis_filter == 'bing':
        vis_where = f"({bing_invis_pred})"
    elif vis_filter == 'google':
        vis_where = f"({google_invis_pred})"
    elif vis_filter == 'both':
        vis_where = f"({bing_invis_pred}) AND ({google_invis_pred})"
    else:
        vis_where = "1=1"

    # Counts (unique URLs)
    total_urls_count = db.execute(
        f"""
        SELECT COUNT(DISTINCT c.url_normalized)
        FROM citations c
        WHERE {account_where}
          AND {group_where}
          AND c.url_normalized != ''
          AND {labels_where}
          AND {vis_where}
        """,
        params + group_params,
    ).fetchone()[0]

    enriched_urls_count = db.execute(
        f"""
        SELECT COUNT(DISTINCT c.url_normalized)
        FROM citations c
        WHERE {account_where}
          AND {group_where}
          AND c.url_normalized != ''
          AND EXISTS (SELECT 1 FROM temp_enriched_urls t WHERE t.url_normalized = c.url_normalized)
          AND {vis_where}
        """,
        params + group_params,
    ).fetchone()[0]
    unlabeled_urls_count = max(total_urls_count - enriched_urls_count, 0) if labels_filter == 'all' else (
        total_urls_count if labels_filter == 'unlabeled' else 0
    )

    # Rows
    rows = db.execute(
        f"""
        SELECT
          c.url_normalized as url_normalized,
          MIN(c.url) as url,
          MIN(c.domain) as domain,
          MIN(c.citation_type) as citation_type,
          COUNT(DISTINCT c.run_id) as run_count,
          COUNT(*) as occurrences
        FROM citations c
        WHERE {account_where}
          AND {group_where}
          AND c.url_normalized != ''
          AND {labels_where}
          AND {vis_where}
        GROUP BY c.url_normalized
        ORDER BY run_count DESC, occurrences DESC
        LIMIT ?
        """,
        params + group_params + (limit,),
    ).fetchall()

    out = []
    for r in rows:
        url_norm = r['url_normalized']
        # Use LLM label first, fallback to deterministic label for known domains
        label = get_label_for_url(url_norm, label_index)
        is_auto = label.get('_auto', False) if label else False
        # Optional enrichment filtering (applied after DB grouping)
        if efield and evalue:
            if efield == '__source':
                source = 'llm' if url_norm in enriched_url_norms else ('auto' if is_auto else 'unlabeled')
                if source != evalue:
                    continue
            else:
                if not label or str(label.get(efield, '')) != evalue:
                    continue
        out.append({
            'url': r['url'],
            'domain': r['domain'] or '',
            'group': r['citation_type'] or '',
            'run_count': int(r['run_count'] or 0),
            'occurrences': int(r['occurrences'] or 0),
            'label_type': label.get('type', '') if label else '',
            'label_tone': label.get('tone', '') if label else '',
            'label_content_format': label.get('content_format', '') if label else '',
            'label_primary_intent': label.get('primary_intent', '') if label else '',
            'is_auto_label': is_auto,
        })

    # ---- Invisible section (per-run visibility, scoped to current selection) ----
    # Note: This intentionally does NOT apply efield/evalue post-filters (those operate on labels after grouping).
    # It is meant as a quick, directional view + link to /invisible for deeper exploration.
    invisible_type_param = group_filter if group_filter != 'all' else 'all'

    # (re-)use bing_invis_pred / google_invis_pred; counts below respect vis_where so section matches current filter context
    try:
        invisible_on_bing_urls_count = db.execute(
            f"""
            SELECT COUNT(DISTINCT c.url_normalized)
            FROM citations c
            WHERE {account_where}
              AND {group_where}
              AND c.url_normalized != ''
              AND {labels_where}
              AND {vis_where}
              AND ({bing_invis_pred})
            """,
            params + group_params,
        ).fetchone()[0]
    except Exception:
        invisible_on_bing_urls_count = 0

    try:
        invisible_on_google_urls_count = db.execute(
            f"""
            SELECT COUNT(DISTINCT c.url_normalized)
            FROM citations c
            WHERE {account_where}
              AND {group_where}
              AND c.url_normalized != ''
              AND {labels_where}
              AND {vis_where}
              AND ({google_invis_pred})
            """,
            params + group_params,
        ).fetchone()[0]
    except Exception:
        invisible_on_google_urls_count = 0

    try:
        truly_invisible_urls_count = db.execute(
            f"""
            SELECT COUNT(DISTINCT c.url_normalized)
            FROM citations c
            WHERE {account_where}
              AND {group_where}
              AND c.url_normalized != ''
              AND {labels_where}
              AND {vis_where}
              AND ({bing_invis_pred}) AND ({google_invis_pred})
            """,
            params + group_params,
        ).fetchone()[0]
    except Exception:
        truly_invisible_urls_count = 0

    truly_invisible_rows_db = []
    try:
        truly_invisible_rows_db = db.execute(
            f"""
            SELECT
              c.url_normalized as url_normalized,
              MIN(c.url) as url,
              MIN(c.domain) as domain,
              GROUP_CONCAT(DISTINCT c.citation_type) as citation_types,
              COUNT(DISTINCT c.run_id) as run_count,
              COUNT(*) as occurrences
            FROM citations c
            WHERE {account_where}
              AND {group_where}
              AND c.url_normalized != ''
              AND {labels_where}
              AND {vis_where}
              AND ({bing_invis_pred}) AND ({google_invis_pred})
            GROUP BY c.url_normalized
            ORDER BY run_count DESC, occurrences DESC
            LIMIT 50
            """,
            params + group_params,
        ).fetchall()
    except Exception:
        truly_invisible_rows_db = []

    truly_invisible_rows = []
    for r in truly_invisible_rows_db:
        ct = (r['citation_types'] or '').strip()
        group_disp = ct if ct else (r['url_normalized'] or '')
        truly_invisible_rows.append({
            'url': r['url'],
            'domain': r['domain'] or '',
            'group': group_disp,
            'run_count': int(r['run_count'] or 0),
            'occurrences': int(r['occurrences'] or 0),
        })

    return render_template_string(
        URL_BREAKDOWN_TEMPLATE,
        account_filter=account_filter,
        group_filter=group_filter,
        labels_filter=labels_filter,
        vis_filter=vis_filter,
        efield=efield,
        evalue=evalue,
        evalue_options=evalue_options,
        limit=limit,
        rows=out,
        total_urls_count=total_urls_count,
        enriched_urls_count=enriched_urls_count if labels_filter != 'unlabeled' else 0,
        unlabeled_urls_count=unlabeled_urls_count,
        invisible_type_param=invisible_type_param,
        invisible_on_bing_urls_count=invisible_on_bing_urls_count,
        invisible_on_google_urls_count=invisible_on_google_urls_count,
        truly_invisible_urls_count=truly_invisible_urls_count,
        truly_invisible_rows=truly_invisible_rows,
    )

if __name__ == '__main__':
    debug = os.environ.get('DATA_VIEWER_DEBUG', '0').lower() in ('1', 'true', 'yes')
    app.run(debug=debug, use_reloader=debug, threaded=True, port=5000)

