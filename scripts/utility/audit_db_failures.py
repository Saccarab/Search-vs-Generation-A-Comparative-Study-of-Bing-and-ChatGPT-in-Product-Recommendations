import json
import os
import sqlite3

def normalize_url_key(raw_url):
    if not raw_url: return ''
    s = raw_url.strip().lower()
    if '://' in s: s = s.split('://',1)[1]
    if s.startswith('www.'): s=s[4:]
    return s.split('?',1)[0].rstrip('/')

def main():
    db_path = 'geo_fresh.db'
    jsonl_path = 'datapass/page_labels_gemini_v2.5.jsonl'
    
    if not os.path.exists(db_path):
        print(f"DB not found: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    # Use simple query to avoid quoting issues in terminal
    rows = conn.execute("SELECT DISTINCT url FROM citations").fetchall()
    conn.close()
    
    db_urls = [r[0] for r in rows if r[0]]
    db_keys = {normalize_url_key(u): u for u in db_urls}

    status = {} # key -> latest_ok_status
    if os.path.exists(jsonl_path):
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    d = json.loads(line)
                    url = d.get('url')
                    if not url: continue
                    k = normalize_url_key(url)
                    if k in db_keys:
                        status[k] = d.get('ok')
                except:
                    continue

    success_keys = [k for k, ok in status.items() if ok is True]
    failed_keys = [k for k, ok in status.items() if ok is False and k not in success_keys]
    never_keys = [k for k in db_keys if k not in status]

    print(f"--- DB URL STATUS AUDIT ---")
    print(f"Total Unique URLs in DB: {len(db_keys)}")
    print(f"Successfully Labeled: {len(success_keys)}")
    print(f"Currently FAILED (only failures, no success): {len(failed_keys)}")
    print(f"Never Attempted: {len(never_keys)}")
    
    if failed_keys:
        print("\nSample of DB URLs that are currently FAILED:")
        for k in failed_keys[:15]:
            print(f" - {db_keys[k]}")

if __name__ == "__main__":
    main()
