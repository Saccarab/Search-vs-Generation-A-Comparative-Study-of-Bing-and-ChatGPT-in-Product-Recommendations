import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple


NON_EN_HINTS = [
    # German
    "kostenlos",
    "untertitel",
    "übersetzen",
    "ubersetzen",
    "beste",
    "bester",
    "bewertungen",
    "münchen",
    "munchen",
    "deutsch",
    "auf deutsch",
    # French
    "gratuit",
    "meilleur",
    "meilleure",
    "traduire",
    "sous-titres",
    # Spanish
    "gratis",
    "mejor",
    "mejores",
    "traducir",
    "subtítulos",
    "subtitulos",
    # Portuguese
    "melhor",
    "gratuito",
    "legendas",
    "traduzir",
    # Italian
    "migliore",
    "gratuita",
    "sottotitoli",
    "tradurre",
    # Dutch
    "gratis",
    "ondertitels",
    "vertalen",
    # Nordic (light)
    "bästa",
    "basta",
]


def iter_rows(path: str) -> Iterable[Dict[str, str]]:
    # These CSVs can contain very large JSON fields (raw_api_response_json, etc.)
    # Increase parser field limit to avoid _csv.Error: field larger than field limit.
    try:
        csv.field_size_limit(sys.maxsize)
    except Exception:
        # best-effort; on some platforms sys.maxsize may be rejected
        pass
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row:
                continue
            yield row


def parse_jsonish(s: str) -> Any:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        # some CSVs may double-encode; try to unescape common patterns
        try:
            s2 = s.encode("utf-8").decode("unicode_escape")
            return json.loads(s2)
        except Exception:
            return None


def normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def looks_english_prompt(prompt: str) -> bool:
    # conservative: treat as English if it's mostly ASCII and has typical English stopwords,
    # and lacks obvious non-English markers.
    p = normalize_ws(prompt).lower()
    if not p:
        return False
    if any(ch for ch in p if ord(ch) > 127):
        return False
    # obvious non-English hints
    for h in NON_EN_HINTS:
        if h in p:
            return False
    english_stop = [" the ", " best ", " for ", " and ", " to ", " with ", " free "]
    hits = sum(1 for w in english_stop if w in f" {p} ")
    return hits >= 1


def classify_query_language_hint(q: str) -> Tuple[bool, Optional[str]]:
    qq = normalize_ws(q).lower()
    if not qq:
        return False, None
    # Normalize common non-ASCII punctuation that often appears in English (avoid false positives)
    qq = (
        qq.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u00a0", " ")
    )
    # Strong signal: non-ascii chars (umlauts, accents, non-latin scripts)
    if any(ch for ch in qq if ord(ch) > 127):
        return True, "non_ascii"
    # Hint words
    for h in NON_EN_HINTS:
        if h in qq:
            return True, h
    return False, None


@dataclass
class Finding:
    dataset: str
    account_type: str
    prompt_id: str
    run_number: str
    query_index: str
    prompt: str
    fanout_queries: str
    flagged_query: str
    reason: str


def extract_hidden_queries(row: Dict[str, str]) -> List[str]:
    raw = (row.get("hidden_queries_json") or "").strip()
    if not raw:
        return []
    obj = parse_jsonish(raw)
    if obj is None:
        return []
    if isinstance(obj, list):
        return [str(x) for x in obj if x is not None and str(x).strip()]
    # sometimes stored as {"queries":[...]}
    if isinstance(obj, dict):
        q = obj.get("queries")
        if isinstance(q, list):
            return [str(x) for x in q if x is not None and str(x).strip()]
    return []


def infer_account_type_from_path(path: str) -> str:
    lp = path.lower()
    if "enterprise" in lp:
        return "enterprise"
    if "personal" in lp:
        return "personal"
    return ""


def main() -> None:
    ap = argparse.ArgumentParser(description="Find GPT runs where an English prompt has a non-English fan-out query (heuristic).")
    ap.add_argument("--in-csv", nargs="+", required=True, help="Input ChatGPT results CSV(s) with hidden_queries_json.")
    ap.add_argument("--out-csv", default="data/enrichment/non_english_fanout_anomalies_gpt.csv")
    args = ap.parse_args()

    findings: List[Finding] = []

    for path in args.in_csv:
        acct_hint = infer_account_type_from_path(path)
        for row in iter_rows(path):
            prompt = row.get("query") or ""
            if not looks_english_prompt(prompt):
                continue
            hqs = extract_hidden_queries(row)
            if not hqs:
                continue
            for q in hqs:
                is_non_en, reason = classify_query_language_hint(q)
                if not is_non_en:
                    continue
                findings.append(
                    Finding(
                        dataset=path,
                        account_type=acct_hint or (row.get("account_type") or ""),
                        prompt_id=row.get("prompt_id") or "",
                        run_number=row.get("run_number") or "",
                        query_index=row.get("query_index") or "",
                        prompt=normalize_ws(prompt),
                        fanout_queries=json.dumps(hqs, ensure_ascii=False),
                        flagged_query=normalize_ws(q),
                        reason=reason or "",
                    )
                )

    # Write output
    out_path = args.out_csv
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "account_type",
                "prompt_id",
                "run_number",
                "query_index",
                "prompt",
                "flagged_query",
                "reason",
                "fanout_queries",
                "source_csv",
            ],
        )
        w.writeheader()
        for x in findings:
            w.writerow(
                {
                    "account_type": x.account_type,
                    "prompt_id": x.prompt_id,
                    "run_number": x.run_number,
                    "query_index": x.query_index,
                    "prompt": x.prompt,
                    "flagged_query": x.flagged_query,
                    "reason": x.reason,
                    "fanout_queries": x.fanout_queries,
                    "source_csv": x.dataset,
                }
            )

    print(f"Flagged {len(findings)} potential anomalies -> {out_path}")


if __name__ == "__main__":
    main()

