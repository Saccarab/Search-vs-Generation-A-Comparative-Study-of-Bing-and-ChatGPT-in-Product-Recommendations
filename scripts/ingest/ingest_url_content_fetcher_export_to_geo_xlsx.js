/**
 * Ingest URL Content Fetcher extension export CSV -> write content to disk + update geo_updated.xlsx `urls`.
 *
 * Input CSV columns (expected):
 *   url, final_url, domain, status, error, page_title, meta_description, canonical_url,
 *   published_date, modified_date, has_schema_markup, js_render_suspected, content_length,
 *   content_truncated, content
 *
 * Writes:
 *  - <content-root>/<run-label>/<hash>.txt
 *  - <content-root>/<run-label>/<hash>.meta.json
 *
 * Updates `geo_updated.xlsx` sheet `urls`:
 *  - content_path, meta_path, content_word_count, has_schema_markup, fetched_at, domain,
 *    page_title, meta_description, canonical_url, published_date, modified_date, js_render_suspected
 *
 * By default, only updates rows where content_path is blank (idempotent-ish).
 *
 * Usage (Windows):
 *  npm install
 *  node scripts/ingest/ingest_url_content_fetcher_export_to_geo_xlsx.js ^
 *    --xlsx geo_updated.xlsx ^
 *    --csv "C:\Users\User\Downloads\url_content_2026-01-12-22-54-24.csv" ^
 *    --content-root "C:\Users\User\Documents\thesis\url_content_fetcher" ^
 *    --run-label "url_content_2026-01-12"
 *
 * Options:
 *  --overwrite                 overwrite existing urls.content_path (and other fields)
 *  --create-missing-urls       if a url from CSV isn't found in urls sheet, append a new row
 *  --min-text-chars N          skip writing/updating when extracted content shorter than N (default 200)
 *  --max N                     cap processed rows
 */

/* eslint-disable no-console */
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const ExcelJS = require("exceljs");
const { parse } = require("csv-parse");

function safeStr(v) {
  if (v === null || v === undefined) return "";
  const s = String(v).trim();
  return s.toLowerCase() === "nan" ? "" : s;
}

function utcNowIso() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  const yyyy = d.getUTCFullYear();
  const mm = pad(d.getUTCMonth() + 1);
  const dd = pad(d.getUTCDate());
  const hh = pad(d.getUTCHours());
  const mi = pad(d.getUTCMinutes());
  const ss = pad(d.getUTCSeconds());
  return `${yyyy}-${mm}-${dd}T${hh}:${mi}:${ss}Z`;
}

function shortHash(text) {
  return crypto.createHash("sha256").update(text, "utf8").digest("hex").slice(0, 16);
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
    const isMicrosoftApps = host === "apps.microsoft.com";
    const dropExact = new Set([
      "gclid",
      "fbclid",
      "msclkid",
      "yclid",
      "mc_cid",
      "mc_eid",
      "igshid",
      "test_uuid",
      "test_variant",
    ]);
    const kept = [];
    for (const [k, v] of p.searchParams.entries()) {
      const lk = k.toLowerCase();
      if (lk.startsWith("utm_")) continue;
      if (isMicrosoftApps && (lk === "hl" || lk === "gl")) continue;
      if (dropExact.has(lk)) continue;
      kept.push([k, v]);
    }
    const q = new URLSearchParams(kept).toString();
    return `${host}${pathname}${q ? `?${q}` : ""}`;
  } catch {
    return u.toLowerCase();
  }
}

function extractDomain(rawUrl) {
  const u = safeStr(rawUrl);
  if (!u) return "";
  let url = u;
  if (!url.includes("://")) url = `https://${url}`;
  try {
    let host = new URL(url).hostname.toLowerCase();
    if (host.startsWith("www.")) host = host.slice(4);
    return host;
  } catch {
    return "";
  }
}

function countWords(text) {
  if (!text) return 0;
  const m = text.match(/[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?/g);
  return m ? m.length : 0;
}

function normalizeDateString(raw) {
  const s = safeStr(raw);
  if (!s) return "";
  if (/^\d{4}-\d{2}-\d{2}([tT].*)?$/.test(s)) return s;
  const d = new Date(s);
  if (!Number.isNaN(d.getTime())) return d.toISOString();
  return s;
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

function ensureHeader(ws, h, colName) {
  if (h.has(colName)) return;
  const headerRow = ws.getRow(1);
  const newCol = headerRow.cellCount + 1;
  headerRow.getCell(newCol).value = colName;
  h.set(colName, newCol);
}

function getCell(ws, rowIdx, h, colName) {
  const col = h.get(colName);
  if (!col) return "";
  return safeStr(ws.getRow(rowIdx).getCell(col).value);
}

function setCell(ws, rowIdx, h, colName, value) {
  const col = h.get(colName);
  if (!col) return;
  ws.getRow(rowIdx).getCell(col).value = value;
}

function parseArgs(argv) {
  const out = {
    xlsx: "geo_updated.xlsx",
    csv: "",
    contentRoot: "",
    runLabel: "",
    overwrite: false,
    createMissingUrls: false,
    minTextChars: 200,
    max: 0,
  };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--xlsx") out.xlsx = argv[++i];
    else if (a === "--csv") out.csv = argv[++i];
    else if (a === "--content-root") out.contentRoot = argv[++i];
    else if (a === "--run-label") out.runLabel = argv[++i] || "";
    else if (a === "--overwrite") out.overwrite = true;
    else if (a === "--create-missing-urls") out.createMissingUrls = true;
    else if (a === "--min-text-chars") {
      const val = argv[++i];
      out.minTextChars = (val !== undefined && val !== "") ? Number(val) : 200;
    }
    else if (a === "--max") out.max = Number(argv[++i] || "0") || 0;
  }
  return out;
}

async function main() {
  const args = parseArgs(process.argv);
  if (!args.csv) throw new Error("Missing required --csv <path-to-export.csv>");
  if (!args.contentRoot) throw new Error('Missing required --content-root, e.g. --content-root "C:\\\\Users\\\\User\\\\Documents\\\\thesis\\\\url_content_fetcher"');

  const runLabel =
    (args.runLabel || "").trim() ||
    `url_content_fetcher_${new Date().toISOString().slice(0, 10)}`;
  const outDir = path.join(args.contentRoot, runLabel);
  fs.mkdirSync(outDir, { recursive: true });

  const wb = new ExcelJS.Workbook();
  await wb.xlsx.readFile(args.xlsx);
  const ws = wb.getWorksheet("urls");
  if (!ws) throw new Error("Workbook missing sheet: urls");
  const h = sheetHeaderMap(ws);

  // Required base columns
  for (const c of ["url", "domain", "content_path", "content_word_count", "has_schema_markup", "fetched_at"]) {
    if (!h.has(c)) throw new Error(`urls sheet missing required column: ${c}`);
  }

  // Ensure optional metadata columns exist
  for (const c of [
    "page_title",
    "meta_description",
    "canonical_url",
    "published_date",
    "modified_date",
    "meta_path",
    "js_render_suspected",
  ]) {
    ensureHeader(ws, h, c);
  }

  // Build an index from normalized URL key -> row index
  const keyToRow = new Map();
  for (let r = 2; r <= ws.rowCount; r++) {
    const url = getCell(ws, r, h, "url");
    if (!url) continue;
    const k = normalizeUrlKey(url);
    if (!k) continue;
    if (!keyToRow.has(k)) {
      keyToRow.set(k, r);
      continue;
    }
    const existingRowIdx = keyToRow.get(k);
    const existingUrl = getCell(ws, existingRowIdx, h, "url");
    const existingLen = existingUrl ? existingUrl.length : 0;
    const currentLen = url.length;
    if (currentLen && (!existingLen || currentLen < existingLen)) {
      keyToRow.set(k, r);
    }
  }

  let processed = 0;
  let matched = 0;
  let appended = 0;
  let skippedHasContent = 0;
  let skippedNonOk = 0;
  let skippedShort = 0;
  let written = 0;
  let updated = 0;

  const parser = fs.createReadStream(args.csv).pipe(
    parse({
      columns: true,
      bom: true,
      relax_quotes: true,
      relax_column_count: true,
      skip_empty_lines: true,
      max_record_size: 50 * 1024 * 1024, // 50MB per record
    })
  );

  for await (const rec of parser) {
    processed++;
    if (args.max && processed > args.max) break;

    const url = safeStr(rec.url);
    const finalUrl = safeStr(rec.final_url);
    const status = Number(safeStr(rec.status) || "0") || 0;
    const content = safeStr(rec.content);
    const pageTitle = safeStr(rec.page_title);
    const metaDescription = safeStr(rec.meta_description);
    const canonicalUrl = safeStr(rec.canonical_url);
    const publishedDate = normalizeDateString(rec.published_date);
    const modifiedDate = normalizeDateString(rec.modified_date);
    const hasSchema = String(safeStr(rec.has_schema_markup)).trim() === "1" ? 1 : 0;
    const jsRenderSuspected = String(safeStr(rec.js_render_suspected)).trim() === "1" ? 1 : 0;
    const domain = safeStr(rec.domain) || extractDomain(finalUrl || url);

    if (!url) continue;
    if (status < 200 || status >= 300 || !content) {
      skippedNonOk++;
      continue;
    }
    if (content.length < args.minTextChars) {
      skippedShort++;
      continue;
    }

    const key = normalizeUrlKey(finalUrl || url || "");
    if (!key) continue;

    let rowIdx = keyToRow.get(key);
    if (rowIdx) {
      matched++;
    } else if (args.createMissingUrls) {
      rowIdx = ws.rowCount + 1;
      ws.getRow(rowIdx).getCell(h.get("url")).value = finalUrl || url;
      ws.getRow(rowIdx).getCell(h.get("domain")).value = domain;
      keyToRow.set(key, rowIdx);
      appended++;
    } else {
      // Export contained URL that isn't in workbook; skip so we don't silently expand dataset.
      continue;
    }

    const existingCp = getCell(ws, rowIdx, h, "content_path");
    if (existingCp && !args.overwrite) {
      skippedHasContent++;
      continue;
    }

    const fname = `${shortHash(key)}.txt`;
    const metaName = `${shortHash(key)}.meta.json`;
    const fpath = path.join(outDir, fname);
    const metaPath = path.join(outDir, metaName);

    fs.writeFileSync(fpath, content, "utf8");
    fs.writeFileSync(
      metaPath,
      JSON.stringify(
        {
          url,
          final_url: finalUrl,
          status,
          error: safeStr(rec.error),
          fetched_at: utcNowIso(),
          domain,
          has_schema_markup: hasSchema,
          js_render_suspected: jsRenderSuspected,
          page_title: pageTitle,
          meta_description: metaDescription,
          canonical_url: canonicalUrl,
          published_date: publishedDate,
          modified_date: modifiedDate,
          content_length: Number(safeStr(rec.content_length) || "0") || 0,
          content_truncated: String(safeStr(rec.content_truncated)).trim() === "1" ? 1 : 0,
        },
        null,
        2
      ),
      "utf8"
    );

    written++;

    const now = utcNowIso();
    setCell(ws, rowIdx, h, "domain", getCell(ws, rowIdx, h, "domain") || domain);
    setCell(ws, rowIdx, h, "content_path", fpath);
    setCell(ws, rowIdx, h, "meta_path", metaPath);
    setCell(ws, rowIdx, h, "content_word_count", countWords(content));
    setCell(ws, rowIdx, h, "has_schema_markup", hasSchema);
    setCell(ws, rowIdx, h, "js_render_suspected", jsRenderSuspected);
    setCell(ws, rowIdx, h, "fetched_at", now);
    setCell(ws, rowIdx, h, "page_title", pageTitle);
    setCell(ws, rowIdx, h, "meta_description", metaDescription);
    setCell(ws, rowIdx, h, "canonical_url", canonicalUrl);
    setCell(ws, rowIdx, h, "published_date", publishedDate);
    setCell(ws, rowIdx, h, "modified_date", modifiedDate);
    if (h.has("missing_reason")) {
      setCell(ws, rowIdx, h, "missing_reason", "");
    }
    updated++;
  }

  await wb.xlsx.writeFile(args.xlsx);

  console.log("Done.");
  console.log({
    csv: args.csv,
    xlsx: args.xlsx,
    outDir,
    processed,
    matched,
    appended,
    skippedHasContent,
    skippedNonOk,
    skippedShort,
    written,
    updated,
    overwrite: args.overwrite,
    createMissingUrls: args.createMissingUrls,
  });
}

main().catch((e) => {
  console.error("Fatal:", e?.stack || String(e));
  process.exit(1);
});

