import fs from 'fs';
import path from 'path';
import { getJson } from 'serpapi';

// --- CONFIGURATION ---
const API_KEY = 'ecc3e49406d80dd9cdeb95aad55927f74164ef8b83bfbac2548786fb4f56bc16'; // Replace with your actual key
const INPUT_CSV = './data/gemini_fanout_missing_only.csv';
const OUTPUT_DIR = './data/serpapi_results';
const CHECKPOINT_FILE = './data/serpapi_checkpoint.json';

// Ensure output directory exists
if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

async function fetchSerpApiResults() {
    console.log('🚀 Starting SerpApi Collection (Target: Top 20 Organic)...');

    // 1. Load Queries
    const fileContent = fs.readFileSync(INPUT_CSV, 'utf-8');
    const lines = fileContent.split('\n').filter(l => l.trim());
    const queries = lines.slice(1).map(line => {
        const firstComma = line.indexOf(',');
        const runId = line.substring(0, firstComma).trim();
        let query = line.substring(firstComma + 1).trim();
        if (query.startsWith('"') && query.endsWith('"')) {
            query = query.substring(1, query.length - 1);
        }
        return { runId, query };
    });

    // 2. Load Checkpoint
    let processed = new Set();
    if (fs.existsSync(CHECKPOINT_FILE)) {
        processed = new Set(JSON.parse(fs.readFileSync(CHECKPOINT_FILE, 'utf-8')));
    }

    console.log(`Total queries: ${queries.length}. Already processed: ${processed.size}`);

    // 3. Process Loop
    for (const item of queries) {
        const { runId, query } = item;
        const storageKey = `${runId}_${query}`;

        if (processed.has(storageKey)) continue;

        console.log(`\n🔍 Fetching [${runId}]: "${query}"`);

        try {
            let allOrganicResults = [];
            let currentParams = {
                engine: "google",
                q: query,
                location: "United States",
                google_domain: "google.com",
                hl: "en",
                num: 20
            };
            
            let pageCount = 0;
            let lastResponse = null;

            // Keep fetching until we have 20 organic results or hit 3 pages
            while (allOrganicResults.length < 20 && pageCount < 3) {
                console.log(`   ...fetching page ${pageCount + 1} (Organic total: ${allOrganicResults.length})`);
                const response = await getJson({
                    api_key: API_KEY,
                    ...currentParams
                });

                lastResponse = response;
                
                // 1. Collect Organic Results (Primary target)
                const pageResults = response.organic_results || [];
                pageResults.forEach(r => {
                    r.result_type = 'organic';
                    allOrganicResults.push(r);
                });

                // 2. Collect Inline Video Results (Extra data, but NOT in main array)
                const pageVideos = [];
                if (response.inline_videos) {
                    response.inline_videos.forEach(v => {
                        v.result_type = 'video';
                        pageVideos.push(v);
                    });
                }

                // 3. Collect Discussions and Forums (Extra data, but NOT in main array)
                const pageDiscussions = [];
                if (response.discussions_and_forums) {
                    response.discussions_and_forums.forEach(d => {
                        d.result_type = 'discussion';
                        pageDiscussions.push(d);
                    });
                }
                
                console.log(`   Found ${pageResults.length} organic results on this page. Total Organic: ${allOrganicResults.length}`);

                // STOP only when we have 20 ORGANIC results
                if (allOrganicResults.length >= 20) {
                    console.log(`   ✅ Target of 20 Organic results reached.`);
                    break;
                }

                // Check if there is a next page link in the response
                if (response.serpapi_pagination && response.serpapi_pagination.next) {
                    // FIX: Set start to exactly how many organic results we have so far
                    currentParams.start = allOrganicResults.length;
                    pageCount++;
                } else {
                    console.log(`   ℹ️ No more pages available according to Google.`);
                    break; 
                }
            }

            // Save the results
            const finalData = { 
                ...lastResponse,
                organic_results: allOrganicResults // This is now ONLY organic results
            };

            const safeQuery = query.replace(/[^a-z0-9]/gi, '_').substring(0, 50);
            const fileName = `${runId}_${safeQuery}.json`;
            fs.writeFileSync(path.join(OUTPUT_DIR, fileName), JSON.stringify(finalData, null, 2));

            // Update Checkpoint
            processed.add(storageKey);
            fs.writeFileSync(CHECKPOINT_FILE, JSON.stringify(Array.from(processed)));

            // Be nice to the API/Rate limits
            await new Promise(r => setTimeout(r, 1000));

        } catch (error) {
            const errorMsg = error.response?.data?.error || error.message || 'Unknown API Error';
            console.error(`❌ Error fetching "${query}":`, errorMsg);
            
            // If it's a credit or key issue, stop the whole script
            if (errorMsg.includes('credits') || errorMsg.includes('API key') || errorMsg.includes('unauthorized')) {
                console.error('🛑 Stopping: Account issue detected.');
                process.exit(1);
            }
            // Wait longer on other errors
            await new Promise(r => setTimeout(r, 5000));
        }
    }

    console.log('\n✨ All SerpApi requests complete!');
}

fetchSerpApiResults();
