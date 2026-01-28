import fs from 'fs';
import path from 'path';
import axios from 'axios';
import * as cheerio from 'cheerio';
import stringSimilarity from 'string-similarity';

const ROOT_DIR = process.cwd();
const RESPONSES_DIR = path.join(ROOT_DIR, 'data', 'gemini_raw_responses');
const RESOLVED_URLS_FILE = path.join(ROOT_DIR, 'data', 'resolved_grounding_urls.json');
const OUTPUT_FILE = path.join(ROOT_DIR, 'data', 'p007_r1_footprint_analysis.json');

async function runFootprintAnalysis() {
    console.log('👣 Starting "Footprint" Matching for P007_r1...');
    
    const resolvedUrls = JSON.parse(fs.readFileSync(RESOLVED_URLS_FILE, 'utf-8'));
    
    // Find the specific P007_r1 file
    const files = fs.readdirSync(RESPONSES_DIR).filter(f => f.startsWith('P007_r1') && f.endsWith('.json'));
    if (files.length === 0) {
        console.error('❌ Could not find P007_r1 response file.');
        return;
    }
    
    // Use the latest one
    const targetFile = files.sort().reverse()[0];
    console.log(`📄 Analyzing: ${targetFile}`);
    
    const content = JSON.parse(fs.readFileSync(path.join(RESPONSES_DIR, targetFile), 'utf-8'));
    const chunks = content.groundingMetadata?.groundingChunks || [];
    const supports = content.groundingMetadata?.groundingSupports || [];

    const results = [];

    for (let i = 0; i < chunks.length; i++) {
        const chunk = chunks[i];
        const rawUri = chunk.web?.uri;
        const resolvedUri = resolvedUrls[rawUri] || rawUri;
        
        if (!resolvedUri || resolvedUri.includes('vertexaisearch')) continue;

        console.log(`\n🌐 Fetching Source [${i}]: ${resolvedUri}`);
        
        let fullText = '';
        try {
            const response = await axios.get(resolvedUri, { 
                timeout: 15000, 
                headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' } 
            });
            const $ = cheerio.load(response.data);
            $('script, style, nav, footer, header, aside').remove();
            fullText = $('body').text().replace(/\s+/g, ' ').trim();
        } catch (e) {
            console.warn(`   ⚠️ Failed to fetch: ${e.message}`);
            continue;
        }

        // Split page into sentences (rough split)
        const pageSentences = fullText.match(/[^.!?]+[.!?]+/g) || [fullText];
        const survivingSentences = [];
        
        // Find segments that cite this chunk
        const relevantSegments = supports.filter(s => s.groundingChunkIndices.includes(i));
        
        console.log(`   Found ${relevantSegments.length} segments in Gemini response citing this source.`);

        let matchedCharsOnPage = 0;

        pageSentences.forEach(pageSent => {
            const cleanPageSent = pageSent.trim();
            if (cleanPageSent.length < 20) return;

            let isSurviving = false;
            let bestScore = 0;

            relevantSegments.forEach(seg => {
                const score = stringSimilarity.compareTwoStrings(cleanPageSent.toLowerCase(), seg.segment.text.toLowerCase());
                if (score > bestScore) bestScore = score;
                
                // If the Gemini segment contains unique keywords from this sentence, or vice versa
                if (score > 0.3) { // Threshold for "semantic footprint"
                    isSurviving = true;
                }
            });

            if (isSurviving) {
                survivingSentences.push({
                    text: cleanPageSent,
                    score: bestScore.toFixed(2)
                });
                matchedCharsOnPage += cleanPageSent.length;
            }
        });

        const survivalRate = (matchedCharsOnPage / fullText.length) * 100;

        results.push({
            chunkIndex: i,
            url: resolvedUri,
            title: chunk.web?.title,
            totalPageChars: fullText.length,
            survivingChars: matchedCharsOnPage,
            survivalRate: survivalRate.toFixed(2) + '%',
            footprints: survivingSentences
        });

        console.log(`   ✅ Survival Rate: ${survivalRate.toFixed(2)}% (${matchedCharsOnPage} / ${fullText.length} chars)`);
    }

    fs.writeFileSync(OUTPUT_FILE, JSON.stringify(results, null, 2));
    console.log(`\n✨ Footprint analysis complete! Results saved to ${OUTPUT_FILE}`);
}

runFootprintAnalysis();
