# Thesis Research Outline
## Grounding Behavior in LLM‑Mediated Commercial Search: How ChatGPT and Gemini Select and Cite Web Sources

**Author:** [Your Name]
**Date:** January 2026
**Status:** Research Notes / Working Draft

---

**What we empirically observe and measure (high-level):**
- **Cross-model grounding**: Gemini vs. ChatGPT
- **Cross-deployment grounding**: ChatGPT **Personal vs Enterprise**
- **Rank effects**: how grounding/citation choices relate to **SERP position distributions** (position bias)
- **Selection bias in sources**: differences between the **available menu** (Top‑N SERP) vs the **selected order** (cited set), measured via **Content DNA enrichment** of cited and non-cited URLs
- **Visibility gaps**: "invisible/shadow" citations (cited URLs missing from the defined Top‑N baseline), analyzed separately from within-SERP drift

## Core Research Question
**RQ1:** *How does grounding behavior manifest in LLM-generated product recommendations, and how does it vary across conditions we can observe (deployment context and/or model)?*

### Operational definition (what "grounding behavior" means in this thesis)
Grounding behavior is the measurable pipeline from **retrieval → selection → citation → final text**, using observable artifacts:
- **Retrieved candidate set** (where available): sources the system pulled/considered
- **Selected set**: sources that "survive" selection (cited/attached)
- **Claim linkage**: which textual claims map to which sources (claim-to-link mapping)
- **SERP support**: whether selected sources are actually present in external SERPs (Bing/Google)
- **Source-to-output fidelity**: whether products mentioned in retrieved listicles are carried into the final recommendations

### Sub-questions (decompositions of RQ1, not separate topics)
- **RQ1a (selection + visibility)**: How do **cited vs additional vs rejected/invisible** sources differ in domain/type, and how does this differ by **enterprise vs personal** runs on chatGPT results?
- **RQ1b (external support)**: How often do selected citations appear in **Top‑N SERPs** (Bing/Google overlap; Gemini "survival" in Top‑20)?
- **RQ1c (selection bias & DNA)**: Does the model exhibit a statistically significant preference for specific **Content DNA features** (e.g., tables, numbered lists, freshness) when selecting from the retrieved "Menu," and how does this preference vary between **GPT Personal, GPT Enterprise and Gemini**?
- **RQ1d (listicle uptake / fidelity)**: When listicles are retrieved, which listicle-mentioned products are **selected vs ignored** in the final response (uptake rate, rank bias, host-bias), and how does this differ by run type?

### Role of external systems (clarify scope)
- **Bing**: baseline "human web" retrieval/ranking surface used as a **measurement instrument** for rank/visibility and "visibility gaps" (**Top‑200**).
- **Google (SerpApi)**: control baseline for Gemini fan-out queries and sensitivity checks (**Organic-only** vs including non-organic result types like **Video/PAA/Discussions**).
- **Gemini**: optional cross-model baseline for grounding mechanics (has explicit `groundingMetadata` and claim-support mapping); not an enterprise/personal split unless we create our own conditions.

---

# Part 1: Introduction & Motivation

## 1.1 Market Context & Motivation (Ahrefs Benchmark)

- **The Macro Shift (8-Month Trend):** According to data from [Ahrefs (ChatGPT vs. Google)](https://chatgpt-vs-google.com/) analyzing **74,752 websites** between **June 2025 and January 2026**, total search traffic across the panel dropped by **7.5%** (from 494M to 457M visits).
- **The AI Growth Engine:** In the same timeframe, referral traffic from AI chatbots grew by **27%** (from 2.9M to 3.7M visits).
- **The "SEO is Not Dead" Reality:** While AI traffic is growing rapidly, traditional search still dominates the referral landscape by orders of magnitude. As noted by **Tim Soulo (CMO at Ahrefs)**, the strategic mistake is not ignoring AI, but abandoning SEO—our study proves that **AI grounding is parasitic on search results**, meaning SEO remains the prerequisite for AI visibility.
- **Thesis Motivation:** This study focuses on the **micro-level mechanics** of this transition: how these AI assistants "ground" their answers in the very search results that currently dominate the market. We measure the *dependency* of generation on search.

## 1.2 Theoretical Framework: From SEO to GEO

*Tracing the evolution of information retrieval from keyword matching to generative synthesis.*

### 1.2.1 The Evolution of Search Optimization
- **Traditional SEO (Search Engine Optimization):** Focus on keyword density, backlink authority, and technical performance to rank in a 10-blue-link UI.
- **The Convergence of AEO & GEO:** These terms are often used interchangeably to describe the shift toward optimizing content for direct synthesis.
    - **AEO (Answer Engine Optimization):** Focuses on being the "single best answer" for voice assistants and featured snippets.
    - **GEO (Generative Engine Optimization):** Focuses on being cited and synthesized by LLMs in conversational RAG (Retrieval-Augmented Generation) workflows.

### 1.2.2 The Genesis and Evolution of RAG (Retrieval-Augmented Generation)
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

### 1.2.3 Sam Altman's "Tiny Model" Vision
- Quoting the framework: *"The perfect AI is a very tiny model with superhuman reasoning... It doesn't need to contain the knowledge - just the ability to think, search, simulate, and solve."*
- **Thesis Connection:** This vision confirms that the future of search is not the death of the web, but the transformation of the web into a **distributed memory layer** for AI orchestrators.

### 1.2.4 The Economic & Technical Necessity of Retrieval
- **The Compute Wall:** Inference (LLM "thinking") is exponentially more expensive than Retrieval (traditional search indexing).
- **The Scaling Limit:** You cannot train a model every hour to keep up with the web. Retrieval is the only scalable solution for real-time information.
- **Thesis Argument:** GEO is not a replacement for SEO; it is **SEO's final form**. Search is the "cheaper, better, faster" engine that feeds the LLM's reasoning core.

### 1.2.5 The Structural Pivot: From "Search" to "Grounding"
- **The August 11, 2025 Retirement:** Microsoft officially decommissioned the legacy Bing Search APIs, forcing a migration to **"Grounding with Bing Search"** as part of the Azure AI Agents ecosystem.
- **Defining "Grounding":** Unlike traditional search ranking (which optimizes for human click-through rates), **Grounding** is the process of anchoring an LLM's response in real-time, verifiable web data to reduce hallucinations and ensure factual accuracy.
- **Retrieval Asymmetry:** This shift codifies the "Two-Web" reality:
    1. **The Human Web (Ranking):** Optimized for SEO, ads, and engagement.
    2. **The Agent Web (Grounding):** Optimized for information density, extraction potential, and factual synthesis.
- **Thesis Connection:** Our discovery that ChatGPT citations are often buried at **Rank 31-200** in the Human Web proves that the "Grounding" engine uses a different set of priorities than the "Ranking" engine.

## 1.3 The Commercial Catalyst for RAG

*Why product recommendations are the "Front Line" of Generative Search.*

### 1.3.1 Industry Benchmark: ChatGPT Web Search Trigger Rates (Profound Analysis)
*To contextualize our study, we refer to industry-wide telemetry from **Profound** (captured as of Jan 6, 2026), which analyzes trigger rates across 667,000 real-user conversations.*

![ChatGPT Web Search Trigger Rate (by Intent)](1767882183827.jpg)

- **Commercial Intent as the Primary Driver**: Web search is triggered in **53.51% of Commercial queries**, compared to only 18.73% for Informational and 8.88% for Generative queries.
- **Overall Trigger Rate**: Across all intents, the baseline trigger rate is **17.41%**.
- **Thesis Alignment**: Our decision to filter for **high commercial intent** (product recommendations) aligns with this industry data, as this is the segment where RAG/Grounding is most active and commercially impactful.
- **The "Winnable" Arena:** Because commercial intent requires real-time data (pricing, availability, reviews), it is the primary driver for RAG adoption. This makes product recommendations the most critical area for studying the shift from SEO to GEO.

### 1.3.2 The GEO Industry Landscape: Citation Tracking & "Share of Model"
- **The Rise of GEO Analytics**: Emerging platforms (e.g., **Profound**, **Peec.ai**) are shifting the industry from "Share of Voice" (traditional search) to "Share of Model" (generative search).
- **The Listicle as the "Critical Node"**: Our research places extreme emphasis on listicles because they are the primary "on-ramp" for product citations. In the GEO ecosystem, being cited in a top-tier listicle is no longer just about referral traffic; it is a prerequisite for being "seen" by the RAG orchestrator.
- **Quantifying the Value of a Citation**: By measuring the **Bias Multiplier** (how much more likely a cited product is to be selected vs. a random one) and **Host Exclusion** (the risk of being ignored if you are the host), we provide the first empirical framework for what these citation-tracking tools are actually measuring.
- **The "Gold Rush" of AEO/GEO:** The rapid rise of companies like **Profound** and **Perplexity AI** underscores the industry's recognition that the "Answer Engine" is the next multi-billion dollar shift in tech.
- **Venture Capital Validation:** A landmark moment occurred on August 12, 2025, when **Profound raised $35 million in a Series B round led by Sequoia Capital**, bringing its total funding to $58.5 million ([Fortune, 2025](https://fortune.com/2025/08/12/ai-search-startup-profound-raises-35-million-series-b-sequoia/)).
- **The "Salesforce of AI Search":** This funding round validated the concept of building a "generational company" centered on helping brands monitor and optimize for how they surface in AI-generated responses across models like ChatGPT, Gemini, and Claude.
- **The European Challenger — Peec AI:** In November 2025, Berlin-based **Peec AI** raised **$21 million in a Series A led by Singular**, bringing its total funding to $29 million ([TechCrunch, 2025](https://techcrunch.com/2025/11/17/as-consumers-ditch-google-for-chatgpt-peec-ai-raises-21m-to-help-brands-adapt/)). Founded in early 2025, Peec grew to **$4M ARR in 10 months** with 1,300 companies on its platform (including ElevenLabs, Chanel, and Axel Springer), explicitly positioning itself in the **Generative Engine Optimization (GEO)** category. The speed of Peec's traction—alongside Profound's Sequoia-backed round—confirms that AI search analytics is rapidly consolidating into a recognized market category, not a niche experiment.
- **The Hype vs. Reality:** While the hype is centered on "killing search," our research suggests the reality is a **deeper integration** where search becomes the infrastructure for AI.
- **The High-Intent Conversion Hypothesis**: Preliminary industry observations suggest that while AI-driven traffic volume is currently lower than traditional search, the **conversion rate** and **purchase intent** of LLM-referred users can be significantly higher — implying that LLM citations act as a "pre-qualified" lead source, making the mechanics of selection (which we study here) commercially critical.

## 1.4 Retrieval Environments & Deployment Contexts
*Defining the specific interfaces and constraints of the models under study.*

### 1.4.1 ChatGPT: UI-Based Network Instrumentation (Personal vs. Enterprise)
- **Deployment Context**: We study ChatGPT as a consumer-facing product accessed via the standard web interface (`chatgpt.com`).
- **Instrumentation Method**: Because OpenAI does not expose grounding metadata (fan-out queries, retrieved snippets) via its public API, we used **Network Payload Inspection** (Chrome DevTools protocol) to capture the raw event stream of the production UI.
- **Session Isolation**: All ChatGPT prompt runs were conducted in **Temporary Chat** mode to prevent conversation history and memory from influencing retrieval or generation behavior across runs.
- **Personal vs. Enterprise**:
    - **Personal**: Executed on a **ChatGPT Plus** subscription in the user's **personal workspace**. OpenAI's [general documentation](https://openai.com/index/introducing-chatgpt-search/) describes ChatGPT search as leveraging "third-party search providers" (plural), leaving the exact provider mix unspecified.
    - **Enterprise**: Executed through a **ChatGPT Enterprise organization account**. OpenAI's [Enterprise documentation](https://help.openai.com/en/articles/10093903-chatgpt-search-for-enterprise-and-edu) explicitly names **Bing** as the search provider, restricting retrieval to the Azure/Bing ecosystem.

### 1.4.2 Gemini: API-Based Grounding (Vertex AI)
- **Deployment Context**: Unlike ChatGPT, Gemini was studied via the **Vertex AI / Google AI Studio API** (Gemini 1.5 Pro/Flash).
- **Instrumentation Method**: We utilized the API specifically to access the **`groundingMetadata`** object, which is not fully transparent in the consumer UI.
- **Reliability of Data**: The API provides a 'cleaner' laboratory environment, exposing the exact `groundingChunks` (retrieved snippets) and `groundingSupports` (segment-to-chunk mapping) required for high-fidelity grounding analysis.

---

# Part 2: Methodology & Tools

## 2.1 Data Collection Pipeline

| Component            | Description                                                                      |
| -------------------- | -------------------------------------------------------------------------------- |
| **Queries**          | 79 product recommendation queries × 3 runs each (237 total runs)                 |
| **ChatGPT Data**     | Full responses with inline citations, additional links, and recommended products through chrome dev tool network packet inspection |
| **Bing Data**        | Top 200 results                                                                  |
| **Gemini Data**      | Full `groundingMetadata` (Chunks vs. Supports) + Fan-out Queries                 |
| **Google SERP**      | SerpApi pagination until **≥20 Organic** results are collected (often ~3 pages), with Video/PAA/Discussions retained as diagnostic buckets |
| **Content Fetching** | Node.js fetcher + Browser extension for blocked pages (Master Content Library)   |

### 2.1.1 Selection of the Research Query Set
- **High-Volume Real-World Prompts:** Our dataset consists of **79 unique product recommendation prompts** (e.g., "Best AI video translators", "Top-rated transcription software"), sourced from two platforms: **65 prompts from Profound** (real user conversations with ChatGPT) and **14 prompts from Ahrefs** (high-volume keyword clusters).
- **Methodology for Selection:**
    - **Keyword Clustering:** Using **Ahrefs** to identify high-intent keyword clusters and derive 14 representative prompts from search volume data.
    - **Prompt Volume Analysis:** Leveraging **Profound's** Prompt Volumes feature to select 65 prompts derived from real user conversations with ChatGPT. Note: Profound states that surfaced prompts may be rewritten for anonymity or clarity, so these are representative of real user intent rather than verbatim transcripts.
    - **Deliberate Intent Filtering:** From the broad set of available user prompts, we **deliberately filtered for high commercial intent**. This ensures the study reflects the specific segment of search where AI synthesis is most active and where the "Extractive Nature" of the model is most visible.
    - **Domain Expertise:** Queries were focused on the **AI and Software-as-a-Service (SaaS)** sectors — particularly **speech and language technology** (speech-to-text, live transcription, voice translation, text-to-speech) — a domain where the author has significant professional expertise, allowing for more nuanced qualitative analysis of the "Signal vs. Noise" in results.
- **Experimental Rigor:** Each of the 79 prompts was executed in **3 independent runs** (with a 4th run added only in cases of technical failure or RAG non-triggering) to analyze the consistency and stochastic nature of the retrieval process.

### 2.1.2 Google SERP Result Types (SerpApi): Organic vs Video vs PAA
SerpApi returns Google results in multiple **result_type** buckets (not just "10 blue links"). This matters because overlap numbers can shift depending on what we count as "the SERP."

- **Organic results**: standard web results (our primary control-group baseline).
- **Video results**: often YouTube-heavy; can appear in top positions and inflate "coverage" for topics where ChatGPT cites YouTube.
- **Discussions / forums blocks**: SerpApi often surfaces forum-like "discussions" sections; we retain them as a separate diagnostic bucket (forums / quota etc..).

**Method rule (comparability)**:
- For overlap metrics, we default to **Organic-only** (and treat Video/PAA as separate diagnostic buckets), unless explicitly stated otherwise.
- We keep the non-organic buckets available as a **discussion point** (e.g., "Google surfaces YouTube via Video blocks earlier than Bing"), and as a sensitivity analysis ("organic-only vs organic+video").
- **Pagination rule (how we collected the "Top‑20 Organic" baseline)**: we paginate SerpApi until we have **≥20 Organic** results (not necessarily only the first page). In practice this is often the first ~3 pages, alongside non-organic blocks.

### 2.1.3 Bing SERP Scraping (Browser Extension)

Because Microsoft retired public Bing Search API access on **August 11, 2025** (see `1.2.5`), no stable programmatic API was available for academic SERP collection. We therefore built a **Chrome browser extension** (`tools/Bing Results Scraper`) that scrapes Bing's live consumer UI via DOM interaction.

- **Scrape method**: The extension runs as a Manifest V3 content script that simulates human search interaction — typing queries character-by-character with randomized inter-key delays (10–50 ms), clicking the search button, and waiting for DOM stabilization (result count checked across 3 consecutive iterations before proceeding).
- **Ad filtering**: Organic results are selected via `.b_algo:not(.b_adTop):not(.b_adBottom):not([data-apurl])`. A supplementary `isSponsoredResultElement()` function provides multi-layer ad detection: DOM class markers (`.adsMvCarousel`, `.b_ads1line`, `.ad_em`), text-prefix matching (`/^Sponsored\b/i`), CSS `::before` pseudo-element inspection, and URL-based filtering of known ad-click endpoints (`/aclick`, `/clk`, `/sclk` on `bing.com`). Unresolved Bing redirect URLs (`bing.com/ck/`) are also discarded as probable ads.
- **Pagination to Rank 200**: The extension clicks Bing's native pagination button (`.sb_pagN`) and waits 3 seconds between pages. Each page yields ~10 organic results; 20 pages × 10 results = 200 results per query. Positions are numbered strictly sequentially across pages (not reset per page).
- **URL decoding**: Bing wraps organic URLs in redirect parameters. The extension decodes these via URL-parameter extraction, Base64 decoding (with prefix stripping), and hex-byte fallback. Tracking parameters (`utm_*`, `fbclid`, `gclid`) are stripped to normalize URLs for overlap matching.
- **US proxy**: All Bing scrapes were routed through a **US-based proxy** to match the retrieval environment used for ChatGPT runs (see `2.7.3`), ensuring that localized SERP variation does not inflate or deflate overlap measurements.
- **Extracted fields per result**: `position`, `title`, `url`, `domain`, `displayUrl`, `snippet`, `page_num`. When content extraction is enabled, the extension also fetches each page and extracts full text (up to 20,000 characters), metadata (`canonical_url`, `published_date`, `modified_date`), schema markup types, and table counts.

## 2.2 Methodological Evolution: From Top 30 to "Deep Hunt" (Rank 200)
- **Starting Point (Single-Query, Top 30):** Our study initially used only the **single fan-out query visible in ChatGPT's UI** (the "Searching for..." text) and scraped the **Top 30 Bing results** for each, yielding a **40.3% citation overlap**. At this stage we had no knowledge of the hidden double fan-out mechanism — we assumed the UI-displayed query was the only query issued.
- **The Network Instrumentation Turning Point:** Once we began capturing raw network payloads (see `2.3`), we discovered that ChatGPT always dispatches **two** fan-out queries per search turn, not one. The "Searching for..." text in the UI only surfaces one of them. This meant our initial Bing scrapes were matching against an incomplete query set, understating true overlap.
- **The Discovery of "UI Erasure":** Even after correcting for fan-out, qualitative review using our custom Data Viewer revealed a significant "Visibility Gap." ChatGPT was citing high-quality, relevant pages that were completely missing from the Top 30 human-facing results.
- **The Pivot to Rank 200:** To test whether these citations were truly "invisible" or merely "buried," we expanded our methodology to a **"Deep Hunt" (Rank 200)**.
- **Key Finding of the Pivot:** We discovered that Bing often surfaces the exact pages ChatGPT cites, but hides them deep within pagination loops or beyond the "Page 2 Cliff" (Rank 11+). This methodological shift allowed us to prove that the difference between Search and GenAI is often a **UI and Ranking problem**, not just an indexing one.
- **Why Even Rank 200 May Not Be Enough:** Our page-level distribution data (see `3.2.1`) shows that citation matches do not reach zero at Rank 200 — the long tail continues. Going deeper (Rank 300+) would likely recover additional matches and further shrink the "truly invisible" set, producing a cleaner separation between sources ChatGPT finds via search indices and sources it accesses through other means (parametric memory, direct partnerships, or non-public indices).

### 2.2.1 Bing Pagination Instability (The "Elastic Page 1" Problem)
A critical methodological challenge arose from Bing's inconsistent UI pagination behavior, which we discovered through repeated scrapes of the same query. This instability is partly why the retirement of the Bing Search API (see `1.2.5`, `2.1.3`) is consequential for grounding research: the consumer UI we were forced to scrape is a far noisier baseline than a stable API would have provided.

- **Page 1 Truncation:** Bing's first page of organic results is not a fixed "Top 10." In some scrapes, Page 1 returned as few as **2 organic results** (e.g., for `"free AI tools to translate video"`, only `zeemo.ai` and `airmore.ai` appeared as organic results on Page 1, while subsequent scrapes of the same query minutes later returned `maestra.ai`, `akool.com`, `veed.io`, `happyscribe.com`, and `rask.ai` in the top positions). The rest of the page was filled with ads, Copilot branding, "People also search for" blocks, and video carousels.
- **The "Missing Middle" Problem:** When Page 1 is truncated, the results at ranks 3–7 do not simply shift to Page 2. Instead, they appear to be **dropped entirely** from that particular scrape. Page 2 begins with a different, loosely-indexed set of results that often includes irrelevant content (e.g., PDF translators, image-to-video tools, and unrelated AI generators appearing for a video translation query). Our citation-overlap data corroborates this qualitative observation: Page 1 concentrates the bulk of matches, Page 2 shows a conspicuous dip, and Pages 3+ settle into a gradual decay — the expected long-tail pattern, but at higher match volumes than a tightly indexed SERP would produce. The Page 2 dip in particular stands out as an artifact of loose indexing rather than smooth ranking decay (see `3.2.1`).
- **Implications for Overlap Measurement:**
    1. **Lost overlap (conservative bias):** If our Bing scrape for a given run captured a truncated Page 1, we may have missed legitimate top-ranking results that ChatGPT's retrieval system almost certainly had access to. This means our reported overlap percentages are likely **underestimates** — some citations we classified as "invisible" may have been present in Bing's index at high ranks but absent from our specific scrape due to pagination instability.
    2. **Why Top 200 was necessary:** Because everything after Page 1 is loosely indexed and inconsistent, we needed to scrape deep (Rank 200) not because ChatGPT is truly "deep hunting" at those ranks, but to **compensate for Bing's UI-layer instability** and recover matches that a stable API would have returned in the Top 10–30.
- **The API vs. UI Divergence Hypothesis:** We strongly suspect that ChatGPT does **not** receive the same noisy, truncated pagination that Bing's web UI serves to human users. Bing likely provides its index to ChatGPT via a backend integration that returns a clean, stable ranked list without ads, carousels, or pagination artifacts — the exact mechanism is not publicly documented, but the ranking and filtering logic almost certainly differs from what the consumer UI exposes. This means our Bing-UI-scraped baseline is a **degraded proxy** for what ChatGPT actually sees — further supporting the interpretation that our overlap figures are conservative lower bounds.
- **What This Implies About ChatGPT's Retrieval:** Given that ChatGPT consistently cites high-quality, relevant sources, one of two things must be true: either ChatGPT receives a **cleaner, more stable ranking** from Bing's backend API than what the consumer UI exposes, or the model is doing substantial work to **filter through the same noisy index** and extract signal from noise. Either interpretation underscores the divergence between the human-facing and agent-facing search experiences described in **`1.2.5`**.
- **Contrast with Google (SerpApi):** This instability was not observed in our Google SERP data collected via SerpApi, which returned consistent, stable organic rankings across paginated requests. This asymmetry between Bing's UI instability and Google's API stability is itself a noteworthy finding for researchers attempting to replicate grounding studies.

## 2.3 Anatomy of a ChatGPT Response (Network-Instrumented)
*What exactly we can observe about ChatGPT's retrieval + citation pipeline from captured network payloads.*

### 2.3.1 Pipeline Overview (Methodology)

Our network instrumentation captured raw event-stream payloads from the ChatGPT production UI, revealing a **three-layer pipeline** (Sonic Classifier → Sonicberry Orchestrator → Generation Model) rather than a monolithic model. The detailed architecture, layer descriptions, and observed flow are reported as empirical findings in **`3.1`**. Here we note only the methodological implication: because each layer emits distinct payload fields, we can separately instrument the search-trigger decision, the fan-out query dispatch, and the citation-generation phase.

### 2.3.2 Source Categories We Use (scope)
- **Cited**: sources referenced inline in the generated answer.
- **Additional**: sources retrieved and attached but not referenced inline (still "considered").
- **Rejected**: sources that appeared in the retrieved pool but did not survive selection (not cited, not attached).

### 2.3.3 Search Trigger Instrumentation (the "decision" fields)
We log the system's search-decision artifacts where present (Enterprise streams are richest):
- `sonic_classification_result`: the classifier output used to decide search (e.g., `simple_search_prob`, `complex_search_prob`, thresholds).
- `web_search_triggered`: whether search actually ran.
- `web_search_forced`: whether search was forced (if present).

The full Sonic Classifier configuration (classifier variant, 3-class thresholds, Enterprise vs. Personal divergence, and comparison with external reverse-engineering by Resoneo) is reported as empirical findings in **`3.1.1`**.

### 2.3.4 Fan-Out Queries ("hidden queries") & the `web.run` Agentic Loop
- **Definition**: multiple search queries issued for one user prompt; these expand/reshape retrieval scope.
- **Why it matters**: fan-out sets control which sources are even eligible to be cited.
- **Observable field (network-derived)**: `search_model_queries.queries` (stored as `hidden_queries_json` in our extracted CSV/DB pipeline).

**The `web.run` mechanism (empirically discovered):**
- The generation model (gpt-5-2) calls a tool named `web.run` via the Sonicberry orchestrator (`alpha.sonic_thinky_v1_paid`). Each `web.run` call **always dispatches exactly 2 queries in parallel** — a fixed pair-generation strategy producing one synonym variant and one structural rephrase. Odd query counts (1, 3, 5) are architecturally impossible.
- In the vast majority of runs (**94%**), a single `web.run` call is all that fires — the 2 queries run in parallel and the results are used directly. However, in a small fraction of runs (2.7%), the generation model evaluates the returned results and calls `web.run` again, creating an iterative re-search loop tracked by the `search_turns_count` field.
- **How it appears in the raw network stream (multi-turn fan-out signature)**:
  - The response arrives as an event stream (patch/append style) containing repeated tool messages (`role="tool"`, `name="web.run"`, `author.metadata.source="sonic_tool"`).
  - Each `web.run` message carries `search_model_queries.queries[]` (always length 2) and `search_turns_count` (incrementing 1, 2, 3…).
  - Multi-turn calls may be **chained** (each `parent_id` = previous `web.run`'s `message_id`) or **independent** (different parent).

The empirical distribution of search turns, re-search strategies, query drift, and timing evidence are reported in **`3.1.3`**.

### 2.3.5 Retrieved Candidate Pool (what the model could have used)
We capture the retrieved candidates and their metadata:
- `search_result_groups`: grouped search entries containing `url`, `title`, `snippet`, and `ref_id` (turn/ref index keys).
- **Interpretation**: this is the model's "shortlist menu" prior to selection.

### 2.3.6 Citation Tokens & Claim Mapping (how we attach sources to text)
Two key payload elements enable claim→source reconstruction:
- `content_references`: token spans / citation tokens with `start_idx` / `end_idx` (where citations appear in the output stream).
- `response_text`: the generated text (often streamed via patch/append events).

From these, we build:
- **Claim blocks**: the text segments preceding each citation token (our `claim_text` extraction).
- **Mapped sources**: resolved URLs/titles/snippets by matching `ref_id` keys to `search_result_groups`.

### 2.3.7 What the Network Does *Not* Reveal (critical limitation)
- It does **not** include the exact on-page snippets/chunks that were fetched/inserted into the model context.
- Therefore: our ChatGPT-side "grounding budget" analyses are **output-side proxies** (claim-attributed text), not true input-side snippet budgets.

### 2.3.8 What Happens Next (how this section feeds the thesis)
This "anatomy" motivates the next analytic layers:
- **Overlap & visibility**: compare cited/additional/rejected pools against Bing Top 30 + Deep Hunt and Google SERP controls.
- **Selection bias**: compare Content DNA of Cited vs Additional vs Rejected.
- **Stochasticity**: quantify fan-out drift across runs and resulting citation churn.

### 2.3.9 Network Parameter Glossary (ChatGPT, Network-Instrumented)
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
- **`metadata.search_model_queries.queries[]`**: the model-generated fan-out query list for a search turn (our "hidden queries").
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

## 2.4 Anatomy of a Gemini Response (API-Instrumented)
*How the Gemini Vertex AI API exposes grounding metadata compared to ChatGPT's hidden network stream.*

### 2.4.1 The `groundingMetadata` Schema
Unlike ChatGPT, where we must "scrape" the network stream, Gemini provides structured grounding data in the API response:
- **`webSearchQueries`**: The explicit fan-out query set generated by the model.
- **`groundingChunks`**: The raw snippets of text retrieved from the web (the "injected context").
- **`groundingSupports`**: The precise mapping between specific segments of the response and the `groundingChunks` (the "paper trail").

### 2.4.2 Key Differences in Instrumentation
- **Transparency**: Gemini is "Grounding-First"—it exposes the raw chunks it read, whereas ChatGPT only exposes the final URL and a snippet.
- **Segment-Level Attribution**: Gemini attributes every sentence/segment to a specific chunk index, allowing for a much higher resolution of fidelity analysis.
- **Vertex Redirects**: Gemini's `groundingChunks` do not expose raw URLs — instead they contain internal redirect URLs (e.g., `vertexaisearch.cloud.google.com/...`) that must be followed to discover the actual destination domain. We built a dedicated resolution script (`scripts/resolve_grounding_urls.mjs`) that collects all unique Vertex redirect URLs from the raw response files, follows each redirect via HTTP, and produces a mapping from Vertex URL → resolved destination URL. Some redirects failed to resolve programmatically (e.g., due to timeouts or anti-bot blocks), so unresolved URLs were exported and resolved manually via a browser-based content fetcher. Without this resolution step, no domain-level or overlap analysis would be possible on the Gemini data.
- **Thinking budget**: All Gemini runs in this study used the **minimum thinking budget** available via the API. Higher thinking budgets produce more fan-out queries — the model generates an initial broad query, discovers brands/products from the results, then issues targeted follow-up queries for those specific entities (e.g., `"best free AI video translation tools 2025 2026"` → `"HeyGen free trial video translation"` → `"ElevenLabs video translator free tier limitations"`). This iterative refinement pattern resembles GPT's multi-turn re-search (see `3.1.3`), but is driven by the thinking budget rather than an explicit agentic tool-call loop. Our use of minimum thinking keeps the fan-out count bounded and comparable across runs, but means the study captures the model's baseline retrieval behavior rather than its maximum-depth grounding capability.
- **API vs. Consumer UI gap**: Our Gemini data comes entirely from the Vertex AI API, which provides structured grounding metadata but does not carry IP/locale signals. Inspecting the **Gemini consumer UI** (`gemini.google.com`) via network packet analysis — mirroring our ChatGPT instrumentation approach — could reveal additional signals not exposed in the API, such as locale-driven fan-out rewriting, internal ranking or filtering stages before the `groundingMetadata` is constructed, or differences in fan-out strategy between the consumer product and the API. This remains a potential avenue for future work.

## 2.5 Content DNA Enrichment (LLM-as-a-Labeler)
*How we transformed raw URLs into structured data for selection bias analysis.*

### 2.5.1 The Labeling Pipeline
To quantify selection effects (what gets cited vs. what was available), we needed to move beyond URLs and domains. We developed an automated enrichment pipeline using **GPT-5-mini** and **Gemini Flash 2.5** as structured labelers:
1.  **Content Extraction**: Raw HTML was fetched and converted to clean markdown/text.
2.  **Schema-Driven Labeling**: The LLM was prompted to evaluate each page against a strict 20-field schema, including:
    *   **Page Type**: `listicle`, `product_page`, `documentation`, `forum_ugc`, etc.
    *   **Content Format**: `best_of_list`, `landing_page`, `comparison_matrix`, etc.
    *   **Structural Features**: `has_tables`, `has_numbered_lists`, `has_pros_cons`.
    *   **Qualitative Scores**: `promotional_intensity_score`, `expertise_signal_score`, `readability_score`.
3.  **Validation**: A subset of labels was manually audited to ensure the LLM labeler correctly distinguished between vendor-owned landing pages and independent editorial listicles.

### 2.5.2 Enrichment Logic & Static Overrides
*To ensure efficiency and accuracy, the labeling pipeline uses a hybrid approach of LLM-labeling and static rules for high-volume, well-known domains.*

- **LLM-Labeling (GPT-5-mini)**: Used for general web pages, blogs, and niche product sites to determine structural features (`has_tables`, `has_pros_cons`, etc.).
- **Static Domain Overrides (Skipped Enrichment)**: Known platforms with consistent structural patterns were assigned "pre-made" labels to save quota and ensure consistency:
    - **`reddit.com`**: Automatically labeled as `type=forum_ugc`, `content_format=discussion_thread`, `tone=opinionated`.
    - **`en.wikipedia.org`**: Automatically labeled as `type=reference`, `content_format=encyclopedic`, `tone=neutral_informational`.
    - **`arxiv.org`**: Labeled as `type=reference`, `content_format=academic_paper`.
    - **App Stores (`apps.apple.com`, `play.google.com`)**: Labeled as `type=app_store_listing`, `primary_intent=transactional`.
- **The "Invisible" Domain Strategy**: Many of the top "invisible" domains (like `reddit.com` and `wikipedia.org`) were handled via these static overrides because their structure is fixed and does not require per-page LLM analysis.

### 2.5.3 Labeler Fidelity (cross-model agreement)
To test whether Content DNA is model-dependent, we ran a direct agreement audit between **Gemini 2.5 Flash** and **GPT-5-mini** on **2,660 overlapping URLs** (`docs/inter_model_fidelity_report.md`).

- **Structural fields (agreement)**: `has_pros_cons` **94.6%**, `has_sources_or_citations` **93.8%**, `has_clear_authorship` **93.3%**, `has_tables` **92.9%**, `has_numbered_lists` **91.1%**
- **Categorical fields (agreement)**: `content_format` **92.1%**, `type` **87.7%**, `tone` **77.7%**
- **Score consistency (correlation)**: `freshness_cue_strength` **r = 0.841** (strong trend agreement, different absolute thresholds)

### 2.5.4 Enrichment Coverage & Label Distribution (Study URL Universe)
To make downstream analyses defensible, we first measured how much of the URL universe was successfully enriched.

- **Enriched URLs:** 11,925 / 11,929 (**~100%**)
- **Unlabeled URLs:** 4

### 2.5.5 Research Questions for Selection Analysis
*These research-design questions guided the enrichment-based analyses in Part 3 (`3.4`–`3.5`).*

1. **Why were Additional links not cited inline?**
   - Compare structural DNA: `has_tables`, `has_numbered_lists`, `heading_density`
   - Compare `tone`: Are Additional links more `promotional` or `salesy`?
   - Compare `type`: Are Additional links more `product_page` vs. `listicle`?

2. **Cross-Run Citation:**
   - Were Additional links from Run 1 cited inline in Run 2/3/4?
   - This shows consistency vs. randomness in ChatGPT's citation selection

3. **Page 1 Ignored Links:**
   - Links in **Bing Page 1** (variable-size SERP page; see `3.2.1`) that ChatGPT did NOT cite
   - Compare their DNA to cited links
   - Hypothesis: Ignored links are more `salesy`, lower `expertise_signal_score`

## 2.6 Citation Mapping & Claim-Level Attribution
*How we precisely map ChatGPT's written claims to their retrieved sources. This pipeline was applied specifically to **listicle-cited claims**, where the research question is sharpest: when a model cites a listicle containing 10+ products, does it actually extract information from that page, or does it hallucinate from parametric knowledge and merely attach the listicle as a plausible-looking source? Listicles are uniquely suited to this test because they contain a discrete, verifiable roster of items we can check against the model's output. We further restricted the analysis to **solo-cited claims** — claim blocks attributed to exactly one URL — because when multiple sources back a single claim (e.g., a listicle + a product page), it becomes impossible to determine which source the model actually drew from. This solo-citation filter was applied across both GPT and Gemini listicle-cited claims.*

### 2.6.1 The "Claim-to-Link" Forensic Pipeline
- **The Challenge:** ChatGPT's final response text replaces internal citation tokens with generic `[URL]` tags. To understand *why* a link was cited, we must reconstruct the link between the **written claim** and the **retrieved source**. Unlike Gemini — which natively provides segment-level attribution via `groundingSupports` (see `2.4.2`) — ChatGPT exposes no such mapping; we had to build one.
- **The Solution:** We developed a forensic mapping pipeline that reconstructs ChatGPT's claim-to-source attribution at a resolution comparable to Gemini's native `groundingSupports`:
    1. **Token Alignment:** Raw citation tokens (e.g., `citeturn0search9`, `citeturn0search24`) are extracted from the network event stream along with their `start_idx` / `end_idx` character positions in the streamed response text.
    2. **Block-Level Extraction:** The script identifies the **Full Claim Block** — the descriptive text between consecutive citation tokens. This captures the complete product description or factual statement ChatGPT attributed to that source, not just a keyword. For example, a single claim block might read: *"InqScribe – desktop transcription software with a perpetual license (no subscription; runs locally)"* mapped to `citeturn0search24` → `inqscribe.com`.
    3. **Metadata Enrichment:** Each claim block is joined to its retrieved "Ground Truth" (the snippet, title, and URL from the `search_result_groups`) by resolving `ref_id` keys (`turn_index`, `ref_type`, `ref_index`).
    4. **Output:** The pipeline produces a structured `mapping.json` per run, where each entry contains `claim_text`, `token`, `target_url`, `start_idx`, and `end_idx` — enabling the same claim-level fidelity and multi-source analyses that Gemini's API provides natively.
- **Cross-model parity:** This pipeline is what makes direct GPT-vs-Gemini comparison possible at the claim level. Without it, ChatGPT attribution would be limited to run-level URL lists with no way to determine which claim maps to which source.

### 2.6.2 Multi-Chip Reconstruction (Synthesis Aggression)
- **Defining Multi-Chips:** We observed cases where ChatGPT groups multiple sources under a single citation (e.g., "Vibe Voice+1").
- **Forensic Discovery:** Our mapping revealed that these correspond to concatenated tokens (e.g., `turn0search8` + `search15`).
- **Research Value:** This allows us to measure **Synthesis Aggression**—how ChatGPT merges facts from multiple distinct search results into a single cohesive claim.

### 2.6.3 Definitions for Multi-Source & Mixed Citation Analysis
- **Multi-cited claim/segment:** a claim/segment with **2+ distinct cited URLs**. Computed by `scripts/analysis/multi_source_claim_support.py`.
- **Mixed listicle+product citation:** among multi-cited claims, a case where the cited URL set contains **≥1** `type=listicle` and **≥1** `type=product_page`.
- **Type-mix buckets:** each multi-cited claim is partitioned into exactly one bucket: *mixed listicle+product*, *listicle-only*, *product-only*, or *neither* (other page types / unknown).
- **Quantitative results** for these metrics are reported in **`3.7`**.

## 2.7 Localization & Retrieval Environment

*How geographical context affects the comparison between Search and GenAI.*

### 2.7.1 Implicit vs. Explicit Localization (Definitions & Instrumentation)
- **Prompt Language Distribution**: Our dataset consists of **72 English prompts** and **7 foreign-language prompts** (1 French, 1 Chinese, 2 Turkish, 1 German, 1 Italian, 1 Spanish). All 7 foreign-language prompts originated from **Ahrefs** keyword clusters; the **Profound**-sourced prompts were exclusively English.
- **Explicit Localization:** When the query targets an inherently local category — even without any geographic qualifier in the prompt. A query like "best bakery" or "best pizza" is implicitly local, and the system will inject a location into the fan-out queries automatically (e.g., rewriting to "best bakery near Munich Germany"). This primarily applies to local-commerce queries and is not a factor in our SaaS/software dataset, where products are globally available.
- **Implicit Localization:** When the query is general (e.g., "Best laptop"), but the search engine uses the user's IP, browser language, and search history to localize results.
- **Observed instrumentation signal (Fan-Out Queries):** In our logged **fan-out query sets** (Gemini `groundingMetadata.webSearchQueries[]` — officially called "grounding support" queries, functionally equivalent to fan-outs; ChatGPT network-derived hidden queries), implicit localization often manifests as **one of the fan-out queries being rewritten into the prompt's local language**, which then steers retrieval toward localized sources.
- **Concrete example (implicit localization via fan-out):** When issuing an English prompt from **Munich, Germany**, we observed a two-query fan-out where one query remained English while the other was rewritten into German:
  - Q1: `"free website or program to translate video and add subtitles"`
  - Q2: `"kostenlos video übersetzen und Untertitel automatisch hinzufügen ..."`

  This resulted in one of the two fan-out queries retrieving German-language sources despite an English user prompt.

- **Concrete example (explicit localization via fan-out):** A location-free prompt like `"what is the best bakery"` can trigger fan-out queries that inject a specific place (e.g., `"best bakery near Munich Germany"`), effectively converting an implicit prompt into an explicitly localized retrieval task.

- **Observed GPT fan-out localization patterns (62 runs with non-English fan-out queries):**
  1. **Case 1 — Foreign-language prompts (30 runs):** When the user prompt is in a non-English language (French P019, Chinese P032, Turkish P038, German P055, Turkish P060), GPT emits fan-out queries in both the prompt's language and English. This is expected behavior — the system mirrors the prompt language while also anchoring to English for broader coverage. Gemini exhibits the same pattern: verified across Chinese (P032: 1 English + 3 Chinese), French (P019: 1 English + 3 French), German (P055: 2 English + 2 German), and Spanish (P062: 1 English + 3 Spanish) prompts.
  2. **Case 2 — Context-triggered anomalies (9 runs):** English prompts that **mention a specific language or locale** in their content trigger non-English fan-out queries. For example, "best software for Parsian/Farsi audio-to-text transcription" (P058) produces Farsi fan-out queries; "Chrome extension for live Chinese to English translation" (P047) produces Chinese fan-out queries. The non-English query is contextually motivated by the prompt's subject matter, not by IP or browser locale.
  3. **Case 3 — Untriggered anomalies (23 runs):** Purely English prompts with **no language or locale context** produce non-English fan-out queries (Chinese, Japanese, Spanish, French, etc.). For example, "Is there a real time audio to text translation?" (P007) or "Can I add a live translation app to calls?" (P048) generate Chinese and Japanese fan-out queries. These appear to be driven by IP/locale signals or unexplained model behavior, as nothing in the prompt suggests a non-English retrieval path.

  *Note: Cases 2 and 3 are GPT-only observations. Gemini was accessed via API without IP-based locale signals, so these patterns could not be tested for Gemini (see `2.4.2`).*

- **Findings** (occurrence rates, "English Anchor" effect, freshness steering stats) are reported in **`3.1`**.

### 2.7.2 Freshness Steering (Methodology)
- **What we measure:** Whether fan-out queries contain explicit year signals (e.g., "2025", "2026") and at which query index they appear.
- **Why it matters:** Explicit year injection steers retrieval toward time-stamped listicles, which changes the composition of the grounding pool.
- **Findings** (Gemini vs. GPT freshness rates) are reported in **`3.1`**.

### 2.7.3 The Proxy Requirement (US-Centric Baseline)
- To ensure a fair "apples-to-apples" comparison, we standardized our retrieval environment using a **US-based Proxy**.
- **Why US Proxy?**
  1. **Baseline Consistency:** ChatGPT's primary training data and search behaviors are heavily weighted toward US-English web content.
  2. **Avoiding "Regional Noise":** Prevents Bing from surfacing local retailers or regional blogs that ChatGPT would never see, which would artificially lower the overlap percentage.
  3. **Global Tech Standard:** Most product recommendations in the "AI/Software" category (our primary focus) are global in nature, making the US SERP the most relevant "Ground Truth."

### 2.7.4 Ethical and Legal Constraints in Retrieval Instrumentation
- **The "Data Access" Bottleneck**: A significant challenge in RAG research is the increasing difficulty of accessing "raw" search indices.
- **Google vs. SerpApi (Dec 2025)**: On December 19, 2025, Google filed a lawsuit against **SerpApi**, alleging "unlawful scraping" and circumvention of security measures ([Google Blog, 2025](https://blog.google/innovation-and-ai/technology/safety-security/serpapi-lawsuit/)).
- **The "Customer List" Paradox**: Interestingly, the SerpApi homepage has historically listed major AI players like **Perplexity** and **OpenAI** (the latter was subsequently removed) as customers ([SerpApi, 2026](https://serpapi.com/)). This suggests a complex ecosystem where the very companies building RAG systems may rely on third-party scrapers to bridge the "Visibility Gap" between their models and the live web.
- **Impact on Methodology**: This legal pressure has led to technical restrictions in the SEO/GEO tool ecosystem, such as the removal of high-volume parameters (e.g., `num=100`).
- **Research Justification**: These constraints further justify our **Deep Hunt (Rank 200)** methodology. As traditional scraping becomes more restricted, the "Visibility Gap" between what an LLM can see (via direct API access) and what a researcher can see (via public search UIs) will likely widen, making the LLM a primary—and increasingly exclusive—gateway to the deep web.

## 2.8 Analysis Applications

We built two separate interactive tools for qualitative inspection and aggregate analysis, one per model:

### 2.8.1 ChatGPT Analysis Viewer (`scripts/utility/data_viewer.py`)
- Per-query/run comparison of ChatGPT responses vs. Bing SERP results (Top 200)
- Highlights cited, additional, and invisible links with overlap status
- Dashboard with aggregate statistics (Overlap %, Invisible Domains, etc.)
- Enabled manual spot-checking that revealed the "Pagination Loop" and "Page 2 Cliff" problems in Bing

### 2.8.2 Gemini Grounding Analyzer (`tools/GeminiVizApp`)
- Per-query/run comparison of Gemini responses vs. Google SERP results
- Visualizes the grounding pipeline by comparing `groundingChunks` (retrieved candidates) vs. `groundingSupports` (final segment-level attributions) vs. Google SERP (control group)
- Surfaces fan-out query overlap distribution per query index (Q1–Q7)
- Aggregate grounding behavior dashboard (SERP overlap rate, per-query citation counts)

### Why two apps:
The two models expose fundamentally different data structures — ChatGPT requires reconstructed citation mapping from network tokens (see `2.6`), while Gemini provides native `groundingMetadata` with chunk-level and segment-level attribution. A single unified viewer would have obscured these structural differences rather than surfacing them.

---

# Part 3: Findings & Analysis

## Executive Summary of Key Findings

*   **The "Fan-Out Strategy" (Implicit vs. Explicit Retrieval):**
    *   **Gemini's Freshness Obsession:** 96.7% of Gemini runs (297/307) explicitly inject a year (2025 or 2026) into their fan-out queries, with 74.3% (228/307) placing this signal in the very first query (Index 0). This drives Gemini's aggressive "Listicle Uptake."
    *   **GPT's Multi-Turn Expansion:** While GPT only uses explicit years in 5.1% of runs, it exhibits a "Multi-Turn Fan-Out" phenomenon where it issues secondary and tertiary queries (3+ queries) in response to initial results, effectively "hunting" for specific citations before finalizing the response.
    *   **Implicit Localization Bias:** Implicit localization signals (non-English fan-out queries from English prompts) were observed in 13.1% of GPT runs and 4.6% of Gemini runs, demonstrating how retrieval environment (IP/locale) can steer grounding even without user intent.

*   **The "Provider Pivot" (Enterprise vs. Personal):** GPT Personal shows significantly higher overlap with Google (~65%) than GPT Enterprise (~28%), suggesting a deployment-specific retrieval strategy where Personal runs are likely multi-provider (Bing + Google) while Enterprise is restricted to the Bing/Azure ecosystem.
*   **The "UI Erasure" & Invisible Citations:** By expanding retrieval depth to Rank 200, we discovered that a significant portion of LLM citations are "invisible" to human searchers (Rank 11–30+). This proves LLMs act as "Deep Hunters," extracting high-quality content that search engine UIs have effectively buried.
*   **The "Page 2 Cliff" & Position Bias:** Despite the ability to "Deep Hunt," citation density exhibits a violent drop-off after Rank 10 (the "Page 2 Cliff"). This confirms that position bias remains the dominant factor in GenAI grounding, creating a "Winner-Take-All" dynamic for the first elastic page.
*   **The "Structural Filter" (Selection Drift):** Models exhibit statistically significant preferences for specific Content DNA. Gemini, for instance, shows a +8.7pp "hunt" for numbered lists, while GPT Personal shows a +12.2pp preference for tables in listicles.
*   **Listicle Uptake & Host Bias:** LLMs exhibit a "graduation" effect, preferentially citing the primary product pages recommended within retrieved listicles, but this is tempered by a measurable "Host Exclusion" bias where certain domains are systematically ignored despite being present in the "Menu."

> **Section 3 Reading Order:**
> The findings are organized to follow the pipeline from retrieval to analysis:
> 1. **3.1 Fan-Out** — How queries are generated and dispatched (the retrieval strategy)
> 2. **3.2 Position Distribution** — Where in the SERP the model's citations actually land
> 3. **3.3 Citation Overlap & Invisible Links** — What fraction of citations exist in conventional search, and what doesn't
> 4. **3.4 Content DNA Profile** — The enrichment breakdown of source types, tones, and structural features
> 5. **3.5 Selection Drift** — How the model's "Order" diverges from the "Menu" based on enriched features
> 6. **3.6 Listicle Bias** — Deep analysis of listicle-specific selection, re-ranking, and fidelity
> 7. **3.7 Multi-Source Citation** — When models cite multiple sources for a single claim

---

## 3.1 Retrieval Strategy & Fan-Out Analysis
*Before analyzing citation overlap, we examine the retrieval phase: how the models reshape the user prompt into multiple search queries. Methodology and instrumentation are defined in `2.3.4`, `2.7.1`, and `2.7.2`.*

#### The Three-Layer Architecture (as observed)

Our network instrumentation reveals a three-layer pipeline, not a monolithic model:

```
Layer 1: SONIC CLASSIFIER (fires once, <15 ms)
  ↓  Decides: search vs. no-search
  ↓  Outputs: simple_search_prob, complex_search_prob, no_search_prob
  ↓  Deterministic for same input (byte-identical across runs of same prompt)

Layer 2: SONICBERRY ORCHESTRATOR (alpha.sonic_thinky_v1_paid)
  ↓  Manages the web.run tool-call loop
  ↓  Each web.run call dispatches exactly 2 queries (fixed pair-generation)
  ↓  Tracks search_turns_count (1, 2, 3…)

Layer 3: GENERATION MODEL (gpt-5-2)
  ↓  After each web.run, evaluates retrieved results in context
  ↓  Decides whether to call web.run again (agentic re-search)
  ↓  Non-deterministic: same input can produce 1–3 search turns
  ↓  Selects sources → generates response with inline citation tokens
```

The high-level flow as observed in the event stream:
1. **User prompt received**
2. **Search decision (Layer 1)**: the Sonic Classifier outputs a 3-class probability distribution and evaluates it against thresholds in priority order (`no_search` → `complex` → `simple`). If `no_search_prob ≥ 0.175`, search is suppressed; otherwise search fires.
3. **Fan-out query generation + retrieval (Layer 2–3)**: the model calls the `web.run` tool, which dispatches exactly 2 reformulated queries. Results return as `search_result_groups`.
4. **Re-search decision (Layer 3)**: the generation model evaluates the retrieved pool and may call `web.run` again (incrementing `search_turns_count`). This creates the agentic re-search loop — 94% of runs complete in 1 turn (2 queries), 2.5% require 2 turns (4 queries), 0.2% require 3 turns (6 queries).
5. **Selection**: the model promotes some sources to be cited inline, and may also attach extra sources as "additional."
6. **Generation**: answer text is streamed + citation tokens are inserted (e.g., `citeturn0search0`) and merged into the final response ("multi-chip").

### 3.1.1 ChatGPT Search Trigger Behavior
*When does ChatGPT decide to search at all?*

- **Overall search rate:** **89.0%** of 474 runs triggered web search (422/474). Enterprise: **91.1%**, Personal: **86.9%** — a 4.2 pp gap.
- **Classifier behavior:** The Sonic Classifier output a median `simple_search_prob` of **96.8%** for product-recommendation prompts. Neither the `complex_search_threshold` (0.4) nor the `no_search_threshold` (0.175) was ever crossed — all runs fell into "simple search" territory. The closest miss: P016 enterprise at `no_search_prob` = 0.1737 (missed the 17.5% gate by 0.0013).
- **External suppression:** The 52 no-search runs were **not** caused by the classifier's probability output:
  - 39 runs had **null classification** (classifier never executed; raw network response files were empty)
  - 13 runs had the classifier **overridden** despite `simple_search_prob` as high as 99.7% — pointing to server-side A/B gates, tool routing (`passthrough_tool_calls`), or session-level factors, predominantly on Personal accounts (11 of 13 overrides)
- **Prompt-level consistency:** 61/79 prompts (77.2%) always triggered search across all 6 runs; 6 prompts (7.6%) never triggered search; 12 prompts (15.2%) showed mixed behavior — P016 had a perfect 50/50 split.
- **Citation impact:** Search-triggered runs averaged **9.94 citations/run** vs **2.62** for no-search runs (~4x). Enterprise no-search runs averaged just 1.10 citations; Personal no-search runs managed 3.65, suggesting Personal more readily generates citation-like references from parametric memory.
- **Ghost citations:** 7 runs (all Personal) produced citation-formatted markers with **zero backing URLs** — hallucinated citation syntax. A further 5 runs produced **fully sourced citations without search** (up to 14 citations from parametric URL recall alone).

**Sonic Classifier configuration (observed across all 474 runs):**
- **Classifier:** `sonic_classifier_5p2_3cls_ev3` (model: `snc-pg-sw-3cls-ev3`, snapshot: `wli-searchdb-model5-2025-09-23-20-17`)
- **3-class output:** `simple_search_prob` + `complex_search_prob` + `no_search_prob` = 1.0
- **Thresholds (evaluated in order):** `no_search_threshold` = 0.175, `complex_search_threshold` = 0.4, `simple_search_threshold` = 0 (catch-all)
- **First-turn override:** `force_search_first_turn_threshold` = 0.00001 (near-zero, almost always forces search on first message)
- **Enterprise vs. Personal divergence:** Enterprise has `prefetch_threshold: null` + `passthrough_tool_calls: true`; Personal has `prefetch_threshold: 0.55` + no passthrough tools

**Note on the "65% search threshold" claim:** Independent reverse-engineering by [Resoneo](https://think.resoneo.com/chatgpt/) documents a single `force_search_threshold` of 65%. Our data captures a different classifier variant using a three-class threshold system rather than a single cutoff. The two may reflect different A/B variants or classifier versions. Our median `simple_search_prob` was 96.8% — far above any plausible boundary — so we cannot empirically test where the effective decision point lies in the 50–70% zone. The Resoneo-reported 65% figure may also correspond to the `prefetch_threshold` (0.55 in our data), which has shifted between versions.

### 3.1.2 Freshness Steering
- **Gemini: Explicit Freshness Obsession:** **96.7%** of Gemini runs (297/307 with valid grounding metadata) explicitly inject a year (2025 or 2026) into their fan-out queries. Of these, **74.3%** (228/307) place the year signal in the very first query (Index 0), while a further **22.5%** (69/307) include it only in later queries. Just **3.3%** (10/307) of runs contained no year signal at all. This drives Gemini's aggressive "Listicle Uptake" — by explicitly searching for "Best [Product] 2025," the model forces the retrieval of time-stamped listicles, which then dominate its grounding.
- **GPT: Implicit Recency Reliance:** Only **5.1%** of GPT runs use explicit year signals in their fan-out queries. GPT relies almost entirely on the search index's (Bing's) internal recency ranking, leading to a more diverse (though still listicle-leaning) grounding pool.
- **GPT's Multi-Turn Expansion:** GPT exhibits a "Multi-Turn Fan-Out" phenomenon where it issues secondary and tertiary queries (3+ queries) in response to initial results, effectively "hunting" for specific citations before finalizing the response. The empirical details of this mechanism are in **`3.1.3`** below.

### 3.1.3 GPT Multi-Turn Fan-Out: Empirical Findings
*Detailed breakdown of how and when GPT's agentic re-search loop fires, based on `web.run` tool-call chain analysis of raw network responses.*

**Distribution (across 474 runs, including 435 with valid search data):**

| Search Turns | `web.run` Calls | Total Queries | Runs | % | Description |
|-------------|----------------|---------------|------|---|-------------|
| 0 (no search) | 0 | 0 | 14 | 3.2% | Search suppressed (classifier null or overridden) |
| 1 (standard) | 1 | 2 | 409 | **94.0%** | Standard: one pair of reformulated queries |
| 2 (re-search) | 2 | 4 | 11 | 2.5% | Re-search: model evaluates Turn 1 results, issues 2 more queries |
| 3 (double re-search) | 3 | 6 | 1 | 0.2% | Double re-search: model issues a third batch |

- **Enterprise triggers multi-turn search 3x more often** than Personal (4.1% vs 1.4%), suggesting different Sonicberry orchestration behavior across deployment tiers.
- Only **P035** (*"Can you list translation services with live interpreters and their 2-day pricing?"*) consistently triggered 2 turns across all 6 runs. All other multi-turn runs were sporadic (1 of 3 runs for that prompt).

**The 12 multi-turn runs — actual queries:**

We cannot determine *why* the model chose to re-search; we can only observe *what* it searched. The table below shows the actual Turn 1 and Turn 2+ query content extracted from raw network payloads.

| Prompt | Turns | `complex_search_prob` | Turn 1 Queries | Turn 2+ Queries |
|--------|-------|----------------------|----------------|-----------------|
| P035 | 2 | 0.069 | "translation services with live interpreters pricing…" | "Jeenie live interpreter pricing per minute…", "Jeenie or Boostlingo pricing" |
| P053 | 2 | **0.259** | "free AI text to speech celebrity voices…" | "ElevenLabs free tier celebrity voices API IoT…", "open source TTS celebrity voices or voice cloning…" |
| P050_r3 | 2 | 0.003 | "free app live translation during a call French…" | "Google Translate app live conversation translation…", "Microsoft Translator app real time voice…" |
| P063_r1 | 2 | 0.037 | "best machine translation tool for live translation that maintains context" | "live translation tools maintain conversation context or memory…", "translation memory or adaptive context in real-time tools" |
| P073_r3 | **3** | 0.012 | "best video translator for YouTube…" | Turn 2: "tools to translate YouTube videos subtitles or audio…"; Turn 3: "tools like VEED, Kapwing, Happy Scribe" |

**Key finding: The Sonic Classifier does NOT control re-search.** The correlation between `complex_search_prob` and multi-turn behavior is loose (avg 0.104 for multi-turn vs 0.025 for single-turn, but P050 re-searched at 0.3% while P020 did not at 30.6%). The re-search decision is made by the generation model (gpt-5-2) at inference time after evaluating initial results. P073 proves this definitively: byte-identical classifier outputs across 3 runs produced 1, 1, and 3 search turns.

**Observed patterns in Turn 2+ queries:**
Across all five multi-turn cases, Turn 2 queries tend to include specific product/service names (Jeenie, Boostlingo, ElevenLabs, Google Translate, Microsoft Translator, VEED, Kapwing) or rephrased terminology, whereas Turn 1 queries are more generic. We report this as an empirical observation without claiming a causal mechanism — the model's internal decision to re-search is not visible in the network data.

**Timing evidence:**
- 4-query runs: second `web.run` fires ~1.2 seconds after the first (time to receive and evaluate Turn 1 results)
- 6-query run (P073_r3): calls are chained (`parent_id` links form a sequential chain) with tight timing (484 ms → 341 ms) — the model rapidly determined each round was insufficient

**Query drift:** Across multiple runs of the same prompt, the fan-out query set can vary. This drift is a primary driver of stochastic retrieval—different fan-out sets lead to different retrieved sources and therefore different citations/recommendations.

### 3.1.4 Implicit Localization Bias
- **GPT Occurrence Rate:** Implicit localization signals (non-English fan-out queries generated from English prompts) were observed in **13.1%** of GPT runs, distributed across three patterns:
    - **Foreign-language anchoring** (30 runs): one of the two fan-out queries is issued in a non-English language (e.g., German, Turkish), with the other remaining in English.
    - **Context-triggered** (9 runs): the prompt references an inherently local category (e.g., "best pizza," "local services"), triggering locale-aware query rewriting.
    - **Untriggered anomalies** (23 runs): non-English fan-out queries appear with no obvious prompt-level trigger, suggesting IP/locale environment leaking into query generation.
- **Gemini — not observed via API:** Because our Gemini data was collected through the Vertex AI API (which does not carry IP or locale signals), we cannot test whether Gemini exhibits similar implicit localization. This remains a limitation; inspecting Gemini's consumer UI network traffic could reveal whether localization occurs there (see `2.4.2`).
- **The "English Anchor" Effect (Gemini-specific):**
    - Even for foreign-language prompts, Gemini **always** reserves the first grounding-support query slot (Index 0) for an English translation of the prompt.
    - Due to the **First-Query Bias** (where models preferentially cite results from the first search query), the English-language search results dominate the final response.
    - In 100% of our localized Gemini runs, the cited sources were primarily global/English SaaS platforms and tech publications (e.g., `pcmag.com`, `techradar.com`), effectively creating a "Global Information Bubble" even for non-English users.
- **Publisher/SEO→GEO implication:** Even if users in non‑English-speaking countries **search in English**, IP/locale-driven fan‑out rewriting can route part of retrieval toward **localized-language SERPs**. Publishers without localized pages may lose visibility (and therefore citations/traffic) in these retrieval paths.

## 3.2 Position Bias & Page Distribution
*Quantifying how search engine ranking (the "Menu" position) influences the final citation (the "Order"). We present this before the invisible-links analysis because understanding where citations land in the SERP provides context for interpreting what falls outside it.*

### 3.2.1 Page-Level Distribution (The "Long Tail" of Retrieval)
Our analysis of 237 runs per engine tier (79 queries × 3 runs) reveals that LLM citations are not concentrated on the first page of search results but are distributed deep into the SERP.

#### Bing Page Distribution (Deep Hunt)
Analysis of where GPT citations match results in our Bing scrape (up to Rank 200). Because ChatGPT likely receives a cleaner backend ranking than the consumer UI we scraped (see `2.2.1`), these match counts reflect our best-effort alignment rather than ChatGPT's actual retrieval depth.

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

**Observations on the Bing page distribution:**
- **Enterprise vs Personal Page 1 gap**: Enterprise shows nearly 3× the Page 1 matches (1,468 vs 521), consistent with Enterprise's higher Bing affinity (81.3% overlap vs 67.6%; see `3.3.1`). Personal's lower Page 1 count aligns with its multi-provider retrieval strategy — many of its citations match Google rather than Bing.
- **The "Page 2 Dip"**: Page 2 shows a conspicuous drop compared to both Page 1 and Pages 3–5. As discussed in `2.2.1`, this is likely an artifact of Bing's UI pagination instability (truncated Page 1 results not shifting cleanly to Page 2) rather than a model preference.
- **Smooth decay after Page 3**: Pages 3–16 show a gradual, expected decay in match counts — the long-tail pattern. The fact that we still see hundreds of matches on Pages 4–10 demonstrates that many GPT citations fall well beyond what human searchers would see.
- **The "Page 1" Elasticity caveat**: We avoid defining Page 1 as a fixed "Rank 1–10" range. In Bing's consumer UI, the first page length varies based on ads, rich snippets, and vertical blocks (see `2.2.1`).

### 3.2.2 Intra-Page Position Bias (The "Rank 1" Effect)
Even within the first page of results, rank position matters significantly for citation likelihood. We show GPT against both the Bing index (its primary retrieval source for Enterprise) and the Google SERP, plus Gemini against its own Google fan-out results.

#### GPT: Bing Rank-Level Match Distribution (Enterprise vs Personal)
Analysis of where GPT citations match results by **global Bing rank** (position 1–200 across our full scrape). All 213 Enterprise and 209 Personal runs have results at every rank, so the match rates below are directly comparable. We count **distinct runs** where at least one cited link matched the Bing result at a given rank — this avoids inflating numbers when the same URL appears in multiple citation slots within a single run (e.g., both as a cited and additional link).

| Rank | Enterprise Runs Matched | Enterprise Rate | Personal Runs Matched | Personal Rate |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **152** | **71.4%** | **56** | **26.8%** |
| 2 | 146 | 68.5% | 49 | 23.4% |
| 3 | 86 | 40.4% | 47 | 22.5% |
| 4 | 70 | 32.9% | 33 | 15.8% |
| 5 | 48 | 22.5% | 40 | 19.1% |
| 6 | 41 | 19.2% | 26 | 12.4% |
| 7 | 44 | 20.7% | 26 | 12.4% |
| 8 | 44 | 20.7% | 24 | 11.5% |
| 9 | 38 | 17.8% | 27 | 12.9% |
| 10 | 20 | 9.4% | 29 | 13.9% |

*Match rate = distinct runs where at least one cited link matched the Bing result at that rank / total runs with a result at that rank (213 Enterprise, 209 Personal — all runs have results at every rank since we scraped to Rank 200).*

**Why we normalize: Bing's "Elastic Page 1"**
The global-rank table above treats every rank equally (all runs have results at Ranks 1–200). But in the actual Bing consumer UI, Page 1 is not a fixed "Top 10" — it varies per scrape (see `2.2.1`). This means raw match counts at higher ranks are partly suppressed by the fact that fewer runs even had a result at that position on Page 1. To avoid overstating the Rank 1–2 advantage, we measured **how many runs actually exposed a result at each rank on Page 1** and computed normalized match rates against that availability baseline.

**Bing Page 1 length distribution (clean runs only):**
*Note: ~50 runs per tier had a scraper artifact where the Bing page-break was not detected, causing all 200 results to be tagged as `page_num=1`. We exclude these from the Page 1 analysis below (161 clean runs per tier remain).*

| Page 1 Length | Enterprise Runs (n=161) | Personal Runs (n=161) |
| :--- | :--- | :--- |
| 1–2 results | 38 (23.6%) | 48 (29.8%) |
| 3–5 results | 41 (25.5%) | 44 (27.3%) |
| 6–7 results | 21 (13.0%) | 21 (13.0%) |
| 8–10 results | 55 (34.2%) | 46 (28.6%) |

*Median Page 1: 6 results (Enterprise), 4 results (Personal). Nearly half of scrapes had 5 or fewer organic results on Page 1, and only about a third had the "classic" 8–10 results. This means raw match counts at Ranks 5+ are partly suppressed by availability — many runs simply did not have a result at those positions on Page 1.*

**Page 1 availability and normalized match rates:**
To account for the elastic Page 1, we normalize: of the runs that actually had a Bing result at Rank N on Page 1, what percentage matched a citation?

| Rank | Ent. Page 1 Avail. | Ent. Matched | Ent. Rate | Pers. Page 1 Avail. | Pers. Matched | Pers. Rate |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 161 (100%) | 111 | **68.9%** | 161 (100%) | 42 | **26.1%** |
| 2 | 161 (100%) | 110 | **68.3%** | 161 (100%) | 39 | **24.2%** |
| 3 | 123 (76%) | 57 | **46.3%** | 113 (70%) | 14 | **12.4%** |
| 4 | 104 (65%) | 43 | **41.3%** | 93 (58%) | 14 | **15.1%** |
| 5 | 89 (55%) | 29 | 32.6% | 77 (48%) | 4 | 5.2% |
| 6 | 82 (51%) | 15 | 18.3% | 69 (43%) | 5 | 7.2% |
| 7 | 72 (45%) | 22 | 30.6% | 55 (34%) | 6 | 10.9% |
| 8 | 61 (38%) | 14 | 23.0% | 48 (30%) | 3 | 6.2% |
| 9 | 55 (34%) | 12 | 21.8% | 40 (25%) | 4 | 10.0% |
| 10 | 31 (19%) | 4 | 12.9% | 28 (17%) | 6 | 21.4% |

**Key observations on Bing rank bias:**
- **Enterprise Rank 1–2 dominance is real, not an artifact**: Even after normalizing for Page 1 availability, 69% of runs cite the Bing Rank 1 and Rank 2 results. The drop to Rank 3 (46%) is the steepest cliff in the data.
- **Enterprise Ranks 5–9 are more uniform than raw counts suggest**: Once normalized, the match rate for Ranks 5–9 is 18–33% — the apparent steep decline in raw match counts was partly driven by fewer runs having results at those positions on Page 1 (only 34–55% of scrapes had results at Ranks 5–9).
- **Personal is flat on Bing**: Normalized rates range 5–26% with no strong rank signal, consistent with Personal drawing citations primarily from Google.
- **The Rank 10 edge**: Only 19% of Enterprise and 17% of Personal scrapes even had a Rank 10 result on Page 1, making rate estimates noisy at this position.

#### GPT: Google Match Distribution (Enterprise vs Personal)
Analysis of where GPT citations match organic results in the Google SERP (collected via SerpApi). Showing both tiers side by side reveals the Enterprise/Personal divergence visible in Bing overlap (`3.3.1`) from a different angle.

| Page | Position | Enterprise Matches | Personal Matches |
| :--- | :--- | :--- | :--- |
| **1** | **1** | **88** | **168** |
| 1 | 2 | 59 | 128 |
| 1 | 3 | 34 | 145 |
| 1 | 4 | 37 | 107 |
| 1 | 5 | 41 | 112 |
| 1 | 6 | 39 | 113 |
| 1 | 7 | 33 | 103 |
| 1 | 8 | 26 | 92 |
| 1 | 9 | 21 | 48 |
| 1 | 10 | 14 | 38 |
| 2 | 1 | 17 | 58 |
| 2 | 2 | 18 | 57 |
| 2 | 3 | 14 | 65 |
| 2 | 4 | 18 | 41 |
| 2 | 5 | 16 | 48 |
| 2 | 6 | 18 | 50 |
| 2 | 7 | 9 | 38 |
| 2 | 8 | 9 | 46 |
| 2 | 9 | 17 | 23 |
| 2 | 10 | 8 | 29 |
| 3 | 1 | 11 | 30 |
| 3 | 2 | 7 | 21 |
| 3 | 3 | 4 | 39 |
| 3 | 4 | 7 | 27 |
| 3 | 5 | 6 | 18 |
| 3 | 6 | 6 | 14 |
| 3 | 7 | 8 | 22 |
| 3 | 8 | 3 | 16 |
| 3 | 9 | — | 6 |

**Non-organic SERP features (PAA, video, discussion):**

| Feature | Enterprise Matches | Personal Matches |
| :--- | :--- | :--- |
| PAA (People Also Ask) | 23 (9+7+6+1) | 44 (19+13+9+3) |
| Video | 3 (1+2) | 3 (1+1+1) |
| Discussion | — | 3 (1+1+1) |

*Non-organic match counts are low, confirming that GPT citations overwhelmingly align with organic results. The Personal tier shows roughly double the PAA matches, consistent with its higher Google affinity.*

**Key contrast — Enterprise vs Personal on Google:**
- Personal shows ~2× the Google matches at every rank, consistent with its multi-provider retrieval strategy (64.6% Google overlap vs Enterprise's 27.8% control).
- Enterprise's low Google match counts confirm it is primarily Bing-driven; the Google matches it does have likely reflect domain overlap between indices rather than Google-sourced retrieval.

#### Gemini: Google Match Distribution & Position Bias
Analysis of where Gemini citations appear in the **per-run** Google fan-out query results (matched against SerpApi organic results for the same grounding-support queries).

| Rank | Citations | Cited % |
| :--- | :--- | :--- |
| **Rank 1** | **181** | **15.7%** |
| Rank 2 | 105 | 9.1% |
| Rank 3 | 93 | 8.1% |
| Rank 4 | 92 | 8.0% |
| Rank 5 | 70 | 6.1% |
| Rank 6 | 62 | 5.4% |
| Rank 7 | 72 | 6.2% |
| Rank 8 | 51 | 4.4% |
| Rank 9 | 39 | 3.4% |
| Rank 10 | 21 | 1.8% |
| Rank 11 | 24 | 2.1% |
| Rank 12 | 26 | 2.3% |
| Rank 13 | 22 | 1.9% |
| Rank 14 | 23 | 2.0% |
| Rank 15 | 21 | 1.8% |

- **The "Rank 1" Dominance**: Gemini shows a clear concentration at the first organic result (15.7%), nearly double the second rank (9.1%).
- **Selection Decay**: Citations decay gradually through Rank 9, then drop sharply at Rank 10 (1.8%). Ranks 11–15 stabilize at ~2%, suggesting that results beyond the first page of Google results are still cited but at a much lower rate.
- **First-Query Bias (Gemini vs GPT)**: Gemini exhibits a strong dependency on the first grounding-support query, with a steep decay across subsequent queries (see per-query tables below). GPT shows a nearly balanced 50/50 split across its two parallel fan-out queries — a fundamental architectural difference.

**GPT per-query citation overlap (237 runs per tier):**

| Metric | Enterprise | Personal |
|--------|--------:|--------:|
| Bing Query 1 Overlap | **63.7%** | 54.1% |
| Bing Query 2 Overlap | **64.2%** | 52.4% |
| Google Query 1 Overlap | — | 50.4% |
| Google Query 2 Overlap | — | 46.4% |

*GPT's two parallel fan-out queries contribute nearly equally to citation overlap — the split is effectively 50/50 on both Bing and Google. Neither query dominates. This contrasts sharply with Gemini's first-query concentration below.*

**Gemini per-query citation overlap distribution (237 runs, 1,651 citations):**

| Query | Overlap | Citations |
|-------|--------:|----------:|
| **Q1** | **37.1%** | 613 |
| Q2 | 18.1% | 299 |
| Q3 | 11.6% | 191 |
| Q4 | 7.4% | 122 |
| Q5 | 2.8% | 46 |
| Q6 | 0.6% | 10 |
| Q7 | 0.1% | 2 |

  *Note: Not all runs produce queries at every index — Q5+ counts are lower partly because fewer runs generate that many fan-out queries (a function of the minimum thinking budget used; see `2.4.2`). The Q1 dominance is striking: the first fan-out query accounts for more citations than Q2–Q7 combined. Compared to GPT's balanced 50/50 split, Gemini's retrieval is heavily front-loaded toward its first grounding-support query.*

## 3.3 Citation Overlap & Invisible Links
*Having established where citations land in the SERP (3.2), we now quantify what fraction exists in conventional search indices at all — and characterize the "invisible" remainder.*

### 3.3.1 Global Overlap & Provider Discrepancy
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

#### Key Observations on Provider Strategy:
- **GPT Enterprise: The Bing Standard**: Consistent with OpenAI's [Enterprise documentation](https://help.openai.com/en/articles/10093903-chatgpt-search-for-enterprise-and-edu), which explicitly names Bing as the search provider, we see an **81.3% overlap** with the Bing index. We used Google SERP as a **control group** here, which only yielded a 27.8% overlap, confirming that Enterprise retrieval is heavily optimized for Bing.
- **GPT Personal: The Multi-Provider Shift**: OpenAI's [general documentation](https://openai.com/index/introducing-chatgpt-search/) describes ChatGPT search as leveraging "third-party search providers" (plural). Our data confirms this: GPT Personal shows a much higher affinity for **Google (64.6%)** than Enterprise (27.8%), and achieves its highest coverage (**80.6%**) when combining both indices.
- **The "Google Jump" (Enterprise vs. Personal)**: We observe a massive **36.8 percentage-point increase** in Google SERP overlap when moving from Enterprise (27.8%) to Personal (64.6%) accounts. This suggests that while Enterprise is "locked" to the Bing index for compliance/contractual reasons, the Personal account type has shifted to a Google-primary or multi-index retrieval strategy, significantly altering the "Menu" of available sources.

### 3.3.2 Invisible Links — The Visibility Gap
We use **Visibility Gap** as the empirical gap between what is **cited** and what is visible in conventional SERP UX. The methodological pivot (Top‑30 → Deep Hunt Rank‑200) is defined once in **`2.2`**; here we report the **residual unmatched** set and what it looks like.

- **What is being compared**: **cited URLs** vs **presence/absence** in the *per-run* SERP snapshot (and/or Bing Deep Hunt ≤200).
- **Output**: **matched** vs **invisible** (unmatched).
- **Invisible rate (headline)**: use the **"Invisible (Missing)"** row in **`3.3.1`** as the canonical rate.
- **Long tail context** (how deep "matched" links are): see **`3.2.1`** (Bing Pages 1–16).

#### Operationalization: "hidden zone" vs "truly invisible"
We separate notions that are easy to conflate:
- **Hidden zone (Bing Rank 11–30)**: a cited URL that is present, but beyond typical human scrolling.
  - **GPT Enterprise**: **388 / 1,637 (23.7%)** of cited occurrences were found in Bing **Rank 11–30**.
  - **GPT Personal**: **326 / 1,839 (17.7%)** of cited occurrences were found in Bing **Rank 11–30**.
- **Truly invisible (Bing+Google control)**: cited URLs **not found in Bing ≤ 200** **and** **not found in Google** (SerpApi control for the same run).
  - This matters for GPT Personal, which shows strong Google affinity; otherwise a Bing-only "invisible" count can overstate what is missing from the combined index surface.

#### Top invisible domains

##### GPT Enterprise — Top Invisible Domains (top 25, excluding niche SaaS)
Enterprise uses Bing exclusively (see `3.3.1`), so Bing-invisible = truly invisible. Google adds zero recovery, confirming Enterprise does not retrieve from Google. Niche SaaS/product domains from our speech/translation query set (e.g., maestra.ai, transyncai.com, x-doc.ai) are excluded — these likely reflect scrape limitations (Page 1 truncation, Rank 200 ceiling) rather than true index absence.

| Rank | Domain | Count |
| :--- | :--- | ---: |
| 1 | en.wikipedia.org | 116 |
| 2 | arxiv.org | 83 |
| 3 | theverge.com | 70 |
| 4 | sfgate.com | 46 |
| 5 | timesofindia.indiatimes.com | 36 |
| 6 | tomsguide.com | 34 |
| 7 | time.com | 34 |
| 8 | lifewire.com | 34 |
| 9 | wired.com | 32 |
| 10 | androidcentral.com | 28 |
| 11 | techradar.com | 24 |
| 12 | nypost.com | 22 |
| 13 | microsoft.com | 14 |
| 14 | windowscentral.com | 11 |
| 15 | tvtechnology.com | 10 |
| 16 | t3.com | 10 |
| 17 | axios.com | 9 |
| 18 | apnews.com | 8 |
| 19 | investopedia.com | 6 |
| 20 | es.wikipedia.org | 6 |
| 21 | deeptrue.org | 6 |
| 22 | sohu.com | 6 |
| 23 | zhuanlan.zhihu.com | 5 |
| 24 | support.google.com | 5 |
| 25 | blog.google | 5 |

*All citation types (cited + additional), www/non-www merged. The list is entirely reference sites (Wikipedia, arxiv), tech publications (theverge, wired, techradar, tomsguide, androidcentral, windowscentral, t3), and news outlets (time, nypost, sfgate, axios, apnews). These are high-authority domains ChatGPT almost certainly accesses through parametric knowledge rather than the fan-out search pipeline.*

##### GPT Personal — Top Invisible Domains (top 25, excluding niche SaaS, with Google recovery)
Personal uses multiple search providers (see `3.3.1`), so a Bing-only invisible check overstates the gap. The table below shows Bing-invisible counts alongside truly invisible (not in Bing **or** Google) and the Google recovery — how many Bing-absent citations were found in Google instead.

| Rank | Domain | Bing-Invisible | Truly Invisible | Google Recovered |
| :--- | :--- | ---: | ---: | ---: |
| 1 | reddit.com | 216 | 90 | **126** (58%) |
| 2 | apps.apple.com | 139 | 94 | **45** (32%) |
| 3 | en.wikipedia.org | 91 | 91 | 0 |
| 4 | arxiv.org | 70 | 70 | 0 |
| 5 | theverge.com | 67 | 67 | 0 |
| 6 | chromewebstore.google.com | 54 | 27 | **27** (50%) |
| 7 | sfgate.com | 42 | 42 | 0 |
| 8 | wired.com | 40 | 40 | 0 |
| 9 | facebook.com | 38 | 10 | **28** (74%) |
| 10 | tomsguide.com | 35 | 35 | 0 |
| 11 | youtube.com | 32 | 0 | **32** (100%) |
| 12 | timesofindia.indiatimes.com | 31 | 31 | 0 |
| 13 | techradar.com | 29 | 27 | 2 |
| 14 | medium.com | 29 | 25 | 4 |
| 15 | nypost.com | 28 | 28 | 0 |
| 16 | lifewire.com | 28 | 28 | 0 |
| 17 | androidcentral.com | 23 | 23 | 0 |
| 18 | naturalreaders.com | 21 | 0 | **21** (100%) |
| 19 | evernote.com | 20 | 0 | **20** (100%) |
| 20 | support.google.com | 14 | 8 | 6 |
| 21 | capcut.com | 14 | 0 | **14** (100%) |
| 22 | atanet.org | 14 | 0 | **14** (100%) |
| 23 | time.com | 13 | 13 | 0 |
| 24 | tvtechnology.com | 11 | 11 | 0 |
| 25 | github.com | 10 | 7 | 3 |

*All citation types (cited + additional), www/non-www merged. Two patterns emerge:*
- *Google fully recovers several domains that are absent from Bing: `youtube.com`, `naturalreaders.com`, `evernote.com`, `capcut.com`, `atanet.org` (100% recovery), and substantially recovers `reddit.com` (58%), `facebook.com` (74%), `chromewebstore.google.com` (50%) — confirming Personal's multi-provider retrieval.*
- *Major news/reference domains (`en.wikipedia.org`, `arxiv.org`, `theverge.com`, `wired.com`, `sfgate.com`, `nypost.com`, `tomsguide.com`) remain equally invisible in both indices — these are the same domains that top the Enterprise list, reinforcing that they originate from parametric knowledge rather than retrieval regardless of which search provider is used.*

#### Why these numbers are conservative (and what "truly invisible" likely means)
Our reported invisible rates (16.3% Enterprise, 19.4% Personal) are **upper bounds** on truly index-absent citations. Two systematic factors inflate the invisible count:

1. **The Rank 200 ceiling**: Our Bing scrape stops at Rank 200, but the page-level match histogram (see `3.2.1`) shows no convergence — matches are still accumulating at Pages 15–16 with a smooth decay curve that does not reach zero. Scraping to Rank 300 or 400 would almost certainly recover additional matches, shrinking the invisible set. The "invisible" label for these URLs does not mean they are absent from Bing's index — only that they fell beyond our scrape depth.

2. **Bing Page 1 truncation (the "Missing Middle")**: As documented in `2.2.1` and `3.2.2`, nearly half of our Bing scrapes had 5 or fewer organic results on Page 1 due to UI-level pagination instability. Results that would normally rank at positions 3–7 can be dropped entirely from a truncated scrape — they do not simply shift to Page 2. This is especially consequential because Page 1 is where we observe the **highest match rates** (69% at Ranks 1–2, 40–46% at Ranks 3–4; see `3.2.2`) — so every result missed due to Page 1 truncation is statistically more likely to be a citation match than a result missed deeper in the index. These "missing middle" results are almost certainly available to ChatGPT through its backend API integration with Bing, which likely returns a clean, stable ranked list without the consumer UI's truncation artifacts. Some of our "invisible" citations may therefore be high-ranking Bing results that our scrape happened to miss.

**If both factors were addressed** (deeper scraping + repeated Page 1 scrapes to capture the full elastic range), our overlap rates would likely increase and the remaining "truly invisible" set would converge toward citations that genuinely come from **outside the search index** — sites like Wikipedia, app stores, and known reference domains that ChatGPT may access through parametric knowledge or supplementary indices rather than the fan-out search pipeline.

## 3.4 Content DNA Profile & Cited vs. Additional Comparison
*Before analyzing selection drift, we establish the enrichment baseline: what types, tones, and structural features characterize the sources the model had to choose from ("Menu") versus what it actually cited ("Order"), and why some retrieved sources were demoted to "Additional."*

#### Note on Content DNA tables
Study-set and cited-set DNA composition tables provide the baseline menu/context for interpreting the drift analysis in **`3.5`**.

### 3.4.1 Study Set Composition (Cited + Additional + Page 1 Ignored)
Distribution across the **study set**, shown separately for each study angle.

#### GPT Enterprise study set (Bing-centric, N=2,858)
| Type | Count | % | Tone | Count | % |
| :--- | ---: | ---: | :--- | ---: | ---: |
| **product_page** | 1,159 | 40.6% | **promotional** | 2,002 | 70.0% |
| **listicle** | 989 | 34.6% | neutral_info | 699 | 24.5% |
| editorial | 161 | 5.6% | salesy | 115 | 4.0% |
| news | 156 | 5.5% | opinionated | 26 | 0.9% |

#### GPT Personal study set (Multi-provider, N=2,194)
| Type | Count | % | Tone | Count | % |
| :--- | ---: | ---: | :--- | ---: | ---: |
| **listicle** | 885 | 40.3% | **promotional** | 1,559 | 71.1% |
| **product_page** | 808 | 36.8% | neutral_info | 495 | 22.6% |
| editorial | 121 | 5.5% | salesy | 100 | 4.6% |
| news | 105 | 4.8% | opinionated | 26 | 1.2% |

#### Gemini study set (Google-centric, N=2,939)
| Type | Count | % | Tone | Count | % |
| :--- | ---: | ---: | :--- | ---: | ---: |
| **listicle** | 1,296 | 44.1% | **promotional** | 2,076 | 70.6% |
| **product_page** | 709 | 24.1% | neutral_info | 768 | 26.1% |
| news | 165 | 5.6% | salesy | 52 | 1.8% |
| marketplace | 150 | 5.1% | opinionated | 37 | 1.3% |

### 3.4.2 Cited Set Composition (Type + Tone)
Distribution of DNA categories for the URLs actually **cited** in the final responses.

#### GPT Enterprise cited set (N=1,614)
| Type | Count | % | Tone | Count | % |
| :--- | ---: | ---: | :--- | ---: | ---: |
| **product_page** | 649 | 40.2% | **promotional** | 1,105 | 68.5% |
| **listicle** | 589 | 36.5% | neutral_info | 390 | 24.2% |
| news_article | 104 | 6.4% | salesy | 95 | 5.9% |

#### GPT Personal cited set (N=1,444)
| Type | Count | % | Tone | Count | % |
| :--- | ---: | ---: | :--- | ---: | ---: |
| **listicle** | 544 | 37.7% | **promotional** | 998 | 69.1% |
| **product_page** | 523 | 36.2% | neutral_info | 329 | 22.8% |
| news_article | 98 | 6.8% | salesy | 82 | 5.7% |

#### Gemini cited set (N=653)
| Type | Count | % | Tone | Count | % |
| :--- | ---: | ---: | :--- | ---: | ---: |
| **listicle** | 371 | 56.8% | **promotional** | 467 | 71.5% |
| **product_page** | 148 | 22.7% | neutral_info | 181 | 27.7% |
| comparison | 26 | 4.0% | opinionated | 5 | 0.8% |

**Cross-references**: Listicle-only feature drift is reported under **`3.5.1`** (Intra-Listicle Selection Drift). Host bias, listicle rank bias, and semantic fidelity are reported under **`3.6`**.

### 3.4.3 Cited vs. Additional vs. Page 1 Ignored — Structural DNA Comparison

*Why were some retrieved links cited inline while others were demoted to "Additional" or ignored entirely?*

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

*Format note:* values are shown as **Enterprise / Personal**. "Page 1 ignored" is computed on **unique URLs** on Bing `page_num=1` that are **not cited** (per run, de-duplicated across runs). In our dataset, this bucket has substantial missing DNA labels because not all Bing Page‑1 results were fetched/labelled (Enterprise: 812/1660 labelled; Personal: 648/1394 labelled).

### 3.4.4 Content-Size Context (Listicles vs Product Pages)
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

**Connection to Dejan ("grounding budget")**: Dejan's analysis of Google AI Overviews discusses a roughly fixed per-query *grounding/snippet budget* (on the order of ~2k words). Our table above is **not** measuring an injected-context budget; it measures **full page length** of the candidate/cited sources we fetched. We include it as context for extractability and selection behavior, not as a budget validation.

## 3.5 Selection Drift (Enrichment-Based)
*With the DNA profile established in 3.4, we now measure how the model's selection ("Order") systematically diverges from the available pool ("Menu") along enriched feature dimensions.*

**Operational definitions** (matches `data/enrichment/full_stratified_drift_report.txt`):
- **Menu% (feature at rank R)** = % of retrieved candidates (for the baseline slice) at rank R with feature F.
- **Order% (feature at rank R)** = % of cited URLs that match into that same baseline slice at rank R with feature F.
- **Drift\(_R\)** = Order% − Menu% (percentage points).
- **Volume‑weighted drift** = \(\sum_R Drift_R \cdot N^{order}_R \; / \; \sum_R N^{order}_R\).

### 3.5.1 Intra-Listicle Selection Drift (Feature Lift)
When the model retrieves multiple listicles, it exhibits a measurable preference for specific structural and content features. The following tables summarize the **weighted-average lift (percentage point drift)** for listicles only, reported in `data/enrichment/listicle_drift_report.txt`.

##### GPT Enterprise (Bing-centric)
*Retrieved from Bing Page 1 (Top 5).*

| Feature | Weighted Avg Lift |
| :--- | :---: |
| `has_numbered_lists` | **+7.34pp** |
| `has_tables` | +3.64pp |
| `has_bullet_points` | +3.29pp |
| `freshness_cue_strength`| +2.15pp |
| `has_pros_cons` | -0.60pp |
| `has_clear_authorship` | -3.57pp |
| `is_current_year_2026` | -4.64pp |

##### GPT Personal (Multi-provider)
*Comparing selection from Google (Top 10) vs. Bing (Page 1, Top 5).*

| Feature | Google T10 Lift | Bing P1 Lift |
| :--- | :---: | :---: |
| `has_tables` | **+12.23pp** | +2.25pp |
| `freshness_cue_strength`| **+6.31pp** | **+11.97pp** |
| `has_bullet_points` | +5.74pp | -8.82pp |
| `is_current_year_2026` | +4.48pp | **+8.58pp** |
| `has_pros_cons` | +3.38pp | -9.17pp |
| `has_numbered_lists` | +2.20pp | -2.90pp |
| `has_clear_authorship` | +1.83pp | +2.20pp |

##### Gemini (Google-centric)
*Retrieved from Google fan-out queries (Top 10).*

| Feature | Weighted Avg Lift |
| :--- | :---: |
| `has_clear_authorship` | **+6.16pp** |
| `has_tables` | +2.35pp |
| `has_numbered_lists` | +1.85pp |
| `has_bullet_points` | +1.74pp |
| `has_pros_cons` | +1.46pp |
| `freshness_cue_strength`| +1.44pp |
| `is_current_year_2026` | -4.01pp |

### 3.5.2 Global Type Drift (De-Listicling)
Across all retrieved links, we observe a consistent "graduation" effect where models prefer primary product pages over the listicles that may have recommended them.

| Account Type | `type=product_page` Lift | `type=listicle` Lift |
| :--- | :---: | :---: |
| **GPT Enterprise** | **+16.5 pp** | -8.5 pp |
| **GPT Personal** | **+18.5 pp** | -9.4 pp |

### 3.5.3 Freshness Paradox (selection drift, stratified)
We analyze how freshness cues influence selection. The key pattern is that freshness signals can look weak or negative in aggregate due to **type confounding** (product pages vs listicles), but become positive when conditioning on listicles only (see `data/enrichment/full_stratified_drift_report.txt`).

### 3.5.4 Statistical Significance of Content DNA Preferences (T-Test)
To validate whether observed selection drifts are statistically significant, we performed a two-sample T-test (Welch's T-test) comparing the prevalence of content DNA features across models.

##### GPT Enterprise vs. Personal (Citations)
| Feature | Ent % | Pers % | Diff | Sig |
| :--- | :---: | :---: | :---: | :---: |
| tables | 21.3% | 19.1% | 2.2% | p<0.01 |
| numbered lists | 50.3% | 35.1% | 15.2% | p<0.01 |
| bullet points | 35.4% | 29.0% | 6.4% | p<0.01 |
| is current year 2026 | 15.1% | 17.8% | -2.7% | p<0.01 |
| clear authorship | 33.6% | 28.7% | 4.9% | p<0.01 |

##### Gemini Selection Preference (Order vs. Menu)
| Feature | Order % | Menu % | Drift | Sig |
| :--- | :---: | :---: | :---: | :---: |
| bullet points | 74.5% | 78.7% | -4.2% | p<0.01 |
| numbered lists | 52.8% | 48.9% | 3.9% | p<0.05 |
| pros cons | 38.1% | 38.8% | -0.8% | ns |
| tables | 33.4% | 35.8% | -2.4% | ns |
| is current year 2026 | 17.0% | 15.7% | 1.3% | ns |
| is vendor owned | 23.1% | 24.8% | -1.7% | ns |

## 3.6 Listicle Extraction & Bias Analysis

*Self-promotion, product text comparison, accuracy.*

### 3.6.1 Self-Promotion Bias & Host Exclusion
- **Host exclusion (empirical)**: In the listicle semantic-fidelity audit (solo-cited listicles), models **often omit** the host's own product even when it is present in the listicle.
  - **Gemini**: host present in **405** listicles; host **missing** in **71.9%** (291/405), **included** in **28.1%** (114/405)
  - **GPT**: host present in **431** listicles; host **missing** in **63.6%** (274/431), **included** in **36.4%** (157/431)
- **Bias multiplier (selection advantage)**: "Missing most of the time" does **not** imply "no bias." When host is present, it is still selected at a rate far above a random item on the page.
  - **Avg listicle size (in this audited subset)**: Gemini **8.1** products/page; GPT **9.3** products/page
  - **Host selection rate**: Gemini **28.15%**; GPT **36.43%**
  - **Random baseline** (approx \(1/\)avg products): Gemini **12.41%**; GPT **10.70%**
  - **Bias multiplier**: Gemini **2.27×**; GPT **3.40×**
- **Interpretation**: LLMs exhibit a mixed behavior: an "anti-self-promo" tendency (frequent host omission) combined with a measurable host selection advantage when they do pick items from host-authored listicles.

### 3.6.2 Selection Order vs. Listicle Rank (The "Re-Ranking" Effect)
- **Rank alignment**: how often **Chat response order** matches the **listicle's internal rank** for the same product (only when `listicle_rank` is recoverable).
  - **Gemini**: **29.5%** (108/366)
  - **GPT**: **27.9%** (166/596)
- **Interpretation**: models frequently **re-rank** listicle items in the final response. The listicle's "#1–#10" order is not preserved as the model's "top picks" order.

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

### 3.6.3 Semantic Fidelity: Reading Comprehension vs. Attribution
- **The "Two-Layer" Grounding Problem:** We decompose "Fidelity" into two distinct measurable phenomena:
    1.  **Attribution Accuracy:** Does the cited source actually contain the product?
    2.  **Reading Comprehension (Pure Fidelity):** When the product is present, how accurately does the model extract its details?
- **Key Findings (Solo-Cited Listicles):**
    - **Pure Fidelity (Comprehension):** Both models exhibit near-perfect scores when the product is present (**Gemini: 4.81/5.0**, **GPT: 4.75/5.0**).
    - **Attribution Failure:** Some "solo-cited" product claims still point to listicles where the product is not present (mis-attribution).
      - **Gemini**: **7.36%** (31/421 product roster items)
      - **GPT**: **1.89%** (13/689 product roster items)
- **Thesis Implication:** The "hallucination problem" in modern RAG systems is increasingly an **attribution/linkage problem**, not a "reading" or "understanding" problem. The models "know" the facts but "forget" which specific tab they were looking at when they found them.

## 3.7 Multi-Source Citation Analysis
*How often do models cite multiple sources for a single claim, and what type combinations appear? Definitions in `2.6.3`.*

### 3.7.1 Multi-Source Claim Support Rate
**All claim/segment occurrences:**
- **GPT**: 458 / 4296 (**10.7%**) multi-cited
- **Gemini**: 788 / 2287 (**34.5%**) multi-cited

**Listicle-cited occurrences only (at least one cited URL has `type=listicle`):**
- **GPT**: 194 / 1363 (**14.2%**) multi-cited
- **Gemini**: 664 / 1519 (**43.7%**) multi-cited

### 3.7.2 Mixed Listicle + Product-Page Citations

**All multi-cited occurrences:**
- **GPT**: 41 / 458 (**9.0%**) mixed listicle+product-page
- **Gemini**: 130 / 788 (**16.5%**) mixed listicle+product-page

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

**What does "neither" look like? (examples of multi-cited type-sets)**
- **GPT neither (N=96)** is dominated by `unknown` (unlabeled URLs) plus small tails like `news_article`, `documentation`, `editorial_article`, `forum_ugc`, `marketplace_directory`, and combinations (see `multi_type_sets_by_bucket.neither_listicle_nor_product` in `data/enrichment/multi_source_claim_support_stats.json`).
- **Gemini neither (N=40)** is mostly `other` / `unknown` mixtures plus a tail of `documentation`, `marketplace_directory`, `forum_ugc`, `editorial_article`, etc. (same JSON).

**Listicle-cited multi-cited occurrences only:**
- **GPT**: 41 / 194 (**21.1%**) mixed listicle+product-page
- **Gemini**: 130 / 664 (**19.6%**) mixed listicle+product-page

**Mixed-case lists (for qualitative inspection):**
- `data/enrichment/mixed_listicle_plus_product_citations_gpt.csv` (41 rows)
- `data/enrichment/mixed_listicle_plus_product_citations_gemini.csv` (130 rows)

---

# Part 4: Research Gaps & Future Work

1. **Deeper Crawling:** We stopped at Rank 200; going to 300+ might find more matches.
2. **Longitudinal Consistency (Expanded Runs):** While this study used 3-4 runs per prompt, future work should expand this to 10+ runs to achieve statistical significance in "stochastic retrieval" patterns and to better map the "long tail" of citations that appear only in rare instances.
3. **Temporal Analysis:** How do results change over time? (Run the same queries in 3 months).
4. **Query Category Segmentation:** Do certain product categories have better/worse overlap?
5. **Multi-Model Comparison:** Compare ChatGPT vs. Gemini vs. Claude on the same queries.
6. **User Study:** Do humans prefer ChatGPT's recommendations or Bing's Top 10?
7. **Exhaustive SERP Depth Analysis:** Expanding Bing/Google search depth from top 200 to top 300+ results to determine if "invisible" citations are simply lower-ranked search results or truly independent LLM retrievals.
8. **Residual Source Isolation:** By programmatically "subtracting" all possible SERP matches (even at extreme depths), researchers can isolate the true "LLM-native" grounding set—sources ChatGPT/Gemini access via internal knowledge bases, direct partnerships, or non-public indices.
9. **Decay Rate of Attribution:** Analyzing if the probability of an LLM citing a source correlates with its SERP rank even beyond the first few pages, or if the LLM's "internal" prioritization overrides search engine ranking at depth.

---

# Part 5: Conclusions & The Future of Search

## 5.1 The Convergence of SEO and GEO
- **GEO as SEO's Final Form:** Our data suggests that the "Extractive Nature" of GenAI means that to win in GEO, you must first win the fundamental elements of SEO (visibility, authority, and structured data).
- **The "High-Signal" Mandate:** As search becomes cheaper than inference, LLMs will increasingly rely on external retrieval. Content that is not "searchable" will become "invisible" to AI.

## 5.2 The Economic Moat of Retrieval
- **Compute Efficiency:** We conclude that the future of AI is not larger models, but smarter **orchestrators**. By using the web as a "distributed memory," AI providers can reduce costs while increasing accuracy.
- **The Relevance of Human-Centric Web:** SEO stays relevant because it provides the "Ground Truth" that AI requires to remain grounded and factual.

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
