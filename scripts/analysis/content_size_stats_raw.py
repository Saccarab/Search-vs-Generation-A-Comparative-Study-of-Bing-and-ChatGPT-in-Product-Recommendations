#!/usr/bin/env python3
"""
Compute content-size stats (bytes/chars and word counts) from *raw fetched files* in:
  data/fetched_content/<hash>.txt

We bucket URLs by:
- page `type` from: data/enrichment/full_url_dna_database_with_groups.csv
- group flags (menu vs cited):
  - cited_any (is_cited_by_gpt OR is_cited_by_gemini)
  - cited_gpt
  - cited_gemini
  - menu_any (any of in_* topN flags below)
  - in_gpt_personal_top10
  - in_gpt_enterprise_p1
  - in_gemini_top10

Outputs:
- data/enrichment/content_size_stats_raw.json
- data/enrichment/content_size_stats_raw.csv  (flattened)
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from urllib.parse import parse_qsl, urlencode, urlparse


DROP_EXACT = {"gclid", "fbclid", "msclkid", "yclid", "mc_cid", "mc_eid", "igshid"}


def normalize_url_key(raw_url: str) -> str:
    if not raw_url:
        return ""
    url = raw_url.strip()
    if "://" not in url:
        url = f"https://{url}"
    try:
        p = urlparse(url)
        host = (p.hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        path = p.path or "/"
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]
        kept: List[Tuple[str, str]] = []
        for k, v in parse_qsl(p.query, keep_blank_values=True):
            lk = k.lower()
            if lk.startswith("utm_") or lk in DROP_EXACT:
                continue
            kept.append((k, v))
        q = urlencode(kept)
        suffix = f"?{q}" if q else ""
        return f"{host}{path}{suffix}"
    except Exception:
        return raw_url.strip().lower()


def short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


WORD_RE = re.compile(r"\b\w+\b", flags=re.UNICODE)


def count_words_streaming(path: str, chunk_bytes: int = 1024 * 1024) -> int:
    """
    Streaming-ish word count. Good enough for distribution stats.
    """
    total = 0
    tail = ""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        while True:
            chunk = f.read(chunk_bytes)
            if not chunk:
                break
            text = tail + chunk
            # keep a small tail to reduce boundary effects
            tail = text[-100:]
            total += len(WORD_RE.findall(text[:-100] if len(text) > 100 else text))
    if tail:
        total += len(WORD_RE.findall(tail))
    return total


def boolish(v: Any) -> bool:
    return str(v or "").strip().lower() in ("yes", "true", "1")


def quantiles(vals: List[float]) -> Optional[Dict[str, Any]]:
    if not vals:
        return None
    xs = sorted(vals)

    def pick(p: float) -> float:
        idx = int(round(p * (len(xs) - 1)))
        return xs[idx]

    return {
        "n": len(xs),
        "mean": sum(xs) / len(xs),
        "p25": pick(0.25),
        "median": pick(0.50),
        "p75": pick(0.75),
        "p95": pick(0.95),
    }


@dataclass
class Bucket:
    total_pages: int = 0
    pages_with_raw: int = 0
    sizes_bytes: List[int] = None  # type: ignore[assignment]
    words: List[int] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.sizes_bytes is None:
            self.sizes_bytes = []
        if self.words is None:
            self.words = []

    def add(self, txt_path: Optional[str]) -> None:
        self.total_pages += 1
        if not txt_path or not os.path.exists(txt_path):
            return
        self.pages_with_raw += 1
        self.sizes_bytes.append(int(os.path.getsize(txt_path)))
        # word counts are slower; compute only if file exists
        self.words.append(int(count_words_streaming(txt_path)))

    def to_dict(self) -> Dict[str, Any]:
        cov = (100.0 * self.pages_with_raw / self.total_pages) if self.total_pages else 0.0
        return {
            "total_pages": self.total_pages,
            "pages_with_raw": self.pages_with_raw,
            "coverage_pct": cov,
            "bytes": quantiles([float(x) for x in self.sizes_bytes]),
            "words": quantiles([float(x) for x in self.words]),
        }


def flatten_stats(buckets: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for bucket_key, stats in buckets.items():
        base = {
            "bucket": bucket_key,
            "total_pages": stats.get("total_pages"),
            "pages_with_raw": stats.get("pages_with_raw"),
            "coverage_pct": stats.get("coverage_pct"),
        }
        b = stats.get("bytes") or {}
        w = stats.get("words") or {}
        for prefix, obj in [("bytes", b), ("words", w)]:
            for k in ["n", "mean", "p25", "median", "p75", "p95"]:
                base[f"{prefix}_{k}"] = obj.get(k)
        out.append(base)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dna-groups-csv", default="data/enrichment/full_url_dna_database_with_groups.csv")
    ap.add_argument("--fetched-dir", default="data/fetched_content")
    ap.add_argument(
        "--types",
        default="listicle,product_page",
        help="Comma-separated types to include (from DNA). Default: listicle,product_page",
    )
    ap.add_argument("--out-json", default="data/enrichment/content_size_stats_raw.json")
    ap.add_argument("--out-csv", default="data/enrichment/content_size_stats_raw.csv")
    args = ap.parse_args()

    include_types = {t.strip() for t in (args.types or "").split(",") if t.strip()}
    if not include_types:
        raise SystemExit("No --types provided")

    if not os.path.exists(args.dna_groups_csv):
        raise SystemExit(f"Missing: {args.dna_groups_csv}")

    FLAGS_MENU = ["in_gpt_personal_top10", "in_gpt_enterprise_p1", "in_gemini_top10"]
    FLAGS_CITED = ["is_cited_by_gpt", "is_cited_by_gemini"]

    buckets: Dict[str, Bucket] = {}

    def bucket(name: str) -> Bucket:
        b = buckets.get(name)
        if b is None:
            b = Bucket()
            buckets[name] = b
        return b

    with open(args.dna_groups_csv, "r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            t = (row.get("type") or "").strip()
            if t not in include_types:
                continue
            url = (row.get("url") or "").strip()
            k = normalize_url_key(url)
            h = short_hash(k) if k else ""
            txt_path = os.path.join(args.fetched_dir, f"{h}.txt") if h else None

            # all
            bucket(f"all::{t}").add(txt_path)

            # cited buckets
            cited_gpt = boolish(row.get("is_cited_by_gpt"))
            cited_gem = boolish(row.get("is_cited_by_gemini"))
            if cited_gpt or cited_gem:
                bucket(f"cited_any::{t}").add(txt_path)
            if cited_gpt:
                bucket(f"cited_gpt::{t}").add(txt_path)
            if cited_gem:
                bucket(f"cited_gemini::{t}").add(txt_path)

            # menu buckets
            menu_hits = [flag for flag in FLAGS_MENU if boolish(row.get(flag))]
            if menu_hits:
                bucket(f"menu_any::{t}").add(txt_path)
                for flag in menu_hits:
                    bucket(f"{flag}::{t}").add(txt_path)

    out_json = {
        "inputs": {
            "dna_groups_csv": args.dna_groups_csv,
            "fetched_dir": args.fetched_dir,
            "types": sorted(include_types),
        },
        "buckets": {k: buckets[k].to_dict() for k in sorted(buckets.keys())},
    }

    os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(out_json, f, indent=2)

    flat = flatten_stats(out_json["buckets"])
    with open(args.out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(flat[0].keys()) if flat else ["bucket"])
        w.writeheader()
        w.writerows(flat)

    print(f"Wrote: {args.out_json}")
    print(f"Wrote: {args.out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

