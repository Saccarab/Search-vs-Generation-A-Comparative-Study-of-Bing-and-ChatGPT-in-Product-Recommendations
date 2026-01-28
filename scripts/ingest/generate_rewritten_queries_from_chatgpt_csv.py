import pandas as pd
import re
import os

def generate_rewritten_queries(input_csv, output_csv):
    if not os.path.exists(input_csv):
        print(f"Error: {input_csv} not found.")
        return

    # Read the ChatGPT results CSV
    df = pd.read_csv(input_csv)
    
    # We need: run_id, query
    # run_id = prompt_id + "_r" + run_number
    # query = generated_search_query
    
    # Filter for rows where web_search_triggered is True and generated_search_query is not null
    # Note: Using .fillna('') to handle any potential missing values gracefully
    df['generated_search_query'] = df['generated_search_query'].fillna('')
    mask = (df['web_search_triggered'] == True) & (df['generated_search_query'].str.strip() != '') & (df['generated_search_query'].str.lower() != 'nan')
    
    filtered_df = df[mask].copy()
    
    # Construct run_id
    filtered_df['run_id'] = filtered_df['prompt_id'].astype(str) + "_r" + filtered_df['run_number'].astype(str)
    
    # Rename generated_search_query to query
    output_df = filtered_df[['run_id', 'generated_search_query']].rename(columns={'generated_search_query': 'query'})
    
    # Drop duplicates just in case
    output_df = output_df.drop_duplicates(subset=['run_id'])
    
    # Save to CSV
    output_df.to_csv(output_csv, index=False)
    print(f"Successfully wrote {len(output_df)} rewritten queries to {output_csv}")

if __name__ == "__main__":
    input_path = r"data\ingest\chatgpt_results_2026-01-17T19-19-42.csv"
    output_path = r"data\ingest\rewritten_queries.csv"
    generate_rewritten_queries(input_path, output_path)
