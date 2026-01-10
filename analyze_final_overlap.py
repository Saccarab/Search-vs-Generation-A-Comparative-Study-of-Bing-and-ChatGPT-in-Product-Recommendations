import pandas as pd
import ast
from urllib.parse import urlparse

# --- Configuration ---
# US Baseline Analysis
CHATGPT_FILE = r"c:\Users\User\Downloads\chatgpt_results_2025-12-25T01-22-48.csv"
# Latest Bing Results (US Proxy)
BING_FILE = r"c:\Users\User\Downloads\bing_results_2025-12-25T04-34-27.csv"
OUTPUT_FILE = "final_overlap_analysis_us.csv"

def normalize_url(url):
    """
    Normalizes a URL for comparison:
    - Removes http/https
    - Removes www.
    - Removes trailing slashes
    - Lowercases
    """
    if not isinstance(url, str):
        return ""
    
    try:
        # Basic cleanup
        url = url.strip().lower()
        
        # Remove scheme
        if "://" in url:
            url = url.split("://")[1]
            
        # Remove www.
        if url.startswith("www."):
            url = url[4:]
            
        # Remove trailing slash
        if url.endswith("/"):
            url = url[:-1]
            
        return url
    except:
        return ""

def get_domain(url):
    """Extracts the main domain from a URL."""
    try:
        if not url.startswith('http'):
            url = 'http://' + url
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain.lower()
    except:
        return ""

def main():
    print("Loading datasets...")
    
    # Load ChatGPT Results
    try:
        gpt_df = pd.read_csv(CHATGPT_FILE)
        gpt_df.columns = [c.strip() for c in gpt_df.columns]
        # Clean newlines from relevant columns if they exist
        for col in ['generated_search_query', 'sources_cited']:
            if col in gpt_df.columns:
                 gpt_df[col] = gpt_df[col].astype(str).str.replace(r'[\r\n]+', ' ', regex=True)

    except Exception as e:
        print(f"Error loading ChatGPT file: {e}")
        return

    # Load Bing Results
    try:
        bing_df = pd.read_csv(BING_FILE)
        bing_df.columns = [c.strip() for c in bing_df.columns]
    except Exception as e:
        print(f"Error loading Bing file: {e}")
        return

    results = []

    print(f"Analyzing {len(gpt_df)} ChatGPT responses against {len(bing_df)} Bing results...")

    # Iterate through each ChatGPT run
    for idx, gpt_row in gpt_df.iterrows():
        query = gpt_row['generated_search_query']
        # Handle N/A or empty queries
        if pd.isna(query) or query == 'nan' or query == 'N/A':
            continue
            
        citations = []
        try:
            raw_cited = gpt_row.get('sources_cited', "[]")
            citations = ast.literal_eval(raw_cited) if isinstance(raw_cited, str) else []
        except:
            # Try basic fallback if eval fails
            print(f"Error parsing citations for query: {query}")
            continue

        if not citations:
            continue

        # Find matching Bing results for this query
        # We need to be careful with exact string matching on query if there are slight variations
        # But here we assume they match from the rewritten list
        bing_matches = bing_df[bing_df['query'].str.strip().str.lower() == query.strip().lower()]
        
        if bing_matches.empty:
            # Fallback: Try partial match or just skip
            # print(f"Warning: No Bing results found for query: '{query}'")
            continue

        bing_urls = set(bing_matches['url'].apply(normalize_url))
        bing_domains = set(bing_matches['domain'].astype(str).str.replace('www.', ''))
        
        exact_matches = 0
        domain_matches = 0
        total_citations = len(citations)
        ranks = []

        for citation in citations:
            norm_cit = normalize_url(citation)
            cit_domain = get_domain(citation)
            
            # Check Exact Match
            if norm_cit in bing_urls:
                exact_matches += 1
                # Find rank
                match_row = bing_matches[bing_matches['url'].apply(normalize_url) == norm_cit]
                if not match_row.empty:
                    # Take the minimum rank found (best rank)
                    rank = match_row['position'].min()
                    ranks.append(rank)
            
            # Check Domain Match (if not exact)
            elif cit_domain in bing_domains:
                domain_matches += 1
                match_row = bing_matches[bing_matches['domain'].astype(str).str.replace('www.', '') == cit_domain]
                if not match_row.empty:
                    rank = match_row['position'].min()
                    ranks.append(rank)

        # Metrics
        avg_rank = sum(ranks) / len(ranks) if ranks else 0
        
        # Rank Buckets
        top1_matches = sum(1 for r in ranks if r <= 1)
        top3_matches = sum(1 for r in ranks if r <= 3)
        top5_matches = sum(1 for r in ranks if r <= 5)
        top10_matches = sum(1 for r in ranks if r <= 10)
        
        results.append({
            'query': query,
            'total_citations': total_citations,
            'exact_matches': exact_matches,
            'domain_matches': domain_matches,
            'total_domain_matches': exact_matches + domain_matches,
            'exact_match_pct': (exact_matches / total_citations) * 100 if total_citations else 0,
            'domain_match_pct': ((exact_matches + domain_matches) / total_citations) * 100 if total_citations else 0,
            'avg_bing_rank': avg_rank,
            'top1_match_pct': (top1_matches / total_citations) * 100 if total_citations else 0,
            'top3_match_pct': (top3_matches / total_citations) * 100 if total_citations else 0,
            'top5_match_pct': (top5_matches / total_citations) * 100 if total_citations else 0,
            'top10_match_pct': (top10_matches / total_citations) * 100 if total_citations else 0
        })

    results_df = pd.DataFrame(results)
    
    if not results_df.empty:
        print("\n--- ANALYSIS SUMMARY (US BASELINE) ---")
        print(f"Total Queries Analyzed: {len(results_df)}")
        print(f"Avg Exact URL Match: {results_df['exact_match_pct'].mean():.2f}%")
        print(f"Avg Domain Match (Top 30): {results_df['domain_match_pct'].mean():.2f}%")
        print("-" * 30)
        print(f"Top 1 Match: {results_df['top1_match_pct'].mean():.2f}%")
        print(f"Top 3 Match: {results_df['top3_match_pct'].mean():.2f}%")
        print(f"Top 5 Match: {results_df['top5_match_pct'].mean():.2f}%")
        print(f"Top 10 Match: {results_df['top10_match_pct'].mean():.2f}%")
        print("-" * 30)
        print(f"Avg Rank of Citations: {results_df['avg_bing_rank'].mean():.1f}")
        
        results_df.to_csv(OUTPUT_FILE, index=False)
        print(f"\nDetailed results saved to {OUTPUT_FILE}")
    else:
        print("No results to save.")

if __name__ == "__main__":
    main()
