
import os

def add_retrieval_findings():
    path = 'docs/thesis_research_outline.md'
    if not os.path.exists(path):
        print("File not found")
        return
        
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    retrieval_findings = """
*   **The "Fan-Out Strategy" (Implicit vs. Explicit Retrieval):**
    *   **Gemini's Freshness Obsession:** 93.4% of Gemini runs explicitly inject a year (2025 or 2026) into their fan-out queries, with 71.7% placing this signal in the very first query (Index 0). This drives Gemini's aggressive "Listicle Uptake."
    *   **GPT's Multi-Turn Expansion:** While GPT only uses explicit years in 5.1% of runs, it exhibits a "Multi-Turn Fan-Out" phenomenon where it issues secondary and tertiary queries (3+ queries) in response to initial results, effectively "hunting" for specific citations before finalizing the response.
    *   **Implicit Localization Bias:** Implicit localization signals (non-English fan-out queries from English prompts) were observed in 13.1% of GPT runs and 4.6% of Gemini runs, demonstrating how retrieval environment (IP/locale) can steer grounding even without user intent.
"""
    
    # Insert into Executive Summary of Key Findings
    marker = '### Executive Summary of Key Findings'
    insert_pos = content.find(marker)
    if insert_pos != -1:
        # Find the first bullet point to insert after
        bullet_pos = content.find('*', insert_pos)
        if bullet_pos != -1:
            new_content = content[:bullet_pos] + retrieval_findings + '\n' + content[bullet_pos:]
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print('Added Retrieval Strategy findings to Executive Summary.')
        else:
            print('Could not find first bullet point in summary.')
    else:
        print('Could not find Executive Summary section.')

if __name__ == "__main__":
    add_retrieval_findings()
