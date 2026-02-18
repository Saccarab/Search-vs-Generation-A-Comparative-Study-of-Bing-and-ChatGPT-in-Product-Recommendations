#!/usr/bin/env python3
"""
Build LLM-ready prompt jobs for per-product semantic fidelity verification against cited listicles.

Design goals:
- Work for BOTH GPT study and Gemini study.
- Do NOT depend on response.listicle_products rosters (not available everywhere).
- Use response-side evidence:
  - GPT: datapass/citation_mappings/*_mapping.json (claim_text + inline_url)
  - Gemini: data/gemini_raw_responses/* (groundingSupports + groundingChunks + response text)
- For each occurrence of a cited listicle, produce one job containing:
  - listicle URL + host domain
  - ordered "provided roster" derived from response-side snippets
  - listicle page text chunks (from datapass/url_content_*.csv, fallback to data/fetched_content)
  - a ready-to-send raw prompt string (JSON-only output)

Outputs:
- data/enrichment/semantic_fidelity_jobs_gpt.jsonl
- data/enrichment/semantic_fidelity_jobs_gemini.jsonl
- data/enrichment/semantic_fidelity_missing_listicle_content.csv
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


def host_domain_from_url(raw_url: str) -> str:
    u = raw_url or ""
    if not u:
        return ""
    if "://" not in u:
        u = "https://" + u
    try:
        from urllib.parse import urlparse

        p = urlparse(u)
        host = (p.hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


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
    by_key: Dict[str, PageText] = {}
    if not url_content_csv or not os.path.exists(url_content_csv):
        return by_key
    with open(url_content_csv, "r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            url = (row.get("url") or "").strip()
            final_url = (row.get("final_url") or "").strip()
            if not url and not final_url:
                continue
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
                by_key.setdefault(k, pt)
    return by_key


def load_page_text_from_fetched_content(fetched_dir: str, url_key: str) -> Optional[PageText]:
    if not fetched_dir or not os.path.isdir(fetched_dir):
        return None
    h = short_hash(url_key)
    txt_path = os.path.join(fetched_dir, f"{h}.txt")
    if not os.path.exists(txt_path):
        return None
    try:
        content = open(txt_path, "r", encoding="utf-8", errors="ignore").read()
    except Exception:
        return None
    if not content.strip():
        return None
    meta_path = os.path.join(fetched_dir, f"{h}.json")
    meta: Dict[str, Any] = {}
    if os.path.exists(meta_path):
        try:
            meta = json.load(open(meta_path, "r", encoding="utf-8"))
        except Exception:
            meta = {}
    return PageText(
        url=str(meta.get("url") or ""),
        final_url=str(meta.get("final_url") or ""),
        status=meta.get("status") if isinstance(meta.get("status"), int) else None,
        page_title=str(meta.get("page_title") or ""),
        meta_description=str(meta.get("meta_description") or ""),
        canonical_url=str(meta.get("canonical_url") or ""),
        content=content,
    )


def chunk_text(text: str, chunk_chars: int = 3500, overlap_chars: int = 250) -> List[str]:
    if not text:
        return []
    t = re.sub(r"\s+", " ", text).strip()
    if not t:
        return []
    out = []
    i = 0
    n = len(t)
    step = max(1, chunk_chars - overlap_chars)
    while i < n:
        out.append(t[i : i + chunk_chars])
        i += step
        if len(out) > 2000:
            break
    return out


def minify_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()

def extract_product_name_from_snippet(snippet: str) -> str:
    """
    Heuristic:
    - if snippet contains **Product**, pick that
    - else take first phrase before dash/colon/newline
    """
    s = (snippet or "").strip()
    if not s:
        return ""
    m = re.search(r"\*\*(.+?)\*\*", s)
    if m:
        cand = m.group(1).strip()
        if 2 <= len(cand) <= 80:
            return cand
    # drop bullets/numbering
    s2 = re.sub(r"^\s*[-*•\d\.\)#\s]+", "", s)
    # split on common separators
    head = re.split(r"\s*[–—\-:|\n]\s*", s2, maxsplit=1)[0].strip()
    head = re.sub(r"\s*\([^)]*\)\s*", " ", head).strip()
    return head[:80]


PROMPT_TEMPLATE = """You are an evaluator. Your job is to verify whether a cited listicle supports what the model claimed about specific products.

Return ONLY valid JSON. No prose, no markdown.

DEFINITIONS
- "response_claim_snippet" = exact text from the model response about the product.
- "evidence_quote" = exact quote from the LISTICLE PAGE TEXT that supports or contradicts the claim.
- "multiple_products_suspected" = whether this single roster item appears to reference MORE THAN ONE distinct product/tool
  (e.g., "Kapwing & VEED.io" or "Otter.ai or Fireflies"). If unsure, set false.
- "roster_item_is_product" = whether product_name is actually a specific product/tool name (not "Yes", "Notes", "Tips", a full sentence, or a source label).
- "roster_item_type" = one of: "product" | "general_claim" | "meta_or_source_label"
- "present_in_listicle" meaning:
  - If roster_item_is_product is true: "yes" | "no" | "unclear"
  - If roster_item_is_product is false: MUST be "n/a"
- "total_products_in_listicle" = total count of distinct products/tools recommended or listed on the page.

SCORING: semantic_fidelity_score_1_5
5 = Fully supported (product present + claim clearly supported, including numbers if any)
4 = Mostly supported (minor mismatch/detail off)
3 = Partially supported/vague (product present but claim not clearly supported)
2 = Weakly supported (thin/indirect evidence)
1 = Not supported or contradicted (product missing or claim contradicts page)

TASK
Given:
(1) LISTICLE URL
(2) LISTICLE PAGE TEXT
(3) PROVIDED ROSTER from the model response (ordered) with claim snippets

A) Scan the LISTICLE PAGE TEXT and count the total number of distinct products/tools recommended.
B) For EACH product in the provided roster:
A-1) Set roster_item_is_product (true/false) and roster_item_type.
A0) Set multiple_products_suspected true/false based ONLY on the product_name + response_claim_snippet.
A) If roster_item_is_product is false:
    - present_in_listicle MUST be "n/a"
    - listicle_rank MUST be null
    - (You can still score semantic_fidelity_score_1_5 based on whether the claim snippet is supported by the page text.)
   Else (roster_item_is_product is true):
    - Decide if the product is present in the listicle: "yes" | "no" | "unclear"
    - If present, extract its listicle rank/position if clearly stated, else null
C) Provide an evidence_quote from the page text
D) Give semantic_fidelity_score_1_5 and a short rationale

Also:
E) Determine whether the listicle includes a product that appears to be owned by the host domain (same brand/product as the website). If yes, output its name and an evidence_quote, and whether it is missing from the provided roster.

INPUTS
LISTICLE_URL: {listicle_url}
HOST_DOMAIN: {host_domain}

PROVIDED_ROSTER_FROM_RESPONSE (ordered):
{roster_json}

LISTICLE_PAGE_TEXT:
{page_text}

OUTPUT JSON SCHEMA
{{
  "listicle_url": string,
  "host_domain": string,
  "total_products_in_listicle": integer,
  "products": [
    {{
      "product_name": string,
      "roster_item_is_product": true|false,
      "roster_item_type": "product"|"general_claim"|"meta_or_source_label",
      "multiple_products_suspected": true|false,
      "present_in_listicle": "yes"|"no"|"unclear"|"n/a",
      "listicle_rank": integer|null,
      "response_claim_snippet": string,
      "evidence_quote": string|null,
      "semantic_fidelity_score_1_5": 1|2|3|4|5,
      "rationale": string
    }}
  ],
  "host_product": {{
    "host_product_in_listicle": true|false|"unclear",
    "host_product_name": string|null,
    "evidence_quote": string|null,
    "missing_from_provided_roster": true|false|"unclear"
  }}
}}
"""


def page_text_for_prompt(pt: PageText) -> str:
    """
    Return full raw page text for the prompt.
    NOTE: Intentionally no truncation/capping logic (per study requirement).
    """
    return pt.content or ""


def load_dna_map(jsonl_paths: List[str]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for p in jsonl_paths:
        if not os.path.exists(p):
            continue
        for rec in iter_jsonl(p):
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


def build_jobs_gpt(mapping_dir: str, dna_map: Dict[str, Dict[str, Any]], page_text: Dict[str, PageText], fetched_dir: str, out_jsonl: str, missing_csv_rows: List[Dict[str, Any]], max_roster: int, max_chunks: int, solo_only: bool) -> int:
    os.makedirs(os.path.dirname(out_jsonl), exist_ok=True)
    n_jobs = 0
    with open(out_jsonl, "w", encoding="utf-8") as out:
        for fn in sorted(os.listdir(mapping_dir)):
            if not fn.endswith("_mapping.json"):
                continue
            if fn.startswith("_"):
                continue
            path = os.path.join(mapping_dir, fn)
            try:
                rec = json.load(open(path, "r", encoding="utf-8"))
            except Exception:
                continue
            base_run_id = rec.get("run_id") or ""
            account_type = rec.get("account_type") or ""
            run_id = f"{base_run_id}_{account_type}" if account_type in ("personal", "enterprise") else base_run_id
            mappings = rec.get("citation_mappings") or []
            if not isinstance(mappings, list):
                continue

            # Group claim snippets by cited listicle URL
            by_listicle: Dict[str, List[Dict[str, Any]]] = {}
            for m in mappings:
                if not isinstance(m, dict):
                    continue
                url = (m.get("inline_url") or "").strip()
                if not url:
                    continue
                cited_urls: Set[str] = set()
                cited_urls.add(url)
                sources = m.get("sources") or []
                if isinstance(sources, list):
                    for s in sources:
                        if not isinstance(s, dict):
                            continue
                        su = (s.get("url") or "").strip()
                        if su:
                            cited_urls.add(su)
                if solo_only and len(cited_urls) != 1:
                    continue
                
                k = normalize_url_key(url)
                dna = dna_map.get(k) or {}
                if (dna.get("type") or "") != "listicle":
                    continue

                # STAGE 2 FILTER: Even if cited_urls is 1, GPT text with "+1" is a multi-citation signal
                claim = (m.get("claim_text") or "").strip()
                if solo_only and re.search(r"\+\d+\s*$", claim):
                    continue

                if not claim:
                    continue
                pos = None
                tp = m.get("token_position") or {}
                if isinstance(tp, dict) and isinstance(tp.get("start_idx"), int):
                    pos = int(tp.get("start_idx"))
                by_listicle.setdefault(k, []).append({"claim": claim, "pos": pos, "raw_url": url, "cited_urls": sorted(cited_urls)})

            for k, entries in by_listicle.items():
                entries.sort(key=lambda x: (x["pos"] is None, x["pos"] if x["pos"] is not None else 10**18))
                listicle_url = entries[0]["raw_url"]
                host_domain = host_domain_from_url(listicle_url)

                roster = []
                roster_meta = []
                for e in entries[:max_roster]:
                    snippet = e["claim"]
                    pn = extract_product_name_from_snippet(snippet)
                    roster.append(
                        {
                            "product_name": pn,
                            "response_claim_snippet": snippet,
                        }
                    )
                    roster_meta.append(
                        {
                            "product_name": pn,
                            "response_claim_snippet": snippet,
                            "cited_urls": e.get("cited_urls") or [],
                        }
                    )

                pt = page_text.get(k)
                if pt is None:
                    pt = load_page_text_from_fetched_content(fetched_dir, k)
                if pt is None:
                    missing_csv_rows.append({"study": "gpt", "run_id": run_id, "listicle_url": listicle_url})
                    continue
                full_text = page_text_for_prompt(pt)

                case_id = f"gpt__{run_id}__{short_hash(k)}"
                prompt = PROMPT_TEMPLATE.format(
                    listicle_url=listicle_url,
                    host_domain=host_domain,
                    roster_json=json.dumps(roster, ensure_ascii=False),
                    page_text=full_text,
                )
                job = {
                    "case_id": case_id,
                    "study": "gpt",
                    "run_id": run_id,
                    "account_type": account_type,
                    "cited_listicle_url": listicle_url,
                    "host_domain": host_domain,
                    "provided_roster_from_response": roster,
                    "roster_items_meta": roster_meta,
                    "page_text_meta": {
                        "url": pt.url,
                        "final_url": pt.final_url,
                        "status": pt.status,
                        "page_title": pt.page_title,
                        "canonical_url": pt.canonical_url,
                    },
                    "prompt": prompt,
                }
                out.write(json.dumps(job, ensure_ascii=False) + "\n")
                n_jobs += 1
    return n_jobs


def build_jobs_gemini(gemini_dir: str, resolved_urls_path: str, dna_map: Dict[str, Dict[str, Any]], page_text: Dict[str, PageText], fetched_dir: str, out_jsonl: str, missing_csv_rows: List[Dict[str, Any]], max_roster: int, max_chunks: int, solo_only: bool) -> int:
    os.makedirs(os.path.dirname(out_jsonl), exist_ok=True)
    resolved: Dict[str, str] = {}
    if resolved_urls_path and os.path.exists(resolved_urls_path):
        try:
            resolved = json.load(open(resolved_urls_path, "r", encoding="utf-8"))
        except Exception:
            resolved = {}

    latest = latest_gemini_files(gemini_dir)
    n_jobs = 0
    with open(out_jsonl, "w", encoding="utf-8") as out:
        for base_run_id, path in sorted(latest.items()):
            try:
                rec = json.load(open(path, "r", encoding="utf-8"))
            except Exception:
                continue
            resp_text = (((rec.get("content") or {}).get("parts") or [{}])[0] or {}).get("text") or ""
            gm = rec.get("groundingMetadata") or {}
            chunks = gm.get("groundingChunks") or []
            supports = gm.get("groundingSupports") or []
            if not isinstance(chunks, list) or not isinstance(supports, list):
                continue

            # chunk_index -> resolved URL
            chunk_urls: Dict[int, str] = {}
            for idx, ch in enumerate(chunks):
                if not isinstance(ch, dict):
                    continue
                web = ch.get("web") or {}
                raw = (web.get("uri") or "").strip()
                if not raw:
                    continue
                resolved_uri = resolved.get(raw) or raw
                chunk_urls[idx] = resolved_uri

            # Group support segments by listicle URL key (only for listicle chunks)
            by_listicle: Dict[str, List[Dict[str, Any]]] = {}
            for s in supports:
                if not isinstance(s, dict):
                    continue
                seg = s.get("segment") or {}
                seg_text = (seg.get("text") or "").strip()
                if not seg_text:
                    continue
                start_idx = seg.get("startIndex")
                if not isinstance(start_idx, int):
                    start_idx = None
                idxs = s.get("groundingChunkIndices") or []
                if not isinstance(idxs, list):
                    continue

                cited_urls: Set[str] = set()
                for ci in idxs:
                    if not isinstance(ci, int):
                        continue
                    u = chunk_urls.get(ci)
                    if u:
                        cited_urls.add(u)
                if not cited_urls:
                    continue
                if solo_only and len(cited_urls) != 1:
                    continue
                
                # STAGE 2 FILTER: Even if cited_urls is 1, GPT text with "+1" is a multi-citation signal
                if solo_only and re.search(r"\+\d+\s*$", seg_text):
                    continue

                listicle_keys: Set[str] = set()
                listicle_url_by_key: Dict[str, str] = {}
                for u in cited_urls:
                    k = normalize_url_key(u)
                    dna = dna_map.get(k) or {}
                    if (dna.get("type") or "") == "listicle":
                        listicle_keys.add(k)
                        listicle_url_by_key.setdefault(k, u)
                if not listicle_keys:
                    continue

                for lk in sorted(listicle_keys):
                    by_listicle.setdefault(lk, []).append(
                        {
                            "claim": seg_text,
                            "pos": start_idx,
                            "raw_url": listicle_url_by_key.get(lk) or next(iter(cited_urls)),
                            "cited_urls": sorted(cited_urls),
                        }
                    )

            for k, entries in by_listicle.items():
                entries.sort(key=lambda x: (x["pos"] is None, x["pos"] if x["pos"] is not None else 10**18))
                listicle_url = entries[0]["raw_url"]
                host_domain = host_domain_from_url(listicle_url)

                roster = []
                roster_meta = []
                for e in entries[:max_roster]:
                    snippet = e["claim"]
                    pn = extract_product_name_from_snippet(snippet)
                    roster.append(
                        {
                            "product_name": pn,
                            "response_claim_snippet": snippet,
                        }
                    )
                    roster_meta.append(
                        {
                            "product_name": pn,
                            "response_claim_snippet": snippet,
                            "cited_urls": e.get("cited_urls") or [],
                        }
                    )

                pt = page_text.get(k)
                if pt is None:
                    pt = load_page_text_from_fetched_content(fetched_dir, k)
                if pt is None:
                    missing_csv_rows.append({"study": "gemini", "run_id": base_run_id, "listicle_url": listicle_url})
                    continue
                full_text = page_text_for_prompt(pt)

                case_id = f"gemini__{base_run_id}__{short_hash(k)}"
                prompt = PROMPT_TEMPLATE.format(
                    listicle_url=listicle_url,
                    host_domain=host_domain,
                    roster_json=json.dumps(roster, ensure_ascii=False),
                    page_text=full_text,
                )
                job = {
                    "case_id": case_id,
                    "study": "gemini",
                    "run_id": base_run_id,
                    "cited_listicle_url": listicle_url,
                    "host_domain": host_domain,
                    "provided_roster_from_response": roster,
                    "roster_items_meta": roster_meta,
                    "response_text": resp_text[:12000],
                    "page_text_meta": {
                        "url": pt.url,
                        "final_url": pt.final_url,
                        "status": pt.status,
                        "page_title": pt.page_title,
                        "canonical_url": pt.canonical_url,
                    },
                    "prompt": prompt,
                }
                out.write(json.dumps(job, ensure_ascii=False) + "\n")
                n_jobs += 1
    return n_jobs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url-content-csv", default="datapass/url_content_2026-01-31-04-26-20.csv")
    ap.add_argument("--fetched-dir", default="data/fetched_content")
    ap.add_argument("--gpt-mapping-dir", default="datapass/citation_mappings")
    ap.add_argument("--gemini-raw-dir", default="data/gemini_raw_responses")
    ap.add_argument("--resolved-urls", default="data/resolved_grounding_urls.json")
    ap.add_argument("--out-gpt", default="data/enrichment/semantic_fidelity_jobs_gpt.jsonl")
    ap.add_argument("--out-gemini", default="data/enrichment/semantic_fidelity_jobs_gemini.jsonl")
    ap.add_argument("--missing-out", default="data/enrichment/semantic_fidelity_missing_listicle_content.csv")
    ap.add_argument("--max-roster", type=int, default=10)
    ap.add_argument(
        "--solo-only",
        action="store_true",
        help="Only include claim/segment occurrences that cite exactly ONE unique URL (to avoid multi-source claims).",
    )
    args = ap.parse_args()

    page_text = load_page_text_by_url_key(args.url_content_csv)

    # GPT listicle classification
    gpt_dna = load_dna_map(["datapass/page_labels_control_gpt5_mini.jsonl"])
    # Gemini listicle classification
    gemini_dna = load_dna_map(["datapass/page_labels_combined_v2.5.jsonl", "datapass/page_labels_gemini_v2.5.jsonl"])

    missing_rows: List[Dict[str, Any]] = []

    n_gpt = build_jobs_gpt(
        mapping_dir=args.gpt_mapping_dir,
        dna_map=gpt_dna,
        page_text=page_text,
        fetched_dir=args.fetched_dir,
        out_jsonl=args.out_gpt,
        missing_csv_rows=missing_rows,
        max_roster=args.max_roster,
        max_chunks=0,
        solo_only=bool(args.solo_only),
    )

    n_gem = build_jobs_gemini(
        gemini_dir=args.gemini_raw_dir,
        resolved_urls_path=args.resolved_urls,
        dna_map=gemini_dna,
        page_text=page_text,
        fetched_dir=args.fetched_dir,
        out_jsonl=args.out_gemini,
        missing_csv_rows=missing_rows,
        max_roster=args.max_roster,
        max_chunks=0,
        solo_only=bool(args.solo_only),
    )

    os.makedirs(os.path.dirname(args.missing_out), exist_ok=True)
    # de-dupe missing listicle URLs
    seen = set()
    rows2 = []
    for r in missing_rows:
        key = (r.get("study"), r.get("listicle_url"))
        if key in seen:
            continue
        seen.add(key)
        rows2.append(r)
    with open(args.missing_out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["study", "run_id", "listicle_url"])
        w.writeheader()
        w.writerows(rows2)

    print(f"Wrote GPT jobs: {n_gpt} -> {args.out_gpt}")
    print(f"Wrote Gemini jobs: {n_gem} -> {args.out_gemini}")
    print(f"Missing listicle content (deduped): {len(rows2)} -> {args.missing_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

