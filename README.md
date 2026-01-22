# Search vs Generation: A Comparative Study of Bing and ChatGPT in Product Recommendations

This repository contains the data collection and analysis pipeline for comparing how ChatGPT cites sources versus traditional Bing search results (AI SEO / GEO analysis).

## Overview

The pipeline collects:
1. **ChatGPT responses** with cited sources and recommended items
2. **Bing SERP results** for the same (rewritten) queries
3. **Full page content** from both sources
4. **LLM-based labels** (type, listicle analysis, etc.) via Gemini

All data is stored in `geo_updated.xlsx` with linked content files on disk.

---

## Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA COLLECTION FLOW                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. ChatGPT Scraping (manual)                                               │
│     └─> chatgpt_results_*.csv                                               │
│                                                                              │
│  2. Generate Bing Input                                                      │
│     └─> input_from_chatgpt_*.csv (run_id + query)                           │
│                                                                              │
│  3. Bing SERP Scraping (extension)                                          │
│     └─> bing_results_*.csv (raw)                                            │
│                                                                              │
│  4. Clean Bing Export                                                        │
│     └─> bing_results_cleaned_*.csv                                          │
│                                                                              │
│  5. Ingest to Excel                                                          │
│     └─> geo_updated.xlsx (runs, citations, bing_results, urls sheets)       │
│                                                                              │
│  6. Content Extraction                                                       │
│     ├─> Node.js fetcher (for most URLs)                                     │
│     └─> Browser extension (for Cloudflare-protected sites)                  │
│         └─> thesis/content/*.txt + *.meta.json                              │
│                                                                              │
│  7. Gemini Labeling                                                          │
│     └─> geo_updated.xlsx (urls.type, listicles, listicle_products)          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Instructions

### Prerequisites

```bash
# Install Node.js dependencies
npm install

# Set Gemini API key (for labeling step)
export GEMINI_API_KEY="your-api-key"
```

---

### Step 1: ChatGPT Response Collection

Manually collect ChatGPT responses for your prompts. Export to CSV with columns:
- `prompt_id`, `run_number`, `generated_search_query`, `web_search_triggered`
- `sources_cited_json`, `sources_additional_json`, `items_json`, `response_text`

Output: `data/chatgpt_results_*.csv`

---

### Step 2: Generate Bing Input CSV

Extract rewritten queries from ChatGPT export for Bing scraping:

```bash
# Creates a CSV with run_id and query columns
python scripts/generate_bing_input_from_chatgpt.py \
  --input data/chatgpt_results_*.csv \
  --output tools/Bing\ Results\ Scraper/input_from_chatgpt.csv
```

---

### Step 3: Bing SERP Scraping

Use the **Bing Results Scraper** Chrome extension:

1. Load extension from `tools/Bing Results Scraper/`
2. Open extension side panel
3. Upload the input CSV (with `run_id` + `query` columns)
4. Configure settings:
   - Results per query: 30
   - Delay between queries: 2000-3000ms
5. Click **Start** and wait for completion
6. Download the exported CSV

Output: `data/bing_results_*.csv`

#### Targeted Top-100 scrape (for “missing” citation diagnosis)
If you want to test whether “not in Bing Top-30” citations are truly absent vs just ranked 31–100,
you can scrape **Top-100 only for a small subset of runs** (e.g., prompt_ids P0003/P0004 where Capterra was inline-cited).

1. Export a subset input CSV from the workbook:

```bash
python scripts/metrics/export_bing_input_subset_from_geo_xlsx.py \
  --xlsx geo_final.xlsx \
  --out data/ingest/bing_input_subset_P0003_P0004.csv \
  --prompt-ids P0003,P0004
```

2. In the Bing scraper extension, set **Results per query = 100**, upload that subset CSV, scrape, and export CSV.
3. Clean with `--top-n 100`, then ingest into a *copy* of the workbook (recommended):
   - This lets you recompute overlap against Top-100 without overwriting your original Top-30 run.
4. Recompute citation metrics with Top-100 buckets (example):

```bash
python scripts/metrics/compute_citation_metrics.py \
  --xlsx geo_final_top100_subset.xlsx \
  --out-dir data/metrics \
  --prefix geo_final_top100_subset \
  --buckets 1,3,5,10,30,100
```

Interpretation:
- If a URL is **missing in Top-30 but present in Top-100**, it suggests “rank cutoff” rather than a different source.
- If it is **missing even in Top-100**, it strengthens the claim that the citation is not explained by the observed Bing SERP (at that locale/time).

---

### Step 4: Clean Bing Export

Clean and normalize the Bing results:

```bash
python scripts/clean_bing_export.py \
  --input "C:\Users\User\Downloads\bing_results_*.csv" \
  --output data/bing_results_cleaned_*.csv \
  --top-n 30
```

This script:
- Decodes `bing.com/ck/a` redirect URLs
- Removes duplicate URLs per query
- Filters out ad-click URLs (DoubleClick, Google Ads, Bing aclick)
- Re-numbers positions 1-30
- Normalizes URLs

---

### Step 5: Ingest to Excel

Ingest ChatGPT and Bing data into the master workbook:

```bash
python scripts/ingest/ingest_pilot_to_geo_xlsx.py \
  --chatgpt data/chatgpt_results_*.csv \
  --bing data/bing_results_cleaned_*.csv \
  --xlsx geo_updated.xlsx
```

This populates:
- `runs` sheet (run metadata)
- `citations` sheet (ChatGPT cited sources with item-level details)
- `bing_results` sheet (SERP results)
- `urls` sheet (deduplicated URL registry)

---

### Step 6: Content Extraction

#### Option A: Node.js Fetcher (for most URLs)

```bash
node scripts/ingest/fetch_urls_to_thesis_node.js \
  --xlsx geo_updated.xlsx \
  --content-root "C:\Users\User\Documents\thesis\node_content" \
  --run-label "node_fetch_YYYY-MM-DD" \
  --concurrency 3 \
  --min-time-ms 400 \
  --timeout-ms 45000
```

This:
- Fetches HTML from each URL
- Extracts clean text (removes scripts, styles, nav, ads, etc.)
- Extracts metadata (title, description, dates, schema markup)
- Writes `.txt` content files and `.meta.json` sidecars
- Updates `urls` sheet with `content_path`, `content_word_count`, etc.

#### Option B: Browser Extension (for Cloudflare-protected sites)

For sites that block programmatic requests (403/429), use the **URL Content Fetcher** extension:

1. Load extension from `tools/URL Content Fetcher/`
2. Export missing URLs:
   ```bash
   node scripts/ingest/export_urls_missing_content_csv.js \
     --xlsx geo_updated.xlsx \
     --missing-content-only \
     --out data/ingest/urls_missing_content.csv
   ```
3. Open extension side panel
4. Upload the CSV
5. Enable **"Browser fallback for blocked pages"** (opens real tabs to bypass Cloudflare)
6. Click **Start** — watch tabs open and close as it fetches
7. Download the exported CSV
8. Ingest:
   ```bash
   node scripts/ingest/ingest_url_content_fetcher_export_to_geo_xlsx.js \
     --overwrite \
     --xlsx geo_updated.xlsx \
     --csv "C:\Users\User\Downloads\url_content_*.csv" \
     --content-root "C:\Users\User\Documents\thesis\url_content_fetcher" \
     --run-label "url_content_YYYY-MM-DD"
   ```

---

### Step 7: Gemini Labeling

Label URLs with type, listicle analysis, and product extraction:

```bash
node scripts/llm/enrich_geo_urls_with_gemini.js \
  --xlsx geo_updated.xlsx \
  --save-every 1 \
  --allow-no-content  # for URLs where content fetch failed
```

Environment variables:
- `GEMINI_API_KEY` (required)
- `CONCURRENCY` (default: 5)
- `MIN_TIME_MS` (default: 200)
- `JOB_EXPIRATION_MS` (optional, max time per URL)

This populates:
- `urls.type` (listicle, product, blog, reference, etc.)
- `urls.content_format`, `urls.tone`, `urls.promotional_intensity_score`
- `listicles` sheet (for listicle URLs)
- `listicle_products` sheet (products mentioned in listicles)

### Alternative Step 7 (OpenAI GPT labeling)

If you choose to label pages using **OpenAI GPT models** (e.g. **GPT‑5 mini**) instead of Gemini, use:

```bash
export OPEN_AI_KEY="your-openai-key"
export OPENAI_MODEL="gpt-5-mini"   # override as needed

node scripts/llm/enrich_geo_urls_with_gpt.js \
  --xlsx geo_updated.xlsx \
  --save-every 1 \
  --allow-no-content
```

**Research transparency requirement**: If you run this GPT script, explicitly state in your thesis/methods section that labeling was performed with **OpenAI GPT** (not Gemini). The script writes an audit log to `data/llm/page_labels_gpt.jsonl`.

---

## Excel Schema (`geo_updated.xlsx`)

### `runs` Sheet
| Column | Description |
|--------|-------------|
| run_id | Unique run identifier (e.g., P0001_r1) |
| prompt_id | Prompt identifier |
| run_number | Run number (1, 2, 3) |
| generated_search_query | ChatGPT's rewritten query |
| web_search_triggered | Whether web search was used |

### `citations` Sheet
| Column | Description |
|--------|-------------|
| run_id | Foreign key to runs |
| url | Cited URL |
| citation_type | "sources_cited", "sources_additional", or "inline" |
| cite_position | Position in sources panel (1-indexed) |
| item_section_title | Section title for inline citations |
| item_position | Item position within section |
| item_name | Product/item name |
| item_text | Description text |
| citation_group_size | Number of citations for this item |
| citation_in_group_rank | Rank within citation group |

### `bing_results` Sheet
| Column | Description |
|--------|-------------|
| run_id | Foreign key to runs |
| position | SERP position (1-30) |
| page_num | Bing results page number |
| title | Result title |
| url | Result URL |
| display_url | Display URL shown on SERP |
| snippet | Result snippet |
| domain | Extracted domain |

### `urls` Sheet
| Column | Description |
|--------|-------------|
| url | Normalized URL (primary key) |
| domain | Extracted domain |
| content_path | Path to .txt content file |
| meta_path | Path to .meta.json file |
| content_word_count | Word count of extracted content |
| has_schema_markup | Boolean |
| fetched_at | Timestamp of content fetch |
| page_title | Extracted page title |
| meta_description | Meta description |
| canonical_url | Canonical URL |
| published_date | Publication date |
| modified_date | Last modified date |
| type | Gemini label (listicle, product, blog, etc.) |
| content_format | Gemini label |
| tone | Gemini label |
| promotional_intensity_score | 0-10 score |

### `listicles` Sheet
| Column | Description |
|--------|-------------|
| url | Foreign key to urls |
| listicle_title | Title of the listicle |
| items_count | Number of products listed |
| freshness_cue_strength | 0-10 score |

### `listicle_products` Sheet
| Column | Description |
|--------|-------------|
| listicle_url | Foreign key to listicles/urls |
| position_in_listicle | Position in the list |
| product_name | Product name |
| product_url | Link to product (if available) |

---

## Utility Scripts

### Validation
```bash
python scripts/validate_iteration.py --xlsx geo_updated.xlsx
```

### Export URLs Missing Content
```bash
node scripts/ingest/export_urls_missing_content_csv.js \
  --xlsx geo_updated.xlsx \
  --missing-any \
  --out data/ingest/urls_missing_any.csv
```

### Compute Overlap Metrics
```bash
python scripts/metrics/compute_serp_overlap.py \
  --xlsx geo_updated.xlsx \
  --output data/metrics/overlap_results.csv
```

### Compute Citation Metrics (Inline + Marginal Gain)
This script produces the “extra” citation-focused metrics that are feasible from the workbook alone (no re-scraping needed):
- **Inline / cited / additional** overlap vs Bing Top-\(k\) (k ∈ {1,3,5,10,30})
- **Rank-bucket distribution** of citations (1, 2–3, 4–5, 6–10, 11–30, not-in-Top30)
- **Duplicate vs unique** citation counts (rows vs unique URLs/domains)
- **Not-in-Top30 breakdowns** (top domains, `urls.type` distribution)
- **Marginal gain** of “additional” (and “cited”) sources beyond inline, restricted to Bing Top-30

Run:

```bash
python scripts/metrics/compute_citation_metrics.py --xlsx geo_final.xlsx --out-dir data/metrics --prefix geo_final
```

Outputs (under `data/metrics/`):
- `geo_final_citation_counts_by_run.csv`
- `geo_final_citation_overlap_by_run.csv`
- `geo_final_citation_rank_bucket_summary.csv`
- `geo_final_citation_not_in_top30_top_domains.csv`
- `geo_final_citation_not_in_top30_type_breakdown.csv`
- `geo_final_citation_marginal_gain_top30_by_run.csv`
- `geo_final_citation_overall_summary.csv`

### Patch Wikipedia URLs to `type: reference`
```bash
node scripts/ingest/patch_wikipedia_reference_type.js --xlsx geo_updated.xlsx
```

### Remove Ad-Click URLs
```bash
node scripts/ingest/remove_ad_click_rows_from_geo_xlsx.js --xlsx geo_updated.xlsx
```

---

## Chrome Extensions

### Bing Results Scraper (`tools/Bing Results Scraper/`)
- Scrapes Bing SERP for a list of queries
- Extracts: position, title, URL, snippet, page number
- Filters out ad-click redirects
- Exports to CSV

### URL Content Fetcher (`tools/URL Content Fetcher/`)
- Fetches content from a list of URLs
- **Browser fallback mode**: Opens real tabs to bypass Cloudflare/DDoS protection
- Extracts: clean text, metadata (title, description, dates, schema)
- Exports to CSV for ingestion

---

## Troubleshooting

### Cloudflare/403 Blocked Sites
Use the URL Content Fetcher extension with **browser fallback** enabled. This opens actual browser tabs that can complete Cloudflare challenges.

### Gemini Timeouts
- Reduce `CONCURRENCY` to 1-2
- Set `JOB_EXPIRATION_MS=180000` (3 minutes per URL)
- Use `--save-every 1` to checkpoint after each URL

### Dead/Unavailable Sites
Some URLs may be permanently unavailable. Use `--allow-no-content` flag with Gemini to label them based on available metadata, or accept them as data quality findings.

### Duplicate URLs in Excel
Run the cleanup script:
```bash
python scripts/ingest/cleanup_geo_urls_redirects_and_dups.py --xlsx geo_updated.xlsx
```

---

## File Structure

```
├── data/
│   ├── chatgpt_results_*.csv          # Raw ChatGPT exports
│   ├── bing_results_cleaned_*.csv     # Cleaned Bing exports
│   ├── ingest/                        # Intermediate CSVs
│   └── llm/
│       └── page_labels_gemini.jsonl   # Gemini labeling log
├── geo_updated.xlsx                   # Master data workbook
├── prompts/
│   └── page_label_prompt_v1.txt       # Gemini prompt template
├── scripts/
│   ├── clean_bing_export.py
│   ├── ingest/
│   │   ├── ingest_pilot_to_geo_xlsx.py
│   │   ├── fetch_urls_to_thesis_node.js
│   │   ├── ingest_url_content_fetcher_export_to_geo_xlsx.js
│   │   └── export_urls_missing_content_csv.js
│   ├── llm/
│   │   ├── enrich_geo_urls_with_gemini.js
│   │   └── enrich_geo_urls_with_gpt.js
│   └── metrics/
│       └── compute_serp_overlap.py
├── tools/
│   ├── Bing Results Scraper/          # Chrome extension
│   └── URL Content Fetcher/           # Chrome extension
└── thesis/                            # Content storage (gitignored)
    ├── node_content/
    └── url_content_fetcher/
```

---

## License

This project is for academic research purposes.
