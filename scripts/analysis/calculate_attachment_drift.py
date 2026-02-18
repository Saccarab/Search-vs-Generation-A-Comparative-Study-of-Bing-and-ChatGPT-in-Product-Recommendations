import csv
import json
import os
import sqlite3
from collections import defaultdict

def norm_key(u: str) -> str:
    if not u: return ""
    u = u.strip().lower()
    if "://" in u: u = u.split("://", 1)[1]
    if u.startswith("www."): u = u[4:]
    if u.endswith("/"): u = u[:-1]
    if "?" in u: u = u.split("?", 1)[0]
    return u

def load_jsonl_dna(jsonl_paths: list[str]) -> dict:
    out: dict[str, dict] = {}
    for p in jsonl_paths:
        if not os.path.exists(p): continue
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line: continue
                try: d = json.loads(line)
                except: continue
                url = d.get("url") or (d.get("response") or {}).get("urls", {}).get("url")
                if not url: continue
                nk = norm_key(url)
                resp = d.get("response", {})
                dna = resp.get("urls", d)
                if nk in out: out[nk].update(dna)
                else: out[nk] = dna
    return out

CAT_FIELDS = ["primary_intent", "content_format", "tone", "type"]
BOOL_FIELDS = ["has_tables", "has_numbered_lists", "has_bullet_points", "has_pros_cons", "is_vendor_owned", "is_current_year_2026", "has_clear_authorship"]
SCORE_FIELDS = ["expertise_signal_score", "freshness_cue_strength", "readability_score", "heading_density"]

def feature_counts(dna_list: list[dict]) -> tuple[dict[str, int], int]:
    total = len(dna_list)
    counts = defaultdict(int)
    if total == 0: return {}, 0
    for d in dna_list:
        if not isinstance(d, dict): continue
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

def calculate_attachment_drift(conn, dna_map, account_type, filter_type=None):
    cur = conn.cursor()
    # Baseline: 'additional' links (the context)
    # Target: 'cited' links (the actual citations)
    
    query = "SELECT citation_type, url_normalized FROM citations WHERE account_type = ?"
    rows = cur.execute(query, (account_type,)).fetchall()
    
    baseline_dna = []
    target_dna = []
    
    for ctype, nk in rows:
        dna = dna_map.get(nk)
        if not dna: continue
        if filter_type and dna.get("type") != filter_type: continue
        
        if ctype == 'additional':
            baseline_dna.append(dna)
        elif ctype == 'cited':
            target_dna.append(dna)
            
    b_counts, b_total = feature_counts(baseline_dna)
    t_counts, t_total = feature_counts(target_dna)
    
    results = []
    all_keys = sorted(set(b_counts.keys()) | set(t_counts.keys()))
    for k in all_keys:
        b_pct = (b_counts.get(k, 0) / b_total * 100) if b_total > 0 else 0
        t_pct = (t_counts.get(k, 0) / t_total * 100) if t_total > 0 else 0
        results.append({
            "feature": k,
            "baseline_n": b_total,
            "target_n": t_total,
            "drift_pp": round(t_pct - b_pct, 4)
        })
    return results

def main():
    db_path = "geo_fresh.db"
    gpt_dna = load_jsonl_dna(["datapass/page_labels_control_gpt5_mini.jsonl"])
    conn = sqlite3.connect(db_path)
    
    out = {"tables": {"listicle": {}, "product_page": {}}}
    
    studies = [
        ("GPT Personal", "personal"),
        ("GPT Enterprise", "enterprise")
    ]
    
    for label, acc_type in studies:
        for ctype in ["listicle", "product_page"]:
            drift = calculate_attachment_drift(conn, gpt_dna, acc_type, filter_type=ctype)
            # Format for dashboard consumption
            table = []
            # Only keep the features we usually show
            target_features = [
                "bool:has_tables", "bool:is_current_year_2026", "bool:has_numbered_lists", 
                "bool:has_bullet_points", "bool:has_pros_cons", "bool:has_clear_authorship",
                "score>=4:expertise_signal_score", "score>=4:freshness_cue_strength", 
                "score>=4:readability_score", "score>=4:heading_density"
            ]
            for row in drift:
                if row["feature"] in target_features:
                    feat_name = row["feature"].split(":")[-1]
                    table.append({
                        "feature": feat_name,
                        "drift_pp": row["drift_pp"]
                    })
            out["tables"][ctype][label] = table

    with open("data/enrichment/attachment_drift.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print("Wrote data/enrichment/attachment_drift.json")
    conn.close()

if __name__ == "__main__":
    main()
