import fs from 'fs';
import path from 'path';
import { getJson } from 'serpapi';

// --- CONFIGURATION ---
// IMPORTANT: do not hardcode SerpApi keys in source files
const API_KEY = process.env.SERPAPI_API_KEY || "";
if (!API_KEY) {
    throw new Error("Missing SERPAPI_API_KEY env var. Set it before running this script.");
}
const STATUS_FILE = './serpapi_status_summary.txt';
const MAPPINGS_DIR = './datapass/citation_mappings';
const OUTPUT_DIR_DEFAULT = './data/serpapi_google_results';
const CHECKPOINT_FILE_DEFAULT = './data/serpapi_google_checkpoint.json';

// Gemini mode defaults (collect SerpApi results for Gemini fan-out queries)
const GEMINI_RESP_DIR_DEFAULT = './data/gemini_raw_responses';
const OUTPUT_DIR_GEMINI_DEFAULT = './data/serpapi_google_results_gemini';
const CHECKPOINT_FILE_GEMINI_DEFAULT = './data/serpapi_google_checkpoint_gemini.json';

function ensureDir(p) {
    if (!fs.existsSync(p)) fs.mkdirSync(p, { recursive: true });
}

function acquireLock(lockPath) {
    try {
        const fd = fs.openSync(lockPath, 'wx'); // fail if exists
        fs.writeFileSync(fd, `${process.pid}\n${new Date().toISOString()}\n`, { encoding: 'utf-8' });
        fs.closeSync(fd);
        return true;
    } catch (e) {
        return false;
    }
}

function releaseLock(lockPath) {
    try { if (fs.existsSync(lockPath)) fs.unlinkSync(lockPath); } catch { /* ignore */ }
}

function parseArgs() {
    const args = process.argv.slice(2);
    const out = {
        mode: args.includes('--gemini') ? 'gemini' : 'chatgpt', // chatgpt | gemini
        inputCsv: null,
        geminiRespDir: GEMINI_RESP_DIR_DEFAULT,
        outDir: null,
        checkpointFile: null,
    };

    const inputIdx = args.indexOf('--input');
    if (inputIdx !== -1) out.inputCsv = args[inputIdx + 1] || null;

    const respIdx = args.indexOf('--gemini-responses');
    if (respIdx !== -1) out.geminiRespDir = args[respIdx + 1] || out.geminiRespDir;

    const outIdx = args.indexOf('--out');
    if (outIdx !== -1) out.outDir = args[outIdx + 1] || null;

    const ckIdx = args.indexOf('--checkpoint');
    if (ckIdx !== -1) out.checkpointFile = args[ckIdx + 1] || null;

    return out;
}

function parseCsvLine(line) {
    const out = [];
    let cur = '';
    let inQuotes = false;
    for (let i = 0; i < line.length; i++) {
        const ch = line[i];
        if (inQuotes) {
            if (ch === '"') {
                if (line[i + 1] === '"') { cur += '"'; i++; }
                else { inQuotes = false; }
            } else {
                cur += ch;
            }
        } else {
            if (ch === '"') inQuotes = true;
            else if (ch === ',') { out.push(cur); cur = ''; }
            else cur += ch;
        }
    }
    out.push(cur);
    return out.map(s => s.trim());
}

function loadGeminiQueriesFromRawResponses(respDir) {
    /**
     * Reads gemini_raw_responses/*.json, dedupes to the latest file per run_id (Pxxx_rN),
     * and returns a query list derived from groundingMetadata.webSearchQueries.
     *
     * Usage:
     *   node scripts/collect_serpapi_results.mjs --gemini
     *   node scripts/collect_serpapi_results.mjs --gemini --gemini-responses ./data/gemini_raw_responses
     */
    if (!fs.existsSync(respDir)) {
        throw new Error(`Gemini responses directory not found: ${respDir}`);
    }
    const files = fs.readdirSync(respDir).filter(f => f.toLowerCase().endsWith('.json'));
    // filename example: P001_r2_2026-02-02T00-01-14-416Z.json
    const re = /^(P\d{3,4})_r(\d+)_([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{3}Z)\.json$/i;

    const latestByRun = new Map(); // run_id -> {ts, fn, pid, run}
    for (const fn of files) {
        const m = fn.match(re);
        if (!m) continue;
        const pid = m[1].toUpperCase();
        const run = Number(m[2]);
        const ts = m[3];
        const runId = `${pid}_r${run}`;
        const prev = latestByRun.get(runId);
        if (!prev || ts > prev.ts) {
            latestByRun.set(runId, { ts, fn, pid, run });
        }
    }

    const out = [];
    for (const [runId, info] of latestByRun.entries()) {
        const p = path.join(respDir, info.fn);
        let obj;
        try {
            obj = JSON.parse(fs.readFileSync(p, 'utf-8'));
        } catch {
            continue;
        }
        const gm = obj?.groundingMetadata || {};
        const qs = gm?.webSearchQueries;
        const cleaned = [];
        if (Array.isArray(qs)) {
            for (const q of qs) {
                if (typeof q === 'string' && q.trim()) cleaned.push(q.trim());
            }
        }
        // de-dupe within run while keeping order
        const seen = new Set();
        const uniq = [];
        for (const q of cleaned) {
            if (seen.has(q)) continue;
            seen.add(q);
            uniq.push(q);
        }

        for (let i = 0; i < uniq.length; i++) {
            out.push({
                runId: `gemini_${runId}_Q${String(i + 1).padStart(2, '0')}`,
                query: uniq[i],
                _meta: {
                    provider: 'gemini',
                    gemini_run_id: runId,
                    prompt_id: info.pid,
                    run_index: info.run,
                    query_type: 'fanout_query'
                }
            });
        }
    }
    return out;
}

function loadQueriesFromCsv(csvPath) {
    const content = fs.readFileSync(csvPath, 'utf-8');
    const lines = content.split(/\r?\n/).filter(Boolean);
    if (lines.length <= 1) return [];
    const header = parseCsvLine(lines[0]);
    const idxRid = header.indexOf('chatgpt_run_id');
    const idxAcc = header.indexOf('account');
    const idxType = header.indexOf('type');
    const idxQuery = header.indexOf('query');
    if (idxRid === -1 || idxAcc === -1 || idxType === -1 || idxQuery === -1) {
        throw new Error(`CSV header must include chatgpt_run_id,account,type,query. Got: ${header.join(',')}`);
    }
    const out = [];
    for (let i = 1; i < lines.length; i++) {
        const cols = parseCsvLine(lines[i]);
        if (cols.length < header.length) continue;
        const chatgptRunId = cols[idxRid];
        const account = cols[idxAcc];
        const type = cols[idxType];
        const query = cols[idxQuery];
        if (!chatgptRunId || !account || !type || !query) continue;
        out.push({
            runId: `${chatgptRunId}_${account}_${type}`,
            query,
            _meta: {
                chatgpt_run_id: chatgptRunId,
                account_type: account,
                query_type: type === 'main' ? 'main' : 'hidden_query'
            }
        });
    }
    return out;
}

function loadMissingQueries() {
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
        
        // Find the full query from the mapping files since the text file is truncated
        const mappingFile = path.join(MAPPINGS_DIR, `${runId.split('_').slice(0,2).join('_')}_${account}_mapping.json`);
        let fullQuery = "";
        
        try {
            if (!fs.existsSync(mappingFile)) {
                console.error(`Mapping file not found: ${mappingFile}`);
                continue;
            }
            const mappingData = JSON.parse(fs.readFileSync(mappingFile, 'utf-8'));
            if (type === 'main') {
                fullQuery = mappingData.prompt;
            } else {
                const idx = parseInt(type.replace('Q', '')) - 1;
                fullQuery = mappingData.metadata.hidden_queries[idx];
            }

            if (fullQuery && fullQuery !== 'n/a') {
                missingQueries.push({
                    runId: `${runId}_${account}_${type}`,
                    query: fullQuery,
                    _meta: {
                        chatgpt_run_id: runId,
                        account_type: account,
                        query_type: type === 'main' ? 'main' : 'hidden_query'
                    }
                });
            }
        } catch (e) {
            console.error(`Could not find full query for ${runId} ${type} in ${mappingFile}: ${e.message}`);
        }
    }
    return missingQueries;
}

async function fetchSerpApiResults() {
    const cfg = parseArgs();
    const isGemini = cfg.mode === 'gemini';

    const OUTPUT_DIR = cfg.outDir || (isGemini ? OUTPUT_DIR_GEMINI_DEFAULT : OUTPUT_DIR_DEFAULT);
    const CHECKPOINT_FILE = cfg.checkpointFile || (isGemini ? CHECKPOINT_FILE_GEMINI_DEFAULT : CHECKPOINT_FILE_DEFAULT);
    ensureDir(OUTPUT_DIR);
    const LOCK_FILE = `${CHECKPOINT_FILE}.lock`;

    if (isGemini) {
        console.log(`🚀 Starting SerpApi Collection (Gemini mode) from: ${cfg.geminiRespDir}`);
    } else {
        console.log('🚀 Starting SerpApi Collection based on serpapi_status_summary.txt...');
    }
    console.log(`📦 Output directory: ${OUTPUT_DIR}`);
    console.log(`🧾 Checkpoint file: ${CHECKPOINT_FILE}`);
    console.log(`🔒 Lock file: ${LOCK_FILE}`);

    if (!acquireLock(LOCK_FILE)) {
        console.error(`❌ Another collector is likely running (lock exists): ${LOCK_FILE}`);
        console.error('   Stop the other process, or delete the lock file if it is stale.');
        process.exit(1);
    }

    const cleanup = () => releaseLock(LOCK_FILE);
    process.on('exit', cleanup);
    process.on('SIGINT', () => { cleanup(); process.exit(130); });
    process.on('SIGTERM', () => { cleanup(); process.exit(143); });

    const queries = isGemini
        ? loadGeminiQueriesFromRawResponses(cfg.geminiRespDir)
        : (cfg.inputCsv ? loadQueriesFromCsv(cfg.inputCsv) : loadMissingQueries());

    console.log(`Found ${queries.length} ${isGemini ? 'Gemini fan-out queries' : (cfg.inputCsv ? 'queries from input CSV' : 'total missing queries (personal + enterprise)')}.`);

    let processed = new Set();
    if (fs.existsSync(CHECKPOINT_FILE)) {
        processed = new Set(JSON.parse(fs.readFileSync(CHECKPOINT_FILE, 'utf-8')));
    }

    for (const item of queries) {
        const { runId, query } = item;
        const account = item._meta.account_type || 'n/a';
        const provider = item._meta.provider || (isGemini ? 'gemini' : 'chatgpt');
        const storageKey = `${runId}::${query}`;

        if (processed.has(storageKey)) continue;

        console.log(`\n🔍 Fetching [${runId}] | Account: ${account}`);
        console.log(`   Provider: ${provider}`);
        console.log(`   Query: "${query}"`);

        try {
            let allOrganicResults = [];
            let currentParams = {
                engine: "google",
                q: query,
                location: "United States",
                google_domain: "google.com",
                hl: "en",
                // SerpApi typically returns 10 organic results per page; we page up to 3 times.
                num: 10
            };
            
            let pageCount = 0;
            let lastResponse = null;
            let allInlineVideos = [];
            let allRelatedQuestions = [];
            let allDiscussions = [];

            while (allOrganicResults.length < 20 && pageCount < 3) {
                const start = Number(currentParams.start || 0);
                const pageNum = Math.floor(start / 10) + 1;
                const response = await getJson({
                    api_key: API_KEY,
                    ...currentParams
                });
                lastResponse = response;
                (response.organic_results || []).forEach(r => {
                    r.result_type = 'organic';
                    // Preserve per-result page/position so downstream ingest can be correct even if we fetch multiple pages.
                    const pos = Number(r.position || 0);
                    r._page_num = pageNum;
                    r._position_in_page = pos;
                    r._global_position = pos ? (start + pos) : 0;
                    allOrganicResults.push(r);
                });

                if (response.inline_videos) {
                    response.inline_videos.forEach(v => {
                        v.result_type = 'video';
                        v._page_num = pageNum;
                        v._position_in_page = Number(v.position || 0);
                        allInlineVideos.push(v);
                    });
                }

                if (response.related_questions) {
                    response.related_questions.forEach(q => {
                        q.result_type = 'related_question';
                        q.has_link = !!(q.link || q.displayed_link);
                        q._page_num = pageNum;
                        q._position_in_page = Number(q.position || 0);
                        allRelatedQuestions.push(q);
                    });
                }

                if (response.discussions_and_forums) {
                    response.discussions_and_forums.forEach(d => {
                        d.result_type = 'discussion';
                        d._page_num = pageNum;
                        d._position_in_page = Number(d.position || 0);
                        allDiscussions.push(d);
                    });
                }
                
                if (allOrganicResults.length >= 20) break;

                if (response.serpapi_pagination && response.serpapi_pagination.next) {
                    // NOTE: Keep legacy behavior for comparability with earlier ChatGPT collections.
                    // SerpApi usually returns ~10 organic results per page; legacy code advanced "start"
                    // by the number of organic results accumulated so far.
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
            if (error.message && String(error.message).toLowerCase().includes('credit')) process.exit(1);
            await new Promise(r => setTimeout(r, 5000));
        }
    }
    console.log('\n✨ Collection complete!');
}

fetchSerpApiResults();
