# Research Note: Content Length Correlation in LLM Grounding DNA

## Objective
Analyze how the length of the input content (raw text from fetched URLs) affects the accuracy and behavior of the labeling LLM (Gemini 2.5 Flash).

## Initial Findings (G2 Hallucination Bug)
We observed a direct correlation between **Input Length** and the **Hallucination Rate** (specifically the "G2 Bug" where the model copies the G2 directory example from the prompt).

| Content Length | Hallucination Rate (G2 Bug) |
|----------------|-----------------------------|
| 0 - 5k chars   | 9.5%                        |
| 5k - 10k chars | 11.8%                       |
| 10k - 20k chars| 12.4%                       |
| 20k - 40k chars| 14.0%                       |
| 40k+ chars     | 17.3%                       |

## Hypothesis
1. **Attention Dilution**: As content length increases, the model's attention to the specific URL and context diminishes, leading it to default to prompt examples.
2. **Directory Bias**: Longer pages (usually listicles) are more likely to be misclassified as `marketplace_directory` because the model spends more tokens parsing structured lists, "forgetting" the source identity (e.g., a blog).

## Data Integration
The `raw_content_length` has been injected into `datapass/page_labels_gemini_v2.5.jsonl` for all 2,782+ records. This allows for:
- Correlation analysis between length and `is_vendor_owned`.
- Filtering the "Invisible Explorer" by content size to see if "Shadow Grounding" links are typically shorter/longer than SERP links.

## Action Items
- [ ] Re-run enrichment with a strictly limited 8k-10k character slice to see if the hallucination rate drops.
- [ ] Compare these rates with the ChatGPT enrichment pass (which used shorter, cleaner inputs).
