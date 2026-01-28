const fs = require('fs');
const path = require('path');

async function filterQueries() {
    try {
        // 1. Read the checkpoint file to see what's already done
        const checkpointPath = 'c:/Users/kayaa/Downloads/google_results_checkpoint_2026-01-26T02-10-14.csv';
        if (!fs.existsSync(checkpointPath)) {
            console.error('Checkpoint file not found at:', checkpointPath);
            return;
        }
        
        const checkpointContent = fs.readFileSync(checkpointPath, 'utf-8');
        const lines = checkpointContent.split('\n');
        const processedQueries = new Set();

        // Skip header, extract unique queries
        for (let i = 1; i < lines.length; i++) {
            const line = lines[i].trim();
            if (!line) continue;
            
            // Simple parsing: query is the first column, usually quoted
            let query = '';
            if (line.startsWith('"')) {
                const secondQuoteIndex = line.indexOf('"', 1);
                query = line.substring(1, secondQuoteIndex);
            } else {
                query = line.split(',')[0];
            }
            
            if (query) {
                processedQueries.add(query.trim());
            }
        }

        console.log(`Found ${processedQueries.size} processed queries in checkpoint.`);

        // 2. Read the full fanout list
        const fullListPath = './data/gemini_fanout_queries.csv';
        const fullListContent = fs.readFileSync(fullListPath, 'utf-8');
        const fullLines = fullListContent.split('\n');
        const header = fullLines[0];
        const remainingLines = [];

        for (let i = 1; i < fullLines.length; i++) {
            const line = fullLines[i].trim();
            if (!line) continue;
            
            // Extract query from full list line (format: run_id,"query")
            const firstComma = line.indexOf(',');
            let query = line.substring(firstComma + 1).trim();
            if (query.startsWith('"') && query.endsWith('"')) {
                query = query.substring(1, query.length - 1);
            }
            
            if (!processedQueries.has(query)) {
                remainingLines.push(line);
            }
        }

        // 3. Write the new subset
        const outputPath = './data/gemini_fanout_remaining.csv';
        fs.writeFileSync(outputPath, header + '\n' + remainingLines.join('\n'));

        console.log(`✅ Created ${outputPath} with ${remainingLines.length} remaining queries.`);
    } catch (err) {
        console.error('Error:', err);
    }
}

filterQueries();
