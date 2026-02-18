#!/usr/bin/env python3
"""
Compute simple content-size stats (word/char counts) for fetched page text, split by:
- type: listicle vs product_page
- group flags from data/enrichment/full_url_dna_database_with_groups.csv

This is descriptive (not a "budget" analysis). It helps contextualize downstream drift/fidelity findings.

Outputs:
- data/enrichment/content_size_stats.json
"""

from __future__ import annotations

import csv
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

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


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def quantiles(vals: List[int]) -> Optional[Dict[str, Any]]:
    if not vals:
        return None
    xs = sorted(vals)

    def pick(p: float) -> int:
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
    total: int = 0
    have_content: int = 0
    words: List[int] = None  # type: ignore[assignment]
    chars: List[int] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.words is None:
            self.words = []
        if self.chars is None:
            self.chars = []

    def add(self, wc_cc: Optional[Tuple[int, int]]) -> None:
        self.total += 1
        if wc_cc is None:
            return
        self.have_content += 1
        wc, cc = wc_cc
        self.words.append(int(wc))
        self.chars.append(int(cc))

    def as_dict(self) -> Dict[str, Any]:
        coverage_pct = (100.0 * self.have_content / self.total) if self.total else 0.0
        return {
            "total_pages": self.total,
            "pages_with_content": self.have_content,
            "coverage_pct": coverage_pct,
            "words": quantiles(self.words),
            "chars": quantiles(self.chars),
        }


def main() -> int:
    url_content_csv = os.environ.get("URL_CONTENT_CSV", "datapass/url_content_2026-01-31-04-26-20.csv")
    dna_groups_csv = os.environ.get("DNA_GROUPS_CSV", "data/enrichment/full_url_dna_database_with_groups.csv")
    out_json = os.environ.get("OUT_JSON", "data/enrichment/content_size_stats.json")

    if not os.path.exists(url_content_csv):
        raise SystemExit(f"Missing url content csv: {url_content_csv}")
    if not os.path.exists(dna_groups_csv):
        raise SystemExit(f"Missing dna groups csv: {dna_groups_csv}")

    # 1) Load content lengths keyed by normalized URL (prefer first-seen)
    content_by_key: Dict[str, Tuple[int, int]] = {}
    with open(url_content_csv, "r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            url = (row.get("url") or "").strip()
            final_url = (row.get("final_url") or "").strip()
            text = row.get("content") or ""
            if not text.strip():
                continue
            wc = word_count(text)
            cc = len(text)
            for candidate in [final_url, url]:
                if not candidate:
                    continue
                k = normalize_url_key(candidate)
                if k and k not in content_by_key:
                    content_by_key[k] = (wc, cc)

    # 2) Iterate dna group rows and bucket stats
    FLAGS = [
        "is_cited_by_gemini",
        "is_cited_by_gpt",
        "in_gemini_top10",
        "in_gpt_personal_top10",
        "in_gpt_enterprise_p1",
    ]

    buckets: Dict[str, Bucket] = {}

    def bucket(name: str) -> Bucket:
        b = buckets.get(name)
        if b is None:
            b = Bucket()
            buckets[name] = b
        return b

    with open(dna_groups_csv, "r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            t = (row.get("type") or "").strip()
            if t not in ("listicle", "product_page"):
                continue

            url = (row.get("url") or "").strip()
            k = normalize_url_key(url)
            wc_cc = content_by_key.get(k)

            bucket(f"all::{t}").add(wc_cc)

            for flag in FLAGS:
                val = (row.get(flag) or "").strip().lower()
                if val in ("yes", "true", "1"):
                    bucket(f"{flag}::{t}").add(wc_cc)

    out: Dict[str, Any] = {
        "inputs": {
            "url_content_csv": url_content_csv,
            "dna_groups_csv": dna_groups_csv,
        },
        "buckets": {k: buckets[k].as_dict() for k in sorted(buckets.keys())},
    }

    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote: {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

