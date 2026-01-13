/**
 * Compute 3-way correlation:
 *   ChatGPT inline item -> cited listicle URL -> Bing rank of that listicle -> product position in listicle
 *
 * Inputs: geo_updated.xlsx (sheets: citations, bing_results, listicle_products, urls)
 * Output: CSV file for downstream analysis.
 *
 * Run:
 *   node scripts/metrics/compute_listicle_3way_correlation.js --xlsx geo_updated.xlsx --out data/metrics_listicle_3way.csv
 *
 * Options:
 *   --fuzzy                enable token-Jaccard matching for product names
 *   --min-sim 0.6          minimum similarity for fuzzy matching
 */

/* eslint-disable no-console */
const fs = require("fs");
const path = require("path");
const ExcelJS = require("exceljs");

function parseArgs(argv) {
  const out = { xlsx: "geo_updated.xlsx", out: "data/metrics_listicle_3way.csv", fuzzy: false, minSim: 0.6 };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--xlsx") out.xlsx = argv[++i];
    else if (a === "--out") out.out = argv[++i];
    else if (a === "--fuzzy") out.fuzzy = true;
    else if (a === "--min-sim") out.minSim = Number(argv[++i] || "0.6") || 0.6;
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

function getCell(ws, r, h, name) {
  const c = h.get(name);
  if (!c) return "";
  return safeStr(ws.getRow(r).getCell(c).value);
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
    // drop fragment always
    // keep query but drop common tracking
    const dropExact = new Set(["gclid", "fbclid", "msclkid", "yclid", "mc_cid", "mc_eid", "igshid", "ref", "ref_src"]);
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

function normalizeProductName(raw) {
  let s = safeStr(raw);
  if (!s) return "";
  // strip leading numbering like "3. " or "#3 "
  s = s.replace(/^\s*(?:#?\d+[\).\s-]+)+/g, "");
  // if the name includes "Brand – description", keep the left side (usually the canonical product/brand)
  const parts = s.split(/\s*[–—\-:|]\s*/);
  if (parts[0] && parts[0].length >= 2) s = parts[0];
  // drop parenthetical suffixes
  s = s.replace(/\s*\([^)]*\)\s*/g, " ");
  // normalize punctuation/whitespace
  s = s
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  return s;
}

function tokenSet(s) {
  const t = normalizeProductName(s);
  if (!t) return new Set();
  // light stopword removal to reduce false mismatches
  const stop = new Set(["the", "a", "an", "best", "for", "and", "to", "of", "in", "with", "free"]);
  const toks = t.split(" ").filter((x) => x && !stop.has(x));
  return new Set(toks);
}

function jaccard(a, b) {
  const A = tokenSet(a);
  const B = tokenSet(b);
  if (!A.size || !B.size) return 0;
  let inter = 0;
  for (const x of A) if (B.has(x)) inter++;
  const uni = A.size + B.size - inter;
  return uni ? inter / uni : 0;
}

function csvEscape(v) {
  const s = v === null || v === undefined ? "" : String(v);
  if (/[,"\r\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

async function main() {
  const args = parseArgs(process.argv);
  fs.mkdirSync(path.dirname(args.out), { recursive: true });

  const wb = new ExcelJS.Workbook();
  await wb.xlsx.readFile(args.xlsx);

  const wsC = wb.getWorksheet("citations");
  const wsB = wb.getWorksheet("bing_results");
  const wsP = wb.getWorksheet("listicle_products");
  const wsU = wb.getWorksheet("urls");
  if (!wsC || !wsB || !wsP || !wsU) throw new Error("Missing required sheets: citations, bing_results, listicle_products, urls");

  const hc = headerMap(wsC);
  const hb = headerMap(wsB);
  const hp = headerMap(wsP);
  const hu = headerMap(wsU);

  for (const col of ["run_id", "citation_type", "url", "item_position", "item_name"]) {
    if (!hc.has(col)) throw new Error(`citations missing required column: ${col}`);
  }
  for (const col of ["run_id", "result_rank", "url"]) {
    if (!hb.has(col)) throw new Error(`bing_results missing required column: ${col}`);
  }
  for (const col of ["listicle_url", "product_name", "position_in_listicle"]) {
    if (!hp.has(col)) throw new Error(`listicle_products missing required column: ${col}`);
  }
  if (!hu.has("url") || !hu.has("type")) throw new Error("urls missing required columns: url, type");

  // url_key -> type (from urls sheet)
  const urlTypeByKey = new Map();
  for (let r = 2; r <= wsU.rowCount; r++) {
    const url = getCell(wsU, r, hu, "url");
    const type = getCell(wsU, r, hu, "type");
    if (!url || !type) continue;
    urlTypeByKey.set(normalizeUrlKey(url), type);
  }

  // listicle_url_key -> array of listicle product rows
  const productsByListicle = new Map();
  for (let r = 2; r <= wsP.rowCount; r++) {
    const listicleUrl = getCell(wsP, r, hp, "listicle_url");
    const productName = getCell(wsP, r, hp, "product_name");
    if (!listicleUrl || !productName) continue;
    const key = normalizeUrlKey(listicleUrl);
    const row = {
      product_name: productName,
      product_domain: getCell(wsP, r, hp, "product_domain"),
      product_url: getCell(wsP, r, hp, "product_url"),
      position_in_listicle: Number(getCell(wsP, r, hp, "position_in_listicle") || "0") || 0,
      mention_type: getCell(wsP, r, hp, "mention_type"),
      is_host_domain: getCell(wsP, r, hp, "is_host_domain"),
      notes: getCell(wsP, r, hp, "notes"),
    };
    if (!productsByListicle.has(key)) productsByListicle.set(key, []);
    productsByListicle.get(key).push(row);
  }

  // (run_id, url_key) -> best rank
  const bingRank = new Map(); // `${run_id}|||${url_key}` -> rank
  for (let r = 2; r <= wsB.rowCount; r++) {
    const runId = getCell(wsB, r, hb, "run_id");
    const url = getCell(wsB, r, hb, "url");
    const rank = Number(getCell(wsB, r, hb, "result_rank") || "0") || 0;
    if (!runId || !url || !rank) continue;
    const key = `${runId}|||${normalizeUrlKey(url)}`;
    const cur = bingRank.get(key);
    if (!cur || rank < cur) bingRank.set(key, rank);
  }

  const outRows = [];
  let inlineRows = 0;
  let inlineListicleCites = 0;
  let matched = 0;
  let matchedAndInBing = 0;

  for (let r = 2; r <= wsC.rowCount; r++) {
    const citationType = getCell(wsC, r, hc, "citation_type");
    if (citationType !== "inline") continue;
    inlineRows++;

    const runId = getCell(wsC, r, hc, "run_id");
    const citedUrl = getCell(wsC, r, hc, "url");
    const itemPos = getCell(wsC, r, hc, "item_position");
    const itemName = getCell(wsC, r, hc, "item_name");
    if (!runId || !citedUrl || !itemPos || !itemName) continue;

    const listicleKey = normalizeUrlKey(citedUrl);
    const urlType = urlTypeByKey.get(listicleKey) || "";
    const hasProducts = productsByListicle.has(listicleKey);
    const isListicle = urlType === "listicle" || hasProducts;
    if (!isListicle) continue;
    inlineListicleCites++;

    const bRank = bingRank.get(`${runId}|||${listicleKey}`) || "";
    const candidates = productsByListicle.get(listicleKey) || [];

    // match item_name -> listicle product_name
    let best = null;
    const want = normalizeProductName(itemName);
    for (const p of candidates) {
      const cand = normalizeProductName(p.product_name);
      if (!cand) continue;
      if (want && cand === want) {
        best = { ...p, match_method: "strict", name_similarity: 1 };
        break;
      }
      if (args.fuzzy) {
        const sim = jaccard(itemName, p.product_name);
        if (sim >= args.minSim && (!best || sim > best.name_similarity)) {
          best = { ...p, match_method: "fuzzy", name_similarity: sim };
        }
      }
    }

    const match = best || {
      product_name: "",
      product_domain: "",
      product_url: "",
      position_in_listicle: "",
      mention_type: "",
      is_host_domain: "",
      notes: "",
      match_method: "none",
      name_similarity: 0,
    };

    if (match.match_method !== "none") matched++;
    if (match.match_method !== "none" && bRank) matchedAndInBing++;

    outRows.push({
      run_id: runId,
      item_position: itemPos,
      item_name: itemName,
      cited_listicle_url: citedUrl,
      cited_listicle_type: urlType || (hasProducts ? "listicle" : ""),
      bing_rank_of_listicle: bRank,
      citation_in_group_rank: getCell(wsC, r, hc, "citation_in_group_rank"),
      citation_group_size: getCell(wsC, r, hc, "citation_group_size"),
      match_method: match.match_method,
      name_similarity: match.name_similarity,
      matched_product_name: match.product_name,
      listicle_position: match.position_in_listicle,
      mention_type: match.mention_type,
      product_domain: match.product_domain,
      product_url: match.product_url,
      product_notes: match.notes,
    });
  }

  const headers = [
    "run_id",
    "item_position",
    "item_name",
    "cited_listicle_url",
    "cited_listicle_type",
    "bing_rank_of_listicle",
    "citation_in_group_rank",
    "citation_group_size",
    "match_method",
    "name_similarity",
    "matched_product_name",
    "listicle_position",
    "mention_type",
    "product_domain",
    "product_url",
    "product_notes",
  ];
  const lines = [headers.join(",")];
  for (const row of outRows) {
    lines.push(headers.map((h) => csvEscape(row[h] ?? "")).join(","));
  }
  fs.writeFileSync(args.out, lines.join("\n"), "utf8");

  console.log("Wrote:", args.out);
  console.log({
    inline_rows: inlineRows,
    inline_listicle_citations: inlineListicleCites,
    matched_products: matched,
    matched_products_and_listicle_in_bing: matchedAndInBing,
    fuzzy: args.fuzzy,
    minSim: args.minSim,
  });
}

main().catch((e) => {
  console.error("Fatal:", e?.stack || String(e));
  process.exit(1);
});

