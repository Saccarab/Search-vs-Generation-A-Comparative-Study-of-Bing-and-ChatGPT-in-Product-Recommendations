import sqlite3, json
from collections import Counter

db=sqlite3.connect('geo_fresh.db'); db.row_factory=sqlite3.Row

# Correct label loading logic
labels = {}
path = 'datapass/page_labels_combined_v2.5.jsonl'
with open(path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            obj = json.loads(line)
            dna_container = obj.get('response')
            if dna_container and isinstance(dna_container, dict):
                dna = dna_container.get('urls') # The actual DNA is in the 'urls' key
                if dna and isinstance(dna, dict):
                    u = obj.get('url')
                    if u:
                        norm = u.lower().replace('https://','').replace('http://','').replace('www.','').strip('/')
                        labels[norm] = dna
        except Exception:
            continue

def get_dna_dist(acct):
    unique_urls = [r[0] for r in db.execute('SELECT DISTINCT url_normalized FROM citations WHERE account_type=? AND citation_type=?', (acct, 'cited')).fetchall()]
    type_counts = Counter()
    tone_counts = Counter()
    lab_n = 0
    for u in unique_urls:
        lab = labels.get(u)
        if lab:
            lab_n += 1
            type_counts[lab.get('type', 'other')] += 1
            tone_counts[lab.get('tone', 'other')] += 1
    return len(unique_urls), lab_n, type_counts, tone_counts

def get_gemini_dna_dist():
    with open('tools/GeminiVizApp/data/master_bundle.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    gemini_types = Counter()
    gemini_tones = Counter()
    gemini_labeled_urls = set()
    for run in data.get('runs', []):
        for chunk in run.get('groundingChunks', []):
            uri = (chunk.get('web') or {}).get('uri')
            if uri:
                resolved = (chunk.get('web') or {}).get('resolvedUri') or data.get('resolvedUrls', {}).get(uri, uri)
                norm = resolved.lower().replace('https://','').replace('http://','').replace('www.','').strip('/')
                if norm in labels and norm not in gemini_labeled_urls:
                    gemini_labeled_urls.add(norm)
                    lab = labels[norm]
                    gemini_types[lab.get('type', 'other')] += 1
                    gemini_tones[lab.get('tone', 'other')] += 1
    return len(gemini_labeled_urls), gemini_types, gemini_tones

def format_table(counts, total):
    out = "| Type | Count | Share (%) |\n| :--- | :---: | :---: |\n"
    for t, c in counts.most_common(5):
        out += f"| {t} | {c} | {round(c/total*100,1)}% |\n"
    return out

def format_tone_table(counts, total):
    out = "| Tone | Count | Share (%) |\n| :--- | :---: | :---: |\n"
    for t, c in counts.most_common(3):
        out += f"| {t} | {c} | {round(c/total*100,1)}% |\n"
    return out

# GPT Enterprise
n_ent, lab_ent, types_ent, tones_ent = get_dna_dist('enterprise')
print("### GPT Enterprise DNA")
print(format_table(types_ent, lab_ent))
print(format_tone_table(tones_ent, lab_ent))

# GPT Personal
n_pers, lab_pers, types_pers, tones_pers = get_dna_dist('personal')
print("\n### GPT Personal DNA")
print(format_table(types_pers, lab_pers))
print(format_tone_table(tones_pers, lab_pers))

# Gemini
lab_gem, types_gem, tones_gem = get_gemini_dna_dist()
print("\n### Gemini DNA")
print(format_table(types_gem, lab_gem))
print(format_tone_table(tones_gem, lab_gem))
