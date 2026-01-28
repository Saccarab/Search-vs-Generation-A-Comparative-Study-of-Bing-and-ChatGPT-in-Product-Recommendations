import fs from 'fs';
import path from 'path';

// --- CONFIGURATION ---
const ROOT_DIR = process.cwd();
const RESPONSES_DIR = path.join(ROOT_DIR, 'data', 'gemini_raw_responses');
const SERP_DIR = path.join(ROOT_DIR, 'data', 'serpapi_results');
const PROMPTS_FILE = path.join(ROOT_DIR, 'data', 'gemini_all_prompts.json');
const RESOLVED_URLS_FILE = path.join(ROOT_DIR, 'data', 'resolved_grounding_urls.json');
const OUTPUT_FILE = path.join(ROOT_DIR, 'tools', 'GeminiVizApp', 'data', 'master_bundle.json');

async function buildMasterBundle() {
    console.log('📦 Building Master Data Bundle for the Viz App...');

    const bundle = {
        resolvedUrls: {},
        prompts: {},
        runs: []
    };

    // 1. Load Resolved URLs
    if (fs.existsSync(RESOLVED_URLS_FILE)) {
        bundle.resolvedUrls = JSON.parse(fs.readFileSync(RESOLVED_URLS_FILE, 'utf-8'));
    }

    // 2. Load Prompts
    if (fs.existsSync(PROMPTS_FILE)) {
        const promptsData = JSON.parse(fs.readFileSync(PROMPTS_FILE, 'utf-8'));
        promptsData.queries.forEach((q, i) => {
            bundle.prompts[promptsData.promptIds[i]] = q;
        });
    }

    // 3. Load All Runs and their associated SERP data
    const responseFiles = fs.readdirSync(RESPONSES_DIR).filter(f => f.endsWith('.json'));
    const serpFiles = fs.readdirSync(SERP_DIR).filter(f => f.endsWith('.json'));
    
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

    for (const [runId, { file }] of latestFilesMap.entries()) {
        try {
            const content = JSON.parse(fs.readFileSync(path.join(RESPONSES_DIR, file), 'utf-8'));
            const parts = file.split('_');
            const promptId = parts[0];
            const runNum = parts[1]; // e.g., "r1", "r2"

            // FILTER: Only include runs between P004 and P007
            const promptNum = parseInt(promptId.replace('P', ''));
            if (promptNum < 4 || promptNum > 7) continue;

            // EXCLUDE: P004_r1 as requested
            if (runId === 'P004_r1') continue;

            const runData = {
                runId,
                promptText: bundle.prompts[promptId] || 'Unknown Prompt',
                geminiResponse: content.content?.parts[0]?.text || '',
                webSearchQueries: content.groundingMetadata?.webSearchQueries || [],
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
                serps: {} // Map query -> results
            };

            // Replace Vertex URLs in the geminiResponse text at build time
            runData.geminiResponse = runData.geminiResponse.replace(/\[(.*?)\]\((.*?)\)/g, (match, title, url) => {
                const resolvedUrl = bundle.resolvedUrls[url] || url;
                return `[${title}](${resolvedUrl})`;
            });

            // Embed SERP results directly into the bundle
            for (const query of runData.webSearchQueries) {
                const queryWords = query.toLowerCase().replace(/[^a-z0-9\s]/g, '').split(/\s+/).filter(w => w.length > 2);
                
                // Find SERP file with a fuzzy word-match
                let bestMatch = null;
                let highestScore = 0;

                for (const serpFile of serpFiles) {
                    const fLower = serpFile.toLowerCase();
                    if (!fLower.startsWith(runId.toLowerCase())) continue;
                    
                    const matchCount = queryWords.filter(word => fLower.includes(word)).length;
                    const score = matchCount / queryWords.length;

                    if (score > highestScore) {
                        highestScore = score;
                        bestMatch = serpFile;
                    }
                }
                
                if (bestMatch && highestScore >= 0.4) {
                    const serpContent = JSON.parse(fs.readFileSync(path.join(SERP_DIR, bestMatch), 'utf-8'));
                    // Use organic_results which now includes our merged videos/discussions
                    runData.serps[query] = serpContent.organic_results || [];
                    console.log(`   ✅ Matched SERP for [${runId}]: "${query.substring(0,30)}..." -> ${bestMatch} (Score: ${highestScore.toFixed(2)})`);
                } else {
                    console.warn(`   ❌ Missing SERP for [${runId}]: "${query}"`);
                }
            }

            bundle.runs.push(runData);
        } catch (e) {
            console.warn(`⚠️ Skipping ${file}: ${e.message}`);
        }
    }

    // Sort runs
    bundle.runs.sort((a, b) => a.runId.localeCompare(b.runId));

    const outputDir = path.dirname(OUTPUT_FILE);
    if (!fs.existsSync(outputDir)) fs.mkdirSync(outputDir, { recursive: true });

    fs.writeFileSync(OUTPUT_FILE, JSON.stringify(bundle));
    console.log(`✅ Success! Bundle created at ${OUTPUT_FILE}`);
    console.log(`📊 Total Runs Bundled: ${bundle.runs.length}`);
}

buildMasterBundle();
