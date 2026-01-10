"""
URL enrichment (deterministic + optional LLM).

Target columns (your schema):
  url, type, domain, content_word_count, has_table, content_format,
  has_schema_markup, tone, readability_score, promotional_intensity_score, freshness_date

Design:
  - Deterministic fields are computed locally from fetched HTML + extracted text.
  - Subjective fields (type/content_format/tone/promo) can be filled via Gemini (optional).

Typical usage (deterministic only):
  python scripts/enrich_urls.py --input bing_results_2026-01-02_clean_top30.csv --url-col url --output urls_enriched.csv --drop-html

With Gemini (requires env var GEMINI_API_KEY):
  python scripts/enrich_urls.py --input urls.csv --url-col url --output urls_enriched.csv --use-gemini
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit, urlparse

import requests


# ----------------------------
# URL normalization for joins
# ----------------------------

TRACKING_PARAM_PREFIXES = ("utm_",)
TRACKING_PARAMS_EXACT = {
    "gclid",
    "fbclid",
    "msclkid",
    "yclid",
    "mc_cid",
    "mc_eid",
    "igshid",
    "ref",
    "ref_src",
    "spm",
}


def normalize_url_key(raw_url: str) -> str:
    """
    URL key for joins/deduping.
    - Lowercase host
    - Remove scheme and leading www.
    - Drop fragment
    - Remove trailing slash (except root)
    - Remove common tracking params (utm_*, gclid, fbclid, ...)

    NOTE: Keeps non-tracking query params to avoid over-merging.
    """
    if not raw_url or not isinstance(raw_url, str):
        return ""

    url = raw_url.strip()
    if not url:
        return ""

    if "://" not in url:
        url = "https://" + url

    parts = urlsplit(url)
    host = (parts.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]

    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]

    kept: List[Tuple[str, str]] = []
    for k, v in parse_qsl(parts.query, keep_blank_values=True):
        lk = k.lower()
        if any(lk.startswith(p) for p in TRACKING_PARAM_PREFIXES):
            continue
        if lk in TRACKING_PARAMS_EXACT:
            continue
        kept.append((k, v))
    query = urlencode(kept, doseq=True)

    rebuilt = urlunsplit(("", host, path, query, ""))  # fragment dropped
    return rebuilt.lstrip("/")


def get_domain(raw_url: str) -> str:
    if not isinstance(raw_url, str) or not raw_url.strip():
        return ""
    try:
        u = raw_url.strip()
        if "://" not in u:
            u = "https://" + u
        parsed = urlparse(u)
        d = parsed.netloc.lower()
        if d.startswith("www."):
            d = d[4:]
        return d
    except Exception:
        return ""


def short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ----------------------------
# HTML -> text + features
# ----------------------------

RE_TAGS = re.compile(r"<[^>]+>")
RE_SCRIPT_STYLE = re.compile(r"(?is)<(script|style|noscript)[^>]*>.*?</\\1>")
RE_SPACE = re.compile(r"\\s+")


def strip_html_to_text(html: str) -> str:
    if not html:
        return ""
    html2 = RE_SCRIPT_STYLE.sub(" ", html)
    txt = RE_TAGS.sub(" ", html2)
    txt = RE_SPACE.sub(" ", txt).strip()
    return txt


def count_words(text: str) -> int:
    if not text:
        return 0
    # Keep letters/numbers; split on whitespace
    tokens = re.findall(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?", text)
    return len(tokens)


def has_table_from_html(html: str) -> bool:
    return "<table" in (html or "").lower()

def detect_pros_cons(html: str, text: str) -> Tuple[bool, float]:
    """
    Deterministic heuristic for whether a page contains a Pros/Cons section.
    Returns (has_pros_cons, score_0_to_1).

    We look for common headings/labels and nearby pairing of pros + cons.
    This is intentionally conservative to reduce false positives.
    """
    h = (html or "").lower()
    t = (text or "").lower()
    if not h and not t:
        return False, 0.0

    score = 0.0

    # Strong signal: explicit "pros" and "cons" headings/labels in HTML
    if re.search(r"(>\\s*pros\\s*<|>\\s*cons\\s*<)", h):
        score += 0.45

    # Common synonyms
    if re.search(r"(advantages\\b|benefits\\b)\\s*(?:and|&)\\s*(disadvantages\\b|limitations\\b)", t):
        score += 0.25

    # Look for nearby occurrence of both words in text (within ~250 chars)
    # This catches "Pros: ... Cons: ..." patterns.
    idx_pros = t.find("pros")
    idx_cons = t.find("cons")
    if idx_pros != -1 and idx_cons != -1 and abs(idx_pros - idx_cons) <= 250:
        score += 0.35

    # List markup hints: classes/ids containing pros/cons
    if re.search(r'(class|id)=["\'][^"\']*(pros|cons)[^"\']*["\']', h):
        score += 0.20

    score = max(0.0, min(1.0, score))
    return score >= 0.6, score

def detect_comparison_table(html: str) -> Tuple[bool, float]:
    """
    Heuristic: detect listicle-style comparison tables vs generic tables.
    Returns (has_comparison_table, score_0_to_1).

    Signals (loosely):
    - table headers mention comparison-ish terms (price, rating, pros, cons, features)
    - multiple product-ish columns/rows (e.g., lots of <tr>)
    - CSS classes/ids containing 'compare', 'comparison', 'vs', 'pricing-table'
    """
    if not html:
        return False, 0.0

    h = html.lower()
    if "<table" not in h:
        return False, 0.0

    score = 0.0

    # Structure signals
    tr_count = h.count("<tr")
    th_count = h.count("<th")
    if tr_count >= 6:
        score += 0.25
    if th_count >= 4:
        score += 0.20

    # Keyword signals (headers / nearby text)
    keywords = [
        "comparison",
        "compare",
        "vs",
        "price",
        "pricing",
        "rating",
        "score",
        "features",
        "feature",
        "pros",
        "cons",
        "best for",
    ]
    kw_hits = sum(1 for k in keywords if k in h)
    if kw_hits >= 4:
        score += 0.35
    elif kw_hits >= 2:
        score += 0.20

    # Class/id hints
    if re.search(r'(class|id)=["\'][^"\']*(comparison|compare|vs|pricing[-_ ]table)[^"\']*["\']', h):
        score += 0.25

    score = max(0.0, min(1.0, score))
    return score >= 0.6, score


def has_schema_markup_from_html(html: str) -> bool:
    h = (html or "").lower()
    if 'type="application/ld+json"' in h:
        return True
    # Microdata / RDFa hints
    if "itemscope" in h and "itemtype" in h:
        return True
    if "typeof=" in h and "property=" in h:
        return True
    return False


def extract_freshness_date(html: str) -> str:
    """
    Best-effort extraction of a date-ish signal.
    Returns ISO date string (YYYY-MM-DD) if found else "".
    """
    if not html:
        return ""

    # Prefer common meta tags
    patterns = [
        r'property=["\']article:published_time["\']\\s+content=["\']([^"\']+)["\']',
        r'property=["\']article:modified_time["\']\\s+content=["\']([^"\']+)["\']',
        r'name=["\']date["\']\\s+content=["\']([^"\']+)["\']',
        r'name=["\']pubdate["\']\\s+content=["\']([^"\']+)["\']',
        r'name=["\']publish_date["\']\\s+content=["\']([^"\']+)["\']',
        r'name=["\']lastmod["\']\\s+content=["\']([^"\']+)["\']',
        r'http-equiv=["\']last-modified["\']\\s+content=["\']([^"\']+)["\']',
    ]

    lower = html.lower()
    for pat in patterns:
        m = re.search(pat, lower, flags=re.IGNORECASE)
        if m:
            return _parse_date_to_iso(m.group(1))

    # JSON-LD datePublished/dateModified (best-effort regex)
    m = re.search(r'"datePublished"\\s*:\\s*"([^"]+)"', html, flags=re.IGNORECASE)
    if m:
        d = _parse_date_to_iso(m.group(1))
        if d:
            return d
    m = re.search(r'"dateModified"\\s*:\\s*"([^"]+)"', html, flags=re.IGNORECASE)
    if m:
        d = _parse_date_to_iso(m.group(1))
        if d:
            return d

    # <time datetime="...">
    m = re.search(r'<time[^>]+datetime=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)
    if m:
        return _parse_date_to_iso(m.group(1))

    return ""


def _parse_date_to_iso(raw: str) -> str:
    if not raw:
        return ""
    s = raw.strip()
    # Normalize common formats quickly
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.date().isoformat()
        except Exception:
            pass
    # Try ISO-ish substring
    m = re.search(r"(20\\d{2})[-/](\\d{1,2})[-/](\\d{1,2})", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return datetime(y, mo, d).date().isoformat()
        except Exception:
            return ""
    return ""


# ----------------------------
# Readability (deterministic)
# ----------------------------

def estimate_syllables(word: str) -> int:
    """
    Very rough, deterministic syllable estimator for English.
    Good enough for a *proxy* readability score; document as approximation.
    """
    w = re.sub(r"[^a-z]", "", (word or "").lower())
    if not w:
        return 0
    vowels = "aeiouy"
    groups = 0
    prev_vowel = False
    for ch in w:
        is_v = ch in vowels
        if is_v and not prev_vowel:
            groups += 1
        prev_vowel = is_v
    # silent 'e'
    if w.endswith("e") and groups > 1:
        groups -= 1
    return max(1, groups)


def flesch_reading_ease(text: str) -> float:
    """
    Flesch Reading Ease:
      206.835 - 1.015*(words/sentences) - 84.6*(syllables/words)
    """
    if not text:
        return 0.0
    sentences = max(1, len(re.findall(r"[.!?]+", text)))
    words = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", text)
    n_words = len(words)
    if n_words == 0:
        return 0.0
    syllables = sum(estimate_syllables(w) for w in words)
    score = 206.835 - 1.015 * (n_words / sentences) - 84.6 * (syllables / n_words)
    # clamp to a sane range
    return float(max(-50.0, min(130.0, score)))


# ----------------------------
# Gemini (optional)
# ----------------------------

def _gemini_model_path(model: str) -> str:
    """
    Accept either:
      - "gemini-3-flash-preview"
      - "models/gemini-3-flash-preview"
    and return a full model path like "models/..."
    """
    m = (model or "").strip()
    if not m:
        return "models/gemini-flash-latest"
    return m if m.startswith("models/") else f"models/{m}"


GEMINI_ENDPOINT_TMPL = "https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent?key={key}"


def gemini_classify(
    *,
    api_key: str,
    model: str,
    url: str,
    title: str,
    snippet: str,
    text: str,
    timeout: int = 60,
) -> Dict[str, str]:
    """
    Returns dict with keys: type, content_format, tone, promotional_intensity_score
    Values are strings (leave blank on failure).
    """
    prompt = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "description": "One of: product_page, listicle, blog_article, category_page, documentation, forum, other"},
            "content_format": {"type": "string", "description": "Short label like: listicle, review, comparison, landing_page, directory, faq, news, other"},
            "tone": {"type": "string", "description": "Short label like: neutral, informational, promotional, salesy, academic, opinionated, other"},
            "promotional_intensity_score": {"type": "number", "description": "0..5 integer-ish (0=not promotional, 5=very promotional)"},
        },
        "required": ["type", "content_format", "tone", "promotional_intensity_score"],
    }

    # Keep payload small: cap text
    text_cap = (text or "")[:6000]
    user = (
        f"Classify this page for a research dataset. "
        f"Return ONLY valid JSON matching this schema: {json.dumps(prompt)}\\n\\n"
        f"URL: {url}\\nTitle: {title}\\nSnippet: {snippet}\\n\\nExtracted text (truncated):\\n{text_cap}"
    )

    payload = {
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"temperature": 0.0},
    }

    model_path = _gemini_model_path(model)
    ep = GEMINI_ENDPOINT_TMPL.format(model_path=model_path, key=api_key)
    r = requests.post(ep, json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    try:
        out_text = data["candidates"][0]["content"]["parts"][0]["text"]
        # Strip fenced code if present
        out_text = re.sub(r"^```(?:json)?\\s*|\\s*```$", "", out_text.strip(), flags=re.IGNORECASE | re.MULTILINE)
        parsed = json.loads(out_text)
        return {
            "type": str(parsed.get("type", "")).strip(),
            "content_format": str(parsed.get("content_format", "")).strip(),
            "tone": str(parsed.get("tone", "")).strip(),
            "promotional_intensity_score": str(parsed.get("promotional_intensity_score", "")).strip(),
        }
    except Exception:
        return {"type": "", "content_format": "", "tone": "", "promotional_intensity_score": ""}


# ----------------------------
# Pipeline
# ----------------------------

@dataclass
class FetchResult:
    html: str
    final_url: str
    status: int
    error: str


def fetch_html(url: str, timeout: int = 30) -> FetchResult:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; GEOThesisBot/0.1; +https://example.invalid)"
        }
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        html = resp.text if resp.ok else ""
        return FetchResult(html=html, final_url=resp.url, status=resp.status_code, error="")
    except Exception as e:
        return FetchResult(html="", final_url=url, status=0, error=str(e))


def read_csv(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        if not r.fieldnames:
            raise ValueError("CSV has no header.")
        return [{k: (v if v is not None else "") for k, v in row.items()} for row in r]


def write_csv(path: str, rows: Sequence[Dict[str, str]]) -> None:
    if not rows:
        raise ValueError("No rows to write.")
    cols: List[str] = []
    seen = set()
    # Prefer your schema columns first
    preferred = [
        "url",
        "type",
        "domain",
        "content_word_count",
        "has_table",
        "has_comparison_table",
        "comparison_table_score",
        "content_format",
        "has_pros_cons",
        "pros_cons_score",
        "has_schema_markup",
        "tone",
        "readability_score",
        "promotional_intensity_score",
        "freshness_date",
        # Useful operational columns
        "url_key",
        "fetch_status",
        "fetch_error",
        "fetched_at",
        "final_url",
    ]
    for c in preferred:
        for r in rows:
            if c in r and c not in seen:
                cols.append(c)
                seen.add(c)
                break
    for r in rows:
        for c in r.keys():
            if c not in seen:
                cols.append(c)
                seen.add(c)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Enrich URL rows with deterministic features + optional Gemini labels.")
    p.add_argument("--input", required=True, help="Input CSV path (must contain a URL column).")
    p.add_argument("--output", required=True, help="Output CSV path.")
    p.add_argument("--url-col", default="url", help="Column name containing URL (default: url).")
    p.add_argument("--title-col", default="title", help="Optional column name for title (default: title).")
    p.add_argument("--snippet-col", default="snippet", help="Optional column name for snippet (default: snippet).")
    p.add_argument("--sleep", type=float, default=0.0, help="Sleep seconds between fetches (politeness).")
    p.add_argument("--max-rows", type=int, default=0, help="If set >0, only process first N rows.")
    p.add_argument("--cache-dir", default="data/url_cache", help="Cache directory for fetched HTML/text.")
    p.add_argument("--drop-html", action="store_true", help="Do not keep raw HTML in output rows.")
    p.add_argument("--use-gemini", action="store_true", help="Use Gemini to fill type/content_format/tone/promo.")
    p.add_argument(
        "--gemini-model",
        default="gemini-3-flash-preview",
        help="Gemini model name (default: gemini-3-flash-preview). You can pass 'models/...' too.",
    )

    args = p.parse_args(argv)

    # Read from system env. (Node uses process.env; Python uses os.getenv.)
    # Support a few common alternate names to reduce friction.
    api_key = (
        os.getenv("GEMINI_API_KEY", "").strip()
        or os.getenv("GOOGLE_API_KEY", "").strip()
        or os.getenv("GOOGLE_GENERATIVE_AI_API_KEY", "").strip()
    )
    if args.use_gemini and not api_key:
        raise SystemExit(
            "Missing API key env var. Set one of: GEMINI_API_KEY (preferred), GOOGLE_API_KEY, GOOGLE_GENERATIVE_AI_API_KEY."
        )

    os.makedirs(args.cache_dir, exist_ok=True)

    rows = read_csv(args.input)
    if args.max_rows and args.max_rows > 0:
        rows = rows[: args.max_rows]

    for i, row in enumerate(rows, start=1):
        raw_url = (row.get(args.url_col) or "").strip()
        row["url"] = raw_url  # normalize output col name
        row["domain"] = get_domain(raw_url)
        row["url_key"] = normalize_url_key(raw_url)

        if not raw_url:
            row["fetch_status"] = "0"
            row["fetch_error"] = "missing url"
            continue

        cache_key = short_hash(row["url_key"] or raw_url)
        html_path = os.path.join(args.cache_dir, f"{cache_key}.html")

        html = ""
        final_url = raw_url
        status = 0
        err = ""

        if os.path.exists(html_path):
            with open(html_path, "r", encoding="utf-8") as rf:
                html = rf.read()
            status = 200
        else:
            fr = fetch_html(raw_url)
            html, final_url, status, err = fr.html, fr.final_url, fr.status, fr.error
            if html:
                with open(html_path, "w", encoding="utf-8") as wf:
                    wf.write(html)
            if args.sleep:
                time.sleep(args.sleep)

        text = strip_html_to_text(html)
        row["content_word_count"] = str(count_words(text))
        row["has_table"] = "1" if has_table_from_html(html) else "0"
        has_cmp, cmp_score = detect_comparison_table(html)
        row["has_comparison_table"] = "1" if has_cmp else "0"
        row["comparison_table_score"] = f"{cmp_score:.2f}"
        has_pc, pc_score = detect_pros_cons(html, text)
        row["has_pros_cons"] = "1" if has_pc else "0"
        row["pros_cons_score"] = f"{pc_score:.2f}"
        row["has_schema_markup"] = "1" if has_schema_markup_from_html(html) else "0"
        row["freshness_date"] = extract_freshness_date(html)
        row["readability_score"] = f"{flesch_reading_ease(text):.2f}"

        # Defaults for LLM columns (leave blank unless classified)
        row.setdefault("type", "")
        row.setdefault("content_format", "")
        row.setdefault("tone", "")
        row.setdefault("promotional_intensity_score", "")

        # Optional Gemini classification
        if args.use_gemini:
            title = (row.get(args.title_col) or "").strip()
            snippet = (row.get(args.snippet_col) or "").strip()
            labels = gemini_classify(
                api_key=api_key,
                model=args.gemini_model,
                url=raw_url,
                title=title,
                snippet=snippet,
                text=text,
            )
            row.update(labels)

        row["fetch_status"] = str(status)
        row["fetch_error"] = err
        row["final_url"] = final_url
        row["fetched_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        if args.drop_html:
            row.pop("html", None)
        else:
            row["html"] = html

        if i % 25 == 0:
            print(f"processed {i}/{len(rows)}")

    write_csv(args.output, rows)
    print(f"wrote {args.output} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


