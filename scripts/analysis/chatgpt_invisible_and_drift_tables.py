import json
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple


DB_PATH = "geo_fresh.db"
LABELS_JSONL = "datapass/page_labels_combined_v2.5.jsonl"


def safe_int(x: Any) -> Optional[int]:
    try:
        if x is None:
            return None
        return int(x)
    except Exception:
        return None


def normalize_for_join(u: str) -> str:
    """
    Best-effort normalization to match geo_fresh.db url_normalized.
    """
    s = (u or "").strip().lower()
    if not s:
        return ""
    for p in ("http://", "https://"):
        if s.startswith(p):
            s = s[len(p) :]
    if s.startswith("www."):
        s = s[4:]
    # drop fragments
    s = s.split("#", 1)[0]
    # drop query
    s = s.split("?", 1)[0]
    # strip trailing slashes
    while s.endswith("/"):
        s = s[:-1]
    return s


def iter_jsonl(path: str) -> Iterable[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue


def load_labels_index() -> Dict[str, Dict[str, Any]]:
    """
    url_normalized -> label dict (response.urls.*)
    """
    out: Dict[str, Dict[str, Any]] = {}
    for rec in iter_jsonl(LABELS_JSONL):
        url = rec.get("url") or ""
        lab = (((rec.get("response") or {}).get("urls") or {}) if isinstance(rec.get("response"), dict) else {}) or {}
        k = normalize_for_join(url)
        if k and isinstance(lab, dict):
            out[k] = lab
    return out


@dataclass
class BucketStats:
    n: int = 0
    # bool fields: count of truthy
    has_tables: int = 0
    has_numbered_lists: int = 0
    has_bullet_points: int = 0
    has_pros_cons: int = 0
    # scored fields: sum + count
    promo_sum: float = 0.0
    promo_n: int = 0
    expert_sum: float = 0.0
    expert_n: int = 0
    spam_sum: float = 0.0
    spam_n: int = 0
    read_sum: float = 0.0
    read_n: int = 0
    # categorical
    type_counts: Counter = None  # type: ignore
    tone_counts: Counter = None  # type: ignore

    def __post_init__(self) -> None:
        self.type_counts = Counter()
        self.tone_counts = Counter()

    def add(self, lab: Dict[str, Any]) -> None:
        self.n += 1
        # bool-ish
        for f in ("has_tables", "has_numbered_lists", "has_bullet_points", "has_pros_cons"):
            v = safe_int(lab.get(f))
            if v:
                setattr(self, f, getattr(self, f) + 1)
        # scores
        for key, sum_name, n_name in (
            ("promotional_intensity_score", "promo_sum", "promo_n"),
            ("expertise_signal_score", "expert_sum", "expert_n"),
            ("spamminess_score", "spam_sum", "spam_n"),
            ("readability_score", "read_sum", "read_n"),
        ):
            v = safe_int(lab.get(key))
            if v is not None:
                setattr(self, sum_name, getattr(self, sum_name) + float(v))
                setattr(self, n_name, getattr(self, n_name) + 1)
        # categorical
        t = (lab.get("type") or "").strip()
        if t:
            self.type_counts[t] += 1
        tone = (lab.get("tone") or "").strip()
        if tone:
            self.tone_counts[tone] += 1

    def mean(self, sum_name: str, n_name: str) -> Optional[float]:
        n = getattr(self, n_name)
        if not n:
            return None
        return getattr(self, sum_name) / n

    def pct(self, k: str) -> Optional[float]:
        if not self.n:
            return None
        return (getattr(self, k) / self.n) * 100.0


def main() -> None:
    labels = load_labels_index()

    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    out: Dict[str, Any] = {"by_account_type": {}}

    for acct in ("enterprise", "personal"):
        # ---- cited URLs universe (occurrence-level; row per citation) ----
        total_cited = db.execute(
            "SELECT COUNT(*) AS n FROM citations WHERE account_type=? AND citation_type='cited'",
            (acct,),
        ).fetchone()["n"]

        found_top200 = db.execute(
            """
            SELECT COUNT(*) AS n
            FROM citations c
            WHERE c.account_type=? AND c.citation_type='cited'
              AND EXISTS (
                SELECT 1 FROM bing_results b
                WHERE b.run_id=c.run_id AND b.url_normalized=c.url_normalized AND b.position<=200
              )
            """,
            (acct,),
        ).fetchone()["n"]

        found_11_30 = db.execute(
            """
            SELECT COUNT(*) AS n
            FROM citations c
            WHERE c.account_type=? AND c.citation_type='cited'
              AND EXISTS (
                SELECT 1 FROM bing_results b
                WHERE b.run_id=c.run_id AND b.url_normalized=c.url_normalized AND b.position BETWEEN 11 AND 30
              )
            """,
            (acct,),
        ).fetchone()["n"]

        # ---- buckets for feature comparisons (unique URLs within bucket) ----
        # cited bucket: unique cited URLs across all runs
        cited_urls = [
            r["url_normalized"]
            for r in db.execute(
                "SELECT DISTINCT url_normalized FROM citations WHERE account_type=? AND citation_type='cited'",
                (acct,),
            ).fetchall()
        ]

        # additional bucket: unique additional URLs across all runs
        additional_urls = [
            r["url_normalized"]
            for r in db.execute(
                "SELECT DISTINCT url_normalized FROM citations WHERE account_type=? AND citation_type='additional'",
                (acct,),
            ).fetchall()
        ]

        # page1 ignored: Bing page 1 URLs (per run) that were not cited; unique across runs
        page1_ignored_urls = [
            r["url_normalized"]
            for r in db.execute(
                """
                SELECT DISTINCT b.url_normalized
                FROM bing_results b
                WHERE b.account_type=? AND b.page_num=1
                  AND NOT EXISTS (
                    SELECT 1 FROM citations c
                    WHERE c.run_id=b.run_id AND c.url_normalized=b.url_normalized AND c.citation_type='cited'
                  )
                """,
                (acct,),
            ).fetchall()
        ]

        # invisible (not found in bing <=200) among *cited URLs* (unique URLs)
        invisible_cited_urls = [
            r["url_normalized"]
            for r in db.execute(
                """
                SELECT DISTINCT c.url_normalized
                FROM citations c
                WHERE c.account_type=? AND c.citation_type='cited'
                  AND NOT EXISTS (
                    SELECT 1 FROM bing_results b
                    WHERE b.run_id=c.run_id AND b.url_normalized=c.url_normalized AND b.position<=200
                  )
                """,
                (acct,),
            ).fetchall()
        ]

        # truly invisible (not found in Bing <=200 AND not found in Google for the same run)
        # NOTE: For Enterprise, Google is treated as a control group; for Personal, Google is part of the observed multi-provider surface.
        truly_invisible_cited_urls = [
            r["url_normalized"]
            for r in db.execute(
                """
                SELECT DISTINCT c.url_normalized
                FROM citations c
                WHERE c.account_type=? AND c.citation_type='cited'
                  AND NOT EXISTS (
                    SELECT 1 FROM bing_results b
                    WHERE b.run_id=c.run_id AND b.url_normalized=c.url_normalized AND b.position<=200
                  )
                  AND NOT EXISTS (
                    SELECT 1 FROM google_results g
                    WHERE g.chatgpt_run_id=REPLACE(c.run_id, '_personal', '')
                      AND g.account_type=c.account_type
                      AND g.url_normalized=c.url_normalized
                  )
                """,
                (acct,),
            ).fetchall()
        ]

        def bucketize(urls: List[str]) -> Dict[str, Any]:
            bs = BucketStats()
            missing = 0
            for u in urls:
                lab = labels.get(u)
                if not lab:
                    missing += 1
                    continue
                bs.add(lab)
            return {
                "n_urls": len(urls),
                "n_labeled": bs.n,
                "n_missing_label": missing,
                "pct_has_tables": bs.pct("has_tables"),
                "pct_has_numbered_lists": bs.pct("has_numbered_lists"),
                "pct_has_bullet_points": bs.pct("has_bullet_points"),
                "pct_has_pros_cons": bs.pct("has_pros_cons"),
                "mean_promotional_intensity_score": bs.mean("promo_sum", "promo_n"),
                "mean_expertise_signal_score": bs.mean("expert_sum", "expert_n"),
                "mean_spamminess_score": bs.mean("spam_sum", "spam_n"),
                "mean_readability_score": bs.mean("read_sum", "read_n"),
                "type_counts": dict(bs.type_counts.most_common()),
                "tone_counts": dict(bs.tone_counts.most_common()),
            }

        out["by_account_type"][acct] = {
            "cited_occurrences_total": total_cited,
            "cited_occurrences_found_in_bing_top200": found_top200,
            "cited_occurrences_found_in_bing_rank_11_30": found_11_30,
            "pct_cited_occurrences_found_in_bing_top200": (found_top200 / total_cited * 100.0) if total_cited else None,
            "pct_cited_occurrences_found_in_bing_rank_11_30": (found_11_30 / total_cited * 100.0) if total_cited else None,
            "buckets": {
                "cited_urls": bucketize(cited_urls),
                "additional_urls": bucketize(additional_urls),
                "page1_ignored_urls": bucketize(page1_ignored_urls),
                "invisible_cited_urls": bucketize(invisible_cited_urls),
                "truly_invisible_cited_urls_bing_and_google": bucketize(truly_invisible_cited_urls),
            },
        }

    out_path = "data/enrichment/chatgpt_invisible_and_feature_buckets.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print(f"Wrote: {out_path}")
    print(json.dumps(out["by_account_type"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

