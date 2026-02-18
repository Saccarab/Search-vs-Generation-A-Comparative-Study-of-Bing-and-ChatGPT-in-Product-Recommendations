import argparse
import csv
import json
import os


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Path to chatgpt_results_*.csv")
    ap.add_argument("--prompt_id", required=True, help="Prompt id like P053 or 53")
    ap.add_argument("--run_number", required=True, type=int, help="Run number like 2 (r2)")
    ap.add_argument("--out", default="", help="Output file path (json)")
    args = ap.parse_args()

    prompt_id = str(args.prompt_id).strip()
    if prompt_id.isdigit():
        prompt_id = f"P{int(prompt_id):03d}"

    out_path = args.out or f"datapass/raw_network_responses/{prompt_id}_r{args.run_number}_enterprise.json"
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    with open(args.csv, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required_cols = {
            "prompt_id",
            "run_number",
            "raw_api_response_json",
        }
        missing_cols = [c for c in required_cols if c not in (reader.fieldnames or [])]
        if missing_cols:
            raise SystemExit(f"CSV missing required columns: {missing_cols}. Found: {reader.fieldnames}")

        match = None
        for row in reader:
            if (row.get("prompt_id") or "").strip() != prompt_id:
                continue
            try:
                rn = int((row.get("run_number") or "").strip())
            except Exception:
                continue
            if rn != args.run_number:
                continue
            match = row
            break

    if not match:
        raise SystemExit(f"No row found for prompt_id={prompt_id} run_number={args.run_number} in {args.csv}")

    raw = (match.get("raw_api_response_json") or "").strip()
    if not raw:
        raise SystemExit("Found row, but raw_api_response_json is empty.")

    try:
        payload = json.loads(raw)
    except Exception:
        # If it's not valid JSON (should be), dump as string for manual debugging
        payload = {"_raw_api_response_json": raw}

    with open(out_path, "w", encoding="utf-8") as out:
        json.dump(payload, out, ensure_ascii=False, indent=2)

    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()

