# Listicle Analysis Jobs (ChatGPT / Gemini)

This repo uses two complementary listicle analyses:

- **(A) Selection/Omission (Uptake)**: which products from a cited listicle the model actually used vs omitted/invented.
- **(B) Fidelity (Groundedness)**: whether claims attributed to the listicle are supported by the listicle’s text (chunked evidence), including cross-item mixups.

This document explains how to build **LLM-ready job files**. It does not run any LLM calls.

---

## Build jobs for ChatGPT runs

Prereqs:
- `geo_fresh.db` has ChatGPT `runs.response_text` populated (used as `answer_text`).
- `datapass/citation_mappings/*_mapping.json` exists (claim→URL attribution).
- `datapass/page_labels_combined_v2.5.jsonl` exists (listicle roster).
- `datapass/url_content_*.csv` exists (page text for evidence chunks).

Command:

```bash
python scripts/semantic/build_listicle_llm_jobs.py ^
  --account_filter all ^
  --out_dir data/listicle_analysis/jobs_chatgpt
```

Outputs:
- `data/listicle_analysis/jobs_chatgpt/selection_omission_jobs.jsonl`
- `data/listicle_analysis/jobs_chatgpt/fidelity_jobs.jsonl`
- `data/listicle_analysis/jobs_chatgpt/build_stats.json`

Prompts:
- `prompts/listicle_selection_omission_analysis_v1.txt`
- `prompts/listicle_fidelity_verification_chunks_v1.txt`

---

## Notes on dedupe / comparability

- SerpApi paging can include duplicate organic URLs across pages.
- The existing ingest pipeline (`scripts/ingest_google_results.py`) dedupes by:
  - **(chatgpt_run_id, account_type, query, url, result_type)**.
- For listicle analysis jobs, we do **not** dedupe claims; we preserve the mapping-level claim list for the (run_id, listicle_url) pair.

