import json
import os

def get_low_scores(results_path, model_name):
    if not os.path.exists(results_path): 
        print(f"File not found: {results_path}")
        return
    print(f"\n--- LOW SCORES FOR {model_name} ---")
    with open(results_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            try:
                data = json.loads(line)
                res = data.get("response", {})
                products = res.get("products", [])
                for p in products:
                    if p.get("roster_item_is_product") is True:
                        score = p.get("semantic_fidelity_score_1_5")
                        if score is not None and score <= 2:
                            print(f"Case: {data.get('case_id')}")
                            print(f"Product: {p.get('product_name')}")
                            print(f"Score: {score}")
                            print(f"Present: {p.get('present_in_listicle')}")
                            print(f"Rationale: {p.get('rationale')}")
                            print("-" * 40)
            except Exception as e: 
                continue

get_low_scores("data/enrichment/semantic_fidelity_results_gemini_v4.1_solo_25flash.jsonl", "GEMINI")
get_low_scores("data/enrichment/semantic_fidelity_results_gpt_v4.1_solo_gpt5mini.jsonl", "GPT")
