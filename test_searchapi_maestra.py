import requests
import json
import os

# API Key from tools/fetch_ground_truth.py
API_KEY = "AVbWYdJQfmaumj9MAFMtcDA3"

def check_searchapi(query, location, gl, hl):
    print(f"\n--- Testing SearchAPI: {location} (gl={gl}, hl={hl}) ---")
    print(f"Query: {query}")
    
    params = {
        "engine": "bing",
        "q": query,
        "api_key": API_KEY,
        "location": location,
        "mkt": gl,  # Passing explicit market if supported, or relying on gl mapping
        "num": 20
    }
    
    try:
        response = requests.get("https://www.searchapi.io/api/v1/search", params=params)
        response.raise_for_status()
        data = response.json()
        
        organic_results = data.get("organic_results", [])
        
        found_german = False
        found_english = False
        
        for result in organic_results:
            pos = result.get("position")
            link = result.get("link")
            title = result.get("title")
            
            # Check main link
            if "maestra.ai" in link:
                print(f"Found Maestra at Rank #{pos}: {link}")
                if "/de" in link:
                    found_german = True
                else:
                    found_english = True
                    
            # Check sitelinks/deep links if they exist
            sitelinks = result.get("sitelinks", [])
            if sitelinks:
                # Sitelinks structure can vary, handling simplified check
                if isinstance(sitelinks, list):
                    for sl in sitelinks:
                        sl_link = sl.get("link", "")
                        if "maestra.ai" in sl_link:
                             print(f"  -> Sitelink: {sl_link}")
                             if "/de" in sl_link:
                                 found_german = True

        if found_german:
            print("\nSUCCESS: Found German Maestra link (/de) via API!")
        elif found_english:
            print("\nRESULT: Only found English Maestra link via API.")
        else:
            print("\nWARNING: Maestra not found in Top 20.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    query = "free website program translate video and add subtitles automatically"
    
    # Test 1: Explicit German Market (de-DE)
    check_searchapi(query, "Munich, Bavaria, Germany", "de-DE", "")
    
    # Test 2: US Market (en-US)
    check_searchapi(query, "United States", "en-US", "")

