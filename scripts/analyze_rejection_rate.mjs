import fs from 'fs';
import path from 'path';

const RESPONSES_DIR = path.join(process.cwd(), 'data', 'gemini_raw_responses');

function analyzeRejectionRate() {
    const files = fs.readdirSync(RESPONSES_DIR).filter(f => f.endsWith('.json'));
    
    // Group by Run ID to get latest
    const latestFiles = {};
    files.forEach(file => {
        const parts = file.split('_');
        if (parts.length < 2) return;
        const runId = `${parts[0]}_${parts[1]}`;
        
        // REMOVED FILTER: Now processing ALL files
        
        if (!latestFiles[runId] || file > latestFiles[runId]) {
            latestFiles[runId] = file;
        }
    });

    console.log('Analyzing Rejection Rate for ALL RUNS (Latest)...\n');
    console.log('Run ID | Chunks | Supports | Rejected | Rejection Rate');
    console.log('-------|--------|----------|----------|---------------');

    let totalChunks = 0;
    let totalSupports = 0;
    let totalRejected = 0;
    let runCount = 0;

    Object.keys(latestFiles).sort().forEach(runId => {
        const file = latestFiles[runId];
        const content = JSON.parse(fs.readFileSync(path.join(RESPONSES_DIR, file), 'utf-8'));
        
        const chunks = content.groundingMetadata?.groundingChunks || [];
        const supports = content.groundingMetadata?.groundingSupports || [];

        // Get unique URLs
        const chunkUrls = new Set(chunks.map(c => c.web?.uri).filter(Boolean));
        
        // Get unique supported URLs (supports reference chunk indices)
        const supportUrls = new Set();
        supports.forEach(support => {
            (support.groundingChunkIndices || []).forEach(index => {
                if (chunks[index]?.web?.uri) {
                    supportUrls.add(chunks[index].web.uri);
                }
            });
        });

        const chunkCount = chunkUrls.size;
        const supportCount = supportUrls.size;
        const rejectedCount = chunkCount - supportCount;
        const rejectionRate = chunkCount > 0 ? ((rejectedCount / chunkCount) * 100).toFixed(1) : '0.0';

        totalChunks += chunkCount;
        totalSupports += supportCount;
        totalRejected += rejectedCount;
        runCount++;

        console.log(`${runId} | ${chunkCount.toString().padStart(6)} | ${supportCount.toString().padStart(8)} | ${rejectedCount.toString().padStart(8)} | ${rejectionRate.padStart(13)}%`);
    });

    console.log('-------|--------|----------|----------|---------------');
    const avgRejection = totalChunks > 0 ? ((totalRejected / totalChunks) * 100).toFixed(1) : '0.0';
    console.log(`TOTAL  | ${totalChunks.toString().padStart(6)} | ${totalSupports.toString().padStart(8)} | ${totalRejected.toString().padStart(8)} | ${avgRejection.padStart(13)}%`);
}

analyzeRejectionRate();
