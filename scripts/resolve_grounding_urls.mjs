import fs from 'fs';
import path from 'path';
import axios from 'axios';

// Use absolute paths or correctly relative to the project root
const ROOT_DIR = process.cwd();
const RESPONSES_DIR = path.join(ROOT_DIR, 'data', 'gemini_raw_responses');
const OUTPUT_MAPPING = path.join(ROOT_DIR, 'data', 'resolved_grounding_urls.json');

async function resolveVertexUrls() {
    console.log('🔗 Starting URL Resolution for Grounding Chunks...');
    console.log(`📂 Searching in: ${RESPONSES_DIR}`);
    
    if (!fs.existsSync(RESPONSES_DIR)) {
        console.error(`❌ Error: Directory not found: ${RESPONSES_DIR}`);
        process.exit(1);
    }

    const mapping = {};
    if (fs.existsSync(OUTPUT_MAPPING)) {
        Object.assign(mapping, JSON.parse(fs.readFileSync(OUTPUT_MAPPING, 'utf-8')));
    }

    const files = fs.readdirSync(RESPONSES_DIR).filter(f => f.endsWith('.json'));
    const allUrls = new Set();

    // 1. Collect all unique Vertex AI URLs (P004-P007 for our current analysis)
    files.forEach(file => {
        try {
            const id = file.split('_')[0];
            const num = parseInt(id.replace('P', ''));
            if (num < 4 || num > 7) return; // Only process P004-P007

            const content = JSON.parse(fs.readFileSync(path.join(RESPONSES_DIR, file), 'utf-8'));
            const chunks = content.groundingMetadata?.groundingChunks || [];
            chunks.forEach(chunk => {
                const uri = chunk.web?.uri;
                if (uri && uri.includes('vertexaisearch.cloud.google.com')) {
                    allUrls.add(uri);
                }
            });
        } catch (e) {
            console.warn(`⚠️ Skipping corrupted file: ${file}`);
        }
    });

    console.log(`Found ${allUrls.size} unique Vertex AI URLs to resolve.`);

    const urlList = Array.from(allUrls);
    let resolvedCount = 0;

    // 2. Resolve them (following redirects)
    for (const url of urlList) {
        if (mapping[url] && mapping[url] !== url) continue; // Skip already resolved

        try {
            console.log(`   Resolving [${resolvedCount + 1}/${urlList.length}]: ${url.substring(0, 60)}...`);
            
            const response = await axios.get(url, {
                maxRedirects: 10,
                timeout: 15000,
                headers: {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
            });

            const finalUrl = response.request.res.responseUrl || url;
            mapping[url] = finalUrl;
            resolvedCount++;

            if (resolvedCount % 5 === 0) {
                fs.writeFileSync(OUTPUT_MAPPING, JSON.stringify(mapping, null, 2));
            }

            await new Promise(r => setTimeout(r, 800));

        } catch (error) {
            console.error(`   ❌ Failed to resolve: ${url.substring(0, 60)}... | Error: ${error.message}`);
            mapping[url] = url; 
        }
    }

    fs.writeFileSync(OUTPUT_MAPPING, JSON.stringify(mapping, null, 2));
    console.log(`\n✨ URL Resolution Complete. ${resolvedCount} URLs processed/updated.`);
}

resolveVertexUrls();
