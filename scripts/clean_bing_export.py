"""
Clean/parse the Bing Results Scraper CSV export.

Why this exists:
- The export can include very large quoted `content` fields (commas/newlines).
- We want deterministic cleaning for analysis/ingest:
  - dedupe results per (run_id, query) by normalized URL key
  - re-number positions sequentially (1..N)
  - optionally trim to Top N (default 30)
  - optionally drop `content` column to keep files light

Input columns (current extension export):
  query, position, content, contentError, contentLength, displayUrl, domain, run_id, snippet, title, url
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import base64
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_PARAM_PREFIXES = ("utm_",)
TRACKING_PARAMS_EXACT = {
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
    URL key for joins/deduping.
    - Lowercase host
    - Remove scheme and leading www.
    - Drop fragment
    - Remove trailing slash (except root)
    - Remove common tracking params (utm_*, gclid, fbclid, ...)

    Note: We intentionally keep non-tracking query params to avoid over-merging
    pages that genuinely differ by query string.
    """
    if not raw_url or not isinstance(raw_url, str):
        return ""

    url = raw_url.strip()
    if not url:
        return ""

    # Ensure urlsplit works even if scheme missing
    if "://" not in url:
        url = "https://" + url

    parts = urlsplit(url)
    host = (parts.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]

    # Bing click-tracking redirect links look like:
    #   https://www.bing.com/ck/a?...&u=a1aHR0cHM6Ly9leGFtcGxlLmNvbS8...&ntb=1
    # The `u` param is usually base64-encoded target URL prefixed with "a1".
    # We decode it and normalize the real destination instead of keeping bing.com/ck/a.
    if host.endswith("bing.com") and parts.path.startswith("/ck/a"):
        try:
            qs = dict(parse_qsl(parts.query, keep_blank_values=True))
            u = (qs.get("u") or "").strip()
            if u.startswith("a1"):
                b64 = u[2:]
                # add base64 padding if missing
                pad = "=" * ((4 - (len(b64) % 4)) % 4)
                try:
                    decoded = base64.urlsafe_b64decode((b64 + pad).encode("utf-8")).decode("utf-8", errors="replace")
                except Exception:
                    return ""
                if decoded.startswith("http"):
                    return normalize_url_key(decoded)
                # If it's an internal bing path (/videos/...), treat as non-web page
                return ""
        except Exception:
            return ""

    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]

    # Filter query params
    kept: List[Tuple[str, str]] = []
    for k, v in parse_qsl(parts.query, keep_blank_values=True):
        lk = k.lower()
        if any(lk.startswith(p) for p in TRACKING_PARAM_PREFIXES):
            continue
        if lk in TRACKING_PARAMS_EXACT:
            continue
        kept.append((k, v))
    query = urlencode(kept, doseq=True)

    # Rebuild without scheme; fragment dropped
    rebuilt = urlunsplit(("", host, path, query, ""))
    # urlunsplit with empty scheme yields "//host/path?..."; strip leading slashes
    rebuilt = rebuilt.lstrip("/")
    return rebuilt


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class GroupKey:
    run_id: str
    query: str


def iter_rows(path: str) -> Iterable[Dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSV appears to have no header/columns.")
        for row in reader:
            # DictReader may return None for missing fields; normalize to strings
            yield {k: (v if v is not None else "") for k, v in row.items()}


def clean_bing_export(
    rows: Iterable[Dict[str, str]],
    top_n: int = 30,
    drop_content: bool = False,
    content_outdir: Optional[str] = None,
) -> Tuple[List[Dict[str, str]], Dict[str, int]]:
    """
    Returns (clean_rows, stats).

    If content_outdir is provided, writes extracted text snapshots:
      <content_outdir>/<url_hash>.txt
    and replaces `content` with empty string (unless drop_content=True).
    """
    grouped: Dict[GroupKey, List[Dict[str, str]]] = {}
    stats: Dict[str, int] = {
        "input_rows": 0,
        "output_rows": 0,
        "groups": 0,
        "dropped_missing_url": 0,
        "dropped_duplicate_url": 0,
        "content_snapshots_written": 0,
    }

    for r in rows:
        stats["input_rows"] += 1
        run_id = (r.get("run_id") or "").strip()
        query = (r.get("query") or "").strip()
        key = GroupKey(run_id=run_id, query=query)
        grouped.setdefault(key, []).append(r)

    stats["groups"] = len(grouped)

    if content_outdir:
        os.makedirs(content_outdir, exist_ok=True)

    out: List[Dict[str, str]] = []

    for key, group_rows in grouped.items():
        # Sort by original position if possible, else keep insertion order
        def pos_val(rr: Dict[str, str]) -> int:
            try:
                return int((rr.get("position") or "").strip())
            except Exception:
                return 10**9

        group_rows_sorted = sorted(group_rows, key=pos_val)

        seen_keys = set()
        kept_rows: List[Dict[str, str]] = []

        for rr in group_rows_sorted:
            raw_url = (rr.get("url") or "").strip()
            if not raw_url:
                stats["dropped_missing_url"] += 1
                continue
            url_key = normalize_url_key(raw_url)
            if not url_key:
                stats["dropped_missing_url"] += 1
                continue
            if url_key in seen_keys:
                stats["dropped_duplicate_url"] += 1
                continue
            seen_keys.add(url_key)

            # Optional snapshot write
            if content_outdir:
                content = rr.get("content") or ""
                h = stable_hash(url_key)
                fp = os.path.join(content_outdir, f"{h}.txt")
                if not os.path.exists(fp):
                    with open(fp, "w", encoding="utf-8") as wf:
                        wf.write(content)
                    stats["content_snapshots_written"] += 1
                rr["content_path"] = fp.replace("\\", "/")
                rr["content"] = "" if drop_content else rr.get("content") or ""

            rr["url_key"] = url_key
            kept_rows.append(rr)
            if len(kept_rows) >= top_n:
                break

        # Re-number sequentially
        for i, rr in enumerate(kept_rows, start=1):
            rr["position"] = str(i)
            if drop_content and "content" in rr:
                rr["content"] = ""
        out.extend(kept_rows)

    stats["output_rows"] = len(out)
    return out, stats


def write_csv(path: str, rows: Sequence[Dict[str, str]]) -> None:
    if not rows:
        raise ValueError("No rows to write.")

    # Keep a stable column order: original export columns first, then added cols.
    preferred = [
        "run_id",
        "query",
        "position",
        "title",
        "snippet",
        "displayUrl",
        "domain",
        "url",
        "url_key",
        "contentLength",
        "contentError",
        "content_path",
        "content",
    ]
    all_cols = []
    seen = set()
    for c in preferred:
        if c in rows[0] and c not in seen:
            all_cols.append(c)
            seen.add(c)
    # Add any remaining columns found
    for r in rows:
        for c in r.keys():
            if c not in seen:
                all_cols.append(c)
                seen.add(c)

    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=all_cols, extrasaction="ignore", quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Clean Bing Results Scraper CSV export.")
    p.add_argument("--input", required=True, help="Path to Bing export CSV.")
    p.add_argument("--output", required=True, help="Path to write cleaned CSV.")
    p.add_argument("--top-n", type=int, default=30, help="Max unique results per (run_id, query). Default: 30")
    p.add_argument("--drop-content", action="store_true", help="Blank out the `content` field in output.")
    p.add_argument(
        "--content-outdir",
        default=None,
        help="Optional directory to write content snapshots (<hash>.txt). Adds `content_path` column.",
    )

    args = p.parse_args(argv)

    rows = iter_rows(args.input)
    clean_rows, stats = clean_bing_export(
        rows,
        top_n=args.top_n,
        drop_content=args.drop_content,
        content_outdir=args.content_outdir,
    )
    write_csv(args.output, clean_rows)

    print("Done.")
    for k in sorted(stats.keys()):
        print(f"{k}: {stats[k]}")
    print(f"output: {args.output}")
    if args.content_outdir:
        print(f"content_outdir: {args.content_outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


