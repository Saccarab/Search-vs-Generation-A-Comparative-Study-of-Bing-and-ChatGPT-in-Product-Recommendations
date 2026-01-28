import fs from 'fs';
import path from 'path';
import axios from 'axios';
import * as cheerio from 'cheerio';

const ROOT_DIR = process.cwd();
const RESPONSES_DIR = path.join(ROOT_DIR, 'data', 'gemini_raw_responses');
const OUTPUT_FILE = path.join(ROOT_DIR, 'data', 'extraction_efficiency.json');
const RESOLVED_URLS_FILE = path.join(ROOT_DIR, 'data', 'resolved_grounding_urls.json');

async function calculateEfficiency() {
    console.log('📊 Starting Extraction Efficiency Analysis...');
    
    const resolvedUrls = JSON.parse(fs.readFileSync(RESOLVED_URLS_FILE, 'utf-8'));
    const responseFiles = fs.readdirSync(RESPONSES_DIR).filter(f => f.endsWith('.json'));
    
    // 1. Group by runId and keep latest
    const latestFilesMap = new Map();
    responseFiles.forEach(file => {
        const parts = file.split('_');
        if (parts.length < 3) return;
        const runId = `${parts[0]}_${parts[1]}`;
        const timestamp = parts[2].replace('.json', '');
        if (!latestFilesMap.has(runId) || timestamp > latestFilesMap.get(runId).timestamp) {
            latestFilesMap.set(runId, { file, timestamp });
        }
    });

    const efficiencyData = [];
    const urlContentCache = {}; // Simple cache to avoid re-fetching same URL

    for (const [runId, { file }] of latestFilesMap.entries()) {
        const pNum = parseInt(runId.substring(1, 5));
        if (pNum < 4 || pNum > 7) continue; // Focus on our current good data

        console.log(`\n🔎 Analyzing Run: ${runId}`);
        const content = JSON.parse(fs.readFileSync(path.join(RESPONSES_DIR, file), 'utf-8'));
        const chunks = content.groundingMetadata?.groundingChunks || [];
        const supports = content.groundingMetadata?.groundingSupports || [];

        // Map chunk index to how many times it was actually cited in supports
        const citationCounts = {};
        supports.forEach(s => {
            (s.groundingChunkIndices || []).forEach(idx => {
                citationCounts[idx] = (citationCounts[idx] || 0) + 1;
            });
        });

        for (let i = 0; i < chunks.length; i++) {
            const chunk = chunks[i];
            const rawUri = chunk.web?.uri;
            const resolvedUri = resolvedUrls[rawUri] || rawUri;
            const chunkText = chunk.web?.title || ''; // Grounding chunks in API usually have a snippet or title
            
            // Note: In some Gemini API versions, the 'chunk' itself contains the extracted text.
            // We'll use the length of the chunk text Gemini stored vs the full page.
            const aiExtractedLength = chunkText.length; 
            
            if (!resolvedUri || resolvedUri.includes('vertexaisearch')) continue;

            console.log(`   [Chunk ${i}] Fetching: ${resolvedUri.substring(0, 50)}...`);
            
            let fullPageText = '';
            if (urlContentCache[resolvedUri]) {
                fullPageText = urlContentCache[resolvedUri];
            } else {
                try {
                    const response = await axios.get(resolvedUri, { timeout: 10000, headers: { 'User-Agent': 'Mozilla/5.0' } });
                    const $ = cheerio.load(response.data);
                    $('script, style, nav, footer, header').remove();
                    fullPageText = $('body').text().replace(/\s+/g, ' ').trim();
                    urlContentCache[resolvedUri] = fullPageText;
                } catch (e) {
                    console.warn(`      ⚠️ Failed to fetch page: ${e.message}`);
                    continue;
                }
            }

            const efficiency = fullPageText.length > 0 ? (aiExtractedLength / fullPageText.length) * 100 : 0;

            efficiencyData.push({
                runId,
                chunkIndex: i,
                url: resolvedUri,
                sourceTitle: chunk.web?.title,
                citationCount: citationCounts[i] || 0, // How many times Gemini actually used it in the response
                aiExtractedChars: aiExtractedLength,
                fullPageChars: fullPageText.length,
                efficiencyPercent: efficiency.toFixed(4)
            });
        }
    }

    fs.writeFileSync(OUTPUT_FILE, JSON.stringify(efficiencyData, null, 2));
    console.log(`\n✅ Efficiency analysis complete! Saved to ${OUTPUT_FILE}`);
    
    // Print quick summary
    const avgEfficiency = efficiencyData.reduce((acc, curr) => acc + parseFloat(curr.efficiencyPercent), 0) / efficiencyData.length;
    console.log(`📊 Average Extraction Efficiency: ${avgEfficiency.toFixed(2)}%`);
}

calculateEfficiency();
