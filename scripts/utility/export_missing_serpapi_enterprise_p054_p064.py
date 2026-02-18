import argparse
import csv
import glob
import json
import os
import sys


MAPPING_GLOB = "datapass/citation_mappings/*_enterprise_mapping.json"
SERP_DIR = "data/serpapi_google_results"


def norm_q(q: str) -> str:
    return " ".join((q or "").strip().lower().split())


def in_range(run_id: str, lo: int, hi: int) -> bool:
    try:
        p = int(run_id[1:4])
        return lo <= p <= hi
    except Exception:
        return False


def load_expected_hidden_queries(lo: int, hi: int) -> list[tuple[str, str, str]]:
    """
    Returns list of (chatgpt_run_id, q_label, query) for enterprise hidden queries in the prompt range.
    q_label is Q1/Q2/... based on hidden_queries index.
    """
    expected: list[tuple[str, str, str]] = []
    for fp in glob.glob(MAPPING_GLOB):
        if fp.endswith("_summary.json") or fp.endswith("_all_mappings.json"):
            continue
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        run_id = data.get("run_id") or ""
        if not in_range(run_id, lo, hi):
            continue

        hidden = (data.get("metadata") or {}).get("hidden_queries") or []
        for i, q in enumerate(hidden):
            if q is None:
                continue
            qs = str(q).strip()
            if not qs or qs.lower() == "n/a":
                continue
            expected.append((run_id, f"Q{i+1}", qs))
    return expected


def index_serp_present_enterprise(lo: int, hi: int) -> set[tuple[str, str]]:
    """Set of (chatgpt_run_id, normalized_query) present in SerpAPI files for enterprise hidden_query."""
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
        rid = qi.get("chatgpt_run_id") or ""
        if not in_range(rid, lo, hi):
            continue
        q = qi.get("query") or ""
        present.add((rid, norm_q(q)))

    return present


def main() -> None:
    # Windows console can choke on some Unicode from queries
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--lo", type=int, default=54)
    ap.add_argument("--hi", type=int, default=64)
    ap.add_argument(
        "--out",
        default="data/serpapi_google_missing_enterprise_p054_p064.csv",
        help="Output CSV path",
    )
    args = ap.parse_args()

    expected = load_expected_hidden_queries(args.lo, args.hi)
    present = index_serp_present_enterprise(args.lo, args.hi)

    missing = [(rid, qlab, q) for (rid, qlab, q) in expected if (rid, norm_q(q)) not in present]

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["chatgpt_run_id", "account", "type", "query"])
        for rid, qlab, q in missing:
            w.writerow([rid, "enterprise", qlab, q])

    print("=== EXPORT MISSING SERPAPI QUEUE (ENTERPRISE) ===")
    print(f"prompt_range: P{args.lo:03d}..P{args.hi:03d}")
    print(f"expected_hidden_queries: {len(expected)}")
    print(f"present_in_serpapi_files: {len(present)} (unique run_id+query normalized)")
    print(f"missing_hidden_queries:   {len(missing)}")
    print(f"wrote_csv: {args.out}")


if __name__ == "__main__":
    main()

