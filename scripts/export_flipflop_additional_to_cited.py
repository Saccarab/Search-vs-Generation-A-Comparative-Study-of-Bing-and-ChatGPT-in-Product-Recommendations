import json
import os
import glob
from collections import defaultdict


def main() -> None:
    mappings_dir = os.environ.get("CITATION_MAPPINGS_DIR", "datapass/citation_mappings")
    out_dir = os.environ.get("FLIPFLOP_OUT_DIR", "datapass")

    files = [
        f
        for f in glob.glob(os.path.join(mappings_dir, "*_mapping.json"))
        if not os.path.basename(f).startswith("_")
    ]

    # Per account: url -> sets of run_ids
    stats = {
        "enterprise": {"cited": defaultdict(set), "additional": defaultdict(set)},
        "personal": {"cited": defaultdict(set), "additional": defaultdict(set)},
    }

    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        acct = (data.get("account_type") or "").strip()
        if acct not in stats:
            # Fallback: infer from filename
            base = os.path.basename(fp)
            acct = "enterprise" if "enterprise" in base else "personal"
        if acct not in stats:
            continue

        run_id = data.get("run_id") or os.path.basename(fp).replace("_mapping.json", "")
        source_summary = data.get("source_summary") or {}

        for s in (source_summary.get("cited") or []):
            url = (s.get("url") or "").strip()
            if url:
                stats[acct]["cited"][url].add(run_id)

        for s in (source_summary.get("additional") or []):
            url = (s.get("url") or "").strip()
            if url:
                stats[acct]["additional"][url].add(run_id)

    os.makedirs(out_dir, exist_ok=True)

    for acct in ["enterprise", "personal"]:
        cited = stats[acct]["cited"]
        additional = stats[acct]["additional"]
        overlap_urls = sorted(set(additional.keys()) & set(cited.keys()))

        # Write a readable txt file
        txt_path = os.path.join(out_dir, f"flipflop_additional_to_cited_{acct}.txt")
        with open(txt_path, "w", encoding="utf-8") as out:
            out.write(f"# Flip-Flop: Additional -> Cited ({acct})\n")
            out.write(
                "# Definition: URL appears in source_summary.additional in >=1 run AND appears in source_summary.cited in >=1 run (same account).\n"
            )
            out.write(f"# Source: {mappings_dir}\n")
            out.write(f"# Files parsed: {len(files)}\n")
            out.write(f"# Unique URLs in Additional: {len(additional)}\n")
            out.write(f"# Unique URLs in Cited: {len(cited)}\n")
            out.write(f"# Overlap (Additional ∩ Cited): {len(overlap_urls)}\n")
            out.write("\n")

            for url in overlap_urls:
                c_runs = sorted(cited[url])
                a_runs = sorted(additional[url])
                out.write(url + "\n")
                out.write(f"  CITED_IN({len(c_runs)}): " + ", ".join(c_runs) + "\n")
                out.write(f"  ADDITIONAL_IN({len(a_runs)}): " + ", ".join(a_runs) + "\n")
                out.write("\n")

        # Also write a CSV for easy filtering
        csv_path = os.path.join(out_dir, f"flipflop_additional_to_cited_{acct}.csv")
        with open(csv_path, "w", encoding="utf-8") as out:
            out.write("url,cited_in_count,additional_in_count,cited_in_runs,additional_in_runs\n")

            def esc(s: str) -> str:
                return '"' + s.replace('"', '""') + '"'

            for url in overlap_urls:
                c_runs = sorted(cited[url])
                a_runs = sorted(additional[url])
                out.write(
                    ",".join(
                        [
                            esc(url),
                            str(len(c_runs)),
                            str(len(a_runs)),
                            esc(" | ".join(c_runs)),
                            esc(" | ".join(a_runs)),
                        ]
                    )
                    + "\n"
                )

        print(f"[{acct}] overlap_urls={len(overlap_urls)}")
        print(f"  wrote: {txt_path}")
        print(f"  wrote: {csv_path}")


if __name__ == "__main__":
    main()

