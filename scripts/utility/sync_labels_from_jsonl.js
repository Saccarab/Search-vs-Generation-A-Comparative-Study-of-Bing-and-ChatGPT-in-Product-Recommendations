const fs = require("fs");
const path = require("path");
const ExcelJS = require("exceljs");
const readline = require("readline");

async function loadJsonl(filePath) {
  if (!fs.existsSync(filePath)) return [];
  const results = [];
  const fileStream = fs.createReadStream(filePath);
  const rl = readline.createInterface({ input: fileStream, crlfDelay: Infinity });
  for await (const line of rl) {
    if (!line.trim()) continue;
    try {
      results.push(JSON.parse(line));
    } catch (e) {
      // ignore
    }
  }
  return results;
}

function safeStr(v) {
  if (v === null || v === undefined) return "";
  return String(v).trim();
}

function normalizeUrlKey(u) {
  if (!u) return "";
  try {
    const url = new URL(u);
    url.hash = "";
    // Drop test params if any
    url.searchParams.delete("test_uuid");
    url.searchParams.delete("test_variant");
    return url.toString().toLowerCase().replace(/\/$/, "");
  } catch (e) {
    return u.toLowerCase().replace(/\/$/, "");
  }
}

function sheetHeaderMap(ws) {
  const map = new Map();
  if (!ws) return map;
  const row = ws.getRow(1);
  row.eachCell((cell, colNumber) => {
    const val = safeStr(cell.value).toLowerCase().trim();
    if (val) map.set(val, colNumber);
  });
  return map;
}

function setCell(ws, rowIdx, headerMap, colName, value) {
  const colIdx = headerMap.get(colName.toLowerCase());
  if (colIdx) {
    ws.getRow(rowIdx).getCell(colIdx).value = value;
  }
}

async function main() {
  const xlsxPath = "geo-fresh.xlsx";
  const geminiLog = path.join("data", "llm", "page_labels_gemini.jsonl");
  const gptLog = path.join("data", "llm", "page_labels_gpt.jsonl");

  console.log("Loading audit logs...");
  const logs = [
    ...(await loadJsonl(geminiLog)),
    ...(await loadJsonl(gptLog))
  ].filter(l => l.ok && l.response);

  // Use a map to keep only the latest successful result per URL
  const latestResults = new Map();
  for (const entry of logs) {
    const key = normalizeUrlKey(entry.url);
    if (!key) continue;
    latestResults.set(key, entry);
  }

  console.log(`Found ${latestResults.size} unique labeled URLs in logs.`);

  const wb = new ExcelJS.Workbook();
  await wb.xlsx.readFile(xlsxPath);

  const wsUrls = wb.getWorksheet("urls");
  const wsListicles = wb.getWorksheet("listicles");
  const wsProducts = wb.getWorksheet("listicle_products");

  const hu = sheetHeaderMap(wsUrls);
  const hl = sheetHeaderMap(wsListicles);
  const hp = sheetHeaderMap(wsProducts);

  // 1. Ensure new columns exist in urls
  const newCols = ["has_tables", "has_numbered_lists", "has_bullet_points", "heading_density", "labeled_at", "labeled_by_model"];
  let nextCol = wsUrls.columnCount + 1;
  for (const col of newCols) {
    if (!hu.has(col)) {
      console.log(`Adding column: ${col}`);
      wsUrls.getRow(1).getCell(nextCol).value = col;
      hu.set(col, nextCol);
      nextCol++;
    }
  }

  // 2. Clean up "empty but existing" rows in listicles and products
  // We'll just clear them and rebuild from the latest log data to be safe,
  // since this is a recovery script.
  console.log("Cleaning listicles and products sheets...");
  if (wsListicles) {
    while (wsListicles.rowCount > 1) wsListicles.spliceRows(2, 1);
  }
  if (wsProducts) {
    while (wsProducts.rowCount > 1) wsProducts.spliceRows(2, 1);
  }

  const urlRowMap = new Map();
  if (wsUrls) {
    const urlCol = hu.get("url");
    for (let r = 2; r <= wsUrls.rowCount; r++) {
      const u = safeStr(wsUrls.getRow(r).getCell(urlCol).value);
      const k = normalizeUrlKey(u);
      if (k) urlRowMap.set(k, r);
    }
  }

  console.log("Syncing data to sheets...");
  let syncedUrls = 0;
  let syncedListicles = 0;
  let syncedProducts = 0;

  for (const [key, entry] of latestResults) {
    const rowIdx = urlRowMap.get(key);
    const resp = entry.response;

    // Sync to URLs
    if (rowIdx && resp.urls) {
      for (const [k, v] of Object.entries(resp.urls)) {
        setCell(wsUrls, rowIdx, hu, k, v);
      }
      setCell(wsUrls, rowIdx, hu, "labeled_at", entry.ts);
      setCell(wsUrls, rowIdx, hu, "labeled_by_model", entry.model);
      syncedUrls++;
    }

    // Sync to Listicles
    if (wsListicles && resp.listicles) {
      const newRow = wsListicles.addRow({});
      for (const [k, v] of Object.entries(resp.listicles)) {
        const c = hl.get(k.toLowerCase());
        if (c) newRow.getCell(c).value = v;
      }
      syncedListicles++;
    }

    // Sync to Products
    if (wsProducts && Array.isArray(resp.listicle_products)) {
      for (const item of resp.listicle_products) {
        const newRow = wsProducts.addRow({});
        for (const [k, v] of Object.entries(item)) {
          const c = hp.get(k.toLowerCase());
          if (c) newRow.getCell(c).value = v;
        }
        syncedProducts++;
      }
    }
  }

  console.log(`Sync complete:
  - URLs updated: ${syncedUrls}
  - Listicles added: ${syncedListicles}
  - Products added: ${syncedProducts}`);

  await wb.xlsx.writeFile(xlsxPath);
  console.log(`Saved ${xlsxPath}`);
}

main().catch(console.error);
