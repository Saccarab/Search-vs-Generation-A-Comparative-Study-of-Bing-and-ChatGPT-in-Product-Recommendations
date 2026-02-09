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
- **Bing**: baseline “human web” retrieval/ranking surface used as a **measurement instrument** for rank/visibility and “visibility gaps” (**Top‑200**).
- **Google (SerpApi)**: control baseline for Gemini fan-out queries and sensitivity checks (**Organic-only** vs including non-organic result types like **Video/PAA/Discussions**).
- **Gemini**: optional cross-model baseline for grounding mechanics (has explicit `groundingMetadata` and claim-support mapping); not an enterprise/personal split unless we create our own conditions.

# Part 1: Methodology & Tools

## 1.1 Data Collection Pipeline

| Component            | Description                                                                      |
| -------------------- | -------------------------------------------------------------------------------- |
| **Queries**          | 79 product recommendation queries × 3 runs each (237 total runs)                 |
| **ChatGPT Data**     | Full responses with inline citations, additional links, and recommended products |
| **Bing Data**        | Top 200 results                                                                  |
| **Gemini Data**      | Full `groundingMetadata` (Chunks vs. Supports) + Fan-out Queries                 |
| **Google SERP**      | SerpApi pagination until **≥20 Organic** results are collected (often ~3 pages), with Video/PAA/Discussions retained as diagnostic buckets |
| **Content Fetching** | Node.js fetcher + Browser extension for blocked pages (Master Content Library)   |

### 1.1.1 Google SERP result types (SerpApi): Organic vs Video vs PAA
SerpApi returns Google results in multiple **result_type** buckets (not just “10 blue links”). This matters because overlap numbers can shift depending on what we count as “the SERP.”

- **Organic results**: standard web results (our primary control-group baseline).
- **Video results**: often YouTube-heavy; can appear in top positions and inflate “coverage” for topics where ChatGPT cites YouTube.
- **PAA (People Also Ask)**: question-card expansions; these are not directly comparable to Bing organic ranks and can introduce additional URLs.
- **Discussions / forums blocks**: SerpApi often surfaces forum-like “discussions” sections; we retain them as a separate diagnostic bucket.

**Method rule (comparability)**:
- For overlap metrics, we default to **Organic-only** (and treat Video/PAA as separate diagnostic buckets), unless explicitly stated otherwise.
- We keep the non-organic buckets available as a **discussion point** (e.g., “Google surfaces YouTube via Video blocks earlier than Bing”), and as a sensitivity analysis (“organic-only vs organic+video”).
- **Pagination rule (how we collected the “Top‑20 Organic” baseline)**: we paginate SerpApi until we have **≥20 Organic** results (not necessarily only the first page). In practice this is often the first ~3 pages, alongside non-organic blocks.

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

### 1.2.2 Methodological Evolution: From Top 30 to "Deep Hunt" (Rank 200)
- **Initial Assumption:** Our study began with a standard retrieval depth of the **Top 30 Bing results**, assuming this would capture the vast majority of relevant citations used by ChatGPT.
- **The Discovery of "UI Erasure":** Upon qualitative review using our custom Data Viewer, we observed a significant "Visibility Gap." ChatGPT was citing high-quality, relevant pages that were completely missing from the Top 30 human-facing results.
- **The Pivot to Rank 200:** To test whether these citations were truly "invisible" or merely "buried," we expanded our methodology to a **"Deep Hunt" (Rank 200)**. 
- **Key Finding of the Pivot:** We discovered that Bing often surfaces the exact pages ChatGPT cites, but hides them deep within pagination loops or beyond the "Page 2 Cliff" (Rank 11+). This methodological shift allowed us to prove that the difference between Search and GenAI is often a **UI and Ranking problem**, not just an indexing one.

## 1.3 Localization & Retrieval Environment

*How geographical context affects the comparison between Search and GenAI.*

### 1.3.1 Implicit vs. Explicit Localization
- **Prompt Language Distribution**: Our dataset consists of **74 English prompts** and **5 foreign-language prompts** (French, Chinese, Turkish, Italian, Spanish).
- **Explicit Localization:** When the user query contains a location (e.g., "Best pizza in New York").
- **Implicit Localization:** When the query is general (e.g., "Best laptop"), but the search engine uses the user's IP, browser language, and search history to localize results.
    - **Occurrence Rates:** We observe implicit localization signals (non-English fan-out queries) in **13.1%** of GPT runs and **4.6%** of Gemini runs.
- **The Research Problem:** Traditional search engines (Bing) are aggressively localized. Generative AI (ChatGPT) often provides a more "Global/US-centric" baseline unless explicitly prompted otherwise.
- **Observed instrumentation signal (Fan-Out Queries):** In our logged **fan-out query sets** (Gemini `groundingMetadata.webSearchQueries[]`, ChatGPT network-derived hidden queries), implicit localization often manifests as **one of the fan-out queries being rewritten into the prompt’s local language**, which then steers retrieval toward localized sources.
- **The "English Anchor" Effect (Gemini-specific):**
    - Even for foreign-language prompts, Gemini **always** reserves the first fan-out slot (Index 0) for an English translation of the prompt.
    - Due to the **First-Query Bias** (where models preferentially cite results from the first search query), the English-language search results dominate the final response.
    - **Finding**: In 100% of our localized Gemini runs, the cited sources were primarily global/English SaaS platforms and tech publications (e.g., `pcmag.com`, `techradar.com`), effectively creating a "Global Information Bubble" even for non-English users.
- **Concrete example (why we used a proxy):** When issuing an English prompt from **Munich, Germany**, we observed a two-query fan-out where one query remained English while the other was rewritten into German:
  - Q1: `"free website or program to translate video and add subtitles"`
  - Q2: `"kostenlos video übersetzen und Untertitel automatisch hinzufügen ..."`
  
  This yielded German-language results despite an English user prompt, demonstrating how implicit localization can enter via fan-out rewriting. (Redacted network excerpt saved at `datapass/raw_network_responses/examples/implicit_localization_fanout_query_rewritten_de_redacted.txt`.)

- **Publisher/SEO→GEO implication:** Even if users in non‑English-speaking countries **search in English**, IP/locale-driven fan‑out rewriting can route part of retrieval toward **localized-language SERPs**. Publishers without localized pages may lose visibility (and therefore citations/traffic) in these retrieval paths.

- **Observed fan-out localization patterns (3 cases we saw):**
  1. **Prompt is foreign-language**: the system may still emit at least one **English** fan-out query alongside the local-language query (mixed-language retrieval).
  2. **Prompt is English + user in non‑English region**: one fan-out query may be rewritten into the region’s language (example above: Munich → German).
  3. **Prompt is English + unexpected non‑English fan-out**: occasionally, a fan-out query appears in another language for unclear reasons (observed in both GPT and Gemini; e.g., Gemini searching in French for a TTS query). This is treated as an anomaly / potential hallucination or hidden locale signal.

- **Concrete example (explicit localization via fan-out):** A location-free prompt like `"what is the best bakery"` can trigger fan-out queries that inject a specific place (e.g., `"best bakery near Munich Germany"`), effectively converting an implicit prompt into an explicitly localized retrieval task. (Redacted network excerpt saved at `datapass/raw_network_responses/examples/explicit_localization_bakery_munich_redacted.txt`.)

### 1.3.2 Freshness Steering (Explicit vs. Implicit)
- **Gemini: Explicit Freshness Obsession**
    - **93.4% of Gemini runs** explicitly inject a year (2025 or 2026) into their fan-out queries.
    - **71.7% of Gemini runs** place this freshness signal in the **very first query (Index 0)**.
    - **Impact**: This explains Gemini's extreme "Listicle Uptake" rate. By explicitly searching for "Best [Product] 2025," the model forces the retrieval of listicles, which then dominate its grounding.
- **GPT: Implicit Recency Reliance**
    - Only **5.1% of GPT runs** use explicit year signals in their fan-out queries.
    - **Impact**: GPT relies almost entirely on the search index's (Bing's) internal recency ranking. It does not "hunt" for listicles as aggressively as Gemini, leading to a more diverse (though still listicle-leaning) grounding pool.
- **Note:** Definition + drift mechanics are described in `1.7.4 Fan-out queries (“hidden queries”)` (instrumentation section); we focus here on the freshness operator specifically.

### 1.3.3 The Proxy Requirement (US-Centric Baseline)
- To ensure a fair "apples-to-apples" comparison, we standardized our retrieval environment using a **US-based Proxy**.
- **Why US Proxy?**
  1. **Baseline Consistency:** ChatGPT's primary training data and search behaviors are heavily weighted toward US-English web content.
  2. **Avoiding "Regional Noise":** Prevents Bing from surfacing local retailers or regional blogs that ChatGPT would never see, which would artificially lower the overlap percentage.
  3. **Global Tech Standard:** Most product recommendations in the "AI/Software" category (our primary focus) are global in nature, making the US SERP the most relevant "Ground Truth."

### 1.3.4 Ethical and Legal Constraints in Retrieval Instrumentation
- **The "Data Access" Bottleneck**: A significant challenge in RAG research is the increasing difficulty of accessing "raw" search indices. 
- **Google vs. SerpApi (Dec 2025)**: On December 19, 2025, Google filed a lawsuit against **SerpApi**, alleging "unlawful scraping" and circumvention of security measures ([Google Blog, 2025](https://blog.google/innovation-and-ai/technology/safety-security/serpapi-lawsuit/)). 
- **The "Customer List" Paradox**: Interestingly, the SerpApi homepage has historically listed major AI players like **Perplexity** and **OpenAI** (the latter was subsequently removed) as customers ([SerpApi, 2026](https://serpapi.com/)). This suggests a complex ecosystem where the very companies building RAG systems may rely on third-party scrapers to bridge the "Visibility Gap" between their models and the live web.
- **Impact on Methodology**: This legal pressure has led to technical restrictions in the SEO/GEO tool ecosystem, such as the removal of high-volume parameters (e.g., `num=100`). 
- **Research Justification**: These constraints further justify our **Deep Hunt (Rank 200)** methodology. As traditional scraping becomes more restricted, the "Visibility Gap" between what an LLM can see (via direct API access) and what a researcher can see (via public search UIs) will likely widen, making the LLM a primary—and increasingly exclusive—gateway to the deep web.

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
- **Thesis Connection:** Our discovery that ChatGPT citations are often buried at **Rank 31-200** in the Human Web proves that the "Grounding" engine uses a different set of priorities than the "Ranking" engine.

## 1.5 The Commercial Catalyst for RAG

*Why product recommendations are the "Front Line" of Generative Search.*

### 1.5.1 Search Trigger Rates by Intent
- **The Commercial Dominance:** Research (e.g., Profound, 2026) indicates that **Commercial Queries** trigger a web search in **53.51%** of ChatGPT conversations—nearly 3x the rate of Informational queries (18.73%).
- **The "Winnable" Arena:** Because commercial intent requires real-time data (pricing, availability, reviews), it is the primary driver for RAG adoption. This makes product recommendations the most critical area for studying the shift from SEO to GEO.

### 1.5.2 Selection of the Research Query Set
- **High-Volume Real-World Prompts:** Our dataset consists of **79 unique product recommendation prompts** (e.g., "Best AI video translators", "Top-rated transcription software").
- **Methodology for Selection:**
    - **Keyword Clustering:** Using tools like **Ahrefs** to identify high-intent clusters.
    - **Prompt Volume Analysis:** Leveraging **Profound's** database to select real-world prompts actually used by consumers.
    - **Deliberate Intent Filtering:** From the broad set of available user prompts, we **deliberately filtered for high commercial intent**. This ensures the study reflects the specific segment of search where AI synthesis is most active and where the "Extractive Nature" of the model is most visible.
    - **Domain Expertise:** Queries were focused on the **AI and Software-as-a-Service (SaaS)** sectors—a domain where the author has significant professional expertise—allowing for more nuanced qualitative analysis of the "Signal vs. Noise" in results.
- **Experimental Rigor:** Each of the 79 prompts was executed in **3 independent runs** (with a 4th run added only in cases of technical failure or RAG non-triggering) to analyze the consistency and stochastic nature of the retrieval process.

### 1.5.3 The GEO Industry Landscape: Citation Tracking & "Share of Model"
- **The Rise of GEO Analytics**: Emerging platforms (e.g., **Profound**, **Peec.ai**) are shifting the industry from "Share of Voice" (traditional search) to "Share of Model" (generative search).
- **The Listicle as the "Critical Node"**: Our research places extreme emphasis on listicles because they are the primary "on-ramp" for product citations. In the GEO ecosystem, being cited in a top-tier listicle is no longer just about referral traffic; it is a prerequisite for being "seen" by the RAG orchestrator.
- **Quantifying the Value of a Citation**: By measuring the **Bias Multiplier** (how much more likely a cited product is to be selected vs. a random one) and **Host Exclusion** (the risk of being ignored if you are the host), we provide the first empirical framework for what these citation-tracking tools are actually measuring.
- **The "Gold Rush" of AEO/GEO:** The rapid rise of companies like **Profound** and **Perplexity AI** underscores the industry's recognition that the "Answer Engine" is the next multi-billion dollar shift in tech.
- **Venture Capital Validation:** A landmark moment occurred on August 12, 2025, when **Profound raised $35 million in a Series B round led by Sequoia Capital**, bringing its total funding to $58.5 million ([Fortune, 2025](https://fortune.com/2025/08/12/ai-search-startup-profound-raises-35-million-series-b-sequoia/)).
- **The "Salesforce of AI Search":** This funding round validated the concept of building a "generational company" centered on helping brands monitor and optimize for how they surface in AI-generated responses across models like ChatGPT, Gemini, and Claude.
- **The Hype vs. Reality:** While the hype is centered on "killing search," our research suggests the reality is a **deeper integration** where search becomes the infrastructure for AI.
- **The High-Intent Conversion Hypothesis**: Preliminary industry observations (e.g., internal data from Maestra AI) suggest that while AI-driven traffic volume is currently lower than traditional search, the **conversion rate** and **purchase intent** of LLM-referred users can be significantly higher. 
    - **Evidence of High Quality**: Comparative analysis of referral traffic (e.g., `utm_source=chatgpt.com` across multiple landing pages such as `live.maestra.ai` and `maestra.ai/tools/web-captioner`) shows that ChatGPT-referred users often exhibit a **~10x higher conversion rate** compared to the site-wide organic average (e.g., ~12% vs ~1.2%). Furthermore, the **Average Order Value (AOV)** from these referrals is observed to be nearly **3x higher**, suggesting that LLM-referred users are not only more likely to convert but also represent higher-value transactions.
    - **Implication**: This suggests that LLM citations act as a "pre-qualified" lead source, making the mechanics of selection (which we study here) commercially critical.

<!-- NOTE: Fan-out definition/instrumentation moved to 1.7.4 to avoid duplication. -->

## 1.6 Citation Mapping & Claim-Level Attribution
*How we precisely map ChatGPT's written claims to their retrieved sources.*

### 1.6.1 The "Claim-to-Link" Forensic Pipeline
- **The Challenge:** ChatGPT's final response text replaces internal citation tokens with generic `[URL]` tags. To understand *why* a link was cited, we must reconstruct the link between the **written claim** and the **retrieved source**.
- **The Solution:** We developed a forensic mapping script (or as Gemini calls them, **grounding supports**) that:
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
- **Important nuance (multi-turn fan-out):** Fan-out queries may be emitted in **multiple batches** across search turns; the run’s fan-out set is the **union** of all observed batches (not just the first).
- **Query drift:** Across multiple runs of the same prompt, the fan-out query set can vary. This drift is a primary driver of stochastic retrieval—different fan-out sets lead to different retrieved sources and therefore different citations/recommendations.
- **How it appears in the raw network stream (multi-turn fan-out signature)**:
  - The response arrives as an event stream (patch/append style) containing repeated tool messages (commonly `role="tool"`, `name="web.run"`).

## 1.8 Anatomy of a Gemini Response (API-Instrumented)
*How the Gemini Vertex AI API exposes grounding metadata compared to ChatGPT’s hidden network stream.*

### 1.8.1 The `groundingMetadata` Schema
Unlike ChatGPT, where we must "scrape" the network stream, Gemini provides structured grounding data in the API response:
- **`webSearchQueries`**: The explicit fan-out query set generated by the model.
- **`groundingChunks`**: The raw snippets of text retrieved from the web (the "injected context").
- **`groundingSupports`**: The precise mapping between specific segments of the response and the `groundingChunks` (the "paper trail").

### 1.8.2 Key Differences in Instrumentation
- **Transparency**: Gemini is "Grounding-First"—it exposes the raw chunks it read, whereas ChatGPT only exposes the final URL and a snippet.
- **Segment-Level Attribution**: Gemini attributes every sentence/segment to a specific chunk index, allowing for a much higher resolution of fidelity analysis.
- **Vertex Redirects**: Gemini uses internal redirect URLs (e.g., `vertexaisearch.cloud.google.com/...`) which must be resolved to find the original domain, a step we automated in our pipeline.

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

## 1.9 Content DNA Enrichment (LLM-as-a-Labeler)
*How we transformed raw URLs into structured data for selection bias analysis.*

### 1.9.1 The Labeling Pipeline
To quantify "selection drift," we needed to move beyond URLs and domains. We developed an automated enrichment pipeline using **GPT-5-mini** as a structured labeler:
1.  **Content Extraction**: Raw HTML was fetched and converted to clean markdown/text.
2.  **Schema-Driven Labeling**: The LLM was prompted to evaluate each page against a strict 20-field schema, including:
    *   **Page Type**: `listicle`, `product_page`, `documentation`, `forum_ugc`, etc.
    *   **Content Format**: `best_of_list`, `landing_page`, `comparison_matrix`, etc.
    *   **Structural Features**: `has_tables`, `has_numbered_lists`, `has_pros_cons`.
    *   **Qualitative Scores**: `promotional_intensity_score`, `expertise_signal_score`, `readability_score`.
3.  **Validation**: A subset of labels was manually audited to ensure the LLM labeler correctly distinguished between vendor-owned landing pages and independent editorial listicles.

### 1.9.2 Enrichment Coverage & Label Distribution (Study URL Universe)
To make the drift analyses defensible, we first measured how much of the URL universe was successfully enriched.

- **Enriched URLs:** 11,925 / 11,929 (**~100%**)  
- **Unlabeled URLs:** 4

**Type distribution (enriched URLs):**

| Type | Count | Share (%) |
| :--- | ---: | ---: |
| **product_page** | 4,125 | **34.6%** |
| **listicle** | 3,994 | **33.5%** |
| app_store_listing | 779 | 6.5% |
| news_article | 609 | 5.1% |
| editorial_article | 547 | 4.6% |
| forum_ugc | 458 | 3.8% |
| other | 422 | 3.5% |
| reference | 391 | 3.3% |
| documentation | 252 | 2.1% |
| marketplace_directory | 213 | 1.8% |

**Tone distribution (enriched URLs):**

| Tone | Count | Share (%) |
| :--- | ---: | ---: |
| **promotional** | 8,193 | **68.7%** |
| **neutral_informational** | 2,410 | **20.2%** |
| salesy | 636 | 5.3% |
| opinionated | 494 | 4.1% |
| academic_technical | 186 | 1.6% |

**Interpretation**:
- The candidate pool is dominated by **product pages + listicles** (~68% combined), so any “listicle uptake” vs “de‑listicling” behavior is operating on a realistically listicle-heavy menu.
- The web’s commercial surface for these prompts is overwhelmingly **promotional**; this motivates our later tone/structure drift analysis (what gets cited vs merely available).

---

# Part 2: Core Findings

## 2.1 Citation Overlap Analysis

### 2.1.1 The Numbers (Global Overlap & Provider Discrepancy)
We analyzed the overlap between LLM citations and the underlying search index (Bing/Google) across 237 runs. This analysis reveals a significant discrepancy in search provider usage between account types, aligning with OpenAI's official documentation.

| Metric | GPT Enterprise (Bing-centric) | GPT Personal (Multi-provider) | Gemini (Google-centric) |
| :--- | :--- | :--- | :--- |
| **Total Cited Links** | 1,637 | 1,839 | 1,651 |
| **Total Additional Links** | 2,820 | 4,506 | - |
| **Bing Overlap (Cited)** | **81.3%** | **67.6%** | - |
| **Bing Overlap (Additional)** | **86.3%** | **56.3%** | - |
| **Google Overlap (Cited)** | **27.8%** (Control) | **64.6%** | **77.7%** |
| **Google Overlap (Additional)** | **20.7%** (Control) | **52.1%** | - |
| **Total Index Coverage** | **83.7%** (Bing+Google) | **80.6%** (Bing+Google) | **77.7%** (Google) |
| **"Invisible" (Missing)** | **16.3%** | **19.4%** | **22.3%** |

#### Gemini: Global Citation DNA Distribution (Cited set only)
To connect overlap/visibility to content selection, we also summarize the DNA distribution of **Gemini’s cited URLs**:

| Type | Count | Share (%) |
| :--- | ---: | ---: |
| **listicle** | 886 | **56.0%** |
| **product_page** | 355 | **22.4%** |
| other | 151 | 9.5% |
| news_article | 53 | 3.4% |
| documentation | 33 | 2.1% |
| comparison_article | 32 | 2.0% |
| marketplace_directory | 31 | 2.0% |

| Tone | Count | Share (%) |
| :--- | ---: | ---: |
| **promotional** | 1,058 | **66.9%** |
| **neutral_informational** | 518 | **32.7%** |
| opinionated | 6 | 0.4% |

#### Key Observations on Provider Strategy:
- **GPT Enterprise: The Bing Standard**: Consistent with OpenAI's [Enterprise documentation](https://help.openai.com/en/articles/10093903-chatgpt-search-for-enterprise-and-edu), which explicitly names Bing as the search provider, we see an **81.3% overlap** with the Bing index. We used Google SERP as a **control group** here, which only yielded a 46.3% overlap, confirming that Enterprise retrieval is heavily optimized for Bing.
- **GPT Personal: The Multi-Provider Shift**: OpenAI's [general documentation](https://openai.com/index/introducing-chatgpt-search/) describes ChatGPT search as leveraging "third-party search providers" (plural). Our data confirms this: GPT Personal shows a much higher affinity for **Google (84.8%)** than Bing (67.6%), and achieves its highest coverage (**88.5%**) only when combining both indices.
- **The "Google Jump" (Enterprise vs. Personal)**: We observe a massive **38.5 percentage-point increase** in Google SERP overlap when moving from Enterprise (46.3%) to Personal (84.8%) accounts. This suggests that while Enterprise is "locked" to the Bing index for compliance/contractual reasons, the Personal account type has shifted to a Google-primary or multi-index retrieval strategy, significantly altering the "Menu" of available sources.
- **The "Visibility Gap" Resolution**: By expanding our search depth to **Rank 200 (Deep Hunt)**, we reduced the "Invisible Citation" rate from ~35% down to **11-22%**, proving that most "missing" citations are simply buried deep in the SERP.
- **First-Query Bias**: Gemini exhibits a massive dependency on the **first fan-out query (37.1%)**, with a steep drop-off for subsequent queries (Q2: 18.1%, Q3: 11.6%). GPT shows a more balanced distribution across its 50/50 fan-out split.

### 2.1.2 The "Visibility Gap" & The Nature of Invisible Links
- **The "Invisible" Citation Problem**: Despite our **Deep Hunt (Rank 200)** methodology, a persistent subset of citations remains "invisible" to both Bing and Google search indices.
    - **GPT Enterprise**: ~18.7% invisible.
    - **GPT Personal**: **11.5%** invisible.
    - **Gemini**: **22.3%** invisible.
- **The "Long Tail" of Retrieval**: Our page distribution analysis shows that citations are not just concentrated on Page 1. We observe a significant "Long Tail" where matches continue deep into the SERP (Page 10-16). 
    - **Truncation Artifact**: The sharp drop-off at Page 17 (only 5-6 matches) is an artifact of our **Rank 200 cap**. This suggests that if we had searched even deeper (e.g., Rank 500), the "Invisible" rate would likely drop even further, potentially below 5-10%.
- **Top Invisible Domains (GPT Enterprise)**: Dominated by high-authority reference and news sites:
    - `en.wikipedia.org` (116)
    - `arxiv.org` (83)
    - `theverge.com` (48)
- **Top Invisible Domains (GPT Personal)**: Shows a shift toward community and platform-specific content:
    - `reddit.com` (216)
    - `apps.apple.com` (139)
    - `chromewebstore.google.com` (54)
- **Key Conclusion**: The "Visibility Gap" is primarily a **retrieval depth and UI issue**. LLMs have high-throughput access to search indices that allow them to surface content that traditional search UIs suppress. The fact that we still find matches at Rank 190+ proves that ChatGPT is "hunting" in the deep tail of the web, far beyond where any human user would paginate.

---

## 2.2 Position Bias & Page Distribution
*Quantifying how search engine ranking (the "Menu" position) influences the final citation (the "Order").*

### 2.2.1 Page-Level Distribution (The "Long Tail" of Retrieval)
Our analysis of 237 runs reveals that LLMs do not just "scrape the surface" of the search results but dig deep into the SERP pages.

| Page Index | GPT Enterprise Matches | GPT Personal Matches |
| :--- | :--- | :--- |
| **Page 1** | **1,468** | **521** |
| Page 2 | 333 | 345 |
| Page 3 | 656 | 663 |
| Page 4 | 692 | 602 |
| Page 5 | 641 | 667 |
| Page 6 | 560 | 579 |
| Page 7 | 453 | 590 |
| Page 8 | 437 | 480 |
| Page 9 | 312 | 433 |
| Page 10 | 271 | 426 |
| Page 11 | 248 | 391 |
| Page 12 | 202 | 327 |
| Page 13 | 191 | 293 |
| Page 14 | 166 | 286 |
| Page 15 | 140 | 264 |
| Page 16 | 103 | 204 |

- **The "Page 1" Elasticity Problem**: We explicitly avoid defining Page 1 as a fixed "Rank 1-10" range. In modern search engines (especially Bing), the length of the first page is highly variable, often truncated or expanded based on the presence of rich snippets, ads, and vertical blocks.
- **The "Page 2 Dip" & Index Volatility**: We observe a curious drop in matches on Page 2 (333-345 matches) compared to Page 1 and Pages 3-5. This is likely an artifact of **Bing index volatility** rather than a deliberate model preference. Qualitative inspection of Bing's "deep" results reveals significant "noise" and irrelevant content across all pages, but Page 2 appears particularly inconsistent in our dataset, often containing transitional or low-signal results that the model bypasses in favor of more stable "deep" candidates found on subsequent pages.
- **The "Deep Hunt" Confirmation**: The fact that we see hundreds of matches on Pages 4-10 proves that LLMs are heavily utilizing results that are effectively invisible to human searchers who rarely paginate past the first elastic page.
- **Truncation Artifact**: The sharp drop-off at Page 17 is an artifact of our **Rank 200 cap**, suggesting the actual retrieval window extends even further.

### 2.2.2 Intra-Page Position Bias (The "Rank 1" Effect)
Even within Page 1, there is a massive bias toward the very first organic result.

#### GPT Personal: Google Match Distribution (Prompt-Scoped)
Analysis of where GPT Personal citations appear in the prompt's specific Google SERP.

| Result Type | Page | Position | Matches |
| :--- | :--- | :--- | :--- |
| **organic** | **1** | **1** | **241** |
| organic | 1 | 2 | 167 |
| organic | 1 | 3 | 183 |
| organic | 1 | 4 | 144 |
| organic | 1 | 5 | 142 |
| organic | 1 | 6 | 143 |
| organic | 1 | 7 | 129 |
| organic | 1 | 8 | 123 |
| organic | 1 | 9 | 68 |
| organic | 1 | 10 | 51 |
| organic | 2 | 1 | 72 |
| organic | 2 | 2 | 80 |
| organic | 2 | 3 | 82 |
| organic | 2 | 4 | 59 |
| organic | 2 | 5 | 68 |
| organic | 2 | 6 | 68 |
| organic | 2 | 7 | 51 |
| organic | 2 | 8 | 61 |
| organic | 2 | 9 | 35 |
| organic | 2 | 10 | 44 |
| related_question | 2 | 1 | 29 |
| related_question | 2 | 2 | 17 |
| video | 2 | 1 | 4 |
| discussion | 2 | 2 | 1 |

#### Gemini: Google Match Distribution (Grounding Chunks)
Analysis of where Gemini citations appear in the prompt's specific Google fan-out query results.

| Result Type | Page | Position | Matches |
| :--- | :--- | :--- | :--- |
| **organic** | **1** | **1** | **124** |
| organic | 1 | 2 | 123 |
| organic | 1 | 3 | 96 |
| organic | 1 | 4 | 102 |
| organic | 1 | 5 | 89 |
| organic | 1 | 6 | 80 |
| organic | 1 | 7 | 87 |
| organic | 1 | 8 | 79 |
| organic | 1 | 9 | 57 |
| organic | 1 | 10 | 37 |
| organic | 2 | 1 | 25 |
| organic | 2 | 2 | 16 |
| organic | 2 | 3 | 17 |
| organic | 2 | 4 | 14 |
| organic | 2 | 5 | 23 |
| organic | 2 | 6 | 17 |
| organic | 2 | 7 | 22 |
| organic | 2 | 8 | 24 |
| organic | 2 | 9 | 18 |
| organic | 2 | 10 | 13 |
| **video** | **1** | **1** | **40** |
| video | 1 | 2 | 21 |
| video | 1 | 3 | 13 |
| related_question | 1 | 0 | 9 |
| discussion | 1 | 0 | 2 |

- **The "Rank 1" Dominance**: Both models show a distinct peak at Organic Rank 1.
- **Gemini's Video Affinity**: Gemini shows a significant number of matches in **Video** results (**40 matches at Rank 1**), which is almost entirely absent in GPT's grounding.
- **PAA (Related Questions) Integration**: Both models occasionally ground in "People Also Ask" blocks, though it remains a minor source compared to organic links.

---

## 2.3 Cited vs. Additional Links Comparison

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
   - Links in **Bing Page 1** (variable-size SERP page; see `2.2.1`) that ChatGPT did NOT cite
   - Compare their DNA to cited links
   - Hypothesis: Ignored links are more `salesy`, lower `expertise_signal_score`

### Data Fields to Compare:

| Field                         | Cited Links | Additional Links | Page 1 Ignored |
| ----------------------------- | ----------- | ---------------- | -------------- |
| `has_tables` (pct)            | 21.0% / 19.9% | 23.9% / 22.9%   | 23.0% / 23.9%  |
| `has_numbered_lists` (pct)    | 56.4% / 45.5% | 61.5% / 46.8%   | 57.5% / 59.7%  |
| `has_bullet_points` (pct)     | 74.7% / 69.4% | 81.4% / 69.1%   | 80.7% / 82.4%  |
| `has_pros_cons` (pct)         | 17.7% / 19.3% | 25.3% / 22.4%   | 23.3% / 24.7%  |
| `tone` (top)                  | promo (70.4%) / promo (72.1%) | promo (70.9%) / promo (66.5%) | promo (72.7%) / promo (74.2%) |
| `promotional_intensity_score` (mean) | 3.28 / 3.32 | 3.11 / 3.15 | 3.20 / 3.23 |
| `expertise_signal_score` (mean)      | 3.58 / 3.78 | 3.57 / 3.72 | 3.65 / 3.61 |
| `spamminess_score` (mean)            | 0.26 / 0.26 | 0.33 / 0.33 | 0.29 / 0.30 |
| `readability_score` (mean)           | 4.05 / 4.06 | 4.03 / 3.98 | 4.05 / 4.05 |
| `type` (top)                  | product_page (45.4%) / product_page (42.2%) | listicle (40.8%) / listicle (34.2%) | product_page (40.8%) / product_page (42.1%) |

*Format note:* values are shown as **Enterprise / Personal**. “Page 1 ignored” is computed on **unique URLs** on Bing `page_num=1` that are **not cited** (per run, de-duplicated across runs). In our dataset, this bucket has substantial missing DNA labels because not all Bing Page‑1 results were fetched/labelled (Enterprise: 812/1660 labelled; Personal: 648/1394 labelled).

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

- **Operational definition (“hidden zone”)**: a **cited URL** that appears in Bing, but only at **Rank 11–30** (beyond what many users treat as “Page 1”).  
- **GPT Enterprise**: **388 / 1,637 (23.7%)** of cited occurrences were found in Bing **Rank 11–30**.  
- **GPT Personal**: **326 / 1,839 (17.7%)** of cited occurrences were found in Bing **Rank 11–30**.
- These links were **not visible** to a human scrolling through Bing normally
- ChatGPT's API access bypasses the UI limitations

### Type Distribution of Invisible Citations:

We separate two notions that are easy to conflate:

- **Bing‑invisible (Bing-only)**: cited URLs **not found in Bing ≤ 200** (our Rank‑200 cap).
- **Truly invisible (Bing+Google control)**: cited URLs **not found in Bing ≤ 200** **and** **not found in Google** (SerpApi control for the same run).  
  *This matters for GPT Personal, which shows high Google affinity; otherwise “Bing‑invisible” overstates how much is actually missing from the combined index surface.*

Below we report **Truly invisible (Bing+Google control)**, computed on **unique cited URLs** (not occurrences).

**GPT Enterprise truly invisible cited URLs (N=147):**

| Type | Count | % of Invisible |
| :--- | ---: | ---: |
| reference | 44 | 29.9% |
| product_page | 37 | 25.2% |
| news_article | 21 | 14.3% |
| listicle | 21 | 14.3% |
| editorial_article | 13 | 8.8% |
| documentation | 4 | 2.7% |
| app_store_listing | 4 | 2.7% |
| review_article | 1 | 0.7% |
| forum_ugc | 1 | 0.7% |
| other | 1 | 0.7% |

**GPT Personal truly invisible cited URLs (N=218):**

| Type | Count | % of Invisible |
| :--- | ---: | ---: |
| listicle | 65 | 29.8% |
| product_page | 59 | 27.1% |
| reference | 26 | 11.9% |
| app_store_listing | 24 | 11.0% |
| news_article | 17 | 7.8% |
| editorial_article | 14 | 6.4% |
| documentation | 4 | 1.8% |
| other | 3 | 1.4% |
| forum_ugc | 3 | 1.4% |
| review_article | 1 | 0.5% |
| marketplace_directory | 1 | 0.5% |
| comparison_article | 1 | 0.5% |

---

### 2.4 Selection Drift: The "Menu vs. Order" Problem
Analysis of why certain results are selected from the "Menu" (retrieved set) while others are ignored.

#### 2.4.1 Intra-Listicle Selection Drift (Feature Lift)
When the model retrieves multiple listicles, it exhibits a measurable preference for specific structural and content features. The following table summarizes the **Weighted Average Drift (percentage point lift)** for listicles only, as reported in `data/enrichment/listicle_drift_report.txt`.

| Feature | Gemini (Google T10) | GPT Personal (Google T10) | GPT Personal (Bing P1) | GPT Enterprise (Bing P1) |
| :--- | :---: | :---: | :---: | :---: |
| `has_tables` | +2.35pp | **+12.23pp** | +2.25pp | +3.64pp |
| `is_current_year_2026` | -4.01pp | **+4.48pp** | **+8.58pp** | -4.64pp |
| `has_numbered_lists` | +1.85pp | +2.20pp | -2.90pp | +7.34pp |
| `has_bullet_points` | +1.74pp | +5.74pp | -8.82pp | +3.29pp |
| `has_pros_cons` | +1.46pp | +3.38pp | -9.17pp | -0.60pp |
| `has_clear_authorship` | **+6.16pp** | +1.83pp | +2.20pp | -3.57pp |
| `freshness_cue_strength`| +1.44pp | **+6.31pp** | **+11.97pp** | +2.15pp |

- **The "Table Premium"**: GPT Personal shows a massive **+12.2pp lift** for listicles containing tables when selecting from Google results.
- **Freshness Steering**: GPT Personal is highly sensitive to freshness cues (**+11.9pp lift** on Bing), while Gemini and Enterprise show much lower or even negative affinity for these markers globally.
- **Authorship as a Gemini Signal**: Gemini shows the strongest preference for listicles with clear authorship (**+6.16pp lift**), a signal that is much weaker or negative in GPT models.

#### 2.4.2 Global Type Drift (De-Listicling)
Across all retrieved links, we observe a consistent "graduation" effect where models prefer primary product pages over the listicles that may have recommended them.

| Account Type | `type=product_page` Lift | `type=listicle` Lift |
| :--- | :---: | :---: |
| **GPT Enterprise** | **+16.5 pp** | -8.5 pp |
| **GPT Personal** | **+18.5 pp** | -9.4 pp |

- **Interpretation**: Listicles serve as the "discovery layer" in retrieval, but the model's selection filter heavily favors citing the **primary vendor page** (Product Page) in the final response.

### 2.4.3 Rank Distribution Analysis
*Talk about links below 150, show distribution.*

### 2.4.1 Histogram: Where ChatGPT Citations Appear in Bing
- X-axis: Bing Rank (1-200+)
- Y-axis: Number of Citations Found

### 2.4.2 Expected Findings:
- Peak at Rank 1-5 (some overlap)
- Sharp drop at Rank 10 (the "Page 1 Cliff")
- Flat, uniform distribution from Rank 11-150 ("Linearity Collapse")
- **Long tail beyond 150** (we acknowledge we didn't go deeper)

### 2.4.3 Selection Drift: The "Freshness Paradox"
Analysis of why certain results are selected from the "Menu" (retrieved set) while others are ignored. We analyzed how "Freshness" (years, update cues, explicit dates) influences selection.

- **Global Anti-Freshness Bias**: Across all retrieved links, "Fresh" pages (those with explicit dates or 2024+ years) actually show a **negative lift** in selection (Enterprise: -9.2pp for explicit dates).
- **The Listicle Confound**: This is primarily because Listicles (which are cited less than Product Pages) are the most likely to have freshness markers.
- **Intra-Listicle Freshness**: When looking *only* at listicles, the bias disappears or reverses. For Enterprise listicles, an "Updated" cue provides a **+7.5pp lift** in selection probability.
- **Implication**: The model values freshness within a category (e.g., choosing the most recent listicle), but its primary selection driver remains **Type** (Product Page > Listicle).

### 2.4.4 Limitations Section:
- We stopped at Rank 200 for practical reasons
- Based on the uniform distribution pattern, we estimate X% more citations would be found at Rank 201-300
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
- These are the "Buried Truth" links (ChatGPT cited, Bing hid at Rank 31-200)
- Compare their DNA to:
  1. Top 10 cited links
  2. Top 10 ignored links

---

# Part 4: Research Gaps & Future Work

1. **Deeper Crawling:** We stopped at Rank 200; going to 300+ might find more matches.
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
| `is_grounded_deep`            | bool | Found in Deep Hunt (Rank 31-200)                     |
| `is_strict_match`             | bool | Exact URL match to citation                          |

---

# Appendix B: Key Terms

| Term                   | Definition                                                                                                                                          |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Extractive Nature**  | The observation that ChatGPT's recommendations are primarily extracted and synthesized from cited sources, rather than generated from training data |
| **UI Suppression**     | Bing's interface hiding relevant results behind pagination loops, inconsistent result counts, and UI clutter                                        |
| **Page 2 Cliff**       | The sharp drop in result relevance and visibility after Bing's Top 10                                                                               |
| **Linearity Collapse** | The breakdown of meaningful page numbering in Bing results (Page 2 ≠ Rank 11-20)                                                                    |
| **Grounded Deep**      | Citations that ChatGPT used which were found in Bing but only at Rank 31-200                                                                        |
| **Truly Invisible**    | Citations that ChatGPT used which were never found in Bing even at Rank 200                                                                         |
| **Content DNA**        | The structural characteristics of a page (tables, lists, headings) that make it "extractable"                                                       |
| **Domain Match**       | When Bing found a page from the same domain but different URL than what ChatGPT cited                                                               |
| **Strict Match**       | When Bing found the exact same URL that ChatGPT cited                                                                                               |
| **Grounding**          | The process of anchoring an LLM's response in real-time, verifiable web data to reduce hallucinations and ensure factual accuracy                   |

---

*Document generated: January 2026*
