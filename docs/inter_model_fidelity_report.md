# Inter-Model Agreement & Data Fidelity Report
**Date:** February 5, 2026
**Models Compared:** Gemini 2.5 Flash vs. GPT-5 mini (Control)
**Dataset Size:** 2,660 overlapping URLs

## 1. Executive Summary
The Content DNA labeling system demonstrates **exceptionally high fidelity** for structural and categorical parameters. While subjective quality scores show expected "model personality" shifts, the **underlying trends are highly consistent (r=0.84 for Freshness)**, proving that the dataset is robust and model-agnostic for core research findings.

---

## 2. Structural Fidelity (Hard Facts)
Parameters with binary or objective definitions show near-perfect agreement between model families. This validates the reliability of the extraction pipeline.

| Parameter | Agreement % | Verdict |
| :--- | :--- | :--- |
| **has_pros_cons** | 94.6% | Near Perfect |
| **has_sources_or_citations** | 93.8% | Near Perfect |
| **has_clear_authorship** | 93.3% | Near Perfect |
| **has_tables** | 92.9% | Near Perfect |
| **has_numbered_lists** | 91.1% | Near Perfect |

---

## 3. Categorical Fidelity (Classification)
Agreement on page "Type" and "Format" is high, confirming that the classification taxonomy is objective and well-understood by different LLMs.

| Parameter | Agreement % | Verdict |
| :--- | :--- | :--- |
| **content_format** | 92.1% | Excellent |
| **readability_score** | 89.1% | Excellent |
| **type** | 87.7% | Excellent |
| **tone** | 77.7% | Good |

---

## 4. Subjective Metric Analysis (Trend vs. Threshold)
Subjective scores show divergence in absolute values but maintain strong relative consistency.

### Correlation Analysis (Pearson r)
| Metric | Correlation (r) | Avg Diff (Gemini - GPT) | Trend Verdict |
| :--- | :--- | :--- | :--- |
| **Freshness** | **0.841** | **+0.47** | **Strong Trend** |
| **Expertise** | **0.505** | **+0.55** | **Moderate Trend** |
| **Spamminess** | **0.367** | **-0.93** | **Weak Trend** |

### Key Findings:
1. **The "Optimism Bias"**: Gemini 2.5 Flash is consistently ~0.5 points more "optimistic" than GPT-5 mini regarding **Freshness** and **Expertise**. 
2. **The "Grumpy GPT" Effect**: GPT-5 mini is significantly harsher on **Spamminess**, scoring it nearly 1 full point higher (worse) than Gemini on average.
3. **Threshold vs. Randomness**: The high correlation in Freshness (`r=0.84`) proves the models aren't guessing; they see the same signals but apply different scoring thresholds. This allows for reliable relative comparisons (e.g., "Source A is fresher than Source B").

---

## 5. Methodology Notes
- **Prompt Parity**: Agreement increased by ~5% when moving from the "Big Prompt" (with product extraction) to the "DNA-Only Prompt."
- **Placeholder Fix**: Early Feb 5 data showed a hallucination bias due to a script bug; this was resolved and the comparison above uses corrected data.
- **2026 Parameter**: The addition of the binary `is_current_year_2026` field provides a hard factual anchor to supplement the subjective `freshness_cue_strength` score.
