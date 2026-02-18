import glob
import json
import sqlite3
import sys


DB_PATH = "geo_fresh.db"
MAPPING_DIR = "datapass/citation_mappings"


def load_expected_hidden_queries(account_type: str) -> set[tuple[str, str]]:
    expected: set[tuple[str, str]] = set()
    pattern = f"{MAPPING_DIR}/*_{account_type}_mapping.json"
    for fp in glob.glob(pattern):
        if fp.endswith("_summary.json") or fp.endswith("_all_mappings.json"):
            continue
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        run_id = data.get("run_id") or ""
        hidden = (data.get("metadata") or {}).get("hidden_queries") or []
        for q in hidden:
            if q is None:
                continue
            qs = str(q).strip()
            if not qs or qs.lower() == "n/a":
                continue
            expected.add((run_id, qs))
    return expected


def load_ingested_hidden_queries(db: sqlite3.Connection, account_type: str) -> set[tuple[str, str]]:
    cur = db.cursor()
    cur.execute(
        """
        SELECT chatgpt_run_id, query
        FROM google_results
        WHERE account_type = ?
          AND query_type = 'hidden_query'
        GROUP BY chatgpt_run_id, query
        """,
        (account_type,),
    )
    return set(cur.fetchall())


def main() -> None:
    # Windows console can choke on some Unicode from fan-out queries (e.g., Japanese/Turkish).
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass

    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        cur.execute("SELECT account_type, COUNT(1) FROM google_results GROUP BY account_type")
        rows = cur.fetchall()
        print("google_results_rows_by_account:", rows)
        cur.execute("SELECT account_type, COUNT(DISTINCT chatgpt_run_id) FROM google_results GROUP BY account_type")
        rows = cur.fetchall()
        print("google_results_distinct_chatgpt_run_id_by_account:", rows)

        for acct in ("enterprise", "personal"):
            expected = load_expected_hidden_queries(acct)
            ingested = load_ingested_hidden_queries(con, acct)
            missing = expected - ingested

            print(f"\n=== {acct.upper()} GOOGLE SERPAPI COVERAGE (HIDDEN QUERIES) ===")
            print(f"expected_hidden_queries: {len(expected)}")
            print(f"ingested_hidden_queries: {len(ingested)}")
            print(f"missing_hidden_queries:  {len(missing)}")
            pct = (len(ingested) / len(expected) * 100.0) if expected else 0.0
            print(f"coverage_pct:            {pct:.1f}%")

            if missing:
                print("missing_sample (first 15):")
                for run_id, q in list(missing)[:15]:
                    q_short = q if len(q) <= 100 else (q[:97] + "...")
                    print(f"  - {run_id} :: {q_short}")
    finally:
        con.close()


if __name__ == "__main__":
    main()

