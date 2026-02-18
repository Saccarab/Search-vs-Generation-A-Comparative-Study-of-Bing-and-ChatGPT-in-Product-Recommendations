#!/usr/bin/env python3
"""
Render filled prompt texts for a small sample of listicle jobs (for inspection).

Inputs:
  - selection_omission_jobs.jsonl
  - fidelity_jobs.jsonl
  - prompt templates:
      prompts/listicle_selection_omission_analysis_v1.txt
      prompts/listicle_fidelity_verification_chunks_v1.txt

Outputs:
  - out_dir/selection_prompts/*.txt
  - out_dir/fidelity_prompts/*.txt
  - out_dir/index.json (metadata + file paths)

This does NOT call any LLM.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import hashlib
from typing import Any, Dict, List


def read_text(p: str) -> str:
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


def iter_jsonl(p: str):
    with open(p, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def safe_filename(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "_", s)
    return s[:180] if len(s) > 180 else s


def short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def fill_placeholders(template: str, mapping: Dict[str, str]) -> str:
    """
    Template files include lots of JSON braces, so we must NOT use str.format().
    We only replace the known placeholders verbatim.
    """
    out = template
    for k, v in mapping.items():
        out = out.replace("{" + k + "}", v)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs_dir", default="data/listicle_analysis/jobs_chatgpt_sample_15")
    ap.add_argument("--out_dir", default="data/listicle_analysis/prompts_chatgpt_sample_15")
    ap.add_argument("--max_per_type", type=int, default=15)
    args = ap.parse_args()

    sel_jobs_path = os.path.join(args.jobs_dir, "selection_omission_jobs.jsonl")
    bias_jobs_path = os.path.join(args.jobs_dir, "bias_uptake_jobs.jsonl")
    fid_jobs_path = os.path.join(args.jobs_dir, "fidelity_jobs.jsonl")

    sel_tpl = read_text("prompts/listicle_selection_omission_analysis_v1.txt")
    bias_tpl = read_text("prompts/listicle_bias_uptake_analysis_v1.txt")
    fid_tpl = read_text("prompts/listicle_fidelity_verification_chunks_v1.txt")

    out_sel = os.path.join(args.out_dir, "selection_prompts")
    out_bias = os.path.join(args.out_dir, "bias_uptake_prompts")
    out_fid = os.path.join(args.out_dir, "fidelity_prompts")
    os.makedirs(out_sel, exist_ok=True)
    os.makedirs(out_bias, exist_ok=True)
    os.makedirs(out_fid, exist_ok=True)

    index: Dict[str, Any] = {"selection": [], "bias_uptake": [], "fidelity": []}

    # Selection/Omission prompts
    for i, job in enumerate(iter_jsonl(sel_jobs_path)):
        if i >= args.max_per_type:
            break
        run_id = job["run_id"]
        listicle_url = job["listicle_url"]
        answer_text = job.get("answer_text", "")
        roster = job.get("listicle_roster", [])
        prompt = fill_placeholders(
            sel_tpl,
            {
                "run_id": run_id,
                "listicle_url": listicle_url,
                "answer_text": answer_text,
            },
        )
        # Always include the actual roster instance (template contains an example roster with "...").
        prompt += "\n\nLISTICLE PRODUCT ROSTER (instance):\n" + json.dumps(roster, ensure_ascii=False, indent=2)

        # Keep filenames short to avoid Windows path length issues
        fn = safe_filename(f"{i+1:02d}_{run_id}_{short_hash(listicle_url)}.txt")
        fp = os.path.join(out_sel, fn)
        with open(fp, "w", encoding="utf-8") as fh:
            fh.write(prompt)
        index["selection"].append({"run_id": run_id, "listicle_url": listicle_url, "path": fp})

    # Bias/Uptake prompts
    if os.path.exists(bias_jobs_path):
        for i, job in enumerate(iter_jsonl(bias_jobs_path)):
            if i >= args.max_per_type:
                break
            run_id = job["run_id"]
            listicle_url = job["listicle_url"]
            answer_text = job.get("answer_text", "")
            roster = job.get("listicle_roster", [])
            meta = job.get("listicle_meta", {}) or {}
            full_content = job.get("full_page_content", "")
            claims = job.get("claims", [])
            prompt = fill_placeholders(
                bias_tpl,
                {
                    "run_id": run_id,
                    "listicle_url": listicle_url,
                    "claims_json": json.dumps(claims, ensure_ascii=False, indent=2),
                    "listicle_meta_json": json.dumps(meta, ensure_ascii=False, indent=2),
                    "listicle_roster_json": json.dumps(roster, ensure_ascii=False, indent=2),
                    "full_page_content": full_content,
                },
            )
            fn = safe_filename(f"{i+1:02d}_{run_id}_{short_hash(listicle_url)}.txt")
            fp = os.path.join(out_bias, fn)
            with open(fp, "w", encoding="utf-8") as fh:
                fh.write(prompt)
            index["bias_uptake"].append({"run_id": run_id, "listicle_url": listicle_url, "path": fp})

    # Fidelity prompts
    for i, job in enumerate(iter_jsonl(fid_jobs_path)):
        if i >= args.max_per_type:
            break
        run_id = job["run_id"]
        source_url = job["source_url"]
        source_type = job.get("source_type", "unknown")
        user_prompt = (job.get("meta") or {}).get("prompt", "N/A")
        roster = job.get("listicle_roster", [])
        claims = job.get("claims", [])
        chunks = job.get("evidence_chunks", [])
        prompt = fill_placeholders(
            fid_tpl,
            {
                "url": source_url,
                "source_type": source_type,
                "user_prompt": user_prompt,
            },
        )
        # Append structured blocks as JSON for clarity (prompt template shows schemas; this is concrete instance)
        prompt += "\n\nLISTICLE PRODUCT ROSTER (instance):\n" + json.dumps(roster, ensure_ascii=False, indent=2)
        prompt += "\n\nCLAIMS (instance):\n" + json.dumps(claims, ensure_ascii=False, indent=2)
        prompt += "\n\nEVIDENCE CHUNKS (instance):\n" + json.dumps(chunks, ensure_ascii=False, indent=2)

        fn = safe_filename(f"{i+1:02d}_{run_id}_{short_hash(source_url)}.txt")
        fp = os.path.join(out_fid, fn)
        with open(fp, "w", encoding="utf-8") as fh:
            fh.write(prompt)
        index["fidelity"].append({"run_id": run_id, "source_url": source_url, "path": fp})

    with open(os.path.join(args.out_dir, "index.json"), "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, indent=2)

    print("WROTE", args.out_dir)
    print(" selection prompts:", len(index["selection"]))
    print(" bias/uptake prompts:", len(index["bias_uptake"]))
    print(" fidelity prompts:", len(index["fidelity"]))
    print(" index:", os.path.join(args.out_dir, "index.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

