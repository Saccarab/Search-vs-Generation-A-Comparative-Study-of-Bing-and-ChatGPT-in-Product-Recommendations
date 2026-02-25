const fs = require('fs');

const raw = fs.readFileSync('datapass/raw_network_responses/P001_r2.json', 'utf8');
const arr = JSON.parse(raw);

// Search for any key containing "query" or "queries" or "search_model"
function findKeys(obj, results = new Set(), path = '') {
  if (obj === null || obj === undefined || typeof obj !== 'object') return results;
  for (const [k, v] of Object.entries(obj)) {
    const p = path ? `${path}.${k}` : k;
    if (k.toLowerCase().includes('quer') || k.toLowerCase().includes('search_model')) {
      results.add(p + ' = ' + JSON.stringify(v).slice(0, 200));
    }
    if (typeof v === 'object') {
      findKeys(v, results, p);
    }
  }
  return results;
}

// Check items around where search happens
for (let i = 0; i < arr.length; i++) {
  const str = JSON.stringify(arr[i]);
  if (str.includes('queries') && str.includes('search')) {
    const results = findKeys(arr[i]);
    for (const r of results) {
      if (r.includes('quer')) {
        console.log(`Item ${i}: ${r}`);
      }
    }
  }
}
