import pandas as pd
import ast
from urllib.parse import urlparse
from collections import Counter

CHATGPT_FILE = r"c:\Users\User\Downloads\chatgpt_results_2025-12-25T01-22-48.csv"
BING_FILE = r"c:\Users\User\Downloads\bing_results_2025-12-25T04-34-27.csv"

def get_domain(url):
    try:
        if not isinstance(url, str): return ""
        if not url.startswith('http'): url = 'http://' + url
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith('www.'): domain = domain[4:]
        return domain
    except:
        return ""

def main():
    print("Loading datasets...")
    gpt_df = pd.read_csv(CHATGPT_FILE)
    bing_df = pd.read_csv(BING_FILE)
    
    # 1. Analyze Bing Top 3 Domains
    # Filter for positions 1, 2, 3
    bing_top3 = bing_df[bing_df['position'].astype(float) <= 3]
    bing_domains = [get_domain(u) for u in bing_top3['url']]
    bing_counts = Counter(bing_domains)
    
    # 2. Analyze ChatGPT Cited Domains
    gpt_domains = []
    for citations in gpt_df['sources_cited']:
        try:
            if pd.isna(citations): continue
            urls = ast.literal_eval(citations)
            gpt_domains.extend([get_domain(u) for u in urls])
        except:
            pass
    gpt_counts = Counter(gpt_domains)
    
    print("\n--- TOP DOMAINS: BING RANK 1-3 (The 'Organic' Winners) ---")
    for domain, count in bing_counts.most_common(10):
        print(f"{domain}: {count}")

    print("\n--- TOP DOMAINS: CHATGPT CITATIONS (The 'Selected' Winners) ---")
    for domain, count in gpt_counts.most_common(10):
        print(f"{domain}: {count}")

if __name__ == "__main__":
    main()

