#!/usr/bin/env python3
"""
Build LLM-ready jobs for listicle analysis from the ChatGPT study.

Produces two job streams (JSONL):
  (A) listicle selection/omission (uses full run answer_text + listicle roster)
  (B) listicle fidelity verification (uses claim_texts attributed to the listicle + evidence chunks from the listicle page)

This script does NOT call any LLM. It only prepares inputs so you can run them with your preferred runner/model.

Default assumptions (matching existing repo conventions):
  - ChatGPT run_id in citation_mappings is base form (e.g., "P001_r3") and account_type is "personal|enterprise".
  - The SQLite DB stores runs as "P001_r3_personal" / "P001_r3_enterprise" (viewer convention).
  - Listicle rosters live in: datapass/page_labels_combined_v2.5.jsonl (response.listicle_products)
  - Page text for evidence chunks comes from: datapass/url_content_*.csv (column "content")
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sqlite3
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
    Match the repo's JS normalizeUrlKey() behavior (approx):
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
    """
    Fallback loader for page text from data/fetched_content.

    Convention in this repo:
      - filename is sha256(normalized_url)[:16]
      - metadata in <hash>.json (url, normalized_url, status, ok, etc.)
      - extracted text in <hash>.txt

    Here url_key is the normalized_url_key() output (e.g., "example.com/path?x=1").
    """
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


def safe_filename(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "_", s)
    return s[:180] if len(s) > 180 else s


def run_id_with_account(base_run_id: str, account_type: str) -> str:
    acct = (account_type or "").strip().lower()
    if acct in ("personal", "enterprise"):
        return f"{base_run_id}_{acct}"
    return base_run_id


def load_listicle_rosters(labels_jsonl: str) -> Dict[str, Dict[str, Any]]:
    """
    Returns: url_key -> { url, roster:[{product_name, position_in_listicle}], meta:{...} }
    Only includes urls where response.urls.type == "listicle".
    """
    out: Dict[str, Dict[str, Any]] = {}
    for rec in iter_jsonl(labels_jsonl):
        if not rec.get("ok"):
            continue
        url = rec.get("url") or ""
        resp = rec.get("response") or {}
        urls_obj = resp.get("urls") or {}
        if urls_obj.get("type") != "listicle":
            continue
        products = resp.get("listicle_products")
        roster: List[Dict[str, Any]] = []
        if isinstance(products, list):
            for i, p in enumerate(products):
                if not isinstance(p, dict):
                    continue
                name = (p.get("product_name") or "").strip()
                if not name:
                    continue
                pos = p.get("position_in_listicle")
                if pos is None:
                    pos = p.get("rank")
                try:
                    pos_int = int(pos) if pos is not None else (i + 1)
                except Exception:
                    pos_int = i + 1
                roster.append({"product_name": name, "position_in_listicle": pos_int})

        k = normalize_url_key(url)
        out[k] = {
            "url": url,
            "roster": roster,
            "meta": {
                "title": (resp.get("listicles") or {}).get("title") if isinstance(resp.get("listicles"), dict) else None,
                "domain": (resp.get("listicles") or {}).get("listicle_domain") if isinstance(resp.get("listicles"), dict) else None,
                "listicle_has_ranked_order": (resp.get("listicles") or {}).get("listicle_has_ranked_order") if isinstance(resp.get("listicles"), dict) else None,
                "bias_score": (resp.get("listicles") or {}).get("bias") if isinstance(resp.get("listicles"), dict) else None,
                "promotional_intensity_score": urls_obj.get("promotional_intensity_score"),
                "content_format": urls_obj.get("content_format"),
                "tone": urls_obj.get("tone"),
                "primary_intent": urls_obj.get("primary_intent"),
            },
        }
    return out


def chunk_text(text: str, chunk_chars: int, overlap_chars: int) -> List[str]:
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
        if len(out) > 5000:
            break
    return out


def build_keywords(claims: List[str], roster: List[Dict[str, Any]]) -> List[str]:
    kws: List[str] = []
    # include product names as substrings (lowercased)
    for p in roster[:300]:
        name = (p.get("product_name") or "").strip().lower()
        if name and len(name) >= 4:
            kws.append(name)
    # include salient longer words from claims
    word_re = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9'\\-]{3,}")
    for c in claims:
        for w in word_re.findall(c.lower()):
            if len(w) >= 5:
                kws.append(w)
    # de-dupe while preserving order, keep bounded
    seen = set()
    out = []
    for k in kws:
        if k in seen:
            continue
        seen.add(k)
        out.append(k)
        if len(out) >= 80:
            break
    return out


def select_chunks(all_chunks: List[str], keywords: List[str], max_chunks: int) -> List[Tuple[str, str]]:
    """
    Returns list of (chunk_id, text), selecting the most relevant chunks by simple keyword hit count.
    Always includes the first chunk if present.
    """
    if not all_chunks:
        return []
    scored: List[Tuple[int, int]] = []  # (score, idx)
    for idx, ch in enumerate(all_chunks):
        low = ch.lower()
        score = 0
        for kw in keywords:
            if kw and kw in low:
                score += 1
        scored.append((score, idx))
    scored.sort(key=lambda x: (x[0], -x[1]), reverse=True)

    chosen: List[int] = []
    if 0 not in chosen:
        chosen.append(0)
    for score, idx in scored:
        if idx in chosen:
            continue
        if len(chosen) >= max_chunks:
            break
        if score <= 0 and len(chosen) >= min(max_chunks, 6):
            # after we have a few, don't keep adding totally-unmatched chunks
            continue
        chosen.append(idx)
    chosen.sort()

    out: List[Tuple[str, str]] = []
    for j, idx in enumerate(chosen, 1):
        out.append((f"c{j:02d}", all_chunks[idx]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default="datapass/page_labels_combined_v2.5.jsonl")
    ap.add_argument("--citation_dir", default="datapass/citation_mappings")
    ap.add_argument("--url_content_csv", default="datapass/url_content_2026-01-31-04-26-20.csv")
    ap.add_argument("--fetched_content_dir", default="data/fetched_content", help="Fallback page text source (hashed .txt/.json)")
    ap.add_argument("--db", default="geo_fresh.db")
    ap.add_argument("--out_dir", default="data/listicle_analysis/jobs_chatgpt")
    ap.add_argument("--account_filter", default="all", help="personal|enterprise|all")
    ap.add_argument("--max_runs", type=int, default=0, help="0 = no limit")
    ap.add_argument("--min_claim_chars", type=int, default=20)
    ap.add_argument("--chunk_chars", type=int, default=1200)
    ap.add_argument("--chunk_overlap", type=int, default=180)
    ap.add_argument("--max_evidence_chunks", type=int, default=18)
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    selection_out = os.path.join(args.out_dir, "selection_omission_jobs.jsonl")
    bias_out = os.path.join(args.out_dir, "bias_uptake_jobs.jsonl")
    fidelity_out = os.path.join(args.out_dir, "fidelity_jobs.jsonl")
    stats_out = os.path.join(args.out_dir, "build_stats.json")

    rosters_by_key = load_listicle_rosters(args.labels)
    page_text_by_key = load_page_text_by_url_key(args.url_content_csv)

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    def get_response_text(base_run_id: str, account_type: str) -> str:
        rid = run_id_with_account(base_run_id, account_type)
        row = conn.execute("SELECT response_text FROM runs WHERE run_id = ? LIMIT 1", (rid,)).fetchone()
        if row and (row["response_text"] or "").strip():
            return row["response_text"]
        # fallback: some DBs might store base_run_id only
        row2 = conn.execute("SELECT response_text FROM runs WHERE run_id = ? LIMIT 1", (base_run_id,)).fetchone()
        if row2 and (row2["response_text"] or "").strip():
            return row2["response_text"]
        return ""

    acct_filter = (args.account_filter or "all").strip().lower()

    n_mapping_files = 0
    n_runs = 0
    n_pairs_with_listicle = 0
    n_selection_jobs = 0
    n_fidelity_jobs = 0
    n_missing_response = 0
    n_missing_roster = 0
    n_missing_page_text = 0
    n_bias_jobs = 0

    with open(selection_out, "w", encoding="utf-8") as sel_fh, open(bias_out, "w", encoding="utf-8") as bias_fh, open(fidelity_out, "w", encoding="utf-8") as fid_fh:
        for mp in iter_mapping_files(args.citation_dir):
            n_mapping_files += 1
            try:
                obj = json.load(open(mp, "r", encoding="utf-8"))
            except Exception:
                continue

            base_run_id = (obj.get("run_id") or "").strip()
            account_type = (obj.get("account_type") or "").strip().lower()
            if acct_filter != "all" and account_type != acct_filter:
                continue
            if not base_run_id:
                continue

            run_id_full = run_id_with_account(base_run_id, account_type)
            answer_text = get_response_text(base_run_id, account_type)
            if not answer_text.strip():
                n_missing_response += 1

            mappings = obj.get("citation_mappings")
            if not isinstance(mappings, list):
                continue

            # Group claims by listicle url_key for this run
            listicle_claims: Dict[str, Dict[str, Any]] = {}
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
                    uk = normalize_url_key(u)
                    if uk not in rosters_by_key:
                        continue
                    claim_id = f"{run_id_full}/m{i}/tok_{start_idx}-{end_idx}/u_{short_hash(uk)}"
                    b = listicle_claims.setdefault(
                        uk,
                        {"listicle_url": rosters_by_key[uk]["url"], "claims": []},
                    )
                    b["claims"].append(
                        {
                            "claim_id": claim_id,
                            "claim_text": claim_text.strip(),
                            "run_id": run_id_full,
                            "account_type": account_type,
                            "citation_token": citation_token,
                            "start_idx": start_idx,
                            "end_idx": end_idx,
                            "mapping_type": mapping_type,
                        }
                    )

            if not listicle_claims:
                continue

            n_runs += 1
            if args.max_runs and n_runs > args.max_runs:
                break

            for uk, bundle in listicle_claims.items():
                n_pairs_with_listicle += 1
                roster_bundle = rosters_by_key.get(uk)
                if not roster_bundle:
                    n_missing_roster += 1
                    continue
                roster = roster_bundle.get("roster") or []
                listicle_meta = roster_bundle.get("meta") or {}

                # (A) selection/omission job
                sel_job = {
                    "task_type": "selection_omission",
                    "run_id": run_id_full,
                    "account_type": account_type,
                    "listicle_url": roster_bundle["url"],
                    "answer_text": answer_text,
                    "listicle_roster": roster,
                    "listicle_meta": listicle_meta,
                    "meta": {
                        "prompt": obj.get("prompt"),
                        "source_mapping_file": os.path.basename(mp),
                    },
                }
                sel_fh.write(json.dumps(sel_job, ensure_ascii=False) + "\n")
                n_selection_jobs += 1

                # (A2) bias/uptake job (rank uptake + dismissal/bias warning signals)
                pt_bias = page_text_by_key.get(uk)
                if not pt_bias:
                    pt_bias = load_page_text_from_fetched_content(args.fetched_content_dir, uk)
                
                full_content = pt_bias.content if pt_bias else ""

                bias_job = {
                    "task_type": "bias_uptake",
                    "run_id": run_id_full,
                    "account_type": account_type,
                    "listicle_url": roster_bundle["url"],
                    "answer_text": answer_text,
                    "claims": [{"claim_id": c["claim_id"], "claim_text": c["claim_text"]} for c in bundle["claims"]],
                    "listicle_roster": roster,
                    "listicle_meta": listicle_meta,
                    "full_page_content": full_content,
                    "meta": {
                        "prompt": obj.get("prompt"),
                        "source_mapping_file": os.path.basename(mp),
                    },
                }
                bias_fh.write(json.dumps(bias_job, ensure_ascii=False) + "\n")
                n_bias_jobs += 1

                # (B) fidelity job (claims + evidence chunks)
                pt = page_text_by_key.get(uk)
                if not pt:
                    # fallback: data/fetched_content/<sha256(url_key)[:16]>.txt
                    pt = load_page_text_from_fetched_content(args.fetched_content_dir, uk)
                if not pt:
                    n_missing_page_text += 1
                    continue
                all_chunks = chunk_text(pt.content, args.chunk_chars, args.chunk_overlap)
                claim_texts = [c["claim_text"] for c in bundle["claims"]]
                kws = build_keywords(claim_texts, roster)
                selected = select_chunks(all_chunks, kws, args.max_evidence_chunks)
                evidence_chunks = [{"chunk_id": cid, "text": txt} for cid, txt in selected]

                fid_job = {
                    "task_type": "fidelity",
                    "run_id": run_id_full,
                    "account_type": account_type,
                    "source_url": roster_bundle["url"],
                    "source_type": "listicle",
                    "claims": [{"claim_id": c["claim_id"], "claim_text": c["claim_text"]} for c in bundle["claims"]],
                    "listicle_roster": roster,
                    "evidence_chunks": evidence_chunks,
                    "page_meta": {
                        "url": pt.url,
                        "final_url": pt.final_url,
                        "status": pt.status,
                        "page_title": pt.page_title,
                        "canonical_url": pt.canonical_url,
                    },
                    "meta": {
                        "prompt": obj.get("prompt"),
                        "source_mapping_file": os.path.basename(mp),
                        "chunk_chars": args.chunk_chars,
                        "chunk_overlap": args.chunk_overlap,
                        "max_evidence_chunks": args.max_evidence_chunks,
                    },
                }
                fid_fh.write(json.dumps(fid_job, ensure_ascii=False) + "\n")
                n_fidelity_jobs += 1

    conn.close()

    with open(stats_out, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "mapping_files_seen": n_mapping_files,
                "runs_with_any_listicle": n_runs,
                "run_listicle_pairs": n_pairs_with_listicle,
                "selection_jobs": n_selection_jobs,
                "bias_uptake_jobs": n_bias_jobs,
                "fidelity_jobs": n_fidelity_jobs,
                "missing_response_text_runs": n_missing_response,
                "missing_roster_pairs": n_missing_roster,
                "missing_page_text_pairs": n_missing_page_text,
                "out_files": {
                    "selection_omission_jobs": selection_out,
                    "bias_uptake_jobs": bias_out,
                    "fidelity_jobs": fidelity_out,
                    "stats": stats_out,
                },
            },
            fh,
            ensure_ascii=False,
            indent=2,
        )

    print("WROTE", selection_out)
    print("WROTE", fidelity_out)
    print("WROTE", stats_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

