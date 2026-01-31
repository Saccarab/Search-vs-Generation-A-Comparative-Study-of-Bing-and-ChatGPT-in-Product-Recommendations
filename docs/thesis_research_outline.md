# Thesis Research Outline
## Search vs. Generation: A Comparative Study of Bing and ChatGPT in Product Recommendations

**Author:** [Your Name]  
**Date:** January 2026  
**Status:** Research Notes / Working Draft

---

# Part 1: Methodology & Tools

## 1.1 Data Collection Pipeline

| Component            | Description                                                                      |
| -------------------- | -------------------------------------------------------------------------------- |
| **Queries**          | 80 product recommendation queries × 3 runs each (240 total runs)                 |
| **ChatGPT Data**     | Full responses with inline citations, additional links, and recommended products |
| **Bing Data**        | Top 30 results + Deep Hunt (Rank 31-150)                                         |
| **Gemini Data**      | Full `groundingMetadata` (Chunks vs. Supports) + Fan-out Queries                 |
| **Google SERP**      | Top 20 Organic Results via SerpApi (for Gemini fan-out queries)                  |
| **Content Fetching** | Node.js fetcher + Browser extension for blocked pages (Master Content Library)   |

## 1.2 The Analysis App (Data Viewer)

*Include this as a "Methodology" section—it shows rigor in your research process.*

### What the app does:
- Interactive comparison of ChatGPT/Gemini responses vs. Search results per query/run
- **Gemini Mode:** Visualizes the "Search Filter" by comparing `groundingChunks` (AI Shortlist) vs. `groundingSupports` (Final Citations) vs. `Google SERP` (The Control Group).
- Three viewing modes: Top 30 Only, Deep Hunt Only, Combined (All)
- Visual indicators for Exact URL Match (Yellow) vs. Domain Match (Green)
- Dashboard with aggregate statistics (Overlap %, Invisible Domains, etc.)

### Why it matters for the thesis:
- Enabled manual spot-checking of automated findings
- Revealed the "Pagination Loop" and "Page 2 Cliff" problems in Bing
- Proved the need for Deep Hunt methodology
- **Gemini Insight:** Revealed that Gemini's `groundingChunks` are already pre-filtered (0% rejection rate vs. supports), necessitating a comparison against external SerpApi data to measure the *true* filter.

### 1.2.2 Methodological Evolution: From Top 30 to "Deep Hunt" (Rank 150)
- **Initial Assumption:** Our study began with a standard retrieval depth of the **Top 30 Bing results**, assuming this would capture the vast majority of relevant citations used by ChatGPT.
- **The Discovery of "UI Erasure":** Upon qualitative review using our custom Data Viewer, we observed a significant "Visibility Gap." ChatGPT was citing high-quality, relevant pages that were completely missing from the Top 30 human-facing results.
- **The Pivot to Rank 150:** To test whether these citations were truly "invisible" or merely "buried," we expanded our methodology to a **"Deep Hunt" (Rank 150)**. 
- **Key Finding of the Pivot:** We discovered that Bing often surfaces the exact pages ChatGPT cites, but hides them deep within pagination loops or beyond the "Page 2 Cliff" (Rank 11+). This methodological shift allowed us to prove that the difference between Search and GenAI is often a **UI and Ranking problem**, not just an indexing one.

## 1.3 Localization & Retrieval Environment

*How geographical context affects the comparison between Search and GenAI.*

### 1.3.1 Implicit vs. Explicit Localization
- **Explicit Localization:** When the user query contains a location (e.g., "Best pizza in New York").
- **Implicit Localization:** When the query is general (e.g., "Best laptop"), but the search engine uses the user's IP, browser language, and search history to localize results.
- **The Research Problem:** Traditional search engines (Bing) are aggressively localized. Generative AI (ChatGPT) often provides a more "Global/US-centric" baseline unless explicitly prompted otherwise.

### 1.3.2 The Proxy Requirement (US-Centric Baseline)
- To ensure a fair "apples-to-apples" comparison, we standardized our retrieval environment using a **US-based Proxy**.
- **Why US Proxy?**
  1. **Baseline Consistency:** ChatGPT's primary training data and search behaviors are heavily weighted toward US-English web content.
  2. **Avoiding "Regional Noise":** Prevents Bing from surfacing local retailers or regional blogs that ChatGPT would never see, which would artificially lower the overlap percentage.
  3. **Global Tech Standard:** Most product recommendations in the "AI/Software" category (our primary focus) are global in nature, making the US SERP the most relevant "Ground Truth."

### 1.3.4 The "Invisible" Citation Problem vs. Empirical Evidence
- **The Observation:** A significant portion (~35%) of ChatGPT's citations were not found in the standard Top 30 Bing results.
- **The "Deep Hunt" Resolution:** Our expanded methodology (Rank 150) proved that many of these "invisible" citations are actually present in the Bing index, but buried deep within the SERP (Rank 100+).
- **Key Conclusion:** The "Visibility Gap" is primarily a **retrieval depth and UI issue**. ChatGPT's API access allows it to surface high-quality content that Bing's human-facing UI suppresses or fails to paginate correctly. This reinforces the argument that Search and GenAI are accessing the same index but through different "visibility filters."

## 1.4 Theoretical Framework: From SEO to GEO

*Tracing the evolution of information retrieval from keyword matching to generative synthesis.*

### 1.4.1 The Evolution of Search Optimization
- **Traditional SEO (Search Engine Optimization):** Focus on keyword density, backlink authority, and technical performance to rank in a 10-blue-link UI.
- **The Convergence of AEO & GEO:** These terms are often used interchangeably to describe the shift toward optimizing content for direct synthesis.
    - **AEO (Answer Engine Optimization):** Focuses on being the "single best answer" for voice assistants and featured snippets.
    - **GEO (Generative Engine Optimization):** Focuses on being cited and synthesized by LLMs in conversational RAG (Retrieval-Augmented Generation) workflows.

### 1.4.2 The Genesis and Evolution of RAG (Retrieval-Augmented Generation)
- **The "Stochastic Parrot" Era (Pre-2023):** Early LLMs relied purely on "parametric knowledge"—static information frozen at the time of training. This led to the "hallucination problem" and the "stale data" bottleneck.
- **The Reasoning vs. Knowledge Split:** The industry realized that LLMs are better at **reasoning** (logic, synthesis, formatting) than being a **database**. RAG was developed to decouple these functions.
- **The RAG Workflow:**
    1. **Retrieval:** The model identifies it needs external info and generates a search query.
    2. **Augmentation:** The search results (grounding chunks) are injected into the model's context window.
    3. **Generation:** The model reasons over the provided text to synthesize a factual response.
- **Why RAG became the Standard:**
    - **Factuality:** Provides a "paper trail" (citations) for every claim.
    - **Efficiency:** Small models + RAG often outperform massive models without RAG.
    - **Freshness:** The only way to handle dynamic data (prices, news, product releases).

### 1.4.3 Sam Altman’s "Tiny Model" Vision
- Quoting the framework: *"The perfect AI is a very tiny model with superhuman reasoning... It doesn't need to contain the knowledge - just the ability to think, search, simulate, and solve."*
- **Thesis Connection:** This vision confirms that the future of search is not the death of the web, but the transformation of the web into a **distributed memory layer** for AI orchestrators.

### 1.4.4 The Economic & Technical Necessity of Retrieval
- **The Compute Wall:** Inference (LLM "thinking") is exponentially more expensive than Retrieval (traditional search indexing).
- **The Scaling Limit:** You cannot train a model every hour to keep up with the web. Retrieval is the only scalable solution for real-time information.
- **Thesis Argument:** GEO is not a replacement for SEO; it is **SEO's final form**. Search is the "cheaper, better, faster" engine that feeds the LLM's reasoning core.

### 1.4.5 The Structural Pivot: From "Search" to "Grounding"
- **The August 11, 2025 Retirement:** Microsoft officially decommissioned the legacy Bing Search APIs, forcing a migration to **"Grounding with Bing Search"** as part of the Azure AI Agents ecosystem.
- **Defining "Grounding":** Unlike traditional search ranking (which optimizes for human click-through rates), **Grounding** is the process of anchoring an LLM's response in real-time, verifiable web data to reduce hallucinations and ensure factual accuracy.
- **Retrieval Asymmetry:** This shift codifies the "Two-Web" reality:
    1. **The Human Web (Ranking):** Optimized for SEO, ads, and engagement.
    2. **The Agent Web (Grounding):** Optimized for information density, extraction potential, and factual synthesis.
- **Thesis Connection:** Our discovery that ChatGPT citations are often buried at **Rank 31-150** in the Human Web proves that the "Grounding" engine uses a different set of priorities than the "Ranking" engine.

## 1.5 The Commercial Catalyst for RAG

*Why product recommendations are the "Front Line" of Generative Search.*

### 1.5.1 Search Trigger Rates by Intent
- **The Commercial Dominance:** Research (e.g., Profound, 2026) indicates that **Commercial Queries** trigger a web search in **53.51%** of ChatGPT conversations—nearly 3x the rate of Informational queries (18.73%).
- **The "Winnable" Arena:** Because commercial intent requires real-time data (pricing, availability, reviews), it is the primary driver for RAG adoption. This makes product recommendations the most critical area for studying the shift from SEO to GEO.

### 1.5.2 Selection of the Research Query Set
- **High-Volume Real-World Prompts:** Our dataset consists of **80 unique product recommendation prompts** (e.g., "Best AI video translators", "Top-rated transcription software").
- **Methodology for Selection:**
    - **Keyword Clustering:** Using tools like **Ahrefs** to identify high-intent clusters.
    - **Prompt Volume Analysis:** Leveraging **Profound's** database to select real-world prompts actually used by consumers.
    - **Deliberate Intent Filtering:** From the broad set of available user prompts, we **deliberately filtered for high commercial intent**. This ensures the study reflects the specific segment of search where AI synthesis is most active and where the "Extractive Nature" of the model is most visible.
    - **Domain Expertise:** Queries were focused on the **AI and Software-as-a-Service (SaaS)** sectors—a domain where the author has significant professional expertise—allowing for more nuanced qualitative analysis of the "Signal vs. Noise" in results.
- **Experimental Rigor:** Each of the 80 prompts was executed in **3 independent runs** (with a 4th run added only in cases of technical failure or RAG non-triggering) to analyze the consistency and stochastic nature of the retrieval process.

### 1.5.3 The GEO Industry Landscape
- **The "Gold Rush" of AEO/GEO:** The rapid rise of companies like **Profound** and **Perplexity AI** underscores the industry's recognition that the "Answer Engine" is the next multi-billion dollar shift in tech.
- **Venture Capital Validation:** A landmark moment occurred on August 12, 2025, when **Profound raised $35 million in a Series B round led by Sequoia Capital**, bringing its total funding to $58.5 million ([Fortune, 2025](https://fortune.com/2025/08/12/ai-search-startup-profound-raises-35-million-series-b-sequoia/)).
- **The "Salesforce of AI Search":** This funding round validated the concept of building a "generational company" centered on helping brands monitor and optimize for how they surface in AI-generated responses across models like ChatGPT, Gemini, and Claude.
- **The Hype vs. Reality:** While the hype is centered on "killing search," our research suggests the reality is a **deeper integration** where search becomes the infrastructure for AI.

### 1.4.6 Fan-Out Queries (Hidden Query Sets)
- **Definition (Fan-Out):** A single user prompt can result in **multiple retrieval queries** (parallel or sequential). We treat these as the model’s **fan-out query set** (often UI-hidden).
- **Observed pattern:** Fan-out queries frequently include *operator-like* changes (e.g., adding a year such as "2025/2026", adding geo terms, adding “reviews/pricing/alternatives”), but we do not rely on a separate “rewriting” concept—only on what is observable in logged fan-out queries.
- **The "Query Drift" Problem:** Across multiple runs of the same prompt, the fan-out query set can vary. This drift is a primary driver of stochastic retrieval—different fan-out sets lead to different retrieved sources and therefore different citations/recommendations.

### 1.4.7 Fan-Out Queries (Cross-Model Instrumentation)
- **Why it matters:** Fan-out query sets are a core degree of freedom that controls retrieval. Two systems can share the same index but diverge because they issue different query sets.

#### Observables (what we can actually log)
- **Gemini:** `groundingMetadata.webSearchQueries[]` (fan-out query list per run).
- **ChatGPT (network-derived):** The internal search queries / triggers when present in the response payloads (treated as “hidden queries” even when not UI-visible).
- **Bing baseline:** The original user prompt as a single query, plus (optional) a controlled query-variant policy we apply ourselves (e.g., add year/location) to test sensitivity.

#### Metrics / analyses enabled
- **Fan-out size:** number of fan-out queries per run; distribution by intent class.
- **Query drift:** similarity of fan-out sets across runs (same prompt, different runs) and its correlation with citation churn.
- **Fan-out operators:** frequency of year-injection, geo-injection, brand expansion, “alternatives” expansion, and “review/pricing” pivots (measured directly from the fan-out queries).
- **Attribution to overlap:** whether higher Bing/Google overlap is driven by (a) different fan-out query sets, (b) deeper retrieval, or (c) different citation visibility rules.

## 1.6 Citation Mapping & Claim-Level Attribution
*How we precisely map ChatGPT's written claims to their retrieved sources.*

### 1.6.1 The "Claim-to-Link" Forensic Pipeline
- **The Challenge:** ChatGPT's final response text replaces internal citation tokens with generic `[URL]` tags. To understand *why* a link was cited, we must reconstruct the link between the **written claim** and the **retrieved source**.
- **The Solution:** We developed a forensic mapping script that:
    1. **Token Alignment:** Extracts raw citation tokens (e.g., `citeturn0search17`) from the network stream and aligns them with their final position in the response text.
    2. **Block-Level Extraction:** Instead of simple keyword matching, the script identifies the **Full Claim Block** (the descriptive text between consecutive citation tags). This captures the complete product description or factual statement ChatGPT attributed to that source.
    3. **Metadata Enrichment:** Maps each claim to its retrieved "Ground Truth" (the snippet, title, and URL from the search result groups).

### 1.6.2 Multi-Chip Reconstruction (Synthesis Aggression)
- **Defining Multi-Chips:** We observed cases where ChatGPT groups multiple sources under a single citation (e.g., "Vibe Voice+1"). 
- **Forensic Discovery:** Our mapping revealed that these correspond to concatenated tokens (e.g., `turn0search8` + `search15`).
- **Research Value:** This allows us to measure **Synthesis Aggression**—how ChatGPT merges facts from multiple distinct search results into a single cohesive claim.

---

# Part 2: Core Findings

## 2.1 Citation Overlap Analysis

### 2.1.1 The Numbers

| Metric                                        | Value      |
| --------------------------------------------- | ---------- |
| Total ChatGPT Citations                       | ~6,667     |
| Strict URL Match (Top 30 + Deep Hunt)         | **64.93%** |
| Domain-Only Match (Same site, different page) | 79.20%     |
| "The Gap" (Domain noise)                      | 14.26%     |
| **Truly Invisible (Never found at Rank 150)** | **~35%**   |

### 2.1.2 The "Invisible" Citation Problem

- ~35% of ChatGPT's citations were **never found** in Bing, even searching 150 results deep
- This proves ChatGPT has access to a different index/cache than Bing's public UI
- **Hypothesis:** These are newer pages, niche expert sites, or pages Bing deprioritizes

---

## 2.2 Cited vs. Additional Links Comparison

*Compare why some relevant links were not cited in the main text.*

### Research Questions:

1. **Why were Additional links not cited inline?**
   - Compare structural DNA: `has_tables`, `has_numbered_lists`, `heading_density`
   - Compare `tone`: Are Additional links more `promotional` or `salesy`?
   - Compare `type`: Are Additional links more `product_page` vs. `listicle`?

2. **Cross-Run Citation:**
   - Were Additional links from Run 1 cited inline in Run 2/3/4?
   - This shows consistency vs. randomness in ChatGPT's citation selection

3. **Page 1 Ignored Links:**
   - Links in Bing Page 1 (Rank 1-10) that ChatGPT did NOT cite
   - Compare their DNA to cited links
   - Hypothesis: Ignored links are more `salesy`, lower `expertise_signal_score`

### Data Fields to Compare:

| Field                         | Cited Links | Additional Links | Page 1 Ignored |
| ----------------------------- | ----------- | ---------------- | -------------- |
| `has_tables`                  | ?           | ?                | ?              |
| `has_numbered_lists`          | ?           | ?                | ?              |
| `has_bullet_points`           | ?           | ?                | ?              |
| `heading_density`             | ?           | ?                | ?              |
| `tone`                        | ?           | ?                | ?              |
| `promotional_intensity_score` | ?           | ?                | ?              |
| `expertise_signal_score`      | ?           | ?                | ?              |
| `spamminess_score`            | ?           | ?                | ?              |
| `readability_score`           | ?           | ?                | ?              |
| `type`                        | ?           | ?                | ?              |

---

## 2.3 The "Invisible Section" Finding

*Links that don't fit on Page 1 and then vanish.*

### The "Bing UI Suppression" Argument:

1. **Page 1 Instability:** Sometimes Bing shows 4 results, sometimes 10, sometimes with "infinite scroll" that breaks pagination.
2. **The "Page 2 Cliff":** Relevant results at Rank 11-15 often vanish entirely when you click "Next."
3. **Pagination Loops:** We observed `&first=5` and no parameter returning the same Top 10.

### Proof that ChatGPT Gets These "Hidden" Links:

- X% of ChatGPT citations were found at Rank 11-30 (the "Hidden Page 1" zone)
- These links were **not visible** to a human scrolling through Bing normally
- ChatGPT's API access bypasses the UI limitations

### Type Distribution of Invisible Citations:

| Type                  | Count | % of Invisible |
| --------------------- | ----- | -------------- |
| listicle              | ?     | ?              |
| review_article        | ?     | ?              |
| product_page          | ?     | ?              |
| marketplace_directory | ?     | ?              |
| reference (Wikipedia) | ?     | ?              |
| other                 | ?     | ?              |

---

## 2.4 Rank Distribution Analysis

*Talk about links below 150, show distribution.*

### Histogram: Where ChatGPT Citations Appear in Bing

- X-axis: Bing Rank (1-150+)
- Y-axis: Number of Citations Found

### Expected Findings:

- Peak at Rank 1-5 (some overlap)
- Sharp drop at Rank 10 (the "Page 1 Cliff")
- Flat, uniform distribution from Rank 11-150 ("Linearity Collapse")
- **Long tail beyond 150** (we acknowledge we didn't go deeper)

### Limitations Section:

- We stopped at Rank 150 for practical reasons
- Based on the uniform distribution pattern, we estimate X% more citations would be found at Rank 151-300
- This strengthens the "UI Suppression" argument—relevant content is scattered infinitely deep

---

## 2.5 Listicle Extraction & Bias Analysis

*Self-promotion, product text comparison, accuracy.*

### 2.5.1 Self-Promotion Bias Detection

- **Definition:** A listicle where `is_host_domain = 1` AND `position_in_listicle = 1` (the host ranks themselves #1)

**Research Questions:**
1. How many listicles in our dataset have self-promotion bias?
2. Does ChatGPT cite these biased listicles?
3. Does ChatGPT's final recommendation match the biased #1 product?
4. **Is bias a positive or negative effect?** (Does the self-promoted product actually deserve #1?)

### 2.5.2 Listicle Product Text Analysis

*This is the "Extractive Nature" proof.*

**Methodology:**
1. For each ChatGPT citation of a listicle:
   - Extract the `listicle_products` and their `notes` (the text snippet from the source)
   - Match ChatGPT's recommended products to products in the listicle
2. Compare:
   - Does ChatGPT's description match the `notes` from the listicle?
   - Does ChatGPT mention pros/cons that appear in the source?
   - Does ChatGPT change the ranking order?

**Research Questions:**
- Which products from a listicle does ChatGPT pick? (#1? #3? Random?)
- Does ChatGPT quote/paraphrase the listicle's product descriptions?
- Does ChatGPT synthesize from multiple listicles?

---

## 2.6 Tone & Intent Comparison

*Compare Additional vs. Cited links.*

### Research Questions:

1. Are Additional links more `promotional` or `salesy` than Cited links?
2. Are Cited links more `neutral_informational`?
3. What is the `primary_intent` distribution?

| Metric                              | Cited Links | Additional Links |
| ----------------------------------- | ----------- | ---------------- |
| `tone = neutral_informational`      | ?%          | ?%               |
| `tone = promotional`                | ?%          | ?%               |
| `tone = salesy`                     | ?%          | ?%               |
| `promotional_intensity_score` (avg) | ?           | ?                |
| `primary_intent = informational`    | ?%          | ?%               |
| `primary_intent = commercial`       | ?%          | ?%               |

---

## 2.7 Cross-Run Consistency Analysis

*How do ChatGPT's responses change across 4 runs of the same prompt?*

### 2.7.1 Research Questions:

1. **RAG Trigger Variability:**
   - **The "Stochastic RAG" Phenomenon:** We observed that for the exact same prompt, RAG (web search) may trigger in Run 1 and Run 2, but fail to trigger in Run 3, resulting in a response based purely on parametric knowledge.
   - **Thesis Implication:** This highlights the instability of the LLM orchestrator. A user's chance of receiving a grounded, up-to-date answer is stochastic, even when the intent is clearly commercial.

2. **Citation Stability:**
   - If ChatGPT cites a source in Run 1, does it cite the same source in Run 2/3/4?
   - What % of citations are "stable" (appear in 3+ runs)?
   - What % are "one-off" (appear in only 1 run)?

2. **Product Recommendation Consistency:**
   - If ChatGPT recommends Product X in Run 1, does it recommend it again in Run 2/3/4?
   - Are there "always recommended" products vs. "sometimes recommended" products?
   - Does the ranking/order of products change between runs?

3. **Fan-Out Query Behavior:**
   - What fan-out queries are issued for a prompt (per run)?
   - Do the fan-out queries change between runs (query drift)?
   - How do changes in fan-out queries affect which sources are found?

4. **Listicle Selection Patterns:**
   - If the same listicle is cited in multiple runs, does ChatGPT pick the same products from it?
   - Or does it pick different products each time?
   - Does it change which position (#1 vs #3 vs #7) it extracts from?

### 2.7.2 Metrics to Calculate:

| Metric                          | Definition                                               |
| ------------------------------- | -------------------------------------------------------- |
| **Citation Overlap Rate (COR)** | % of citations that appear in 2+ runs of the same prompt |
| **Product Overlap Rate (POR)**  | % of recommended products that appear in 2+ runs         |
| **Stable Citation Count**       | Number of citations that appear in ALL 4 runs            |
| **Citation Churn Rate**         | % of citations that are unique to a single run           |
| **Fan-Out Query Similarity**    | Similarity between fan-out query sets across runs        |

### 2.7.3 Expected Findings:

**Hypothesis 1:** Core recommendations are stable, but peripheral citations vary.
- The top 3-5 product recommendations should be consistent (70%+ overlap)
- Additional links and lower-ranked citations will have higher churn

**Hypothesis 2:** Fan-out query drift introduces variability.
- Different fan-out query sets → different search results → different citations
- This explains why the same prompt can produce different outputs

**Hypothesis 3:** Listicle extraction is deterministic, but listicle selection is not.
- Once ChatGPT picks a listicle, it extracts products consistently
- But which listicle it picks may vary between runs

### 2.7.4 Data Tables to Generate:

**Table A: Citation Stability by Run**
| Prompt | Citations in R1 | Citations in R2 | Citations in R3 | Citations in R4 | Overlap (All 4) | Overlap (Any 2+) |
| ------ | --------------- | --------------- | --------------- | --------------- | --------------- | ---------------- |
| P001   | ?               | ?               | ?               | ?               | ?               | ?                |
| P002   | ?               | ?               | ?               | ?               | ?               | ?                |
| ...    |                 |                 |                 |                 |                 |                  |

**Table B: Product Recommendation Consistency**
| Prompt | Products in R1 | Products in R2 | Products in R3 | Products in R4 | Stable Products | Unique Products |
| ------ | -------------- | -------------- | -------------- | -------------- | --------------- | --------------- |
| P001   | ?              | ?              | ?              | ?              | ?               | ?               |
| ...    |                |                |                |                |                 |                 |

**Table C: Fan-Out Query Analysis**
| Prompt | Original Query             | Fan-out Qs (R1) | Fan-out Qs (R2) | Fan-out Qs (R3) | Fan-out Qs (R4) | Similarity Score |
| ------ | -------------------------- | ---------------- | ---------------- | ---------------- | ---------------- | ---------------- |
| P001   | "best AI video translator" | ?                | ?                | ?                | ?                | ?                |
| ...    |                            |                  |                  |                  |                  |                  |

### 2.7.5 The Equivalence of Fan-Out Queries (Q1 vs Q2)
*Both queries get "Equal Love" from the model.*

**The Discovery:**
We analyzed the overlap rates between ChatGPT citations and the results from each fan-out query (Q1 = first hidden query, Q2 = second hidden query). The results were strikingly similar:

| Account    | Q1 Overlap | Q2 Overlap | Difference |
|------------|------------|------------|------------|
| Enterprise | **63.7%**  | **64.2%**  | 0.5%       |
| Personal   | **54.1%**  | **52.4%**  | 1.7%       |

**Key Findings:**
- **No "Recency Bias":** The model does NOT prioritize links from its first search query over its second. Both queries contribute equally to the final citation pool.
- **"Bulk Retrieval, Bulk Synthesis":** This proves the model performs a two-phase process:
    1. **Phase 1 (Retrieval):** Issue all fan-out queries and collect all results into a flat pool.
    2. **Phase 2 (Synthesis):** Reason over the combined pool to select citations.
- **Account Variance in Quality, Not Distribution:**
    - **Enterprise (~64%):** High fidelity to search results for both queries.
    - **Personal (~53%):** Lower fidelity (more "hallucination" or parametric knowledge), but Q1/Q2 remain balanced.

**Thesis Implication:**
This finding justifies the architectural choice of "Fan-Out" searching. If Q2 had significantly lower overlap, one could argue that multi-query expansion is wasteful. The equal contribution proves that **every fan-out query is essential** for the model to reach its citation quota. The model treats the entire search pool as a single, unified knowledge base.

### 2.7.6 The "Flip-Flop" Phenomenon: Additional → Cited Overlap Analysis
*How consistently does the model filter its search results?*

**The Discovery:**
We analyzed the "Additional" URLs (sources found in search results but not cited) to see if they were truly "low quality" or just "stochastically ignored."

**Key Findings:**
- **The Global Constant (26.0% vs 25.9%):** Across the entire dataset, the "Flip-Flop" rate is nearly identical. 
    - **Enterprise:** **26.0%** (337 cited elsewhere / 1,298 unique additional)
    - **Personal:** **25.9%** (413 cited elsewhere / 1,594 unique additional)
- **"Additional ≈ Citation-Worthy" (Equivalence Hypothesis):** Within this study’s topical coverage (AI/SaaS product recommendations), many sources labeled **Additional** behave like **citation-worthy candidates** that simply were not promoted to **Cited** in that particular run. The 26% flip-flop rate quantifies this “promotion potential.”
- **Dataset Dependence (Important):** This global flip-flop metric is only meaningful when prompts share a **common source pool** (as is true in this study’s clustered topics). In a dataset of fully disjoint topics, cross-run URL reuse would be rare and the global flip-flop rate would shrink accordingly.
- **Statistical Synchronization:** When splitting by category, the models move in perfect sync:
    - **Business Queries (P041+):** Both accounts hit exactly **24.5%** overlap.

**Thesis Implication:**
The near-identical global overlap (0.1% difference) proves a **shared underlying architecture**. The "Grounding Filter" is a universal constant in the model's RAG pipeline, operating with a fixed ~26% "ambiguity margin" where sources are stochastically rotated between primary and secondary status.

### 2.7.6 The "Conservation of Retrieval" Law: Systemic Intake Tendency
*The discovery of the model's "Link Thirst" and aggregate convergence.*

**The Discovery:**
By quantifying the "Total Considered" universe (Cited + Additional + Rejected), we found a shocking symmetry in scale between account types, despite massive variance in individual runs.

**Key Findings:**
- **The "Link Thirst" Constant:** Across 240 runs, both models exhibit an almost identical "appetite" for information:
    - **Enterprise:** **63,046** total links considered.
    - **Personal:** **62,460** total links considered.
    - **The Convergence:** A difference of only **0.9%**, proving a shared systemic mean for retrieval depth.
- **High Per-Prompt Variance:** While the aggregate is identical, individual prompts show a high **"Variance Allowance"**:
    - **P001 (Perfect Match):** 20.7 vs 20.7 avg links (**0.0% diff**).
    - **P002 (High Divergence):** Personal (37.0) vs Enterprise (13.3) (**94.0% diff**).
    - **P005 (Personal Dominance):** Personal (36.0) vs Enterprise (19.3) (**60.2% diff**).
- **The "Balancing Act":** The model exhibits a stochastic "burstiness"—it may over-retrieve for one prompt and under-retrieve for another, but the **Aggregate Intake Tendency** remains a universal constant.

**Thesis Implication:**
This reveals that "Search" in ChatGPT is governed by a **Systemic Tendency** rather than a rigid per-prompt quota. The model has a specific "Link Thirst" (averaging ~260 links per run) that it satisfies stochastically. The identical aggregate totals prove that the **Intake Engine** is a shared commodity, while the **Fidelity Filter** (81% vs 67% match rate) is where account-level tuning (Enterprise vs. Personal) occurs.

### 2.7.7 Methodological Limitations & Future Scaling
*The case for longitudinal sampling.*

- **Sample Depth vs. Breadth:** While this study utilized 3 runs per prompt to establish the existence of the "Flip-Flop Phenomenon," the total sample size of ~480 independent grounding events provides high statistical confidence in the "Ambiguity Floor" (~26%).
- **Future Work (Same-Prompt Flip-Flop):** To separate “shared topical source pool” effects from true within-prompt stochasticity, future work should compute the **Same-Prompt Flip-Flop Rate**: Additional in Run A → Cited in Run B for the **same prompt_id**. This requires **10+ runs per prompt** to stabilize estimates and produce per-prompt distributions (not just a single global mean).
- **Future Work (Controlled Topic Split):** Repeat the same analyses on intentionally **disjoint topic buckets** (e.g., “video translation” vs. “CRM software”) to quantify how much of the global flip-flop is explained by topic overlap vs. model randomness.

---

## 2.8 Freshness Analysis

### Research Questions:

1. Does ChatGPT prefer more recently updated content?
2. Are Bing Top 10 results "stale" compared to ChatGPT citations?

| Metric                         | ChatGPT Citations | Bing Top 10 | Additional Links |
| ------------------------------ | ----------------- | ----------- | ---------------- |
| `freshness_cue_strength` (avg) | ?                 | ?           | ?                |
| Has `published_date`           | ?%                | ?%          | ?%               |
| Has `modified_date`            | ?%                | ?%          | ?%               |
| Published in 2025-2026         | ?%                | ?%          | ?%               |

---

# Part 3: Additional Analyses (Using All Fields)

## 3.1 Content Quality Indicators

| Field                      | What it measures              | Hypothesis            |
| -------------------------- | ----------------------------- | --------------------- |
| `has_pros_cons`            | Structured evaluation content | Higher in Cited links |
| `has_clear_authorship`     | Credibility signal            | Higher in Cited links |
| `has_sources_or_citations` | Research-backed content       | Higher in Cited links |
| `expertise_signal_score`   | Author/site authority         | Higher in Cited links |
| `spamminess_score`         | SEO junk indicators           | Lower in Cited links  |
| `readability_score`        | Ease of extraction            | Higher in Cited links |
| `content_word_count`       | Content depth                 | Compare distributions |
| `has_schema_markup`        | Technical SEO maturity        | Compare distributions |

## 3.2 Deep Hunt Specific Analysis

- Filter by `is_grounded_deep = TRUE`
- These are the "Buried Truth" links (ChatGPT cited, Bing hid at Rank 31-150)
- Compare their DNA to:
  1. Top 10 cited links
  2. Top 10 ignored links

---

# Part 4: Research Gaps & Future Work

1. **Deeper Crawling:** We stopped at Rank 150; going to 300+ might find more matches.
2. **Longitudinal Consistency (Expanded Runs):** While this study used 3-4 runs per prompt, future work should expand this to 10+ runs to achieve statistical significance in "stochastic retrieval" patterns and to better map the "long tail" of citations that appear only in rare instances.
3. **Temporal Analysis:** How do results change over time? (Run the same queries in 3 months).
3. **Query Category Segmentation:** Do certain product categories have better/worse overlap?
4. **Multi-Model Comparison:** Compare ChatGPT vs. Gemini vs. Claude on the same queries
5. **User Study:** Do humans prefer ChatGPT's recommendations or Bing's Top 10?

---

# Part 5: Conclusions & The Future of Search

## 5.1 The Convergence of SEO and GEO
- **GEO as SEO’s Final Form:** Our data suggests that the "Extractive Nature" of GenAI means that to win in GEO, you must first win the fundamental elements of SEO (visibility, authority, and structured data).
- **The "High-Signal" Mandate:** As search becomes cheaper than inference, LLMs will increasingly rely on external retrieval. Content that is not "searchable" will become "invisible" to AI.

## 5.2 The Economic Moat of Retrieval
- **Compute Efficiency:** We conclude that the future of AI is not larger models, but smarter **orchestrators**. By using the web as a "distributed memory," AI providers can reduce costs while increasing accuracy.
- **The Relevance of Human-Centric Web:** SEO stays relevant because it provides the "Ground Truth" that AI requires to remain grounded and factual.

---

## 8. Future Work & Extensions

### 8.1 Exhaustive SERP Depth Analysis
Current findings indicate a high overlap with Bing's top results, but a tail of "invisible" citations remains (e.g., Wikipedia, niche tech blogs). A future extension should involve:
- **Deep SERP Crawling**: Expanding Bing/Google search depth from top 30/50 to top 100+ results to determine if "invisible" citations are simply lower-ranked search results or truly independent LLM retrievals.
- **Residual Source Isolation**: By programmatically "subtracting" all possible SERP matches (even at extreme depths), researchers can isolate the true "LLM-native" grounding set—sources ChatGPT/Gemini access via internal knowledge bases, direct partnerships, or non-public indices.
- **Decay Rate of Attribution**: Analyzing if the probability of an LLM citing a source correlates with its SERP rank even beyond the first few pages, or if the LLM's "internal" prioritization overrides search engine ranking at depth.

---

# Appendix A: Data Schema Reference

## URLs Table Fields

| Field                         | Type | Description                                          |
| ----------------------------- | ---- | ---------------------------------------------------- |
| `type`                        | enum | listicle, marketplace_directory, product_page, etc.  |
| `content_format`              | enum | best_of_list, comparison_matrix, single_review, etc. |
| `tone`                        | enum | neutral_informational, promotional, salesy, etc.     |
| `promotional_intensity_score` | 0-5  | How "pushy" the content is                           |
| `freshness_cue_strength`      | 0-5  | Recency signals                                      |
| `expertise_signal_score`      | 0-5  | Authority indicators                                 |
| `spamminess_score`            | 0-5  | SEO junk indicators                                  |
| `readability_score`           | 0-5  | Ease of reading/scanning                             |
| `heading_density`             | 0-5  | Structural organization                              |
| `has_tables`                  | 0/1  | Contains comparison tables                           |
| `has_numbered_lists`          | 0/1  | Uses ordered lists                                   |
| `has_bullet_points`           | 0/1  | Uses unordered lists                                 |
| `has_pros_cons`               | 0/1  | Has pros/cons section                                |
| `has_clear_authorship`        | 0/1  | Author attribution                                   |
| `has_sources_or_citations`    | 0/1  | References other sources                             |
| `has_schema_markup`           | 0/1  | Structured data                                      |
| `primary_intent`              | enum | informational, commercial, transactional             |
| `is_grounded_deep`            | bool | Found in Deep Hunt (Rank 31-150)                     |
| `is_strict_match`             | bool | Exact URL match to citation                          |

---

# Appendix B: Key Terms

| Term                   | Definition                                                                                                                                          |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Extractive Nature**  | The observation that ChatGPT's recommendations are primarily extracted and synthesized from cited sources, rather than generated from training data |
| **UI Suppression**     | Bing's interface hiding relevant results behind pagination loops, inconsistent result counts, and UI clutter                                        |
| **Page 2 Cliff**       | The sharp drop in result relevance and visibility after Bing's Top 10                                                                               |
| **Linearity Collapse** | The breakdown of meaningful page numbering in Bing results (Page 2 ≠ Rank 11-20)                                                                    |
| **Grounded Deep**      | Citations that ChatGPT used which were found in Bing but only at Rank 31-150                                                                        |
| **Truly Invisible**    | Citations that ChatGPT used which were never found in Bing even at Rank 150                                                                         |
| **Content DNA**        | The structural characteristics of a page (tables, lists, headings) that make it "extractable"                                                       |
| **Domain Match**       | When Bing found a page from the same domain but different URL than what ChatGPT cited                                                               |
| **Strict Match**       | When Bing found the exact same URL that ChatGPT cited                                                                                               |
| **Grounding**          | The process of anchoring an LLM's response in real-time, verifiable web data to reduce hallucinations and ensure factual accuracy                   |

---

*Document generated: January 2026*
