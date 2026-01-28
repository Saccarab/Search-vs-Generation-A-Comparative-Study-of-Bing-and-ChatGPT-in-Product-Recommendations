#!/usr/bin/env python3
"""
Gemini Grounding Analysis - Task 1: Extract webSearchQueries from JSON files

This script processes Gemini response JSON files to extract webSearchQueries
and build the foundation for the AI Search Filter analysis.
"""

import json
import os
import pandas as pd
from pathlib import Path
from typing import Dict, List, Set
import argparse

def extract_web_search_queries(json_file_path: str) -> List[str]:
    """
    Extract webSearchQueries from a single Gemini JSON response file.

    Args:
        json_file_path: Path to the JSON file

    Returns:
        List of search queries used by Gemini
    """
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Extract webSearchQueries - handle different possible structures
        queries = []

        # Check if it's a list of responses or a single response
        if isinstance(data, list):
            for response in data:
                if 'candidates' in response:
                    for candidate in response['candidates']:
                        if 'groundingMetadata' in candidate:
                            metadata = candidate['groundingMetadata']
                            if 'webSearchQueries' in metadata:
                                queries.extend(metadata['webSearchQueries'])
        else:
            # Single response structure
            if 'candidates' in data:
                for candidate in data['candidates']:
                    if 'groundingMetadata' in candidate:
                        metadata = candidate['groundingMetadata']
                        if 'webSearchQueries' in metadata:
                            queries.extend(metadata['webSearchQueries'])

        return list(set(queries))  # Remove duplicates

    except Exception as e:
        print(f"Error processing {json_file_path}: {e}")
        return []

def extract_grounding_data(json_file_path: str) -> Dict:
    """
    Extract comprehensive grounding data from a Gemini JSON response.

    Returns dict with:
    - webSearchQueries: list of queries
    - groundingChunks: list of retrieved sources
    - groundingSupports: list of actually cited sources
    """
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        result = {
            'file': os.path.basename(json_file_path),
            'webSearchQueries': [],
            'groundingChunks': [],
            'groundingSupports': []
        }

        def process_candidate(candidate):
            if 'groundingMetadata' in candidate:
                metadata = candidate['groundingMetadata']

                # Extract queries
                if 'webSearchQueries' in metadata:
                    result['webSearchQueries'].extend(metadata['webSearchQueries'])

                # Extract chunks (retrieved sources)
                if 'groundingChunks' in metadata:
                    for chunk in metadata['groundingChunks']:
                        chunk_data = {
                            'title': chunk.get('title', ''),
                            'uri': chunk.get('uri', ''),
                            'index': chunk.get('index', 0)
                        }
                        result['groundingChunks'].append(chunk_data)

                # Extract supports (cited sources)
                if 'groundingSupports' in metadata:
                    for support in metadata['groundingSupports']:
                        support_data = {
                            'segment': support.get('segment', ''),
                            'text': support.get('text', ''),
                            'web': support.get('web', {}),
                            'confidenceScore': support.get('confidenceScore', 0.0)
                        }
                        result['groundingSupports'].append(support_data)

        # Process data structure
        if isinstance(data, list):
            for response in data:
                if 'candidates' in response:
                    for candidate in response['candidates']:
                        process_candidate(candidate)
        else:
            if 'candidates' in data:
                for candidate in data['candidates']:
                    process_candidate(candidate)

        # Remove duplicates from queries
        result['webSearchQueries'] = list(set(result['webSearchQueries']))

        return result

    except Exception as e:
        print(f"Error processing {json_file_path}: {e}")
        return {
            'file': os.path.basename(json_file_path),
            'webSearchQueries': [],
            'groundingChunks': [],
            'groundingSupports': []
        }

def build_master_csv_foundation(json_dir: str, output_csv: str) -> pd.DataFrame:
    """
    Build the foundation for the Master CSV by processing all JSON files.

    Args:
        json_dir: Directory containing JSON files
        output_csv: Output CSV path

    Returns:
        DataFrame with the foundation data
    """
    json_path = Path(json_dir)
    all_data = []

    # Find all JSON files
    json_files = list(json_path.glob("*.json"))
    print(f"Found {len(json_files)} JSON files")

    for json_file in json_files:
        print(f"Processing {json_file.name}...")
        data = extract_grounding_data(str(json_file))

        # Create rows for each query-chunk combination
        for query in data['webSearchQueries']:
            # Add entries for chunks
            for chunk in data['groundingChunks']:
                all_data.append({
                    'file': data['file'],
                    'query': query,
                    'url': chunk['uri'],
                    'title': chunk['title'],
                    'chunk_index': chunk['index'],
                    'is_in_chunks': True,
                    'is_in_supports': False,  # Will be updated below
                    'support_text': '',
                    'confidence_score': 0.0
                })

            # If no chunks for this query, still add the query
            if not data['groundingChunks']:
                all_data.append({
                    'file': data['file'],
                    'query': query,
                    'url': '',
                    'title': '',
                    'chunk_index': -1,
                    'is_in_chunks': False,
                    'is_in_supports': False,
                    'support_text': '',
                    'confidence_score': 0.0
                })

        # Mark URLs that are actually cited in supports
        support_urls = set()
        for support in data['groundingSupports']:
            if 'web' in support and support['web']:
                # Extract URL from web field - might need adjustment based on actual structure
                web_info = support['web']
                if isinstance(web_info, dict) and 'uri' in web_info:
                    support_urls.add(web_info['uri'])

        # Update is_in_supports for matching URLs
        for row in all_data:
            if row['file'] == data['file'] and row['url'] in support_urls:
                row['is_in_supports'] = True
                # Find the corresponding support data
                for support in data['groundingSupports']:
                    if ('web' in support and support['web'] and
                        isinstance(support['web'], dict) and
                        support['web'].get('uri') == row['url']):
                        row['support_text'] = support.get('text', '')
                        row['confidence_score'] = support.get('confidenceScore', 0.0)
                        break

    # Create DataFrame
    df = pd.DataFrame(all_data)

    # Remove duplicates (same file, query, url combination)
    df = df.drop_duplicates(subset=['file', 'query', 'url'])

    # Save to CSV
    df.to_csv(output_csv, index=False)
    print(f"Saved {len(df)} rows to {output_csv}")

    return df

def main():
    parser = argparse.ArgumentParser(description='Extract Gemini grounding data for AI Search Filter analysis')
    parser.add_argument('--json-dir', required=True, help='Directory containing Gemini JSON response files')
    parser.add_argument('--output-csv', default='data/gemini_grounding_foundation.csv',
                        help='Output CSV file path')
    parser.add_argument('--summary-only', action='store_true',
                        help='Only print summary statistics, don\'t create full CSV')

    args = parser.parse_args()

    if not os.path.exists(args.json_dir):
        print(f"Error: Directory {args.json_dir} does not exist")
        return

    if args.summary_only:
        # Just extract and summarize queries
        json_path = Path(args.json_dir)
        all_queries = set()

        for json_file in json_path.glob("*.json"):
            queries = extract_web_search_queries(str(json_file))
            all_queries.update(queries)

        print("=== GEMINI GROUNDING ANALYSIS SUMMARY ===")
        print(f"Total JSON files processed: {len(list(json_path.glob('*.json')))}")
        print(f"Unique webSearchQueries found: {len(all_queries)}")
        print("\nSample queries:")
        for i, query in enumerate(sorted(list(all_queries))[:10]):
            print(f"  {i+1}. {query}")
        if len(all_queries) > 10:
            print(f"  ... and {len(all_queries) - 10} more")

    else:
        # Build full foundation CSV
        print("Building Gemini grounding foundation CSV...")
        df = build_master_csv_foundation(args.json_dir, args.output_csv)

        print("\n=== FOUNDATION CSV SUMMARY ===")
        print(f"Total rows: {len(df)}")
        print(f"Unique queries: {df['query'].nunique()}")
        print(f"Unique URLs: {df['url'].nunique()}")
        print(f"URLs in chunks: {df['is_in_chunks'].sum()}")
        print(f"URLs in supports (cited): {df['is_in_supports'].sum()}")

if __name__ == "__main__":
    main()