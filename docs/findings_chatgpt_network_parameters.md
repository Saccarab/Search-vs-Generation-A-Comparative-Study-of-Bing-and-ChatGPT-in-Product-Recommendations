# Findings: ChatGPT Network Parameters & Citation Architecture

## Overview

This section presents findings derived from **474 ChatGPT runs** (237 Enterprise, 237 Personal) across **79 unique product-recommendation prompts**, each executed 3 times per account type. By intercepting ChatGPT's WebSocket stream, we captured the full internal pipeline — from the **Sonic Classifier's** search-trigger decision through to the **citation token mapping** in the final response. These network-level artifacts, typically invisible to end users, reveal the mechanics of how ChatGPT decides *whether* to search, *what* to search for, and *how* it attaches sources to its generated text.

---

## 1. The Sonic Classifier: ChatGPT's Search-Trigger Gate

### 1.1 What Is the Sonic Classifier?

Before ChatGPT generates a single word, every user message passes through an internal probabilistic gate called the **Sonic Classifier** (`sonic_classifier_5p2_3cls_ev3`). This lightweight model (snapshot: `wli-searchdb-model5-2025-09-23-20-17`) runs in under ~15 ms and outputs three probability scores that sum to 1.0:

| Parameter | Description |
|-----------|-------------|
| `simple_search_prob` | Probability the query requires a straightforward web search (single fan-out) |
| `complex_search_prob` | Probability the query requires a multi-step / deep research search (multiple fan-outs) |
| `no_search_prob` | Probability the query can be answered from parametric memory alone |

These probabilities are evaluated against **thresholds** in a fixed priority order (`threshold_order: ["no_search", "complex", "simple"]`):

| Threshold | Value | Interpretation |
|-----------|-------|----------------|
| `no_search_threshold` | **0.175** | If `no_search_prob` ≥ 17.5%, suppress search |
| `complex_search_threshold` | **0.400** | If `complex_search_prob` ≥ 40%, trigger deep/multi-query search |
| `simple_search_threshold` | **0.000** | Any remaining probability triggers a simple search (effectively a catch-all) |
| `force_search_first_turn_threshold` | **0.00001** | Near-zero — almost always forces search on a conversation's very first turn |

**Decision logic (evaluated in order):**
1. If `no_search_prob ≥ 0.175` → **skip search**, answer from parametric memory
2. Else if `complex_search_prob ≥ 0.4` → **complex search** (multiple fan-out queries)
3. Else → **simple search** (default single-query retrieval)

### 1.2 Additional Classifier Configuration

The Sonic Classifier operates with the following model configuration:

| Parameter | Value | Description |
|-----------|-------|-------------|
| `model_name` | `snc-pg-sw-3cls-ev3` | The classifier model identifier |
| `renderer_name` | `harmony_v4.0.15_16k_orion_text_only_no_asr_2k_action` | The rendering pipeline used to prepare context |
| `n_ctx` | 2048 | Context window for the classifier (tokens) |
| `max_message_tokens` | 2000 | Maximum token budget per message input |
| `num_messages` | 20 | Number of conversation turns the classifier considers |
| `remove_memory` | true | Classifier ignores saved user "memory" entries |
| `support_mm` | true | Multimodal input supported |
| `timeout` | 1 second | Hard timeout for the classifier decision |

**Token mapping:** The classifier is a 3-class model that maps its output tokens to decisions: token `"1"` = no_search, token `"7"` = simple_search, token `"5"` = complex_search.

### 1.3 Enterprise vs. Personal Differences

A notable structural difference exists between deployment types:

| Parameter | Enterprise | Personal |
|-----------|-----------|----------|
| `prefetch_threshold` | `null` (disabled) | **0.55** |
| `passthrough_tool_calls` | `true` | `null` |
| `passthrough_tool_names` | `["api_tool", "bio", "container", "gcal", "gcontacts", "gmail", "image_gen_no_temp_chat", "python", "python_user_visible"]` | `[]` (empty) |

The **prefetch_threshold** (0.55) on Personal accounts allows ChatGPT to begin fetching search results *before* the classifier fully resolves — a speculative prefetch optimization absent from Enterprise. Enterprise accounts instead have access to a broader set of **passthrough tools** (calendar, contacts, email), reflecting the workspace integration layer.

### 1.4 The "65% Search Probability" Claim vs. Our Data

Independent reverse-engineering research by [Resoneo](https://think.resoneo.com/chatgpt/) documents a `force_search_threshold` of **65%**, describing it as the primary activation trigger — if `search_prob` exceeds 65%, web search fires. This has been widely cited in online discussions of ChatGPT's search mechanics.

**Our data tells a different story.** The classifier configuration captured in our 474 runs uses a **three-class threshold system** rather than a single probability cutoff:

| Approach | Resoneo / Community Claim | Our Observed Configuration |
|----------|--------------------------|---------------------------|
| **Threshold model** | Single `force_search_threshold` = 65% | Three thresholds evaluated in order: `no_search` (17.5%), `complex` (40%), `simple` (0%) |
| **Decision logic** | If search_prob > 65% → search | If `no_search_prob` < 17.5% → search (effectively) |
| **Probability framing** | One score: "probability search is needed" | Three scores summing to 1.0 |

We cannot directly confirm or refute the 65% claim because the systems may differ:

1. **Different classifier versions.** Resoneo's observations may reflect an older or A/B-variant classifier. Our data captures `sonic_classifier_5p2_3cls_ev3` (snapshot `wli-searchdb-model5-2025-09-23-20-17`). The "65%" may correspond to a different `classifier_config_name` or an earlier 2-class model that used a single threshold.

2. **The 55% prefetch threshold is close.** Our Personal accounts show `prefetch_threshold: 0.55` — which is in the same ballpark as 65%. It is possible that the "65%" figure conflates the search *decision* threshold with the speculative *prefetch* threshold, or that the prefetch threshold was 65% in an earlier version and has since been lowered to 55%.

3. **Our runs were overwhelmingly high-confidence.** The median `simple_search_prob` in our data is **96.8%** — far above any plausible threshold. Only 2 runs fell below 70% (`simple_search_prob`), and those were the atypical P045 runs with high `complex_search_prob`. We simply don't have enough runs in the 50–70% zone to test where the effective boundary lies.

**What we can confirm:** In our data, the effective search-trigger boundary is controlled by `no_search_prob ≥ 0.175` (if no-search probability exceeds 17.5%, search is suppressed). The highest `no_search_prob` we observed was 17.37% — just barely below this gate — and that run *did* trigger search. This threshold-first architecture is functionally different from a "if search_prob > X" model, because it evaluates the *no-search* class first rather than the search class.

---

## 2. Search Trigger Rates: When Does ChatGPT Actually Search?

### 2.1 Overall Rates

Across all 474 runs:

| Condition | Runs | Percentage |
|-----------|------|------------|
| **Search triggered** | 422 | **89.03%** |
| **Search not triggered** | 52 | **10.97%** |

For product-recommendation queries, ChatGPT triggered web search in nearly **9 out of 10** runs. This high rate aligns with the near-zero `force_search_first_turn_threshold` (0.00001) — since all our prompts were first-turn messages in fresh conversations, the classifier was strongly biased toward searching.

### 2.2 By Account Type

| Account Type | Total | Search Triggered | % Triggered | No Search | % No Search |
|--------------|-------|-----------------|-------------|-----------|-------------|
| **Enterprise** | 237 | 216 | **91.14%** | 21 | 8.86% |
| **Personal** | 237 | 206 | **86.92%** | 31 | 13.08% |

Enterprise accounts triggered search **4.22 percentage points more often** than Personal accounts. This gap may relate to the absence of the prefetch mechanism on Enterprise (making the classifier's binary decision more deterministic) or to subtle A/B test configuration differences between deployment tiers.

### 2.3 Prompt-Level Search Consistency

Of the 79 unique prompts:

| Behavior | Prompt Count | % of Prompts |
|----------|-------------|--------------|
| **Always triggered search** (all 6 runs) | 61 | 77.2% |
| **Mixed** (some runs triggered, some didn't) | 12 | 15.2% |
| **Never triggered search** (all runs) | 6 | 7.6% |

The **6 prompts that never triggered search** (P013, P036, P056, P059, P062, P067) represent cases where the Sonic Classifier consistently judged the query answerable from parametric knowledge. These tended to be generic how-to queries (e.g., *"How can I convert an audio file to text?"*) where the model's training data contained sufficient coverage.

Among the 12 mixed-behavior prompts, **P016** stands out with a perfect 50/50 split (3 triggered, 3 didn't), illustrating the stochastic nature of the classifier operating near its decision boundary.

### 2.4 Classifier Probability Distributions: What the Sonic Classifier Actually Decided

Across all 435 runs with valid sonic classification data, the probability distributions reveal that our product-recommendation prompts occupied a narrow band of the classifier's decision space:

| Metric | `simple_search_prob` | `complex_search_prob` | `no_search_prob` |
|--------|---------------------|-----------------------|------------------|
| **Min** | 0.6318 | 0.000246 | 0.000947 |
| **Median** | 0.9680 | 0.00293 | 0.01128 |
| **Max** | 0.9984 | 0.3056 | 0.1737 |
| **p25** | — | 0.00136 | 0.00493 |
| **p75** | — | 0.01475 | 0.04276 |
| **p95** | — | 0.24217 | 0.10419 |

**Key observation:** The median `simple_search_prob` is **96.8%** — the classifier was nearly certain on most prompts that a simple web search was the correct action. Product recommendation queries are, by nature, straightforward information-seeking tasks that the classifier handles with high confidence.

#### 2.4.1 Complex Search: Never Triggered

**The `complex_search_threshold` (0.4) was never reached in any of our 474 runs.** The highest observed `complex_search_prob` was **0.3056** (P020, enterprise — *"Request a tool to translate foreign audio to English in real-time during video playback"*).

The top 5 prompts by `complex_search_prob`:

| Prompt | Enterprise | Personal | Prompt Text |
|--------|-----------|----------|-------------|
| P020 | **0.3056** | 0.2970 | *"Request a tool to translate foreign audio to English in real-time during video playback."* |
| P046 | 0.2949 | 0.2872 | *"What are direct competitors of Doctranslate that offer similar translation services for text, audio, video, and live translation?"* |
| P053 | **0.2591** | — | *"Can you recommend the best free AI text-to-speech software with celebrity voices for IoT applications?"* |
| P047 | 0.2602 | 0.2535 | *"I need a Chrome extension for live Chinese to English translation that works better than the built-in live caption feature."* |
| P045 | 0.2422 | 0.2324 | *"What are the biggest opportunities for live speech translation in sports arenas and football stadiums?"* |

These share a pattern: **multi-constraint prompts** that combine specific technical requirements (real-time, competitor analysis, named entities, cross-platform). Even so, none crossed the 0.4 bar. For product-recommendation queries, the "complex search" pathway exists in the architecture but was never activated — the classifier treats them uniformly as simple retrieval tasks.

#### 2.4.2 No-Search Threshold: Never Crossed Either

**The `no_search_threshold` (0.175) was also never reached via the classifier's own probability output.** The closest was **P016 enterprise at 0.1737** — missing the cutoff by just **0.0013** (*"I need live transcribing while using online streaming or watching videos"*).

Top `no_search_prob` values:

| Prompt | Enterprise | Personal | Prompt Text |
|--------|-----------|----------|-------------|
| P016 | **0.1737** | 0.1077 | *"I need live transcribing while using online streaming or watching videos."* |
| P011 | 0.1594 | 0.1331 | *"How can I quickly and for free convert text to speech?"* |
| P060 | 0.1236 | 0.0938 | *"Anlik ceviri yapan programlar nelerdir?"* (Turkish) |
| P008 | 0.1042 | 0.1202 | *"Is there an AI that changes your voice?"* |

These tend to be **generic, well-known tasks** (text-to-speech, transcription, voice changing) where the model's training data likely covers the answer space. The Turkish-language prompt (P060) also scored high, possibly because the classifier has lower confidence about non-English query intent.

#### 2.4.3 The Real Suppression Mechanism

Since neither threshold was actually crossed, **the 52 no-search runs in our dataset were caused by mechanisms external to the Sonic Classifier's probability output:**

- **39 runs** had **null sonic classification** entirely (P013, P036, P056, P059, P062, P067 — all runs) — the classifier never executed, and the raw network response files were empty (`[]`). These likely represent server-side routing decisions or session-level suppressions that preempted the classifier.
- **13 runs** had valid sonic data with high `simple_search_prob` (up to 0.997) yet `web_search_triggered: false`. These represent **post-classifier overrides** — the classifier recommended search, but something downstream (tool routing via `passthrough_tool_calls`, A/B test gates, or rate limiting) suppressed it.

| Run | simple_search_prob | no_search_prob | Search? | Account |
|-----|-------------------|----------------|---------|---------|
| P071_r1 | **99.73%** | 0.24% | **No** | Personal |
| P028_r2 | **99.38%** | 0.58% | **No** | Personal |
| P077_r1 | **99.13%** | 0.15% | **No** | Personal |
| P014_r3 | **98.56%** | 1.20% | **No** | Personal |
| P012_r2 | **97.97%** | 1.13% | **No** | Personal |
| P001_r3 | **97.22%** | 2.00% | **No** | Enterprise |
| P076_r1 | **96.72%** | 2.93% | **No** | Personal |
| P004_r1 | **93.91%** | 4.20% | **No** | Enterprise |
| P026_r3 | **92.23%** | 5.26% | **No** | Personal |
| P004_r1 | **91.64%** | 5.55% | **No** | Personal |
| P045_r1 | **68.46%** | 8.30% | **No** | Personal |
| P045_r2 | **68.31%** | 7.47% | **No** | Enterprise |

11 of 13 overridden runs occurred on **Personal accounts**, and they often affected only a single run (r1) while r2 and r3 for the same prompt triggered search normally — pointing to non-deterministic server-side factors rather than prompt-level characteristics.

---

## 3. Citation Output: Search vs. No-Search Runs

### 3.1 Citation Volume by Search Status

| Condition | N Runs | Avg Citations per Run |
|-----------|--------|----------------------|
| **Search triggered** | 422 | **9.94** |
| **Search not triggered** | 52 | **2.62** |

Runs backed by web search produced **~4x more citations** on average. Breaking this down further:

| Account | Search-Triggered Avg | No-Search Avg |
|---------|---------------------|---------------|
| Enterprise | 9.98 (n=216) | **1.10** (n=21) |
| Personal | 9.90 (n=206) | **3.65** (n=31) |

Enterprise non-search runs averaged just **1.10 citations** — near zero sourcing. Personal non-search runs still managed **3.65 citations**, suggesting Personal accounts more readily generate citation-like references from parametric memory even without live retrieval.

### 3.2 Edge Cases: Citations Without Search

**18 runs** produced citations despite `web_search_triggered: false`. These split into two distinct patterns:

**Pattern A — "Ghost Citations" (cited_sources = 0):**

| Run | Citations | Cited Sources | Account |
|-----|-----------|---------------|---------|
| P012_r2 | 9 | 0 | Personal |
| P016_r1 | 10 | 0 | Personal |
| P016_r2 | 7 | 0 | Personal |
| P016_r3 | 6 | 0 | Personal |
| P036_r1 | 4 | 0 | Personal |
| P036_r2 | 5 | 0 | Personal |
| P036_r3 | 4 | 0 | Personal |

These runs generated numbered citation markers in the output text but mapped to **zero actual URLs** — the model hallucinated citation formatting from parametric memory. This "ghost citation" phenomenon occurred exclusively on Personal accounts.

**Pattern B — Parametric URL Recall:**

| Run | Citations | Cited Sources | Account |
|-----|-----------|---------------|---------|
| P026_r3 | 12 | 12 | Personal |
| P071_r1 | 14 | 13 | Personal |
| P074_r1 | 7 | 7 | Personal |
| P077_r1 | 10 | 10 | Personal |
| P001_r3 | 12 | 8 | Enterprise |

These runs produced **fully sourced citations without any live search**, meaning the model recalled real URLs from its training data. P071_r1 is the most extreme case: 14 citations with 13 verified sources, entirely from parametric knowledge.

---

## 4. Hidden Queries & Fan-Out Architecture

When search is triggered, ChatGPT does not send the user's exact prompt to its search provider. Instead, the system generates **hidden queries** (`hidden_queries` / `search_model_queries`) — reformulated, keyword-optimized search strings invisible to the user. This reformulation step mirrors traditional search-engine query rewriting but occurs entirely within ChatGPT's pipeline.

### 4.1 The `web.run` Tool-Call Chain: How Fan-Out Actually Works

Inspecting the raw WebSocket stream reveals that fan-out is not a single event where N queries are dispatched at once. It is an **iterative agentic loop** built on a tool called `web.run`. The generation model (gpt-5-2, orchestrated through the Sonicberry layer `alpha.sonic_thinky_v1_paid`) calls `web.run` as a tool, receives results, and then *decides whether to call it again*. Each `web.run` invocation always dispatches exactly **2 queries** (a fixed pair-generation strategy). The key network field is `search_turns_count`, which increments with each successive round:

**Standard run (2 queries) — 1 `web.run` call:**
```
web.run #1  →  2 queries  →  search_turns_count: 1  →  model proceeds to generate response
```

**Extended run (4 queries) — 2 `web.run` calls:**
```
web.run #1  →  2 queries  →  search_turns_count: 1  →  model evaluates results
                                                       →  decides: "not enough"
web.run #2  →  2 queries  →  search_turns_count: 2  →  model proceeds to generate response
```

**Maximum observed (6 queries) — 3 `web.run` calls:**
```
web.run #1  →  2 queries  →  search_turns_count: 1  →  model evaluates results
                                                       →  decides: "not enough"
web.run #2  →  2 queries  →  search_turns_count: 2  →  model evaluates results
                                                       →  decides: "still not enough"
web.run #3  →  2 queries  →  search_turns_count: 3  →  model proceeds to generate response
```

This means there is no upfront "plan 6 queries" decision. The model issues a standard 2-query search, sees the results in its context, and makes a real-time judgment call on whether to search again. The Sonic Classifier plays no role in this loop — it fires once at the start to decide *whether* to search at all. Everything after that is the generation model's own agentic behavior.

### 4.2 Evidence from Raw Network Responses

The `web.run` tool calls appear as separate message objects in the WebSocket stream, each authored by `tool:web` with metadata from the Sonicberry orchestration layer. Key fields per call:

| Field | Description |
|-------|-------------|
| `author.name` | Always `"web.run"` |
| `author.metadata.sonicberry_model_id` | `"alpha.sonic_thinky_v1_paid"` — the orchestration layer that decides whether to re-search |
| `author.metadata.source` | `"sonic_tool"` |
| `search_model_queries.queries` | Array of exactly 2 reformulated search strings |
| `search_turns_count` | Incremental counter: 1, 2, 3... per successive call |
| `search_source` | `"composer_auto"` — indicates the search was auto-triggered, not user-forced |
| `parent_id` | Links to the previous message in the chain |

**Empirical data across all extended fan-out runs:**

| Run | `web.run` Calls | `search_turns_count` Progression | Total Queries | Chained? | Inter-Call Timing |
|-----|----------------|----------------------------------|---------------|----------|-------------------|
| P001_r1 (baseline) | 1 | [1] | 2 | — | — |
| P073_r1 (baseline) | 1 | [1] | 2 | — | — |
| P035_r1 (4q) | 2 | [1, 2] | 4 | No | 1,174 ms |
| P053_r1 (4q) | 2 | [1, 2] | 4 | No | 1,180 ms |
| P053_r2 (4q) | 2 | [1, 2] | 4 | No | 1,258 ms |
| P050_r3 (4q) | 2 | [1, 2] | 4 | No | 1,183 ms |
| P063_r1 (4q) | 2 | [1, 2] | 4 | No | 1,543 ms |
| **P073_r3 (6q)** | **3** | **[1, 2, 3]** | **6** | **Yes** | **484 ms, 341 ms** |

**Observations:**
- **All 4-query runs** have exactly 2 `web.run` calls with `search_turns_count` progressing [1, 2]. The second call fires ~1.2 seconds after the first — enough time for the model to receive and evaluate the first batch of results.
- **The 6-query run (P073_r3)** has 3 `web.run` calls with `search_turns_count` [1, 2, 3]. Notably, these calls are **chained** (each `parent_id` = the previous call's `message_id`), forming a sequential dependency chain. The inter-call timing is tighter (484 ms, 341 ms), suggesting the model quickly determined each round was insufficient.
- **The 4-query runs are NOT chained** — the second `web.run`'s `parent_id` does not point to the first `web.run`. This suggests they may be triggered by a different mechanism (e.g., the model's initial query plan rather than a reactive "results weren't good enough" judgment).

### 4.3 Fan-Out Distribution

Given the `web.run` architecture (always 2 queries per call), the total query count is always a multiple of 2:

| Total Queries | `web.run` Calls | Runs | Percentage | Description |
|---------------|----------------|------|------------|-------------|
| **0** | 0 | 14 | 3.2% | No search / null classification |
| **2** | 1 | 409 | **94.0%** | Single search turn (standard) |
| **4** | 2 | 11 | 2.5% | Two search turns (extended) |
| **6** | 3 | 1 | 0.2% | Three search turns (maximum observed) |

Odd-numbered query counts (1, 3, 5) are **architecturally impossible** — the `web.run` tool always dispatches pairs. This explains the absence of 1-query and 3-query runs that we initially noted as "striking."

**By account type:**

| Account | 0 queries | 2 queries (1 turn) | 4+ queries (2+ turns) |
|---------|-----------|--------------------|-----------------------|
| Enterprise (n=219) | 7 (3.2%) | 203 (92.7%) | **9 (4.1%)** |
| Personal (n=216) | 7 (3.2%) | 206 (95.4%) | **3 (1.4%)** |

Enterprise accounts trigger multi-turn search at **~3x the rate** of Personal accounts (4.1% vs 1.4%), suggesting the Sonicberry layer is more willing to re-search on enterprise deployments.

### 4.4 The Standard Single-Turn Search (94% of Runs)

The dominant pattern: one `web.run` call → 2 queries → done. The two queries are typically one synonym-substituted variant and one structurally reorganized variant:

**Example — P001_r1** (*"Which free AI would you recommend for translating my video?"*):
```
web.run #1 (search_turns_count: 1):
  → "free AI tools for translating videos"        (keyword extraction)
  → "free AI video translation tools"              (noun-phrase restructuring)
```

**Example — P001_r2** (same prompt, different run):
```
web.run #1 (search_turns_count: 1):
  → "free AI tools to translate video"             (verb form change)
  → "free video translation AI service"            (reordered + broadened)
```

The classifier probabilities for these standard runs show consistently low `complex_search_prob` (median: 0.003), confirming the system treats single-turn, 2-query fan-out as its "simple search" operation.

### 4.5 Multi-Turn Search (4–6 Queries): The Agentic Re-Search Loop

The 12 runs with 4+ queries were **not classified as complex search** by the Sonic Classifier — none crossed the 0.4 threshold. The additional search turns are initiated by the generation model itself, after evaluating the first round of results.

| Run | Turns | Queries | `complex_search_prob` | Prompt |
|-----|-------|---------|----------------------|--------|
| P035 (all 6 runs) | 2 | **4** | 0.069 | *"Can you list translation services with live interpreters and their 2-day pricing?"* |
| P053 (r1–r3, enterprise) | 2 | **4** | **0.259** | *"Can you recommend the best free AI text-to-speech software with celebrity voices for IoT applications?"* |
| P050_r3 (enterprise) | 2 | **4** | 0.003 | *"Can you recommend a free app for live time translation during a call with French speakers?"* |
| P063_r1 (enterprise) | 2 | **4** | 0.037 | *"What is the best machine translation tool for live translation that saves context?"* |
| **P073_r3 (enterprise)** | **3** | **6** | 0.012 | *"Can you recommend the best video translator for YouTube?"* |

**Correlation between `complex_search_prob` and multi-turn behavior:**

| Search Turns | Avg `complex_search_prob` | Min | Max | N |
|-------------|--------------------------|-----|-----|---|
| 1 turn (2q) | 0.025 | 0.000246 | 0.3056 | 409 |
| 2+ turns (4q+) | **0.104** | 0.003 | 0.259 | 12 |

The average is ~4x higher for multi-turn runs, but the relationship is loose. P050_r3 had `complex_search_prob` of just 0.27% yet still re-searched, while some single-turn runs reached 30.6% without re-searching. The decision to re-search is made by the generation model at inference time, not by the classifier.

### 4.6 Detailed Breakdown: What the Model Searches For in Each Turn

Below is the complete per-run breakdown showing the full sonic classifier output and the actual queries dispatched in each `web.run` call. A critical observation: **the classifier outputs are deterministic** for the same prompt+account combination (identical probabilities across r1/r2/r3), but **the re-search decision is non-deterministic** — the same prompt can produce 1 search turn on one run and 3 on another.

---

#### P035 — *"Can you list translation services with live interpreters and their 2-day pricing?"*
**2 search turns on all 6 runs (enterprise + personal) — the only consistently multi-turn prompt**

| Parameter | Enterprise | Personal |
|-----------|-----------|----------|
| `simple_search_prob` | 0.9260 (92.60%) | 0.9262 (92.62%) |
| `complex_search_prob` | **0.0693** (6.93%) | **0.0688** (6.88%) |
| `no_search_prob` | 0.0047 (0.47%) | 0.0049 (0.49%) |
| `latency_ms` | 9.74 | 2.60 |

**Enterprise — Turn 1 (`search_turns_count: 1`):**
```
  → "translation services with live interpreters pricing 2 day cost live interpreter service pricing"
  → "live interpreter translation services 2 day pricing interpreter on demand translation live interpreters cost"
```
**Enterprise — Turn 2 (`search_turns_count: 2`):**
```
  → "Jeenie live interpreter pricing per minute or per session Jeenie translation live interpreters cost"
  → "does Jeenie or similar service list pricing or 2-day event pricing live interpreters Jeenie or Boostlingo pricing"
```

**Personal — Turn 1:**
```
  → "translation services with live interpreters 2-day pricing live interpreter translation services cost pricing"
  → "translation services offering live interpreters pricing for short sessions or 2 day conferences..."
```
**Personal — Turn 2:**
```
  → "LanguageLine Solutions interpreting pricing and plans or packages live interpreters LanguageLine Solutions pricing"
  → "Boostlingo live interpreter services pricing and plans for interpreting services"
```

**Analysis:** Turn 1 uses broad keyword variants. Turn 2 pivots to **specific named services** (Jeenie, Boostlingo, LanguageLine) — the model saw the initial results, identified relevant vendors, and issued targeted follow-up queries for their pricing. Enterprise and personal name *different* services in Turn 2, suggesting the model draws on different parametric knowledge per deployment when constructing follow-up queries.

---

#### P053 — *"Can you recommend the best free AI text-to-speech software with celebrity voices for IoT applications?"*
**2 search turns on enterprise r1–r3 only (personal stayed at 1 turn)**

| Parameter | Enterprise | Personal (1 turn) |
|-----------|-----------|----------|
| `simple_search_prob` | **0.7358** (73.58%) | — |
| `complex_search_prob` | **0.2591** (25.91%) | — |
| `no_search_prob` | 0.0051 (0.51%) | — |

**Enterprise — Turn 1:**
```
  → "free AI text to speech software with celebrity voices for IoT applications"
  → "best free TTS celebrity voices API IoT text to speech celebrity voices freeware"
```
**Enterprise — Turn 2:**
```
  → "Uberduck FakeYou free celebrity TTS API for developers IoT"
  → "are free celebrity TTS voices allowed in applications and their limitations"
```

**Analysis:** Highest `complex_search_prob` of any multi-turn run (25.91%). Turn 2 splits into two angles: **named-entity lookup** (Uberduck, FakeYou) and a **legal/limitation question** — the model recognized the prompt implies both "what exists" and "can I use it." Only enterprise re-searched; personal found Turn 1 results sufficient.

---

#### P050_r3 — *"Can you recommend a free app for live time translation during a call with French speakers?"*
**2 search turns on enterprise r3 only (r1, r2 stayed at 1 turn)**

| Parameter | Enterprise |
|-----------|-----------|
| `simple_search_prob` | **0.9958** (99.58%) |
| `complex_search_prob` | **0.0027** (0.27%) |

**Turn 1:**
```
  → "free app live translation during a call French speakers real time translation app"
  → "applications that translate live voice calls French free"
```
**Turn 2:**
```
  → "Google Translate app live conversation translation free French English conversation mode phone"
  → "Microsoft Translator app real time voice conversation translation support French"
```

**Analysis:** `complex_search_prob` was near-zero (0.27%), yet the model still re-searched — naming Google Translate and Microsoft Translator explicitly in Turn 2. The classifier had zero signal this would happen. The same prompt on r1 and r2 with identical classifier values produced only 1 turn each, proving the re-search decision is stochastic.

---

#### P063_r1 — *"What is the best machine translation tool for live translation that saves context?"*
**2 search turns on enterprise r1 only**

| Parameter | Enterprise |
|-----------|-----------|
| `simple_search_prob` | 0.9548 (95.48%) |
| `complex_search_prob` | **0.0374** (3.74%) |

**Turn 1:**
```
  → "best machine translation tool for live translation that maintains context"
  → "tools supporting live translation with contextual memory features"
```
**Turn 2:**
```
  → "which live translation tools maintain conversation context or memory in translation? contextual memory in live translation"
  → "machine translation live translation maintaining context features translation memory or adaptive context in real-time tools"
```

**Analysis:** Unlike other multi-turn runs, Turn 2 does **not** name specific products. Instead it progressively disambiguates the concept — from "saves context" → "contextual memory" → "translation memory" → "adaptive context." The model recognized the user's term was ambiguous and used Turn 2 to cast a wider semantic net.

---

#### P073_r3 — *"Can you recommend the best video translator for YouTube?"*
**3 search turns (maximum observed) — enterprise r3 only**

| Parameter | Enterprise (all runs identical) |
|-----------|-----------|
| `simple_search_prob` | 0.9774 (97.74%) |
| `complex_search_prob` | **0.0124** (1.24%) |
| `latency_ms` | 4.33 (r3) / 9.08 (r1) / 14.16 (r2) |

**Cross-run comparison (same prompt, same classifier output, different fan-out):**

| Run | Search Turns | Total Queries |
|-----|-------------|---------------|
| P073_r1 | 1 | 2 |
| P073_r2 | 1 | 2 |
| **P073_r3** | **3** | **6** |

**P073_r3 — Turn 1 (`search_turns_count: 1`):**
```
  → "best video translator for YouTube translate videos subtitles tools"
  → "YouTube video translator tools comparison automatic translation subtitles for YouTube"
```
**P073_r3 — Turn 2 (`search_turns_count: 2`, +484 ms):**
```
  → "tools to translate YouTube videos subtitles or audio translate YouTube video translator"
  → "best YouTube video translation tools automatic subtitle translation and dubbing for YouTube"
```
**P073_r3 — Turn 3 (`search_turns_count: 3`, +341 ms):**
```
  → "best tools to translate YouTube videos subtitles automatic translate and dubbing YouTube translation tools"
  → "how to translate YouTube video subtitles or audio - tools like VEED, Kapwing, Happy Scribe"
```

**Analysis:** This is the definitive proof that **fan-out is decoupled from the Sonic Classifier.** The classifier produced byte-identical outputs for all 3 runs (`simple_search_prob` = 0.9773789267643763 to 16 decimal places), yet r1/r2 completed in 1 turn and r3 required 3 turns. Turns 1–2 are largely synonymous broad reformulations. Only Turn 3's second query names specific tools (VEED, Kapwing, Happy Scribe) — suggesting the model kept re-searching because the generic queries weren't surfacing the product-level specificity it wanted. The tight timing (484 ms, 341 ms between turns) indicates rapid dissatisfaction with results rather than deep evaluation.

### 4.7 Three Strategies for Re-Search

Across all multi-turn runs, the generation model employs three distinct re-search strategies in Turn 2+:

| Strategy | Runs | Description |
|----------|------|-------------|
| **Named-entity drill-down** | P035, P050, P053 | Turn 1 returns broad results; Turn 2 queries name specific products/services identified from Turn 1 results or parametric memory (e.g., *"Jeenie pricing"*, *"Google Translate conversation mode"*) |
| **Semantic disambiguation** | P063 | The original prompt uses an ambiguous term; Turn 2 rephrases it into multiple technical synonyms to broaden coverage (e.g., "saves context" → "translation memory", "adaptive context") |
| **Exhaustive re-query** | P073_r3 | Turns 2–3 are near-synonymous reformulations of Turn 1, with a named-entity query appended last — suggesting the model was unsatisfied with result quality and brute-forced additional coverage |

### 4.8 Summary: The Agentic Search Architecture

The fan-out findings reveal a three-layer architecture:

```
Layer 1: SONIC CLASSIFIER (fires once)
  → Decides: search vs. no-search (vs. complex, though never triggered)
  → Deterministic for same input
  → Outputs: simple_search_prob, complex_search_prob, no_search_prob

Layer 2: SONICBERRY ORCHESTRATOR (alpha.sonic_thinky_v1_paid)
  → Manages the web.run tool-call loop
  → Each web.run always dispatches exactly 2 queries
  → Tracks search_turns_count (1, 2, 3...)

Layer 3: GENERATION MODEL (gpt-5-2)
  → After each web.run, evaluates results in context
  → Decides whether to call web.run again (re-search)
  → Non-deterministic: same input can produce 1–3 turns
  → Uses parametric knowledge to construct follow-up queries
```

Key implications:

1. **The Sonic Classifier does NOT control fan-out count.** It is a binary search/no-search gate. The classifier's `complex_search_prob` has a loose correlation with multi-turn behavior (~4x higher average) but is neither necessary (P050: 0.27% → 2 turns) nor sufficient (P020: 30.6% → 1 turn).

2. **Extended fan-out is an emergent behavior of the generation model**, not a planned-in-advance decision. The model acts as an agent that can iteratively call tools, similar to how it calls the Python or image generation tools.

3. **The 2-query-per-call invariant** means total query counts are always multiples of 2. Odd counts are architecturally impossible.

4. **Re-search is non-deterministic.** P073 had byte-identical classifier outputs across 3 runs but produced 2, 2, and 6 queries respectively. P035 is the only prompt that consistently triggered multi-turn search, suggesting its structure (explicit pricing request) reliably causes the model to judge initial results as insufficient.

5. **Enterprise accounts re-search 3x more often** (4.1% vs 1.4%), which may reflect different Sonicberry configurations or generation model behavior across deployment tiers.

### 4.9 Zero-Query Runs

The 14 runs with empty `hidden_queries` arrays cluster around 3 prompts (P004, P029, P045) and represent cases where the search pipeline was entered but no queries were ultimately dispatched — possibly due to the same post-classifier suppression mechanism identified in Section 2.4.3.

---

## 5. Citation Architecture: The Three-Tier Visibility Model

### 5.1 Citation Token Structure

Each citation in ChatGPT's output is encoded as a **citation token** embedded in the response stream, following the format:

```
citeturn{turn_index}search{ref_index}
```

For example, `citeturn0search0` refers to the **first search result** from **turn 0** of the conversation. These tokens are parsed client-side and rendered as clickable superscript numbers.

### 5.2 Three Tiers of Source Visibility

Our network data reveals that ChatGPT distinguishes between three tiers of source visibility:

| Tier | Label | User Visibility | Description |
|------|-------|-----------------|-------------|
| **1. Citations** | `"cited"` | **High** — inline superscript + Sources panel | These are the numbered links shown at the end of sentences and listed in the expandable "Sources" panel |
| **2. Additional Sources** | `"additional"` | **Medium** — buried in "More" section | Appear below the cited sources in a collapsed "More" section. Retrieved but not directly referenced in the text |
| **3. Hidden/Internal** | `"hidden"` | **None** — invisible to users | Grounding URLs used internally for context but never displayed. Academic sources (Wikipedia, arXiv) and corporate pages dominate this tier |

**Aggregate counts across all 474 runs:**

| Tier | Total Sources | Avg per Run |
|------|--------------|-------------|
| Cited | 3,476 | 7.33 |
| Additional | 7,326 | 15.46 |
| **Total retrieved** | **10,802** | **22.79** |

The system retrieves on average **~23 sources per run** but only surfaces **~7 as visible citations** — meaning roughly **68% of retrieved sources are demoted to "Additional" or hidden status**. This selective surfacing is the core mechanism through which ChatGPT exercises editorial control over which sources reach the user.

---

## 6. Network Parameter Glossary

A complete reference of the parameters captured from the ChatGPT WebSocket stream:

### 6.1 Sonic Classifier Output

| Parameter | Type | Description |
|-----------|------|-------------|
| `simple_search_prob` | float (0–1) | Probability that a simple single-query web search is needed |
| `complex_search_prob` | float (0–1) | Probability that a complex multi-query search is needed |
| `no_search_prob` | float (0–1) | Probability that no web search is required (parametric answer sufficient) |
| `latency_ms` | float | Time (in milliseconds) for the classifier to reach its decision |
| `decision_source` | string | Origin of the search decision (typically `"classifier"`) |
| `classifier_config_name` | string | Active A/B test variant identifier (e.g., `sonic_classifier_5p2_3cls_ev3`) |
| `classifier_snapshot_id` | string | Model checkpoint identifier with training date |

### 6.2 Threshold Configuration

| Parameter | Type | Description |
|-----------|------|-------------|
| `no_search_threshold` | float | Minimum `no_search_prob` to suppress search (0.175 = 17.5%) |
| `complex_search_threshold` | float | Minimum `complex_search_prob` to trigger complex search (0.4 = 40%) |
| `simple_search_threshold` | float | Minimum `simple_search_prob` to trigger simple search (0 = always passes) |
| `force_search_first_turn_threshold` | float | Near-zero threshold forcing search on first conversation turn (0.00001) |
| `prefetch_threshold` | float/null | Speculative search prefetch trigger; **0.55 on Personal**, `null` on Enterprise |
| `threshold_order` | array | Evaluation order for threshold checks: `["no_search", "complex", "simple"]` |

### 6.3 Classifier Model Configuration

| Parameter | Type | Description |
|-----------|------|-------------|
| `model_name` | string | Classifier model identifier (`snc-pg-sw-3cls-ev3`) |
| `renderer_name` | string | Context rendering pipeline for the classifier |
| `n_ctx` | int | Classifier context window in tokens (2048) |
| `max_message_tokens` | int | Max tokens per input message (2000) |
| `num_messages` | int | Number of conversation turns considered (20) |
| `remove_memory` | bool | Whether to strip saved "memory" items from classifier input |
| `no_search_token` / `simple_search_token` / `complex_search_token` | string | Output token IDs mapping to each class (`"1"`, `"7"`, `"5"`) |
| `timeout` | int | Hard timeout in seconds for classifier inference (1) |

### 6.4 Search & Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `web_search_triggered` | bool | Whether the run actually performed a web search |
| `web_search_forced` | bool | Whether search was force-enabled by system rules (bypassing classifier) |
| `generated_search_query` | string | The primary reformulated query sent to the search provider |
| `hidden_queries` | array | All internal fan-out query variants generated for retrieval (aggregated across all search turns) |
| `passthrough_tool_calls` | bool/null | Whether non-search tools can preempt the search decision |
| `passthrough_tool_names` | array | List of tools that can intercept instead of search (Enterprise only) |

### 6.5 `web.run` Tool-Call Parameters (per search turn)

| Parameter | Type | Description |
|-----------|------|-------------|
| `author.name` | string | Always `"web.run"` — identifies this as a search tool invocation |
| `author.metadata.sonicberry_model_id` | string | Orchestration layer model (`"alpha.sonic_thinky_v1_paid"`) — the Sonicberry agent managing the search loop |
| `author.metadata.source` | string | Always `"sonic_tool"` — marks this as a Sonic-system tool call |
| `search_model_queries.type` | string | Always `"search_model_queries"` |
| `search_model_queries.queries` | array | Exactly 2 reformulated search strings dispatched in this turn |
| `search_turns_count` | int | Incremental counter tracking which search turn this is (1 = first, 2 = re-search, 3 = second re-search) |
| `search_source` | string | How the search was initiated; `"composer_auto"` = auto-triggered by the system |
| `client_reported_search_source` | string | Client-side echo of search_source |
| `parent_id` | string | UUID of the previous message — reveals whether search turns are chained (sequential dependency) or independent |
| `model_slug` | string | Generation model used (e.g., `"gpt-5-2"`) |
| `model_switcher_deny` | array | Lists models that cannot be switched to mid-conversation due to search tool incompatibility (e.g., `gpt-5-2-pro`, `gpt-5-1-pro`, `gpt-5-pro` — all marked `"unsupported_tool_search"`) |

### 6.6 Citation Mapping Fields

| Parameter | Type | Description |
|-----------|------|-------------|
| `citation_token` | string | Encoded reference ID (e.g., `citeturn0search0`) |
| `token_position.start_idx` / `end_idx` | int | Character offsets of the citation token in the raw response stream |
| `type` | string | Visibility tier: `"cited"`, `"additional"`, or `"hidden"` |
| `sources` | array | Matched source objects from the search result groups |
| `inline_url` | string | The URL rendered in the citation link |
| `url_position` | int | Character offset where the URL appears in text |
| `claim_text` | string | The surrounding text passage this citation supports |
| `url_index` | int | Sequential index of this URL within the run's citation list |

### 6.7 Source Metadata (per source in `sources[]`)

| Parameter | Type | Description |
|-----------|------|-------------|
| `url` | string | Full URL of the source |
| `title` | string | Page title as returned by the search provider |
| `snippet` | string | Preview text / meta description |
| `domain` | string | Extracted root domain |
| `ref_type` | string | Source retrieval method (typically `"search"`) |
| `ref_index` | int | Position in the search results returned to the model |
| `turn_index` | int | Conversation turn during which this source was retrieved |
| `pub_date` | string/null | Publication date (when available from the search provider) |
| `ref_key` | string | Composite key: `"{turn_index}_{ref_type}_{ref_index}"` |

---

## 7. Key Takeaways

1. **ChatGPT searches ~89% of the time** for product-recommendation queries, confirming the RAG-dependent nature of commercial search. The remaining ~11% relied on parametric memory, producing significantly fewer (and sometimes hallucinated) citations.

2. **All 474 runs fell into "simple search" territory.** Neither the `complex_search_threshold` (0.4) nor the `no_search_threshold` (0.175) was ever crossed by the classifier's probability output. The closest miss was P016 enterprise with `no_search_prob` = 0.1737 — just 0.0013 short of the 17.5% gate. For product-recommendation queries, the Sonic Classifier's three-class architecture effectively collapses to a single class: simple search.

3. **The 52 no-search runs were caused by external suppression, not the classifier.** 39 runs had null classification (classifier never executed), and 13 had the classifier overridden despite `simple_search_prob` as high as 99.7%. This points to server-side A/B gates, tool routing, or session-level factors operating independently of the Sonic probabilities — predominantly affecting Personal accounts (11 of 13 overrides).

4. **Fan-out is an agentic re-search loop, not a planned dispatch.** The `web.run` tool always sends exactly 2 queries per call. Extended fan-out (4 or 6 queries) happens when the generation model (gpt-5-2), after evaluating initial results, decides to call `web.run` again — tracked by the `search_turns_count` field incrementing [1] → [1, 2] → [1, 2, 3]. This makes odd query counts architecturally impossible and explains the discrete 0/2/4/6 distribution.

5. **The Sonic Classifier does NOT control fan-out count.** The classifier fires once and decides search vs. no-search. The re-search loop is driven by the generation model's own judgment of result quality. P073 proves this definitively: byte-identical classifier outputs (`simple_search_prob` = 0.9774 to 16 decimal places) across 3 runs produced 2, 2, and 6 queries respectively. P050 re-searched with a `complex_search_prob` of just 0.27%, while P020 did not re-search at 30.6%.

6. **Enterprise accounts behave differently at both layers.** Enterprise searches more consistently (91.1% vs 86.9%) and re-searches 3x more often (4.1% vs 1.4%), while Personal accounts have the speculative prefetch mechanism (0.55 threshold) and more frequent post-classifier suppression.

7. **~68% of retrieved sources never reach the user.** The system retrieves ~23 sources per run but only surfaces ~7 as visible citations. The "Additional" and "Hidden" tiers represent a substantial editorial filter that shapes what information users actually see.

8. **Ghost citations exist.** On Personal accounts, 7 runs produced citation-formatted markers with zero backing URLs — the model fabricated citation syntax from training data without any search grounding.

9. **High classifier confidence ≠ guaranteed search.** Runs with >90% `simple_search_prob` were still suppressed, indicating post-classifier filtering layers (tool routing, A/B overrides) that can override the Sonic Classifier's recommendation.
