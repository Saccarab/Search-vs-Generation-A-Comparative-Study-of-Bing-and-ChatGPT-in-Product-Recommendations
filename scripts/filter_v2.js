const fs = require('fs');
const path = require('path');

function filterV2() {
    try {
        const checkpointPath = 'c:/Users/kayaa/Downloads/partial-2google_results_checkpoint_2026-01-26T02-23-27.csv';
        if (!fs.existsSync(checkpointPath)) {
            console.error('Checkpoint not found');
            return;
        }
        const checkpointContent = fs.readFileSync(checkpointPath, 'utf-8');
        const lines = checkpointContent.split('\n');
        const processedQueries = new Set();

        for (let i = 1; i < lines.length; i++) {
            const line = lines[i].trim();
            if (!line) continue;
            let query = '';
            if (line.startsWith('"')) {
                const secondQuoteIndex = line.indexOf('"', 1);
                query = line.substring(1, secondQuoteIndex);
            } else {
                query = line.split(',')[0];
            }
            if (query) processedQueries.add(query.trim());
        }

        const currentListPath = './data/gemini_fanout_remaining.csv';
        const currentListContent = fs.readFileSync(currentListPath, 'utf-8');
        const currentLines = currentListContent.split('\n');
        const header = currentLines[0];
        const remainingLines = [];

        for (let i = 1; i < currentLines.length; i++) {
            const line = currentLines[i].trim();
            if (!line) continue;
            const firstComma = line.indexOf(',');
            let query = line.substring(firstComma + 1).trim();
            if (query.startsWith('"') && query.endsWith('"')) {
                query = query.substring(1, query.length - 1);
            }
            if (!processedQueries.has(query)) {
                remainingLines.push(line);
            }
        }

        const outputPath = './data/gemini_fanout_remaining_v2.csv';
        fs.writeFileSync(outputPath, header + '\n' + remainingLines.join('\n'));
        console.log(`Found ${processedQueries.size} more processed queries.`);
        console.log(`✅ Created ${outputPath} with ${remainingLines.length} remaining queries.`);
    } catch (err) {
        console.error(err);
    }
}

filterV2();
