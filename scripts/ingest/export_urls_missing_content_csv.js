/**
 * Export a CSV of URLs that are "missing" for content/labeling.
 *
 * Default export:
 * - urls.type is blank
 * - AND urls.content_path is blank
 *
 * Output CSV has a single column: url
 *
 * Run:
 *   node scripts/ingest/export_urls_missing_content_csv.js --xlsx geo_updated.xlsx --out data/ingest/urls_missing_content.csv
 *
 * Options:
 *   --missing-type-only          include rows with blank type (regardless of content_path)
 *   --missing-content-only       include rows with blank content_path (regardless of type)
 *   --missing-any               include rows with blank type OR blank content_path
 *   --url-contains <substr>      filter URLs
 *   --max <n>                    cap rows
 */

/* eslint-disable no-console */
const fs = require("fs");
const path = require("path");
const ExcelJS = require("exceljs");

function parseArgs(argv) {
  const out = {
    xlsx: "geo_updated.xlsx",
    outPath: path.join("data", "ingest", "urls_missing_content.csv"),
    missingTypeOnly: false,
    missingContentOnly: false,
    missingAny: false,
    urlContains: "",
    max: 0,
  };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--xlsx") out.xlsx = argv[++i];
    else if (a === "--out") out.outPath = argv[++i];
    else if (a === "--missing-type-only") out.missingTypeOnly = true;
    else if (a === "--missing-content-only") out.missingContentOnly = true;
    else if (a === "--missing-any") out.missingAny = true;
    else if (a === "--url-contains") out.urlContains = String(argv[++i] || "");
    else if (a === "--max") out.max = Number(argv[++i] || "0") || 0;
  }
  return out;
}

function safeStr(v) {
  if (v === null || v === undefined) return "";
  const s = String(v).trim();
  return s.toLowerCase() === "nan" ? "" : s;
}

function csvEscape(v) {
  const s = safeStr(v);
  if (/[,"\r\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

async function main() {
  const args = parseArgs(process.argv);
  const wb = new ExcelJS.Workbook();
  await wb.xlsx.readFile(args.xlsx);
  const ws = wb.getWorksheet("urls");
  if (!ws) throw new Error("Workbook missing sheet: urls");

  const h = new Map();
  ws.getRow(1).eachCell((c, i) => {
    const k = safeStr(c.value);
    if (k) h.set(k, i);
  });
  const cUrl = h.get("url");
  const cType = h.get("type");
  const cCp = h.get("content_path");
  if (!cUrl || !cType || !cCp) throw new Error("urls sheet missing required columns: url, type, content_path");

  const contains = safeStr(args.urlContains).toLowerCase();
  const rows = [];

  for (let r = 2; r <= ws.rowCount; r++) {
    const url = safeStr(ws.getRow(r).getCell(cUrl).value);
    if (!url) continue;
    if (contains && !url.toLowerCase().includes(contains)) continue;

    const type = safeStr(ws.getRow(r).getCell(cType).value);
    const cp = safeStr(ws.getRow(r).getCell(cCp).value);

    const missType = !type;
    const missCp = !cp;

    let include = false;
    if (args.missingAny) include = missType || missCp;
    else if (args.missingTypeOnly) include = missType;
    else if (args.missingContentOnly) include = missCp;
    else include = missType && missCp;

    if (!include) continue;
    rows.push(url);
    if (args.max && rows.length >= args.max) break;
  }

  fs.mkdirSync(path.dirname(args.outPath), { recursive: true });
  const csv = ["url", ...rows.map((u) => csvEscape(u))].join("\n");
  fs.writeFileSync(args.outPath, csv, "utf8");

  console.log(`Wrote ${rows.length} URL(s) -> ${args.outPath}`);
}

main().catch((e) => {
  console.error("Fatal:", e?.stack || String(e));
  process.exit(1);
});

