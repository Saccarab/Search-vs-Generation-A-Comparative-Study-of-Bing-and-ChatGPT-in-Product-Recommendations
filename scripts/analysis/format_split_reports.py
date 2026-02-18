import pandas as pd
import os
import json

def _rank_sample_sizes(df: pd.DataFrame, rank_min: int, rank_max: int):
    """
    menu_n/order_n are constant within a given rank across features.
    Pull one row per rank, then sum across ranks for the bin.
    """
    if df is None or df.empty:
        return (0, 0)
    one = df.sort_values(["rank", "feature"]).groupby("rank").head(1)[["rank", "menu_n", "order_n"]]
    one = one[(one["rank"] >= rank_min) & (one["rank"] <= rank_max)]
    if one.empty:
        return (0, 0)
    return (int(one["menu_n"].sum()), int(one["order_n"].sum()))

def generate_report(suffix, title):
    files = [
        ("Gemini (Google T10)", f"data/enrichment/rank_stratified_drift_gemini_google_top10{suffix}.csv"),
        ("GPT Personal (Google T10)", f"data/enrichment/rank_stratified_drift_gpt_personal_google_top10{suffix}.csv"),
        ("GPT Personal (Bing P1, Top5)", f"data/enrichment/rank_stratified_drift_gpt_personal_bing_page1_top5{suffix}.csv"),
        ("GPT Enterprise (Bing P1)", f"data/enrichment/rank_stratified_drift_gpt_enterprise_bing_page1{suffix}.csv"),
    ]

    features = [
        "bool:has_tables",
        "bool:is_current_year_2026",
        "bool:has_numbered_lists",
        "bool:has_bullet_points",
        "bool:has_pros_cons",
        "bool:has_sources_or_citations",
        "bool:has_clear_authorship",
        # Scores (binned: >=4)
        "score>=4:expertise_signal_score",
        "score>=4:freshness_cue_strength",
        "score>=4:readability_score",
        "score>=4:heading_density",
    ]

    lines = []
    lines.append("=" * 80)
    lines.append(f"DRIFT REPORT: {title}")
    lines.append("=" * 80)
    lines.append("Methodology: Binned (1-5 vs 6-10) and Volume-Weighted Average Drift.")
    lines.append("Note: For Bing studies, Bot 6-10 may be omitted (N/A) due to variable Page-1 depth. GPT Personal (Bing P1, Top5) is computed only over ranks 1-5. GPT Enterprise (Bing P1) uses ranks 1-5 for Weighted Avg.")
    lines.append("")

    for label, path in files:
        if not os.path.exists(path):
            continue
        df = pd.read_csv(path)
        is_enterprise_bing = "Enterprise" in label and "Bing" in label
        is_personal_bing_top5 = ("Personal" in label and "Bing" in label)

        top_menu_n, top_order_n = _rank_sample_sizes(df, 1, 5)
        bot_menu_n, bot_order_n = _rank_sample_sizes(df, 6, 10)
        w_menu_n, w_order_n = (top_menu_n, top_order_n) if (is_enterprise_bing or is_personal_bing_top5) else (top_menu_n + bot_menu_n, top_order_n + bot_order_n)
        
        lines.append(f">>> STUDY: {label} <<<")
        lines.append(f"Sample sizes (with DNA): Top1-5 menu_n={top_menu_n}, order_n={top_order_n}"
                     + ("" if (is_enterprise_bing or is_personal_bing_top5) else f" | Bot6-10 menu_n={bot_menu_n}, order_n={bot_order_n}")
                     + f" | Weighted window menu_n={w_menu_n}, order_n={w_order_n}")
        lines.append("-" * 80)
        lines.append(f"{'Feature':<30} | {'Top 1-5':<10} | {'Bot 6-10':<10} | {'Weighted Avg'}")
        lines.append("-" * 80)

        for f in features:
            f_df = df[df['feature'] == f]
            if f_df.empty: continue
            
            # Binned 1-5
            bin15 = f_df[f_df['rank'].between(1, 5)]
            if not bin15.empty:
                m_n = bin15['menu_n'].sum()
                o_n = bin15['order_n'].sum()
                m_pct = (bin15['menu_count'].sum() / m_n * 100) if m_n > 0 else 0
                o_pct = (bin15['order_count'].sum() / o_n * 100) if o_n > 0 else 0
                drift15 = o_pct - m_pct
            else: drift15 = 0

            # Binned 6-10
            drift610 = None
            if not is_enterprise_bing and not is_personal_bing_top5:
                bin610 = f_df[f_df['rank'].between(6, 10)]
                if not bin610.empty:
                    m_n = bin610['menu_n'].sum()
                    o_n = bin610['order_n'].sum()
                    m_pct = (bin610['menu_count'].sum() / m_n * 100) if m_n > 0 else 0
                    o_pct = (bin610['order_count'].sum() / o_n * 100) if o_n > 0 else 0
                    drift610 = o_pct - m_pct
                else:
                    drift610 = 0

            # Weighted Avg
            # Weighted avg is computed as Sum(drift_at_rank * order_n_at_rank) / total_order_n
            # For Bing studies (Enterprise, and Personal Top5), restrict to ranks 1..5 only.
            ranks_df = f_df[f_df['rank'].between(1, 5)] if (is_enterprise_bing or is_personal_bing_top5) else f_df[f_df['rank'].between(1, 10)]
            total_order = ranks_df['order_n'].sum()
            if total_order > 0:
                weighted_drift = (ranks_df['drift_pp'] * ranks_df['order_n']).sum() / total_order
            else:
                weighted_drift = 0

            feat_name = f.split(':')[-1]
            drift610_str = "   N/A   " if drift610 is None else f"{drift610:>8.2f}pp"
            lines.append(f"{feat_name:<30} | {drift15:>8.2f}pp | {drift610_str:>10} | {weighted_drift:>8.2f}pp")
        lines.append("")

    return "\n".join(lines)

def build_drift_json():
    files = [
        ("Gemini (Google T10)", {
            "listicle": "data/enrichment/rank_stratified_drift_gemini_google_top10_listicle.csv",
            "product_page": "data/enrichment/rank_stratified_drift_gemini_google_top10_product_page.csv",
        }),
        ("GPT Personal (Google T10)", {
            "listicle": "data/enrichment/rank_stratified_drift_gpt_personal_google_top10_listicle.csv",
            "product_page": "data/enrichment/rank_stratified_drift_gpt_personal_google_top10_product_page.csv",
        }),
        ("GPT Personal (Bing P1, Top5)", {
            "listicle": "data/enrichment/rank_stratified_drift_gpt_personal_bing_page1_top5_listicle.csv",
            "product_page": "data/enrichment/rank_stratified_drift_gpt_personal_bing_page1_top5_product_page.csv",
        }),
        ("GPT Enterprise (Bing P1)", {
            "listicle": "data/enrichment/rank_stratified_drift_gpt_enterprise_bing_page1_listicle.csv",
            "product_page": "data/enrichment/rank_stratified_drift_gpt_enterprise_bing_page1_product_page.csv",
        }),
    ]

    features = [
        ("has_tables", "bool:has_tables"),
        ("is_current_year_2026", "bool:is_current_year_2026"),
        ("has_numbered_lists", "bool:has_numbered_lists"),
        ("has_bullet_points", "bool:has_bullet_points"),
        ("has_pros_cons", "bool:has_pros_cons"),
        ("has_sources_or_citations", "bool:has_sources_or_citations"),
        ("has_clear_authorship", "bool:has_clear_authorship"),
        # Scores (binned: >=4)
        ("expertise_signal_score", "score>=4:expertise_signal_score"),
        ("freshness_cue_strength", "score>=4:freshness_cue_strength"),
        ("readability_score", "score>=4:readability_score"),
        ("heading_density", "score>=4:heading_density"),
    ]

    out = {
        "methodology": {
            "bins": ["1-5", "6-10"],
            "weighted_avg": "Volume-weighted by order_n per rank",
            "enterprise_note": "For Bing studies, ranks 6-10 may be omitted; weighted average is computed over ranks 1-5 only. GPT Personal (Bing P1, Top5) is computed only over ranks 1-5.",
        },
        "features": [f[0] for f in features],
        "content_types": ["listicle", "product_page"],
        "studies": [s for s, _ in files],
        "tables": {
            "listicle": {},
            "product_page": {},
        },
        "categoricals": {
            "listicle": {},
            "product_page": {},
        },
        "sample_sizes": {
            "listicle": {},
            "product_page": {},
        },
    }

    for study_label, paths in files:
        is_enterprise_bing = ("Enterprise" in study_label and "Bing" in study_label)
        is_personal_bing_top5 = ("Personal" in study_label and "Bing" in study_label)
        for ctype in ("listicle", "product_page"):
            path = paths[ctype]
            if not os.path.exists(path):
                continue
            df = pd.read_csv(path)
            table = []
            for feat_name, feat_key in features:
                f_df = df[df["feature"] == feat_key]
                if f_df.empty:
                    continue

                bin15 = f_df[f_df["rank"].between(1, 5)]
                if not bin15.empty:
                    m_n = bin15["menu_n"].sum()
                    o_n = bin15["order_n"].sum()
                    m_pct = (bin15["menu_count"].sum() / m_n * 100) if m_n > 0 else 0.0
                    o_pct = (bin15["order_count"].sum() / o_n * 100) if o_n > 0 else 0.0
                    drift15 = o_pct - m_pct
                else:
                    drift15 = 0.0

                drift610 = None
                if not is_enterprise_bing and not is_personal_bing_top5:
                    bin610 = f_df[f_df["rank"].between(6, 10)]
                    if not bin610.empty:
                        m_n = bin610["menu_n"].sum()
                        o_n = bin610["order_n"].sum()
                        m_pct = (bin610["menu_count"].sum() / m_n * 100) if m_n > 0 else 0.0
                        o_pct = (bin610["order_count"].sum() / o_n * 100) if o_n > 0 else 0.0
                        drift610 = o_pct - m_pct
                    else:
                        drift610 = 0.0

                ranks_df = f_df[f_df["rank"].between(1, 5)] if (is_enterprise_bing or is_personal_bing_top5) else f_df[f_df["rank"].between(1, 10)]
                total_order = ranks_df["order_n"].sum()
                weighted = ((ranks_df["drift_pp"] * ranks_df["order_n"]).sum() / total_order) if total_order > 0 else 0.0

                table.append({
                    "feature": feat_name,
                    "top_1_5_drift_pp": round(float(drift15), 4),
                    "bot_6_10_drift_pp": (None if drift610 is None else round(float(drift610), 4)),
                    "weighted_avg_drift_pp": round(float(weighted), 4),
                })

            out["tables"][ctype][study_label] = table

            # Sample sizes for context
            top_menu_n, top_order_n = _rank_sample_sizes(df, 1, 5)
            bot_menu_n, bot_order_n = _rank_sample_sizes(df, 6, 10)
            w_menu_n, w_order_n = (top_menu_n, top_order_n) if (is_enterprise_bing or is_personal_bing_top5) else (top_menu_n + bot_menu_n, top_order_n + bot_order_n)
            out["sample_sizes"][ctype][study_label] = {
                "top_1_5": {"menu_n": top_menu_n, "order_n": top_order_n},
                "bot_6_10": (None if (is_enterprise_bing or is_personal_bing_top5) else {"menu_n": bot_menu_n, "order_n": bot_order_n}),
                "weighted_window": {"menu_n": w_menu_n, "order_n": w_order_n},
            }

            # Add categorical drift summaries (Tone + Content format)
            def _weighted_by_order_n(sub_df):
                total_order = sub_df["order_n"].sum()
                if total_order <= 0:
                    return 0.0
                return float((sub_df["drift_pp"] * sub_df["order_n"]).sum() / total_order)

            cats_out = {}
            for cat_prefix in ("tone:", "content_format:"):
                cat_df = df[df["feature"].astype(str).str.startswith(cat_prefix)].copy()
                # Restrict ranks according to study
                if is_enterprise_bing or is_personal_bing_top5:
                    cat_df = cat_df[cat_df["rank"].between(1, 5)]
                else:
                    cat_df = cat_df[cat_df["rank"].between(1, 10)]
                if cat_df.empty:
                    cats_out[cat_prefix.rstrip(":")] = {"top_positive": [], "top_negative": []}
                    continue

                # Compute weighted drift per categorical value
                rows = []
                for key, g in cat_df.groupby("feature"):
                    w = _weighted_by_order_n(g)
                    val = str(key).split(":", 1)[1] if ":" in str(key) else str(key)
                    rows.append({"value": val, "weighted_avg_drift_pp": round(w, 4)})

                rows_sorted = sorted(rows, key=lambda x: x["weighted_avg_drift_pp"], reverse=True)
                top_pos = [r for r in rows_sorted if r["weighted_avg_drift_pp"] > 0][:8]
                top_neg = [r for r in reversed(rows_sorted) if r["weighted_avg_drift_pp"] < 0][:8]
                cats_out[cat_prefix.rstrip(":")] = {"top_positive": top_pos, "top_negative": top_neg}

            out["categoricals"][ctype][study_label] = cats_out

    os.makedirs("data/enrichment", exist_ok=True)
    with open("data/enrichment/drift_split_tables.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)


listicle_report = generate_report("_listicle", "LISTICLES ONLY")
product_report = generate_report("_product_page", "PRODUCT PAGES ONLY")
build_drift_json()

with open("data/enrichment/listicle_drift_report.txt", "w", encoding="utf-8") as f:
    f.write(listicle_report)
with open("data/enrichment/product_page_drift_report.txt", "w", encoding="utf-8") as f:
    f.write(product_report)

print("Wrote data/enrichment/listicle_drift_report.txt")
print("Wrote data/enrichment/product_page_drift_report.txt")
print("Wrote data/enrichment/drift_split_tables.json")
