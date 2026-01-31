import fs from 'fs';
import path from 'path';

const mappingsDir = 'datapass/citation_mappings';
const files = fs.readdirSync(mappingsDir).filter(f => f.endsWith('_mapping.json') && !f.startsWith('_'));

const queries = [];
const seen = new Set();

files.forEach(file => {
  try {
    const data = JSON.parse(fs.readFileSync(path.join(mappingsDir, file), 'utf8'));
    const runId = data.run_id || file.replace('_mapping.json', '');
    
    // Get hidden queries (fan-out queries)
    if (data.metadata && data.metadata.hidden_queries) {
      data.metadata.hidden_queries.forEach((q, idx) => {
        const key = runId + '_Q' + (idx + 1) + '_' + q;
        if (!seen.has(key)) {
          seen.add(key);
          queries.push({
            runId: runId + '_Q' + (idx + 1),
            query: q
          });
        }
      });
    }
    
    // Also get the generated_search_query if different
    if (data.metadata && data.metadata.generated_search_query) {
      const q = data.metadata.generated_search_query;
      const key = runId + '_main_' + q;
      if (!seen.has(key)) {
        seen.add(key);
        queries.push({
          runId: runId + '_main',
          query: q
        });
      }
    }
  } catch (e) {
    console.error('Error parsing', file, e.message);
  }
});

// Write CSV
const lines = ['runId,query'];
queries.forEach(q => {
  const escapedQuery = q.query.replace(/"/g, '""');
  lines.push(`${q.runId},"${escapedQuery}"`);
});

fs.writeFileSync('data/serpapi_google_input.csv', lines.join('\n'));

console.log('Generated data/serpapi_google_input.csv');
console.log('Total unique queries:', queries.length);
console.log('');
console.log('Sample queries:');
queries.slice(0, 10).forEach(q => console.log('  ' + q.runId + ': ' + q.query));
