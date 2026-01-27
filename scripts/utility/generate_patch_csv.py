import pandas as pd
import csv

def generate_patch_csv_robust(original_csv, output_csv):
    patch_config = {
        "P021": 2, "P062": 3, "P002": 1, "P026": 1, "P031": 1,
        "P034": 1, "P035": 1, "P046": 1, "P071": 1, "P076": 1,
        "P009": 1, "P011": 1, "P029": 1, "P048": 1, "P060": 1
    }
    
    # Read manually to avoid pandas tokenizer issues with commas
    query_map = {}
    with open(original_csv, 'r', encoding='utf-8') as f:
        # Some rows have extra commas without quotes, so we split only on the first comma
        for line in f:
            line = line.strip()
            if not line or line.startswith('prompt_id'): continue
            parts = line.split(',', 1)
            if len(parts) == 2:
                pid, q = parts
                query_map[pid.strip()] = q.strip()

    patch_rows = []
    for pid, count in patch_config.items():
        if pid in query_map:
            for _ in range(count):
                patch_rows.append({"prompt_id": pid, "query": query_map[pid]})
        else:
            print(f"Warning: Prompt {pid} not found in query map.")
            
    df_patch = pd.DataFrame(patch_rows)
    df_patch.to_csv(output_csv, index=False)
    print(f"Successfully generated {len(df_patch)} rows in {output_csv}")

if __name__ == "__main__":
    generate_patch_csv_robust("data/ingest/chatgpt_prompts_input.csv", "data/ingest/chatgpt_patch_input.csv")
