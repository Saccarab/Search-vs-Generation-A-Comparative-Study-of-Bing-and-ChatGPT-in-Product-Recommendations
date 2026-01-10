import requests
import csv
import json
import time
import os

# Configuration
API_KEY = "AVbWYdJQfmaumj9MAFMtcDA3"
INPUT_CSV = "queries.csv"
OUTPUT_CSV = "ground_truth_comparison.csv"

def get_bing_results(query, location, gl):
    """
    Fetches organic results from Bing via SearchAPI.
    """
    params = {
        "engine": "bing",
        "q": query,
        "api_key": API_KEY,
        "location": location,
        "gl": gl,
        "num": 10  # Top 10 results
    }
    
    try:
        response = requests.get("https://www.searchapi.io/api/v1/search", params=params)
        response.raise_for_status()
        data = response.json()
        
        organic_results = data.get("organic_results", [])
        
        # Extract just the titles and domains/URLs for easier comparison
        simplified_results = []
        for result in organic_results:
            simplified_results.append({
                "position": result.get("position"),
                "title": result.get("title"),
                "link": result.get("link"),
                "domain": result.get("domain", "")
            })
            
        return simplified_results
        
    except Exception as e:
        print(f"Error fetching {location} results for '{query}': {e}")
        return []

def main():
    # Read queries
    queries = []
    with open(INPUT_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("query"):
                queries.append(row["query"].strip('"'))

    # Prepare output file
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            "Query", 
            "US_Rank_1_Domain", "US_Rank_1_Title", "US_Rank_1_Link",
            "US_Rank_2_Domain", "US_Rank_2_Title", "US_Rank_2_Link",
            "US_Rank_3_Domain", "US_Rank_3_Title", "US_Rank_3_Link",
            "DE_Rank_1_Domain", "DE_Rank_1_Title", "DE_Rank_1_Link",
            "DE_Rank_2_Domain", "DE_Rank_2_Title", "DE_Rank_2_Link",
            "DE_Rank_3_Domain", "DE_Rank_3_Title", "DE_Rank_3_Link"
        ])

        print(f"Starting Ground Truth Collection for {len(queries)} queries...")

        for i, query in enumerate(queries):
            print(f"[{i+1}/{len(queries)}] Processing: {query[:50]}...")
            
            # Fetch US Results
            us_results = get_bing_results(query, "United States", "us")
            
            # Fetch German Results
            de_results = get_bing_results(query, "Germany", "de")
            
            # Helper to safely get result at index
            def get_res(results, idx):
                if idx < len(results):
                    return results[idx]["domain"], results[idx]["title"], results[idx]["link"]
                return "", "", ""

            # Extract Top 3 for both
            us1_dom, us1_tit, us1_lnk = get_res(us_results, 0)
            us2_dom, us2_tit, us2_lnk = get_res(us_results, 1)
            us3_dom, us3_tit, us3_lnk = get_res(us_results, 2)
            
            de1_dom, de1_tit, de1_lnk = get_res(de_results, 0)
            de2_dom, de2_tit, de2_lnk = get_res(de_results, 1)
            de3_dom, de3_tit, de3_lnk = get_res(de_results, 2)
            
            writer.writerow([
                query,
                us1_dom, us1_tit, us1_lnk,
                us2_dom, us2_tit, us2_lnk,
                us3_dom, us3_tit, us3_lnk,
                de1_dom, de1_tit, de1_lnk,
                de2_dom, de2_tit, de2_lnk,
                de3_dom, de3_tit, de3_lnk
            ])
            
            # Be nice to the API
            time.sleep(1)

    print(f"\nDone! Comparison data saved to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()



