# Analysis Methodology Notes

This document captures all analysis approaches, metrics, and research questions discussed for the Gemini/ChatGPT grounding study. Use this as a checklist when all data is ready.

---

## 1. Grounding Budget Analysis (Dejan Validation)

### Goal
Validate Dejan AI's finding that there's a **~2,000 word budget** per query.

### Critical constraint (what we can and cannot validate)
In our current Gemini dataset, `groundingMetadata.groundingSupports.segment.text` is **output text spans** that Gemini chose to attribute/cite in the final answer.
That is **not guaranteed to equal** the *retrieved / injected* context text Dejan measures in Google AI Mode.

So with Gemini API-style `groundingMetadata` alone, we should treat this as an **output-side proxy budget** (how much of the answer is citation-attributed),
unless we separately log the retriever payload (e.g., via Vertex AI Search over an indexed corpus, or a DIY “search → fetch → inject” pipeline).

### Methodology
```javascript
// For each Gemini response (run):
runBudget = sum(groundingSupports.segment.text.length)

// Across all runs:
averageBudget = mean(allRunBudgets)
medianBudget = median(allRunBudgets)
p25, p75, p95 = percentiles(allRunBudgets)
```

### Expected Findings
- Dejan found: median ~1,929 words, p95 ~2,798 words
- Compare our numbers to validate or challenge this

### Key Question
> "Is the grounding budget consistent across query types, or does it vary by complexity?"

---

## 2. Budget Share Analysis (Per URL)

### Goal
Determine how the fixed budget is **distributed** among sources.

### Note
This is a clean analysis **only** when the underlying “budget” is truly input-side (retrieved/injected text).
If we use `groundingSupports.segment.text` as the numerator/denominator, we’re measuring **output-side attribution share**, which is still useful but should be labeled accordingly.

### Methodology
```javascript
// For each URL in a run:
urlShare = urlGroundingChars / runTotalGroundingChars * 100

// Dejan's findings for reference:
// Rank #1: 28% share (531 words)
// Rank #2: 23% share (433 words)
// Rank #3: 20% share (378 words)
// Rank #4: 17% share (330 words)
// Rank #5: 13% share (266 words)
```

### Key Questions
1. Does our data match Dejan's rank distribution?
2. Do certain content types (listicles, product pages) get larger shares?
3. Is there correlation between Google SERP rank and grounding share?

---

## 3. Source Coverage / Extraction Efficiency

### Goal
Measure what % of a source page gets used in grounding.

### Note
True “coverage” requires the actual retrieved/extracted snippet text (or injected chunks) per URL.
If we only have the final answer + citations, we can still do coverage-style analysis, but it becomes a **claim→page** verification task (Section 17) rather than a direct retriever-coverage measurement.

### Methodology
```javascript
// For each URL:
coverage = groundingCharsFromUrl / totalPageChars * 100
```

### Dejan's Findings (Benchmark)
| Page Size | Avg Grounding | Coverage |
|-----------|---------------|----------|
| <1K words | 370 words | **61%** |
| 1-2K | 492 words | 35% |
| 2-3K | 532 words | 22% |
| 3K+ | 544 words | **13%** |

### Key Insight
> "Density beats length" - Short, focused pages get higher coverage %

---

## 4. Semantic Footprint Matching (Unified Judge)

### Goal
Verify that grounded text **actually exists** in the source page.

### Two-Stage Approach

#### Stage 1: DNA Enrichment (No Thinking)
- Model: `gemini-2.5-flash-preview`
- One call per unique URL
- Output schema:
```json
{
  "page_type": "listicle | product_page | review | forum | news",
  "tone": "promotional | informational | neutral | salesy",
  "structure": "table | numbered_list | bullet_list | paragraphs | mixed",
  "has_pros_cons": true/false,
  "has_pricing_info": true/false,
  "has_author_byline": true/false
}
```

#### Stage 2: Semantic Audit (With Thinking)
- Model: `gemini-2.5-flash-preview` with `thinkingBudget: 2048`
- One call per (URL + claims)
- Output schema:
```json
{
  "verifications": [
    {
      "claim_index": 1,
      "is_supported": true/false,
      "source_footprint": "exact text from source",
      "confidence": 0-100
    }
  ]
}
```

### Key Metrics
1. **Match Rate**: % of claims that are `is_supported: true`
2. **Hallucination Rate**: % of claims that are `is_supported: false`
3. **Average Confidence**: Mean confidence score across all matches

---

## 5. Content DNA Correlation Analysis

### Goal
Determine if certain content characteristics predict higher grounding success.

### Research Questions
1. Do **listicles** get higher budget share than **reviews**?
2. Do pages with **tables** outperform pages with **paragraphs**?
3. Does **informational tone** beat **promotional tone**?
4. Do pages with **pros/cons sections** have higher survival rate?

### Analysis
```javascript
// Group URLs by DNA characteristics
// Compare average budget share across groups
avgShareByType = {
  "listicle": mean(shares where type == "listicle"),
  "product_page": mean(shares where type == "product_page"),
  "review": mean(shares where type == "review"),
  // ...
}
```

---

## 6. SERP Rank vs. Grounding Rank Analysis

### Goal
Determine if Google's ranking correlates with Gemini's grounding priority.

### Methodology
```javascript
// For each grounded URL:
// - Find its position in Google SERP (from fan-out query results)
// - Find its budget share in Gemini response
// - Calculate correlation
```

### Key Questions
1. Does Google #1 = Grounding #1?
2. What's the **survival rate** by SERP position?
3. Are there cases where SERP #10 gets more grounding share than SERP #1?

---

## 7. Listicle Influence Analysis (ChatGPT Focus)

### Goal
Determine if ChatGPT **copies** listicle opinions or **synthesizes** independently.

### Specific Analysis: Dual-Citation Cases
Find cases where ChatGPT cites BOTH:
- A listicle (e.g., "Top 10 TTS Tools")
- A product's own website (e.g., elevenlabs.com)

### Comparison
```
Listicle says: "ElevenLabs supports 29 languages"
Product site says: "32 language support"
ChatGPT says: ???

If ChatGPT says "29 languages" → Copied from listicle
If ChatGPT says "32 languages" → Verified with product site
```

### Key Questions
1. In dual-citation cases, which source does the text match?
2. Does ChatGPT inherit **position bias** from listicles (always recommend #1)?
3. Does ChatGPT inherit **self-promotion bias** (when listicle ranks its own product #1)?

---

## 8. Cross-Platform Comparison (ChatGPT vs. Gemini)

### Goal
Compare grounding behaviors between platforms.

### Metrics to Compare
| Metric | ChatGPT | Gemini |
|--------|---------|--------|
| Average budget per response | ? | ? |
| Number of sources per response | ? | ? |
| Budget share distribution | ? | ? |
| Listicle vs. product page preference | ? | ? |
| Rejection rate (sources retrieved but not cited) | ? | ? |

### Key Insight from Existing Data
- Gemini: **Pilot hypothesis to verify** — in some collected examples, `groundingChunks` appear heavily “pre-filtered”, and many chunks are referenced by `groundingSupports`. We must compute the true rejection rate by checking whether each chunk index is referenced by any support.
- ChatGPT: Has `sources_all` vs `sources_cited` → measurable rejection rate

---

## 9. Model Configuration for Data Collection

### Rationale
Use models that match **real user experience** for data collection.

| Task | Model | Thinking | Rationale |
|------|-------|----------|-----------|
| **Gemini Data Collection** | `gemini-3-flash-preview` | Yes (default) | Matches Gemini UI default |
| **DNA Enrichment** | `gemini-2.5-flash-preview` | No | Simple classification |
| **Semantic Audit** | `gemini-2.5-flash-preview` | Yes (budget: 2048) | Precision matching |

### Why Not Non-Thinking for Data Collection?
- Real users get thinking-enabled responses from Gemini UI
- Thinking models generate more fan-out queries (more thorough)
- Non-thinking would not represent actual user experience

---

## 10. Budget Share Matrix (Advanced Analysis)

### The 2x2 Matrix

```
                    Low Source Coverage    High Source Coverage
                  ┌─────────────────────┬─────────────────────┐
High Budget Share │  "Dense Winner"     │  "Comprehensive"    │
                  │  (efficient, high   │  (lots of facts,    │
                  │   signal per word)  │   heavily used)     │
                  ├─────────────────────┼─────────────────────┤
Low Budget Share  │  "Barely Relevant"  │  "Bloated Loser"    │
                  │  (one small fact)   │  (lots read, little │
                  │                     │   used = low signal)│
                  └─────────────────────┴─────────────────────┘
```

### Goal
Categorize sources and correlate with Content DNA.

---

## 11. Key Thesis Claims to Validate

### From Dejan AI
- [ ] ~2,000 word budget per query
- [ ] Rank #1 gets 2x share vs Rank #5
- [ ] Coverage drops as page size increases
- [ ] "Density beats length"

### Original Research Questions
- [ ] What Content DNA predicts grounding success?
- [ ] Do listicles dominate AI recommendations?
- [ ] Is there measurable "AI Search Filter" (rejection rate)?
- [ ] How do ChatGPT and Gemini differ in grounding behavior?

---

## 12. Data Files Reference

### Gemini Pipeline
- Raw responses: `data/gemini_raw_responses/`
- Resolved URLs: `data/resolved_grounding_urls.json`
- Master content: `data/ingest/gemini_urls_master.json`
- Content text: `data/ingest/content/`
- SERP results: `data/serpapi_results/`

### Analysis Outputs
- DNA results: `data/llm/page_dna_results.json`
- Audit results: `data/llm/semantic_audit_results.json`
- Budget analysis: `data/llm/budget_analysis.json` (to create)

### Scripts
- Unified Judge: `scripts/llm/run_unified_judge_vertex.js`
- Budget Analysis: (to create)
- Listicle Comparison: (to create)

---

## 13. Statistical Considerations

### Sample Size
- Dejan: 7,060 queries, 2,275 pages
- Our pilot: ~12 runs (P004-P007 × 3)
- Full run: 240 runs (80 prompts × 3)

### Variance Reporting
Always report:
- Mean / Median
- Standard Deviation
- Percentiles (p25, p50, p75, p95)
- Confidence intervals where appropriate

### Limitations to Acknowledge
1. We measure **output citations**, not internal context
2. Semantic matching via LLM is interpretive, not exact
3. Product recommendation vertical may not generalize to all query types

---

## 14. ChatGPT Search Engine Theory (Google vs. Bing)

### Hypothesis
Despite the Microsoft partnership, ChatGPT may be using **Google** (via SerpApi or similar) rather than **Bing** for its web searches.

### Test Methodology
For each ChatGPT citation:
1. Check if URL exists in **Bing Top 30** (or Deep Hunt Top 150)
2. Check if URL exists in **Google Top 20**
3. Calculate overlap percentages

```javascript
// For all ChatGPT citations:
bingOverlap = citationsFoundInBing / totalCitations * 100
googleOverlap = citationsFoundInGoogle / totalCitations * 100
```

### Interpretation
| Result | Implication |
|--------|-------------|
| Bing Overlap >> Google Overlap | ChatGPT uses Bing (expected) |
| Google Overlap >> Bing Overlap | ChatGPT may use Google (unexpected) |
| Both similar | Inconclusive (SERPs often overlap) |

### Additional Analysis
- Check for **Google-exclusive** citations (in Google Top 20 but NOT in Bing Top 150)
- Check for **Bing-exclusive** citations (in Bing but NOT in Google)
- Look for patterns in which domains appear in one but not the other

### Data Needed
- ChatGPT citations (existing data)
- Bing Deep Hunt results (existing data)
- Google SERP for same queries (need to collect via SerpApi)

### Why This Matters
If ChatGPT uses Google under the hood, it has major implications for:
1. The Microsoft partnership value
2. SEO strategy (optimize for Google, not Bing)
3. The "two-web" theory (maybe there's just one web after all)

---

## 15. Bing Result Volatility / "Disappearing Results" Bug

### Initial Discovery
- **P001_r1 Q1**: Canva appears at **Rank #5** in Bing
- **P001_r3**: Canva is **cited by ChatGPT** but has **NO match in Bing results**
- **Hypothesis**: Bing sometimes returns fewer results on Page 1, and items that "should" be there just disappear instead of getting pushed to Page 2

### Why This Matters
1. **Methodological**: Our "survival rate" calculations might be artificially low because Bing itself is inconsistent
2. **The Page 2 Problem**: This might explain why Page 2 overlap metrics are worse - it's not that ChatGPT ignores Page 2, but that Bing's Page 2 is unreliable
3. **Cross-Run Variance**: Same prompt, different runs = different Bing results = different "match" outcomes

### Test Methodology
```javascript
// For each prompt with 3 runs:
// Compare cited URLs across runs
// Flag cases where a URL is:
//   - Cited in all 3 runs (consistent behavior)
//   - In Bing for Run 1/2 but NOT Run 3 (Bing volatility)
//   - Cited but NEVER in any run's Bing results (truly "invisible")
```

### Questions to Answer
1. **How often does the same URL appear/disappear across runs for identical prompts?**
2. **Is the Bing volatility correlated with page number?** (Higher pages = more volatile?)
3. **Should we use "best of 3 runs" matching instead of per-run matching?**

---

## 16. Freshness Filter Analysis (ChatGPT Date Bias)

### Hypothesis
ChatGPT may apply an internal **freshness filter** that deprioritizes older content, even when it ranks highly on Bing.

### Initial Discovery
- **ODMS Olympus Dictation** was **Bing Rank #1** for query "transcription software one-time payment"
- **ChatGPT did NOT cite it**
- **Reason**: The article is from **December 14, 2021** - 4+ years old

### Test Methodology
```javascript
// For each Bing result that is NOT cited by ChatGPT:
// Check if it has a published_date in our enriched data

uncitedTopBing = bingResults.filter(r => r.position <= 10 && !r.is_cited)
oldUncited = uncitedTopBing.filter(r => r.published_date && r.published_date < "2024-01-01")
freshUncited = uncitedTopBing.filter(r => r.published_date && r.published_date >= "2024-01-01")

// Compare ratios
oldRejectionRate = oldUncited.length / totalOldInTop10
freshRejectionRate = freshUncited.length / totalFreshInTop10
```

### Key Questions
1. **Does ChatGPT systematically reject old content?** (Compare rejection rates)
2. **What is the "freshness cutoff"?** (2 years? 3 years? 5 years?)
3. **Does this vary by query type?** (Product recs may need fresher content than factual queries)

### Expected Findings
- Higher rejection rate for content older than ~2 years
- Product recommendation queries may have stricter freshness requirements
- This would explain some "invisible" citations that rank well on Bing but aren't cited

### Data Needed
- Bing results with `published_date` from enriched CSV
- ChatGPT citations to identify which were rejected
- Query categorization to see if freshness bias varies by topic

### Why This Matters
If ChatGPT has a freshness filter, it means:
1. **SEO date matters** - even good content gets deprioritized if old
2. **"Evergreen" content may underperform** in AI citations
3. **Bing rank alone doesn't predict AI visibility**

## 17. Semantic Coverage & Fidelity Analysis (The "Extractive Proof")

### Goal
Quantify how much of the **cited claim** actually exists in the **source page content** (Semantic Coverage) and how accurately it reflects the source (Fidelity).

### Methodology
For each mapping in `datapass/citation_mappings/`:
1.  **Retrieve Pair**: `claim_text` (what ChatGPT wrote) + `full_page_content` (from our Master Content Library).
2.  **LLM Audit**: Use `gemini-2.5-flash-preview` (with thinking) to perform a semantic lookup.
    - **Prompt**: "Does the following claim [CLAIM] appear semantically in this webpage text [CONTENT]? If yes, provide the exact matching snippet from the source."
3.  **Metrics**:
    - **Semantic Match Rate**: % of claims that can be traced back to the source text.
    - **Extraction Efficiency**: (Character count of `claim_text`) / (Character count of `source_snippet`).
    - **Hallucination Delta**: Identification of facts in the `claim_text` (e.g., a specific price or feature) that are missing from the source.

### Key Research Questions
1.  **Direct vs. Synthesized**: Does ChatGPT quote the source directly, or does it rephrase?
2.  **Listicle Fidelity**: When citing a listicle, does ChatGPT use the listicle's "Notes" or does it hallucinate its own pros/cons?
3.  **The "Plus One" Effect**: In multi-chip citations, does the claim contain facts from *both* sources or just one?

---

## 22. Comparison of Attribution Precision (ChatGPT vs. Gemini)

### Goal
Document the fundamental difference in how ChatGPT and Gemini handle citation indices and what that means for our audit.

### Key Distinction
1.  **ChatGPT (Reference-to-Token)**:
    - **Data Source**: `content_references_json`
    - **Mechanism**: Indices point to the **location of the citation tag** (e.g., the `[1]` or `[URL]` chip) in the response text.
    - **Audit Impact**: We must **infer** the claim boundaries (the "claim text") by looking backward from the index. This introduces a heuristic layer (guessing if it covers one sentence or the whole paragraph).
2.  **Gemini (Segment-to-Chunk)**:
    - **Data Source**: `groundingMetadata.groundingSupports`
    - **Mechanism**: Indices point to the **entire span of the claim** (the "segment").
    - **Audit Impact**: The model explicitly defines the boundaries of its claims. This is a **native attribution** that removes the need for heuristic guessing of what text a citation supports.

### Shared Limitation (The "Dejan" Gap)
Neither model currently returns the **raw source snippet** (the specific text from the webpage that was fed into the prompt). 
- **ChatGPT**: Discards the raw browsing text in the final response.
- **Gemini**: Provides a pointer to a `groundingChunk` (URL), but not the text within that chunk.

### Thesis Conclusion
While Gemini provides a more precise **mapping** of claims to sources, both models remain "black boxes" regarding the **exact input text** they prioritized from those sources. Our methodology must bridge this gap by fetching the full page content and performing semantic overlap checks (Section 17).

---

*Last updated: January 31, 2026*

---

## 18. ChatGPT "Budget" Analysis (Proxy, Not True Context Budget)

### Key Constraint (vs. Gemini / Google AIO)
For Gemini (and Dejan’s Vertex AI Search examples), the system exposes **grounding snippet text** (the “trimmed versions” fed into the model) which enables true analysis of:
- total injected grounding text per run, and
- per-source share of that injected context.

For ChatGPT, our network artifacts expose:
- `search_result_groups_json` (SERP entries + snippets),
- `content_references_json` (token→ref mapping),
- `sources_*` lists,
but **not** the full “grounding context” text actually injected into the model (if any), nor how much was trimmed per source.

So: we *can* do a Dejan-style analysis, but only as a **proxy** based on *output evidence*, not true input budget.

### What We *Can* Measure Reliably (Output-Side Budget)
Define per run:
- **\(B_{out}\)**: total characters (or tokens) in all extracted `claim_text` blocks that are attributed to citations (including multi-chip attribution splits if desired).
- **Per-URL share**: \(share(url) = claimChars(url) / B_{out}\).
- **Cited vs Additional split**: compare allocation across `sources_cited` and `sources_additional`.
- **Multi-chip “synthesis aggression”**: how often one claim block maps to multiple URLs.

This is analogous to “how much of the answer is grounded” rather than “how much context was fed in”.

### What We *Can* Estimate (Input-Side Upper Bounds)
Using `search_result_groups_json.entry.snippet` as a *lower-fidelity proxy* for grounding text:
- **\(B_{snip}\)** = sum of snippet lengths for URLs that were actually used/cited (or for `sources_all`).

This is noisy (snippets ≠ what the model saw), but it gives a comparable scale to Dejan’s “snippet budget” framing.

### What We *Should Not* Claim for ChatGPT
- a fixed “2,000-word grounding budget” like Dejan’s Vertex examples, unless we’re explicit it’s a **proxy** and validated only on snippet/claim lengths.

### Recommended Reporting Language
Use wording like:
- “**Output-side grounding allocation**” (claim text share by URL),
- “**Snippet-level budget proxy**” (SERP snippet totals),
and keep “true grounding budget” reserved for Gemini/Vertex-style exposed chunk text.

---

## 19. Immediate Next Additions (Highest Signal / Feasibility)

### 19.1 Google SERP Control Group (SerpApi)
**High feasibility, high thesis value**:
- Collect Google Top 20/30 for each ChatGPT rewritten query (Q1/Q2).
- Compute: overlap(ChatGPT citations, Google SERP) vs overlap(ChatGPT citations, Bing SERP).
- Identify “Google-only” citations (in Google top results but absent from Bing deep results), a direct test for the “Google Farm” hypothesis.

### 19.2 Page DNA: Why Cited vs Additional vs Ignored
**Feasible once content fetch coverage is good**:
- Run Stage-1 DNA enrichment on all unique URLs in `sources_cited` + `sources_additional` (and optionally top Bing results that were *not* cited).
- Compare feature distributions (tables, pros/cons, bylines, tone) to identify predictors of citation selection.

### 19.3 Claim→Page Semantic Verification (Core “Extractive Proof”)
**Most defensible, but costs more**:
- For each mapping: verify `claim_text` is supported by the fetched page content.

---

## 20. ChatGPT Retrieval Anomalies & "Hallucinated" Queries

### 20.1 Cross-Lingual Fan-out Queries
**Discovery**: In several runs (e.g., P007, P018, P032, P044), ChatGPT generates fan-out queries in foreign languages (Chinese, Japanese, Spanish) even when the user prompt is entirely in English.

**Hypothesis**: This is an intentional retrieval strategy where the model "pivots" to languages it associates with a specific technical domain (e.g., Chinese for real-time translation tech) to find primary sources or diverse perspectives.

**Thesis Value**:
- **Agentic Retrieval**: Demonstrates the LLM acting as a multi-lingual research agent rather than a passive keyword searcher.
- **Invisible Links**: Explains why some citations may appear "out of nowhere" if they were found via a foreign-language search that our Bing/Google English control groups didn't capture.

**Methodology**:
1.  **Identify**: Flag runs where `hidden_queries_json` contains non-English characters or bilingual bridging (e.g., `实时翻译 Zoom Teams translation tools`).
2.  **Correlate**: Check if these queries lead to citations that are absent from English SERPs.
3.  **Contrast**: Compare with Gemini to see if it exhibits similar cross-lingual "pivot" behavior.

---

## 21. Methodological Notes & Validation Plans

### 21.1 LLM Structural Labeling Validation
- **Current Approach**: Structural features (e.g., `has_tables`, `has_numbered_lists`, `has_bullet_points`) are being extracted via LLM (Gemini) using scraped text content.
- **Potential Issue**: Scraped text lacks HTML tags, which may lead to under-reporting of structural elements.
- **Validation Plan**: After the full enrichment run, perform a manual or assisted audit on a small deterministic sample (e.g., 50-100 URLs). Compare LLM labels against original HTML or manual inspection to quantify the error rate for structural features.
- Output match snippets + confidence, then aggregate match rate / hallucination delta.
