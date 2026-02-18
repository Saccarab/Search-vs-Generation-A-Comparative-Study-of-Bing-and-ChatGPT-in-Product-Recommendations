import csv
import json
import os


def main():
    mapping_path = "data/resolved_grounding_urls.json"
    out_csv = "data/enrichment/browser_resolve_vertex_queue.csv"

    if not os.path.exists(mapping_path):
        raise SystemExit(f"Missing: {mapping_path}")

    with open(mapping_path, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    unresolved = [k for k, v in mapping.items() if k == v]
    unresolved = [u for u in unresolved if isinstance(u, str) and u.strip()]

    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["url"])
        for u in unresolved:
            w.writerow([u])

    print(f"Unresolved vertex redirects: {len(unresolved)}")
    print(f"Wrote queue: {out_csv}")


if __name__ == "__main__":
    main()

