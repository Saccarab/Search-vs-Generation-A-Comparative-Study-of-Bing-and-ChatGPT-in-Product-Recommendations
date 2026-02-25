const fs = require('fs');

const raw = fs.readFileSync('datapass/raw_network_responses/P001_r2.json', 'utf8');
const arr = JSON.parse(raw);

for (let i = 0; i < arr.length; i++) {
  const str = JSON.stringify(arr[i]);
  if (str.includes('web.run') || str.includes('web_run')) {
    // Find the context
    const idx = str.indexOf('web.run');
    if (idx > -1) {
      console.log(`Item ${i}: ...${str.slice(Math.max(0, idx - 100), idx + 200)}...`);
      console.log('---');
    }
    const idx2 = str.indexOf('web_run');
    if (idx2 > -1 && idx2 !== idx) {
      console.log(`Item ${i} (web_run): ...${str.slice(Math.max(0, idx2 - 100), idx2 + 200)}...`);
      console.log('---');
    }
  }
}
