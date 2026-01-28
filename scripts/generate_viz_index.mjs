import fs from 'fs';
import path from 'path';

const RESPONSES_DIR = './data/gemini_raw_responses';
const OUTPUT_FILE = './tools/GeminiVizApp/data/index.json';

function generateIndex() {
    console.log('📂 Generating index for Gemini Visualization App...');
    
    if (!fs.existsSync(RESPONSES_DIR)) {
        console.error('❌ Responses directory not found!');
        return;
    }

    const files = fs.readdirSync(RESPONSES_DIR).filter(f => f.endsWith('.json'));
    const index = [];

    files.forEach(file => {
        const parts = file.split('_');
        if (parts.length < 2) return;

        const runId = `${parts[0]}_${parts[1]}`; // e.g., P001_r1
        index.push({
            runId,
            filename: file
        });
    });

    // Sort by Run ID
    index.sort((a, b) => a.runId.localeCompare(b.runId));

    const outputDir = path.dirname(OUTPUT_FILE);
    if (!fs.existsSync(outputDir)) {
        fs.mkdirSync(outputDir, { recursive: true });
    }

    fs.writeFileSync(OUTPUT_FILE, JSON.stringify(index, null, 2));
    console.log(`✅ Index generated with ${index.length} runs.`);
    console.log(`📍 Saved to: ${OUTPUT_FILE}`);
}

generateIndex();
