import fs from 'fs';
import path from 'path';

/**
 * Extract webSearchQueries from Gemini JSON responses for Bing/Google Scraper
 */
function extractFanoutQueries() {
  const inputDir = './data/gemini_raw_responses';
  const outputFile = './data/gemini_fanout_queries.csv';
  
  if (!fs.existsSync(inputDir)) {
    console.error('❌ Input directory not found');
    return;
  }

  const files = fs.readdirSync(inputDir).filter(f => f.endsWith('.json'));
  const allQueries = [];

  files.forEach(file => {
    const content = JSON.parse(fs.readFileSync(path.join(inputDir, file), 'utf-8'));
    // Extract promptId and run number from filename, e.g., P0001_r1
    const parts = file.split('_');
    const runId = `${parts[0]}_${parts[1]}`; 
    
    const queries = content.groundingMetadata?.webSearchQueries || [];
    queries.forEach(q => {
      allQueries.push({ runId, query: q });
    });
  });

  // Create CSV content (run_id, query) - matching your extension's expected format
  const csvHeader = 'run_id,query\n';
  const csvRows = allQueries.map(item => `${item.runId},"${item.query.replace(/"/g, '""')}"`).join('\n');
  
  fs.writeFileSync(outputFile, csvHeader + csvRows);
  console.log(`✅ Extracted ${allQueries.length} fan-out queries to ${outputFile}`);
  console.log(`🚀 You can now upload this CSV to your Bing/Google Results Scraper extension.`);
}

extractFanoutQueries();
