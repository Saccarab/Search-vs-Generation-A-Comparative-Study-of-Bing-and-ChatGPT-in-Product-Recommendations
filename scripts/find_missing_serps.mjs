import fs from 'fs';
import path from 'path';

const RESPONSES_DIR = 'data/gemini_raw_responses';
const SERP_DIR = 'data/serpapi_results';
const OUTPUT_CSV = 'data/gemini_fanout_missing_only.csv';

const responseFiles = fs.readdirSync(RESPONSES_DIR).filter(f => f.endsWith('.json'));
const serpFiles = fs.readdirSync(SERP_DIR).filter(f => f.endsWith('.json'));

const latestFilesMap = new Map();
responseFiles.forEach(file => {
    const parts = file.split('_');
    if (parts.length < 3) return;
    const runId = parts[0] + '_' + parts[1];
    const timestamp = parts[2].replace('.json', '');
    if (!latestFilesMap.has(runId) || timestamp > latestFilesMap.get(runId).timestamp) {
        latestFilesMap.set(runId, { file, timestamp });
    }
});

let missingRows = 'run_id,query\n';
let missingCount = 0;

latestFilesMap.forEach(({ file }, runId) => {
    const pNum = parseInt(runId.substring(1, 5));
    if (pNum < 4 || pNum > 7) return;
    if (runId === 'P004_r1') return;

    const content = JSON.parse(fs.readFileSync(path.join(RESPONSES_DIR, file), 'utf-8'));
    const queries = content.groundingMetadata?.webSearchQueries || [];
    
    queries.forEach(query => {
        const queryWords = query.toLowerCase().replace(/[^a-z0-9\s]/g, '').split(/\s+/).filter(w => w.length > 2);
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

        if (!bestMatch || highestScore < 0.4) {
            missingRows += `${runId},"${query.replace(/"/g, '""')}"\n`;
            missingCount++;
        }
    });
});

fs.writeFileSync(OUTPUT_CSV, missingRows);
console.log(`✅ Created ${OUTPUT_CSV} with ${missingCount} missing queries.`);
