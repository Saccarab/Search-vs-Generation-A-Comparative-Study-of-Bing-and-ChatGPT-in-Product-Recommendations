import json
import sqlite3
import os

def normalize_url(url):
    if not url: return ""
    u = url.strip().lower()
    if "://" in u:
        u = u.split("://")[1]
    if u.startswith("www."):
        u = u[4:]
    return u.split("?")[0].rstrip("/")

def main():
    # 1. Get all unique URLs from DB (Cited, Additional, Rejected)
    conn = sqlite3.connect('geo_fresh.db')
    db_urls = [r[0] for r in conn.execute("SELECT DISTINCT url FROM citations WHERE url IS NOT NULL AND url != ''").fetchall()]
    conn.close()
    
    db_url_map = {normalize_url(u): u for u in db_urls}
    print(f"Unique URLs in DB: {len(db_url_map)}")

    # 2. Check page_labels_gemini.jsonl
    gemini_path = 'datapass/page_labels_gemini.jsonl'
    labeled_urls = set()
    if os.path.exists(gemini_path):
        with open(gemini_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    url = data.get('url')
                    is_ok = data.get('ok') is True
                    if url and is_ok:
                        labeled_urls.add(normalize_url(url))
                except:
                    continue
    
    print(f"Labeled URLs in Gemini JSONL: {len(labeled_urls)}")

    # 3. Intersection
    overlap = labeled_urls.intersection(db_url_map.keys())
    missing = set(db_url_map.keys()) - labeled_urls
    
    print(f"--- RESULTS ---")
    print(f"URLs in DB already labeled: {len(overlap)}")
    print(f"URLs in DB still MISSING labels: {len(missing)}")

if __name__ == "__main__":
    main()
