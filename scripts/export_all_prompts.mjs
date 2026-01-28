import ExcelJS from 'exceljs';
import fs from 'fs';
import path from 'path';

/**
 * Export all prompts from geo-gemini.xlsx to a JSON file for the batch collector
 */
async function exportPromptsForBatch() {
  const sourceFile = 'geo-gemini.xlsx';
  const outputFile = './data/gemini_all_prompts.json';

  console.log(`📖 Reading prompts from ${sourceFile}...`);
  
  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.readFile(sourceFile);
  
  const sheet = workbook.getWorksheet('prompts');
  if (!sheet) {
    console.error('❌ Could not find "prompts" sheet');
    return;
  }

  const queries = [];
  const promptIds = [];

  sheet.eachRow((row, rowNumber) => {
    if (rowNumber > 1) { // Skip header
      const id = row.getCell(1).value;
      const text = row.getCell(2).value;
      
      if (text) {
        queries.push(text);
        promptIds.push(id);
      }
    }
  });

  const data = {
    queries,
    promptIds,
    metadata: {
      source: sourceFile,
      total: queries.length,
      created_at: new Date().toISOString()
    }
  };

  if (!fs.existsSync('./data')) fs.mkdirSync('./data');
  fs.writeFileSync(outputFile, JSON.stringify(data, null, 2));
  
  console.log(`✅ Exported ${queries.length} prompts to ${outputFile}`);
}

exportPromptsForBatch().catch(err => console.error(err));
