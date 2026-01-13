/**
 * Patch geo_updated.xlsx `citations` sheet:
 * - Backfill sources-panel cite position for inline citations:
 *     - compute per-run URL -> cite_position from citation_type in {cited, additional}
 *     - match using normalized URL key (drops utm/msclkid/etc, www, scheme, fragment)
 *     - write to `sources_panel_cite_position` and (if blank) `cite_position` for inline rows
 *
 * - Sanity-fix inline group fields:
 *     - if citation_group_size is blank or < citation_in_group_rank, set group_size = group_rank
 *     - leaves values alone otherwise
 *
 * Run:
 *   node scripts/ingest/patch_citations_inline_positions_and_groups.js --xlsx geo_updated.xlsx
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

function ensureHeader(ws, h, colName) {
  if (h.has(colName)) return h.get(colName);
  const headerRow = ws.getRow(1);
  const newCol = headerRow.cellCount + 1;
  headerRow.getCell(newCol).value = colName;
  h.set(colName, newCol);
  return newCol;
}

function normalizeUrlKey(rawUrl) {
  const u = safeStr(rawUrl);
  if (!u) return "";
  let url = u;
  if (!url.includes("://")) url = `https://${url}`;
  try {
    const p = new URL(url);
    let host = (p.hostname || "").toLowerCase();
    if (host.startsWith("www.")) host = host.slice(4);
    let pathname = p.pathname || "/";
    if (pathname.length > 1 && pathname.endsWith("/")) pathname = pathname.slice(0, -1);
    const dropExact = new Set([
      "gclid",
      "fbclid",
      "msclkid",
      "yclid",
      "mc_cid",
      "mc_eid",
      "igshid",
      "ref",
      "ref_src",
    ]);
    const kept = [];
    for (const [k, v] of p.searchParams.entries()) {
      const lk = k.toLowerCase();
      if (lk.startsWith("utm_")) continue;
      if (dropExact.has(lk)) continue;
      kept.push([k, v]);
    }
    const q = new URLSearchParams(kept).toString();
    return `${host}${pathname}${q ? `?${q}` : ""}`;
  } catch {
    return u.toLowerCase();
  }
}

function toIntOr0(s) {
  const n = Number(safeStr(s));
  return Number.isFinite(n) ? n : 0;
}

async function main() {
  const args = parseArgs(process.argv);
  const wb = new ExcelJS.Workbook();
  await wb.xlsx.readFile(args.xlsx);

  const ws = wb.getWorksheet("citations");
  if (!ws) throw new Error("Missing sheet: citations");

  const h = headerMap(ws);
  const need = ["run_id", "url", "citation_type", "cite_position", "citation_in_group_rank", "citation_group_size"];
  for (const k of need) {
    if (!h.has(k)) throw new Error(`citations missing required column: ${k}`);
  }
  const cRun = h.get("run_id");
  const cUrl = h.get("url");
  const cType = h.get("citation_type");
  const cCitePos = h.get("cite_position");
  const cRank = h.get("citation_in_group_rank");
  const cSize = h.get("citation_group_size");
  const cSP = ensureHeader(ws, h, "sources_panel_cite_position");

  // per run: url_key -> cite_position (from sources panel)
  const perRun = new Map();
  for (let r = 2; r <= ws.rowCount; r++) {
    const row = ws.getRow(r);
    const runId = safeStr(row.getCell(cRun).value);
    const url = safeStr(row.getCell(cUrl).value);
    const type = safeStr(row.getCell(cType).value);
    const pos = safeStr(row.getCell(cCitePos).value);
    if (!runId || !url || !pos) continue;
    if (type !== "cited" && type !== "additional") continue;
    const key = normalizeUrlKey(url);
    if (!key) continue;
    if (!perRun.has(runId)) perRun.set(runId, new Map());
    const m = perRun.get(runId);
    if (!m.has(key)) m.set(key, pos); // keep first
  }

  let inlineRows = 0;
  let filledPositions = 0;
  let fixedGroupSizes = 0;

  for (let r = 2; r <= ws.rowCount; r++) {
    const row = ws.getRow(r);
    const runId = safeStr(row.getCell(cRun).value);
    const url = safeStr(row.getCell(cUrl).value);
    const type = safeStr(row.getCell(cType).value);
    if (!runId || !url || type !== "inline") continue;
    inlineRows++;

    // backfill sources-panel position
    const key = normalizeUrlKey(url);
    const m = perRun.get(runId);
    const spPos = m ? safeStr(m.get(key)) : "";
    if (spPos) {
      const curSp = safeStr(row.getCell(cSP).value);
      const curCite = safeStr(row.getCell(cCitePos).value);
      if (!curSp) {
        row.getCell(cSP).value = spPos;
        filledPositions++;
      }
      if (!curCite) {
        row.getCell(cCitePos).value = spPos;
      }
    }

    // fix group size
    const rank = toIntOr0(row.getCell(cRank).value);
    const size = toIntOr0(row.getCell(cSize).value);
    if (rank > 0 && (size === 0 || size < rank)) {
      row.getCell(cSize).value = rank;
      fixedGroupSizes++;
    }
  }

  if (args.write) {
    await wb.xlsx.writeFile(args.xlsx);
    console.log(`[patch] wrote ${args.xlsx}`);
  } else {
    console.log("[patch] --no-write (dry run)");
  }

  console.log({ inline_rows_seen: inlineRows, sources_panel_positions_filled: filledPositions, group_sizes_fixed: fixedGroupSizes });
}

main().catch((e) => {
  console.error("Fatal:", e?.stack || String(e));
  process.exit(1);
});

