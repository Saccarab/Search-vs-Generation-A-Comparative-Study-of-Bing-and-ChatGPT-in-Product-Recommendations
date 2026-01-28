# Analysis Methodology Notes

This document captures all analysis approaches, metrics, and research questions discussed for the Gemini/ChatGPT grounding study. Use this as a checklist when all data is ready.

---

## 1. Grounding Budget Analysis (Dejan Validation)

### Goal
Validate Dejan AI's finding that there's a **~2,000 word budget** per query.

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
- Gemini: **0% rejection rate** (all groundingChunks appear in groundingSupports)
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

---

*Last updated: January 28, 2026*
