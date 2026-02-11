
import os

def add_environment_section():
    path = 'docs/thesis_research_outline.md'
    if not os.path.exists(path):
        print("File not found")
        return
        
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    env_section = """
## 1.6 Retrieval Environments & Deployment Contexts
*Defining the specific interfaces and constraints of the models under study.*

### 1.6.1 ChatGPT: UI-Based Network Instrumentation (Personal vs. Enterprise)
- **Deployment Context**: We study ChatGPT as a consumer-facing product accessed via the standard web interface (`chatgpt.com`).
- **Instrumentation Method**: Because OpenAI does not expose grounding metadata (fan-out queries, retrieved snippets) via its public API, we used **Network Payload Inspection** (Chrome DevTools protocol) to capture the raw event stream of the production UI.
- **Personal vs. Enterprise**: 
    - **Personal**: Standard consumer account; exhibits more 'elastic' retrieval and higher overlap with Google.
    - **Enterprise**: Corporate-tier account; restricted to Azure/Bing-centric grounding, providing a more 'controlled' corporate retrieval baseline.

### 1.6.2 Gemini: API-Based Grounding (Vertex AI)
- **Deployment Context**: Unlike ChatGPT, Gemini was studied via the **Vertex AI / Google AI Studio API** (Gemini 1.5 Pro/Flash).
- **Instrumentation Method**: We utilized the API specifically to access the **`groundingMetadata`** object, which is not fully transparent in the consumer UI.
- **Reliability of Data**: The API provides a 'cleaner' laboratory environment, exposing the exact `groundingChunks` (retrieved snippets) and `groundingSupports` (segment-to-chunk mapping) required for high-fidelity grounding analysis.
"""
    
    # Insert before Anatomy of ChatGPT
    # We need to find the exact current header to replace/insert before
    target_header = '## 1.6 Anatomy of ChatGPT'
    insert_pos = content.find(target_header)
    
    if insert_pos != -1:
        # Build new content with renumbering
        new_content = content[:insert_pos] + env_section + '\n'
        remainder = content[insert_pos:]
        
        # Renumber subsequent sections in the remainder
        remainder = remainder.replace('## 1.6 Anatomy of ChatGPT', '## 1.7 Anatomy of ChatGPT')
        remainder = remainder.replace('## 1.7 Anatomy of Gemini', '## 1.8 Anatomy of Gemini')
        remainder = remainder.replace('## 1.8 Localization', '## 1.9 Localization')
        remainder = remainder.replace('## 1.9 Citation Mapping', '## 1.10 Citation Mapping')
        remainder = remainder.replace('## 1.10 Content DNA', '## 1.11 Content DNA')
        
        new_content += remainder
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print('Added Environment section and renumbered subsequent sections.')
    else:
        print(f'Could not find target header: {target_header}')

if __name__ == "__main__":
    add_environment_section()
