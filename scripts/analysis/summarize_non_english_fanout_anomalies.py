import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from typing import Dict, List, Tuple


LANG_KEYWORDS = {
    "german": ["german", "deutsch", "de-de"],
    "french": ["french", "français", "francais", "fr-fr"],
    "spanish": ["spanish", "español", "espanol", "es-es"],
    "japanese": ["japanese", "日本語", "jp-ja", "ja-jp"],
    "chinese": ["chinese", "中文", "mandarin", "cantonese", "zh-cn", "zh-tw"],
    "korean": ["korean", "한국어", "ko-kr"],
    # NOTE: don't include short language codes like "ar" because they match many English words.
    "arabic": ["arabic", "العربية"],
    "farsi": ["farsi", "persian", "فارسی", "پارسی"],
    "portuguese": ["portuguese", "pt-br", "pt-pt"],
    "italian": ["italian", "it-it"],
    "russian": ["russian", "ru-ru"],
}


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def prompt_mentions_language(prompt: str) -> List[str]:
    p = normalize(prompt)
    hits = []
    for lang, kws in LANG_KEYWORDS.items():
        for kw in kws:
            kw_l = kw.lower()
            # If keyword is purely alnum, require word boundary; otherwise substring is fine
            if re.fullmatch(r"[a-z0-9]+", kw_l):
                if re.search(rf"\b{re.escape(kw_l)}\b", p):
                    hits.append(lang)
                    break
            else:
                if kw_l in p:
                    hits.append(lang)
                    break
    return sorted(set(hits))


def detect_script(s: str) -> str:
    # Rough classification by Unicode ranges
    # Normalize common smart punctuation that can appear in English
    s = (
        (s or "")
        .replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u00a0", " ")
    )
    if re.search(r"[\u3040-\u30ff]", s):  # Hiragana/Katakana
        return "jp"
    if re.search(r"[\u4e00-\u9fff]", s):  # CJK Unified
        return "cjk"
    if re.search(r"[\uac00-\ud7af]", s):  # Hangul
        return "kr"
    if re.search(r"[\u0600-\u06ff]", s):  # Arabic block
        return "arabic"
    if re.search(r"[\u0400-\u04ff]", s):  # Cyrillic
        return "cyrillic"
    if re.search(r"[^\x00-\x7F]", s):  # other non-ascii (mostly Latin accents)
        return "latin_ext"
    return "latin_ascii"


def likely_expected_by_prompt(script: str, mentioned_langs: List[str]) -> bool:
    # If prompt explicitly references the language family, treat as expected.
    if not mentioned_langs:
        return False
    if script in ("jp",) and ("japanese" in mentioned_langs):
        return True
    if script in ("cjk",) and ("chinese" in mentioned_langs or "japanese" in mentioned_langs):
        return True
    if script == "arabic" and ("arabic" in mentioned_langs or "farsi" in mentioned_langs):
        return True
    # For latin-script non-English (e.g., French/Spanish/German words), we can't map reliably here,
    # so we only use prompt language mentions as a weak signal.
    if script in ("latin_ascii", "latin_ext") and any(x in mentioned_langs for x in ("german", "french", "spanish", "portuguese", "italian", "russian")):
        return True
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description="Summarize non-English fan-out anomalies and separate expected vs unexpected.")
    ap.add_argument("--in", dest="in_csv", default="data/enrichment/non_english_fanout_anomalies_gpt.csv")
    ap.add_argument("--out-json", default="data/enrichment/non_english_fanout_anomalies_gpt_summary.json")
    ap.add_argument("--out-unexpected-csv", default="data/enrichment/non_english_fanout_anomalies_gpt_unexpected_only.csv")
    args = ap.parse_args()

    rows: List[Dict[str, str]] = []
    with open(args.in_csv, "r", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r:
                rows.append(r)

    counts = Counter()
    unexpected: List[Dict[str, str]] = []
    by_run = defaultdict(int)

    for r in rows:
        prompt = r.get("prompt", "") or ""
        flagged = r.get("flagged_query", "") or ""
        script = detect_script(flagged)
        mentioned = prompt_mentions_language(prompt)
        expected = likely_expected_by_prompt(script, mentioned)

        counts["total_flagged_rows"] += 1
        counts[f"script::{script}"] += 1
        if expected:
            counts["expected_by_prompt_language"] += 1
        else:
            counts["unexpected_or_unexplained"] += 1
            rr = dict(r)
            rr["script"] = script
            rr["prompt_language_mentions"] = ",".join(mentioned)
            unexpected.append(rr)

        run_key = f"{r.get('prompt_id','')}_r{r.get('run_number','')}_{r.get('account_type','')}"
        by_run[run_key] += 1

    # write unexpected csv
    if unexpected:
        fieldnames = list(unexpected[0].keys())
        with open(args.out_unexpected_csv, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for r in unexpected:
                w.writerow(r)

    payload = {
        "counts": dict(counts),
        "unique_runs_flagged": len(by_run),
        "example_run_counts": dict(list(by_run.items())[:20]),
        "unexpected_rows_written_to": args.out_unexpected_csv,
    }
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

