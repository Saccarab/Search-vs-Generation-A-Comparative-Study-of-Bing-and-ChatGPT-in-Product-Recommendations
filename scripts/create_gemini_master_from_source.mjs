import ExcelJS from 'exceljs';
import fs from 'fs';
import path from 'path';

/**
 * Create geo-gemini-master.xlsx based on geo_updated (1).xlsx
 * but with the new Gemini-specific grounding sheets.
 */
async function createGeminiMaster() {
  const sourceFile = 'geo_updated (1).xlsx';
  const targetFile = 'geo-gemini-master.xlsx';

  console.log(`📖 Reading source structure from ${sourceFile}...`);
  
  const sourceWb = new ExcelJS.Workbook();
  await sourceWb.xlsx.readFile(sourceFile);
  
  const targetWb = new ExcelJS.Workbook();

  // 1. Copy existing sheets from geo_updated (1).xlsx
  // We keep the data in 'prompts_updated' but create empty versions of others for the new run
  for (const sheet of sourceWb.worksheets) {
    const newSheet = targetWb.addWorksheet(sheet.name);
    
    // Copy headers and formatting for all sheets
    const headerRow = sheet.getRow(1);
    const newHeader = newSheet.addRow(headerRow.values);
    newHeader.font = { bold: true };
    newHeader.fill = {
      type: 'pattern',
      pattern: 'solid',
      fgColor: { argb: 'FFE6E6FA' }
    };

    // Special case: Copy ALL data for 'prompts_updated'
    if (sheet.name === 'prompts_updated') {
      console.log(`✅ Copying all data for ${sheet.name}`);
      sheet.eachRow((row, rowNumber) => {
        if (rowNumber > 1) {
          newSheet.addRow(row.values);
        }
      });
    } else {
      console.log(`✅ Created empty ${sheet.name} with original headers`);
    }
  }

  // 2. Add Gemini-Specific Grounding Sheets
  console.log('➕ Adding Gemini-specific grounding sheets...');

  const groundingSheets = {
    'gemini_web_search_queries': {
      'run_id': 'Foreign key to runs',
      'query_index': 'Position in Gemini\'s query list',
      'search_query': 'The actual search query Gemini sent to Google'
    },
    'gemini_grounding_chunks': {
      'run_id': 'Foreign key to runs',
      'chunk_index': 'Position in groundingChunks array',
      'title': 'Source page title',
      'uri': 'Source URL',
      'domain': 'Extracted domain',
      'chunk_text': 'The actual text chunk Gemini extracted',
      'is_cited': 'Boolean: does this chunk appear in groundingSupports?'
    },
    'google_serp_results': {
      'serp_query': 'The Gemini webSearchQuery this SERP is for',
      'run_id': 'Foreign key to runs',
      'position': 'SERP position (1-20)',
      'title': 'Result title',
      'url': 'Result URL',
      'domain': 'Extracted domain'
    }
  };

  for (const [name, cols] of Object.entries(groundingSheets)) {
    const ws = targetWb.addWorksheet(name);
    const header = ws.addRow(Object.keys(cols));
    header.font = { bold: true };
    header.fill = {
      type: 'pattern',
      pattern: 'solid',
      fgColor: { argb: 'FFD1E8FF' } // Light blue for Gemini sheets
    };
    ws.addRow(Object.values(cols)).font = { italic: true, size: 10 };
    console.log(`✅ Added Gemini sheet: ${name}`);
  }

  // 3. Update 'urls' sheet with Gemini analysis columns
  const urlsSheet = targetWb.getWorksheet('urls');
  if (urlsSheet) {
    const lastCol = urlsSheet.columnCount;
    const newCols = [
      'gemini_chunk_extracted',
      'gemini_support_cited',
      'gemini_chunk_word_count',
      'gemini_extraction_efficiency'
    ];
    
    const headerRow = urlsSheet.getRow(1);
    newCols.forEach((col, i) => {
      headerRow.getCell(lastCol + i + 1).value = col;
    });
    console.log('✅ Added Gemini analysis columns to "urls" sheet');
  }

  await targetWb.xlsx.writeFile(targetFile);
  console.log(`\n🎯 Created new master file: ${targetFile}`);
}

createGeminiMaster().catch(err => console.error(err));
