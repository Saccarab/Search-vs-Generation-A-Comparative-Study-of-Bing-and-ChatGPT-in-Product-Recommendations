import json
import os
import sqlite3
import hashlib
from urllib.parse import urlsplit, parse_qsl, urlencode, urlunsplit

def normalize_url_key(raw_url):
    if not raw_url: return ''
    u = raw_url.strip()
    if '://' not in u: u = 'https://' + u
    try:
        p = urlsplit(u)
        host = (p.netloc or '').lower()
        if host.startswith('www.'): host = host[4:]
        path = p.path or '/'
        if len(path) > 1 and path.endswith('/'): path = path[:-1]
        drop_exact = {'gclid','fbclid','msclkid','yclid','mc_cid','mc_eid','igshid'}
        kept=[]
        for k,v in parse_qsl(p.query, keep_blank_values=True):
            lk=k.lower()
            if lk.startswith('utm_') or lk in drop_exact: continue
            kept.append((k,v))
        q = urlencode(kept, doseq=True)
        return urlunsplit(('', host, path, q, '')).lstrip('/')
    except: return raw_url.strip().lower()

def short_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]

def main():
    db_path = 'geo_fresh.db'
    content_dir = 'data/fetched_content'
    output_csv = 'data/enrichment/browser_fetch_queue.csv'
    
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)

    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT DISTINCT url FROM citations WHERE url IS NOT NULL AND url != ''").fetchall()
    conn.close()
    
    db_urls = [r[0] for r in rows]
    
    # Check existing content
    existing_hashes = set()
    if os.path.isdir(content_dir):
        for fn in os.listdir(content_dir):
            if fn.endswith('.txt'):
                existing_hashes.add(fn[:-4])

    skip_domains = {
        'wikipedia.org','reddit.com','arxiv.org','github.com','youtube.com','youtu.be',
        'apple.com','apps.apple.com','microsoft.com','microsoftstore.com','chrome.google.com','chromewebstore.google.com','play.google.com',
        'facebook.com','instagram.com','twitter.com','x.com','linkedin.com'
    }

    queue = []
    for url in db_urls:
        key = normalize_url_key(url)
        if not key: continue
        
        # Skip common domains
        domain = key.split('/')[0].lower() if '/' in key else key.lower()
        if any(domain == sd or domain.endswith('.' + sd) for sd in skip_domains):
            continue
            
        h = short_hash(key)
        if h not in existing_hashes:
            queue.append(url)

    # Write to CSV for the browser tool
    with open(output_csv, 'w', encoding='utf-8') as f:
        f.write("url\n")
        for url in queue:
            f.write(f'"{url}"\n')

    print(f"Total URLs missing content: {len(queue)}")
    print(f"Queue saved to: {output_csv}")

if __name__ == "__main__":
    main()
