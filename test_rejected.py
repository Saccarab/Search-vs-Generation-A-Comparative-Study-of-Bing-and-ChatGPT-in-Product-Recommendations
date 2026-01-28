import json
import csv

with open('datapass/chatgpt_results_2026-01-27T11-23-04-enterprise.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        rid = f"{row['prompt_id']}_r{row['run_number']}"
        if rid == 'P001_r1':
            srg = json.loads(row.get('search_result_groups_json') or '[]')
            cited = set(s['url'] for s in json.loads(row.get('sources_cited_json') or '[]'))
            additional = set(s['url'] for s in json.loads(row.get('sources_additional_json') or '[]'))
            all_used = cited | additional
            
            rejected = []
            for group in srg:
                for entry in group.get('entries', []):
                    if entry.get('url') and entry['url'] not in all_used:
                        rejected.append({
                            'url': entry['url'],
                            'title': entry.get('title', ''),
                            'domain': group.get('domain', ''),
                            'snippet': (entry.get('snippet') or '')[:100]
                        })
            print(f'SRG groups: {len(srg)}')
            print(f'Cited: {len(cited)}')
            print(f'Additional: {len(additional)}')
            print(f'All used: {len(all_used)}')
            print(f'Rejected: {len(rejected)}')
            for r in rejected:
                print(f"  - {r['domain']}: {r['title'][:40]}")
            break
