import hashlib
import os
import sqlite3
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


SKIP_DOMAINS = {
    "wikipedia.org",
    "reddit.com",
    "arxiv.org",
    "github.com",
    "youtube.com",
    "youtu.be",
    "apple.com",
    "apps.apple.com",
    "microsoft.com",
    "microsoftstore.com",
    "chrome.google.com",
    "chromewebstore.google.com",
    "play.google.com",
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "linkedin.com",
}


def normalize_url_key(raw_url: str) -> str:
    """Match the Node fetcher normalization for hashing."""
    if not raw_url or not isinstance(raw_url, str):
        return ""
    url = raw_url.strip()
    if not url:
        return ""
    if "://" not in url:
        url = "https://" + url
    try:
        p = urlsplit(url)
        host = (p.netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        path = p.path or "/"
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]
        drop_exact = {"gclid", "fbclid", "msclkid", "yclid", "mc_cid", "mc_eid", "igshid"}
        kept = []
        for k, v in parse_qsl(p.query, keep_blank_values=True):
            lk = k.lower()
            if lk.startswith("utm_") or lk in drop_exact:
                continue
            kept.append((k, v))
        q = urlencode(kept, doseq=True)
        return urlunsplit(("", host, path, q, "")).lstrip("/")
    except Exception:
        # fallback: crude normalization
        s = raw_url.strip().lower()
        if "://" in s:
            s = s.split("://", 1)[1]
        if s.startswith("www."):
            s = s[4:]
        return s.split("?", 1)[0].rstrip("/")


def short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def domain_from_key(key: str) -> str:
    return (key.split("/", 1)[0] if key else "").lower()


def is_skipped_domain(domain: str) -> bool:
    d = (domain or "").lower().lstrip(".")
    return any(d == sd or d.endswith("." + sd) for sd in SKIP_DOMAINS)


def main() -> None:
    db_path = "geo_fresh.db"
    content_dir = os.path.join("data", "fetched_content")

    conn = sqlite3.connect(db_path)
    urls = [r[0] for r in conn.execute("SELECT DISTINCT url FROM citations WHERE url IS NOT NULL AND url != ''").fetchall()]
    conn.close()

    existing = set()
    if os.path.isdir(content_dir):
        for fn in os.listdir(content_dir):
            if fn.endswith(".txt"):
                existing.add(fn[:-4])

    need = 0
    have = 0
    missing_samples = []

    for u in urls:
        k = normalize_url_key(u)
        if not k:
            continue
        dom = domain_from_key(k)
        if is_skipped_domain(dom):
            continue
        need += 1
        h = short_hash(k)
        if h in existing:
            have += 1
        else:
            if len(missing_samples) < 25:
                missing_samples.append(u)

    print("--- CONTENT FETCH COVERAGE (DB URLs) ---")
    print(f"Unique DB URLs: {len(urls)}")
    print(f"After skip domains: {need}")
    print(f"Have local .txt: {have}")
    print(f"Missing local .txt: {need - have}")
    if missing_samples:
        print("Missing sample URLs:")
        for s in missing_samples:
            print(f" - {s}")


if __name__ == "__main__":
    main()

