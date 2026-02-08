import argparse
import json
import math
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple


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


def safe_int(x: Any) -> Optional[int]:
    if isinstance(x, int):
        return x
    if isinstance(x, str):
        x = x.strip()
        if x.isdigit():
            try:
                return int(x)
            except Exception:
                return None
    return None


def mean(xs: List[float]) -> Optional[float]:
    if not xs:
        return None
    return sum(xs) / len(xs)


def pearson_corr(xs: List[float], ys: List[float]) -> Optional[float]:
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    mx = mean(xs)
    my = mean(ys)
    if mx is None or my is None:
        return None
    num = 0.0
    dx = 0.0
    dy = 0.0
    for x, y in zip(xs, ys):
        ax = x - mx
        ay = y - my
        num += ax * ay
        dx += ax * ax
        dy += ay * ay
    if dx <= 0 or dy <= 0:
        return None
    return num / math.sqrt(dx * dy)


def analyze(path: str) -> Dict[str, Any]:
    def bucket_for(rec: Dict[str, Any]) -> str:
        study = (rec.get("study") or "").strip().lower() or "unknown"
        if study == "gpt":
            acct = (rec.get("account_type") or "").strip().lower() or "unknown"
            return f"gpt::{acct}"
        if study == "gemini":
            return "gemini"
        return study

    # We only analyze actual "product" roster items that are confirmed present and have listicle_rank.
    agg: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "norm_ranks": [],
        "raw_ranks": [],
        "totals": [],
        "resp_orders": [],
        "listicle_ranks_for_corr": [],
        "topk_counts": Counter(),
        "topk_expected": Counter(),
        "n_items": 0,
        "skipped_missing_total": 0,
        "skipped_missing_rank": 0,
    })

    for rec in iter_jsonl(path):
        b = bucket_for(rec)
        a = agg[b]

        resp = rec.get("response") or {}
        products = resp.get("products") or []
        total = safe_int(resp.get("total_products_in_listicle"))

        # Compute product-only response order (1..m within each job)
        prod_items: List[Tuple[int, Dict[str, Any]]] = []
        for i, p in enumerate(products):
            if not isinstance(p, dict):
                continue
            if (p.get("roster_item_type") or "").strip() != "product":
                continue
            prod_items.append((i, p))

        prod_order = 0
        for _, p in prod_items:
            present = (p.get("present_in_listicle") or "").strip().lower()
            if present != "yes":
                continue

            r = safe_int(p.get("listicle_rank"))
            if r is None:
                a["skipped_missing_rank"] += 1
                continue

            if total is None or total <= 1:
                a["skipped_missing_total"] += 1
                continue

            a["n_items"] += 1
            a["raw_ranks"].append(r)
            a["totals"].append(total)

            # Normalized rank in [0,1]; lower is "higher ranked"
            norm = (r - 1) / (total - 1)
            a["norm_ranks"].append(norm)

            # top-k rates relative to listicle size
            if r == 1:
                a["topk_counts"]["top1"] += 1
            if r <= 3:
                a["topk_counts"]["top3"] += 1
            if r <= 5:
                a["topk_counts"]["top5"] += 1
            if r <= 10:
                a["topk_counts"]["top10"] += 1

            # expected probability of falling into top-k under uniform random selection of an item
            # from a list of length `total`
            a["topk_expected"]["top1"] += min(1.0 / total, 1.0)
            a["topk_expected"]["top3"] += min(3.0 / total, 1.0)
            a["topk_expected"]["top5"] += min(5.0 / total, 1.0)
            a["topk_expected"]["top10"] += min(10.0 / total, 1.0)

            # Correlation: response order among products vs listicle rank
            prod_order += 1
            a["resp_orders"].append(float(prod_order))
            a["listicle_ranks_for_corr"].append(float(r))

    buckets_out: Dict[str, Any] = {}
    for b, a in agg.items():
        n_items = a["n_items"]
        raw_ranks: List[int] = a["raw_ranks"]
        totals: List[int] = a["totals"]
        norm_ranks: List[float] = a["norm_ranks"]
        topk_counts: Counter = a["topk_counts"]
        resp_orders: List[float] = a["resp_orders"]
        listicle_ranks_for_corr: List[float] = a["listicle_ranks_for_corr"]

        med = None
        if raw_ranks:
            sr = sorted(raw_ranks)
            med = sr[len(sr) // 2]

        topk_rates: Dict[str, float] = {}
        if n_items:
            topk_rates = {k: (v / n_items) for k, v in topk_counts.items()}

        topk_expected_rates: Dict[str, float] = {}
        topk_lift_vs_uniform: Dict[str, float] = {}
        if n_items:
            # expected counts are already summed probabilities per item; divide by n_items to get expected rate
            topk_expected_rates = {k: (v / n_items) for k, v in a["topk_expected"].items()}
            for k, obs in topk_rates.items():
                exp = topk_expected_rates.get(k)
                if exp is not None and exp > 0:
                    topk_lift_vs_uniform[k] = obs / exp

        buckets_out[b] = {
            "n_product_items_present_with_rank_and_total": n_items,
            "skipped_missing_listicle_rank": a["skipped_missing_rank"],
            "skipped_missing_total_products_in_listicle": a["skipped_missing_total"],
            "mean_total_products_in_listicle_for_used_items": mean([float(x) for x in totals]),
            "mean_normalized_rank_0_best_1_worst": mean(norm_ranks),
            "median_listicle_rank": med,
            "topk_rates": topk_rates,
            "topk_expected_rates_uniform": topk_expected_rates,
            "topk_lift_vs_uniform": topk_lift_vs_uniform,
            "pearson_corr_response_product_order_vs_listicle_rank": pearson_corr(resp_orders, listicle_ranks_for_corr),
        }

    return {"path": path, "by_bucket": buckets_out}


def main() -> None:
    ap = argparse.ArgumentParser(description="Quantify listicle-rank bias from semantic-fidelity judge JSONL outputs.")
    ap.add_argument("--in", dest="inputs", nargs="+", required=True, help="Input JSONL result files.")
    ap.add_argument("--out-json", default="data/enrichment/listicle_rank_bias_summary_v4.1.json")
    args = ap.parse_args()

    summaries = [analyze(p) for p in args.inputs]
    payload = {"summaries": summaries}

    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # Print a compact console summary
    for s in summaries:
        print("\n===", s["path"], "===")
        byb = s.get("by_bucket") or {}
        for b in sorted(byb.keys()):
            r = byb[b] or {}
            print(f"\n  [{b}]")
            print("  n_used:", r.get("n_product_items_present_with_rank_and_total"))
            print("  mean_norm_rank:", r.get("mean_normalized_rank_0_best_1_worst"))
            print("  mean_total_products:", r.get("mean_total_products_in_listicle_for_used_items"))
            tr = r.get("topk_rates") or {}
            print("  top1/top3/top5:", tr.get("top1"), tr.get("top3"), tr.get("top5"))
            print("  corr(resp_order, listicle_rank):", r.get("pearson_corr_response_product_order_vs_listicle_rank"))


if __name__ == "__main__":
    main()

