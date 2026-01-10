import pandas as pd
import os
from openpyxl import load_workbook

INPUT_FILE = 'GEO Data.xlsx'
OUTPUT_FILE = 'GEO_Data_v2.xlsx'

def upgrade_schema():
    print(f"Reading {INPUT_FILE}...")
    
    # 1. Read existing sheets
    try:
        xls = pd.ExcelFile(INPUT_FILE)
        sheet_map = {sheet: pd.read_excel(xls, sheet) for sheet in xls.sheet_names}
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    # 2. Define Schema Updates (New Columns per Sheet)
    schema_updates = {
        'runs': [
            'user_location', 'browser_language', 'vpn_status', 
            'generated_search_query', 'prompt_intent_type'
        ],
        'bing_results': [
            'content_word_count', 'content_format', 'listicle_item_count',
            'has_table', 'has_schema_markup', 'tone', 
            'readability_score', 'freshness_date', 'semantic_similarity_score',
            'primary_product_id'
        ],
        'citations': [
            'is_hallucination', 'bing_rank_match', 'recommendation_sentiment',
            'is_primary_recommendation', 'primary_product_id'
        ],
        'domains': [
            'traffic_value', 'linked_root_domains', 'primary_topic'
        ]
    }

    # 3. Apply Column Updates
    for sheet_name, new_cols in schema_updates.items():
        if sheet_name in sheet_map:
            df = sheet_map[sheet_name]
            existing_cols = set(df.columns)
            for col in new_cols:
                if col not in existing_cols:
                    df[col] = None  # Add empty column
            sheet_map[sheet_name] = df
            print(f"Updated schema for '{sheet_name}'")

    # 4. Create NEW Sheets (Empty Dataframes)
    
    # Products Sheet (Master Entity List)
    if 'products' not in sheet_map:
        products_cols = [
            'product_id', 'product_name', 'canonical_domain', 
            'category', 'competitor_tier', 'notes'
        ]
        sheet_map['products'] = pd.DataFrame(columns=products_cols)
        print("Created new sheet 'products'")

    # Listicle Mentions Sheet (Indirect Visibility)
    if 'listicle_mentions' not in sheet_map:
        mentions_cols = [
            'mention_id', 'run_id', 'source_url', 'product_id',
            'list_position', 'sentiment', 'context_snippet'
        ]
        sheet_map['listicle_mentions'] = pd.DataFrame(columns=mentions_cols)
        print("Created new sheet 'listicle_mentions'")

    # 5. Save to New Excel File
    print(f"Saving to {OUTPUT_FILE}...")
    with pd.ExcelWriter(OUTPUT_FILE, engine='openpyxl') as writer:
        for sheet_name, df in sheet_map.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            
    print("Success! Schema upgrade complete.")

if __name__ == "__main__":
    upgrade_schema()


