#!/usr/bin/env node

/**
 * Create initial Gemini grounding analysis Excel file with proper schema.
 *
 * This creates gemini_grounding_analysis.xlsx with the same structure as geo_updated.xlsx
 * but adapted for Gemini AI Search Filter research.
 */

const ExcelJS = require('exceljs');
const path = require('path');
const fs = require('fs');

async function createSheetWithSchema(workbook, sheetName, columns) {
    const worksheet = workbook.addWorksheet(sheetName);

    // Add column headers with styling
    const headerRow = worksheet.addRow(Object.keys(columns));
    headerRow.font = { bold: true };
    headerRow.fill = {
        type: 'pattern',
        pattern: 'solid',
        fgColor: { argb: 'FFE6E6FA' }
    };

    // Add descriptions as second row
    const descriptionRow = worksheet.addRow(Object.values(columns));
    descriptionRow.font = { italic: true, size: 10 };

    // Set column widths
    worksheet.columns = Object.keys(columns).map((colName, index) => ({
        key: colName,
        width: Math.max(15, colName.length + 2)
    }));

    return worksheet;
}

async function createGeminiAnalysisExcel(outputPath) {
    const workbook = new ExcelJS.Workbook();

    // Sheet 1: gemini_runs
    const runsColumns = {
        'run_id': 'Unique run identifier (e.g., G0001_r1)',
        'query_id': 'Query identifier',
        'run_number': 'Run number (1, 2, 3) for consistency checks',
        'original_prompt': 'Original user query/prompt',
        'web_search_triggered': 'Whether Gemini triggered web search (boolean)',
        'response_timestamp': 'When Gemini API call was made (ISO format)',
        'model_version': 'Gemini model used (e.g., gemini-2.0-flash-exp)',
        'total_web_search_queries': 'Number of search queries Gemini generated',
        'total_grounding_chunks': 'Number of sources retrieved',
        'total_grounding_supports': 'Number of sources actually cited'
    };
    await createSheetWithSchema(workbook, 'gemini_runs', runsColumns);

    // Sheet 2: gemini_web_search_queries
    const searchQueriesColumns = {
        'run_id': 'Foreign key to gemini_runs',
        'query_index': 'Position in Geminis query list (0-indexed)',
        'search_query': 'The actual search query Gemini sent to Google',
        'serp_results_count': 'Number of Google SERP results scraped for this query'
    };
    await createSheetWithSchema(workbook, 'gemini_web_search_queries', searchQueriesColumns);

    // Sheet 3: gemini_grounding_chunks (retrieved sources)
    const chunksColumns = {
        'run_id': 'Foreign key to gemini_runs',
        'chunk_index': 'Position in groundingChunks array',
        'title': 'Source page title',
        'uri': 'Source URL',
        'domain': 'Extracted domain',
        'chunk_text': 'The actual text chunk Gemini extracted',
        'chunk_word_count': 'Word count of extracted chunk',
        'is_cited': 'Boolean: does this chunk appear in groundingSupports?'
    };
    await createSheetWithSchema(workbook, 'gemini_grounding_chunks', chunksColumns);

    // Sheet 4: gemini_grounding_supports (cited sources)
    const supportsColumns = {
        'run_id': 'Foreign key to gemini_runs',
        'support_index': 'Position in groundingSupports array',
        'segment_text': 'The sentence/segment in Geminis response',
        'segment_word_count': 'Word count of the segment',
        'confidence_score': 'Geminis confidence score (0.0-1.0)',
        'grounding_chunk_indices': 'Array of chunk indices this segment cites',
        'citation_count': 'Number of chunks cited by this segment',
        'uri': 'Primary cited URL (from groundingChunkIndices[0])',
        'domain': 'Extracted domain of primary citation'
    };
    await createSheetWithSchema(workbook, 'gemini_grounding_supports', supportsColumns);

    // Sheet 5: google_serp_results (control group)
    const serpColumns = {
        'serp_query': 'The Gemini webSearchQuery this SERP is for',
        'run_id': 'Foreign key to gemini_runs',
        'position': 'SERP position (1-20)',
        'title': 'Result title',
        'url': 'Result URL',
        'display_url': 'Display URL shown on SERP',
        'snippet': 'Result snippet',
        'domain': 'Extracted domain',
        'serp_timestamp': 'When SERP was scraped (ISO format)'
    };
    await createSheetWithSchema(workbook, 'google_serp_results', serpColumns);

    // Sheet 6: gemini_citations (derived analysis)
    const citationsColumns = {
        'run_id': 'Foreign key to gemini_runs',
        'citation_type': 'grounding_support (Gemini equivalent of citations)',
        'url': 'Cited URL',
        'serp_rank': 'Position in Google SERP (null if not in top 20)',
        'chunk_index': 'Which groundingChunk this citation came from',
        'support_index': 'Which groundingSupport cited this',
        'segment_text': 'The response segment that cited this',
        'citation_group_size': 'How many URLs cited in this segment',
        'citation_in_group_rank': 'Position within the citation group'
    };
    await createSheetWithSchema(workbook, 'gemini_citations', citationsColumns);

    // Sheet 7: urls (reuse existing schema with Gemini additions)
    const urlsColumns = {
        'url': 'Normalized URL (primary key)',
        'domain': 'Extracted domain',
        'content_path': 'Path to .txt content file',
        'meta_path': 'Path to .meta.json file',
        'content_word_count': 'Word count of extracted content',
        'has_schema_markup': 'Boolean',
        'fetched_at': 'Timestamp of content fetch',
        'page_title': 'Extracted page title',
        'meta_description': 'Meta description',
        'canonical_url': 'Canonical URL',
        'published_date': 'Publication date',
        'modified_date': 'Last modified date',
        'type': 'Gemini label (listicle, product, blog, etc.)',
        'content_format': 'Gemini label',
        'tone': 'Gemini label',
        'promotional_intensity_score': '0-10 score',
        'gemini_chunk_extracted': 'Boolean: was this URL extracted by Gemini?',
        'gemini_support_cited': 'Boolean: was this URL cited in Gemini response?',
        'gemini_chunk_word_count': 'Words extracted by Gemini from this URL',
        'gemini_extraction_efficiency': '(gemini_chunk_word_count / content_word_count) * 100'
    };
    await createSheetWithSchema(workbook, 'urls', urlsColumns);

    // Add metadata sheet
    const metadataSheet = workbook.addWorksheet('metadata');
    metadataSheet.addRow(['Gemini Grounding Analysis Workbook']);
    metadataSheet.addRow(['Created:', new Date().toISOString()]);
    metadataSheet.addRow(['Purpose:', 'AI Search Filter analysis inspired by Dejan AI research']);
    metadataSheet.addRow(['Schema Version:', '1.0']);

    // Ensure output directory exists
    const outputDir = path.dirname(outputPath);
    if (!fs.existsSync(outputDir)) {
        fs.mkdirSync(outputDir, { recursive: true });
    }

    // Save the workbook
    await workbook.xlsx.writeFile(outputPath);
    console.log(`✅ Created Gemini analysis Excel file: ${outputPath}`);

    // Print schema summary
    console.log(`\n📊 Schema Summary:`);
    console.log(`   ${workbook.worksheets.length} sheets created`);
    console.log(`   Sheets: ${workbook.worksheets.map(ws => ws.name).join(', ')}`);
}

async function main() {
    const args = process.argv.slice(2);

    let outputPath = 'data/gemini_grounding_analysis.xlsx';

    if (args.length > 0 && args[0] === '--output') {
        outputPath = args[1];
    }

    try {
        await createGeminiAnalysisExcel(outputPath);
        console.log('\n🎯 Ready for Gemini AI Search Filter research!');
        console.log('   Next: Collect Gemini responses and populate the sheets');
    } catch (error) {
        console.error('❌ Error creating Excel file:', error.message);
        process.exit(1);
    }
}

// Run if called directly
if (require.main === module) {
    main();
}

module.exports = { createGeminiAnalysisExcel };