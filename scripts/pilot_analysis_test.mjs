import fs from 'fs';
import path from 'path';

const RESPONSES_DIR = './data/gemini_raw_responses';
const SERP_DIR = './data/serpapi_results';
const OUTPUT_FILE = './data/pilot_test_results.json';

async function runPilotTest() {
    console.log('🧪 Starting Pilot Test Analysis (P001 - P006)...');

    const results = [];
    const responseFiles = fs.readdirSync(RESPONSES_DIR).filter(f => f.endsWith('.json'));

    // Filter for P001 to P006
    const pilotResponses = responseFiles.filter(f => {
        const id = f.split('_')[0];
        const num = parseInt(id.replace('P', ''));
        return num >= 1 && num <= 6;
    });

    console.log(`Found ${pilotResponses.length} Gemini responses for P001-P006.`);

    // Normalize Domain function
    const getDomain = (url) => {
        try {
            const u = new URL(url);
            return u.hostname.replace('www.', '').toLowerCase();
        } catch (e) {
            return url.toLowerCase();
        }
    };

    for (const file of pilotResponses) {
        const content = JSON.parse(fs.readFileSync(path.join(RESPONSES_DIR, file), 'utf-8'));
        const parts = file.split('_');
        const runId = `${parts[0]}_${parts[1]}`; // e.g., P001_r1
        
        const webQueries = content.groundingMetadata?.webSearchQueries || [];
        const groundingChunks = content.groundingMetadata?.groundingChunks || [];
        
        const runAnalysis = {
            runId,
            totalChunks: groundingChunks.length,
            queries: []
        };

        for (const query of webQueries) {
            const safeQuery = query.replace(/[^a-z0-9]/gi, '_').substring(0, 50);
            const serpFile = fs.readdirSync(SERP_DIR).find(f => f.startsWith(runId) && f.includes(safeQuery));
            
            const queryData = {
                query,
                serpFound: !!serpFile,
                survivalCount: 0,
                survivingRanks: []
            };

            if (serpFile) {
                const serpData = JSON.parse(fs.readFileSync(path.join(SERP_DIR, serpFile), 'utf-8'));
                const organicResults = serpData.organic_results || [];
                
                // Match by DOMAIN instead of full URL
                groundingChunks.forEach(chunk => {
                    const chunkTitle = chunk.web?.title || ''; // e.g. "meetjamie.ai"
                    const chunkUrl = chunk.web?.uri || '';
                    
                    const match = organicResults.find(r => {
                        const serpDomain = getDomain(r.link);
                        // Check if chunk title matches serp domain OR chunk uri domain matches serp domain
                        return serpDomain === chunkTitle.toLowerCase() || serpDomain === getDomain(chunkUrl);
                    });

                    if (match) {
                        queryData.survivalCount++;
                        queryData.survivingRanks.push(match.position);
                    }
                });
            }
            runAnalysis.queries.push(queryData);
        }
        results.push(runAnalysis);
    }

    fs.writeFileSync(OUTPUT_FILE, JSON.stringify(results, null, 2));
    
    console.log('\n📊 PILOT SUMMARY (P001 - P006):');
    let totalSurvival = 0;
    let totalPossible = 0;
    let runsWithMatches = 0;

    results.forEach(r => {
        const runSurvival = r.queries.reduce((sum, q) => sum + q.survivalCount, 0);
        totalSurvival += runSurvival;
        totalPossible += r.totalChunks;
        if (runSurvival > 0) runsWithMatches++;
        console.log(`[${r.runId}] Chunks: ${r.totalChunks} | Survived from SERP: ${runSurvival}`);
    });

    console.log(`\n✨ Overall Stats:`);
    console.log(`- Total Grounding Chunks: ${totalPossible}`);
    console.log(`- Total Survived from Top 20: ${totalSurvival}`);
    console.log(`- Overall Survival Rate: ${((totalSurvival / totalPossible) * 100).toFixed(2)}%`);
    console.log(`- Runs with at least one match: ${runsWithMatches} / ${results.length}`);
}

runPilotTest();
