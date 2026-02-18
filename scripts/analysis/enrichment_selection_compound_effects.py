"""
Analyze compound selection effects using enrichment features (tables/authorship/tone/etc).

Goal
----
Quantify how URL *selection* (cited vs. candidate pool) changes as a function of:
- page type (listicle/product_page/...)
- structure signals (has_tables, has_numbered_lists, has_pros_cons)
- credibility signals (has_clear_authorship, has_sources_or_citations, expertise_signal_score)
- tone/promotional intensity
and how these interact with *ranking/page depth* (Bing page_num) and account type.

Inputs
------
- geo_fresh.db (runs, bing_results)
- datapass/page_labels_combined_v2.5.jsonl (enrichment labels)

Outputs
-------
Writes CSVs to an output directory:
- selection_lift_univariate.csv
- selection_lift_bivariate.csv
- cited_page_distribution_by_feature.csv
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import re
import hashlib
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pandas as pd


DROP_EXACT = {
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
    Mirror the normalization used elsewhere in the repo for joins/dedup:
    - Ensure scheme for parsing
    - Lowercase host, strip leading www.
    - Drop fragment
    - Trim trailing slash (except root)
    - Drop tracking params (utm_*, gclid, fbclid, ...)
    - Sort remaining query params by key for stability
    """
    if not isinstance(raw_url, str):
        return ""
    s = raw_url.strip()
    if not s:
        return ""
    if "://" not in s:
        s = "https://" + s

    try:
        parts = urlsplit(s)
    except Exception:
        return ""

    host = (parts.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]

    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]

    kept: List[Tuple[str, str]] = []
    for k, v in parse_qsl(parts.query, keep_blank_values=True):
        lk = k.lower()
        if lk.startswith("utm_"):
            continue
        if lk in DROP_EXACT:
            continue
        kept.append((k, v))
    kept.sort(key=lambda kv: kv[0].lower())
    query = urlencode(kept, doseq=True)

    rebuilt = urlunsplit(("", host, path, query, ""))  # scheme + fragment dropped
    return rebuilt.lstrip("/")


def parse_json_maybe(v: Any, default: Any) -> Any:
    if v is None:
        return default
    if isinstance(v, (dict, list)):
        return v
    s = str(v).strip()
    if not s:
        return default
    try:
        return json.loads(s)
    except Exception:
        return default


def safe_int(v: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        if v is None or v == "":
            return default
        return int(v)
    except Exception:
        return default


def load_labels(labels_jsonl: str) -> Dict[str, Dict[str, Any]]:
    """
    Returns: url_key -> flattened label dict
    """
    out: Dict[str, Dict[str, Any]] = {}
    with open(labels_jsonl, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue

            url = obj.get("url") or ""
            url_key = normalize_url_key(url)
            if not url_key:
                continue

            resp = obj.get("response") or {}
            urls = (resp.get("urls") if isinstance(resp, dict) else None) or {}
            if not isinstance(urls, dict):
                continue
            listicles = (resp.get("listicles") if isinstance(resp, dict) else None) or {}
            if not isinstance(listicles, dict):
                listicles = {}

            # keep only the stable, analysis-relevant fields
            keep = {
                "type": urls.get("type") or "",
                "content_format": urls.get("content_format") or "",
                "tone": urls.get("tone") or "",
                # "mixed" ended up being over-used; treat as unknown to avoid washing out analyses
                "primary_intent": (urls.get("primary_intent") or "").strip(),
                "promotional_intensity_score": safe_int(urls.get("promotional_intensity_score")),
                "freshness_cue_strength": safe_int(urls.get("freshness_cue_strength")),
                "readability_score": safe_int(urls.get("readability_score")),
                "heading_density": safe_int(urls.get("heading_density")),
                "has_tables": safe_int(urls.get("has_tables"), 0),
                "has_numbered_lists": safe_int(urls.get("has_numbered_lists"), 0),
                "has_bullet_points": safe_int(urls.get("has_bullet_points"), 0),
                "has_pros_cons": safe_int(urls.get("has_pros_cons"), 0),
                "has_clear_authorship": safe_int(urls.get("has_clear_authorship"), 0),
                "has_sources_or_citations": safe_int(urls.get("has_sources_or_citations"), 0),
                "expertise_signal_score": safe_int(urls.get("expertise_signal_score")),
                "spamminess_score": safe_int(urls.get("spamminess_score")),
                # for derived freshness proxies (mostly useful for listicles)
                "listicle_title": (listicles.get("title") or "").strip(),
            }
            keep["url"] = url
            keep["url_key"] = url_key
            if keep["primary_intent"].lower() == "mixed":
                keep["primary_intent"] = ""
            out[url_key] = keep
    return out

MONTH_RE = re.compile(
    r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|"
    r"sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b",
    re.IGNORECASE,
)
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
UPDATED_RE = re.compile(r"\b(last\s+updated|updated\s+on|updated:|updated\b|as\s+of)\b", re.IGNORECASE)
ISO_DATE_RE = re.compile(r"\b(20\d{2})[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])\b")


def short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def build_fetched_text_index(fetched_dir: str) -> Dict[str, str]:
    """
    Map content hash (filename stem) -> .txt filepath.
    """
    if not fetched_dir or not os.path.isdir(fetched_dir):
        return {}
    out: Dict[str, str] = {}
    for fn in os.listdir(fetched_dir):
        if not fn.endswith(".txt"):
            continue
        stem = fn[:-4]
        out[stem] = os.path.join(fetched_dir, fn)
    return out


def read_fetched_text(fetched_index: Dict[str, str], url_key: str, max_chars: int = 20000) -> str:
    """
    Attempt to load fetched page text for url_key. Returns "" if missing.
    """
    if not fetched_index:
        return ""
    h = short_hash(url_key)
    p = fetched_index.get(h)
    if not p or not os.path.exists(p):
        return ""
    try:
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(max_chars)
    except Exception:
        return ""


def derive_freshness_proxies(url_key: str, listicle_title: str, fetched_text: str) -> Dict[str, Any]:
    """
    Split "freshness" into more interpretable proxies:
    - freshness_has_year: any year token present
    - freshness_has_recent_year: year >= 2024 present (tunable; matches dataset era)
    - freshness_has_updated_cue: 'updated'/'last updated'/'as of' etc present
    - freshness_has_explicit_date: month-name+year or ISO date present
    - freshness_mode: one of {'updated_date','year_only','none'}
    """
    title = (listicle_title or "")
    url_s = (url_key or "")
    txt = (fetched_text or "")
    blob = " ".join([title, url_s, txt])

    years = [int(m.group(0)) for m in YEAR_RE.finditer(blob)]
    has_year = 1 if years else 0
    has_recent_year = 1 if any(y >= 2024 for y in years) else 0
    has_updated = 1 if UPDATED_RE.search(blob) else 0
    has_explicit_date = 1 if (ISO_DATE_RE.search(blob) or (MONTH_RE.search(blob) and years)) else 0

    if has_updated or has_explicit_date:
        mode = "updated_date"
    elif has_year:
        mode = "year_only"
    else:
        mode = "none"

    return {
        "freshness_has_year": has_year,
        "freshness_has_recent_year": has_recent_year,
        "freshness_has_updated_cue": has_updated,
        "freshness_has_explicit_date": has_explicit_date,
        "freshness_mode": mode,
    }


def build_candidate_rows_from_db(
    db_path: str,
    limit_runs: Optional[int] = None,
) -> pd.DataFrame:
    """
    Build a per-(run,url) dataset with a selection label:
    - cited
    - additional
    - rejected   (seen in search results but not attached)

    Also attaches Bing page depth if present (page_num).
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Preload per-run Bing page mapping: (run_id, url_normalized) -> min(page_num)
    page_map: Dict[Tuple[str, str], int] = {}
    for row in cur.execute(
        """
        SELECT run_id, url_normalized, MIN(page_num) AS page_num
        FROM bing_results
        WHERE url_normalized IS NOT NULL AND url_normalized != ''
        GROUP BY run_id, url_normalized
        """
    ):
        rid = row["run_id"]
        uk = row["url_normalized"]
        pn = row["page_num"]
        if rid and uk and pn is not None:
            page_map[(rid, uk)] = int(pn)

    q = """
    SELECT run_id, prompt_id, run_number, account_type,
           sources_cited_json, sources_additional_json, search_result_groups_json
    FROM runs
    """
    if limit_runs is not None:
        q += f" LIMIT {int(limit_runs)}"

    rows: List[Dict[str, Any]] = []
    for r in cur.execute(q):
        run_id = r["run_id"]
        prompt_id = r["prompt_id"]
        run_number = r["run_number"]
        account_type = r["account_type"] or ""

        cited = parse_json_maybe(r["sources_cited_json"], [])
        additional = parse_json_maybe(r["sources_additional_json"], [])
        srg = parse_json_maybe(r["search_result_groups_json"], [])

        used: set[str] = set()

        def add_one(url: str, group: str) -> None:
            uk = normalize_url_key(url)
            if not uk:
                return
            used.add(uk)
            rows.append(
                {
                    "run_id": run_id,
                    "prompt_id": prompt_id,
                    "run_number": run_number,
                    "account_type": account_type,
                    "group": group,
                    "url": url,
                    "url_key": uk,
                    "page_num": page_map.get((run_id, uk)),
                }
            )

        # cited/additional
        for s in cited if isinstance(cited, list) else []:
            u = (s or {}).get("url")
            if u:
                add_one(u, "cited")
        for s in additional if isinstance(additional, list) else []:
            u = (s or {}).get("url")
            if u:
                add_one(u, "additional")

        # rejected = in search results but not in cited/additional
        if isinstance(srg, list):
            for group in srg:
                if not isinstance(group, dict):
                    continue
                entries = group.get("entries")
                if entries is None and group.get("url"):
                    entries = [group]
                if not isinstance(entries, list):
                    continue
                for e in entries:
                    if not isinstance(e, dict):
                        continue
                    u = e.get("url")
                    if not u:
                        continue
                    uk = normalize_url_key(u)
                    if not uk or uk in used:
                        continue
                    # record rejected, and mark used to prevent duplicates within the run
                    used.add(uk)
                    rows.append(
                        {
                            "run_id": run_id,
                            "prompt_id": prompt_id,
                            "run_number": run_number,
                            "account_type": account_type,
                            "group": "rejected",
                            "url": u,
                            "url_key": uk,
                            "page_num": page_map.get((run_id, uk)),
                        }
                    )

    conn.close()
    return pd.DataFrame(rows)


def compute_selection_lift_univariate(df: pd.DataFrame, feature: str) -> pd.DataFrame:
    # candidate pool = all rows where feature is present
    base = df[df[feature].notna()].copy()
    if base.empty:
        return pd.DataFrame()

    def summarize(g: pd.DataFrame) -> pd.DataFrame:
        total = len(g)
        cited = (g["group"] == "cited").sum()
        # per feature value
        out = []
        for val, gv in g.groupby(feature, dropna=False):
            n_all = len(gv)
            n_cited = (gv["group"] == "cited").sum()
            p_all = n_all / total if total else 0.0
            p_cited = n_cited / cited if cited else 0.0
            out.append(
                {
                    "account_type": g["account_type"].iloc[0],
                    "feature": feature,
                    "value": val,
                    "n_all": n_all,
                    "n_cited": n_cited,
                    "p_all": p_all,
                    "p_cited": p_cited,
                    "lift_pp": (p_cited - p_all) * 100.0,
                }
            )
        return pd.DataFrame(out)

    frames = []
    for acct, g in base.groupby("account_type", dropna=False):
        if not acct:
            continue
        frames.append(summarize(g))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def compute_selection_lift_bivariate(
    df: pd.DataFrame,
    a: str,
    b: str,
    min_support: int = 25,
) -> pd.DataFrame:
    base = df[df[a].notna() & df[b].notna()].copy()
    if base.empty:
        return pd.DataFrame()

    out_rows: List[Dict[str, Any]] = []
    for acct, g in base.groupby("account_type", dropna=False):
        if not acct:
            continue
        total = len(g)
        cited_total = (g["group"] == "cited").sum()
        for (va, vb), gv in g.groupby([a, b], dropna=False):
            n_all = len(gv)
            if n_all < min_support:
                continue
            n_cited = (gv["group"] == "cited").sum()
            p_all = n_all / total if total else 0.0
            p_cited = n_cited / cited_total if cited_total else 0.0
            out_rows.append(
                {
                    "account_type": acct,
                    "feature_a": a,
                    "value_a": va,
                    "feature_b": b,
                    "value_b": vb,
                    "n_all": n_all,
                    "n_cited": n_cited,
                    "p_all": p_all,
                    "p_cited": p_cited,
                    "lift_pp": (p_cited - p_all) * 100.0,
                }
            )
    return pd.DataFrame(out_rows)


def compute_cited_page_distribution(df: pd.DataFrame, feature: str) -> pd.DataFrame:
    cited = df[df["group"] == "cited"].copy()
    cited = cited[cited[feature].notna()]
    if cited.empty:
        return pd.DataFrame()

    # page_num may be null; keep it as "None" bucket for invisibles
    cited["page_bucket"] = cited["page_num"].fillna(-1).astype(int)

    out_rows: List[Dict[str, Any]] = []
    for (acct, val, pb), g in cited.groupby(["account_type", feature, "page_bucket"], dropna=False):
        out_rows.append(
            {
                "account_type": acct,
                "feature": feature,
                "value": val,
                "page_num": None if pb == -1 else int(pb),
                "n_cited": len(g),
            }
        )
    return pd.DataFrame(out_rows)

def compute_selection_lift_univariate_subset(
    df: pd.DataFrame,
    feature: str,
    subset_filter: pd.Series,
    label: str,
) -> pd.DataFrame:
    """
    Same as compute_selection_lift_univariate, but restricted to a subset (e.g., listicles-only).
    Adds a column `subset` for downstream interpretation.
    """
    sub = df[subset_filter].copy()
    out = compute_selection_lift_univariate(sub, feature)
    if out.empty:
        return out
    out.insert(1, "subset", label)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="geo_fresh.db", help="Path to geo_fresh.db")
    ap.add_argument(
        "--labels",
        default="datapass/page_labels_combined_v2.5.jsonl",
        help="Path to combined labels JSONL",
    )
    ap.add_argument("--outdir", default="data/enrichment_compound_effects", help="Output directory")
    ap.add_argument(
        "--fetched-dir",
        default="data/fetched_content",
        help="Directory containing fetched page text (.txt) used for derived freshness proxies",
    )
    ap.add_argument("--limit-runs", type=int, default=None, help="Optional LIMIT on number of runs")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    labels = load_labels(args.labels)
    cand = build_candidate_rows_from_db(args.db, limit_runs=args.limit_runs)
    if cand.empty:
        raise SystemExit("No candidate rows produced from DB. Check DB path / schema.")

    # Attach labels
    lab_df = pd.DataFrame(list(labels.values()))
    merged = cand.merge(lab_df, how="left", on="url_key", suffixes=("", "_label"))

    # Derived freshness proxies (more interpretable than freshness_cue_strength)
    fetched_index = build_fetched_text_index(args.fetched_dir)
    if fetched_index:
        proxy_rows = []
        for _, r in merged.iterrows():
            uk = r.get("url_key")
            if not isinstance(uk, str) or not uk:
                proxy_rows.append({})
                continue
            title = r.get("listicle_title") or ""
            txt = read_fetched_text(fetched_index, uk)
            proxy_rows.append(derive_freshness_proxies(uk, str(title), txt))
        proxy_df = pd.DataFrame(proxy_rows)
        merged = pd.concat([merged.reset_index(drop=True), proxy_df.reset_index(drop=True)], axis=1)
    else:
        # still derive from url+title (no fetched text)
        proxy_rows = []
        for _, r in merged.iterrows():
            uk = r.get("url_key")
            title = r.get("listicle_title") or ""
            proxy_rows.append(derive_freshness_proxies(str(uk or ""), str(title), ""))  # safe
        proxy_df = pd.DataFrame(proxy_rows)
        merged = pd.concat([merged.reset_index(drop=True), proxy_df.reset_index(drop=True)], axis=1)

    # Keep only rows we can label (otherwise lift tables get misleading)
    merged_labeled = merged[merged["type"].notna() & (merged["type"] != "")].copy()

    # Univariate lifts
    uni_features = [
        "type",
        "tone",
        "content_format",
        "primary_intent",
        "has_tables",
        "has_numbered_lists",
        "has_bullet_points",
        "has_clear_authorship",
        "has_sources_or_citations",
        "has_pros_cons",
        "freshness_cue_strength",
        "freshness_mode",
        "freshness_has_year",
        "freshness_has_recent_year",
        "freshness_has_updated_cue",
        "freshness_has_explicit_date",
        "heading_density",
        "readability_score",
        "promotional_intensity_score",
        "expertise_signal_score",
        "spamminess_score",
    ]
    uni_frames = [compute_selection_lift_univariate(merged_labeled, f) for f in uni_features]
    uni = pd.concat([x for x in uni_frames if not x.empty], ignore_index=True) if uni_frames else pd.DataFrame()
    if not uni.empty:
        uni.sort_values(["account_type", "feature", "lift_pp"], ascending=[True, True, False], inplace=True)
        uni.to_csv(os.path.join(args.outdir, "selection_lift_univariate.csv"), index=False)

    # Univariate lifts within listicles only (controls for type)
    listicle_filter = merged_labeled["type"] == "listicle"
    listicle_uni_frames = [
        compute_selection_lift_univariate_subset(merged_labeled, f, listicle_filter, "type=listicle")
        for f in [
            "tone",
            "has_tables",
            "has_numbered_lists",
            "has_bullet_points",
            "has_pros_cons",
            "has_clear_authorship",
            "has_sources_or_citations",
            "freshness_cue_strength",
            "freshness_mode",
            "freshness_has_recent_year",
            "freshness_has_updated_cue",
            "freshness_has_explicit_date",
            "readability_score",
            "expertise_signal_score",
            "promotional_intensity_score",
        ]
    ]
    listicle_uni = (
        pd.concat([x for x in listicle_uni_frames if not x.empty], ignore_index=True)
        if listicle_uni_frames
        else pd.DataFrame()
    )
    if not listicle_uni.empty:
        listicle_uni.sort_values(["account_type", "feature", "lift_pp"], ascending=[True, True, False], inplace=True)
        listicle_uni.to_csv(os.path.join(args.outdir, "selection_lift_univariate_listicle_only.csv"), index=False)

    # Bivariate lifts (compound effects)
    biv_pairs = [
        ("type", "has_tables"),
        ("type", "has_clear_authorship"),
        ("tone", "has_tables"),
        ("tone", "has_clear_authorship"),
        ("type", "tone"),
        ("type", "has_pros_cons"),
        ("type", "freshness_cue_strength"),
    ]
    biv_frames = [compute_selection_lift_bivariate(merged_labeled, a, b, min_support=25) for a, b in biv_pairs]
    biv = pd.concat([x for x in biv_frames if not x.empty], ignore_index=True) if biv_frames else pd.DataFrame()
    if not biv.empty:
        biv.sort_values(["account_type", "lift_pp"], ascending=[True, False], inplace=True)
        biv.to_csv(os.path.join(args.outdir, "selection_lift_bivariate.csv"), index=False)

    # Page depth for citations (ranking/page interaction proxy)
    page_features = ["type", "tone", "has_tables", "has_clear_authorship", "has_sources_or_citations"]
    page_frames = [compute_cited_page_distribution(merged_labeled, f) for f in page_features]
    page = pd.concat([x for x in page_frames if not x.empty], ignore_index=True) if page_frames else pd.DataFrame()
    if not page.empty:
        page.sort_values(["account_type", "feature", "value", "page_num"], inplace=True)
        page.to_csv(os.path.join(args.outdir, "cited_page_distribution_by_feature.csv"), index=False)

    # Avoid unicode issues on some Windows terminals (cp1252)
    print(f"Wrote outputs to: {args.outdir}")


if __name__ == "__main__":
    main()

