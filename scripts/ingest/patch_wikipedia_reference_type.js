/**
 * One-time local patch: set urls.type = "reference" for wikipedia.org URLs.
 * No API calls. Just edits geo_updated.xlsx in-place.
 *
 * Usage:
 *   node scripts/ingest/patch_wikipedia_reference_type.js --xlsx geo_updated.xlsx
 *
 * Behavior:
 * - If urls.type is blank OR equals "other", set it to "reference"
 * - Only when url contains "wikipedia.org/"
 */

/* eslint-disable no-console */
const ExcelJS = require("exceljs");

function safeStr(v) {
  if (v === null || v === undefined) return "";
  return String(v).trim();
}

function parseArgs(argv) {
  const out = { xlsx: "geo_updated.xlsx" };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--xlsx") out.xlsx = argv[++i];
  }
  return out;
}

function sheetHeaderMap(ws) {
  const map = new Map();
  const headerRow = ws.getRow(1);
  headerRow.eachCell((cell, col) => {
    const key = safeStr(cell.value);
    if (key) map.set(key, col);
  });
  return map;
}

async function main() {
  const args = parseArgs(process.argv);
  const wb = new ExcelJS.Workbook();
  await wb.xlsx.readFile(args.xlsx);

  const ws = wb.getWorksheet("urls");
  if (!ws) throw new Error("Workbook missing sheet: urls");
  const h = sheetHeaderMap(ws);
  if (!h.has("url") || !h.has("type")) throw new Error("urls sheet missing required columns: url/type");

  const cUrl = h.get("url");
  const cType = h.get("type");

  let scanned = 0;
  let updated = 0;
  for (let r = 2; r <= ws.rowCount; r++) {
    const url = safeStr(ws.getRow(r).getCell(cUrl).value);
    if (!url) continue;
    scanned++;
    if (!url.toLowerCase().includes("wikipedia.org/")) continue;
    const cur = safeStr(ws.getRow(r).getCell(cType).value).toLowerCase();
    if (cur && cur !== "other") continue;
    ws.getRow(r).getCell(cType).value = "reference";
    updated++;
  }

  await wb.xlsx.writeFile(args.xlsx);
  console.log("Done.");
  console.log({ xlsx: args.xlsx, scanned, updated });
}

main().catch((e) => {
  console.error("Fatal:", e?.stack || String(e));
  process.exit(1);
});

