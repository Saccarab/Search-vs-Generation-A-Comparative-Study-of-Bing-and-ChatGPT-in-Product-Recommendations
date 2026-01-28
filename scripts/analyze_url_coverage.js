/**
 * Analyze URL Coverage
 * 
 * Compares Gemini groundingChunks URLs against existing enriched URLs
 * to identify what's new vs. already available.
 */

const fs = require('fs');
const path = require('path');
const ExcelJS = require('exceljs');

const RESPONSES_DIR = 'data/gemini_raw_responses';
const RESOLVED_URLS = 'data/resolved_grounding_urls.json';
const ENTERPRISE_EXCEL = 'datapass/geo-enterprise-master.xlsx';

async function analyze() {
    console.log('🔍 Analyzing URL Coverage...\n');

    // Load resolved URLs map
    const resolvedUrls = fs.existsSync(RESOLVED_URLS)
        ? JSON.parse(fs.readFileSync(RESOLVED_URLS, 'utf-8'))
        : {};

    // Collect all Gemini groundingChunks URLs
    const geminiUrls = new Set();
    const files = fs.readdirSync(RESPONSES_DIR).filter(f => f.endsWith('.json'));
    
    // Dedupe to latest file per run
    const latestFiles = {};
    files.forEach(f => {
        const runId = f.split('_').slice(0, 2).join('_');
        if (!latestFiles[runId] || f > latestFiles[runId]) {
            latestFiles[runId] = f;
        }
    });

    Object.values(latestFiles).forEach(file => {
        const content = JSON.parse(fs.readFileSync(path.join(RESPONSES_DIR, file), 'utf-8'));
        const chunks = content.groundingMetadata?.groundingChunks || [];
        
        chunks.forEach(chunk => {
            const rawUri = chunk.web?.uri;
            if (rawUri) {
                const finalUri = resolvedUrls[rawUri] || rawUri;
                geminiUrls.add(finalUri);
            }
        });
    });

    console.log(`📊 Gemini groundingChunks: ${geminiUrls.size} unique URLs`);
    console.log(`   From ${Object.keys(latestFiles).length} runs\n`);

    // Load existing enriched URLs from Excel
    const wb = new ExcelJS.Workbook();
    await wb.xlsx.readFile(ENTERPRISE_EXCEL);
    const urlSheet = wb.getWorksheet('urls');
    
    const existingUrls = new Set();
    const existingUrlData = {};
    
    urlSheet.eachRow((row, rowNum) => {
        if (rowNum === 1) return; // Skip header
        const url = row.getCell(1).value;
        if (url) {
            existingUrls.add(url);
            existingUrlData[url] = {
                hasContent: !!row.getCell(4).value, // content_word_count
                hasDna: !!row.getCell(7).value, // tone
            };
        }
    });

    console.log(`📚 Existing enriched URLs: ${existingUrls.size}`);

    // Compare
    const alreadyEnriched = [];
    const needsFetching = [];
    const domainStats = {};

    geminiUrls.forEach(url => {
        const domain = extractDomain(url);
        domainStats[domain] = (domainStats[domain] || 0) + 1;

        if (existingUrls.has(url)) {
            alreadyEnriched.push(url);
        } else {
            needsFetching.push(url);
        }
    });

    console.log(`\n✅ Already enriched: ${alreadyEnriched.length} (${(alreadyEnriched.length/geminiUrls.size*100).toFixed(1)}%)`);
    console.log(`❌ Needs fetching: ${needsFetching.length} (${(needsFetching.length/geminiUrls.size*100).toFixed(1)}%)`);

    // Domain breakdown for new URLs
    console.log('\n📈 Top domains in Gemini citations:');
    const sortedDomains = Object.entries(domainStats)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 15);
    
    sortedDomains.forEach(([domain, count]) => {
        console.log(`   ${domain}: ${count}`);
    });

    // Export URLs that need fetching
    if (needsFetching.length > 0) {
        const outputPath = 'data/gemini_urls_to_fetch.json';
        fs.writeFileSync(outputPath, JSON.stringify(needsFetching, null, 2));
        console.log(`\n📝 Exported ${needsFetching.length} URLs to: ${outputPath}`);
    }

    // Also show overlap with ChatGPT citations
    const citationsSheet = wb.getWorksheet('citations');
    const chatgptCitedUrls = new Set();
    
    citationsSheet.eachRow((row, rowNum) => {
        if (rowNum === 1) return;
        const url = row.getCell(5).value; // url column
        if (url) chatgptCitedUrls.add(url);
    });

    const geminiChatgptOverlap = [...geminiUrls].filter(u => chatgptCitedUrls.has(u));
    console.log(`\n🔗 Gemini-ChatGPT URL Overlap: ${geminiChatgptOverlap.length} URLs`);
    console.log(`   (${(geminiChatgptOverlap.length/geminiUrls.size*100).toFixed(1)}% of Gemini citations also in ChatGPT)`);
}

function extractDomain(url) {
    try {
        const u = new URL(url);
        return u.hostname.replace('www.', '');
    } catch {
        return 'unknown';
    }
}

analyze().catch(console.error);
