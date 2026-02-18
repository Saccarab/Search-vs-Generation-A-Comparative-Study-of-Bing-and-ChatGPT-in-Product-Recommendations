#!/usr/bin/env python3
"""
Quantify how often a single response claim/segment is supported by MULTIPLE cited URLs.

We compute this for:
- GPT study: datapass/citation_mappings/*_mapping.json
  Each mapping row has claim_text + inline_url (+ optional sources[] urls).
  We treat a "claim occurrence" as (run_id, account_type, token_position.start/end, claim_text).
  The cited URL set is {inline_url} ∪ {sources[].url}.

- Gemini study: data/gemini_raw_responses/*.json
  Each groundingSupport segment has groundingChunkIndices -> groundingChunks[i].web.uri.
  We treat a "segment occurrence" as (run_id, segment.startIndex/endIndex, segment.text).
  The cited URL set is the resolved URLs for those chunk indices.

We also report a "listicle-cited" slice: occurrences where ANY cited URL is labeled type=listicle
in our existing enrichment DNA label jsonls.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Set, Tuple


DROP_EXACT = {
    "gclid",
    "fbclid",
    "msclkid",
    "yclid",
    "mc_cid",
    "mc_eid",
    "igshid",
}


def normalize_url_key(raw_url: str) -> str:
    if not raw_url:
        return ""
    url = raw_url.strip()
    if "://" not in url:
        url = f"https://{url}"
    try:
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


def safe_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def load_dna_map(jsonl_paths: List[str]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for p in jsonl_paths:
        if not p or not os.path.exists(p):
            continue
        with open(p, "r", encoding="utf-8") as fh:
            for line in fh:
                t = line.strip()
                if not t:
                    continue
                try:
                    rec = json.loads(t)
                except Exception:
                    continue
                url = rec.get("url") or (rec.get("response") or {}).get("urls", {}).get("url")
                if not url:
                    continue
                k = normalize_url_key(url)
                dna = (rec.get("response") or {}).get("urls") or rec
                if k in out and isinstance(out[k], dict) and isinstance(dna, dict):
                    out[k].update(dna)
                else:
                    out[k] = dna if isinstance(dna, dict) else {}
    return out


def latest_gemini_files(dir_path: str) -> Dict[str, str]:
    """
    Files are like: P001_r1_<timestamp>.json. Keep latest per (Pxxx_rY).
    """
    latest: Dict[str, Tuple[str, str]] = {}
    if not os.path.isdir(dir_path):
        return {}
    for fn in os.listdir(dir_path):
        if not fn.endswith(".json"):
            continue
        parts = fn.split("_")
        if len(parts) < 3:
            continue
        run_id = f"{parts[0]}_{parts[1]}"
        ts = parts[2].replace(".json", "")
        prev = latest.get(run_id)
        if prev is None or ts > prev[0]:
            latest[run_id] = (ts, os.path.join(dir_path, fn))
    return {rid: path for rid, (ts, path) in latest.items()}


def load_resolved_urls(path: str) -> Dict[str, str]:
    if not path or not os.path.exists(path):
        return {}
    try:
        return json.load(open(path, "r", encoding="utf-8"))
    except Exception:
        return {}


def url_type(url: str, dna_map: Dict[str, Dict[str, Any]]) -> str:
    k = normalize_url_key(url)
    dna = dna_map.get(k) or {}
    return safe_str(dna.get("type")) or ""


def is_listicle_url(url: str, dna_map: Dict[str, Dict[str, Any]]) -> bool:
    return url_type(url, dna_map) == "listicle"


def is_product_page_url(url: str, dna_map: Dict[str, Dict[str, Any]]) -> bool:
    return url_type(url, dna_map) == "product_page"


def pct(a: int, b: int) -> str:
    if b <= 0:
        return "0.0%"
    return f"{(100.0 * a / b):.1f}%"


def summarize_counts(label: str, total: int, multi: int, dist: Counter) -> None:
    print(f"[{label}] total={total} multi_url={multi} share={pct(multi, total)}")
    if total:
        buckets = []
        for k in sorted(dist.keys()):
            buckets.append(f"{k}:{dist[k]}")
        print(f"[{label}] urls_per_occurrence={{" + ", ".join(buckets[:12]) + (" ..." if len(buckets) > 12 else "") + "}}")


def summarize_multi_type_mix(label: str, multi_total: int, buckets: Dict[str, int]) -> None:
    """
    Buckets should sum to multi_total.
    """
    if multi_total <= 0:
        print(f"[{label}] multi_type_mix: (no multi-cited occurrences)")
        return
    order = [
        "mixed_listicle+product",
        "listicle_only",
        "product_only",
        "neither_listicle_nor_product",
    ]
    parts = []
    for k in order:
        v = int(buckets.get(k, 0))
        parts.append(f"{k}={v} ({pct(v, multi_total)})")
    print(f"[{label}] multi_type_mix: " + ", ".join(parts))


def summarize_top_type_sets(label: str, counts: Counter, total: int, top_k: int = 12) -> None:
    if total <= 0:
        print(f"[{label}] top_type_sets: (none)")
        return
    items = counts.most_common(top_k)
    parts = []
    for k, v in items:
        parts.append(f"{k}={v} ({pct(v, total)})")
    print(f"[{label}] top_type_sets: " + "; ".join(parts))


def type_set_key(urls: Set[str], dna_map: Dict[str, Dict[str, Any]]) -> str:
    """
    Stable key like: "listicle+product_page" or "marketplace_directory+unknown".
    """
    types: Set[str] = set()
    for u in urls:
        t = url_type(u, dna_map)
        types.add(t if t else "unknown")
    return "+".join(sorted(types))


def bucket_name(any_listicle: bool, any_product: bool) -> str:
    if any_listicle and any_product:
        return "mixed_listicle+product"
    if any_listicle and (not any_product):
        return "listicle_only"
    if any_product and (not any_listicle):
        return "product_only"
    return "neither_listicle_nor_product"


def analyze_gpt(
    mapping_dir: str,
    dna_map: Dict[str, Dict[str, Any]],
    out_mixed_csv: str = "",
    max_mixed_rows: int = 2000,
) -> Dict[str, Any]:
    total = 0
    multi = 0
    dist: Counter = Counter()
    multi_mixed_listicle_product = 0
    multi_listicle_only = 0
    multi_product_only = 0
    multi_neither = 0
    multi_with_any_listicle = 0

    listicle_total = 0
    listicle_multi = 0
    listicle_dist: Counter = Counter()
    listicle_multi_mixed_listicle_product = 0
    listicle_multi_listicle_only = 0

    mixed_rows: List[Dict[str, Any]] = []
    multi_type_sets_all: Counter = Counter()
    multi_type_sets_by_bucket: Dict[str, Counter] = {
        "mixed_listicle+product": Counter(),
        "listicle_only": Counter(),
        "product_only": Counter(),
        "neither_listicle_nor_product": Counter(),
    }

    for fn in sorted(os.listdir(mapping_dir)) if os.path.isdir(mapping_dir) else []:
        if not fn.endswith("_mapping.json") or fn.startswith("_"):
            continue
        path = os.path.join(mapping_dir, fn)
        try:
            rec = json.load(open(path, "r", encoding="utf-8"))
        except Exception:
            continue

        base_run_id = safe_str(rec.get("run_id"))
        account_type = safe_str(rec.get("account_type"))
        run_id = f"{base_run_id}_{account_type}" if account_type in ("personal", "enterprise") else base_run_id
        mappings = rec.get("citation_mappings") or []
        if not isinstance(mappings, list):
            continue

        # occurrence_key -> set(urls)
        occ_urls: Dict[Tuple[str, str, Optional[int], Optional[int], str], Set[str]] = {}

        for m in mappings:
            if not isinstance(m, dict):
                continue
            claim = safe_str(m.get("claim_text"))
            if not claim:
                continue
            tp = m.get("token_position") or {}
            start_idx = tp.get("start_idx") if isinstance(tp, dict) else None
            end_idx = tp.get("end_idx") if isinstance(tp, dict) else None
            if not isinstance(start_idx, int):
                start_idx = None
            if not isinstance(end_idx, int):
                end_idx = None

            key = (run_id, account_type, start_idx, end_idx, claim)
            urls = occ_urls.setdefault(key, set())

            inline = safe_str(m.get("inline_url"))
            if inline:
                urls.add(inline)
            sources = m.get("sources") or []
            if isinstance(sources, list):
                for s in sources:
                    if not isinstance(s, dict):
                        continue
                    u = safe_str(s.get("url"))
                    if u:
                        urls.add(u)

        for key, urls in occ_urls.items():
            n = len(urls)
            if n <= 0:
                continue
            total += 1
            dist[n] += 1
            if n >= 2:
                multi += 1

            any_listicle = any(is_listicle_url(u, dna_map) for u in urls)
            if any_listicle and n >= 2:
                multi_with_any_listicle += 1
            any_product = any(is_product_page_url(u, dna_map) for u in urls)
            mixed_lp = bool(any_listicle and any_product)

            if n >= 2:
                ts_key = type_set_key(urls, dna_map)
                bname = bucket_name(any_listicle, any_product)
                multi_type_sets_all[ts_key] += 1
                multi_type_sets_by_bucket[bname][ts_key] += 1
            if n >= 2 and mixed_lp:
                multi_mixed_listicle_product += 1
                if out_mixed_csv and len(mixed_rows) < max_mixed_rows:
                    run_id, account_type, start_idx, end_idx, claim = key
                    typed = [{"url": u, "type": url_type(u, dna_map)} for u in sorted(urls)]
                    mixed_rows.append(
                        {
                            "study": "gpt",
                            "run_id": run_id,
                            "account_type": account_type,
                            "start_idx": start_idx,
                            "end_idx": end_idx,
                            "claim_text": claim,
                            "n_urls": n,
                            "urls_json": json.dumps(typed, ensure_ascii=False),
                        }
                    )
            if any_listicle:
                listicle_total += 1
                listicle_dist[n] += 1
                if n >= 2:
                    listicle_multi += 1
                    if mixed_lp:
                        listicle_multi_mixed_listicle_product += 1

            # Multi-cited bucket breakdown (mutually exclusive)
            if n >= 2:
                if mixed_lp:
                    pass
                elif any_listicle and not any_product:
                    multi_listicle_only += 1
                elif any_product and not any_listicle:
                    multi_product_only += 1
                else:
                    multi_neither += 1

            # Listicle-cited multi-cited slice breakdown (mutually exclusive; should sum to listicle_multi)
            if any_listicle and n >= 2 and (not mixed_lp):
                listicle_multi_listicle_only += 1

    summarize_counts("gpt", total, multi, dist)
    print(f"[gpt] multi_mixed_listicle+product={multi_mixed_listicle_product} share_of_multi={pct(multi_mixed_listicle_product, multi)}")
    summarize_multi_type_mix(
        "gpt",
        multi,
        {
            "mixed_listicle+product": multi_mixed_listicle_product,
            "listicle_only": multi_listicle_only,
            "product_only": multi_product_only,
            "neither_listicle_nor_product": multi_neither,
        },
    )
    summarize_top_type_sets("gpt_multi", multi_type_sets_all, multi)
    summarize_top_type_sets("gpt_multi_neither", multi_type_sets_by_bucket["neither_listicle_nor_product"], multi_neither)
    summarize_counts("gpt_listicle_cited", listicle_total, listicle_multi, listicle_dist)
    print(
        f"[gpt_listicle_cited] multi_mixed_listicle+product={listicle_multi_mixed_listicle_product} share_of_multi={pct(listicle_multi_mixed_listicle_product, listicle_multi)}"
    )
    summarize_multi_type_mix(
        "gpt_listicle_cited",
        listicle_multi,
        {
            "mixed_listicle+product": listicle_multi_mixed_listicle_product,
            "listicle_only": listicle_multi_listicle_only,
            "product_only": 0,
            "neither_listicle_nor_product": 0,
        },
    )

    if out_mixed_csv:
        import csv

        os.makedirs(os.path.dirname(out_mixed_csv) or ".", exist_ok=True)
        with open(out_mixed_csv, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "study",
                    "run_id",
                    "account_type",
                    "start_idx",
                    "end_idx",
                    "n_urls",
                    "claim_text",
                    "urls_json",
                ],
            )
            w.writeheader()
            w.writerows(mixed_rows)
        print(f"[gpt] wrote mixed listicle+product cases -> {out_mixed_csv} rows={len(mixed_rows)} (capped={max_mixed_rows})")
    return {
        "total": total,
        "multi": multi,
        "dist": dict(dist),
        "multi_mixed_listicle_product": multi_mixed_listicle_product,
        "multi_listicle_only": multi_listicle_only,
        "multi_product_only": multi_product_only,
        "multi_neither_listicle_nor_product": multi_neither,
        "listicle_total": listicle_total,
        "listicle_multi": listicle_multi,
        "listicle_dist": dict(listicle_dist),
        "listicle_multi_mixed_listicle_product": listicle_multi_mixed_listicle_product,
        "listicle_multi_listicle_only": listicle_multi_listicle_only,
        "multi_type_sets_all": dict(multi_type_sets_all),
        "multi_type_sets_by_bucket": {k: dict(v) for k, v in multi_type_sets_by_bucket.items()},
    }


def analyze_gemini(
    gemini_dir: str,
    resolved_urls: Dict[str, str],
    dna_map: Dict[str, Dict[str, Any]],
    out_mixed_csv: str = "",
    max_mixed_rows: int = 2000,
) -> Dict[str, Any]:
    total = 0
    multi = 0
    dist: Counter = Counter()
    multi_mixed_listicle_product = 0
    multi_listicle_only = 0
    multi_product_only = 0
    multi_neither = 0

    listicle_total = 0
    listicle_multi = 0
    listicle_dist: Counter = Counter()
    listicle_multi_mixed_listicle_product = 0
    listicle_multi_listicle_only = 0

    mixed_rows: List[Dict[str, Any]] = []
    multi_type_sets_all: Counter = Counter()
    multi_type_sets_by_bucket: Dict[str, Counter] = {
        "mixed_listicle+product": Counter(),
        "listicle_only": Counter(),
        "product_only": Counter(),
        "neither_listicle_nor_product": Counter(),
    }

    latest = latest_gemini_files(gemini_dir)
    for run_id, path in sorted(latest.items()):
        try:
            rec = json.load(open(path, "r", encoding="utf-8"))
        except Exception:
            continue

        gm = rec.get("groundingMetadata") or {}
        chunks = gm.get("groundingChunks") or []
        supports = gm.get("groundingSupports") or []
        if not isinstance(chunks, list) or not isinstance(supports, list):
            continue

        chunk_urls: Dict[int, str] = {}
        for idx, ch in enumerate(chunks):
            if not isinstance(ch, dict):
                continue
            web = ch.get("web") or {}
            raw = safe_str(web.get("uri"))
            if not raw:
                continue
            resolved = safe_str(resolved_urls.get(raw)) or raw
            chunk_urls[idx] = resolved

        # occurrence_key -> set(urls)
        occ_urls: Dict[Tuple[str, Optional[int], Optional[int], str], Set[str]] = {}
        for s in supports:
            if not isinstance(s, dict):
                continue
            seg = s.get("segment") or {}
            if not isinstance(seg, dict):
                continue
            text = safe_str(seg.get("text"))
            if not text:
                continue
            start_idx = seg.get("startIndex")
            end_idx = seg.get("endIndex")
            if not isinstance(start_idx, int):
                start_idx = None
            if not isinstance(end_idx, int):
                end_idx = None

            idxs = s.get("groundingChunkIndices") or []
            if not isinstance(idxs, list):
                continue

            key = (run_id, start_idx, end_idx, text)
            urls = occ_urls.setdefault(key, set())
            for ci in idxs:
                if not isinstance(ci, int):
                    continue
                u = chunk_urls.get(ci)
                if u:
                    urls.add(u)

        for key, urls in occ_urls.items():
            n = len(urls)
            if n <= 0:
                continue
            total += 1
            dist[n] += 1
            if n >= 2:
                multi += 1

            any_listicle = any(is_listicle_url(u, dna_map) for u in urls)
            any_product = any(is_product_page_url(u, dna_map) for u in urls)
            mixed_lp = bool(any_listicle and any_product)

            if n >= 2:
                ts_key = type_set_key(urls, dna_map)
                bname = bucket_name(any_listicle, any_product)
                multi_type_sets_all[ts_key] += 1
                multi_type_sets_by_bucket[bname][ts_key] += 1
            if n >= 2 and mixed_lp:
                multi_mixed_listicle_product += 1
                if out_mixed_csv and len(mixed_rows) < max_mixed_rows:
                    run_id, start_idx, end_idx, text = key
                    typed = [{"url": u, "type": url_type(u, dna_map)} for u in sorted(urls)]
                    mixed_rows.append(
                        {
                            "study": "gemini",
                            "run_id": run_id,
                            "account_type": "",
                            "start_idx": start_idx,
                            "end_idx": end_idx,
                            "claim_text": text,
                            "n_urls": n,
                            "urls_json": json.dumps(typed, ensure_ascii=False),
                        }
                    )
            if any_listicle:
                listicle_total += 1
                listicle_dist[n] += 1
                if n >= 2:
                    listicle_multi += 1
                    if mixed_lp:
                        listicle_multi_mixed_listicle_product += 1

            # Multi-cited bucket breakdown (mutually exclusive)
            if n >= 2:
                if mixed_lp:
                    pass
                elif any_listicle and not any_product:
                    multi_listicle_only += 1
                elif any_product and not any_listicle:
                    multi_product_only += 1
                else:
                    multi_neither += 1

            # Listicle-cited multi-cited slice breakdown (mutually exclusive; should sum to listicle_multi)
            if any_listicle and n >= 2 and (not mixed_lp):
                listicle_multi_listicle_only += 1

    summarize_counts("gemini", total, multi, dist)
    print(f"[gemini] multi_mixed_listicle+product={multi_mixed_listicle_product} share_of_multi={pct(multi_mixed_listicle_product, multi)}")
    summarize_multi_type_mix(
        "gemini",
        multi,
        {
            "mixed_listicle+product": multi_mixed_listicle_product,
            "listicle_only": multi_listicle_only,
            "product_only": multi_product_only,
            "neither_listicle_nor_product": multi_neither,
        },
    )
    summarize_top_type_sets("gemini_multi", multi_type_sets_all, multi)
    summarize_top_type_sets("gemini_multi_neither", multi_type_sets_by_bucket["neither_listicle_nor_product"], multi_neither)
    summarize_counts("gemini_listicle_cited", listicle_total, listicle_multi, listicle_dist)
    print(
        f"[gemini_listicle_cited] multi_mixed_listicle+product={listicle_multi_mixed_listicle_product} share_of_multi={pct(listicle_multi_mixed_listicle_product, listicle_multi)}"
    )
    summarize_multi_type_mix(
        "gemini_listicle_cited",
        listicle_multi,
        {
            "mixed_listicle+product": listicle_multi_mixed_listicle_product,
            "listicle_only": listicle_multi_listicle_only,
            "product_only": 0,
            "neither_listicle_nor_product": 0,
        },
    )

    if out_mixed_csv:
        import csv

        os.makedirs(os.path.dirname(out_mixed_csv) or ".", exist_ok=True)
        with open(out_mixed_csv, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "study",
                    "run_id",
                    "account_type",
                    "start_idx",
                    "end_idx",
                    "n_urls",
                    "claim_text",
                    "urls_json",
                ],
            )
            w.writeheader()
            w.writerows(mixed_rows)
        print(f"[gemini] wrote mixed listicle+product cases -> {out_mixed_csv} rows={len(mixed_rows)} (capped={max_mixed_rows})")
    return {
        "total": total,
        "multi": multi,
        "dist": dict(dist),
        "multi_mixed_listicle_product": multi_mixed_listicle_product,
        "multi_listicle_only": multi_listicle_only,
        "multi_product_only": multi_product_only,
        "multi_neither_listicle_nor_product": multi_neither,
        "listicle_total": listicle_total,
        "listicle_multi": listicle_multi,
        "listicle_dist": dict(listicle_dist),
        "listicle_multi_mixed_listicle_product": listicle_multi_mixed_listicle_product,
        "listicle_multi_listicle_only": listicle_multi_listicle_only,
        "multi_type_sets_all": dict(multi_type_sets_all),
        "multi_type_sets_by_bucket": {k: dict(v) for k, v in multi_type_sets_by_bucket.items()},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpt-mapping-dir", default="datapass/citation_mappings")
    ap.add_argument("--gemini-raw-dir", default="data/gemini_raw_responses")
    ap.add_argument("--resolved-urls", default="data/resolved_grounding_urls.json")
    ap.add_argument(
        "--dna-gpt",
        default="datapass/page_labels_control_gpt5_mini.jsonl",
        help="DNA labels to detect listicle URLs for GPT study (type=listicle).",
    )
    ap.add_argument(
        "--dna-gemini",
        default="datapass/page_labels_combined_v2.5.jsonl,datapass/page_labels_gemini_v2.5.jsonl",
        help="Comma-separated DNA label jsonls to detect listicle URLs for Gemini study.",
    )
    ap.add_argument("--out-json", default="")
    ap.add_argument("--out-mixed-csv-gpt", default="data/enrichment/mixed_listicle_plus_product_citations_gpt.csv")
    ap.add_argument("--out-mixed-csv-gemini", default="data/enrichment/mixed_listicle_plus_product_citations_gemini.csv")
    ap.add_argument("--max-mixed-rows", type=int, default=2000)
    args = ap.parse_args()

    print("[multi_source] loading DNA maps...")
    gpt_dna = load_dna_map([args.dna_gpt])
    gem_dna = load_dna_map([p.strip() for p in safe_str(args.dna_gemini).split(",") if p.strip()])

    print("[multi_source] loading resolved grounding URL map...")
    resolved = load_resolved_urls(args.resolved_urls)

    print("[multi_source] analyzing GPT citation mappings...")
    gpt_stats = analyze_gpt(
        args.gpt_mapping_dir,
        gpt_dna,
        out_mixed_csv=args.out_mixed_csv_gpt,
        max_mixed_rows=args.max_mixed_rows,
    )

    print("[multi_source] analyzing Gemini grounding supports (latest per run)...")
    gem_stats = analyze_gemini(
        args.gemini_raw_dir,
        resolved,
        gem_dna,
        out_mixed_csv=args.out_mixed_csv_gemini,
        max_mixed_rows=args.max_mixed_rows,
    )

    if args.out_json:
        os.makedirs(os.path.dirname(args.out_json) or ".", exist_ok=True)
        json.dump({"gpt": gpt_stats, "gemini": gem_stats}, open(args.out_json, "w", encoding="utf-8"), indent=2)
        print(f"[multi_source] wrote {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

