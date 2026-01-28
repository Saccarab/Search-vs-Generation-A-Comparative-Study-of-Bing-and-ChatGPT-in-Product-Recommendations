#!/usr/bin/env python3
"""
Prepare and deduplicate query sets for Gemini data collection.
Combines queries from multiple CSV files and prepares them for batch processing.
"""

import pandas as pd
import argparse
from pathlib import Path

def load_and_combine_queries(csv_files):
    """Load queries from multiple CSV files and combine them."""
    all_queries = []

    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file)
            # Assume the first column contains queries
            query_col = df.columns[0]
            queries = df[query_col].dropna().tolist()
            all_queries.extend(queries)
            print(f"Loaded {len(queries)} queries from {csv_file}")
        except Exception as e:
            print(f"Error loading {csv_file}: {e}")

    return all_queries

def clean_and_deduplicate_queries(queries):
    """Clean and deduplicate the query list."""
    # Remove extra whitespace and normalize quotes
    cleaned = []
    for query in queries:
        if isinstance(query, str):
            # Strip whitespace and normalize quotes
            cleaned_query = query.strip()
            if cleaned_query.startswith('"') and cleaned_query.endswith('"'):
                cleaned_query = cleaned_query[1:-1]
            if cleaned_query:  # Only add non-empty queries
                cleaned.append(cleaned_query)

    # Remove duplicates while preserving order
    seen = set()
    deduplicated = []
    for query in cleaned:
        if query not in seen:
            seen.add(query)
            deduplicated.append(query)

    return deduplicated

def save_query_set(queries, output_file, format='csv'):
    """Save the query set to a file."""
    if format == 'csv':
        df = pd.DataFrame({'query': queries})
        df.to_csv(output_file, index=False)
    elif format == 'txt':
        with open(output_file, 'w', encoding='utf-8') as f:
            for query in queries:
                f.write(f"{query}\n")

    print(f"Saved {len(queries)} queries to {output_file}")

def main():
    parser = argparse.ArgumentParser(description='Prepare query sets for Gemini data collection')
    parser.add_argument('--input-csv', nargs='+', help='Input CSV files containing queries')
    parser.add_argument('--output-csv', default='data/gemini_queries.csv', help='Output CSV file')
    parser.add_argument('--output-txt', help='Also save as text file')
    parser.add_argument('--auto-discover', action='store_true', help='Automatically find query CSV files')

    args = parser.parse_args()

    # Auto-discover query files if requested
    if args.auto_discover:
        query_files = [
            'queries.csv',
            'query2.csv',
            'data/product recommendation query set.xlsx'  # Note: Excel might need special handling
        ]
        # Only include files that exist
        args.input_csv = [f for f in query_files if Path(f).exists()]

    if not args.input_csv:
        print("No input CSV files specified. Use --input-csv or --auto-discover")
        return

    # Load and combine queries
    all_queries = load_and_combine_queries(args.input_csv)

    # Clean and deduplicate
    cleaned_queries = clean_and_deduplicate_queries(all_queries)

    print(f"\nQuery processing summary:")
    print(f"  Raw queries loaded: {len(all_queries)}")
    print(f"  After cleaning/deduplication: {len(cleaned_queries)}")
    print(f"  Duplicates removed: {len(all_queries) - len(cleaned_queries)}")

    # Save to CSV
    save_query_set(cleaned_queries, args.output_csv, format='csv')

    # Save to text file if requested
    if args.output_txt:
        save_query_set(cleaned_queries, args.output_txt, format='txt')

    # Print sample queries
    print("
Sample queries:")
    for i, query in enumerate(cleaned_queries[:5]):
        print(f"  {i+1}. {query}")
    if len(cleaned_queries) > 5:
        print(f"  ... and {len(cleaned_queries) - 5} more")

if __name__ == "__main__":
    main()