import { GoogleGenAI } from '@google/genai';
import fs from 'fs';
import path from 'path';

/**
 * Gemini Grounding Collector
 * 
 * This script runs your prompts through Gemini 2.0 Flash with Google Search grounding enabled.
 * It saves the full JSON response (including groundingMetadata) for analysis.
 */

// Initialize the client
const genAI = new GoogleGenAI(process.env.GEMINI_API_KEY);

const OUTPUT_DIR = './data/gemini_raw_responses';

// Ensure output directory exists
if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

/**
 * Runs a single prompt and saves the result
 */
async function runGeminiGrounding(prompt, promptId = 'test') {
  console.log(`\n🚀 Processing: "${prompt}"`);
  
  try {
    const response = await genAI.models.generateContent({
      model: 'gemini-3-flash-preview',
      contents: [{ role: 'user', parts: [{ text: prompt }] }],
      config: {
        tools: [{ googleSearch: {} }],
        thinkingConfig: {
          includeThoughts: true,
          thinkingLevel: 'minimal'
        },
        // We use a lower thinking level to focus on grounding extraction
        generationConfig: {
          temperature: 1,
        }
      }
    });

    const data = response.candidates[0];

    // Save the raw response for the "80 JSON" style analysis
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const filename = `${promptId}_${timestamp}.json`;
    const filePath = path.join(OUTPUT_DIR, filename);

    fs.writeFileSync(filePath, JSON.stringify(data, null, 2));
    
    console.log(`✅ Success! Response saved to: ${filePath}`);
    
    // Quick summary for console
    const metadata = data.groundingMetadata || {};
    console.log(`   - Queries generated: ${metadata.webSearchQueries?.length || 0}`);
    console.log(`   - Chunks retrieved: ${metadata.groundingChunks?.length || 0}`);
    console.log(`   - Supports cited: ${metadata.groundingSupports?.length || 0}`);

    return data;
  } catch (error) {
    console.error(`❌ Error with prompt "${prompt}":`, error.message);
    return null;
  }
}

/**
 * Batch process queries from a JSON file with multiple runs per prompt
 */
async function processBatch(queryFilePath, runsPerPrompt = 3) {
  const fileContent = fs.readFileSync(queryFilePath, 'utf-8');
  const { queries, promptIds } = JSON.parse(fileContent);
  
  console.log(`\n--- Starting Batch Process (${queries.length} queries x ${runsPerPrompt} runs) ---`);
  
  for (let run = 1; run <= runsPerPrompt; run++) {
    console.log(`\n=== RUN ${run} OF ${runsPerPrompt} ===`);
    for (let i = 0; i < queries.length; i++) {
      const promptId = promptIds ? promptIds[i] : `P${(i + 1).toString().padStart(4, '0')}`;
      const runId = `${promptId}_r${run}`;
      await runGeminiGrounding(queries[i], runId);
      
      // Small delay to be nice to the API
      await new Promise(r => setTimeout(r, 2000));
    }
  }
  
  console.log('\n--- Batch Process Complete ---');
}

// Check command line args
const args = process.argv.slice(2);
if (args[0] === '--batch') {
  const queryFile = args[1] || './data/gemini_all_prompts.json';
  const runs = parseInt(args[2]) || 3;
  processBatch(queryFile, runs);
} else if (args[0]) {
  runGeminiGrounding(args[0]);
} else {
  console.log('Usage:');
  console.log('  node collect_gemini.mjs "Your prompt here"');
  console.log('  node collect_gemini.mjs --batch ./data/gemini_11_queries.json');
}
