
import sqlite3
import math
import json
import csv
import os

def calculate_full_ttest():
    dna_path = 'data/enrichment/full_url_dna_database.csv'
    if not os.path.exists(dna_path):
        return {'error': 'DNA database not found'}

    url_features = {}
    with open(dna_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row.get('url')
            if url:
                url_features[url] = row

    conn = sqlite3.connect('geo_fresh.db')
    cursor = conn.cursor()
    
    # GPT Citations
    cursor.execute("SELECT account_type, url FROM citations")
    citations = cursor.fetchall()
    
    # Gemini Citations
    cursor.execute("SELECT account_type, url FROM bing_results WHERE account_type='gemini'")
    gemini_results = cursor.fetchall()
    conn.close()

    features = ['has_tables', 'has_numbered_lists', 'has_bullet_points', 'is_current_year_2026', 'has_clear_authorship']
    groups = {'enterprise': {}, 'personal': {}, 'gemini': {}}
    for feat in features:
        for k in groups: groups[k][feat] = []

    for acc, url in citations:
        feat_dict = url_features.get(url)
        if feat_dict and acc in groups:
            for feat in features:
                raw_val = feat_dict.get(feat)
                val = 1 if str(raw_val).lower() in ['1', 'true', 'yes', '1.0'] else 0
                groups[acc][feat].append(val)

    for acc, url in gemini_results:
        feat_dict = url_features.get(url)
        if feat_dict:
            for feat in features:
                raw_val = feat_dict.get(feat)
                val = 1 if str(raw_val).lower() in ['1', 'true', 'yes', '1.0'] else 0
                groups['gemini'][feat].append(val)

    def get_stats(data):
        n = len(data)
        if n == 0: return 0, 0, 0
        mean = sum(data) / n
        var = mean * (1 - mean)
        return n, mean, var

    def compare(g1_name, g2_name):
        comp_results = {}
        for feat in features:
            n1, m1, v1 = get_stats(groups[g1_name][feat])
            n2, m2, v2 = get_stats(groups[g2_name][feat])
            if n1 < 10 or n2 < 10: continue
            se = math.sqrt((v1/n1) + (v2/n2)) if (n1 > 0 and n2 > 0) else 0
            t_stat = (m1 - m2) / se if se > 0 else 0
            comp_results[feat] = {
                'm1': round(m1 * 100, 1),
                'm2': round(m2 * 100, 1),
                'diff': round((m1 - m2) * 100, 1),
                't': round(t_stat, 2),
                'sig': 'p<0.01' if abs(t_stat) > 2.58 else 'p<0.05' if abs(t_stat) > 1.96 else 'ns'
            }
        return comp_results

    return {
        'ent_vs_pers': compare('enterprise', 'personal'),
        'gemini_vs_gpt_all': compare('gemini', 'personal'),
        'counts': {k: len(groups[k][features[0]]) for k in groups}
    }

if __name__ == "__main__":
    res = calculate_full_ttest()
    with open('data/enrichment/feature_ttests.json', 'w') as f:
        json.dump(res, f, indent=2)
    print('T-test results saved. Counts:', res.get('counts'))
