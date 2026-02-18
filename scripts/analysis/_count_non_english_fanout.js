const fs = require('fs');
const path = require('path');

const DIR = path.join(__dirname, '../../datapass/raw_network_responses');

function hasNonEnglishChars(query) {
  const nonAsciiLetters = query.match(/[^\x00-\x7F]/g);
  if (nonAsciiLetters && nonAsciiLetters.length > 0) {
    const langChars = nonAsciiLetters.filter(c => {
      const code = c.codePointAt(0);
      if (code === 0x2013 || code === 0x2014) return false;
      if (code === 0x2018 || code === 0x2019) return false;
      if (code === 0x201C || code === 0x201D) return false;
      if (code === 0x2026) return false;
      if (code === 0x00A9 || code === 0x00AE || code === 0x2122) return false;
      if (code === 0x00B0) return false;
      return true;
    });
    if (langChars.length > 0) return langChars.join('');
  }
  return null;
}

function extractFanoutQueries(data) {
  const queries = [];
  // Recursively search for search_model_queries in any structure
  const searchObj = (obj) => {
    if (obj === null || typeof obj !== 'object') return;
    if (Array.isArray(obj)) {
      for (const item of obj) searchObj(item);
      return;
    }
    if (obj.search_model_queries && obj.search_model_queries.queries) {
      queries.push(...obj.search_model_queries.queries);
    }
    for (const key of Object.keys(obj)) {
      searchObj(obj[key]);
    }
  };
  searchObj(data);
  return queries;
}

const files = fs.readdirSync(DIR).filter(f => f.endsWith('.json'));
console.log(`Total JSON files: ${files.length}\n`);

const runsWithNonEnglish = [];
let totalRuns = 0;
let totalQueries = 0;
let totalNonEnglishQueries = 0;

for (const file of files) {
  const filePath = path.join(DIR, file);
  let data;
  try {
    data = JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch (e) {
    console.error(`  ERROR reading ${file}: ${e.message}`);
    continue;
  }

  const queries = extractFanoutQueries(data);
  if (queries.length === 0) continue;

  totalRuns++;
  totalQueries += queries.length;

  const nonEnglishInRun = [];
  for (const q of queries) {
    const chars = hasNonEnglishChars(q);
    if (chars) {
      nonEnglishInRun.push({ query: q, chars });
      totalNonEnglishQueries++;
    }
  }

  if (nonEnglishInRun.length > 0) {
    runsWithNonEnglish.push({ file, queries: nonEnglishInRun, totalQueries: queries.length });
  }
}

console.log('========================================');
console.log('RUNS WITH NON-ENGLISH FAN-OUT QUERIES');
console.log('========================================\n');

for (const run of runsWithNonEnglish) {
  console.log(`File: ${run.file} (${run.queries.length}/${run.totalQueries} queries non-English)`);
  for (const q of run.queries) {
    console.log(`  Query: "${q.query}"`);
    console.log(`  Non-English chars: ${q.chars}`);
  }
  console.log('');
}

console.log('========================================');
console.log('SUMMARY');
console.log('========================================');
console.log(`Total files scanned:              ${files.length}`);
console.log(`Total runs with fan-out queries:  ${totalRuns}`);
console.log(`Total fan-out queries found:      ${totalQueries}`);
console.log(`Runs with non-English queries:    ${runsWithNonEnglish.length}`);
console.log(`Percentage of runs:               ${totalRuns > 0 ? (runsWithNonEnglish.length / totalRuns * 100).toFixed(1) : 0}%`);
console.log(`Total non-English queries:        ${totalNonEnglishQueries}`);
console.log(`Percentage of queries:            ${totalQueries > 0 ? (totalNonEnglishQueries / totalQueries * 100).toFixed(1) : 0}%`);
