"""
Compute overlap between ChatGPT sources and Bing SERP results by rank buckets.

Inputs:
  - ChatGPT export CSV (from ChatGPT scraper)
  - Bing export CSV (cleaned; ideally top<=30 per run_id with url_key)

Outputs:
  - Per-run metrics CSV (URLs + domains), computed separately for:
      - sources_cited (Citations panel)
      - sources_additional (More panel)

This is intentionally *analysis output* (not Excel raw data).
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pandas as pd


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
    """Normalized URL key for joins/deduping (mirrors scripts/clean_bing_export.py)."""
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
    rebuilt = urlunsplit(("", host, path, query, "")).lstrip("/")
    return rebuilt


def extract_domain(raw_url: str) -> str:
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
    return host


def parse_sources_json(cell: object) -> List[str]:
    """Parse sources_*_json cell into list of urls."""
    if cell is None:
        return []
    s = str(cell).strip()
    if not s or s == "[]":
        return []
    try:
        arr = json.loads(s)
    except Exception:
        return []
    out: List[str] = []
    if isinstance(arr, list):
        for it in arr:
            if isinstance(it, dict) and isinstance(it.get("url"), str):
                out.append(it["url"])
            elif isinstance(it, str):
                out.append(it)
    return out


def overlap_stats(a: List[str], b: List[str]) -> Tuple[int, int, int, float, float]:
    """
    Return (|A|, |B|, |A∩B|, frac_in_A, overlap_coeff)
      - frac_in_A = |A∩B| / |A|   (if |A|=0 -> 0)
      - overlap_coeff = |A∩B| / min(|A|,|B|)  (if min=0 -> 0)
    """
    A = list(dict.fromkeys(a))  # preserve order, unique
    B = list(dict.fromkeys(b))
    setA = set(A)
    setB = set(B)
    inter = len(setA & setB)
    frac_in_a = (inter / len(setA)) if setA else 0.0
    denom = min(len(setA), len(setB))
    overlap_coeff = (inter / denom) if denom else 0.0
    return (len(setA), len(setB), inter, frac_in_a, overlap_coeff)


@dataclass(frozen=True)
class Bucket:
    k: int


BUCKETS: List[Bucket] = [Bucket(1), Bucket(3), Bucket(5), Bucket(10), Bucket(30)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chatgpt", required=True, help="Path to ChatGPT results CSV")
    ap.add_argument("--bing", required=True, help="Path to cleaned Bing results CSV (top<=30 recommended)")
    ap.add_argument("--out", required=True, help="Path to write metrics CSV")
    args = ap.parse_args()

    chat = pd.read_csv(args.chatgpt, engine="python")
    bing = pd.read_csv(args.bing, engine="python")

    # Normalize/ensure needed fields
    needed_chat = {"prompt_id", "run_number", "generated_search_query", "sources_cited_json", "sources_additional_json"}
    missing = sorted([c for c in needed_chat if c not in chat.columns])
    if missing:
        raise ValueError(f"ChatGPT CSV missing required columns: {missing}")

    if "run_id" not in bing.columns or "position" not in bing.columns or "url" not in bing.columns:
        raise ValueError("Bing CSV must include run_id, position, url columns.")

    # Build url_key if not present
    if "url_key" not in bing.columns:
        bing["url_key"] = bing["url"].astype(str).map(normalize_url_key)

    bing["position"] = pd.to_numeric(bing["position"], errors="coerce").fillna(10**9).astype(int)

    # Precompute per run_id: topK url_keys and domains
    bing_groups = {}
    for rid, g in bing.groupby("run_id", sort=False):
        g2 = g.sort_values("position")
        url_keys = g2["url_key"].astype(str).tolist()
        domains = g2["domain"].astype(str).tolist() if "domain" in g2.columns else [extract_domain(u) for u in g2["url"].astype(str).tolist()]
        bing_groups[rid] = {
            "url_keys": url_keys,
            "domains": domains,
        }

    rows = []
    for _, r in chat.iterrows():
        prompt_id = str(r.get("prompt_id", "")).strip()
        run_number = int(r.get("run_number"))
        run_id = f"{prompt_id}_r{run_number}"
        gen_q = str(r.get("generated_search_query", "")).strip()

        bg = bing_groups.get(run_id)
        if not bg:
            # No Bing data for this run_id; skip
            continue

        cited_urls = parse_sources_json(r.get("sources_cited_json"))
        add_urls = parse_sources_json(r.get("sources_additional_json"))

        cited_keys = [normalize_url_key(u) for u in cited_urls if normalize_url_key(u)]
        add_keys = [normalize_url_key(u) for u in add_urls if normalize_url_key(u)]

        cited_domains = [extract_domain(u) for u in cited_urls if extract_domain(u)]
        add_domains = [extract_domain(u) for u in add_urls if extract_domain(u)]

        for section, A_keys, A_domains in [
            ("cited", cited_keys, cited_domains),
            ("additional", add_keys, add_domains),
        ]:
            for b in BUCKETS:
                B_keys = bg["url_keys"][: b.k]
                B_domains = bg["domains"][: b.k]

                a_n, b_n, inter, frac_in_a, oc = overlap_stats(A_keys, B_keys)
                da_n, db_n, dinter, dfrac_in_a, doc = overlap_stats(A_domains, B_domains)

                rows.append(
                    {
                        "run_id": run_id,
                        "prompt_id": prompt_id,
                        "run_number": run_number,
                        "generated_search_query": gen_q,
                        "section": section,  # cited | additional
                        "bucket_k": b.k,
                        "n_sources": a_n,
                        "n_bing": b_n,
                        "n_overlap": inter,
                        "frac_sources_in_bing": frac_in_a,
                        "overlap_coeff": oc,
                        "n_domains": da_n,
                        "n_bing_domains": db_n,
                        "n_domain_overlap": dinter,
                        "frac_domains_in_bing": dfrac_in_a,
                        "domain_overlap_coeff": doc,
                    }
                )

    out_df = pd.DataFrame(rows)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False)
    print(f"Wrote {out_path} ({len(out_df)} rows)")


if __name__ == "__main__":
    main()


