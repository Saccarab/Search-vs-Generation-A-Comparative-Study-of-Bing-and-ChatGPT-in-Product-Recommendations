
import pandas as pd
import ast
from urllib.parse import urlparse

def extract_domain(url):
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain.startswith("www."):
            domain = domain[4:]
        return domain.lower()
    except:
        return ""

# 1. Load ChatGPT Results
# This file has 'generated_search_query' and 'sources_cited'
chatgpt_df = pd.read_csv(r"c:\Users\User\Documents\thesis\5 prompt for lang variation test.csv")

# 2. Load Bing Results (German)
# This file has 'query' (which matches generated_search_query) and 'url'/'domain' and 'position'
bing_df = pd.read_csv(r"c:\Users\User\Downloads\bing_results_2025-12-13T12-57-16.csv")

# Clean up Bing queries to match ChatGPT format (strip quotes if any)
bing_df['query_clean'] = bing_df['query'].astype(str).str.strip('"').str.strip()
chatgpt_df['query_clean'] = chatgpt_df['generated_search_query'].astype(str).str.strip('"').str.strip()

print(f"Loaded {len(chatgpt_df)} ChatGPT rows and {len(bing_df)} Bing rows.")

results_analysis = []

# Group Bing results by query
bing_groups = bing_df.groupby('query_clean')

for index, row in chatgpt_df.iterrows():
    query = row['query_clean']
    
    # Get ChatGPT citations
    try:
        # sources_cited column looks like "['url1', 'url2']"
        citations = ast.literal_eval(row['sources_cited'])
        cited_domains = [extract_domain(c) for c in citations]
    except:
        citations = []
        cited_domains = []
        
    # Get Bing Ground Truth for this query
    if query in bing_groups.groups:
        bing_rows = bing_groups.get_group(query)
        # Create a map of Domain -> Rank
        bing_rank_map = {}
        for idx, b_row in bing_rows.iterrows():
            d = extract_domain(b_row['url'])
            if d and d not in bing_rank_map: # keep highest rank (lowest number)
                bing_rank_map[d] = b_row['position']
                
        # Compare
        for cited_domain in cited_domains:
            rank = bing_rank_map.get(cited_domain, "Not in Top 10")
            
            results_analysis.append({
                "Prompt ID": row['query_index'],
                "Run ID": row['run_number'],
                "Query": query[:50] + "...",
                "Cited Domain": cited_domain,
                "Bing DE Rank": rank,
                "Bing DE Top 3": [extract_domain(x) for x in bing_rows.sort_values('position').head(3)['url'].tolist()]
            })
            
    else:
        # print(f"Warning: Query not found in Bing results: {query}")
        pass

# Convert to DataFrame for display
analysis_df = pd.DataFrame(results_analysis)

print("\n--- ANALYSIS: ChatGPT Citations vs. German Bing Ranks ---")
# Filter to show where ChatGPT cited something found in Top 10 vs Not
print(analysis_df.to_string())

# Summary Stats
total_citations = len(analysis_df)
visible_citations = len(analysis_df[analysis_df['Bing DE Rank'] != "Not in Top 10"])
print(f"\nTotal Citations Analyzed: {total_citations}")
print(f"Citations visible in Bing DE (Top 10): {visible_citations} ({visible_citations/total_citations*100:.1f}%)")

