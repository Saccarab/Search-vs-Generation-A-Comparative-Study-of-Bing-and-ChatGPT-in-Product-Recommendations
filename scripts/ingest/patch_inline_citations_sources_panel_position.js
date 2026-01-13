/**
 * Backfill sources-panel cite position for inline citations in geo_updated.xlsx.
 *
 * What it does:
 * - Reads `citations` sheet
 * - Builds per-run map: url -> cite_position from citation_type in {cited, additional}
 * - For citation_type == inline:
 *     - fills `sources_panel_cite_position` (creates column if missing)
 *     - optionally fills `cite_position` if blank (same value)
 *
 * Run:
 *   node scripts/ingest/patch_inline_citations_sources_panel_position.js --xlsx geo_updated.xlsx
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

function ensureHeader(ws, headerMap, colName) {
  if (headerMap.has(colName)) return headerMap.get(colName);
  const headerRow = ws.getRow(1);
  const newCol = headerRow.cellCount + 1;
  headerRow.getCell(newCol).value = colName;
  headerMap.set(colName, newCol);
  return newCol;
}

function headerMap(ws) {
  const m = new Map();
  const hr = ws.getRow(1);
  hr.eachCell((cell, col) => {
    const k = safeStr(cell.value);
    if (k) m.set(k, col);
  });
  return m;
}

async function main() {
  const args = parseArgs(process.argv);

  const wb = new ExcelJS.Workbook();
  await wb.xlsx.readFile(args.xlsx);

  const ws = wb.getWorksheet("citations");
  if (!ws) {
    console.error("Missing sheet: citations");
    process.exit(2);
  }

  const h = headerMap(ws);
  const need = ["run_id", "url", "citation_type", "cite_position"];
  for (const k of need) {
    if (!h.has(k)) {
      console.error(`Missing citations column: ${k}`);
      process.exit(2);
    }
  }

  // Ensure optional column exists
  ensureHeader(ws, h, "sources_panel_cite_position");

  const cRun = h.get("run_id");
  const cUrl = h.get("url");
  const cType = h.get("citation_type");
  const cCitePos = h.get("cite_position");
  const cSP = h.get("sources_panel_cite_position");

  // Build per-run sources panel positions
  const perRun = new Map(); // run_id -> Map(url -> cite_position)
  for (let r = 2; r <= ws.rowCount; r++) {
    const row = ws.getRow(r);
    const runId = safeStr(row.getCell(cRun).value);
    const url = safeStr(row.getCell(cUrl).value);
    const type = safeStr(row.getCell(cType).value);
    const pos = safeStr(row.getCell(cCitePos).value);
    if (!runId || !url || !pos) continue;
    if (type !== "cited" && type !== "additional") continue;
    if (!perRun.has(runId)) perRun.set(runId, new Map());
    const m = perRun.get(runId);
    // If duplicated URL in sources panel, keep the first position
    if (!m.has(url)) m.set(url, pos);
  }

  let touched = 0;
  let filled = 0;

  for (let r = 2; r <= ws.rowCount; r++) {
    const row = ws.getRow(r);
    const runId = safeStr(row.getCell(cRun).value);
    const url = safeStr(row.getCell(cUrl).value);
    const type = safeStr(row.getCell(cType).value);
    if (!runId || !url || type !== "inline") continue;

    const m = perRun.get(runId);
    const spPos = m ? safeStr(m.get(url)) : "";
    if (!spPos) continue;

    const curSp = safeStr(row.getCell(cSP).value);
    const curCite = safeStr(row.getCell(cCitePos).value);
    let changed = false;

    if (!curSp) {
      row.getCell(cSP).value = spPos;
      filled++;
      changed = true;
    }

    // If cite_position is blank for inline rows, fill it too (same semantics: sources panel position)
    if (!curCite) {
      row.getCell(cCitePos).value = spPos;
      changed = true;
    }

    if (changed) touched++;
  }

  if (args.write) {
    await wb.xlsx.writeFile(args.xlsx);
    console.log(`[patch] wrote ${args.xlsx}`);
  } else {
    console.log("[patch] --no-write (dry run)");
  }

  console.log({ inline_rows_updated: touched, sources_panel_positions_filled: filled });
}

main().catch((e) => {
  console.error("Fatal:", e?.stack || String(e));
  process.exit(1);
});

