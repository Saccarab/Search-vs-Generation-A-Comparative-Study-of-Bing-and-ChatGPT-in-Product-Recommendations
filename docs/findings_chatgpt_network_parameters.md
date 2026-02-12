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

### 4.1 Fan-Out Distribution

The fan-out system operates in **discrete modes** — it does not generate arbitrary numbers of queries:

| Fan-Out Count | Runs | Percentage | Classification |
|---------------|------|------------|----------------|
| **0 queries** | 14 | 3.2% | No search / null classification |
| **1 query** | 0 | 0.0% | *Never observed* |
| **2 queries** | 409 | **94.0%** | Standard simple search |
| **3 queries** | 0 | 0.0% | *Never observed* |
| **4 queries** | 11 | 2.5% | Extended fan-out |
| **6 queries** | 1 | 0.2% | Maximum observed fan-out |

The absence of 1-query and 3-query runs is striking: the system uses a **fixed pair-generation strategy** for its default mode, always producing exactly 2 reformulated queries — typically one close paraphrase and one structural rephrase. There is no "single query" mode.

**By account type:**

| Account | 0 queries | 2 queries | 4+ queries |
|---------|-----------|-----------|------------|
| Enterprise (n=219) | 7 (3.2%) | 203 (92.7%) | **9 (4.1%)** |
| Personal (n=216) | 7 (3.2%) | 206 (95.4%) | **3 (1.4%)** |

Enterprise accounts produce 4+ fan-out queries at **~3x the rate** of Personal accounts (4.1% vs 1.4%), suggesting more aggressive query expansion in the enterprise pipeline.

### 4.2 The Standard 2-Query Fan-Out (94% of Runs)

The dominant pattern generates one synonym-substituted query and one structurally reorganized variant:

**Example — P001_r1** (*"Which free AI would you recommend for translating my video?"*):
```
  → "free AI tools for translating videos"        (keyword extraction)
  → "free AI video translation tools"              (noun-phrase restructuring)
```

**Example — P001_r2** (same prompt, different run):
```
  → "free AI tools to translate video"             (verb form change)
  → "free video translation AI service"            (reordered + broadened)
```

The classifier probabilities for these standard runs show consistently low `complex_search_prob` (median: 0.003), confirming the system treats 2-query fan-out as a "simple search" operation.

### 4.3 Extended Fan-Out (4–6 Queries): Not "Complex Search," But Prompt-Driven

The 12 runs with 4+ fan-out queries are notable because they were **not classified as complex search** by the Sonic Classifier. None crossed the 0.4 `complex_search_threshold`. Instead, extended fan-out appears to be driven by **prompt structure** — specifically, multi-constraint queries that require targeted follow-up searches:

| Run | Fan-Out | complex_search_prob | Prompt |
|-----|---------|---------------------|--------|
| P035 (all 6 runs) | **4** | 0.069 | *"Can you list translation services with live interpreters and their 2-day pricing?"* |
| P053 (r1–r3, enterprise) | **4** | **0.259** | *"Can you recommend the best free AI text-to-speech software with celebrity voices for IoT applications?"* |
| P050_r3 (enterprise) | **4** | 0.003 | *"Can you recommend a free app for live time translation during a call with French speakers?"* |
| P063_r1 (enterprise) | **4** | 0.037 | *"What is the best machine translation tool for live translation that saves context?"* |
| **P073_r3 (enterprise)** | **6** | 0.012 | *"Can you recommend the best video translator for YouTube?"* |

**The correlation between `complex_search_prob` and fan-out count:**

| Fan-Out | Avg `complex_search_prob` | Min | Max | N |
|---------|--------------------------|-----|-----|---|
| 2 queries | 0.025 | 0.000246 | 0.3056 | 409 |
| 4+ queries | **0.104** | 0.003 | 0.259 | 12 |

The average `complex_search_prob` is **~4x higher** for extended fan-out runs, but the relationship is not deterministic. P073_r3 (the maximum 6-query fan-out) had a very low `complex_search_prob` of just 0.012, while some 2-query runs reached up to 0.306 without triggering additional fan-outs.

**What drives extended fan-out instead:** The 4+ query runs share a common trait — their prompts ask for **specific named entities, pricing, or feature comparisons** that require targeted lookups beyond broad keyword search. The hidden queries in these cases progressively narrow, often explicitly naming products or services:

- P035's 4 queries escalate from *"translation services with live interpreters"* → *"LanguageLine, Boostlingo, Interprefy pricing"*
- P053's 4 queries escalate from *"free AI TTS celebrity voices"* → *"FakeYou, Uberduck, ElevenLabs, 15.dev review"*
- P073's 6 queries escalate from *"best video translator YouTube"* → *"VEED, Kapwing, Happy Scribe video translation"*

This suggests that **fan-out count is determined by the generation model's query planner** (which identifies how many distinct sub-questions the prompt implies), not by the Sonic Classifier's three-way probability split. The classifier decides *whether* to search; a separate downstream component decides *how many queries* to issue.

### 4.4 Detailed Network Parameters for Extended Fan-Out Runs

Below is the complete per-run breakdown of every 4+ fan-out instance, showing the full sonic classifier output alongside the actual hidden queries generated. A critical observation: **the classifier outputs are deterministic** for the same prompt+account combination (identical probabilities across r1/r2/r3), but **the query planner is non-deterministic** — the same prompt can produce 2 queries on one run and 6 on another.

---

#### P035 — *"Can you list translation services with live interpreters and their 2-day pricing?"*
**Fan-out: 4 queries on all 6 runs (enterprise + personal)**

| Parameter | Enterprise | Personal |
|-----------|-----------|----------|
| `simple_search_prob` | 0.9260 (92.60%) | 0.9262 (92.62%) |
| `complex_search_prob` | **0.0693** (6.93%) | **0.0688** (6.88%) |
| `no_search_prob` | 0.0047 (0.47%) | 0.0049 (0.49%) |
| `latency_ms` | 9.74 | 2.60 |
| `web_search_triggered` | true | true |
| `generated_search_query` | N/A | *"translation services with live interpreters 2-day pricing..."* |

**Enterprise hidden queries:**
```
1. "translation services with live interpreters pricing 2 day cost live interpreter service pricing"
2. "live interpreter translation services 2 day pricing interpreter on demand translation live interpreters cost"
3. "Jeenie live interpreter pricing per minute or per session Jeenie translation live interpreters cost"
4. "does Jeenie or similar service list pricing or 2-day event pricing live interpreters Jeenie or Boostlingo pricing"
```

**Personal hidden queries:**
```
1. "translation services with live interpreters 2-day pricing live interpreter translation services cost pricing"
2. "translation services offering live interpreters pricing for short sessions or 2 day conferences interpreter services pricing translation live interpreters"
3. "LanguageLine Solutions interpreting pricing and plans or packages live interpreters LanguageLine Solutions pricing"
4. "Boostlingo live interpreter services pricing and plans for interpreting services"
```

**Analysis:** Queries 1–2 are broad keyword variants. Queries 3–4 pivot to **specific named services** (Jeenie, Boostlingo, LanguageLine) — the query planner identifies that "pricing" requires targeted per-vendor lookups. Interestingly, enterprise and personal name *different* services, suggesting the query planner draws on different parametric knowledge per deployment.

---

#### P053 — *"Can you recommend the best free AI text-to-speech software with celebrity voices for IoT applications?"*
**Fan-out: 4 queries on enterprise r1–r3 only (personal had 2)**

| Parameter | Enterprise | Personal (2 queries) |
|-----------|-----------|----------|
| `simple_search_prob` | **0.7358** (73.58%) | — |
| `complex_search_prob` | **0.2591** (25.91%) | — |
| `no_search_prob` | 0.0051 (0.51%) | — |
| `latency_ms` | 4.59 | — |

**Enterprise hidden queries:**
```
1. "free AI text to speech software with celebrity voices for IoT applications"
2. "best free TTS celebrity voices API IoT text to speech celebrity voices freeware"
3. "Uberduck FakeYou free celebrity TTS API for developers IoT"
4. "are free celebrity TTS voices allowed in applications and their limitations"
```

**Analysis:** This run has the **highest `complex_search_prob` of any 4+ fan-out run** (25.91%). Query 3 names specific services (Uberduck, FakeYou), and query 4 pivots to a **legal/limitation angle** — the planner recognized the prompt implies both "what tools exist" and "can I actually use them." Only enterprise triggered 4 queries; personal used the standard 2-query path for the same prompt.

---

#### P050_r3 — *"Can you recommend a free app for live time translation during a call with French speakers?"*
**Fan-out: 4 queries on enterprise r3 only (r1, r2 had 2)**

| Parameter | Enterprise |
|-----------|-----------|
| `simple_search_prob` | **0.9958** (99.58%) |
| `complex_search_prob` | **0.0027** (0.27%) |
| `no_search_prob` | 0.0015 (0.15%) |
| `latency_ms` | 10.06 |

**Hidden queries:**
```
1. "free app live translation during a call French speakers real time translation app"
2. "applications that translate live voice calls French free"
3. "Google Translate app live conversation translation free French English conversation mode phone"
4. "Microsoft Translator app real time voice conversation translation support French"
```

**Analysis:** Despite an extremely low `complex_search_prob` (0.27%), the planner still issued 4 queries — naming Google Translate and Microsoft Translator explicitly. This confirms the **fan-out decision is independent of the sonic classifier**. The same prompt on r1 and r2 produced only 2 queries with identical classifier values, proving the query planner has its own non-deterministic logic.

---

#### P063_r1 — *"What is the best machine translation tool for live translation that saves context?"*
**Fan-out: 4 queries on enterprise r1 only**

| Parameter | Enterprise |
|-----------|-----------|
| `simple_search_prob` | 0.9548 (95.48%) |
| `complex_search_prob` | **0.0374** (3.74%) |
| `no_search_prob` | 0.0078 (0.78%) |
| `latency_ms` | 7.04 |

**Hidden queries:**
```
1. "best machine translation tool for live translation that maintains context"
2. "tools supporting live translation with contextual memory features"
3. "which live translation tools maintain conversation context or memory in translation? contextual memory in live translation"
4. "machine translation live translation maintaining context features translation memory or adaptive context in real-time tools"
```

**Analysis:** Unlike the other extended fan-out runs, these queries do **not** name specific products. Instead, they progressively refine the concept — from "saves context" → "contextual memory" → "translation memory" → "adaptive context." The planner recognized the prompt uses an ambiguous term ("saves context") and expanded it into multiple technical phrasings.

---

#### P073_r3 — *"Can you recommend the best video translator for YouTube?"*
**Fan-out: 6 queries (maximum observed) — enterprise r3 only**

| Parameter | Enterprise (all runs identical) |
|-----------|-----------|
| `simple_search_prob` | 0.9774 (97.74%) |
| `complex_search_prob` | **0.0124** (1.24%) |
| `no_search_prob` | 0.0102 (1.02%) |
| `latency_ms` | 4.33 (r3) / 9.08 (r1) / 14.16 (r2) |

**Comparison across runs of the same prompt:**

| Run | Fan-Out | Sonic Probs (identical) | Hidden Queries |
|-----|---------|------------------------|----------------|
| P073_r1 | **2** | simple=97.74%, complex=1.24% | `"best video translator for YouTube subtitles translation tools"`, `"YouTube video translator tools comparison YouTube auto translate services"` |
| P073_r2 | **2** | simple=97.74%, complex=1.24% | `"video translator for YouTube best tools translate YouTube videos"`, `"best YouTube video translator software or services video subtitles translation"` |
| P073_r3 | **6** | simple=97.74%, complex=1.24% | See below |

**P073_r3 hidden queries (6):**
```
1. "best video translator for YouTube translate videos subtitles tools"
2. "YouTube video translator tools comparison automatic translation subtitles for YouTube"
3. "tools to translate YouTube videos subtitles or audio translate YouTube video translator"
4. "best YouTube video translation tools automatic subtitle translation and dubbing for YouTube"
5. "best tools to translate YouTube videos subtitles automatic translate and dubbing YouTube translation tools"
6. "how to translate YouTube video subtitles or audio - tools like VEED, Kapwing, Happy Scribe"
```

**Analysis:** This is the strongest evidence that **fan-out is decoupled from the Sonic Classifier.** The classifier produced byte-identical outputs for all 3 runs (`simple_search_prob` = 0.9773789267643763 to 16 decimal places), yet r1/r2 got 2 queries and r3 got 6. The 6-query version escalates from generic reformulations (queries 1–5 are largely synonymous) to a final query that names specific tools (VEED, Kapwing, Happy Scribe). The query planner's decision to expand appears stochastic — possibly influenced by sampling temperature or server-side experimentation at the generation layer.

---

### 4.5 Summary: Fan-Out ≠ Complex Search

The extended fan-out runs reveal three key architectural insights:

1. **The Sonic Classifier and the query planner are separate systems.** The classifier decides search vs. no-search (and theoretically simple vs. complex). The query planner decides *how many* and *what* queries to issue. These operate independently — P073 proves this definitively with identical classifier outputs producing 2 and 6 fan-outs.

2. **Extended fan-out is non-deterministic.** The same prompt+account can produce different fan-out counts across runs. Only P035 was consistent (4 queries on all 6 runs). P050, P063, and P073 had extended fan-out on only 1 of their 3 runs each.

3. **The query planner uses two expansion strategies:**
   - **Named-entity targeting** (P035, P050, P053): queries 3–4 name specific products/services for targeted lookups
   - **Concept disambiguation** (P063): queries progressively rephrase an ambiguous concept into multiple technical terms
   - **Exhaustive variation** (P073_r3): queries 1–5 are near-synonymous broad searches, with a final named-entity query — suggesting the planner over-generated rather than strategically expanding

### 4.6 Zero-Query Runs

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
| `hidden_queries` | array | All internal fan-out query variants generated for retrieval |
| `passthrough_tool_calls` | bool/null | Whether non-search tools can preempt the search decision |
| `passthrough_tool_names` | array | List of tools that can intercept instead of search (Enterprise only) |

### 6.5 Citation Mapping Fields

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

### 6.6 Source Metadata (per source in `sources[]`)

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

4. **94% of searches use exactly 2 fan-out queries** — a fixed pair-generation strategy producing one synonym variant and one structural rephrase. The system never generates 1 or 3 queries, operating in discrete modes (0, 2, 4, or 6).

5. **Extended fan-out (4–6 queries) is prompt-driven, not classifier-driven.** The 12 runs with 4+ queries had ~4x higher `complex_search_prob` on average (0.104 vs 0.025), but the correlation is loose. Fan-out count is driven by the **query planner** detecting multi-constraint prompts (pricing, named entities, feature comparisons), not by the Sonic Classifier's probability split. Enterprise accounts trigger extended fan-out at 3x the rate of Personal.

6. **Enterprise accounts search more consistently** (91.1% vs 86.9%), potentially due to the absence of the speculative prefetch mechanism and a more deterministic tool-routing pipeline.

7. **~68% of retrieved sources never reach the user.** The system retrieves ~23 sources per run but only surfaces ~7 as visible citations. The "Additional" and "Hidden" tiers represent a substantial editorial filter that shapes what information users actually see.

8. **Ghost citations exist.** On Personal accounts, 7 runs produced citation-formatted markers with zero backing URLs — the model fabricated citation syntax from training data without any search grounding.

9. **High classifier confidence ≠ guaranteed search.** Runs with >90% `simple_search_prob` were still suppressed, indicating post-classifier filtering layers (tool routing, A/B overrides) that can override the Sonic Classifier's recommendation.
