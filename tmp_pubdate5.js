const fs = require('fs');

const raw = fs.readFileSync('datapass/raw_network_responses/P001_r2.json', 'utf8');
const arr = JSON.parse(raw);

// Show item 53 which had content_references
console.log('Item 53 (first 500 chars):');
console.log(JSON.stringify(arr[53]).slice(0, 800));
console.log('\n---\n');

// Collect all content_reference appends
for (let i = 0; i < arr.length; i++) {
  const str = JSON.stringify(arr[i]);
  if (str.includes('content_references') && str.includes('matched_text')) {
    // Extract the matched_text values
    const mtMatches = str.matchAll(/"matched_text":"([^"]+)"/g);
    for (const m of mtMatches) {
      console.log(`Item ${i}: matched_text="${m[1]}"`);
    }
  }
}

// Also check: how many groups does this file actually have? (only 1 from earlier)
// Let me check ALL items for search_result_groups
let groupCount = 0;
for (let i = 0; i < arr.length; i++) {
  const str = JSON.stringify(arr[i]);
  if (str.includes('search_result_groups')) {
    groupCount++;
  }
}
console.log(`\nItems containing search_result_groups: ${groupCount}`);
