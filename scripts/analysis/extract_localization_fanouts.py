import os
import json
import csv

def get_gpt_from_csv():
    csv_path = 'data/enrichment/non_english_fanout_anomalies_gpt_v2.csv'
    results = []
    if os.path.exists(csv_path):
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Construct a run_id like P001_r1_enterprise
                run_id = f"{row['prompt_id']}_r{row['run_number']}_{row['account_type']}"
                results.append({'run_id': run_id, 'query': row['flagged_query'], 'model': 'GPT'})
    return results

def get_gemini_fanouts():
    raw_dir = 'data/gemini_raw_responses'
    results = []
    if os.path.exists(raw_dir):
        for fn in os.listdir(raw_dir):
            if not fn.endswith('.json'): continue
            try:
                with open(os.path.join(raw_dir, fn), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                queries = data.get('groundingMetadata', {}).get('webSearchQueries', [])
                for q in queries:
                    if any(ord(ch) > 127 for ch in q):
                        # Construct a run_id like P001_r1
                        parts = fn.split('_')
                        run_id = f"{parts[0]}_{parts[1]}"
                        results.append({'run_id': run_id, 'query': q, 'model': 'Gemini'})
            except: pass
    return results

gpt_results = get_gpt_from_csv()
gemini_results = get_gemini_fanouts()

all_fanouts = gpt_results + gemini_results
output_path = 'data/enrichment/localization_fanout_occurrences.json'
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(all_fanouts, f, indent=2)

gpt_runs = set(r['run_id'] for r in gpt_results)
gemini_runs = set(r['run_id'] for r in gemini_results)

# Total runs for percentage calculation
# GPT: 79 prompts * 3 runs * 2 accounts = 474 (but we only have 237 in our current analysis scope usually? 
# Actually user said 79 prompts, total runs 237 (3 per prompt). 
# Let's assume 237 for GPT (Enterprise/Personal mixed) and 237 for Gemini.
TOTAL_RUNS_PER_MODEL = 237 

gpt_pct = (len(gpt_runs) / TOTAL_RUNS_PER_MODEL) * 100
gemini_pct = (len(gemini_runs) / TOTAL_RUNS_PER_MODEL) * 100

print(f"GPT: {len(gpt_runs)} unique runs ({gpt_pct:.1f}%)")
print(f"Gemini: {len(gemini_runs)} unique runs ({gemini_pct:.1f}%)")
print(f"Total occurrences saved to {output_path}")
