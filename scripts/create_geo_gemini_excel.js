#!/usr/bin/env node

/**
 * Create geo-gemini.xlsx - Master workbook for Gemini AI Search Filter research.
 *
 * Based on geo_updated.xlsx structure but adapted for Gemini grounding analysis.
 * Maintains similar structure for easy comparison with existing Bing/ChatGPT data.
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

async function createGeoGeminiExcel(outputPath) {
    const workbook = new ExcelJS.Workbook();

    // ===== EXISTING SHEETS (KEPT SIMILAR) =====

    // Sheet 1: prompts (KEPT EXACTLY THE SAME as requested)
    const promptsColumns = {
        'prompt_id': 'Unique prompt identifier (e.g., P0001)',
        'prompt_text': 'The actual prompt text used',
        'category': 'Prompt category/topic',
        'created_date': 'When prompt was created',
        'notes': 'Any additional notes about the prompt'
    };
    await createSheetWithSchema(workbook, 'prompts', promptsColumns);

    // Sheet 2: runs (adapted for Gemini)
    const runsColumns = {
        'run_id': 'Unique run identifier (e.g., G0001_r1)',
        'prompt_id': 'Foreign key to prompts (e.g., P0001)',
        'run_number': 'Run number (1, 2, 3) for consistency checks',
        'original_prompt': 'Original user query/prompt',
        'generated_search_query': 'Gemini\'s rewritten query (if different)',
        'web_search_triggered': 'Whether Gemini triggered web search (boolean)',
        'response_timestamp': 'When Gemini API call was made (ISO format)',
        'model_version': 'Gemini model used (e.g., gemini-2.0-flash-exp)',
        'total_web_search_queries': 'Number of search queries Gemini generated',
        'total_grounding_chunks': 'Number of sources retrieved',
        'total_grounding_supports': 'Number of sources actually cited'
    };
    await createSheetWithSchema(workbook, 'runs', runsColumns);

    // Sheet 3: citations (adapted for Gemini grounding supports)
    const citationsColumns = {
        'run_id': 'Foreign key to runs',
        'url': 'Cited URL',
        'citation_type': 'grounding_support (Gemini equivalent of citations)',
        'support_index': 'Position in groundingSupports array',
        'segment_text': 'The sentence/segment in Gemini\'s response',
        'confidence_score': 'Gemini\'s confidence score (0.0-1.0)',
        'grounding_chunk_indices': 'Array of chunk indices this segment cites',
        'citation_group_size': 'Number of chunks cited by this segment',
        'citation_in_group_rank': 'Position within the citation group'
    };
    await createSheetWithSchema(workbook, 'citations', citationsColumns);

    // Sheet 4: bing_results (KEPT - for comparison with existing data)
    const bingResultsColumns = {
        'run_id': 'Foreign key to runs',
        'position': 'SERP position (1-30)',
        'page_num': 'Bing results page number',
        'title': 'Result title',
        'url': 'Result URL',
        'display_url': 'Display URL shown on SERP',
        'snippet': 'Result snippet',
        'domain': 'Extracted domain'
    };
    await createSheetWithSchema(workbook, 'bing_results', bingResultsColumns);

    // ===== NEW SHEETS (GEMINI-SPECIFIC) =====

    // Sheet 5: gemini_web_search_queries (new)
    const searchQueriesColumns = {
        'run_id': 'Foreign key to runs',
        'query_index': 'Position in Gemini\'s query list (0-indexed)',
        'search_query': 'The actual search query Gemini sent to Google',
        'serp_results_count': 'Number of Google SERP results scraped for this query'
    };
    await createSheetWithSchema(workbook, 'gemini_web_search_queries', searchQueriesColumns);

    // Sheet 6: gemini_grounding_chunks (new - like bing_results but for retrieved sources)
    const chunksColumns = {
        'run_id': 'Foreign key to runs',
        'chunk_index': 'Position in groundingChunks array',
        'title': 'Source page title',
        'uri': 'Source URL',
        'domain': 'Extracted domain',
        'chunk_text': 'The actual text chunk Gemini extracted',
        'chunk_word_count': 'Word count of extracted chunk',
        'is_cited': 'Boolean: does this chunk appear in groundingSupports?'
    };
    await createSheetWithSchema(workbook, 'gemini_grounding_chunks', chunksColumns);

    // Sheet 7: google_serp_results (new - control group baseline)
    const serpColumns = {
        'serp_query': 'The Gemini webSearchQuery this SERP is for',
        'run_id': 'Foreign key to runs',
        'position': 'SERP position (1-20)',
        'title': 'Result title',
        'url': 'Result URL',
        'display_url': 'Display URL shown on SERP',
        'snippet': 'Result snippet',
        'domain': 'Extracted domain',
        'serp_timestamp': 'When SERP was scraped (ISO format)'
    };
    await createSheetWithSchema(workbook, 'google_serp_results', serpColumns);

    // ===== SHARED SHEETS (EXTENDED) =====

    // Sheet 8: urls (extended with Gemini fields)
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

    // Sheet 9: listicles (KEPT - for LLM labeling)
    const listiclesColumns = {
        'url': 'Foreign key to urls',
        'listicle_title': 'Title of the listicle',
        'items_count': 'Number of products listed',
        'freshness_cue_strength': '0-10 score'
    };
    await createSheetWithSchema(workbook, 'listicles', listiclesColumns);

    // Sheet 10: listicle_products (KEPT - for LLM labeling)
    const productsColumns = {
        'listicle_url': 'Foreign key to listicles/urls',
        'position_in_listicle': 'Position in the list',
        'product_name': 'Product name',
        'product_url': 'Link to product (if available)'
    };
    await createSheetWithSchema(workbook, 'listicle_products', productsColumns);

    // ===== ANALYSIS SHEETS =====

    // Sheet 11: gemini_citations_analysis (derived analysis)
    const citationsAnalysisColumns = {
        'run_id': 'Foreign key to runs',
        'url': 'Cited URL',
        'gemini_citation_rank': 'Position in Gemini citation list',
        'google_serp_rank': 'Position in Google SERP (null if not in top 20)',
        'bing_serp_rank': 'Position in Bing SERP (null if not in top 30)',
        'domain': 'Extracted domain',
        'citation_type': 'inline/support/cited/additional',
        'segment_text': 'The response segment that cited this',
        'confidence_score': 'Gemini confidence score',
        'survival_analysis': 'Retrieved by Gemini AND cited vs just retrieved'
    };
    await createSheetWithSchema(workbook, 'gemini_citations_analysis', citationsAnalysisColumns);

    // Add metadata sheet
    const metadataSheet = workbook.addWorksheet('metadata');
    metadataSheet.addRow(['Geo-Gemini Master Workbook']);
    metadataSheet.addRow(['Created:', new Date().toISOString()]);
    metadataSheet.addRow(['Purpose:', 'Combined Bing/ChatGPT vs Gemini AI Search Filter analysis']);
    metadataSheet.addRow(['Schema Version:', '1.0']);
    metadataSheet.addRow(['Compatible with:', 'geo_updated.xlsx structure']);
    metadataSheet.addRow(['Key Changes:', 'Added Gemini grounding sheets, kept prompts identical']);

    // Ensure output directory exists
    const outputDir = path.dirname(outputPath);
    if (!fs.existsSync(outputDir)) {
        fs.mkdirSync(outputDir, { recursive: true });
    }

    // Save the workbook
    await workbook.xlsx.writeFile(outputPath);
    console.log(`✅ Created Geo-Gemini master Excel file: ${outputPath}`);

    // Print schema summary
    console.log(`\n📊 Schema Summary:`);
    console.log(`   ${workbook.worksheets.length} sheets created`);
    console.log(`   Sheets: ${workbook.worksheets.map(ws => ws.name).join(', ')}`);

    console.log(`\n🔄 Structure Comparison:`);
    console.log(`   ✅ Kept: prompts (identical)`);
    console.log(`   ✅ Kept: runs, citations, bing_results, urls, listicles, listicle_products`);
    console.log(`   ➕ Added: gemini_web_search_queries, gemini_grounding_chunks, google_serp_results`);
    console.log(`   📊 Added: gemini_citations_analysis (derived metrics)`);
}

async function main() {
    const outputPath = 'geo-gemini.xlsx';

    try {
        await createGeoGeminiExcel(outputPath);
        console.log('\n🎯 Ready for comparative Bing/ChatGPT vs Gemini research!');
        console.log('   Next: Start with your 11 prompts and collect Gemini responses');
    } catch (error) {
        console.error('❌ Error creating Excel file:', error.message);
        process.exit(1);
    }
}

// Run if called directly
if (require.main === module) {
    main();
}

module.exports = { createGeoGeminiExcel };