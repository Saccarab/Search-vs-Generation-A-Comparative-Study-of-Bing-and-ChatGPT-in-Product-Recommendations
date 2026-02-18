import glob
import json
import os
import sqlite3
import sys
from collections import defaultdict


DB_PATH = "geo_fresh.db"
MAPPING_GLOB = "datapass/citation_mappings/*_enterprise_mapping.json"
SERP_DIR = "data/serpapi_google_results"


def norm_q(q: str) -> str:
    return " ".join((q or "").strip().lower().split())


def in_range(run_id: str, lo: int = 55, hi: int = 65) -> bool:
    # run_id like P055_r1
    try:
        p = int(run_id[1:4])
        return lo <= p <= hi
    except Exception:
        return False


def load_expected_hidden_queries() -> set[tuple[str, str]]:
    expected: set[tuple[str, str]] = set()
    for fp in glob.glob(MAPPING_GLOB):
        if fp.endswith("_summary.json") or fp.endswith("_all_mappings.json"):
            continue
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        run_id = data.get("run_id") or ""
        if not in_range(run_id):
            continue
        hidden = (data.get("metadata") or {}).get("hidden_queries") or []
        for q in hidden:
            if q is None:
                continue
            qs = str(q).strip()
            if not qs or qs.lower() == "n/a":
                continue
            expected.add((run_id, qs))
    return expected


def index_serp_files_enterprise() -> set[tuple[str, str]]:
    """Return set of (chatgpt_run_id, query) seen in SerpAPI JSON files for enterprise hidden_query."""
    present: set[tuple[str, str]] = set()
    if not os.path.isdir(SERP_DIR):
        return present
    for fn in os.listdir(SERP_DIR):
        if not fn.endswith(".json"):
            continue
        fp = os.path.join(SERP_DIR, fn)
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        qi = data.get("_query_info") or {}
        if (qi.get("account_type") or "") != "enterprise":
            continue
        if (qi.get("query_type") or "") != "hidden_query":
            continue
        chatgpt_run_id = qi.get("chatgpt_run_id") or ""
        if not in_range(chatgpt_run_id):
            continue
        q = qi.get("query") or ""
        present.add((chatgpt_run_id, q))
    return present


def index_db_enterprise_hidden_queries(cur: sqlite3.Cursor) -> set[tuple[str, str]]:
    cur.execute(
        """
        SELECT chatgpt_run_id, query
        FROM google_results
        WHERE account_type='enterprise'
          AND query_type='hidden_query'
        GROUP BY chatgpt_run_id, query
        """
    )
    rows = cur.fetchall()
    present = set()
    for rid, q in rows:
        if in_range(rid):
            present.add((rid, q))
    return present


def main() -> None:
    # Windows console can choke on some Unicode from queries (e.g., Persian/Japanese).
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass

    expected = load_expected_hidden_queries()
    serp_present = index_serp_files_enterprise()

    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        db_present = index_db_enterprise_hidden_queries(cur)
    finally:
        con.close()

    # Exact match missing
    missing_in_serp = sorted(expected - serp_present)
    missing_in_db = sorted(expected - db_present)

    # Normalized match missing (helps diagnose query text drift)
    exp_norm = defaultdict(set)
    for rid, q in expected:
        exp_norm[(rid, norm_q(q))].add(q)
    serp_norm = set((rid, norm_q(q)) for rid, q in serp_present)
    db_norm = set((rid, norm_q(q)) for rid, q in db_present)

    missing_in_serp_norm = sorted(k for k in exp_norm.keys() if k not in serp_norm)
    missing_in_db_norm = sorted(k for k in exp_norm.keys() if k not in db_norm)

    print("=== ENTERPRISE P055–P065 GOOGLE COVERAGE REPORT ===")
    print(f"expected_hidden_queries: {len(expected)}")
    print(f"serp_files_present_exact: {len(serp_present)}")
    print(f"db_present_exact: {len(db_present)}")
    print("")
    print(f"missing_in_serp_exact: {len(missing_in_serp)}")
    print(f"missing_in_db_exact:   {len(missing_in_db)}")
    print(f"missing_in_serp_norm:  {len(missing_in_serp_norm)}")
    print(f"missing_in_db_norm:    {len(missing_in_db_norm)}")
    print("")

    if missing_in_serp_norm:
        print("Missing in SerpAPI files (normalized) – sample 20:")
        for (rid, nq) in missing_in_serp_norm[:20]:
            origs = sorted(exp_norm[(rid, nq)])
            print(f"  - {rid} :: {origs[0][:120]}")
    else:
        print("✅ No missing queries in SerpAPI files for P055–P065 (normalized).")

    print("")
    if missing_in_db_norm:
        print("Missing in DB after ingest (normalized) – sample 20:")
        for (rid, nq) in missing_in_db_norm[:20]:
            origs = sorted(exp_norm[(rid, nq)])
            print(f"  - {rid} :: {origs[0][:120]}")
    else:
        print("✅ No missing queries in DB for P055–P065 (normalized).")


if __name__ == "__main__":
    main()

