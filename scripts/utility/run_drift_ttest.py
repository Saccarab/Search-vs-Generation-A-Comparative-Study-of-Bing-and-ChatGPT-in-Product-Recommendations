"""
Drift T-Tests: Menu (all retrieved) vs Order (cited) for each condition.
Tests whether the selection drift for each Content DNA feature is statistically significant.

Produces tables like:
  Feature | Menu % | Order % | Drift (pp) | t-stat | p-value | sig

Conditions:
  - GPT Enterprise (listicles, product pages)
  - GPT Personal   (listicles, product pages)
  - Gemini          (listicles, product pages)

Uses Welch's two-sample t-test on binary feature vectors.
"""

import sqlite3
import csv
import math
import json
import os

DB_PATH = 'geo_fresh.db'
DNA_PATH = 'data/enrichment/full_url_dna_database_with_groups.csv'
GPT_DRIFT_PATH = 'data/enrichment/review_gpt_drift.csv'
GEMINI_DRIFT_PATH = 'data/enrichment/review_gemini_drift.csv'
OUTPUT_PATH = 'data/enrichment/drift_ttests.json'

# Features to test (binary 0/1 except freshness_cue_strength which is 0-5)
BINARY_FEATURES = [
    'has_tables',
    'has_numbered_lists',
    'has_bullet_points',
    'has_pros_cons',
    'has_clear_authorship',
    'has_sources_or_citations',
    'is_vendor_owned',
]

# Freshness: we binarize freshness_cue_strength >= 3 as "has strong freshness cues"
FRESHNESS_THRESHOLD = 3

CONTENT_TYPES = ['listicle', 'product_page']


def parse_binary(val):
    return 1 if str(val).strip().lower() in ['1', 'true', 'yes', '1.0'] else 0


def parse_freshness(val):
    try:
        return 1 if int(val) >= FRESHNESS_THRESHOLD else 0
    except (ValueError, TypeError):
        return 0


def welch_ttest(group_a, group_b):
    """Two-sample Welch's t-test for binary data. Returns t-stat, p-approx, significance label."""
    n1, n2 = len(group_a), len(group_b)
    if n1 < 10 or n2 < 10:
        return None

    m1 = sum(group_a) / n1
    m2 = sum(group_b) / n2

    # For binary data, variance = p*(1-p)
    v1 = m1 * (1 - m1)
    v2 = m2 * (1 - m2)

    se = math.sqrt(v1 / n1 + v2 / n2) if (v1 / n1 + v2 / n2) > 0 else 0
    if se == 0:
        return {
            'menu_pct': round(m2 * 100, 1),
            'order_pct': round(m1 * 100, 1),
            'drift_pp': round((m1 - m2) * 100, 1),
            'n_menu': n2,
            'n_order': n1,
            't_stat': 0.0,
            'sig': 'ns'
        }

    t = (m1 - m2) / se

    # Welch-Satterthwaite degrees of freedom
    num = (v1 / n1 + v2 / n2) ** 2
    denom = ((v1 / n1) ** 2 / max(n1 - 1, 1)) + ((v2 / n2) ** 2 / max(n2 - 1, 1))
    df = num / denom if denom > 0 else min(n1, n2) - 1

    # Significance thresholds (two-tailed)
    if abs(t) > 3.291:
        sig = 'p<0.001'
    elif abs(t) > 2.576:
        sig = 'p<0.01'
    elif abs(t) > 1.960:
        sig = 'p<0.05'
    else:
        sig = 'ns'

    return {
        'menu_pct': round(m2 * 100, 1),
        'order_pct': round(m1 * 100, 1),
        'drift_pp': round((m1 - m2) * 100, 1),
        'n_menu': n2,
        'n_order': n1,
        't_stat': round(t, 3),
        'df': round(df, 1),
        'sig': sig
    }


def get_feature_vector(row, feature):
    if feature == 'freshness_cue_strength':
        return parse_freshness(row.get(feature, '0'))
    return parse_binary(row.get(feature, '0'))


def run_drift_test(rows, content_type, features):
    """Split rows by cited (Order) vs not-cited (Menu), test each feature."""
    ct_rows = [r for r in rows if r.get('type') == content_type]
    order = [r for r in ct_rows if str(r.get('cited', '0')).strip() == '1']
    menu = [r for r in ct_rows if str(r.get('cited', '0')).strip() == '0']

    results = {}
    for feat in features:
        order_vals = [get_feature_vector(r, feat) for r in order]
        menu_vals = [get_feature_vector(r, feat) for r in menu]
        res = welch_ttest(order_vals, menu_vals)
        if res:
            results[feat] = res

    return results, len(order), len(menu)


def run_gpt_split(content_type, features):
    """GPT needs Enterprise/Personal split via the database."""
    # Load DNA features by URL
    url_features = {}
    with open(DNA_PATH, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            url = row.get('url', '')
            if url:
                url_features[url] = row

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    results = {}
    for account_type in ['enterprise', 'personal']:
        # Order = cited URLs
        cited_urls = set(r[0] for r in c.execute(
            'SELECT DISTINCT url FROM citations WHERE account_type=? AND citation_type="cited"',
            (account_type,)).fetchall())

        # Menu = all URLs (cited + additional + rejected)
        all_urls = set(r[0] for r in c.execute(
            'SELECT DISTINCT url FROM citations WHERE account_type=?',
            (account_type,)).fetchall())

        # Build rows with cited flag and DNA features
        rows = []
        for url in all_urls:
            feat = url_features.get(url)
            if not feat:
                continue
            if feat.get('type') != content_type:
                continue
            row = dict(feat)
            row['cited'] = '1' if url in cited_urls else '0'
            rows.append(row)

        order = [r for r in rows if r['cited'] == '1']
        menu = [r for r in rows if r['cited'] == '0']

        feat_results = {}
        for feat_name in features:
            order_vals = [get_feature_vector(r, feat_name) for r in order]
            menu_vals = [get_feature_vector(r, feat_name) for r in menu]
            res = welch_ttest(order_vals, menu_vals)
            if res:
                feat_results[feat_name] = res

        results[account_type] = {
            'features': feat_results,
            'n_order': len(order),
            'n_menu': len(menu)
        }

    conn.close()
    return results


def main():
    all_features = BINARY_FEATURES + ['freshness_cue_strength']

    output = {}

    # --- GPT Enterprise & Personal (from DB + DNA CSV) ---
    for ct in CONTENT_TYPES:
        gpt_results = run_gpt_split(ct, all_features)
        output[f'gpt_enterprise_{ct}'] = gpt_results['enterprise']
        output[f'gpt_personal_{ct}'] = gpt_results['personal']

    # --- Gemini (from review_gemini_drift.csv) ---
    with open(GEMINI_DRIFT_PATH, 'r', encoding='utf-8') as f:
        gemini_rows = list(csv.DictReader(f))

    for ct in CONTENT_TYPES:
        feat_results, n_order, n_menu = run_drift_test(gemini_rows, ct, all_features)
        output[f'gemini_{ct}'] = {
            'features': feat_results,
            'n_order': n_order,
            'n_menu': n_menu
        }

    # Save
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)

    # Print summary tables
    for condition, data in output.items():
        print(f'\n{"=" * 70}')
        print(f'  {condition.upper()}  (Order N={data["n_order"]}, Menu N={data["n_menu"]})')
        print(f'{"=" * 70}')
        print(f'  {"Feature":<28} {"Menu%":>7} {"Order%":>7} {"Drift":>8} {"t":>8} {"Sig":>10}')
        print(f'  {"-" * 68}')
        for feat, res in data['features'].items():
            label = feat.replace('has_', '').replace('is_', '').replace('_', ' ')
            if feat == 'freshness_cue_strength':
                label = 'freshness (>=3)'
            print(f'  {label:<28} {res["menu_pct"]:>6.1f}% {res["order_pct"]:>6.1f}% {res["drift_pp"]:>+7.1f}pp {res["t_stat"]:>7.2f}  {res["sig"]:>9}')


if __name__ == '__main__':
    main()
