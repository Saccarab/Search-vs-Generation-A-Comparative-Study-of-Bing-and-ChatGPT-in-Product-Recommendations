import ExcelJS from 'exceljs';
import fs from 'fs';
import path from 'path';

/**
 * Export the actual prompts from Column 3 of geo-gemini-master.xlsx
 */
async function exportCorrectPrompts() {
  const sourceFile = 'geo-gemini-master.xlsx';
  const outputFile = './data/gemini_all_prompts.json';

  console.log(`📖 Reading correct prompts from ${sourceFile}...`);
  
  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.readFile(sourceFile);
  
  const sheet = workbook.getWorksheet('prompts_updated');
  if (!sheet) {
    console.error('❌ Could not find "prompts_updated" sheet');
    return;
  }

  const queries = [];
  const promptIds = [];

  sheet.eachRow((row, rowNumber) => {
    if (rowNumber > 1) { // Skip header
      const id = row.getCell(1).value;
      const text = row.getCell(3).value; // COLUMN 3 is the actual prompt text
      
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
  
  console.log(`✅ Exported ${queries.length} CORRECT prompts to ${outputFile}`);
}

exportCorrectPrompts().catch(err => console.error(err));
