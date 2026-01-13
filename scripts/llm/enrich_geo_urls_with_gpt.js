/**
 * OpenAI GPT-based alternative to the Gemini enrichment pipeline.
 *
 * IMPORTANT (research transparency):
 * - If you run this script, you are using OpenAI (GPT) for labeling (not Gemini).
 * - This script appends an audit log line to: data/llm/page_labels_gpt.jsonl
 *
 * API key: from env ONLY (never hardcode)
 *   OPEN_AI_KEY
 *
 * Model:
 *   OPENAI_MODEL (default: gpt-5-mini)
 *
 * Run:
 *   OPEN_AI_KEY=... node scripts/llm/enrich_geo_urls_with_gpt.js --xlsx geo_updated.xlsx --save-every 1
 *
 * Optional args:
 *   --xlsx geo_updated.xlsx
 *   --max 50
 *   --only-url <url>        (can be repeated)
 *   --url-contains <substr>
 *   --save-every N
 *   --allow-no-content
 */

/* eslint-disable no-console */
const fs = require("fs");
const path = require("path");
const ExcelJS = require("exceljs");
const Bottleneck = require("bottleneck");
const OpenAI = require("openai");

function getOpenAiKey() {
  return (process.env.OPEN_AI_KEY || "").trim();
}

function safeStr(v) {
  if (v === null || v === undefined) return "";
  const s = String(v).trim();
  return s.toLowerCase() === "nan" ? "" : s;
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

function utcNowIso() {
  return new Date().toISOString();
}

function appendJsonlLine(jsonlPath, obj) {
  fs.appendFileSync(jsonlPath, JSON.stringify({ ts: utcNowIso(), ...obj }) + "\n");
}

async function saveWorkbookWithLog({ wb, xlsxPath, reason }) {
  const started = Date.now();
  const ts = utcNowIso();
  console.log(`[xlsx] saving reason=${reason} ts=${ts} path=${xlsxPath}`);
  await wb.xlsx.writeFile(xlsxPath);
  const ms = Date.now() - started;
  console.log(`[xlsx] saved reason=${reason} ms=${ms} path=${xlsxPath}`);
}

function parseArgs(argv) {
  const out = {
    xlsx: "geo_updated.xlsx",
    max: 0,
    onlyUrl: [],
    urlContains: "",
    saveEvery: 20,
    allowNoContent: false,
  };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--xlsx") out.xlsx = argv[++i];
    else if (a === "--max") out.max = Number(argv[++i] || "0") || 0;
    else if (a === "--only-url") out.onlyUrl.push(argv[++i]);
    else if (a === "--url-contains") out.urlContains = argv[++i] || "";
    else if (a === "--save-every") out.saveEvery = Number(argv[++i] || "20") || 20;
    else if (a === "--allow-no-content") out.allowNoContent = true;
  }
  return out;
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

function fillPrompt(template, { url, title, snippet, extractedText }) {
  const dom = urlDomain(url);
  return template
    .replaceAll("{URL}", url)
    .replaceAll("{URL_DOMAIN}", dom)
    .replaceAll("{TITLE}", title || "")
    .replaceAll("{SNIPPET_OR_META_DESCRIPTION}", snippet || "")
    .replaceAll("{EXTRACTED_TEXT}", (extractedText || "").slice(0, 12000));
}

function extractTextFromOpenAiResponse(data) {
  if (!data) return "";
  if (typeof data.output_text === "string") return data.output_text;
  if (Array.isArray(data.output)) {
    for (const o of data.output) {
      const content = o?.content;
      if (!Array.isArray(content)) continue;
      for (const p of content) {
        if (typeof p?.text === "string") return p.text;
        if (typeof p?.output_text === "string") return p.output_text;
      }
    }
  }
  // Fallback for chat-completions shaped responses
  const cc = data?.choices?.[0]?.message?.content;
  if (typeof cc === "string") return cc;
  return "";
}

async function openAiGenerateJson({ apiKey, model, prompt }) {
  const baseURL = (process.env.OPENAI_BASE_URL || "").trim() || undefined;
  const client = new OpenAI({ apiKey, baseURL });

  try {
    // Use the Responses API with the input format shown in OpenAI docs/UI.
    const response = await client.responses.create({
      model,
      input: [
        {
          role: "system",
          content: [{ type: "input_text", text: "Return ONLY valid JSON. No markdown. No commentary." }],
        },
        {
          role: "user",
          content: [{ type: "input_text", text: prompt }],
        },
      ],
    });

    const outText = extractTextFromOpenAiResponse(response);
    const cleaned = String(outText).replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/i, "").trim();
    return JSON.parse(cleaned);
  } catch (e) {
    // Normalize OpenAI SDK errors to match our logging
    const err = new Error(String(e?.message || e));
    err.name = e?.name || "Error";
    err.httpStatus = e?.status || e?.response?.status || 0;
    const body = e?.error ? JSON.stringify(e.error) : (e?.response?.data ? JSON.stringify(e.response.data) : "");
    if (body) err.httpBodySnippet = body.slice(0, 800);
    throw err;
  }
}

async function main() {
  const args = parseArgs(process.argv);
  const apiKey = getOpenAiKey();
  if (!apiKey) {
    console.error("Missing OPEN_AI_KEY env var.");
    process.exit(2);
  }

  const model = (process.env.OPENAI_MODEL || "gpt-5-mini").trim();
  const concurrency = Number(process.env.CONCURRENCY || "3");
  const minTimeMs = Number(process.env.MIN_TIME_MS || "800");
  const jobExpirationMs = Number(process.env.JOB_EXPIRATION_MS || "0");

  const apiLimiter = new Bottleneck({
    maxConcurrent: Math.max(1, concurrency),
    minTime: Math.max(0, minTimeMs),
  });
  const writeLimiter = new Bottleneck({ maxConcurrent: 1, minTime: 0 });

  const jsonlPath = path.join("data", "llm", "page_labels_gpt.jsonl");
  fs.mkdirSync(path.dirname(jsonlPath), { recursive: true });

  const promptTemplate = fs.readFileSync(path.join("prompts", "page_label_prompt_v1.txt"), "utf8");

  const wb = new ExcelJS.Workbook();
  await wb.xlsx.readFile(args.xlsx);
  const wsUrls = wb.getWorksheet("urls");
  const wsListicles = wb.getWorksheet("listicles");
  const wsProducts = wb.getWorksheet("listicle_products");
  if (!wsUrls) throw new Error("Workbook missing sheet: urls");
  if (!wsListicles) throw new Error("Workbook missing sheet: listicles");
  if (!wsProducts) throw new Error("Workbook missing sheet: listicle_products");

  const hu = sheetHeaderMap(wsUrls);
  const hl = sheetHeaderMap(wsListicles);
  const hp = sheetHeaderMap(wsProducts);
  const existingProductKeys = buildExistingListicleProductKeys(wsProducts, hp);

  // url -> (title, snippet)
  const meta = new Map();
  if (wsUrls && hu.has("url")) {
    const hasTitle = hu.has("page_title");
    const hasDesc = hu.has("meta_description");
    const hasSnippet = hu.has("snippet");
    for (let r = 2; r <= wsUrls.rowCount; r++) {
      const u = getCell(wsUrls, r, hu, "url");
      if (!u || meta.has(u)) continue;
      const t = hasTitle ? getCell(wsUrls, r, hu, "page_title") : "";
      const d = hasDesc ? getCell(wsUrls, r, hu, "meta_description") : "";
      const s = hasSnippet ? getCell(wsUrls, r, hu, "snippet") : "";
      meta.set(u, { title: t, snippet: d || s || "" });
    }
  }

  let processed = 0;
  let labeled = 0;
  let failed = 0;
  let skipped = 0;
  let writesSinceCheckpoint = 0;
  const saveEvery = Math.max(1, Number(args.saveEvery || 20) || 20);

  const onlyUrls = new Set((args.onlyUrl || []).map((u) => safeStr(u)).filter(Boolean));
  const contains = safeStr(args.urlContains).toLowerCase();

  const writeCheckpoint = async () => {
    await saveWorkbookWithLog({ wb, xlsxPath: args.xlsx, reason: "checkpoint" });
    console.log(`[save] checkpoint processed=${processed} labeled=${labeled} failed=${failed} skipped=${skipped}`);
  };

  const tasks = [];
  for (let r = 2; r <= wsUrls.rowCount; r++) {
    const url = getCell(wsUrls, r, hu, "url");
    if (!url) continue;

    if (onlyUrls.size && !onlyUrls.has(url)) continue;
    if (!onlyUrls.size && contains && !url.toLowerCase().includes(contains)) continue;

    const typeVal = getCell(wsUrls, r, hu, "type");
    const cp = getCell(wsUrls, r, hu, "content_path");
    const hasCp = cp && fs.existsSync(cp);
    if (!hasCp && !args.allowNoContent) continue;

    if (typeVal) {
      skipped++;
      continue;
    }

    processed++;
    if (args.max && processed > args.max) break;

    const rowIdx = r;
    tasks.push(
      apiLimiter
        .schedule(jobExpirationMs > 0 ? { expiration: jobExpirationMs } : {}, async () => {
          console.log(`[gpt] start url=${url}`);
          const extractedText = hasCp ? fs.readFileSync(cp, "utf8") : "";
          const m = meta.get(url) || { title: "", snippet: "" };
          const prompt = fillPrompt(promptTemplate, { url, title: m.title, snippet: m.snippet, extractedText });
          const parsed = await openAiGenerateJson({ apiKey, model, prompt });
          return { url, parsed, rowIdx };
        })
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

            appendJsonlLine(jsonlPath, { url, ok: true, provider: "openai", model, response: parsed });
            console.log(`[gpt] ok url=${url}`);
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
            appendJsonlLine(jsonlPath, { url, ok: false, provider: "openai", model, error: err });
            console.log(`[gpt] fail url=${url} err=${err.type}: ${err.message.slice(0, 120)}`);
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

  await Promise.allSettled(tasks);
  await saveWorkbookWithLog({ wb, xlsxPath: args.xlsx, reason: "final" });
  console.log("Done.");
  console.log({ processed, labeled, failed, skipped });
}

main().catch((e) => {
  console.error("Fatal:", e?.stack || String(e));
  process.exit(1);
});

