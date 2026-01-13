/**
 * Minimal Node.js port of the Gemini enrichment pipeline.
 *
 * What it does:
 * - Reads geo_updated.xlsx
 * - For each URL row where:
 *     - content_path exists on disk
 *     - urls.type is empty
 *   it calls Gemini with prompts/page_label_prompt_v1.txt and writes:
 *     - urls: type/content_format/tone/promotional_intensity_score/freshness_cue_strength/...
 *     - listicles + listicle_products (if present in model output)
 * - Appends an audit log line to data/llm/page_labels_gemini.jsonl
 *
 * API key: from env ONLY (never hardcode)
 *   GEMINI_API_KEY (preferred) or GOOGLE_API_KEY or GOOGLE_GENERATIVE_AI_API_KEY
 *
 * Install deps:
 *   npm install
 *
 * Run:
 *   node scripts/llm/enrich_geo_urls_with_gemini.js
 *
 * Optional args:
 *   --xlsx geo_updated.xlsx
 *   --max 50
 *   --retry-failures   (kept for compatibility; missing rows are processed regardless)
 */

/* eslint-disable no-console */
const fs = require("fs");
const path = require("path");

// Dependency (npm i exceljs)
const ExcelJS = require("exceljs");
const Bottleneck = require("bottleneck");

function getApiKey() {
  return (
    (process.env.GEMINI_API_KEY || "").trim() ||
    (process.env.GOOGLE_API_KEY || "").trim() ||
    (process.env.GOOGLE_GENERATIVE_AI_API_KEY || "").trim()
  );
}

function modelPath(model) {
  const m = (model || "").trim();
  if (!m) return "models/gemini-flash-latest";
  return m.startsWith("models/") ? m : `models/${m}`;
}

function urlDomain(u) {
  try {
    const url = new URL(u.includes("://") ? u : `https://${u}`);
    const host = (url.hostname || "").toLowerCase();
    return host.startsWith("www.") ? host.slice(4) : host;
  } catch {
    return "";
  }
}

function safeStr(v) {
  if (v === null || v === undefined) return "";
  const s = String(v).trim();
  return s.toLowerCase() === "nan" ? "" : s;
}

function parseArgs(argv) {
  const out = {
    xlsx: "geo_updated.xlsx",
    max: 0,
    retryFailures: false,
    onlyUrl: [],
    urlContains: "",
    saveEvery: 20,
    allowNoContent: false,
  };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--xlsx") out.xlsx = argv[++i];
    else if (a === "--max") out.max = Number(argv[++i] || "0") || 0;
    else if (a === "--retry-failures") out.retryFailures = true;
    else if (a === "--only-url") out.onlyUrl.push(argv[++i]);
    else if (a === "--url-contains") out.urlContains = argv[++i] || "";
    else if (a === "--save-every") out.saveEvery = Number(argv[++i] || "20") || 20;
    else if (a === "--allow-no-content") out.allowNoContent = true;
  }
  return out;
}

function loadJsonlSets(jsonlPath) {
  const ok = new Set();
  const fail = new Set();
  if (!fs.existsSync(jsonlPath)) return { ok, fail };
  const lines = fs.readFileSync(jsonlPath, "utf8").split(/\r?\n/);
  for (const line of lines) {
    if (!line.trim()) continue;
    try {
      const obj = JSON.parse(line);
      const u = safeStr(obj.url);
      if (!u) continue;
      if (obj.ok === true) ok.add(u);
      else if (obj.ok === false) fail.add(u);
    } catch {
      // ignore
    }
  }
  return { ok, fail };
}

function utcNowIso() {
  const d = new Date();
  return d.toISOString();
}

function appendJsonlLine(jsonlPath, obj) {
  fs.appendFileSync(jsonlPath, JSON.stringify({ ts: utcNowIso(), ...obj }) + "\n");
}

async function saveWorkbookWithLog({ wb, xlsxPath, reason }) {
  const started = Date.now();
  const ts = utcNowIso();
  console.log(`[xlsx] saving reason=${reason} ts=${ts} path=${xlsxPath}`);
  try {
    await wb.xlsx.writeFile(xlsxPath);
    const ms = Date.now() - started;
    console.log(`[xlsx] saved reason=${reason} ms=${ms} path=${xlsxPath}`);
  } catch (e) {
    const ms = Date.now() - started;
    const msg = String(e?.message || e);
    console.log(`[xlsx] save_failed reason=${reason} ms=${ms} path=${xlsxPath} err=${msg.slice(0, 200)}`);
    throw e;
  }
}

function fillPrompt(template, { url, title, snippet, extractedText }) {
  const dom = urlDomain(url);
  return template
    .replaceAll("{URL}", url)
    .replaceAll("{URL_DOMAIN}", dom)
    .replaceAll("{TITLE}", title || "")
    .replaceAll("{SNIPPET_OR_META_DESCRIPTION}", snippet || "")
    .replaceAll("{EXTRACTED_TEXT}", (extractedText || "").slice(0, 12000));
}

async function geminiGenerateJson({ apiKey, model, prompt, timeoutMs }) {
  const endpoint = `https://generativelanguage.googleapis.com/v1beta/${modelPath(model)}:generateContent?key=${encodeURIComponent(apiKey)}`;
  const payload = {
    contents: [{ role: "user", parts: [{ text: prompt }] }],
    generationConfig: { temperature: 0.0 },
  };

  // NOTE: No AbortController timeout by request (per user request).
  // If you want a "give up" timer without aborting the HTTP request, use Bottleneck's
  // `expiration` option when scheduling jobs (see below).
  const res = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await res.text();
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status} ${res.statusText}`);
    err.httpStatus = res.status;
    err.httpBodySnippet = body.slice(0, 800);
    throw err;
  }
  const data = JSON.parse(body);
  const outText = data?.candidates?.[0]?.content?.parts?.[0]?.text || "";
  const cleaned = outText.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/i, "").trim();
  return JSON.parse(cleaned);
}

function sheetHeaderMap(sheet) {
  const map = new Map();
  const headerRow = sheet.getRow(1);
  headerRow.eachCell((cell, col) => {
    const key = safeStr(cell.value);
    if (key) map.set(key, col);
  });
  return map;
}

function getCell(sheet, rowIdx, headerMap, colName) {
  const col = headerMap.get(colName);
  if (!col) return "";
  return safeStr(sheet.getRow(rowIdx).getCell(col).value);
}

function setCell(sheet, rowIdx, headerMap, colName, value) {
  const col = headerMap.get(colName);
  if (!col) return;
  sheet.getRow(rowIdx).getCell(col).value = value;
}

function upsertByKey(sheet, headerMap, keyCol, keyVal, obj, overwrite) {
  const keyIdx = headerMap.get(keyCol);
  if (!keyIdx) return;
  // find
  let targetRow = 0;
  for (let r = 2; r <= sheet.rowCount; r++) {
    const v = safeStr(sheet.getRow(r).getCell(keyIdx).value);
    if (v === keyVal) {
      targetRow = r;
      break;
    }
  }
  if (!targetRow) {
    targetRow = sheet.rowCount + 1;
    sheet.getRow(targetRow).getCell(keyIdx).value = keyVal;
  }

  for (const [k, v] of Object.entries(obj || {})) {
    if (!headerMap.has(k)) continue;
    const val = v === null || v === undefined ? "" : v;
    if (val === "") continue;
    const cur = getCell(sheet, targetRow, headerMap, k);
    if (!overwrite && cur) continue;
    setCell(sheet, targetRow, headerMap, k, val);
  }
}

function buildExistingListicleProductKeys(wsProducts, hp) {
  const keys = new Set();
  if (!wsProducts) return keys;
  const need = ["listicle_url", "position_in_listicle", "product_name"];
  if (!need.every((k) => hp.has(k))) return keys;
  const cList = hp.get("listicle_url");
  const cPos = hp.get("position_in_listicle");
  const cName = hp.get("product_name");
  for (let r = 2; r <= wsProducts.rowCount; r++) {
    const row = wsProducts.getRow(r);
    const lk = safeStr(row.getCell(cList).value);
    const pos = safeStr(row.getCell(cPos).value);
    const pn = safeStr(row.getCell(cName).value);
    if (!lk || !pos || !pn) continue;
    keys.add(`${lk}|||${pos}|||${pn}`);
  }
  return keys;
}

async function main() {
  const args = parseArgs(process.argv);
  const apiKey = getApiKey();
  if (!apiKey) {
    console.error("Missing GEMINI_API_KEY env var.");
    process.exit(2);
  }

  const model = process.env.GEMINI_MODEL || "gemini-1.5-flash-latest";
  // Kept for compatibility, but not used for AbortController anymore.
  // You can use it as Bottleneck job expiration (see JOB_EXPIRATION_MS).
  const timeoutMs = Number(process.env.GEMINI_TIMEOUT_MS || "900000");
  const concurrency = Number(process.env.CONCURRENCY || "5");
  const minTimeMs = Number(process.env.MIN_TIME_MS || "400"); // spacing between starting jobs
  const jobExpirationMs = Number(process.env.JOB_EXPIRATION_MS || "0"); // 0 = no expiration

  const apiLimiter = new Bottleneck({
    maxConcurrent: Math.max(1, concurrency),
    minTime: Math.max(0, minTimeMs),
  });
  // Serialize workbook writes (ExcelJS is not safe to mutate from multiple in-flight tasks)
  const writeLimiter = new Bottleneck({ maxConcurrent: 1, minTime: 0 });

  const jsonlPath = path.join("data", "llm", "page_labels_gemini.jsonl");
  fs.mkdirSync(path.dirname(jsonlPath), { recursive: true });
  const { ok: okUrls } = loadJsonlSets(jsonlPath);

  const promptTemplate = fs.readFileSync(path.join("prompts", "page_label_prompt_v1.txt"), "utf8");

  const wb = new ExcelJS.Workbook();
  await wb.xlsx.readFile(args.xlsx);

  const wsUrls = wb.getWorksheet("urls");
  const wsBing = wb.getWorksheet("bing_results");
  const wsCit = wb.getWorksheet("citations");
  const wsListicles = wb.getWorksheet("listicles");
  const wsProducts = wb.getWorksheet("listicle_products");

  const hu = sheetHeaderMap(wsUrls);
  const hb = sheetHeaderMap(wsBing);
  const hc = sheetHeaderMap(wsCit);
  const hl = sheetHeaderMap(wsListicles);
  const hp = sheetHeaderMap(wsProducts);
  const existingProductKeys = buildExistingListicleProductKeys(wsProducts, hp);

  // url -> (title, snippet)
  const meta = new Map();
  // Prefer URL-sheet metadata (if present) because it's closer to "meta description" than Bing snippets.
  if (wsUrls && hu.has("url")) {
    const hasTitle = hu.has("page_title");
    const hasDesc = hu.has("meta_description");
    const hasPub = hu.has("published_date");
    const hasMod = hu.has("modified_date");
    if (hasTitle || hasDesc || hasPub || hasMod) {
      for (let r = 2; r <= wsUrls.rowCount; r++) {
        const u = getCell(wsUrls, r, hu, "url");
        if (!u || meta.has(u)) continue;
        const t = hasTitle ? getCell(wsUrls, r, hu, "page_title") : "";
        const d = hasDesc ? getCell(wsUrls, r, hu, "meta_description") : "";
        const pub = hasPub ? getCell(wsUrls, r, hu, "published_date") : "";
        const mod = hasMod ? getCell(wsUrls, r, hu, "modified_date") : "";
        let snippet = d;
        if (pub || mod) {
          const parts = [];
          if (pub) parts.push(`Published: ${pub}`);
          if (mod) parts.push(`Updated: ${mod}`);
          snippet = [d, parts.join(" | ")].filter(Boolean).join("\n");
        }
        if (t || snippet) meta.set(u, { title: t, snippet });
      }
    }
  }
  if (wsBing && hb.has("url")) {
    for (let r = 2; r <= wsBing.rowCount; r++) {
      const u = getCell(wsBing, r, hb, "url");
      if (!u || meta.has(u)) continue;
      const t = getCell(wsBing, r, hb, "result_title");
      const s = getCell(wsBing, r, hb, "snippet");
      if (t || s) meta.set(u, { title: t, snippet: s });
    }
  }
  if (wsCit && hc.has("url")) {
    for (let r = 2; r <= wsCit.rowCount; r++) {
      const u = getCell(wsCit, r, hc, "url");
      if (!u || meta.has(u)) continue;
      const t = getCell(wsCit, r, hc, "citation_title");
      if (t) meta.set(u, { title: t, snippet: "" });
    }
  }

  let processed = 0;
  let labeled = 0;
  let failed = 0;
  let skipped = 0;

  const onlyUrls = new Set((args.onlyUrl || []).map((u) => safeStr(u)).filter(Boolean));
  const contains = safeStr(args.urlContains).toLowerCase();

  const writeCheckpoint = async () => {
    await saveWorkbookWithLog({ wb, xlsxPath: args.xlsx, reason: "checkpoint" });
    console.log(`[save] checkpoint processed=${processed} labeled=${labeled} failed=${failed} skipped=${skipped}`);
  };

  let writesSinceCheckpoint = 0;
  const saveEvery = Math.max(1, Number(args.saveEvery || 20) || 20);
  const tasks = [];

  for (let r = 2; r <= wsUrls.rowCount; r++) {
    const url = getCell(wsUrls, r, hu, "url");
    if (!url) continue;

    if (onlyUrls.size && !onlyUrls.has(url)) continue;
    if (!onlyUrls.size && contains && !url.toLowerCase().includes(contains)) continue;

    const typeVal = getCell(wsUrls, r, hu, "type");
    const cp = getCell(wsUrls, r, hu, "content_path");
    const hasCp = cp && fs.existsSync(cp);

    // Default behavior: require content_path to exist on disk.
    // Optional: --allow-no-content lets us label type using title/snippet/meta only (useful for 403/blocked fetches).
    if (!hasCp && !args.allowNoContent) continue;

    // resume behavior based on jsonl
    if (typeVal) {
      skipped++;
      continue;
    }
    // If JSONL says ok:true but Excel still has empty type (e.g. crash before save),
    // DO NOT skip; re-run so the workbook gets filled.
    if (okUrls.has(url) && !typeVal) {
      // fallthrough (process)
    } else if (okUrls.has(url)) {
      skipped++;
      continue;
    }
    // We intentionally DO NOT skip previously-failed URLs when the Excel row is still missing.
    // JSONL is an attempt log; Excel completeness is the real "done-ness" gate.

    processed++;
    if (args.max && processed > args.max) break;

    const rowIdx = r;
    tasks.push(
      apiLimiter.schedule(
        jobExpirationMs > 0 ? { expiration: jobExpirationMs } : {},
        async () => {
          console.log(`[gemini] start url=${url}`);
          const extractedText = hasCp ? fs.readFileSync(cp, "utf8") : "";
          const m = meta.get(url) || { title: "", snippet: "" };
          const prompt = fillPrompt(promptTemplate, { url, title: m.title, snippet: m.snippet, extractedText });
          const parsed = await geminiGenerateJson({ apiKey, model, prompt, timeoutMs });
          return { url, parsed, rowIdx };
        }
      )
        .then(({ url, parsed, rowIdx }) =>
          writeLimiter.schedule(async () => {
            // urls
            const uo = parsed?.urls;
            if (uo && typeof uo === "object") {
              for (const k of Object.keys(uo)) {
                if (!hu.has(k)) continue;
                setCell(wsUrls, rowIdx, hu, k, uo[k]);
              }
            }

            // listicles
            const lo = parsed?.listicles;
            if (lo && typeof lo === "object") {
              upsertByKey(wsListicles, hl, "listicle_url", url, lo, false);
            }

            // listicle_products (idempotent-ish)
            const po = parsed?.listicle_products;
            if (Array.isArray(po)) {
              for (const item of po) {
                if (!item || typeof item !== "object") continue;
                item.listicle_url = safeStr(item.listicle_url) || url;
                const lk = safeStr(item.listicle_url);
                const pos = safeStr(item.position_in_listicle);
                const pn = safeStr(item.product_name);
                const key = lk && pos && pn ? `${lk}|||${pos}|||${pn}` : "";
                if (key && existingProductKeys.has(key)) continue;
                const newRow = wsProducts.addRow({});
                for (const [k, v] of Object.entries(item)) {
                  if (!hp.has(k)) continue;
                  newRow.getCell(hp.get(k)).value = v;
                }
                if (key) existingProductKeys.add(key);
              }
            }

            appendJsonlLine(jsonlPath, { url, ok: true, model, response: parsed });
            console.log(`[gemini] ok url=${url}`);
            labeled++;

            writesSinceCheckpoint++;
            if (writesSinceCheckpoint >= saveEvery) {
              writesSinceCheckpoint = 0;
              await writeCheckpoint();
            }
          })
        )
        .catch((e) =>
          writeLimiter.schedule(async () => {
            const err = {
              type: e?.name || "Error",
              message: String(e?.message || e).slice(0, 1200),
            };
            if (e?.httpStatus) err.http_status = e.httpStatus;
            if (e?.httpBodySnippet) err.http_body_snippet = e.httpBodySnippet;

            appendJsonlLine(jsonlPath, { url, ok: false, model, error: err });
            console.log(`[gemini] fail url=${url} err=${err.type}: ${err.message.slice(0, 120)}`);
            failed++;

            writesSinceCheckpoint++;
            if (writesSinceCheckpoint >= saveEvery) {
              writesSinceCheckpoint = 0;
              await writeCheckpoint();
            }
          })
        )
    );
  }

  // Wait for all scheduled work to finish (or fail)
  await Promise.allSettled(tasks);

  await saveWorkbookWithLog({ wb, xlsxPath: args.xlsx, reason: "final" });
  console.log("Done.");
  console.log({ processed, labeled, failed, skipped });
}

main().catch((e) => {
  console.error("Fatal:", e?.stack || String(e));
  process.exit(1);
});

