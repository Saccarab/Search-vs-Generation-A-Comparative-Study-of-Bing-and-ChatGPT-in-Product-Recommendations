/**
 * Migrate Enterprise Data to geo-fresh.xlsx
 * 
 * This script:
 * 1. Keeps: prompts_updated, urls, listicles, listicle_products
 * 2. Replaces: citations (from ChatGPT enterprise CSV)
 * 3. Replaces: bing_results (from enterprise Bing data)
 */

const fs = require('fs');
const path = require('path');
const ExcelJS = require('exceljs');
const { parse } = require('csv-parse/sync');

const DATAPASS = 'datapass';
const INPUT_EXCEL = path.join(DATAPASS, 'geo-fresh.xlsx');
const OUTPUT_EXCEL = path.join(DATAPASS, 'geo-enterprise-master.xlsx');
const CHATGPT_CSV = path.join(DATAPASS, 'chatgpt_results_2026-01-27T11-23-04-enterprise.csv');
const BING_CSV = path.join(DATAPASS, 'parital-2-enterprise.csv');
const BING_JSON = path.join(DATAPASS, 'partial_scraping_results-enterprise.json');

async function migrate() {
    console.log('📦 Starting Enterprise Data Migration...\n');

    // Load existing workbook
    const wb = new ExcelJS.Workbook();
    await wb.xlsx.readFile(INPUT_EXCEL);
    console.log('✅ Loaded existing workbook');
    console.log('   Existing sheets:', wb.worksheets.map(s => s.name).join(', '));

    // ========== KEEP THESE SHEETS AS-IS ==========
    const sheetsToKeep = ['prompts_updated', 'urls', 'listicles', 'listicle_products'];
    console.log('\n📌 Keeping sheets:', sheetsToKeep.join(', '));

    // ========== PARSE CHATGPT ENTERPRISE DATA ==========
    console.log('\n🤖 Parsing ChatGPT Enterprise Data...');
    const chatgptRaw = fs.readFileSync(CHATGPT_CSV, 'utf-8');
    const chatgptRows = parse(chatgptRaw, { columns: true, skip_empty_lines: true });
    console.log(`   Found ${chatgptRows.length} ChatGPT response rows`);

    // Build citations from ChatGPT data
    const citations = [];
    chatgptRows.forEach(row => {
        const promptId = row.prompt_id;
        const runNumber = row.run_number;
        
        // Parse sources_cited_json
        let sourcesCited = [];
        try {
            if (row.sources_cited_json && row.sources_cited_json !== '[]') {
                sourcesCited = JSON.parse(row.sources_cited_json);
            }
        } catch (e) {
            // Skip malformed JSON
        }

        // Parse sources_additional_json
        let sourcesAdditional = [];
        try {
            if (row.sources_additional_json && row.sources_additional_json !== '[]') {
                sourcesAdditional = JSON.parse(row.sources_additional_json);
            }
        } catch (e) {}

        // Add cited sources
        sourcesCited.forEach((src, idx) => {
            citations.push({
                prompt_id: promptId,
                run_number: runNumber,
                citation_type: 'cited',
                position: idx + 1,
                url: src.url || src,
                title: src.title || '',
                domain: src.domain || extractDomain(src.url || src)
            });
        });

        // Add additional sources
        sourcesAdditional.forEach((src, idx) => {
            citations.push({
                prompt_id: promptId,
                run_number: runNumber,
                citation_type: 'additional',
                position: idx + 1,
                url: src.url || src,
                title: src.title || '',
                domain: src.domain || extractDomain(src.url || src)
            });
        });
    });
    console.log(`   Extracted ${citations.length} total citations`);

    // ========== UPDATE CITATIONS SHEET ==========
    let citationsSheet = wb.getWorksheet('citations');
    if (citationsSheet) {
        wb.removeWorksheet(citationsSheet.id);
    }
    citationsSheet = wb.addWorksheet('citations');
    
    // Add headers
    citationsSheet.columns = [
        { header: 'prompt_id', key: 'prompt_id', width: 10 },
        { header: 'run_number', key: 'run_number', width: 12 },
        { header: 'citation_type', key: 'citation_type', width: 15 },
        { header: 'position', key: 'position', width: 10 },
        { header: 'url', key: 'url', width: 60 },
        { header: 'title', key: 'title', width: 40 },
        { header: 'domain', key: 'domain', width: 30 }
    ];
    
    // Add rows
    citations.forEach(c => citationsSheet.addRow(c));
    console.log('✅ Updated citations sheet');

    // ========== BUILD RUNS SHEET FROM CHATGPT DATA ==========
    let runsSheet = wb.getWorksheet('runs');
    if (runsSheet) {
        wb.removeWorksheet(runsSheet.id);
    }
    runsSheet = wb.addWorksheet('runs');
    
    runsSheet.columns = [
        { header: 'prompt_id', key: 'prompt_id', width: 10 },
        { header: 'run_number', key: 'run_number', width: 12 },
        { header: 'query', key: 'query', width: 50 },
        { header: 'generated_search_query', key: 'generated_search_query', width: 50 },
        { header: 'web_search_triggered', key: 'web_search_triggered', width: 20 },
        { header: 'items_count', key: 'items_count', width: 12 },
        { header: 'sources_cited_count', key: 'sources_cited_count', width: 18 },
        { header: 'sources_all_count', key: 'sources_all_count', width: 18 },
        { header: 'domains_cited', key: 'domains_cited', width: 40 },
        { header: 'hidden_queries', key: 'hidden_queries', width: 60 }
    ];

    chatgptRows.forEach(row => {
        let hiddenQueries = '';
        try {
            const hq = JSON.parse(row.hidden_queries_json || '[]');
            hiddenQueries = hq.join(' | ');
        } catch (e) {}

        runsSheet.addRow({
            prompt_id: row.prompt_id,
            run_number: row.run_number,
            query: row.query,
            generated_search_query: row.generated_search_query,
            web_search_triggered: row.web_search_triggered,
            items_count: row.items_count,
            sources_cited_count: (row.sources_cited || '').split(',').filter(s => s.trim()).length,
            sources_all_count: (row.sources_all || '').split(',').filter(s => s.trim()).length,
            domains_cited: row.domains_cited,
            hidden_queries: hiddenQueries
        });
    });
    console.log('✅ Updated runs sheet');

    // ========== PARSE BING ENTERPRISE DATA ==========
    console.log('\n🔍 Parsing Bing Enterprise Data...');
    
    // Load CSV (has enrichments like content, tables, schema)
    const bingCsvRaw = fs.readFileSync(BING_CSV, 'utf-8');
    const bingCsvRows = parse(bingCsvRaw, { columns: true, skip_empty_lines: true });
    console.log(`   CSV: ${bingCsvRows.length} results`);
    
    // Load JSON (has additional queries not in CSV)
    const bingJsonRows = JSON.parse(fs.readFileSync(BING_JSON, 'utf-8'));
    console.log(`   JSON: ${bingJsonRows.length} results`);
    
    // Track queries we already have from CSV
    const csvQueries = new Set(bingCsvRows.map(r => r.query));
    
    // Filter JSON to only queries NOT in CSV (avoid duplicates)
    const jsonOnlyRows = bingJsonRows.filter(r => !csvQueries.has(r.query));
    console.log(`   JSON-only (new queries): ${jsonOnlyRows.length} results`);
    console.log(`   Combined total: ${bingCsvRows.length + jsonOnlyRows.length} results`);

    // ========== UPDATE BING_RESULTS SHEET ==========
    let bingSheet = wb.getWorksheet('bing_results');
    if (bingSheet) {
        wb.removeWorksheet(bingSheet.id);
    }
    bingSheet = wb.addWorksheet('bing_results');
    
    bingSheet.columns = [
        { header: 'run_id', key: 'run_id', width: 15 },
        { header: 'query', key: 'query', width: 50 },
        { header: 'position', key: 'position', width: 10 },
        { header: 'page_num', key: 'page_num', width: 10 },
        { header: 'title', key: 'title', width: 40 },
        { header: 'url', key: 'url', width: 60 },
        { header: 'domain', key: 'domain', width: 30 },
        { header: 'snippet', key: 'snippet', width: 60 },
        { header: 'has_content', key: 'has_content', width: 12 },
        { header: 'content_length', key: 'content_length', width: 15 },
        { header: 'page_title', key: 'page_title', width: 40 },
        { header: 'has_table', key: 'has_table', width: 12 },
        { header: 'table_count', key: 'table_count', width: 12 },
        { header: 'has_schema_markup', key: 'has_schema_markup', width: 18 },
        { header: 'published_date', key: 'published_date', width: 15 }
    ];

    // Add CSV rows (have enrichments)
    bingCsvRows.forEach(row => {
        bingSheet.addRow({
            run_id: row.run_id,
            query: row.query,
            position: row.position,
            page_num: row.page_num,
            title: row.title,
            url: row.url,
            domain: row.domain,
            snippet: row.snippet,
            has_content: (row.content && row.content.length > 100) ? 'Yes' : 'No',
            content_length: row.contentLength || (row.content ? row.content.length : 0),
            page_title: row.page_title,
            has_table: row.has_table,
            table_count: row.table_count,
            has_schema_markup: row.has_schema_markup,
            published_date: row.published_date
        });
    });
    
    // Add JSON-only rows (may not have enrichments)
    jsonOnlyRows.forEach(row => {
        bingSheet.addRow({
            run_id: row.run_id,
            query: row.query,
            position: row.position,
            page_num: row.page_num,
            title: row.title,
            url: row.url,
            domain: row.domain,
            snippet: row.snippet,
            has_content: (row.content && row.content.length > 100) ? 'Yes' : 'No',
            content_length: row.content ? row.content.length : 0,
            page_title: '',
            has_table: '',
            table_count: '',
            has_schema_markup: '',
            published_date: ''
        });
    });
    
    const totalBing = bingCsvRows.length + jsonOnlyRows.length;
    console.log('✅ Updated bing_results sheet');

    // ========== SAVE ==========
    await wb.xlsx.writeFile(OUTPUT_EXCEL);
    console.log(`\n✨ Migration complete! Saved to: ${OUTPUT_EXCEL}`);
    
    // Summary
    console.log('\n📊 Summary:');
    console.log(`   - ChatGPT runs: ${chatgptRows.length}`);
    console.log(`   - Citations extracted: ${citations.length}`);
    console.log(`   - Bing results: ${totalBing}`);
}

function extractDomain(url) {
    try {
        const u = new URL(url);
        return u.hostname.replace('www.', '');
    } catch {
        return '';
    }
}

migrate().catch(console.error);
