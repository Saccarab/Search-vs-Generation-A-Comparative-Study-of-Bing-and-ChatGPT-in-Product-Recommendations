
import os

def move_fanout_to_findings():
    path = 'docs/thesis_research_outline.md'
    if not os.path.exists(path):
        print("File not found")
        return
        
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Extract Fan-out Query Findings from Executive Summary
    start_marker = '*   **The "Fan-Out Strategy" (Implicit vs. Explicit Retrieval):**'
    start_idx = content.find(start_marker)
    if start_idx == -1:
        print("Could not find Fan-out summary")
        return
        
    # Find the end of this bullet point block
    end_idx = content.find('*   **The "Provider Pivot"', start_idx)
    if end_idx == -1:
        end_idx = content.find('### Operational definition', start_idx)

    fanout_summary = content[start_idx:end_idx].strip()
    
    # 2. Create the formal section
    fanout_section = f"""
## 2.0 Retrieval Strategy & Fan-Out Analysis
*Before analyzing citation overlap, we examine the retrieval phase: how the models reshape the user prompt into multiple search queries.*

{fanout_summary}
"""
    
    # 3. Find where to insert it (Before 2.1 Citation Overlap)
    target_marker = '## 2.1 Citation Overlap Analysis'
    insert_pos = content.find(target_marker)
    
    if insert_pos != -1:
        # Insert it before 2.1
        new_content = content[:insert_pos] + fanout_section + '\n' + content[insert_pos:]
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("Added Fan-out Analysis section before Citation Overlap.")
    else:
        print("Could not find Citation Overlap section.")

if __name__ == "__main__":
    move_fanout_to_findings()
