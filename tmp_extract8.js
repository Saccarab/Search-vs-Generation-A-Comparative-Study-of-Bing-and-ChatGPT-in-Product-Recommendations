const fs = require('fs');

const raw = fs.readFileSync('datapass/raw_network_responses/P001_r2.json', 'utf8');
const arr = JSON.parse(raw);

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
    if (groups && Array.isArray(groups) && groups.length > 0) {
      // Show full first entry to see all fields
      console.log('First group, first entry keys:', Object.keys(groups[0].entries[0]));
      console.log('\nFull first entry:');
      console.log(JSON.stringify(groups[0].entries[0], null, 2));
      break;
    }
  }
}
