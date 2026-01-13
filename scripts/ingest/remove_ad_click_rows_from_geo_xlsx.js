/**
 * Remove ad-click rows from geo_updated.xlsx.
 *
 * Deletes:
 * - `bing_results` rows where URL/domain looks like ad click (doubleclick/googleadservices/bing.com/aclick)
 * - Corresponding `urls` rows if they are no longer referenced by any remaining `bing_results` or any `citations`.
 *
 * Run:
 *   node scripts/ingest/remove_ad_click_rows_from_geo_xlsx.js --xlsx geo_updated.xlsx
 */

/* eslint-disable no-console */
const ExcelJS = require("exceljs");

function parseArgs(argv) {
  const out = { xlsx: "geo_updated.xlsx", write: true };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--xlsx") out.xlsx = argv[++i];
    else if (a === "--no-write") out.write = false;
  }
  return out;
}

function safeStr(v) {
  if (v === null || v === undefined) return "";
  const s = String(v).trim();
  return s.toLowerCase() === "nan" ? "" : s;
}

function headerMap(ws) {
  const m = new Map();
  ws.getRow(1).eachCell((cell, col) => {
    const k = safeStr(cell.value);
    if (k) m.set(k, col);
  });
  return m;
}

function isAdClickUrl(urlOrDomain) {
  const s = safeStr(urlOrDomain).toLowerCase();
  if (!s) return false;
  if (s.includes("doubleclick.net")) return true;
  if (s.includes("googleadservices.com")) return true;
  if (s.includes("googlesyndication.com")) return true;
  if (s.includes("adservice.google.com")) return true;
  if (s.includes("bing.com/aclick") || s.includes("bing.com/clk") || s.includes("bing.com/sclk")) return true;
  if (s.includes("doubleclick.net/searchads")) return true;
  return false;
}

function deleteRowsDescending(ws, rows) {
  const sorted = Array.from(new Set(rows)).sort((a, b) => b - a);
  for (const r of sorted) {
    ws.spliceRows(r, 1);
  }
}

async function main() {
  const args = parseArgs(process.argv);
  const wb = new ExcelJS.Workbook();
  await wb.xlsx.readFile(args.xlsx);

  const wsB = wb.getWorksheet("bing_results");
  const wsU = wb.getWorksheet("urls");
  const wsC = wb.getWorksheet("citations");
  if (!wsB || !wsU || !wsC) {
    console.error("Workbook must have sheets: bing_results, urls, citations");
    process.exit(2);
  }

  const hb = headerMap(wsB);
  const hu = headerMap(wsU);
  const hc = headerMap(wsC);

  const bUrl = hb.get("url");
  const bDom = hb.get("result_domain");
  if (!bUrl) throw new Error("bing_results missing url col");

  const uUrl = hu.get("url");
  const uDom = hu.get("domain");
  if (!uUrl) throw new Error("urls missing url col");

  const cUrl = hc.get("url");
  if (!cUrl) throw new Error("citations missing url col");

  // 1) Identify ad rows in bing_results
  const bingRowsToDelete = [];
  const adUrls = new Set();
  for (let r = 2; r <= wsB.rowCount; r++) {
    const row = wsB.getRow(r);
    const url = safeStr(row.getCell(bUrl).value);
    const dom = safeStr(bDom ? row.getCell(bDom).value : "");
    if (!url) continue;
    if (isAdClickUrl(url) || isAdClickUrl(dom)) {
      bingRowsToDelete.push(r);
      adUrls.add(url);
    }
  }

  // 2) Delete bing_results rows
  deleteRowsDescending(wsB, bingRowsToDelete);

  // 3) Build keep set of URLs still referenced after deletion
  const keepUrls = new Set();
  for (let r = 2; r <= wsB.rowCount; r++) {
    const url = safeStr(wsB.getRow(r).getCell(bUrl).value);
    if (url) keepUrls.add(url);
  }
  for (let r = 2; r <= wsC.rowCount; r++) {
    const url = safeStr(wsC.getRow(r).getCell(cUrl).value);
    if (url) keepUrls.add(url);
  }

  // 4) Delete urls rows that are ad-click + not referenced anywhere
  const urlRowsToDelete = [];
  for (let r = 2; r <= wsU.rowCount; r++) {
    const row = wsU.getRow(r);
    const url = safeStr(row.getCell(uUrl).value);
    const dom = safeStr(uDom ? row.getCell(uDom).value : "");
    if (!url) continue;
    if (!keepUrls.has(url) && (adUrls.has(url) || isAdClickUrl(url) || isAdClickUrl(dom))) {
      urlRowsToDelete.push(r);
    }
  }
  deleteRowsDescending(wsU, urlRowsToDelete);

  if (args.write) {
    await wb.xlsx.writeFile(args.xlsx);
    console.log(`[patch] wrote ${args.xlsx}`);
  } else {
    console.log("[patch] --no-write (dry run)");
  }

  console.log({
    deleted_bing_results_rows: bingRowsToDelete.length,
    deleted_urls_rows: urlRowsToDelete.length,
  });
}

main().catch((e) => {
  console.error("Fatal:", e?.stack || String(e));
  process.exit(1);
});

