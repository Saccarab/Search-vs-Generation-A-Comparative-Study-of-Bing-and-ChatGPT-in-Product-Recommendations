# Thesis Research Outline
## Grounding Behavior in LLM‑Mediated Commercial Search: Citation Patterns and Selection Bias

**Author:** [Your Name]  
**Date:** January 2026  
**Status:** Research Notes / Working Draft

---

# Framing: “Grounding Behavior” as the Core Research Spine

This thesis is not “Bing vs ChatGPT” as competing products; **Bing/Google are measurement instruments** used to quantify *grounding behavior* in LLM-generated product recommendations.

**What we empirically observe and measure (high-level):**
- **Cross-model grounding**: Gemini vs. ChatGPT
- **Cross-deployment grounding**: ChatGPT **Personal vs Enterprise**
- **Rank effects**: how grounding/citation choices relate to **SERP position distributions** (position bias)
- **Selection bias in sources**: differences between the **available menu** (Top‑N SERP) vs the **selected order** (cited set), measured via **Content DNA enrichment** of cited and non-cited URLs
- **Visibility gaps**: “invisible/shadow” citations (cited URLs missing from the defined Top‑N baseline), analyzed separately from within-SERP drift

## Core Research Question (single spine)
**RQ1:** *How does grounding behavior manifest in LLM-generated product recommendations, and how does it vary across conditions we can observe (deployment context and/or model)?*

### Operational definition (what “grounding behavior” means in this thesis)
Grounding behavior is the measurable pipeline from **retrieval → selection → citation → final text**, using observable artifacts:
- **Retrieved candidate set** (where available): sources the system pulled/considered
- **Selected set**: sources that “survive” selection (cited/attached)
- **Claim linkage**: which textual claims map to which sources (claim-to-link mapping)
- **SERP support**: whether selected sources are actually present in external SERPs (Bing/Google)
- **Source-to-output fidelity**: whether products mentioned in retrieved listicles are carried into the final recommendations

### Primary measurement idea: “Menu vs Order” (selection drift)
We quantify grounding-related selection bias by comparing the **DNA distribution of the Menu** (Top‑N SERP results / retrieved candidate set) against the **DNA distribution of the Order** (the URLs the model actually cites), optionally **rank-stratified** (Rank 1..N) to control for position bias.

**Evidence hierarchy (how we present results):**
- **Highest-confidence**: SERP position / visibility findings (rank distributions, “deep” vs “invisible” citations). These are based on direct URL/domain matching + observed rank positions.
- **Secondary (more measurement noise)**: DNA-based Menu vs Order comparisons (e.g., `has_tables`, `has_pros_cons`, structure/format labels). These are still useful to characterize selection behavior, but depend on enrichment/labeling fidelity and page-template variance.

## Sub-questions (decompositions of RQ1, not separate topics)
- **RQ1a (selection + visibility)**: How do **cited vs additional vs rejected/invisible** sources differ in domain/type, and how does this differ by **enterprise vs personal** runs?
- **RQ1b (external support)**: How often do selected sources appear in **Top‑N SERPs** (Bing/Google overlap; Gemini “survival” in Top‑20), and what are the failure modes (pagination cliff, deep-rank burial, etc.)?
- **RQ1c (listicle uptake / fidelity)**: When listicles are retrieved, which listicle-mentioned products are **selected vs ignored** in the final response (uptake rate, rank bias, host-bias), and how does this differ by run type?
- **RQ1d (claim-level grounding)**: At claim span level, how tightly do claims align to specific sources (and where do “multi-chip” merges occur)?

## Role of external systems (clarify scope)
- **Bing**: baseline “human web” retrieval/ranking surface; used to measure overlap/coverage and “visibility gaps” (Top‑30 vs Deep Hunt).
- **Google (SerpApi)**: control baseline for Gemini fan-out queries and sensitivity checks (organic-only vs organic+video/PAA).
- **Gemini**: optional cross-model baseline for grounding mechanics (has explicit `groundingMetadata` and claim-support mapping); not an enterprise/personal split unless we create our own conditions.

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

### 1.1.1 Google SERP result types (SerpApi): Organic vs Video vs PAA
SerpApi returns Google results in multiple **result_type** buckets (not just “10 blue links”). This matters because overlap numbers can shift depending on what we count as “the SERP.”

- **Organic results**: standard web results (our primary control-group baseline).
- **Video results**: often YouTube-heavy; can appear in top positions and inflate “coverage” for topics where ChatGPT cites YouTube.
- **PAA (People Also Ask)**: question-card expansions; these are not directly comparable to Bing organic ranks and can introduce additional URLs.

**Method rule (comparability)**:
- For overlap metrics, we default to **Organic-only** (and treat Video/PAA as separate diagnostic buckets), unless explicitly stated otherwise.
- We keep the non-organic buckets available as a **discussion point** (e.g., “Google surfaces YouTube via Video blocks earlier than Bing”), and as a sensitivity analysis (“organic-only vs organic+video”).

### 1.1.2 Content-size context (listicles vs product pages)
We report page-length as **context** (not a grounding budget claim): listicles are longer and more heterogeneous than vendor pages, which can influence extractability and selection behavior.

Computed from raw fetched text dumps in `data/fetched_content/` (see `data/enrichment/content_size_stats_raw.csv`).

| Bucket | Median words | Median bytes | Coverage |
| --- | ---: | ---: | ---: |
| `all::listicle` | 2,094 | 14,645 | 99.7% |
| `all::product_page` | 927 | 6,593 | 97.7% |
| `menu_any::listicle` | 2,111 | 14,747 | 99.8% |
| `menu_any::product_page` | 930 | 6,614 | 98.0% |
| `cited_any::listicle` | 2,182 | 15,343 | 99.5% |
| `cited_any::product_page` | 925 | 6,563 | 96.1% |

**Interpretation**: listicles are ~2× longer than product pages (median words). Menu vs cited size differences are small, suggesting selection effects are not driven by length alone.

**Connection to Dejan (“grounding budget”)**: Dejan’s analysis of Google AI Overviews discusses a roughly fixed per-query *grounding/snippet budget* (on the order of ~2k words). Our table above is **not** measuring an injected-context budget; it measures **full page length** of the candidate/cited sources we fetched. We include it as context for extractability and selection behavior, not as a budget validation.

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
- **Important nuance (multi-turn fan-out):** Fan-out queries may be emitted in **multiple batches** across search turns; the “fan-out set” for a run is the **union** of all observed batches (not just the first).

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

### 1.6.3 Multi-source claim support rate (single claim/segment cites >1 URL)
**Definition (operational):** a claim/segment is “multi-cited” if it has **2+ distinct cited URLs**.

Computed by `scripts/analysis/multi_source_claim_support.py` (artifacts in `data/enrichment/`).

**All claim/segment occurrences:**
- **GPT**: 458 / 4296 (**10.7%**) multi-cited
- **Gemini**: 788 / 2287 (**34.5%**) multi-cited

**Listicle-cited occurrences only (at least one cited URL has `type=listicle`):**
- **GPT**: 194 / 1363 (**14.2%**) multi-cited
- **Gemini**: 664 / 1519 (**43.7%**) multi-cited

### 1.6.4 Mixed listicle + product-page citations (within a single claim/segment)
**Definition (operational):** among **multi-cited** claims/segments, label a case “mixed” if the cited URL set contains **≥1** `type=listicle` and **≥1** `type=product_page`.

**All multi-cited occurrences:**
- **GPT**: 41 / 458 (**9.0%**) mixed listicle+product-page
- **Gemini**: 130 / 788 (**16.5%**) mixed listicle+product-page

**What are the “rest” of multi-cited claims? (type-mix buckets)**
When we say “multi-cited”, we partition each multi-cited claim/segment into **exactly one** bucket:
- **mixed listicle+product**: at least one `listicle` and at least one `product_page`
- **listicle-only**: at least one `listicle` and **no** `product_page`
- **product-only**: at least one `product_page` and **no** `listicle`
- **neither**: **no** `listicle` and **no** `product_page` cited (i.e., multiple citations drawn from other page types such as directories, docs, news, etc., or “unknown” when a URL lacks a DNA label)

**GPT multi-cited (N=458) bucket breakdown:**
- mixed listicle+product: **41 (9.0%)**
- listicle-only: **153 (33.4%)**
- product-only: **168 (36.7%)**
- neither (no listicle/product_page): **96 (21.0%)**

**Gemini multi-cited (N=788) bucket breakdown:**
- mixed listicle+product: **130 (16.5%)**
- listicle-only: **534 (67.8%)**
- product-only: **84 (10.7%)**
- neither (no listicle/product_page): **40 (5.1%)**

**What does “neither” look like? (examples of multi-cited type-sets)**
- **GPT neither (N=96)** is dominated by `unknown` (unlabeled URLs) plus small tails like `news_article`, `documentation`, `editorial_article`, `forum_ugc`, `marketplace_directory`, and combinations (see `multi_type_sets_by_bucket.neither_listicle_nor_product` in `data/enrichment/multi_source_claim_support_stats.json`).
- **Gemini neither (N=40)** is mostly `other` / `unknown` mixtures plus a tail of `documentation`, `marketplace_directory`, `forum_ugc`, `editorial_article`, etc. (same JSON).

**Listicle-cited multi-cited occurrences only:**
- **GPT**: 41 / 194 (**21.1%**) mixed listicle+product-page
- **Gemini**: 130 / 664 (**19.6%**) mixed listicle+product-page

**Mixed-case lists (for qualitative inspection):**
- `data/enrichment/mixed_listicle_plus_product_citations_gpt.csv` (41 rows)
- `data/enrichment/mixed_listicle_plus_product_citations_gemini.csv` (130 rows)

## 1.7 Anatomy of a ChatGPT Response (Network-Instrumented)
*What exactly we can observe about ChatGPT’s retrieval + citation pipeline from captured network payloads.*

### 1.7.1 The high-level “agent loop” (as observed)
1. **User prompt received**
2. **Search decision**: the system decides whether to call web search (probabilistic trigger)
3. **Fan-out query generation** (often hidden): multiple search queries issued for the same prompt
4. **Retrieval**: a pool of search results is returned (grouped lists of candidate sources)
5. **Selection**: the model promotes some sources to be cited inline, and may also attach extra sources
6. **Generation**: answer text is streamed + citations are inserted/merged (“multi-chip”)

### 1.7.2 Source categories we use (scope)
- **Cited**: sources referenced inline in the generated answer.
- **Additional**: sources retrieved and attached but not referenced inline (still “considered”).
- **Rejected**: sources that appeared in the retrieved pool but did not survive selection (not cited, not attached).

### 1.7.3 Search trigger instrumentation (the “decision” fields)
We log the system’s search-decision artifacts where present (Enterprise streams are richest):
- `sonic_classification_result`: the classifier output used to decide search (e.g., `simple_search_prob`, `complex_search_prob`, thresholds).
- `web_search_triggered`: whether search actually ran.
- `web_search_forced`: whether search was forced (if present).

### 1.7.4 Fan-out queries (“hidden queries”)
- **Definition**: multiple search queries issued for one user prompt; these expand/reshape retrieval scope.
- **Why it matters**: fan-out sets control which sources are even eligible to be cited.
- **Observable field (network-derived)**: `search_model_queries.queries` (stored as `hidden_queries_json` in our extracted CSV/DB pipeline).
- **Typical vs. exception**: Many runs have **two** fan-out queries (Q1/Q2), but some runs have **4+**; these can appear as **2 queries in search turn 1** and **2 more in search turn 2** (e.g., `P053_r2`).
- **How it appears in the raw network stream (multi-turn fan-out signature)**:
  - The response arrives as an event stream (patch/append style) containing repeated tool messages (commonly `role="tool"`, `name="web.run"`).
  - Each search “turn” can include a `metadata.search_model_queries` object with a `queries[]` list, plus a `search_turns_count` counter.
  - When multi-turn fan-out happens, **multiple** `metadata.search_model_queries` blocks appear in the same run with **increasing** `search_turns_count` (e.g., 1 → 2 → 3). The run’s fan-out set is the **union** of all `queries[]` lists across these blocks.
  - A useful corroborating field in the run-level metadata is `search_tool_call_count`, which tends to equal the number of search turns (typical single-turn runs: `1`; multi-turn runs: `2+`).
  - Example patterns observed:
    - `P053_r2` (Enterprise): 2 queries at `search_turns_count=1` + 2 queries at `search_turns_count=2` → 4 total.
    - `P073_r3` (Enterprise): 2 queries at each of `search_turns_count=1,2,3` → 6 total.

### 1.7.5 Retrieved candidate pool (what the model could have used)
We capture the retrieved candidates and their metadata:
- `search_result_groups`: grouped search entries containing `url`, `title`, `snippet`, and `ref_id` (turn/ref index keys).
- **Interpretation**: this is the model’s “shortlist menu” prior to selection.

### 1.7.6 Citation tokens & claim mapping (how we attach sources to text)
Two key payload elements enable claim→source reconstruction:
- `content_references`: token spans / citation tokens with `start_idx` / `end_idx` (where citations appear in the output stream).
- `response_text`: the generated text (often streamed via patch/append events).

From these, we build:
- **Claim blocks**: the text segments preceding each citation token (our `claim_text` extraction).
- **Mapped sources**: resolved URLs/titles/snippets by matching `ref_id` keys to `search_result_groups`.

### 1.7.7 What the network does *not* reveal (critical limitation)
- It does **not** include the exact on-page snippets/chunks that were fetched/inserted into the model context.
- Therefore: our ChatGPT-side “grounding budget” analyses are **output-side proxies** (claim-attributed text), not true input-side snippet budgets.

### 1.7.8 What happens next (how this section feeds the thesis)
This “anatomy” motivates the next analytic layers:
- **Overlap & visibility**: compare cited/additional/rejected pools against Bing Top 30 + Deep Hunt and Google SERP controls.
- **Selection bias**: compare Content DNA of Cited vs Additional vs Rejected.
- **Stochasticity**: quantify fan-out drift across runs and resulting citation churn.

### 1.7.9 Network Parameter Glossary (ChatGPT, Network-Instrumented)
*A practical glossary of the recurring fields we use when decoding the raw event stream. This is intentionally limited to parameters we directly observed in captured payloads.*

#### Identifiers / linkage
- **`conversation_id`**: conversation session identifier (useful for grouping, not analysis).
- **`message.id`**: unique message identifier in the stream.
- **`parent_id`**: links a message to its parent; helps follow the chain of events.
- **`request_id`**: correlates events belonging to the same request; often shared across tool calls and patches for that run.
- **`turn_exchange_id` / `turn_trace_id`**: internal tracing IDs for a single turn; useful for debugging continuity across events.

#### Search trigger & decision
- **`sonic_classification_result`**: the search trigger classifier output (probabilities + thresholds).
- **`web_search_triggered` / `web_search_forced`**: whether search ran / was forced (when present).
- **`message_marker`**: markers like `search_start` that indicate when retrieval begins.

#### Fan-out queries & search turns
- **`metadata.search_model_queries.queries[]`**: the model-generated fan-out query list for a search turn (our “hidden queries”).
- **`search_turns_count`**: which search turn we are in (1, 2, 3…); multi-turn fan-out appears as repeated query batches with increasing counts.
- **`search_tool_call_count`**: run-level count of search tool invocations; typically correlates with `max(search_turns_count)` (single-turn: 1; multi-turn: 2+).
- **`search_source` / `client_reported_search_source`**: indicates the origin mode (often `composer_auto`); useful for auditing when behavior changes.

#### Retrieved candidates (what came back from search)
- **`metadata.search_result_groups`**: the grouped retrieval pool (URLs, titles, snippets).
- **`ref_id`**: the key (turn/ref indices) we use to map candidates to citations (`turn_index`, `ref_type`, `ref_index`).
- **`debug_sonic_thread_id`**: internal identifier for the search thread (debugging/trace only).

#### Citation / attribution artifacts
- **`content_references`**: citation token spans inserted into the streamed response; indices point to the citation token location, not the claim boundary.
- **`safe_urls`** and **`url_moderation` events**: safety/allow-list decisions for URLs that show up in citations and link cards.

#### Completion / response framing
- **`finish_details`**: how generation ended (stop reason / tokens).
- **`model_slug` / `default_model_slug`**: the model variant used for the run.

---

## 1.7 Market Context & Motivation (Ahrefs Benchmark)
*To motivate the study, we anchor the "Search vs. Generation" transition in macro-level traffic data.*

- **The Macro Baseline:** According to [Ahrefs (ChatGPT vs. Google)](https://chatgpt-vs-google.com/), as of December 2025, traditional search engines still dominate web traffic (~41.68% share), while AI Assistants hold a much smaller but highly volatile share (~0.24%).
- **The Research Opportunity:** While macro traffic to AI assistants is currently low, the **competition for user attention** is intensifying (e.g., Gemini's 31.7% growth in Dec '25).
- **Thesis Motivation:** This study focuses on the **micro-level mechanics** of this transition: how these AI assistants "ground" their answers in the very search results that currently dominate the market. We measure the *dependency* of generation on search.

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

## 2.2.1 Content DNA “Drift” (Cited vs. All Retrieved Candidates)
*Early enrichment results (from `geo_fresh.db` + `page_labels_combined_v2.5.jsonl`). These quantify the “selection filter” stage: what gets **cited** vs what was merely available.*

### Key finding A: citations drift toward product landing pages (de‑listicling)
Across both account types, the cited set is strongly enriched for **`type=product_page` / `content_format=landing_page`**, while listicle formats are under-selected.

- **Enterprise** (cited vs all candidates):
  - `type=product_page`: **+16.5 pp** selection lift
  - `content_format=landing_page`: **+17.3 pp** selection lift
  - `content_format=best_of_list`: **-8.5 pp** selection lift
- **Personal** (cited vs all candidates):
  - `type=product_page`: **+18.5 pp** selection lift
  - `content_format=landing_page`: **+17.8 pp** selection lift
  - `content_format=best_of_list`: **-9.4 pp** selection lift

**Interpretation**: listicles are frequently retrieved in purchase-intent SERPs, but the model often “graduates” citations to primary vendor pages at selection time.

### Key finding B: within listicles, “extractable structure” increases citation odds
Conditioning on `type=listicle` (so this is not confounded by “product pages don’t have authorship”), the strongest positive drifts are:
- **Tables**: listicles with `has_tables=1` are more likely to be cited (largest lift within listicles).
- **Pros/cons**: `has_pros_cons=1` is also positively associated with being cited.

**Interpretation**: listicles that present structured, scannable evidence (tables, pros/cons blocks) are more “citation-ready.”

### Key finding C: authorship is ambiguous and needs targeted audit
Authorship signals (`has_clear_authorship`) do **not** cleanly predict citation selection once we control for type:
- Enterprise: near-zero effect within listicles.
- Personal: slight negative drift within listicles.

**Action item**: treat authorship as a **candidate confounded signal** (publisher style / affiliate patterns / extraction noise) and validate with a targeted audit (see “Future Work” notes below).

### Key finding D: page-depth and “invisible in Bing” behave differently for listicles vs product pages
Using Bing `page_num` (Page 1 vs Page 2+ vs not found in Bing within our snapshot), we observe:
- **Listicle citations** are more often found on **Bing Page 1**, especially in Enterprise.
- **Product-page citations** are disproportionately “not found in Bing,” especially in Personal.

**Interpretation**: the “invisible URL” phenomenon is not uniform; it clusters by page type and varies by account context.

### Note (investigate next): drift for additional enrichment fields
We should compute and report drift/lift for fields where it is plausibly meaningful:
- `freshness_cue_strength` (recency bias / “current-year” listicles)
- `has_bullet_points`, `has_numbered_lists`, `heading_density` (extractability)
- `readability_score` (scanability)
- `expertise_signal_score` and `has_sources_or_citations` (credibility proxies)
- `promotional_intensity_score` / `spamminess_score` (marketing pressure)

This is operationalized in the drift outputs under `data/enrichment_compound_effects/`, including a listicle-only drift table (`selection_lift_univariate_listicle_only.csv`).

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

### 2.5.1 Self-Promotion Bias & Host Exclusion
- **Host exclusion (empirical)**: In the listicle semantic-fidelity audit (solo-cited listicles), models **often omit** the host’s own product even when it is present in the listicle.
  - **Gemini**: host present in **405** listicles; host **missing** in **71.9%** (291/405), **included** in **28.1%** (114/405)
  - **GPT**: host present in **431** listicles; host **missing** in **63.6%** (274/431), **included** in **36.4%** (157/431)
- **Bias multiplier (selection advantage)**: “Missing most of the time” does **not** imply “no bias.” When host is present, it is still selected at a rate far above a random item on the page.
  - **Avg listicle size (in this audited subset)**: Gemini **8.1** products/page; GPT **9.3** products/page
  - **Host selection rate**: Gemini **28.15%**; GPT **36.43%**
  - **Random baseline** (approx \(1/\)avg products): Gemini **12.41%**; GPT **10.70%**
  - **Bias multiplier**: Gemini **2.27×**; GPT **3.40×**
- **Interpretation**: LLMs exhibit a mixed behavior: an “anti-self-promo” tendency (frequent host omission) combined with a measurable host selection advantage when they do pick items from host-authored listicles.

### 2.5.2 Selection Order vs. Listicle Rank (The "Re-Ranking" Effect)
- **Rank alignment**: how often **Chat response order** matches the **listicle’s internal rank** for the same product (only when `listicle_rank` is recoverable).
  - **Gemini**: **29.5%** (108/366)
  - **GPT**: **27.9%** (166/596)
- **Interpretation**: models frequently **re-rank** listicle items in the final response. The listicle’s “#1–#10” order is not preserved as the model’s “top picks” order.

**Listicle rank bias (top-item skew):** Do models preferentially pick items that are near the top of the cited listicle?
- **Data used**: product roster items only where `present_in_listicle=="yes"` and `listicle_rank` and `total_products_in_listicle>1` are available.
  - **GPT Enterprise**: **n=391** (mean listicle size **10.95**)
  - **GPT Personal**: **n=205** (mean listicle size **8.57**)
  - **Gemini**: **n=365** (mean listicle size **8.56**)
- **Observed share of selected items coming from top ranks**:
  - **GPT Enterprise**: #1 **18.9%**, Top‑3 **50.9%**, Top‑5 **76.0%**
  - **GPT Personal**: #1 **31.7%**, Top‑3 **60.5%**, Top‑5 **81.0%**
  - **Gemini**: #1 **34.8%**, Top‑3 **61.1%**, Top‑5 **79.5%**
- **Lift vs uniform baseline** (expected Top‑K share under random pick from a listicle of that size; computed per-item as \(K/N\), capped at 1.0):
  - **GPT Enterprise**: #1 **1.73×**, Top‑3 **1.55×**, Top‑5 **1.40×**
  - **GPT Personal**: #1 **2.34×**, Top‑3 **1.49×**, Top‑5 **1.22×**
  - **Gemini**: #1 **2.53×**, Top‑3 **1.48×**, Top‑5 **1.18×**
- **Interpretation**: when a listicle has a recoverable internal ranking signal, models **over-select higher-ranked items** (especially the #1 entry), but still **re-rank** them in the final response order (weak correlation between response product order and listicle rank).

### 2.5.3 Semantic Fidelity: Reading Comprehension vs. Attribution
- **The "Two-Layer" Grounding Problem:** We decompose "Fidelity" into two distinct measurable phenomena:
    1.  **Attribution Accuracy:** Does the cited source actually contain the product?
    2.  **Reading Comprehension (Pure Fidelity):** When the product is present, how accurately does the model extract its details?
- **Key Findings (Solo-Cited Listicles):**
    - **Pure Fidelity (Comprehension):** Both models exhibit near-perfect scores when the product is present (**Gemini: 4.81/5.0**, **GPT: 4.75/5.0**).
    - **Attribution Failure:** Some “solo-cited” product claims still point to listicles where the product is not present (mis-attribution).
      - **Gemini**: **7.36%** (31/421 product roster items)
      - **GPT**: **1.89%** (13/689 product roster items)
- **Thesis Implication:** The "hallucination problem" in modern RAG systems is increasingly an **attribution/linkage problem**, not a "reading" or "understanding" problem. The models "know" the facts but "forget" which specific tab they were looking at when they found them.

---

## 2.6 Tone & Intent Comparison — Dropped (not part of final thesis)

We originally considered a sentiment/tone-oriented study, but dropped it to keep the thesis spine focused on **grounding mechanics**:
retrieval → selection → citation → claim-level fidelity. Tone remains available as a descriptive label in the enrichment dataset, but is not a core claim in the final narrative.

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
