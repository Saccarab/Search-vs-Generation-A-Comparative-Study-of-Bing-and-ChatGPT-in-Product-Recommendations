import ExcelJS from 'exceljs';
import fs from 'fs';
import path from 'path';
import { parse } from 'csv-parse/sync';

const ROOT_DIR = process.cwd();
const DATAPASS_DIR = path.join(ROOT_DIR, 'datapass');
const PERSONAL_DIR = path.join(DATAPASS_DIR, 'personal_data_run');
const OUTPUT_EXCEL = path.join(DATAPASS_DIR, 'geo-enterprise-master.xlsx');

// Personal data files
const PERSONAL_CHATGPT_CSV = path.join(PERSONAL_DIR, 'chatgpt_results_2026-01-28T02-25-34.csv');
const PERSONAL_BING_PART1 = path.join(PERSONAL_DIR, 'bing_partial_2026-perso-part1-01-28T09-17-18.csv');
const PERSONAL_BING_PART2 = path.join(PERSONAL_DIR, 'bing_results_2026-perso-part2-01-28T19-24-52.csv');

function extractDomain(url) {
    try {
        const u = new URL(url);
        return u.hostname.replace('www.', '');
    } catch {
        return '';
    }
}

function normalizeUrl(url) {
    if (!url) return "";
    let cleanedUrl = url.toLowerCase().trim();
    cleanedUrl = cleanedUrl.replace(/^https?:\/\/(www\.)?/i, '');
    const urlParts = cleanedUrl.split('?');
    cleanedUrl = urlParts[0];
    if (cleanedUrl.endsWith('/')) {
        cleanedUrl = cleanedUrl.slice(0, -1);
    }
    return cleanedUrl;
}

async function migrate() {
    console.log('📦 Starting Personal Data Migration...\n');

    // Load existing workbook
    const wb = new ExcelJS.Workbook();
    await wb.xlsx.readFile(OUTPUT_EXCEL);
    console.log('✅ Loaded existing workbook');
    console.log(`   Existing sheets: ${wb.worksheets.map(ws => ws.name).join(', ')}\n`);

    // ========== PARSE PERSONAL CHATGPT DATA ==========
    console.log('🤖 Parsing Personal ChatGPT Data...');
    const chatgptRaw = fs.readFileSync(PERSONAL_CHATGPT_CSV, 'utf-8');
    const chatgptRows = parse(chatgptRaw, { columns: true, skip_empty_lines: true });
    console.log(`   Found ${chatgptRows.length} ChatGPT response rows`);

    // Get existing runs sheet
    let runsSheet = wb.getWorksheet('runs');
    
    // Get existing columns from header row
    const runsColumns = runsSheet.getRow(1).values.slice(1); // Skip empty first
    console.log(`   Existing columns: ${runsColumns.join(', ')}`);
    
    // Build a set of existing run_ids by constructing them from prompt_id + run_number
    const existingRunIds = new Set();
    const promptIdCol = runsColumns.indexOf('prompt_id') + 1;
    const runNumCol = runsColumns.indexOf('run_number') + 1;
    
    runsSheet.eachRow((row, rowNum) => {
        if (rowNum > 1) {
            const pid = row.getCell(promptIdCol).value;
            const rn = row.getCell(runNumCol).value;
            const acct = row.getCell(runsColumns.indexOf('account_type') + 1).value || 'enterprise';
            const rid = acct === 'personal' ? `${pid}_r${rn}_personal` : `${pid}_r${rn}`;
            existingRunIds.add(rid);
        }
    });
    console.log(`   Existing runs: ${existingRunIds.size}`);

    // Add run_id column if it doesn't exist
    let runIdColIdx = runsColumns.indexOf('run_id') + 1;
    if (runIdColIdx === 0) {
        // Insert run_id as first column
        runsSheet.spliceColumns(1, 0, ['run_id']);
        runIdColIdx = 1;
        // Fill run_id for existing rows
        runsSheet.eachRow((row, rowNum) => {
            if (rowNum > 1) {
                const pid = row.getCell(promptIdCol + 1).value;
                const rn = row.getCell(runNumCol + 1).value;
                const acct = row.getCell(runsColumns.indexOf('account_type') + 2).value || 'enterprise';
                row.getCell(1).value = acct === 'personal' ? `${pid}_r${rn}_personal` : `${pid}_r${rn}`;
            }
        });
        console.log('   Added run_id column');
    }

    // Check if account_type column exists, if not add it
    let accountTypeColIdx = runsColumns.indexOf('account_type') + 1;
    if (accountTypeColIdx === 0) {
        // Find the last column and add account_type
        const newColIndex = runsSheet.getRow(1).actualCellCount + 1;
        runsSheet.getRow(1).getCell(newColIndex).value = 'account_type';
        accountTypeColIdx = newColIndex;
        
        // Mark existing rows as 'enterprise'
        runsSheet.eachRow((row, rowNum) => {
            if (rowNum > 1) {
                row.getCell(accountTypeColIdx).value = 'enterprise';
            }
        });
        console.log('   Added account_type column, marked existing as "enterprise"');
    }

    // Add personal runs (with _personal suffix to distinguish)
    let addedRuns = 0;
    
    // Get fresh column list after potential modifications
    const freshColumns = runsSheet.getRow(1).values.slice(1);
    
    chatgptRows.forEach(row => {
        const baseRunId = `${row.prompt_id}_r${row.run_number}`;
        const personalRunId = `${baseRunId}_personal`;
        
        if (!existingRunIds.has(personalRunId)) {
            let hiddenQueries = '';
            try {
                const hq = JSON.parse(row.hidden_queries_json || '[]');
                hiddenQueries = hq.map(q => typeof q === 'string' ? q : q.query).join(' | ');
            } catch (e) {}

            // Build row array matching existing column order
            const newRow = freshColumns.map(col => {
                switch(col) {
                    case 'run_id': return personalRunId;
                    case 'prompt_id': return row.prompt_id;
                    case 'run_number': return row.run_number;
                    case 'query': return row.query;
                    case 'generated_search_query': return row.generated_search_query;
                    case 'web_search_triggered': return row.web_search_triggered;
                    case 'items_count': return row.items_count;
                    case 'sources_cited_count': return (row.sources_cited || '').split(',').filter(s => s.trim()).length;
                    case 'sources_all_count': return (row.sources_all || '').split(',').filter(s => s.trim()).length;
                    case 'domains_cited': return row.domains_cited;
                    case 'hidden_queries': return hiddenQueries;
                    case 'account_type': return 'personal';
                    default: return null;
                }
            });
            runsSheet.addRow(newRow);
            addedRuns++;
        }
    });
    console.log(`   Added ${addedRuns} personal runs`);

    // ========== ADD PERSONAL CITATIONS ==========
    console.log('\n📎 Adding Personal Citations...');
    let citationsSheet = wb.getWorksheet('citations');
    
    // Check/add account_type column
    const citColumns = citationsSheet.getRow(1).values.slice(1);
    if (!citColumns.includes('account_type')) {
        const newColIndex = citColumns.length + 1;
        citationsSheet.getRow(1).getCell(newColIndex).value = 'account_type';
        citationsSheet.eachRow((row, rowNum) => {
            if (rowNum > 1) row.getCell(newColIndex).value = 'enterprise';
        });
    }

    let addedCitations = 0;
    chatgptRows.forEach(row => {
        const personalRunId = `${row.prompt_id}_r${row.run_number}_personal`;
        const sourcesCited = JSON.parse(row.sources_cited_json || '[]');
        const sourcesAdditional = JSON.parse(row.sources_additional_json || '[]');

        sourcesCited.forEach((src, index) => {
            citationsSheet.addRow({
                run_id: personalRunId,
                prompt_id: row.prompt_id,
                run_number: row.run_number,
                citation_type: 'cited',
                position: index + 1,
                url: src.url,
                url_normalized: normalizeUrl(src.url),
                title: src.title,
                domain: extractDomain(src.url),
                account_type: 'personal'
            });
            addedCitations++;
        });
        sourcesAdditional.forEach((src, index) => {
            citationsSheet.addRow({
                run_id: personalRunId,
                prompt_id: row.prompt_id,
                run_number: row.run_number,
                citation_type: 'additional',
                position: index + 1,
                url: src.url,
                url_normalized: normalizeUrl(src.url),
                title: src.title,
                domain: extractDomain(src.url),
                account_type: 'personal'
            });
            addedCitations++;
        });
    });
    console.log(`   Added ${addedCitations} personal citations`);

    // ========== ADD PERSONAL BING RESULTS ==========
    console.log('\n🔍 Parsing Personal Bing Data...');
    const bingPart1Raw = fs.readFileSync(PERSONAL_BING_PART1, 'utf-8');
    const bingPart1 = parse(bingPart1Raw, { columns: true, skip_empty_lines: true });
    console.log(`   Part 1: ${bingPart1.length} results`);

    const bingPart2Raw = fs.readFileSync(PERSONAL_BING_PART2, 'utf-8');
    const bingPart2 = parse(bingPart2Raw, { columns: true, skip_empty_lines: true });
    console.log(`   Part 2: ${bingPart2.length} results`);

    const allPersonalBing = [...bingPart1, ...bingPart2];
    console.log(`   Combined: ${allPersonalBing.length} results`);

    let bingSheet = wb.getWorksheet('bing_results');
    
    // Check/add account_type column
    const bingColumns = bingSheet.getRow(1).values.slice(1);
    if (!bingColumns.includes('account_type')) {
        const newColIndex = bingColumns.length + 1;
        bingSheet.getRow(1).getCell(newColIndex).value = 'account_type';
        bingSheet.eachRow((row, rowNum) => {
            if (rowNum > 1) row.getCell(newColIndex).value = 'enterprise';
        });
    }

    let addedBing = 0;
    allPersonalBing.forEach(row => {
        // Add _personal suffix to run_id
        const personalRunId = row.run_id ? `${row.run_id}_personal` : '';
        
        bingSheet.addRow({
            run_id: personalRunId,
            query: row.query,
            position: parseInt(row.position),
            page_num: parseInt(row.page_num),
            title: row.title,
            url: row.url,
            url_normalized: normalizeUrl(row.url),
            domain: extractDomain(row.url),
            snippet: row.snippet,
            has_content: (row.content && row.content.length > 100) ? 'Yes' : 'No',
            content_length: row.contentLength || (row.content ? row.content.length : 0),
            page_title: row.page_title || '',
            has_table: row.has_table || 'No',
            table_count: row.table_count || 0,
            has_schema_markup: row.has_schema_markup || 'No',
            published_date: row.published_date || '',
            account_type: 'personal'
        });
        addedBing++;
    });
    console.log(`   Added ${addedBing} personal Bing results`);

    // ========== SAVE ==========
    await wb.xlsx.writeFile(OUTPUT_EXCEL);
    console.log(`\n✨ Migration complete! Updated: ${OUTPUT_EXCEL}`);

    // Summary
    console.log('\n📊 Summary:');
    console.log(`   - Personal ChatGPT runs added: ${addedRuns}`);
    console.log(`   - Personal citations added: ${addedCitations}`);
    console.log(`   - Personal Bing results added: ${addedBing}`);
}

migrate().catch(console.error);
