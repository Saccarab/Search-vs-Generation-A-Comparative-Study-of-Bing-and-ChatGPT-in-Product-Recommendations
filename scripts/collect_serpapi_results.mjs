import fs from 'fs';
import path from 'path';
import { getJson } from 'serpapi';

// --- CONFIGURATION ---
const API_KEY = "a2c9e987988d85a2d2995fec78857b83a5be43fdaeab8d69acaeb0bdbf0d6230"
const STATUS_FILE = './serpapi_status_summary.txt';
const MAPPINGS_DIR = './datapass/citation_mappings';
const OUTPUT_DIR = './data/serpapi_google_results';
const CHECKPOINT_FILE = './data/serpapi_google_checkpoint.json';

if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

function loadMissingPersonalQueries() {
    const content = fs.readFileSync(STATUS_FILE, 'utf-8');
    const lines = content.split('\n');
    const missingQueries = [];
    
    // Find the start of the detailed missing queries section
    let startIndex = lines.findIndex(l => l.includes('=== DETAILED MISSING QUERIES ==='));
    if (startIndex === -1) return [];

    // Skip header lines
    for (let i = startIndex + 2; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) continue;

        // Parse fixed-width columns from the status file
        // Format: Run ID (0-7), Account (8-18), Type (19-24), Query (25+)
        const runId = line.substring(0, 8).trim();
        const account = line.substring(8, 19).trim();
        const type = line.substring(19, 25).trim();
        
        if (account === 'personal') {
            // Find the full query from the mapping files since the text file is truncated
            const mappingFile = path.join(MAPPINGS_DIR, `${runId.split('_').slice(0,2).join('_')}_personal_mapping.json`);
            let fullQuery = "";
            
            try {
                const mappingData = JSON.parse(fs.readFileSync(mappingFile, 'utf-8'));
                if (type === 'main') {
                    fullQuery = mappingData.prompt;
                } else {
                    const idx = parseInt(type.replace('Q', '')) - 1;
                    fullQuery = mappingData.metadata.hidden_queries[idx];
                }

                if (fullQuery && fullQuery !== 'n/a') {
                    missingQueries.push({
                        runId: `${runId}_personal_${type}`,
                        query: fullQuery,
                        _meta: {
                            chatgpt_run_id: runId,
                            account_type: 'personal',
                            query_type: type === 'main' ? 'main' : 'hidden_query'
                        }
                    });
                }
            } catch (e) {
                console.error(`Could not find full query for ${runId} ${type} in ${mappingFile}`);
            }
        }
    }
    return missingQueries;
}

async function fetchSerpApiResults() {
    console.log('🚀 Starting SerpApi Collection based on serpapi_status_summary.txt...');
    
    const queries = loadMissingPersonalQueries();
    console.log(`Found ${queries.length} missing personal queries.`);

    let processed = new Set();
    if (fs.existsSync(CHECKPOINT_FILE)) {
        processed = new Set(JSON.parse(fs.readFileSync(CHECKPOINT_FILE, 'utf-8')));
    }

    for (const item of queries) {
        const { runId, query } = item;
        const storageKey = `${runId}::${query}`;

        if (processed.has(storageKey)) continue;

        console.log(`\n🔍 Fetching [${runId}] | Account: personal`);
        console.log(`   Query: "${query}"`);

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
            let allInlineVideos = [];
            let allRelatedQuestions = [];
            let allDiscussions = [];

            while (allOrganicResults.length < 20 && pageCount < 3) {
                const response = await getJson({
                    api_key: API_KEY,
                    ...currentParams
                });

                lastResponse = response;
                (response.organic_results || []).forEach(r => {
                    r.result_type = 'organic';
                    allOrganicResults.push(r);
                });

                if (response.inline_videos) {
                    response.inline_videos.forEach(v => {
                        v.result_type = 'video';
                        allInlineVideos.push(v);
                    });
                }

                if (response.related_questions) {
                    response.related_questions.forEach(q => {
                        q.result_type = 'related_question';
                        q.has_link = !!(q.link || q.displayed_link);
                        allRelatedQuestions.push(q);
                    });
                }

                if (response.discussions_and_forums) {
                    response.discussions_and_forums.forEach(d => {
                        d.result_type = 'discussion';
                        allDiscussions.push(d);
                    });
                }
                
                if (allOrganicResults.length >= 20) break;

                if (response.serpapi_pagination && response.serpapi_pagination.next) {
                    currentParams.start = allOrganicResults.length;
                    pageCount++;
                } else break;
            }

            const finalData = { 
                _query_info: {
                    run_id: runId,
                    query: query,
                    collected_at: new Date().toISOString(),
                    ...item._meta
                },
                _collection_stats: {
                    organic_count: allOrganicResults.length,
                    video_count: allInlineVideos.length,
                    related_questions_count: allRelatedQuestions.length,
                    discussions_count: allDiscussions.length
                },
                organic_results: allOrganicResults,
                inline_videos: allInlineVideos,
                related_questions: allRelatedQuestions,
                discussions_and_forums: allDiscussions,
                search_metadata: lastResponse?.search_metadata,
                search_parameters: lastResponse?.search_parameters
            };

            const safeQuery = query.replace(/[^a-z0-9]/gi, '_').substring(0, 50);
            const fileName = `${runId}_${safeQuery}.json`;
            fs.writeFileSync(path.join(OUTPUT_DIR, fileName), JSON.stringify(finalData, null, 2));

            processed.add(storageKey);
            fs.writeFileSync(CHECKPOINT_FILE, JSON.stringify(Array.from(processed)));

            await new Promise(r => setTimeout(r, 1000));

        } catch (error) {
            console.error(`❌ Error fetching "${query}":`, error.message);
            if (error.message&& error.emssage.includes('credits')) process.exit(1);
            await new Promise(r => setTimeout(r, 5000));
        }
    }
    console.log('\n✨ Collection complete!');
}

fetchSerpApiResults();
