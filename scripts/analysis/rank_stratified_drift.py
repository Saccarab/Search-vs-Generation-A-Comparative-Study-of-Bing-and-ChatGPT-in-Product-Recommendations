import csv
import json
import os
import sqlite3
from collections import defaultdict
import argparse

def norm_key(u: str) -> str:
    if not u:
        return ""
    u = u.strip().lower()
    if "://" in u:
        u = u.split("://", 1)[1]
    if u.startswith("www."):
        u = u[4:]
    if u.endswith("/"):
        u = u[:-1]
    if "?" in u:
        u = u.split("?", 1)[0]
    return u

def load_embedded_bundle(js_path: str) -> dict:
    with open(js_path, "r", encoding="utf-8") as f:
        content = f.read()
    marker = "window.EMBEDDED_BUNDLE = "
    if marker not in content:
        raise RuntimeError(f"Could not find embedded bundle marker in {js_path}")
    json_str = content.split(marker, 1)[1].strip().rstrip(";")
    return json.loads(json_str)

def load_jsonl_dna(jsonl_paths: list[str]) -> dict:
    out: dict[str, dict] = {}
    for p in jsonl_paths:
        if not os.path.exists(p):
            continue
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                url = d.get("url") or (d.get("response") or {}).get("urls", {}).get("url")
                if not url:
                    continue
                nk = norm_key(url)
                resp = d.get("response", {})
                dna = resp.get("urls", d)
                if nk in out and isinstance(out[nk], dict) and isinstance(dna, dict):
                    out[nk].update(dna)
                else:
                    out[nk] = dna
    return out

CAT_FIELDS = ["primary_intent", "content_format", "tone", "type"]
BOOL_FIELDS = [
    "has_tables",
    "has_numbered_lists",
    "has_bullet_points",
    "has_pros_cons",
    "is_vendor_owned",
    "is_current_year_2026",
    "has_clear_authorship",
]
# Score-like fields are binned via the lens: score>=4:<field>
SCORE_FIELDS = [
    "expertise_signal_score",
    "freshness_cue_strength",
    "readability_score",
    "heading_density",
    "spamminess_score",
]

def feature_counts(dna_list: list[dict]) -> tuple[dict[str, int], int]:
    total = len(dna_list)
    counts: dict[str, int] = defaultdict(int)
    if total == 0:
        return {}, 0

    for d in dna_list:
        if not isinstance(d, dict):
            continue
        for f in CAT_FIELDS:
            val = d.get(f) if f != "content_format" else (d.get("content_format") or d.get("type"))
            if not val: val = "unknown"
            counts[f"{f}:{val}"] += 1
        for f in BOOL_FIELDS:
            val = d.get(f)
            if val is True or str(val) == "1" or str(val).lower() == "true":
                counts[f"bool:{f}"] += 1
        for f in SCORE_FIELDS:
            v = d.get(f)
            try:
                iv = int(v)
                if iv >= 4: counts[f"score>=4:{f}"] += 1
            except: pass
    return dict(counts), total

def counts_to_pct(counts: dict[str, int], total: int) -> dict[str, float]:
    if total <= 0: return {}
    return {k: (v / total) * 100.0 for k, v in counts.items()}

def write_rank_stratified_csv(out_path, menu_by_rank, order_by_rank, max_rank=10):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    rows = []
    for r in range(1, max_rank + 1):
        m_counts, m_total = feature_counts(menu_by_rank.get(r, []))
        o_counts, o_total = feature_counts(order_by_rank.get(r, []))
        m_pct = counts_to_pct(m_counts, m_total)
        o_pct = counts_to_pct(o_counts, o_total)
        all_keys = sorted(set(m_counts.keys()) | set(o_counts.keys()))
        for k in all_keys:
            rows.append({"rank": r, "feature": k, "menu_n": m_total, "order_n": o_total, 
                         "menu_count": m_counts.get(k, 0), "order_count": o_counts.get(k, 0),
                         "menu_pct": round(m_pct.get(k, 0.0), 4), "order_pct": round(o_pct.get(k, 0.0), 4),
                         "drift_pp": round(o_pct.get(k, 0.0) - m_pct.get(k, 0.0), 4)})
    
    # Global row (rank 0)
    m_all = [d for r in range(1, max_rank+1) for d in menu_by_rank.get(r, [])]
    o_all = [d for r in range(1, max_rank+1) for d in order_by_rank.get(r, [])]
    m_counts, m_total = feature_counts(m_all)
    o_counts, o_total = feature_counts(o_all)
    m_pct = counts_to_pct(m_counts, m_total)
    o_pct = counts_to_pct(o_counts, o_total)
    for k in sorted(set(m_counts.keys()) | set(o_counts.keys())):
        rows.append({"rank": 0, "feature": k, "menu_n": m_total, "order_n": o_total,
                     "menu_count": m_counts.get(k, 0), "order_count": o_counts.get(k, 0),
                     "menu_pct": round(m_pct.get(k, 0.0), 4), "order_pct": round(o_pct.get(k, 0.0), 4),
                     "drift_pp": round(o_pct.get(k, 0.0) - m_pct.get(k, 0.0), 4)})

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["rank", "feature", "menu_n", "order_n", "menu_count", "order_count", "menu_pct", "order_pct", "drift_pp"])
        writer.writeheader()
        writer.writerows(rows)

def gemini_rank_stratified(bundle_path, dna_map, filter_type=None, max_rank=10):
    bundle = load_embedded_bundle(bundle_path)
    menu_by_rank, order_by_rank = defaultdict(list), defaultdict(list)
    invisible, no_dna_cit, no_dna_menu = 0, 0, 0
    for run in bundle.get("runs", []):
        serp_min_rank = {}
        for results in (run.get("serps") or {}).values():
            for idx, res in enumerate((results or [])[:max_rank]):
                nk = norm_key(res.get("link"))
                if nk and (nk not in serp_min_rank or (idx+1) < serp_min_rank[nk]):
                    serp_min_rank[nk] = idx + 1
        for nk, rank in serp_min_rank.items():
            dna = dna_map.get(nk)
            if dna:
                if not filter_type or dna.get("type") == filter_type:
                    menu_by_rank[rank].append(dna)
            else: no_dna_menu += 1
        for chunk in run.get("groundingChunks", []) or []:
            u = (chunk.get("web") or {}).get("resolvedUri") or (chunk.get("web") or {}).get("uri")
            nk = norm_key(u)
            if not nk: continue
            if nk not in serp_min_rank: invisible += 1; continue
            dna = dna_map.get(nk)
            if dna:
                if not filter_type or dna.get("type") == filter_type:
                    order_by_rank[serp_min_rank[nk]].append(dna)
            else: no_dna_cit += 1
    return menu_by_rank, order_by_rank, {"invisible": invisible, "no_dna_menu": no_dna_menu, "no_dna_cit": no_dna_cit}

def gpt_rank_stratified(conn, dna_map, engine, account_type, filter_type=None, max_rank=10):
    cur = conn.cursor()
    if engine == "google":
        query = "SELECT chatgpt_run_id, url, url_normalized, position FROM google_results WHERE account_type = ? AND chatgpt_run_id IS NOT NULL AND position <= ?"
    else:
        query = "SELECT run_id, url, url_normalized, position FROM bing_results WHERE account_type = ? AND page_num = 1 AND position <= ?"
    serp_rows = cur.execute(query, (account_type, max_rank)).fetchall()
    
    serp_min_rank_by_run = defaultdict(dict)
    for rid, url, url_norm, pos in serp_rows:
        nk = (url_norm or "").strip().lower() or norm_key(url)
        if nk:
            if nk not in serp_min_rank_by_run[rid] or int(pos) < serp_min_rank_by_run[rid][nk]:
                serp_min_rank_by_run[rid][nk] = int(pos)

    cit_rows = cur.execute("SELECT run_id, url, url_normalized FROM citations WHERE account_type = ?", (account_type,)).fetchall()
    menu_by_rank, order_by_rank = defaultdict(list), defaultdict(list)
    invisible, no_dna_cit, no_dna_menu = 0, 0, 0
    for rid, urlmap in serp_min_rank_by_run.items():
        for nk, rank in urlmap.items():
            dna = dna_map.get(nk)
            if dna:
                if not filter_type or dna.get("type") == filter_type:
                    menu_by_rank[rank].append(dna)
            else: no_dna_menu += 1
    for rid, url, url_norm in cit_rows:
        nk = (url_norm or "").strip().lower() or norm_key(url)
        join_rid = rid
        if engine == "google" and account_type == "personal" and rid.endswith("_personal"):
            join_rid = rid[:-len("_personal")]
        if nk not in serp_min_rank_by_run.get(join_rid, {}): invisible += 1; continue
        dna = dna_map.get(nk)
        if dna:
            if not filter_type or dna.get("type") == filter_type:
                order_by_rank[serp_min_rank_by_run[join_rid][nk]].append(dna)
        else: no_dna_cit += 1
    return menu_by_rank, order_by_rank, {"invisible": invisible, "no_dna_menu": no_dna_menu, "no_dna_cit": no_dna_cit}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", help="Filter by content type (e.g. listicle, product_page)")
    parser.add_argument("--suffix", help="Suffix for output filenames", default="")
    args = parser.parse_args()

    bundle_path = "tools/GeminiVizApp/data/master_bundle.js"
    db_path = "geo_fresh.db"
    gemini_dna = load_jsonl_dna(["datapass/page_labels_combined_v2.5.jsonl", "datapass/page_labels_gemini_v2.5.jsonl"])
    gpt_dna = load_jsonl_dna(["datapass/page_labels_control_gpt5_mini.jsonl"])
    conn = sqlite3.connect(db_path)

    # max_rank differs by study:
    # - Google: Top10
    # - Enterprise Bing: we still compute 1..10 in CSV, but downstream reporting may omit 6..10
    # - Personal Bing: requested Top1..5 only (Page-1 depth is variable)
    configs = [
        ("gemini", "google", None, gemini_dna, "rank_stratified_drift_gemini_google_top10", 10),
        ("gpt_personal", "google", "personal", gpt_dna, "rank_stratified_drift_gpt_personal_google_top10", 10),
        ("gpt_enterprise", "bing", "enterprise", gpt_dna, "rank_stratified_drift_gpt_enterprise_bing_page1", 10),
        ("gpt_personal_bing", "bing", "personal", gpt_dna, "rank_stratified_drift_gpt_personal_bing_page1_top5", 5),
    ]

    for label, engine, acc_type, dna_map, base_name, max_rank in configs:
        if label == "gemini":
            m, o, meta = gemini_rank_stratified(bundle_path, dna_map, filter_type=args.type, max_rank=max_rank)
        else:
            m, o, meta = gpt_rank_stratified(conn, dna_map, engine, acc_type, filter_type=args.type, max_rank=max_rank)
        
        fname = f"data/enrichment/{base_name}{args.suffix}.csv"
        write_rank_stratified_csv(fname, m, o, max_rank=max_rank)
        print(f"Wrote {fname}")

    conn.close()

if __name__ == "__main__":
    main()
