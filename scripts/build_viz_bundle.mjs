import fs from 'fs';
import path from 'path';

// --- CONFIGURATION ---
const ROOT_DIR = process.cwd();
const RESPONSES_DIR = path.join(ROOT_DIR, 'data', 'gemini_raw_responses');
const SERP_DIR = path.join(ROOT_DIR, 'data', 'serpapi_google_results_gemini');
const PROMPTS_FILE = path.join(ROOT_DIR, 'data', 'gemini_all_prompts.json');
const RESOLVED_URLS_FILE = path.join(ROOT_DIR, 'data', 'resolved_grounding_urls.json');
const ENRICHED_DATA_FILES = [
    path.join(ROOT_DIR, 'datapass', 'page_labels_combined_v2.5.jsonl'),
    path.join(ROOT_DIR, 'datapass', 'page_labels_gemini_v2.5.jsonl'),
    path.join(ROOT_DIR, 'datapass', 'page_labels_control_gpt5_mini.jsonl') // Add the new GPT-5 mini control data
];
const OUTPUT_FILE = path.join(ROOT_DIR, 'tools', 'GeminiVizApp', 'data', 'master_bundle.json');

function normalizeUrlKey(rawUrl) {
    if (!rawUrl) return "";
    let url = rawUrl.trim();
    if (!url.includes("://")) url = `https://${url}`;
    try {
        const p = new URL(url);
        let host = (p.hostname || "").toLowerCase();
        if (host.startsWith("www.")) host = host.slice(4);
        let pathname = p.pathname || "/";
        if (pathname.length > 1 && pathname.endsWith("/")) pathname = pathname.slice(0, -1);
        const dropExact = new Set(["gclid", "fbclid", "msclkid", "yclid", "mc_cid", "mc_eid", "igshid"]);
        const kept = [];
        for (const [k, v] of p.searchParams.entries()) {
            const lk = k.toLowerCase();
            if (lk.startsWith("utm_") || dropExact.has(lk)) continue;
            kept.push([k, v]);
        }
        const q = new URLSearchParams(kept).toString();
        return `${host}${pathname}${q ? `?${q}` : ""}`;
    } catch {
        return rawUrl.toLowerCase();
    }
}

function normalizeQuery(q) {
    return String(q || '')
        .toLowerCase()
        .replace(/\s+/g, ' ')
        .trim();
}

function dedupeByLink(items, linkField = 'link') {
    if (!Array.isArray(items)) return [];
    const seen = new Set();
    const out = [];
    for (const item of items) {
        const link = (item && item[linkField]) ? String(item[linkField]).trim() : '';
        if (!link) continue;
        const k = link.toLowerCase();
        if (seen.has(k)) continue;
        seen.add(k);
        out.push(item);
    }
    return out;
}

async function buildMasterBundle() {
    console.log('📦 Building Master Data Bundle for the Viz App...');

    const bundle = {
        resolvedUrls: {},
        enrichedData: {}, // key: normalizedUrl -> DNA
        prompts: {},
        runs: []
    };

    // 1. Load Resolved URLs
    if (fs.existsSync(RESOLVED_URLS_FILE)) {
        bundle.resolvedUrls = JSON.parse(fs.readFileSync(RESOLVED_URLS_FILE, 'utf-8'));
    }

    // 1.5 Load Enriched Data (Content DNA)
    console.log('🧬 Loading Enriched Data (Content DNA)...');
    for (const file of ENRICHED_DATA_FILES) {
        if (!fs.existsSync(file)) continue;
        const lines = fs.readFileSync(file, 'utf-8').split('\n');
        for (const line of lines) {
            if (!line.trim()) continue;
            try {
                const d = JSON.parse(line);
                if (d.url && (d.ok || d.response)) {
                    const norm = normalizeUrlKey(d.url);
                    // If multiple labels exist, the last one wins (usually the more specific Gemini one)
                    bundle.enrichedData[norm] = d.response || d;
                }
            } catch (e) {}
        }
    }
    console.log(`   ✅ Loaded DNA for ${Object.keys(bundle.enrichedData).length} unique URLs`);

    // 2. Load Prompts
    if (fs.existsSync(PROMPTS_FILE)) {
        const promptsData = JSON.parse(fs.readFileSync(PROMPTS_FILE, 'utf-8'));
        promptsData.queries.forEach((q, i) => {
            bundle.prompts[promptsData.promptIds[i]] = q;
        });
    }

    // 3. Load all SERP files and index them by gemini_run_id + query
    const responseFiles = fs.readdirSync(RESPONSES_DIR).filter(f => f.endsWith('.json'));
    const serpFiles = fs.existsSync(SERP_DIR) ? fs.readdirSync(SERP_DIR).filter(f => f.endsWith('.json')) : [];
    const serpIndex = new Map(); // key: `${gemini_run_id}||${normalizeQuery(query)}`
    for (const serpFile of serpFiles) {
        try {
            const serpContent = JSON.parse(fs.readFileSync(path.join(SERP_DIR, serpFile), 'utf-8'));
            const qi = serpContent?._query_info || {};
            const geminiRunId = qi.gemini_run_id;
            const query = qi.query;
            if (!geminiRunId || !query) continue;
            const key = `${geminiRunId}||${normalizeQuery(query)}`;

            // Deduplicate each section in-place, preserving original order and rank fields.
            serpContent.organic_results = dedupeByLink(serpContent.organic_results, 'link');
            serpContent.inline_videos = dedupeByLink(serpContent.inline_videos, 'link');
            serpContent.related_questions = dedupeByLink(serpContent.related_questions, 'link');
            serpContent.discussions_and_forums = dedupeByLink(serpContent.discussions_and_forums, 'link');

            // Keep latest collected_at if duplicates exist for same run+query.
            const collectedAt = String(qi.collected_at || '');
            const prev = serpIndex.get(key);
            if (!prev || collectedAt > prev.collectedAt) {
                serpIndex.set(key, { collectedAt, serpContent, serpFile });
            }
        } catch (e) {
            // skip bad SERP file
        }
    }
    
    // Sort files to keep the LATEST one for each runId
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

    console.log(`🔍 Found ${serpFiles.length} SERP files in ${SERP_DIR}`);
    console.log(`🧭 SERP index keys: ${serpIndex.size}`);

    for (const [runId, { file }] of latestFilesMap.entries()) {
        try {
            const content = JSON.parse(fs.readFileSync(path.join(RESPONSES_DIR, file), 'utf-8'));
            const parts = file.split('_');
            const promptId = parts[0];
            const runNum = parts[1]; // e.g., "r1", "r2"

            const runData = {
                runId,
                promptText: bundle.prompts[promptId] || 'Unknown Prompt',
                geminiResponse: content.content?.parts[0]?.text || '',
                webSearchQueries: (content.groundingMetadata?.webSearchQueries || []).filter(q => normalizeQuery(q).length > 0),
                groundingChunks: (content.groundingMetadata?.groundingChunks || []).map(chunk => {
                    // Resolve the URI at build time
                    const rawUri = chunk.web?.uri || '';
                    const resolvedUri = bundle.resolvedUrls[rawUri] || rawUri;
                    return {
                        ...chunk,
                        web: {
                            ...chunk.web,
                            resolvedUri: resolvedUri // Add resolved URI explicitly
                        }
                    };
                }),
                groundingSupports: content.groundingMetadata?.groundingSupports || [],
                serps: {} // Map query -> results
            };

            // Replace Vertex URLs in the geminiResponse text at build time
            runData.geminiResponse = runData.geminiResponse.replace(/\[(.*?)\]\((.*?)\)/g, (match, title, url) => {
                const resolvedUrl = bundle.resolvedUrls[url] || url;
                return `[${title}](${resolvedUrl})`;
            });

            // Embed SERP results directly into the bundle
            for (const query of runData.webSearchQueries) {
                const key = `${runId}||${normalizeQuery(query)}`;
                const hit = serpIndex.get(key);
                if (!hit) {
                    console.warn(`   ❌ Missing SERP for [${runId}]: "${query}"`);
                    continue;
                }
                const serpContent = hit.serpContent || {};
                const merged = [
                    ...(serpContent.organic_results || []),
                    ...(serpContent.inline_videos || []),
                    ...(serpContent.related_questions || []),
                    ...(serpContent.discussions_and_forums || []),
                ];
                // Dedupe across *all* result types for this query, preserving first-seen order.
                runData.serps[query] = dedupeByLink(merged, 'link');
                console.log(`   ✅ Matched SERP for [${runId}]: "${query.substring(0,30)}..." -> ${hit.serpFile}`);
            }

            bundle.runs.push(runData);
        } catch (e) {
            console.warn(`⚠️ Skipping ${file}: ${e.message}`);
        }
    }

    // Sort runs
    bundle.runs.sort((a, b) => a.runId.localeCompare(b.runId));

    // 4. Calculate Rank Distribution & Drift
    console.log('📊 Calculating Rank Distribution & Drift...');
    const rankCounts = {}; // rank -> count
    const serpRankCounts = {}; // rank -> count (how many times this rank was available)
    let totalCitationsWithRank = 0;
    let totalSerpResults = 0;

    bundle.runs.forEach(run => {
        const runChunks = run.groundingChunks || [];
        
        // Track SERP availability per query
        Object.values(run.serps || {}).forEach(results => {
            results.forEach((r, idx) => {
                const rank = idx + 1;
                if (rank <= 30) {
                    serpRankCounts[rank] = (serpRankCounts[rank] || 0) + 1;
                    totalSerpResults++;
                }
            });
        });

        // Track Citations (using the best rank found across all queries in this run)
        const allSerpUrlsInRun = {}; 
        Object.values(run.serps || {}).forEach(results => {
            results.forEach((r, idx) => {
                const norm = normalizeUrlKey(r.link);
                if (!(norm in allSerpUrlsInRun) || (idx + 1) < allSerpUrlsInRun[norm]) {
                    allSerpUrlsInRun[norm] = idx + 1;
                }
            });
        });

        runChunks.forEach(chunk => {
            const finalUri = chunk.web?.resolvedUri || chunk.web?.uri || '';
            const norm = normalizeUrlKey(finalUri);
            const rank = allSerpUrlsInRun[norm];
            if (rank && rank <= 30) {
                rankCounts[rank] = (rankCounts[rank] || 0) + 1;
                totalCitationsWithRank++;
            }
        });
    });

    bundle.rankDistribution = [];
    for (let r = 1; r <= 30; r++) {
        const citedCount = rankCounts[r] || 0;
        const serpCount = serpRankCounts[r] || 0;
        
        const citedPct = totalCitationsWithRank > 0 ? (citedCount / totalCitationsWithRank * 100) : 0;
        const serpPct = totalSerpResults > 0 ? (serpCount / totalSerpResults * 100) : 0;

        bundle.rankDistribution.push({
            rank: r,
            count: citedCount,
            serpCount: serpCount,
            citedPercentage: citedPct.toFixed(1),
            serpPercentage: serpPct.toFixed(1),
            drift: (citedPct - serpPct).toFixed(1)
        });
    }

    const outputDir = path.dirname(OUTPUT_FILE);
    if (!fs.existsSync(outputDir)) fs.mkdirSync(outputDir, { recursive: true });

    // 1. Save as raw JSON for API/reference
    fs.writeFileSync(OUTPUT_FILE, JSON.stringify(bundle));
    
    // 2. Save as a JS file that attaches to window for "zero-load" logic
    const jsOutputFile = OUTPUT_FILE.replace('.json', '.js');
    fs.writeFileSync(jsOutputFile, `window.EMBEDDED_BUNDLE = ${JSON.stringify(bundle)};`);

    console.log(`✅ Success! Bundle created at ${OUTPUT_FILE}`);
    console.log(`✅ JS Bundle created at ${jsOutputFile}`);
    console.log(`📊 Total Runs Bundled: ${bundle.runs.length}`);
}

buildMasterBundle();
