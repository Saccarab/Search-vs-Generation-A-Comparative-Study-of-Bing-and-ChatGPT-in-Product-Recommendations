# Search vs. Generation: A Comparative Study of Bing and ChatGPT in Product Recommendations

This repository contains the full implementation and experimental tooling of my bachelor’s thesis:

**“Search vs. Generation: A Comparative Study of Bing and ChatGPT in Product Recommendations”**  

---

## Abstract

Generative search engines are increasingly used for product research and purchasing decisions, challenging the dominance of traditional web search engines. This work provides an empirical comparison between **Bing**, representing traditional keyword-based search, and **ChatGPT**, representing generative, retrieval-augmented search.

Using 48 structured product queries from the consumer electronics domain with varying levels of complexity, the study analyzes  
(1) differences in product recommendations,  
(2) differences in referenced information sources, and  
(3) the internal consistency of ChatGPT’s outputs across repeated queries.

To enable large-scale and reproducible analysis, this repository includes custom-built data collection tools, automated product extraction pipelines, and a comprehensive evaluation framework based on both syntactic and semantic overlap metrics. The results show that Bing and ChatGPT operate under fundamentally different recommendation and visibility logics, with implications for **Generative Engine Optimization (GEO)**.

---

## Repository Overview

This repository contains **both experimental infrastructure and analysis code** used in the thesis.

### Key Components

- **Two custom Chrome extensions** for automated data collection:
  - A ChatGPT web interface scraper
  - A Bing search result scraper
- Scripts for:
  - Query execution and response collection
  - Automated product extraction using large language models
  - Source and product overlap evaluation
- Evaluation framework and metric implementations
- Supporting configuration files and prompts

---

## Chrome Extensions for Data Collection

A central contribution of this repository is the development of **two dedicated Chrome extensions**, created specifically for this research.

### 1. ChatGPT Scraper Extension
- Collects responses from the ChatGPT web interface
- Extracts:
  - Generated recommendation text
  - Cited and additional sources
- Designed to support **multiple independent runs** per query to measure output consistency
- Operates under controlled experimental conditions (incognito mode, fresh chats)

### 2. Bing Scraper Extension
- Extracts the **top 10 organic search results** for each query
- Retrieves linked webpage content for downstream product extraction
- Removes tracking and referral parameters to ensure clean source comparison

---

## Experimental Design

- **Domain:** Consumer electronics  
- **Queries:** 48 structured queries  
- **Market types:**
  - Commodity / saturated markets
  - Niche / emerging markets
  - High-involvement / high-cost markets
- **Query complexity levels:**
  - General query
  - Price constraint
  - One feature constraint
  - Two feature constraints
- **ChatGPT runs:** 3 independent runs per query  
- **Bing baseline:** Top 10 organic search results per query

---

## Product Extraction

Due to the large volume of unstructured text, product recommendations are extracted automatically using a large language model (Gemini).

The extraction pipeline:
- Identifies explicit, user-directed product recommendations
- Normalizes outputs into structured product lists
- Avoids counting non-recommended or incidental product mentions

---

## Evaluation Metrics

The repository implements the full evaluation framework proposed in the thesis, including:

- **Syntactic overlap** (Szymkiewicz–Simpson coefficient) for source comparison
- **Semantic product overlap**, based on:
  - Sentence embeddings
  - Cosine similarity
  - Bipartite matching via the Hungarian algorithm
- Cross-system and internal consistency metrics:
  - Cross-System Mean Product Overlap (CSMPO)
  - Cross-System Mean Source Overlap (CSMSO)
  - Mean Internal Product Overlap (MIPO)
  - Mean Internal Source Overlap (MISO)
  - Cross-Query Mean Internal Product Overlap (CQMIPO)
  - Cross-Query Mean Internal Source Overlap (CQMISO)

These metrics allow systematic comparison between traditional and generative search behavior.

---

## Reproducibility and Transparency

This repository is intended to support:
- Reproducible experimental evaluation
- Transparent comparison of generative and traditional search systems
- Future research on generative search, GEO, and recommendation behavior

Due to the evolving nature of proprietary search and LLM systems, exact numerical results may vary over time, but the methodology remains transferable.

---

## License

This project is licensed under the MIT License. See the LICENSE file for details.
