"""
Fetch missing content for citations directly from geo_fresh.db.

Behavior:
1. Identifies citations that are missing content in the `urls` table.
2. Inserts missing URLs into `urls` table if they don't exist.
3. Fetches HTML, strips to text, and saves to `data/content/citations/`.
4. Updates `urls` table with content_path, word_count, etc.
"""

import sqlite3
import requests
import re
import os
import hashlib
import time
import datetime as dt
from pathlib import Path
from urllib.parse import urlparse

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

DB_PATH = 'geo_fresh.db'
CONTENT_ROOT = Path('data/content/citations')
USER_AGENT = "Mozilla/5.0 (compatible; GEOThesisBot/0.1)"

RE_SCRIPT_STYLE = re.compile(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>")
RE_TAGS = re.compile(r"<[^>]+>")
RE_SPACE = re.compile(r"[\s]+")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def utc_now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

def extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc
    except:
        return ""

def strip_html_to_text(html: str) -> str:
    if not html: return ""
    if BeautifulSoup:
        try:
            soup = BeautifulSoup(html, "html.parser")
            for el in soup.select("script, style, noscript, nav, header, footer, aside"):
                el.decompose()
            text = soup.get_text(" ", strip=True)
            return re.sub(r"\s+", " ", text).strip()
        except:
            pass
    
    # Fallback
    text = RE_SCRIPT_STYLE.sub(" ", html)
    text = RE_TAGS.sub(" ", text)
    return RE_SPACE.sub(" ", text).strip()

def fetch_and_save(url: str) -> dict:
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        if resp.status_code != 200:
            return {"error": f"Status {resp.status_code}"}
        
        text = strip_html_to_text(resp.text)
        if len(text) < 100:
            return {"error": "Content too short"}
            
        file_hash = short_hash(url)
        file_name = f"{file_hash}.txt"
        file_path = CONTENT_ROOT / file_name
        
        CONTENT_ROOT.mkdir(parents=True, exist_ok=True)
        file_path.write_text(text, encoding="utf-8", errors="ignore")
        
        return {
            "content_path": str(file_path),
            "word_count": len(text.split()),
            "domain": extract_domain(url),
            "status": "success"
        }
    except Exception as e:
        return {"error": str(e)}

def main():
    conn = get_db()
    
    # 1. Ensure all citations are in urls table
    print("Syncing citations to urls table...")
    conn.execute('''
        INSERT OR IGNORE INTO urls (url, domain, fetched_at)
        SELECT DISTINCT url, '', ? FROM citations
    ''', (utc_now_iso(),))
    conn.commit()
    
    # 2. Find targets
    targets = conn.execute('''
        SELECT u.url 
        FROM urls u
        JOIN citations c ON u.url = c.url
        WHERE u.content_path IS NULL OR u.content_path = ''
        GROUP BY u.url
    ''').fetchall()
    
    print(f"Found {len(targets)} citations missing content.")
    
    success = 0
    failed = 0
    
    for i, row in enumerate(targets):
        url = row['url']
        print(f"[{i+1}/{len(targets)}] Fetching: {url}")
        
        res = fetch_and_save(url)
        
        if res.get("status") == "success":
            conn.execute('''
                UPDATE urls 
                SET content_path = ?, content_word_count = ?, domain = ?, fetched_at = ?
                WHERE url = ?
            ''', (res['content_path'], res['word_count'], res['domain'], utc_now_iso(), url))
            conn.commit()
            success += 1
        else:
            print(f"  Failed: {res.get('error')}")
            conn.execute('UPDATE urls SET missing_reason = ?, fetched_at = ? WHERE url = ?', 
                        (res.get('error'), utc_now_iso(), url))
            conn.commit()
            failed += 1
            
        time.sleep(0.5)

    print(f"\nDone. Success: {success}, Failed: {failed}")

if __name__ == "__main__":
    main()
