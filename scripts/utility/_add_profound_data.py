
import os

def add_profound_trigger_data():
    path = 'docs/thesis_research_outline.md'
    if not os.path.exists(path):
        print("File not found")
        return
        
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    profound_data = """
### 1.3.1 Industry Benchmark: ChatGPT Web Search Trigger Rates (Profound Analysis)
*To contextualize our study, we refer to industry-wide telemetry from **Profound** (captured as of Jan 6, 2026), which analyzes trigger rates across 667,000 real-user conversations.*

- **Commercial Intent as the Primary Driver**: Web search is triggered in **53.51% of Commercial queries**, compared to only 18.73% for Informational and 8.88% for Generative queries.
- **Overall Trigger Rate**: Across all intents, the baseline trigger rate is **17.41%**.
- **Thesis Alignment**: Our decision to filter for **high commercial intent** (product recommendations) aligns with this industry data, as this is the segment where RAG/Grounding is most active and commercially impactful.
"""
    
    # Insert into Section 1.3 (The Commercial Catalyst)
    marker = '## 1.3 The Commercial Catalyst for RAG'
    insert_pos = content.find(marker)
    if insert_pos != -1:
        # Find the next header or the end of the current section
        next_header_pos = content.find('##', insert_pos + len(marker))
        if next_header_pos == -1:
            next_header_pos = content.find('# Part 2', insert_pos)
            
        if next_header_pos != -1:
            new_content = content[:next_header_pos] + profound_data + "\n" + content[next_header_pos:]
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print("Added Profound trigger data to Section 1.3.")
        else:
            with open(path, 'a', encoding='utf-8') as f:
                f.write(profound_data)
            print("Appended Profound trigger data.")
    else:
        print("Could not find Section 1.3.")

if __name__ == "__main__":
    add_profound_trigger_data()
