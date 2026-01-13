"""
Retry a Gemini generateContent request using a raw payload JSON (as-is) for debugging.

This is useful when you want to test whether a specific payload is flaky (timeouts) without
any workbook logic.

You provide:
- A payload JSON file that matches Gemini generateContent body, e.g.:
  {
    "contents": [{"role": "user", "parts": [{"text": "..."}]}],
    "generationConfig": {"temperature": 0.0}
  }

API key is read from env (never hardcode secrets):
  - GEMINI_API_KEY (preferred) OR GOOGLE_API_KEY OR GOOGLE_GENERATIVE_AI_API_KEY

Usage (Git Bash):
  python -u scripts/llm/retry_gemini_payload_raw.py --model gemini-3-flash-preview --payload-file payload.json --tries 5 --timeout 90
"""

from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any, Dict

import requests


GEMINI_ENDPOINT_TMPL = "https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent?key={key}"


def _gemini_model_path(model: str) -> str:
    m = (model or "").strip()
    if not m:
        return "models/gemini-flash-latest"
    return m if m.startswith("models/") else f"models/{m}"


def get_api_key() -> str:
    return (
        (os.getenv("GEMINI_API_KEY", "") or "").strip()
        or (os.getenv("GOOGLE_API_KEY", "") or "").strip()
        or (os.getenv("GOOGLE_GENERATIVE_AI_API_KEY", "") or "").strip()
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--payload-file", required=True, help="Path to JSON file containing the request payload body.")
    ap.add_argument("--model", default="gemini-3-flash-preview")
    ap.add_argument("--tries", type=int, default=3, help="How many times to retry the same payload.")
    ap.add_argument("--timeout", type=int, default=60, help="Per-request timeout in seconds.")
    ap.add_argument("--sleep", type=float, default=0.0, help="Sleep seconds between tries.")
    ap.add_argument("--save-responses", default="", help="Optional directory to save raw responses per try.")
    args = ap.parse_args()

    api_key = get_api_key()
    if not api_key:
        print("Missing API key. Set GEMINI_API_KEY (preferred).")
        return 2

    payload: Dict[str, Any] = json.loads(open(args.payload_file, "r", encoding="utf-8").read())
    if not isinstance(payload, dict) or "contents" not in payload:
        print("payload-file must be a JSON object containing at least 'contents'.")
        return 2

    if args.save_responses:
        os.makedirs(args.save_responses, exist_ok=True)

    ep = GEMINI_ENDPOINT_TMPL.format(model_path=_gemini_model_path(args.model), key=api_key)

    for i in range(1, max(1, args.tries) + 1):
        print(f"\n=== try {i}/{args.tries} ===", flush=True)
        t0 = time.time()
        try:
            r = requests.post(ep, json=payload, timeout=args.timeout)
            dt = time.time() - t0
            print(f"HTTP {r.status_code} ({dt:.1f}s)", flush=True)
            body = r.text or ""
            print("body_snippet:", body[:1200], flush=True)
            if args.save_responses:
                out = os.path.join(args.save_responses, f"try_{i:02d}_status_{r.status_code}.json")
                with open(out, "w", encoding="utf-8") as wf:
                    wf.write(body)
                print("saved:", out, flush=True)
        except requests.exceptions.ReadTimeout:
            dt = time.time() - t0
            print(f"ReadTimeout after {dt:.1f}s (timeout={args.timeout}s)", flush=True)
        except Exception as e:
            dt = time.time() - t0
            print(f"Error after {dt:.1f}s: {type(e).__name__}: {str(e)[:400]}", flush=True)

        if args.sleep:
            time.sleep(args.sleep)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

