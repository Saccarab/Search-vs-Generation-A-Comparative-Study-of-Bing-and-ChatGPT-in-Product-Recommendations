const fs = require('fs');
const path = require('path');

// Debug one file
const raw = fs.readFileSync('datapass/raw_network_responses/P001_r2.json', 'utf8');
const arr = JSON.parse(raw);

// Show all cite patterns
const citeRefs = new Set();
for (const item of arr) {
  const str = JSON.stringify(item);
  const matches = str.matchAll(/citeturn(\d+)search(\d+)/g);
  for (const m of matches) {
    citeRefs.add(`turn=${m[1]}, search=${m[2]}`);
  }
}
console.log('Cited refs:', [...citeRefs]);

// Show all ref_ids in search_result_groups
function findKey(obj, key) {
  if (obj === null || obj === undefined || typeof obj !== 'object') return null;
  if (obj[key]) return obj[key];
  for (const val of Object.values(obj)) {
    const r = findKey(val, key);
    if (r) return r;
  }
  return null;
}

for (const item of arr) {
  if (item && typeof item === 'object') {
    const groups = findKey(item, 'search_result_groups');
    if (groups && Array.isArray(groups)) {
      console.log('\nSearch result groups ref_ids:');
      for (let i = 0; i < groups.length; i++) {
        for (const e of groups[i].entries) {
          const hasDate = e.pub_date !== null && e.pub_date !== undefined;
          console.log(`  Group ${i}: ref_index=${e.ref_id.ref_index}, pub_date=${hasDate ? new Date(e.pub_date*1000).toISOString().slice(0,10) : 'null'}, title=${e.title.slice(0,50)}`);
        }
      }
      break;
    }
  }
}
