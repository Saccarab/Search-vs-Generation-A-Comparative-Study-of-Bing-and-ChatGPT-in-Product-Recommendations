import ExcelJS from 'exceljs';
import fs from 'fs';

/**
 * Sync Prompts from geo-fresh.xlsx to geo-gemini.xlsx
 */
async function syncPrompts() {
  const sourceFile = 'geo-fresh.xlsx';
  const targetFile = 'geo-gemini.xlsx';

  console.log(`📖 Reading prompts from ${sourceFile}...`);
  
  const sourceWb = new ExcelJS.Workbook();
  await sourceWb.xlsx.readFile(sourceFile);
  
  // Your original sheet is named 'prompts_updated' based on our previous check
  const sourceSheet = sourceWb.getWorksheet('prompts_updated');
  if (!sourceSheet) {
    console.error('❌ Could not find "prompts_updated" sheet in geo-fresh.xlsx');
    return;
  }

  const targetWb = new ExcelJS.Workbook();
  await targetWb.xlsx.readFile(targetFile);
  const targetSheet = targetWb.getWorksheet('prompts');

  let count = 0;
  sourceSheet.eachRow((row, rowNumber) => {
    if (rowNumber > 1) { // Skip header
      // Map columns: id, text, category, date, notes
      const promptData = [
        row.getCell(1).value, // prompt_id
        row.getCell(2).value, // prompt_text
        row.getCell(3).value, // category
        row.getCell(4).value, // created_date
        row.getCell(5).value  // notes
      ];
      
      // Only add if there's actual prompt text
      if (promptData[1]) {
        targetSheet.addRow(promptData);
        count++;
      }
    }
  });

  await targetWb.xlsx.writeFile(targetFile);
  console.log(`✅ Successfully synced ${count} prompts to ${targetFile}`);
}

syncPrompts().catch(err => console.error(err));
