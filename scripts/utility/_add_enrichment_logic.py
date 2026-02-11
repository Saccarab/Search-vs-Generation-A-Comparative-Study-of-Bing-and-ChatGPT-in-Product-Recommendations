
import os

def add_enrichment_logic():
    path = 'docs/thesis_research_outline.md'
    if not os.path.exists(path):
        print("File not found")
        return
        
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    enrichment_logic = """
### 1.11.3 Enrichment Logic & Static Overrides
*To ensure efficiency and accuracy, the labeling pipeline uses a hybrid approach of LLM-labeling and static rules for high-volume, well-known domains.*

- **LLM-Labeling (GPT-4o-mini)**: Used for general web pages, blogs, and niche product sites to determine structural features (`has_tables`, `has_pros_cons`, etc.).
- **Static Domain Overrides (Skipped Enrichment)**: Known platforms with consistent structural patterns were assigned "pre-made" labels to save quota and ensure consistency:
    - **`reddit.com`**: Automatically labeled as `type=forum_ugc`, `content_format=discussion_thread`, `tone=opinionated`.
    - **`en.wikipedia.org`**: Automatically labeled as `type=reference`, `content_format=encyclopedic`, `tone=neutral_informational`.
    - **`arxiv.org`**: Labeled as `type=reference`, `content_format=academic_paper`.
    - **App Stores (`apps.apple.com`, `play.google.com`)**: Labeled as `type=app_store_listing`, `primary_intent=transactional`.
- **The "Invisible" Domain Strategy**: Many of the top "invisible" domains (like `reddit.com` and `wikipedia.org`) were handled via these static overrides because their structure is fixed and does not require per-page LLM analysis.
"""
    
    # Target the renumbered Content DNA section
    target_header = '## 1.11 Content DNA Enrichment'
    insert_pos = content.find(target_header)
    
    if insert_pos != -1:
        # Find the end of the Content DNA section (start of Part 2 or next ## header)
        next_sec = content.find('##', insert_pos + len(target_header))
        if next_sec == -1:
            next_sec = content.find('# Part 2', insert_pos)
            
        if next_sec != -1:
            new_content = content[:next_sec] + enrichment_logic + '\n' + content[next_sec:]
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print('Added Enrichment Logic & Overrides section.')
        else:
            # If it's the very last section
            with open(path, 'a', encoding='utf-8') as f:
                f.write(enrichment_logic)
            print('Appended Enrichment Logic & Overrides section.')
    else:
        print(f'Could not find target header: {target_header}')

if __name__ == "__main__":
    add_enrichment_logic()
