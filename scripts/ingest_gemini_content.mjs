import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import axios from 'axios';
import * as cheerio from 'cheerio';
import Bottleneck from 'bottleneck';

/**
 * FETCH URL CONTENT FOR GEMINI GROUNDING ANALYSIS
 * 
 * This script:
 * 1. Scans gemini_raw_responses for unique grounding URLs (P004-P007)
 * 2. Fetches content using Node.js (axios)
 * 3. Extracts text (removing boilerplate)
 * 4. Saves to data/ingest/content/
 * 5. Updates data/ingest/gemini_urls_master.json
 */

const ROOT_DIR = process.cwd();
const RESPONSES_DIR = path.join(ROOT_DIR, 'data', 'gemini_raw_responses');
const RESOLVED_URLS_FILE = path.join(ROOT_DIR, 'data', 'resolved_grounding_urls.json');
const CONTENT_DIR = path.join(ROOT_DIR, 'data', 'ingest', 'content');
const MASTER_JSON = path.join(ROOT_DIR, 'data', 'ingest', 'gemini_urls_master.json');

// Ensure directories exist
if (!fs.existsSync(CONTENT_DIR)) fs.mkdirSync(CONTENT_DIR, { recursive: true });

function shortHash(text) {
    return crypto.createHash("sha256").update(text, "utf8").digest("hex").slice(0, 16);
}

function extractText(html) {
    if (!html) return "";
    const $ = cheerio.load(html);
    $("script, style, noscript, nav, header, footer, aside").remove();
    let text = $("body").text() || "";
    return text.replace(/\s+/g, " ").trim();
}

async function runIngest() {
    console.log('🚀 Starting Gemini URL Ingest & Content Fetching...');

    const resolvedUrls = JSON.parse(fs.readFileSync(RESOLVED_URLS_FILE, 'utf-8'));
    const masterData = fs.existsSync(MASTER_JSON) ? JSON.parse(fs.readFileSync(MASTER_JSON, 'utf-8')) : {};

    const responseFiles = fs.readdirSync(RESPONSES_DIR).filter(f => f.endsWith('.json'));
    const uniqueUrls = new Set();

    // 1. Collect unique resolved URLs from P004-P007
    responseFiles.forEach(file => {
        const pNum = parseInt(file.split('_')[0].replace('P', ''));
        if (pNum >= 4 && pNum <= 7) {
            const content = JSON.parse(fs.readFileSync(path.join(RESPONSES_DIR, file), 'utf-8'));
            const chunks = content.groundingMetadata?.groundingChunks || [];
            chunks.forEach(c => {
                const rawUri = c.web?.uri;
                const resolvedUri = resolvedUrls[rawUri] || rawUri;
                if (resolvedUri && !resolvedUri.includes('vertexaisearch')) {
                    uniqueUrls.add(resolvedUri);
                }
            });
        }
    });

    console.log(`Found ${uniqueUrls.size} unique URLs to process.`);

    const limiter = new Bottleneck({ maxConcurrent: 3, minTime: 500 });
    let fetched = 0;
    let skipped = 0;
    let failed = 0;

    const tasks = Array.from(uniqueUrls).map(url => limiter.schedule(async () => {
        const hash = shortHash(url);
        const contentPath = path.join(CONTENT_DIR, `${hash}.txt`);

        if (fs.existsSync(contentPath) && masterData[url]?.content_path) {
            skipped++;
            return;
        }

        console.log(`   Fetching: ${url.substring(0, 60)}...`);
        try {
            const res = await axios.get(url, { 
                timeout: 15000, 
                headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36' } 
            });
            
            const text = extractText(res.data);
            if (text.length < 200) {
                throw new Error(`Text too short (${text.length} chars)`);
            }

            fs.writeFileSync(contentPath, text);
            
            masterData[url] = {
                url,
                hash,
                content_path: contentPath,
                char_count: text.length,
                fetched_at: new Date().toISOString()
            };
            
            fetched++;
        } catch (e) {
            console.warn(`   ❌ Failed: ${url.substring(0, 40)} | ${e.message}`);
            
            // Record failure so we can retry later or export
            masterData[url] = {
                url,
                hash,
                error: e.message,
                status: 'failed',
                fetched_at: new Date().toISOString()
            };
            
            failed++;
        }
    }));

    await Promise.all(tasks);

    fs.writeFileSync(MASTER_JSON, JSON.stringify(masterData, null, 2));
    
    console.log('\n✨ Ingest Complete!');
    console.log({ total: uniqueUrls.size, fetched, skipped, failed });
}

runIngest().catch(console.error);
