
import json
import os

def update_data_viewer():
    file_path = 'scripts/utility/data_viewer.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Add load_feature_ttests function
    load_func = """
    def load_feature_ttests():
        try:
            with open('data/enrichment/feature_ttests.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return None
"""
    if 'def load_feature_ttests():' not in content:
        content = content.replace('    def load_localization_data():', load_func + '\n    def load_localization_data():')

    # 2. Add ttests to render_template_string
    if 'ttests=load_feature_ttests()' not in content:
        content = content.replace('loc_summary=load_localization_data())', 'loc_summary=load_localization_data(),\n                                 ttests=load_feature_ttests())')

    # 3. Add the HTML section for T-tests
    ttest_html = """
            <div id="ttest-analysis-container" style="margin-top:40px;">
            <h3 style="font-size:14px; color:#111827; margin-bottom:10px;">Statistical Significance (Two-Sample T-Test)</h3>
            {% if ttests %}
            <div class="stat-sub" style="margin: 6px 0 12px;">
                Comparing content DNA feature prevalence between models. <strong>p&lt;0.05</strong> indicates statistical significance.
            </div>

            <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 18px; align-items:start;">
                <div>
                    <h2 style="font-size: 14px; margin-top:0;">GPT Enterprise vs. Personal</h2>
                    <table>
                        <tr>
                            <th>Feature</th>
                            <th style="text-align:right;">Ent %</th>
                            <th style="text-align:right;">Pers %</th>
                            <th style="text-align:right;">Diff</th>
                            <th style="text-align:right;">Sig</th>
                        </tr>
                        {% for feat, res in ttests.ent_vs_pers.items() %}
                        <tr>
                            <td>{{ feat.replace('has_', '').replace('_', ' ') }}</td>
                            <td style="text-align:right;">{{ res.m1 }}%</td>
                            <td style="text-align:right;">{{ res.m2 }}%</td>
                            <td style="text-align:right; color: {{ '#16a34a' if res.diff > 0 else '#dc2626' if res.diff < 0 else 'inherit' }}; font-weight:600;">
                                {{ "%+.1f"|format(res.diff) }}%
                            </td>
                            <td style="text-align:right; font-weight:bold; color: {{ '#10a37f' if res.sig != 'ns' else '#94a3b8' }};">
                                {{ res.sig }}
                            </td>
                        </tr>
                        {% endfor %}
                    </table>
                </div>

                <div>
                    <h2 style="font-size: 14px; margin-top:0;">Gemini vs. GPT Personal</h2>
                    <table>
                        <tr>
                            <th>Feature</th>
                            <th style="text-align:right;">Gem %</th>
                            <th style="text-align:right;">GPT %</th>
                            <th style="text-align:right;">Diff</th>
                            <th style="text-align:right;">Sig</th>
                        </tr>
                        {% for feat, res in ttests.gemini_vs_gpt_all.items() %}
                        <tr>
                            <td>{{ feat.replace('has_', '').replace('_', ' ') }}</td>
                            <td style="text-align:right;">{{ res.m1 }}%</td>
                            <td style="text-align:right;">{{ res.m2 }}%</td>
                            <td style="text-align:right; color: {{ '#16a34a' if res.diff > 0 else '#dc2626' if res.diff < 0 else 'inherit' }}; font-weight:600;">
                                {{ "%+.1f"|format(res.diff) }}%
                            </td>
                            <td style="text-align:right; font-weight:bold; color: {{ '#10a37f' if res.sig != 'ns' else '#94a3b8' }};">
                                {{ res.sig }}
                            </td>
                        </tr>
                        {% endfor %}
                    </table>
                </div>
            </div>
            {% endif %}
            </div>
"""
    if 'id="ttest-analysis-container"' not in content:
        content = content.replace('<div id="attachment-drift-container"', ttest_html + '\n            <div id="attachment-drift-container"')

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == "__main__":
    update_data_viewer()
    print('Successfully updated data_viewer.py with T-test analysis.')
