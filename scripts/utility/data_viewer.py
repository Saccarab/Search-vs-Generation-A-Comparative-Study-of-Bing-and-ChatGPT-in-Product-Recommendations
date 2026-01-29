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
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 30px; }
        .card { background: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
        h2 { margin-top: 0; color: #333; font-size: 18px; border-bottom: 2px solid #f0f0f0; padding-bottom: 10px; }
        .stat-big { font-size: 36px; font-weight: bold; }
        .stat-label { color: #666; font-size: 14px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { text-align: left; padding: 8px; border-bottom: 1px solid #eee; font-size: 13px; }
        .enterprise { border-left: 4px solid #3b82f6; }
        .personal { border-left: 4px solid #f59e0b; }
    </style>
</head>
<body>
    <div class="nav">
        <a href="/">← Back to Run Viewer</a>
    </div>
    <h1>GEO Research Dashboard</h1>
    
    <div class="grid">
        <!-- Enterprise Stats -->
        <div class="card enterprise">
            <h2 style="color: #3b82f6;">🏢 Enterprise Account</h2>
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:15px; margin-bottom: 15px;">
                <div style="background:#eff6ff; padding:15px; border-radius:8px; text-align:center;">
                    <div class="stat-label">All Citations</div>
                    <div class="stat-big" style="color:#3b82f6;">{{ "%.1f"|format(ent_matched_all / ent_total_all * 100 if ent_total_all > 0 else 0) }}%</div>
                    <div style="font-size:11px; color:#666;">{{ ent_matched_all }} / {{ ent_total_all }}</div>
                </div>
                <div style="background:#dbeafe; padding:15px; border-radius:8px; text-align:center;">
                    <div class="stat-label" style="font-weight:bold;">Cited Only</div>
                    <div class="stat-big" style="color:#1d4ed8;">{{ "%.1f"|format(ent_matched_main / ent_total_main * 100 if ent_total_main > 0 else 0) }}%</div>
                    <div style="font-size:11px; color:#1e40af;">{{ ent_matched_main }} / {{ ent_total_main }}</div>
                </div>
            </div>
            <div style="font-size: 12px; color: #666;">
                <strong>Runs:</strong> {{ ent_runs }} | <strong>Bing Results:</strong> {{ ent_bing }}
            </div>
        </div>
        
        <!-- Personal Stats -->
        <div class="card personal">
            <h2 style="color: #f59e0b;">👤 Personal Account</h2>
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:15px; margin-bottom: 15px;">
                <div style="background:#fffbeb; padding:15px; border-radius:8px; text-align:center;">
                    <div class="stat-label">All Citations</div>
                    <div class="stat-big" style="color:#f59e0b;">{{ "%.1f"|format(pers_matched_all / pers_total_all * 100 if pers_total_all > 0 else 0) }}%</div>
                    <div style="font-size:11px; color:#666;">{{ pers_matched_all }} / {{ pers_total_all }}</div>
                </div>
                <div style="background:#fef3c7; padding:15px; border-radius:8px; text-align:center;">
                    <div class="stat-label" style="font-weight:bold;">Cited Only</div>
                    <div class="stat-big" style="color:#d97706;">{{ "%.1f"|format(pers_matched_main / pers_total_main * 100 if pers_total_main > 0 else 0) }}%</div>
                    <div style="font-size:11px; color:#92400e;">{{ pers_matched_main }} / {{ pers_total_main }}</div>
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
                <div style="background: #dbeafe; padding: 6px 12px; border-radius: 6px; font-size: 12px;">
                    <strong>Search Prob:</strong> Simple {{ run_raw.simple_search_prob }}% | Complex {{ run_raw.complex_search_prob }}% | None {{ run_raw.no_search_prob }}%
                </div>
                {% if run_raw.rejected_sources %}
                <div style="background: #fef2f2; padding: 6px 12px; border-radius: 6px; font-size: 12px;">
                    <strong>Rejected:</strong> {{ run_raw.rejected_sources|length }} sources
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
                                    <div style="font-size: 10px; background: {{ '#d1fae5' if cit.bing_rank else '#fee2e2' }}; color: {{ '#065f46' if cit.bing_rank else '#991b1b' }}; padding: 3px 8px; border-radius: 10px;">
                                        {{ cit.domain }} 🔗
                                        {% if cit.bing_rank %}
                                        <span style="font-weight: bold;">#{{ cit.bing_rank }} Q{{ cit.bing_query_num }}</span>
                                        {% else %}
                                        <span style="font-weight: bold;">✗</span>
                                        {% endif %}
                                    </div>
                                </a>
                            {% endfor %}
                            </div>
                            
                            {% if additional_sources %}
                            <div style="font-size: 11px; color: #6b7280; font-weight: bold; margin-bottom: 8px;">➕ ADDITIONAL SOURCES ({{ additional_sources|length }})</div>
                            <div style="display: flex; flex-wrap: wrap; gap: 4px;">
                            {% for cit in additional_sources %}
                                <a href="{{ cit.url }}" target="_blank" style="text-decoration: none;">
                                    <div style="font-size: 10px; background: {{ '#e0f2fe' if cit.bing_rank else '#f3f4f6' }}; color: {{ '#0369a1' if cit.bing_rank else '#6b7280' }}; padding: 3px 8px; border-radius: 10px;">
                                        {{ cit.domain }} 🔗
                                        {% if cit.bing_rank %}
                                        <span style="font-weight: bold;">#{{ cit.bing_rank }}</span>
                                        {% else %}
                                        <span style="font-weight: bold;">✗</span>
                                        {% endif %}
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
                        <div style="font-weight: bold; color: #111; font-size: 11px; margin-top: 2px;">
                            <a href="{{ b['url'] }}" target="_blank" style="text-decoration: none; color: #111;">{{ (b['title'] or 'No title')[:50] }}... 🔗</a>
                        </div>
                        <div style="font-size: 10px; color: #10a37f;">{{ b['domain'] }}</div>
                    </div>
                    {% endfor %}
                    </div>
                </div>
            </div>
        </div>

        <script>
            // Query toggle checkboxes
            document.querySelectorAll('.query-toggle').forEach(checkbox => {
                checkbox.addEventListener('change', function() {
                    const queryText = this.getAttribute('data-query');
                    const isVisible = this.checked;
                    
                    document.querySelectorAll(`.bing-item[data-query-text="${queryText}"]`).forEach(item => {
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
    items_raw = []
    unique_queries = []
    
    if run_id:
        # Get run data from database
        db_run = db.execute('''
            SELECT p.prompt as query, r.generated_search_query, r.response_text, r.hidden_queries, r.items_json,
                   r.web_search_triggered, r.web_search_forced, r.items_count, r.items_with_citations_count,
                   r.search_result_groups_json
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
                            
                            if bing_rank:
                                chips_html.append(f'<a href="{html.escape(u)}" target="_blank" style="display:inline-block; font-size:11px; background:#d1fae5; color:#065f46; padding:2px 8px; border-radius:12px; text-decoration:none; margin:2px 2px;">{html.escape(domain)} <span style="background:#10a37f;color:white;padding:1px 4px;border-radius:6px;font-size:9px;font-weight:bold;">#{bing_rank}</span></a>')
                            else:
                                chips_html.append(f'<a href="{html.escape(u)}" target="_blank" style="display:inline-block; font-size:11px; background:#fee2e2; color:#991b1b; padding:2px 8px; border-radius:12px; text-decoration:none; margin:2px 2px;">{html.escape(domain)} <span style="font-weight:bold;">✗</span></a>')
                        return "".join(chips_html)
                    
                    # Fallback to single chip
                    used_urls.add(url_norm)
                    clean_url = url.replace('https://', '').replace('http://', '').replace('www.', '').split('?')[0].rstrip('/')
                    domain = clean_url.split('/')[0] if '/' in clean_url else clean_url
                    
                    bing_info = bing_lookup.get(url_norm, {})
                    bing_rank = bing_info.get('rank')
                    
                    if bing_rank:
                        return f'<a href="{html.escape(url)}" target="_blank" style="display:inline-block; font-size:11px; background:#d1fae5; color:#065f46; padding:2px 8px; border-radius:12px; text-decoration:none; margin:2px 0;">{html.escape(domain)} <span style="background:#10a37f;color:white;padding:1px 4px;border-radius:6px;font-size:9px;font-weight:bold;">#{bing_rank}</span></a>'
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
                            
                            if bing_rank:
                                chips_html.append(f'<a href="{html.escape(u)}" target="_blank" style="display:inline-block; font-size:11px; background:#d1fae5; color:#065f46; padding:2px 8px; border-radius:12px; text-decoration:none; margin:2px 2px;">{html.escape(domain)} <span style="background:#10a37f;color:white;padding:1px 4px;border-radius:6px;font-size:9px;font-weight:bold;">#{bing_rank}</span></a>')
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
                    
                    if bing_rank:
                        return f'<a href="{html.escape(url)}" target="_blank" style="display:inline-block; font-size:11px; background:#d1fae5; color:#065f46; padding:2px 8px; border-radius:12px; text-decoration:none; margin:2px 0;">{html.escape(domain)} <span style="background:#10a37f;color:white;padding:1px 4px;border-radius:6px;font-size:9px;font-weight:bold;">#{bing_rank}</span></a>'
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
                        
                        chip_html = ""
                        if bing_rank:
                            chip_html = f'<a href="{html.escape(url)}" target="_blank" style="display:inline-block; font-size:11px; background:#d1fae5; color:#065f46; padding:2px 8px; border-radius:12px; text-decoration:none; margin:2px 0; margin-left:5px;">{html.escape(domain)} <span style="background:#10a37f;color:white;padding:1px 4px;border-radius:6px;font-size:9px;font-weight:bold;">#{bing_rank}</span></a>'
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
                            
                            if bing_rank:
                                multi_chip_html += f'<a href="{html.escape(url)}" target="_blank" style="display:inline-block; font-size:10px; background:#d1fae5; color:#065f46; padding:2px 6px; border-radius:10px; text-decoration:none; margin:2px;">{html.escape(domain)} <span style="background:#10a37f;color:white;padding:1px 3px;border-radius:4px;font-size:8px;font-weight:bold;">#{bing_rank}</span></a>'
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

        # Get unique queries for this run to power the checkboxes
        # preserve order of appearance (matches how queries were executed)
        unique_queries = list(dict.fromkeys([b['query'] for b in bing_results if b.get('query')]))

        # Map query text to Q1/Q2 number using this preserved order
        query_to_num = {q: i + 1 for i, q in enumerate(unique_queries)}
        for cit in cit_db:
            if cit.get('bing_query'):
                cit['bing_query_num'] = query_to_num.get(cit['bing_query'], '?')

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


    return render_template_string(HTML_TEMPLATE, 
                                 run_ids=run_ids, 
                                 active_run_id=run_id,
                                 run_raw=run_raw,
                                 cit_db=cit_db,
                                 bing_results=bing_results,
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
    ent_matched_main = db.execute(f"SELECT COUNT(DISTINCT c.id) FROM citations c WHERE account_type = 'enterprise' AND citation_type = 'cited' AND {match_sql}").fetchone()[0]
    
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
    
    # ===== PERSONAL STATS =====
    pers_runs = db.execute("SELECT COUNT(*) FROM runs WHERE account_type = 'personal'").fetchone()[0]
    pers_bing = db.execute("SELECT COUNT(*) FROM bing_results WHERE account_type = 'personal'").fetchone()[0]
    
    pers_total_all = db.execute("SELECT COUNT(*) FROM citations WHERE account_type = 'personal'").fetchone()[0]
    pers_matched_all = db.execute(f"SELECT COUNT(DISTINCT c.id) FROM citations c WHERE account_type = 'personal' AND {match_sql}").fetchone()[0]
    
    pers_total_main = db.execute("SELECT COUNT(*) FROM citations WHERE account_type = 'personal' AND citation_type = 'cited'").fetchone()[0]
    pers_matched_main = db.execute(f"SELECT COUNT(DISTINCT c.id) FROM citations c WHERE account_type = 'personal' AND citation_type = 'cited' AND {match_sql}").fetchone()[0]
    
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

    return render_template_string(DASHBOARD_TEMPLATE,
                                 ent_runs=ent_runs, ent_bing=ent_bing,
                                 ent_total_all=ent_total_all, ent_matched_all=ent_matched_all,
                                 ent_total_main=ent_total_main, ent_matched_main=ent_matched_main,
                                 ent_invisible=ent_invisible, ent_page_data=ent_page_data,
                                 pers_runs=pers_runs, pers_bing=pers_bing,
                                 pers_total_all=pers_total_all, pers_matched_all=pers_matched_all,
                                 pers_total_main=pers_total_main, pers_matched_main=pers_matched_main,
                                 pers_invisible=pers_invisible, pers_page_data=pers_page_data)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
