"""
Build listicles-only semantic verification batches (per URL) from:
- ChatGPT citation mappings (datapass/citation_mappings/*_mapping.json)
- URL labels (datapass/page_labels_combined_v2.5.jsonl) where response.urls.type == "listicle"
- Local extracted page text (datapass/url_content_*.csv, column "content")

Output: one JSON per source URL containing:
  - source_url
  - normalized_url_key
  - claims[] (claim_id, claim_text, run_id, citation_token, start_idx/end_idx, mapping_type)
  - page_text (+ optional page metadata)

This is meant for a pilot where you run the verifier once per URL, not once per claim.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


DROP_EXACT = {
    "gclid",
    "fbclid",
    "msclkid",
    "yclid",
    "mc_cid",
    "mc_eid",
    "igshid",
}


def short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def normalize_url_key(raw_url: str) -> str:
    """
    Match the repo's JS normalizeUrlKey() behavior:
    - force scheme if missing
    - lowercase host and strip leading www.
    - strip trailing slash (except root)
    - drop common tracking params (utm_*, gclid, fbclid, ...)
    """
    if not raw_url:
        return ""
    url = raw_url.strip()
    if "://" not in url:
        url = f"https://{url}"
    try:
        # stdlib url parsing is limited; use simple regex to avoid adding deps.
        # We'll approximate WHATWG URL:
        from urllib.parse import urlparse, parse_qsl, urlencode

        p = urlparse(url)
        host = (p.hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        path = p.path or "/"
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]
        q_pairs = []
        for k, v in parse_qsl(p.query, keep_blank_values=True):
            lk = k.lower()
            if lk.startswith("utm_") or lk in DROP_EXACT:
                continue
            q_pairs.append((k, v))
        q = urlencode(q_pairs)
        return f"{host}{path}{('?' + q) if q else ''}"
    except Exception:
        return raw_url.strip().lower()


def iter_jsonl(path: str) -> Iterable[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue


def load_listicle_url_keys(labels_jsonl: str) -> Set[str]:
    out: Set[str] = set()
    for rec in iter_jsonl(labels_jsonl):
        if not rec.get("ok"):
            continue
        url = rec.get("url") or ""
        resp = rec.get("response") or {}
        urls_obj = resp.get("urls") or {}
        if urls_obj.get("type") == "listicle":
            out.add(normalize_url_key(url))
    return out


@dataclass
class PageText:
    url: str
    final_url: str
    status: Optional[int]
    page_title: str
    meta_description: str
    canonical_url: str
    content: str


def load_page_text_by_url_key(url_content_csv: str) -> Dict[str, PageText]:
    """
    Build mapping from normalized URL key -> PageText, using both url and final_url keys.
    The CSV is expected to have at least: url, final_url, status, page_title, meta_description, canonical_url, content
    """
    by_key: Dict[str, PageText] = {}
    with open(url_content_csv, "r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            url = (row.get("url") or "").strip()
            final_url = (row.get("final_url") or "").strip()
            if not url and not final_url:
                continue

            # Prefer successful rows with non-empty content
            content = row.get("content") or ""
            if not content.strip():
                continue

            status_raw = (row.get("status") or "").strip()
            try:
                status = int(status_raw) if status_raw else None
            except Exception:
                status = None

            pt = PageText(
                url=url,
                final_url=final_url,
                status=status,
                page_title=(row.get("page_title") or "").strip(),
                meta_description=(row.get("meta_description") or "").strip(),
                canonical_url=(row.get("canonical_url") or "").strip(),
                content=content,
            )

            for candidate in [final_url, url]:
                if not candidate:
                    continue
                k = normalize_url_key(candidate)
                # Keep first seen; CSV usually has one row per URL already.
                by_key.setdefault(k, pt)

    return by_key


def extract_urls_from_mapping_entry(entry: Dict[str, Any]) -> List[str]:
    urls: List[str] = []
    inline = entry.get("inline_url")
    if isinstance(inline, str) and inline.strip():
        urls.append(inline.strip())
    sources = entry.get("sources")
    if isinstance(sources, list):
        for s in sources:
            if isinstance(s, dict):
                u = s.get("url")
                if isinstance(u, str) and u.strip():
                    urls.append(u.strip())
    # de-dupe while preserving order
    seen = set()
    out = []
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def iter_mapping_files(citation_dir: str) -> Iterable[str]:
    for name in sorted(os.listdir(citation_dir)):
        if not name.endswith("_mapping.json"):
            continue
        yield os.path.join(citation_dir, name)


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def safe_filename(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "_", s)
    return s[:180] if len(s) > 180 else s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default="datapass/page_labels_combined_v2.5.jsonl")
    ap.add_argument("--citation_dir", default="datapass/citation_mappings")
    ap.add_argument("--url_content_csv", default="datapass/url_content_2026-01-31-04-26-20.csv")
    ap.add_argument("--out_dir", default="data/semantic_verification/batches_listicles")
    ap.add_argument("--max_urls", type=int, default=0, help="0 = no limit")
    ap.add_argument("--min_claim_chars", type=int, default=20)
    args = ap.parse_args()

    listicle_keys = load_listicle_url_keys(args.labels)
    page_text_by_key = load_page_text_by_url_key(args.url_content_csv)

    os.makedirs(args.out_dir, exist_ok=True)

    # url_key -> (source_url, claims[])
    grouped: Dict[str, Dict[str, Any]] = {}

    mapping_files = list(iter_mapping_files(args.citation_dir))
    for p in mapping_files:
        try:
            obj = load_json(p)
        except Exception:
            continue

        run_id = obj.get("run_id") or ""
        account_type = obj.get("account_type") or ""
        mappings = obj.get("citation_mappings")
        if not isinstance(mappings, list):
            continue

        for i, entry in enumerate(mappings):
            if not isinstance(entry, dict):
                continue
            claim_text = entry.get("claim_text")
            if not isinstance(claim_text, str) or len(claim_text.strip()) < args.min_claim_chars:
                continue

            token_pos = entry.get("token_position") or {}
            start_idx = token_pos.get("start_idx")
            end_idx = token_pos.get("end_idx")
            citation_token = entry.get("citation_token") or ""
            mapping_type = entry.get("type") or ""

            urls = extract_urls_from_mapping_entry(entry)
            for u in urls:
                k = normalize_url_key(u)
                if k not in listicle_keys:
                    continue

                claim_id = f"{run_id}/{account_type}/m{i}/tok_{start_idx}-{end_idx}/u_{short_hash(k)}"
                g = grouped.setdefault(
                    k,
                    {
                        "source_url": u,
                        "normalized_url_key": k,
                        "claims": [],
                    },
                )
                g["claims"].append(
                    {
                        "claim_id": claim_id,
                        "claim_text": claim_text.strip(),
                        "run_id": run_id,
                        "account_type": account_type,
                        "citation_token": citation_token,
                        "start_idx": start_idx,
                        "end_idx": end_idx,
                        "mapping_type": mapping_type,
                    }
                )

    # write outputs
    total_written = 0
    total_missing_text = 0
    for url_key, bundle in grouped.items():
        # prefer text keyed by normalized URL
        pt = page_text_by_key.get(url_key)
        if not pt:
            total_missing_text += 1
            continue

        out_obj = {
            "source_url": bundle["source_url"],
            "normalized_url_key": url_key,
            "page": {
                "url": pt.url,
                "final_url": pt.final_url,
                "status": pt.status,
                "page_title": pt.page_title,
                "meta_description": pt.meta_description,
                "canonical_url": pt.canonical_url,
            },
            "claims": bundle["claims"],
            "page_text": pt.content,
        }

        fname = safe_filename(f"{short_hash(url_key)}.json")
        out_path = os.path.join(args.out_dir, fname)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(out_obj, fh, ensure_ascii=False, indent=2)

        total_written += 1
        if args.max_urls and total_written >= args.max_urls:
            break

    print("LISTICLE_URL_KEYS", len(listicle_keys))
    print("PAGE_TEXT_KEYS", len(page_text_by_key))
    print("GROUPED_LISTICLE_URLS_WITH_CLAIMS", len(grouped))
    print("WROTE_BATCH_FILES", total_written)
    print("MISSING_PAGE_TEXT_FOR_GROUPED_URLS", total_missing_text)
    print("OUT_DIR", args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

