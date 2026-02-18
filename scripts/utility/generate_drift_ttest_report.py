"""
Generate full drift t-test report and URL list files.
Outputs to data/enrichment/ttest_results/

Methodology (per-run, no overlap):
  For each run, split SERP results (filtered by content type) into two groups:
    - Cited-from-SERP: URLs in the SERP that the model cited in that run
    - Not-Cited-from-SERP: URLs in the SERP that the model did NOT cite in that run
  Pool across all runs and run Welch's t-test on each binary DNA feature.

  A URL may contribute to multiple runs (once per run it appears in).
  Each run is an independent selection event: in run A the model may cite URL X,
  in run B it may not, even though X appeared in both SERPs.

  GPT: SERP from Bing Page 1 (enterprise + personal) and Google Top-10 (personal).
       Citations from geo_fresh.db citations table.
  Gemini: SERP from Google Top-10 (fan-out queries). Citations reconstructed from
          raw Gemini responses via master_bundle.json (Vertex grounding chunks).
"""
import sqlite3, csv, math, os, json

FRESHNESS_THRESHOLD = 3
OUT_DIR = 'data/enrichment/ttest_results'
os.makedirs(OUT_DIR, exist_ok=True)

DB_PATH = 'geo_fresh.db'
DNA_PATH = 'data/enrichment/full_url_dna_database_with_groups.csv'
GEMINI_DRIFT_PATH = 'data/enrichment/review_gemini_drift.csv'
GEMINI_SERPAPI_DIR = 'data/serpapi_google_results_gemini'

def parse_bin(v):
    return 1 if str(v).strip().lower() in ['1','true','yes','1.0'] else 0

def parse_fresh(v):
    try: return 1 if int(v) >= FRESHNESS_THRESHOLD else 0
    except: return 0

def welch(a, b):
    n1, n2 = len(a), len(b)
    if n1 < 10 or n2 < 10:
        return None
    m1, m2 = sum(a)/n1, sum(b)/n2
    v1, v2 = m1*(1-m1), m2*(1-m2)
    denom = v1/n1 + v2/n2
    se = math.sqrt(denom) if denom > 0 else 0
    if se == 0:
        return {'g1_pct': round(m1*100,1), 'g2_pct': round(m2*100,1), 'drift': 0, 't': 0, 'sig': 'ns'}
    t = (m1 - m2) / se
    if abs(t) > 3.291: sig = 'p<0.001'
    elif abs(t) > 2.576: sig = 'p<0.01'
    elif abs(t) > 1.960: sig = 'p<0.05'
    else: sig = 'ns'
    return {'g1_pct': round(m1*100,1), 'g2_pct': round(m2*100,1),
            'drift': round((m1-m2)*100,1), 't': round(t,2), 'sig': sig}

FEATS = [
    'has_tables', 'has_numbered_lists', 'has_bullet_points', 'has_pros_cons',
    'has_clear_authorship', 'has_sources_or_citations', 'is_vendor_owned',
    'freshness_cue_strength'
]
FEAT_LABELS = {
    'has_tables': 'Tables',
    'has_numbered_lists': 'Numbered Lists',
    'has_bullet_points': 'Bullet Points',
    'has_pros_cons': 'Pros/Cons',
    'has_clear_authorship': 'Clear Authorship',
    'has_sources_or_citations': 'Sources/Citations',
    'is_vendor_owned': 'Vendor Owned',
    'freshness_cue_strength': 'Freshness (>=3)'
}

def get_feat_vals(rows, feat):
    if feat == 'freshness_cue_strength':
        return [parse_fresh(r.get(feat, '0')) for r in rows]
    return [parse_bin(r.get(feat, '0')) for r in rows]

def main():
    # Load DNA
    url_features = {}
    with open(DNA_PATH, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            url_features[row.get('url', '')] = row

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    all_tests = []
    url_lists = {}

    def run_test(title, g1_rows, g2_rows, g1_label, g2_label, g1_key=None, g2_key=None):
        result = {
            'title': title, 'g1_label': g1_label, 'g2_label': g2_label,
            'g1_n': len(g1_rows), 'g2_n': len(g2_rows), 'features': []
        }
        for feat in FEATS:
            a = get_feat_vals(g1_rows, feat)
            b = get_feat_vals(g2_rows, feat)
            res = welch(a, b)
            if res:
                res['feature'] = FEAT_LABELS[feat]
                result['features'].append(res)
        all_tests.append(result)
        if g1_key:
            url_lists[g1_key] = sorted(set(r.get('url', '') for r in g1_rows))
        if g2_key:
            url_lists[g2_key] = sorted(set(r.get('url', '') for r in g2_rows))

    # ================ GPT CITED vs ADDITIONAL ================
    # Citation-stage drift: both groups were surfaced by the model.
    # Cited = appeared in response text. Additional = supplementary sources.
    # Per-run counting (same URL in multiple runs counts multiple times).
    for acct in ['enterprise', 'personal']:
        acct_cap = acct.capitalize()
        cited_raw = c.execute(
            'SELECT url FROM citations WHERE account_type=? AND citation_type="cited"', (acct,)
        ).fetchall()
        addl_raw = c.execute(
            'SELECT url FROM citations WHERE account_type=? AND citation_type="additional"', (acct,)
        ).fetchall()
        for ct in ['listicle', 'product_page']:
            ct_label = 'Listicle' if ct == 'listicle' else 'Product Page'
            cited = [url_features[r[0]] for r in cited_raw if url_features.get(r[0], {}).get('type') == ct]
            addl = [url_features[r[0]] for r in addl_raw if url_features.get(r[0], {}).get('type') == ct]
            run_test(
                f'GPT {acct_cap} {ct_label} -- Cited vs Additional',
                cited, addl, 'Cited', 'Additional',
                f'gpt_{acct}_cited_{ct}s', f'gpt_{acct}_additional_{ct}s'
            )

    # ================ GPT PER-RUN TESTS ================
    # For each run, split SERP into cited-from-SERP vs not-cited-from-SERP.
    # No overlap: every SERP URL in a given run is in exactly one group.
    for acct in ['enterprise', 'personal']:
        acct_cap = acct.capitalize()
        runs = [r[0] for r in c.execute(
            'SELECT DISTINCT run_id FROM bing_results WHERE account_type=?', (acct,)
        ).fetchall()]

        for ct in ['listicle', 'product_page']:
            ct_label = 'Listicle' if ct == 'listicle' else 'Product Page'

            # --- Bing P1 ---
            bing_cited = []
            bing_not_cited = []
            for run in runs:
                serp_urls = [r[0] for r in c.execute(
                    'SELECT url FROM bing_results WHERE run_id=? AND position<=10', (run,)
                ).fetchall()]
                serp_typed = [u for u in serp_urls if url_features.get(u, {}).get('type') == ct]
                cited_urls = set(r[0] for r in c.execute(
                    'SELECT url FROM citations WHERE run_id=? AND citation_type="cited"', (run,)
                ).fetchall())
                for u in serp_typed:
                    if u in cited_urls:
                        bing_cited.append(url_features[u])
                    else:
                        bing_not_cited.append(url_features[u])

            run_test(
                f'GPT {acct_cap} {ct_label} -- Cited vs Not-Cited (Bing P1)',
                bing_cited, bing_not_cited, 'Cited', 'Not-Cited',
                f'gpt_{acct}_bing_cited_{ct}s', f'gpt_{acct}_bing_notcited_{ct}s'
            )

            # --- Google T10 (Personal only) ---
            if acct == 'personal':
                google_cited = []
                google_not_cited = []
                google_runs = [r[0] for r in c.execute(
                    'SELECT DISTINCT chatgpt_run_id FROM google_results WHERE account_type="personal"'
                ).fetchall()]
                for grun in google_runs:
                    serp_urls = [r[0] for r in c.execute(
                        'SELECT url FROM google_results WHERE chatgpt_run_id=? AND account_type="personal" AND position<=10', (grun,)
                    ).fetchall()]
                    serp_typed = [u for u in serp_urls if url_features.get(u, {}).get('type') == ct]
                    cite_run = grun + '_personal'
                    cited_urls = set(r[0] for r in c.execute(
                        'SELECT url FROM citations WHERE run_id=? AND citation_type="cited"', (cite_run,)
                    ).fetchall())
                    for u in serp_typed:
                        if u in cited_urls:
                            google_cited.append(url_features[u])
                        else:
                            google_not_cited.append(url_features[u])

                run_test(
                    f'GPT Personal {ct_label} -- Cited vs Not-Cited (Google T10)',
                    google_cited, google_not_cited, 'Cited', 'Not-Cited',
                    f'gpt_personal_google_cited_{ct}s', f'gpt_personal_google_notcited_{ct}s'
                )

    # ================ GEMINI vs GOOGLE SERP ================
    # Gemini data is per-unique-URL (no run granularity).
    with open(GEMINI_DRIFT_PATH, 'r', encoding='utf-8') as f:
        gem = list(csv.DictReader(f))
    # Deduplicated to match per-unique-URL cited side.
    gemini_serp_urls = set()
    if os.path.isdir(GEMINI_SERPAPI_DIR):
        for fname in os.listdir(GEMINI_SERPAPI_DIR):
            if not fname.endswith('.json'):
                continue
            with open(os.path.join(GEMINI_SERPAPI_DIR, fname), 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                except:
                    continue
            for r in data.get('organic_results', []):
                pos = r.get('position', 0)
                url = r.get('link', '')
                if url and pos <= 10:
                    gemini_serp_urls.add(url)
    gemini_serp_urls = list(gemini_serp_urls)

    for ct in ['listicle', 'product_page']:
        ct_label = 'Listicle' if ct == 'listicle' else 'Product Page'
        gem_cited = [r for r in gem if r['type'] == ct and r['cited'] == '1']
        google_menu = [url_features[u] for u in gemini_serp_urls
                       if url_features.get(u, {}).get('type') == ct]
        run_test(
            f'Gemini {ct_label} -- Cited vs Google Top-10',
            gem_cited, google_menu, 'Cited', 'Google T10',
            None, f'gemini_google_t10_{ct}s'
        )

    conn.close()

    # ================ WRITE REPORT ================
    lines = []
    lines.append('=' * 80)
    lines.append('CONTENT DNA SELECTION DRIFT -- T-TEST RESULTS')
    lines.append('=' * 80)
    lines.append('')
    lines.append('Method: Welch\'s two-sample t-test on binary DNA features')
    lines.append('')
    lines.append('Unit of observation (GPT):')
    lines.append('  Per-run, no overlap. For each run, every SERP URL (filtered by')
    lines.append('  content type) is classified as either Cited or Not-Cited in that run.')
    lines.append('  A URL may appear in multiple runs; each is an independent event.')
    lines.append('')
    lines.append('Unit of observation (Gemini):')
    lines.append('  Per-unique-URL. Gemini data lacks run-level granularity,')
    lines.append('  so each URL appears exactly once as Cited or Non-Cited.')
    lines.append('  Google SERP is also deduplicated for consistency.')
    lines.append('')
    lines.append('Freshness: binarized at freshness_cue_strength >= 3')
    lines.append('Source: geo_fresh.db + full_url_dna_database_with_groups.csv')
    lines.append('')
    lines.append('TESTS PERFORMED:')
    lines.append('  1. GPT Cited vs Additional (citation-stage, per-run)')
    lines.append('     Both groups surfaced by the model. Cited = in response text.')
    lines.append('     Additional = supplementary sources shown alongside response.')
    lines.append('  2-3. GPT Cited vs Not-Cited from SERP (per-run, no overlap)')
    lines.append('     For each run, split SERP into Cited vs Not-Cited.')
    lines.append('     Enterprise: vs Bing Page 1')
    lines.append('     Personal:   vs Bing Page 1 AND vs Google Top-10')
    lines.append('  4. Gemini Cited vs Google Top-10 (deduplicated, per-unique-URL)')
    lines.append('')

    section_keys = [
        'Cited vs Additional',
        'Bing P1',
        'Google T10',
        'Cited vs Google Top-10'
    ]
    section_map = {k: [] for k in section_keys}
    for test in all_tests:
        if 'Cited vs Additional' in test['title']:
            section_map['Cited vs Additional'].append(test)
        elif 'Bing P1' in test['title']:
            section_map['Bing P1'].append(test)
        elif 'Google T10' in test['title']:
            section_map['Google T10'].append(test)
        elif 'Google Top-10' in test['title']:
            section_map['Cited vs Google Top-10'].append(test)

    section_titles = {
        'Cited vs Additional': 'SECTION 1: GPT CITED vs ADDITIONAL (Citation-Stage Selection)',
        'Bing P1': 'SECTION 2: GPT CITED vs NOT-CITED FROM BING PAGE 1 (Per-Run)',
        'Google T10': 'SECTION 3: GPT PERSONAL CITED vs NOT-CITED FROM GOOGLE TOP-10 (Per-Run)',
        'Cited vs Google Top-10': 'SECTION 4: GEMINI CITED vs GOOGLE TOP-10 (Per-Unique-URL)'
    }

    for key, tests in section_map.items():
        if not tests:
            continue
        lines.append('')
        lines.append('#' * 80)
        lines.append(f'  {section_titles[key]}')
        lines.append('#' * 80)

        for test in tests:
            lines.append('')
            lines.append('-' * 80)
            lines.append(f'  {test["title"]}')
            lines.append(f'  {test["g1_label"]} N = {test["g1_n"]:,}    '
                         f'{test["g2_label"]} N = {test["g2_n"]:,}')
            lines.append('-' * 80)
            lines.append(f'  {"Feature":<24} '
                         f'{test["g2_label"]+"%":>10} '
                         f'{test["g1_label"]+"%":>10} '
                         f'{"Drift":>10} '
                         f'{"t-stat":>10} '
                         f'{"Sig":>12}')
            lines.append(f'  {"─"*76}')
            for feat in test['features']:
                star = ' ***' if feat['sig'] == 'p<0.001' else ' **' if feat['sig'] == 'p<0.01' else ' *' if feat['sig'] == 'p<0.05' else ''
                lines.append(
                    f'  {feat["feature"]:<24} '
                    f'{feat["g2_pct"]:>9.1f}% '
                    f'{feat["g1_pct"]:>9.1f}% '
                    f'{feat["drift"]:>+9.1f}pp '
                    f'{feat["t"]:>9.2f}  '
                    f'{feat["sig"]:>9}{star}'
                )

    lines.append('')
    lines.append('=' * 80)
    lines.append('KEY: *** p<0.001   ** p<0.01   * p<0.05   ns = not significant')
    lines.append('=' * 80)
    lines.append('')
    lines.append('INTERPRETATION NOTES:')
    lines.append('')
    lines.append('Section 1 (Cited vs Additional):')
    lines.append('  Both groups were surfaced by the model, so drift isolates the final')
    lines.append('  citation preference from an already-filtered pool. Per-run counting.')
    lines.append('')
    lines.append('Sections 2-3 (GPT Per-Run, SERP-based):')
    lines.append('  Zero overlap between groups. For each run, every SERP listicle/product')
    lines.append('  page is either Cited or Not-Cited. The same URL contributes once per')
    lines.append('  run it appears in (independent selection events). Drift measures the')
    lines.append('  structural preference ChatGPT exhibits when choosing which SERP results')
    lines.append('  to cite.')
    lines.append('')
    lines.append('Section 4 (Gemini vs Google SERP):')
    lines.append('  Per-unique-URL. Compares what Gemini cited vs what appeared in the')
    lines.append('  Google SERP for the same fan-out queries (deduplicated).')
    lines.append('  Gemini lacks an "additional" citation category, so only SERP-level')
    lines.append('  comparison is possible.')

    report_path = os.path.join(OUT_DIR, 'drift_ttest_report.txt')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f'Report: {report_path}')

    # ================ WRITE URL LISTS ================
    for key, urls in url_lists.items():
        fpath = os.path.join(OUT_DIR, f'urls_{key}.txt')
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(f'# {key}\n')
            f.write(f'# {len(urls)} unique URLs\n')
            f.write(f'#\n')
            for u in urls:
                f.write(u + '\n')
        print(f'  {fpath} ({len(urls)} URLs)')

    print(f'\nDone: {len(all_tests)} tests, {len(url_lists)} URL lists.')

if __name__ == '__main__':
    main()
