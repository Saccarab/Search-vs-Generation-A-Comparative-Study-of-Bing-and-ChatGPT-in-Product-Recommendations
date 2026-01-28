#!/usr/bin/env node

/**
 * Gemini Grounding Data Collection Pipeline
 *
 * This script collects Gemini responses with grounding metadata for AI Search Filter analysis.
 * Inspired by Dejan AI's research on Google's grounding chunks and AI search filter.
 */

import { GoogleGenAI } from '@google/genai';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Configuration
const CONFIG = {
  modelId: 'gemini-2.0-flash-exp', // Latest experimental model with grounding
  maxRetries: 3,
  delayBetweenCalls: 1000, // ms
  outputDir: path.join(__dirname, '..', 'data', 'gemini_responses')
};

// Ensure output directory exists
if (!fs.existsSync(CONFIG.outputDir)) {
  fs.mkdirSync(CONFIG.outputDir, { recursive: true });
}

// Initialize Gemini client
const ai = new GoogleGenAI({
  apiKey: process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY
});

async function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function callGeminiWithGrounding(prompt, attempt = 1) {
  try {
    console.log(`Calling Gemini for: "${prompt.substring(0, 60)}..." (attempt ${attempt})`);

    const response = await ai.models.generateContent({
      model: CONFIG.modelId,
      contents: prompt,
      config: {
        tools: [{ googleSearch: {} }], // Enable web search grounding
        thinkingConfig: {
          thinkingLevel: 'low', // Balanced for research
          includeThoughts: true
        },
        responseMimeType: 'application/json' // For structured output if needed
      },
    });

    return response;
  } catch (error) {
    console.error(`Attempt ${attempt} failed:`, error.message);

    if (attempt < CONFIG.maxRetries) {
      const backoffDelay = CONFIG.delayBetweenCalls * Math.pow(2, attempt - 1);
      console.log(`Retrying in ${backoffDelay}ms...`);
      await delay(backoffDelay);
      return callGeminiWithGrounding(prompt, attempt + 1);
    }

    throw error;
  }
}

function saveResponseToJson(prompt, response, index) {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const safePrompt = prompt.replace(/[^a-zA-Z0-9]/g, '_').substring(0, 50);
  const filename = `${timestamp}_query_${index}_${safePrompt}.json`;

  const filepath = path.join(CONFIG.outputDir, filename);

  // Extract key metadata for analysis
  const candidate = response.candidates?.[0];
  const groundingMetadata = candidate?.groundingMetadata;

  const dataToSave = {
    metadata: {
      timestamp: new Date().toISOString(),
      model: CONFIG.modelId,
      original_prompt: prompt,
      query_index: index
    },
    response: {
      text: candidate?.content?.parts?.[0]?.text || '',
      groundingMetadata: groundingMetadata || null
    },
    analysis_ready: {
      webSearchQueries: groundingMetadata?.webSearchQueries || [],
      groundingChunks: groundingMetadata?.groundingChunks || [],
      groundingSupports: groundingMetadata?.groundingSupports || []
    }
  };

  fs.writeFileSync(filepath, JSON.stringify(dataToSave, null, 2));
  console.log(`Saved response to: ${filename}`);

  return filepath;
}

async function loadQueriesFromCsv(csvPath) {
  const fs = await import('fs');
  const content = fs.readFileSync(csvPath, 'utf-8');
  const lines = content.split('\n').filter(line => line.trim());

  // Skip header if it exists
  const startIndex = lines[0].toLowerCase().includes('query') ? 1 : 0;

  return lines.slice(startIndex).map(line => {
    // Handle quoted CSV values
    if (line.startsWith('"') && line.endsWith('"')) {
      return line.slice(1, -1);
    }
    return line;
  }).filter(query => query.trim());
}

async function collectGeminiResponses(queries, startIndex = 0, batchSize = null) {
  const results = [];
  const endIndex = batchSize ? Math.min(startIndex + batchSize, queries.length) : queries.length;

  console.log(`\n=== Starting Gemini Data Collection ===`);
  console.log(`Processing queries ${startIndex + 1} to ${endIndex} of ${queries.length}`);
  console.log(`Model: ${CONFIG.modelId}`);
  console.log(`Output directory: ${CONFIG.outputDir}\n`);

  for (let i = startIndex; i < endIndex; i++) {
    const query = queries[i];
    console.log(`\n[${i + 1}/${queries.length}] Processing query: ${query}`);

    try {
      const response = await callGeminiWithGrounding(query);
      const filepath = saveResponseToJson(query, response, i);

      results.push({
        index: i,
        query: query,
        success: true,
        filepath: filepath,
        groundingQueries: response.candidates?.[0]?.groundingMetadata?.webSearchQueries?.length || 0,
        groundingChunks: response.candidates?.[0]?.groundingMetadata?.groundingChunks?.length || 0,
        groundingSupports: response.candidates?.[0]?.groundingMetadata?.groundingSupports?.length || 0
      });

    } catch (error) {
      console.error(`Failed to process query ${i}:`, error.message);
      results.push({
        index: i,
        query: query,
        success: false,
        error: error.message
      });
    }

    // Rate limiting
    if (i < endIndex - 1) {
      console.log(`Waiting ${CONFIG.delayBetweenCalls}ms before next call...`);
      await delay(CONFIG.delayBetweenCalls);
    }
  }

  return results;
}

function printSummary(results) {
  const successful = results.filter(r => r.success);
  const failed = results.filter(r => !r.success);

  console.log(`\n=== COLLECTION SUMMARY ===`);
  console.log(`Total queries processed: ${results.length}`);
  console.log(`Successful: ${successful.length}`);
  console.log(`Failed: ${failed.length}`);

  if (successful.length > 0) {
    console.log(`\nGrounding statistics:`);
    console.log(`Average webSearchQueries per response: ${(successful.reduce((sum, r) => sum + r.groundingQueries, 0) / successful.length).toFixed(1)}`);
    console.log(`Average groundingChunks per response: ${(successful.reduce((sum, r) => sum + r.groundingChunks, 0) / successful.length).toFixed(1)}`);
    console.log(`Average groundingSupports per response: ${(successful.reduce((sum, r) => sum + r.groundingSupports, 0) / successful.length).toFixed(1)}`);
  }

  if (failed.length > 0) {
    console.log(`\nFailed queries:`);
    failed.forEach(f => console.log(`  - Query ${f.index + 1}: ${f.error}`));
  }
}

// CLI interface
async function main() {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    console.log(`
Usage: node collect_gemini_responses.js <command> [options]

Commands:
  collect <csv-file> [start-index] [batch-size]  - Collect responses from CSV
  test <query>                                     - Test single query
  list                                            - List existing response files

Examples:
  node collect_gemini_responses.js collect queries.csv
  node collect_gemini_responses.js collect queries.csv 0 5  # First 5 queries
  node collect_gemini_responses.js test "What is AI search?"
  node collect_gemini_responses.js list
    `);
    return;
  }

  const command = args[0];

  try {
    switch (command) {
      case 'collect':
        const csvPath = args[1];
        const startIndex = parseInt(args[2]) || 0;
        const batchSize = args[3] ? parseInt(args[3]) : null;

        if (!csvPath) {
          console.error('Please specify a CSV file path');
          return;
        }

        const queries = await loadQueriesFromCsv(csvPath);
        console.log(`Loaded ${queries.length} queries from ${csvPath}`);

        const results = await collectGeminiResponses(queries, startIndex, batchSize);
        printSummary(results);
        break;

      case 'test':
        const testQuery = args.slice(1).join(' ');
        if (!testQuery) {
          console.error('Please specify a test query');
          return;
        }

        console.log(`Testing single query: "${testQuery}"`);
        const testResponse = await callGeminiWithGrounding(testQuery);
        const testFilepath = saveResponseToJson(testQuery, testResponse, 0);

        console.log(`Test response saved to: ${testFilepath}`);
        break;

      case 'list':
        const files = fs.readdirSync(CONFIG.outputDir)
          .filter(file => file.endsWith('.json'))
          .sort()
          .reverse(); // Most recent first

        console.log(`\n=== Existing Gemini Response Files ===`);
        console.log(`Found ${files.length} files in ${CONFIG.outputDir}:`);

        files.slice(0, 10).forEach((file, i) => {
          console.log(`${i + 1}. ${file}`);
        });

        if (files.length > 10) {
          console.log(`... and ${files.length - 10} more files`);
        }
        break;

      default:
        console.error(`Unknown command: ${command}`);
    }

  } catch (error) {
    console.error('Error:', error.message);
    process.exit(1);
  }
}

// Run if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}

export { callGeminiWithGrounding, saveResponseToJson, collectGeminiResponses };