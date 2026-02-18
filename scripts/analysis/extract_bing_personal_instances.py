import sqlite3, json, os, pandas as pd
from collections import defaultdict

def norm_key(u):
    if not u: return ''
    u = u.strip().lower().replace('https://', '').replace('http://', '').replace('www.', '').split('?')[0].rstrip('/')
    return u

def load_jsonl_dna(paths):
    out = {}
    for p in paths:
        if not os.path.exists(p): continue
        with open(p, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    d = json.loads(line)
                    url = d.get('url') or (d.get('response') or {}).get('urls', {}).get('url')
                    if not url: continue
                    nk = norm_key(url)
                    resp = d.get('response', {})
                    dna = resp.get('urls', d)
                    out[nk] = dna
                except: pass
    return out

def main():
    dna_map = load_jsonl_dna(['datapass/page_labels_control_gpt5_mini.jsonl'])
    conn = sqlite3.connect('geo_fresh.db')
    cur = conn.cursor()

    # Get citations for personal
    cit_rows = cur.execute("SELECT run_id, url_normalized FROM citations WHERE account_type='personal'").fetchall()
    cited_map = defaultdict(set)
    for rid, nk in cit_rows:
        cited_map[rid].add(nk)

    # Get Bing Top 5 for personal
    serp_rows = cur.execute("SELECT run_id, query, position, url, url_normalized FROM bing_results WHERE account_type='personal' AND page_num=1 AND position<=5").fetchall()
    
    data = []
    for rid, q, pos, url, url_norm in serp_rows:
        nk = url_norm.strip().lower() if url_norm else norm_key(url)
        dna = dna_map.get(nk)
        if not dna or dna.get('type') != 'listicle':
            continue
        
        is_cited = nk in cited_map.get(rid, set())
        data.append({
            'run_id': rid,
            'query': q[:30],
            'rank': pos,
            'cited': 'YES' if is_cited else 'no',
            'url': url,
            'has_tables': dna.get('has_tables'),
            'has_numbered_lists': dna.get('has_numbered_lists'),
            'has_bullet_points': dna.get('has_bullet_points'),
            'has_pros_cons': dna.get('has_pros_cons'),
            'is_2026': dna.get('is_current_year_2026')
        })

    df = pd.DataFrame(data)
    output_path = 'data/enrichment/bing_personal_top5_listicle_instances.csv'
    df.to_csv(output_path, index=False)
    
    cited_only = df[df['cited'] == 'YES']
    print(f'Found {len(cited_only)} cited listicles in Bing Top 5.')
    print(f'Saved all {len(df)} menu instances to {output_path}')
    print('\nSample of Cited Instances:')
    print(cited_only[['rank', 'query', 'has_tables', 'has_pros_cons', 'url']].head(15).to_string(index=False))

if __name__ == "__main__":
    main()
