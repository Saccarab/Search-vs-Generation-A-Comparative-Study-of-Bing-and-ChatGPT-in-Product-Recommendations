#!/usr/bin/env node

/**
 * Prepare the 11 unique queries for Gemini testing by combining and deduplicating
 * queries from queries.csv and query2.csv
 */

const fs = require('fs');
const path = require('path');

function loadQueriesFromCSV(filename) {
    const content = fs.readFileSync(filename, 'utf-8');
    const lines = content.split('\n').filter(line => line.trim());

    // Skip header if it exists
    const startIndex = lines[0].toLowerCase().includes('query') ? 1 : 0;

    return lines.slice(startIndex).map(line => {
        // Handle quoted CSV values
        if (line.startsWith('"') && line.endsWith('"')) {
            return line.slice(1, -1);
        }
        return line.trim();
    }).filter(query => query);
}

function deduplicateQueries(queries) {
    // Remove duplicates while preserving order
    const seen = new Set();
    const deduplicated = [];

    for (const query of queries) {
        const normalized = query.toLowerCase().trim();
        if (!seen.has(normalized)) {
            seen.add(normalized);
            deduplicated.push(query);
        }
    }

    return deduplicated;
}

function main() {
    try {
        // Load queries from both files
        const queries1 = loadQueriesFromCSV('queries.csv');
        const queries2 = loadQueriesFromCSV('query2.csv');

        console.log(`Loaded ${queries1.length} queries from queries.csv`);
        console.log(`Loaded ${queries2.length} queries from query2.csv`);

        // Combine and deduplicate
        const allQueries = [...queries1, ...queries2];
        const uniqueQueries = deduplicateQueries(allQueries);

        console.log(`\nCombined queries: ${allQueries.length}`);
        console.log(`Unique queries: ${uniqueQueries.length}`);

        // Create output for geo-gemini.xlsx prompts sheet
        const outputPath = 'data/gemini_11_queries.csv';
        const csvContent = 'query\n' + uniqueQueries.map(q => `"${q}"`).join('\n');

        // Ensure data directory exists
        const dataDir = path.dirname(outputPath);
        if (!fs.existsSync(dataDir)) {
            fs.mkdirSync(dataDir, { recursive: true });
        }

        fs.writeFileSync(outputPath, csvContent);
        console.log(`\n✅ Saved ${uniqueQueries.length} unique queries to: ${outputPath}`);

        // Display the queries
        console.log('\n📋 Your 11 Gemini Test Queries:');
        uniqueQueries.forEach((query, i) => {
            console.log(`${i + 1}. ${query}`);
        });

        // Also create a JSON version for easy programmatic access
        const jsonOutput = {
            queries: uniqueQueries,
            metadata: {
                source_files: ['queries.csv', 'query2.csv'],
                total_raw: allQueries.length,
                total_unique: uniqueQueries.length,
                created_at: new Date().toISOString()
            }
        };

        fs.writeFileSync('data/gemini_11_queries.json', JSON.stringify(jsonOutput, null, 2));
        console.log('✅ Also saved JSON version for API scripts');

    } catch (error) {
        console.error('❌ Error preparing queries:', error.message);
        process.exit(1);
    }
}

if (require.main === module) {
    main();
}