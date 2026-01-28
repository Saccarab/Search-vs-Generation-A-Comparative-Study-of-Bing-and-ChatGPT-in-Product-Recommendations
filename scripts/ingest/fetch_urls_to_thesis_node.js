/**
 * Fetch URL content for rows in geo_updated.xlsx -> `urls` sheet (Node.js version).
 *
 * Goal:
 * - Replace the Python fetcher with a Node workflow (consistent with extension-style extraction).
 * - Fetch HTML, extract visible-ish text (remove script/style/noscript + nav/header/footer/aside + common junk),
 *   write to disk, update `urls` columns:
 *     content_path, content_word_count, has_schema_markup, fetched_at, domain
 *
 * Install:
 *   npm install
 *
 * Run (refetch everything, but don't wipe existing content on failures):
 *   node scripts/ingest/fetch_urls_to_thesis_node.js --xlsx geo_updated.xlsx --content-root "C:\\Users\\User\\Documents\\thesis\\node_content" --overwrite
 *
 * Useful knobs:
 *   --max 50
 *   --concurrency 3
 *   --min-time-ms 400
 *   --timeout-ms 45000
 *   --only-url <url>           (repeatable)
 *   --url-contains <substr>
 *
 * Proxy:
 *   set HTTPS_PROXY=http://user:pass@host:port
 *   set HTTP_PROXY=http://user:pass@host:port
 *   set NO_PROXY=localhost,127.0.0.1
 *
 * Logs:
 *   Appends JSONL to data/ingest/url_fetch_log.jsonl
 */

/* eslint-disable no-console */
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const ExcelJS = require("exceljs");
const Bottleneck = require("bottleneck");
const cheerio = require("cheerio");

function safeStr(v) {
  if (v === null || v === undefined) return "";
  const s = String(v).trim();
  return s.toLowerCase() === "nan" ? "" : s;
}

function utcNowIso() {
  // no ms
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
    // keep query but drop common tracking
    const dropExact = new Set(["gclid", "fbclid", "msclkid", "yclid", "mc_cid", "mc_eid", "igshid"]);
    const kept = [];
    for (const [k, v] of p.searchParams.entries()) {
      const lk = k.toLowerCase();
      if (lk.startsWith("utm_")) continue;
      if (dropExact.has(lk)) continue;
      kept.push([k, v]);
    }
    const q = new URLSearchParams(kept).toString();
    // scheme intentionally dropped (like python normalize_url_key)
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

function hasSchemaMarkupFromHtml(html) {
  const h = (html || "").toLowerCase();
  if (h.includes('type="application/ld+json"')) return true;
  if (h.includes("itemscope") && h.includes("itemtype")) return true;
  return false;
}

function normalizeDateString(raw) {
  const s = safeStr(raw);
  if (!s) return "";
  // Keep ISO-ish strings stable when possible
  if (/^\d{4}-\d{2}-\d{2}([tT].*)?$/.test(s)) return s;
  const d = new Date(s);
  if (!Number.isNaN(d.getTime())) return d.toISOString();
  return s;
}

function extractMetadataFromHtml(html) {
  const out = {
    page_title: "",
    meta_description: "",
    canonical_url: "",
    published_date: "",
    modified_date: "",
  };
  if (!html) return out;

  const $ = cheerio.load(html, { decodeEntities: true });

  const pickFirst = (arr) => {
    for (const v of arr) {
      const s = safeStr(v);
      if (s) return s;
    }
    return "";
  };
  const meta = (sel, attr = "content") => safeStr($(sel).first().attr(attr));

  out.page_title = pickFirst([$("title").first().text(), meta('meta[property="og:title"]'), meta('meta[name="twitter:title"]')]);
  out.meta_description = pickFirst([
    meta('meta[name="description"]'),
    meta('meta[property="og:description"]'),
    meta('meta[name="twitter:description"]'),
  ]);
  out.canonical_url = pickFirst([safeStr($('link[rel="canonical"]').first().attr("href")), meta('meta[property="og:url"]')]);

  const publishedCandidates = [
    meta('meta[property="article:published_time"]'),
    meta('meta[property="og:published_time"]'),
    meta('meta[name="pubdate"]'),
    meta('meta[name="publish-date"]'),
    meta('meta[name="date"]'),
    meta('meta[itemprop="datePublished"]'),
    safeStr($("time[datetime]").first().attr("datetime")),
  ];
  const modifiedCandidates = [
    meta('meta[property="article:modified_time"]'),
    meta('meta[property="og:updated_time"]'),
    meta('meta[name="last-modified"]'),
    meta('meta[name="modified"]'),
    meta('meta[itemprop="dateModified"]'),
  ];

  // JSON-LD: datePublished / dateModified
  const ldDates = { datePublished: "", dateModified: "" };
  const scripts = $('script[type="application/ld+json"]').toArray().slice(0, 25);
  const scanJson = (obj) => {
    if (!obj) return;
    if (Array.isArray(obj)) {
      for (const it of obj) scanJson(it);
      return;
    }
    if (typeof obj !== "object") return;
    if (!ldDates.datePublished && typeof obj.datePublished === "string") ldDates.datePublished = obj.datePublished;
    if (!ldDates.dateModified && typeof obj.dateModified === "string") ldDates.dateModified = obj.dateModified;
    if (obj["@graph"]) scanJson(obj["@graph"]);
    for (const v of Object.values(obj)) {
      if (typeof v === "object") scanJson(v);
    }
  };
  for (const sEl of scripts) {
    const txt = safeStr($(sEl).text());
    if (!txt) continue;
    try {
      scanJson(JSON.parse(txt));
    } catch {
      // ignore bad JSON-LD
    }
    if (ldDates.datePublished && ldDates.dateModified) break;
  }

  out.published_date = normalizeDateString(pickFirst([ldDates.datePublished, ...publishedCandidates]));
  out.modified_date = normalizeDateString(pickFirst([ldDates.dateModified, ...modifiedCandidates]));
  return out;
}

function extractTextFromHtmlLikeExtension(html) {
  if (!html) return "";
  const $ = cheerio.load(html, { decodeEntities: true });

  // Match the extension's extraction logic as closely as possible:
  // - remove script/style/noscript
  // - remove common non-content elements and class selectors
  $("script, style, noscript").remove();

  const nonContentSelectors = [
    "nav",
    "header",
    "footer",
    "aside",
    ".navigation",
    ".nav",
    ".menu",
    ".sidebar",
    ".advertisement",
    ".ad",
    ".ads",
    ".cookie",
    ".popup",
    ".modal",
    ".overlay",
  ];
  $(nonContentSelectors.join(", ")).remove();

  // Prefer body text
  let text = $("body").text() || "";
  text = text.replace(/\u00a0/g, " ");
  // normalize whitespace exactly like extension (effectively single-space collapse)
  text = text.replace(/\s+/g, " ").trim();
  return text;
}

async function fetchHtml(url, timeoutMs) {
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      method: "GET",
      redirect: "follow",
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
      },
      signal: controller.signal,
    });
    const ct = (res.headers.get("content-type") || "").toLowerCase();
    const okType = ct.includes("text/html") || ct.includes("application/xhtml") || ct.includes("text/plain");
    const body = okType ? await res.text() : "";
    return {
      ok: res.ok,
      status: res.status,
      finalUrl: res.url || url,
      html: body,
      error: res.ok ? "" : `HTTP ${res.status} ${res.statusText}`.trim(),
      contentType: ct,
    };
  } catch (e) {
    const name = e?.name || "Error";
    const msg = String(e?.message || e);
    return { ok: false, status: 0, finalUrl: url, html: "", error: `${name}: ${msg}`, contentType: "" };
  } finally {
    clearTimeout(t);
  }
}

function parseArgs(argv) {
  const out = {
    xlsx: "geo_updated.xlsx",
    contentRoot: "",
    runLabel: "",
    overwrite: false,
    noUpdateXlsx: false,
    max: 0,
    concurrency: 3,
    minTimeMs: 400,
    timeoutMs: 45000,
    minTextChars: 200,
    onlyUrl: [],
    urlContains: "",
    onlyContentPathContains: "",
    includeAdditionalOnly: false,
  };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--xlsx") out.xlsx = argv[++i];
    else if (a === "--content-root") out.contentRoot = argv[++i];
    else if (a === "--run-label") out.runLabel = argv[++i];
    else if (a === "--overwrite") out.overwrite = true;
    else if (a === "--no-update-xlsx") out.noUpdateXlsx = true;
    else if (a === "--max") out.max = Number(argv[++i] || "0") || 0;
    else if (a === "--concurrency") out.concurrency = Number(argv[++i] || "3") || 3;
    else if (a === "--min-time-ms") out.minTimeMs = Number(argv[++i] || "400") || 400;
    else if (a === "--timeout-ms") out.timeoutMs = Number(argv[++i] || "45000") || 45000;
    else if (a === "--min-text-chars") out.minTextChars = Number(argv[++i] || "200") || 200;
    else if (a === "--only-url") out.onlyUrl.push(argv[++i]);
    else if (a === "--url-contains") out.urlContains = argv[++i] || "";
    else if (a === "--only-content-path-contains") out.onlyContentPathContains = argv[++i] || "";
    else if (a === "--include-additional-only") out.includeAdditionalOnly = true;
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

async function main() {
  const args = parseArgs(process.argv);
  if (!args.contentRoot) {
    console.error('Missing required --content-root, e.g. --content-root "C:\\\\Users\\\\User\\\\Documents\\\\thesis\\\\node_content"');
    process.exit(2);
  }

  const runLabel = (args.runLabel || "").trim() || `node_fetch_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "").slice(0, 15)}`;
  const outDir = path.join(args.contentRoot, runLabel);
  fs.mkdirSync(outDir, { recursive: true });

  const logPath = path.join("data", "ingest", "url_fetch_log.jsonl");
  fs.mkdirSync(path.dirname(logPath), { recursive: true });

  const wb = new ExcelJS.Workbook();
  await wb.xlsx.readFile(args.xlsx);
  const ws = wb.getWorksheet("urls");
  if (!ws) throw new Error("Workbook missing sheet: urls");
  const wsCit = wb.getWorksheet("citations");
  const wsBing = wb.getWorksheet("bing_results");
  const h = sheetHeaderMap(ws);

  const required = ["url", "domain", "content_path", "content_word_count", "has_schema_markup", "fetched_at"];
  const missing = required.filter((c) => !h.has(c));
  if (missing.length) throw new Error(`urls sheet missing required columns: ${missing.join(", ")}`);

  // Optional metadata columns (we'll create them if missing).
  // These help later freshness analysis and better prompt context without polluting extracted text.
  for (const c of ["page_title", "meta_description", "canonical_url", "published_date", "modified_date", "meta_path"]) {
    ensureHeader(ws, h, c);
  }

  const onlyUrls = new Set((args.onlyUrl || []).map((u) => safeStr(u)).filter(Boolean));
  const contains = safeStr(args.urlContains).toLowerCase();
  const onlyCpContains = safeStr(args.onlyContentPathContains).toLowerCase();

  // Default: skip URLs that appear ONLY as citation_type=additional (\"More\" panel)
  // and are not referenced by inline/cited citations or by Bing results.
  // This keeps additional sources for analysis, but avoids fetch cost at scale.
  const keepKeys = new Set();
  if (wsBing) {
    const hb = sheetHeaderMap(wsBing);
    if (hb.has("url")) {
      for (let r = 2; r <= wsBing.rowCount; r++) {
        const u = getCell(wsBing, r, hb, "url");
        const k = normalizeUrlKey(u);
        if (k) keepKeys.add(k);
      }
    }
  }
  if (wsCit) {
    const hc = sheetHeaderMap(wsCit);
    if (hc.has("url") && hc.has("citation_type")) {
      for (let r = 2; r <= wsCit.rowCount; r++) {
        const u = getCell(wsCit, r, hc, "url");
        const t = safeStr(getCell(wsCit, r, hc, "citation_type")).toLowerCase();
        if (!u) continue;
        if (t === "additional") continue;
        const k = normalizeUrlKey(u);
        if (k) keepKeys.add(k);
      }
    }
  }

  const limiter = new Bottleneck({ maxConcurrent: Math.max(1, args.concurrency), minTime: Math.max(0, args.minTimeMs) });
  const writeLimiter = new Bottleneck({ maxConcurrent: 1 });

  let processed = 0;
  let fetchedOk = 0;
  let failed = 0;
  let skipped = 0;
  let skippedAdditionalOnly = 0;
  let written = 0;

  const tasks = [];

  for (let r = 2; r <= ws.rowCount; r++) {
    const url = getCell(ws, r, h, "url");
    if (!url) continue;

    if (onlyUrls.size && !onlyUrls.has(url)) continue;
    if (!onlyUrls.size && contains && !url.toLowerCase().includes(contains)) continue;

    // Skip additional-only URLs unless explicitly included or targeted with --only-url
    if (!args.includeAdditionalOnly && !onlyUrls.size && keepKeys.size) {
      const k = normalizeUrlKey(url);
      if (k && !keepKeys.has(k)) {
        skippedAdditionalOnly++;
        continue;
      }
    }

    const existingCp = getCell(ws, r, h, "content_path");
    if (onlyCpContains) {
      // Only refetch rows that already have a content_path matching some prior pipeline (e.g. python_fetch_*)
      if (!existingCp || !existingCp.toLowerCase().includes(onlyCpContains)) {
        continue;
      }
    }
    if (existingCp && !args.overwrite) {
      skipped++;
      continue;
    }

    processed++;
    if (args.max && processed > args.max) break;

    const rowIdx = r;
    tasks.push(
      limiter
        .schedule(async () => {
          const startedAt = Date.now();
          const rawUrl = url.includes("://") ? url : `https://${url}`;
          const fr = await fetchHtml(rawUrl, args.timeoutMs);

          let extractedText = "";
          let schema = false;
          let domain = extractDomain(rawUrl);
          let metaOut = { page_title: "", meta_description: "", canonical_url: "", published_date: "", modified_date: "" };

          if (fr.ok && fr.html) {
            schema = hasSchemaMarkupFromHtml(fr.html);
            metaOut = extractMetadataFromHtml(fr.html);
            extractedText = extractTextFromHtmlLikeExtension(fr.html);
          }

          const ms = Date.now() - startedAt;
          return { rowIdx, rawUrl, fr, extractedText, schema, domain, metaOut, ms };
        })
        .then((res) =>
          writeLimiter.schedule(async () => {
            const { rowIdx, rawUrl, fr, extractedText, schema, domain, metaOut, ms } = res;
            const now = utcNowIso();

            // Always stamp fetched_at so attempts are visible (unless no-update)
            if (!args.noUpdateXlsx) {
              setCell(ws, rowIdx, h, "fetched_at", now);
              if (!getCell(ws, rowIdx, h, "domain")) setCell(ws, rowIdx, h, "domain", domain);
            }

            if (!fr.ok || !fr.html) {
              failed++;
              fs.appendFileSync(
                logPath,
                JSON.stringify({
                  ts: now,
                  url: rawUrl,
                  ok: false,
                  status: fr.status,
                  error: fr.error,
                  content_type: fr.contentType,
                  ms,
                }) + "\n"
              );
              console.log(`[fetch] fail url=${rawUrl} status=${fr.status} err=${fr.error}`);
              return;
            }

            if (!extractedText || extractedText.length < args.minTextChars) {
              // Do NOT wipe existing content_path on a weak extraction
              failed++;
              fs.appendFileSync(
                logPath,
                JSON.stringify({
                  ts: now,
                  url: rawUrl,
                  ok: false,
                  status: fr.status,
                  error: `extracted_text_too_short(len=${(extractedText || "").length})`,
                  ms,
                }) + "\n"
              );
              console.log(`[fetch] short url=${rawUrl} len=${(extractedText || "").length}`);
              return;
            }

            const key = normalizeUrlKey(rawUrl) || rawUrl;
            const fname = `${shortHash(key)}.txt`;
            const metaName = `${shortHash(key)}.meta.json`;
            const fpath = path.join(outDir, fname);
            const metaPath = path.join(outDir, metaName);
            fs.writeFileSync(fpath, extractedText, { encoding: "utf8" });
            fs.writeFileSync(
              metaPath,
              JSON.stringify(
                {
                  url: rawUrl,
                  final_url: fr.finalUrl || "",
                  status: fr.status || 0,
                  content_type: fr.contentType || "",
                  fetched_at: now,
                  domain,
                  has_schema_markup: schema ? 1 : 0,
                  page_title: metaOut.page_title,
                  meta_description: metaOut.meta_description,
                  canonical_url: metaOut.canonical_url,
                  published_date: metaOut.published_date,
                  modified_date: metaOut.modified_date,
                },
                null,
                2
              ),
              { encoding: "utf8" }
            );
            written++;

            if (!args.noUpdateXlsx) {
              setCell(ws, rowIdx, h, "content_path", fpath);
              setCell(ws, rowIdx, h, "content_word_count", countWords(extractedText));
              setCell(ws, rowIdx, h, "has_schema_markup", schema ? 1 : 0);
              setCell(ws, rowIdx, h, "page_title", metaOut.page_title);
              setCell(ws, rowIdx, h, "meta_description", metaOut.meta_description);
              setCell(ws, rowIdx, h, "canonical_url", metaOut.canonical_url);
              setCell(ws, rowIdx, h, "published_date", metaOut.published_date);
              setCell(ws, rowIdx, h, "modified_date", metaOut.modified_date);
              setCell(ws, rowIdx, h, "meta_path", metaPath);
            }

            fetchedOk++;
            fs.appendFileSync(
              logPath,
              JSON.stringify({
                ts: now,
                url: rawUrl,
                ok: true,
                status: fr.status,
                final_url: fr.finalUrl,
                file_path: fpath,
                text_chars: extractedText.length,
                word_count: countWords(extractedText),
                has_schema: schema,
                page_title: metaOut.page_title,
                meta_description: metaOut.meta_description,
                canonical_url: metaOut.canonical_url,
                published_date: metaOut.published_date,
                modified_date: metaOut.modified_date,
                ms,
              }) + "\n"
            );
            console.log(`[fetch] ok url=${rawUrl} chars=${extractedText.length} ms=${ms} file=${fpath}`);
          })
        )
    );
  }

  await Promise.allSettled(tasks);
  if (!args.noUpdateXlsx) {
    await wb.xlsx.writeFile(args.xlsx);
  }

  console.log("Done.");
  console.log({ processed, fetchedOk, failed, skipped, skippedAdditionalOnly, written, outDir, noUpdateXlsx: args.noUpdateXlsx });
}

main().catch((e) => {
  console.error("Fatal:", e?.stack || String(e));
  process.exit(1);
});

