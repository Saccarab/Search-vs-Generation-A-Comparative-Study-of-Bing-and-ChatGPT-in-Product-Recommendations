import fs from "fs";
import path from "path";
import ExcelJS from "exceljs";

function parseArgs(argv) {
  const out = {
    rawDir: path.join("datapass", "raw_network_responses"),
    xlsx: "", // optional
    jsonl: "datapass/page_labels_gemini.jsonl,datapass/page_labels_gpt.jsonl", // comma list of existing labels
    outCsv: path.join("data", "enrichment", "enrichment_queue.csv"),
    account: "all", // all|personal|enterprise
    include: "cited,additional,rejected", // comma list
    onlyMissingType: true,
    skipDomains:
      "wikipedia.org,reddit.com,arxiv.org,scholar.google.com,semanticscholar.org,github.com,youtube.com,youtu.be,medium.com,substack.com",
  };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--raw-dir") out.rawDir = argv[++i];
    else if (a === "--xlsx") out.xlsx = argv[++i];
    else if (a === "--out") out.outCsv = argv[++i];
    else if (a === "--account") out.account = String(argv[++i] || "all");
    else if (a === "--include") out.include = String(argv[++i] || out.include);
    else if (a === "--only-missing-type") out.onlyMissingType = true;
    else if (a === "--include-has-type") out.onlyMissingType = false;
    else if (a === "--skip-domains") out.skipDomains = String(argv[++i] || out.skipDomains);
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

function urlDomain(u) {
  try {
    const url = new URL(u.includes("://") ? u : `https://${u}`);
    const host = (url.hostname || "").toLowerCase();
    return host.startsWith("www.") ? host.slice(4) : host;
  } catch {
    return "";
  }
}

function normalizeUrlKey(rawUrl) {
  // Mirrors the intent of scripts/enrich_urls.py normalize_url_key():
  // - lowercase host, drop scheme, drop www, drop fragment
  // - drop trailing slash (except root)
  // - drop common tracking params (utm_*, gclid, fbclid, msclkid, ...)
  const s = safeStr(rawUrl);
  if (!s) return "";
  let u;
  try {
    u = new URL(s.includes("://") ? s : `https://${s}`);
  } catch {
    return "";
  }
  let host = (u.hostname || "").toLowerCase();
  if (host.startsWith("www.")) host = host.slice(4);
  let pathname = u.pathname || "/";
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
    "spm",
  ]);
  const kept = [];
  for (const [k, v] of u.searchParams.entries()) {
    const lk = k.toLowerCase();
    if (lk.startsWith("utm_")) continue;
    if (dropExact.has(lk)) continue;
    kept.push([k, v]);
  }
  kept.sort((a, b) => a[0].localeCompare(b[0]));
  const qs = kept.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join("&");
  return `${host}${pathname}${qs ? `?${qs}` : ""}`;
}

function parseJsonMaybeString(v, fallback) {
  if (v === null || v === undefined) return fallback;
  if (typeof v === "object") return v;
  const s = String(v).trim();
  if (!s) return fallback;
  try {
    return JSON.parse(s);
  } catch {
    return fallback;
  }
}

function addUrlHit(map, { url, runId, accountType, bucket }) {
  const urlStr = safeStr(url);
  if (!urlStr) return;
  const urlKey = normalizeUrlKey(urlStr);
  if (!urlKey) return;
  const domain = urlDomain(urlStr);

  const cur =
    map.get(urlKey) ||
    ({
      url: urlStr,
      url_key: urlKey,
      domain,
      account_types: new Set(),
      cited_runs: new Set(),
      additional_runs: new Set(),
      rejected_runs: new Set(),
      sources: new Set(),
    });

  cur.account_types.add(accountType);
  cur.sources.add(bucket);
  if (bucket === "cited") cur.cited_runs.add(runId);
  else if (bucket === "additional") cur.additional_runs.add(runId);
  else if (bucket === "rejected") cur.rejected_runs.add(runId);

  // keep first url we saw (fine)
  map.set(urlKey, cur);
}

async function loadUrlsSheetIndex(xlsxPath) {
  if (!xlsxPath) return null;
  const wb = new ExcelJS.Workbook();
  await wb.xlsx.readFile(xlsxPath);
  const ws = wb.getWorksheet("urls");
  if (!ws) throw new Error("Workbook missing sheet: urls");

  const h = new Map();
  ws.getRow(1).eachCell((c, i) => {
    const k = safeStr(c.value);
    if (k) h.set(k, i);
  });
  const cUrl = h.get("url");
  const cType = h.get("type");
  if (!cUrl) throw new Error("urls sheet missing required column: url");

  const idx = new Map(); // url_key -> { url, type }
  for (let r = 2; r <= ws.rowCount; r++) {
    const u = safeStr(ws.getRow(r).getCell(cUrl).value);
    if (!u) continue;
    const k = normalizeUrlKey(u);
    if (!k) continue;
    const t = cType ? safeStr(ws.getRow(r).getCell(cType).value) : "";
    idx.set(k, { url: u, type: t });
  }
  return idx;
}

function loadJsonlIndex(jsonlPaths) {
  const idx = new Map();
  if (!jsonlPaths) return idx;
  const paths = jsonlPaths.split(",").map(p => p.trim()).filter(Boolean);
  for (const p of paths) {
    if (!fs.existsSync(p)) continue;
    const content = fs.readFileSync(p, "utf8");
    const lines = content.split("\n");
    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const obj = JSON.parse(line);
        const u = safeStr(obj.url);
        if (!u) continue;
        const k = normalizeUrlKey(u);
        if (!k) continue;
        // If it has a type or ok=true, count it as labeled
        if (obj.type || obj.ok === true) {
          idx.set(k, { url: u, type: obj.type || "labeled" });
        }
      } catch (e) {
        // skip
      }
    }
  }
  return idx;
}

async function main() {
  const args = parseArgs(process.argv);

  const include = new Set(
    String(args.include || "")
      .split(",")
      .map((s) => s.trim().toLowerCase())
      .filter(Boolean)
  );
  const accountFilter = String(args.account || "all").trim().toLowerCase();

  const skipDomains = new Set(
    String(args.skipDomains || "")
      .split(",")
      .map((s) => s.trim().toLowerCase())
      .filter(Boolean)
  );

  const urlsSheetIdx = await loadUrlsSheetIndex(args.xlsx);
  const jsonlIdx = loadJsonlIndex(args.jsonl);

  const files = fs
    .readdirSync(args.rawDir)
    .filter((f) => f.endsWith(".json") && !f.startsWith("_"))
    .map((f) => path.join(args.rawDir, f));

  const urlMap = new Map(); // url_key -> aggregate

  for (const fp of files) {
    const raw = JSON.parse(fs.readFileSync(fp, "utf8"));
    const runId = safeStr(raw.run_id || raw.chatgpt_run_id || `${raw.prompt_id || ""}_r${raw.run_number || ""}`).trim();
    const accountType = safeStr(raw.account_type || "unknown").toLowerCase();
    if (accountFilter !== "all" && accountType !== accountFilter) continue;

    const cited = parseJsonMaybeString(raw.sources_cited_json, []);
    const additional = parseJsonMaybeString(raw.sources_additional_json, []);
    const srg = parseJsonMaybeString(raw.search_result_groups_json, []);

    const used = new Set();
    if (Array.isArray(cited)) for (const s of cited) if (s?.url) used.add(normalizeUrlKey(s.url));
    if (Array.isArray(additional)) for (const s of additional) if (s?.url) used.add(normalizeUrlKey(s.url));

    if (include.has("cited") && Array.isArray(cited)) {
      for (const s of cited) addUrlHit(urlMap, { url: s?.url, runId, accountType, bucket: "cited" });
    }
    if (include.has("additional") && Array.isArray(additional)) {
      for (const s of additional) addUrlHit(urlMap, { url: s?.url, runId, accountType, bucket: "additional" });
    }
    if (include.has("rejected")) {
      // rejected = urls in search_result_groups_json not in cited/additional
      const rejectedUrls = [];
      if (Array.isArray(srg)) {
        for (const group of srg) {
          if (group && typeof group === "object" && Array.isArray(group.entries)) {
            for (const entry of group.entries) {
              if (entry?.url) rejectedUrls.push(entry.url);
            }
          } else if (group?.url) {
            rejectedUrls.push(group.url);
          }
        }
      }
      for (const u of rejectedUrls) {
        const k = normalizeUrlKey(u);
        if (!k) continue;
        if (used.has(k)) continue;
        addUrlHit(urlMap, { url: u, runId, accountType, bucket: "rejected" });
      }
    }
  }

  const rows = [];
  for (const v of urlMap.values()) {
    const domain = safeStr(v.domain).toLowerCase();
    const skip = domain && (skipDomains.has(domain) || [...skipDomains].some((d) => domain === d || domain.endsWith(`.${d}`)));

    const excel = urlsSheetIdx ? urlsSheetIdx.get(v.url_key) : null;
    const jsonl = jsonlIdx.get(v.url_key);
    const alreadyHasType = !!safeStr(excel?.type) || !!safeStr(jsonl?.type);
    if (args.onlyMissingType && alreadyHasType) continue;

    rows.push({
      url: v.url,
      url_key: v.url_key,
      domain: v.domain,
      sources: Array.from(v.sources).sort().join("|"),
      cited_runs: Array.from(v.cited_runs).sort().join("|"),
      additional_runs: Array.from(v.additional_runs).sort().join("|"),
      rejected_runs: Array.from(v.rejected_runs).sort().join("|"),
      account_types: Array.from(v.account_types).sort().join("|"),
      skip_domain: skip ? "1" : "0",
      skip_reason: skip ? "skip_domain" : "",
      excel_has_type: alreadyHasType ? "1" : "0",
    });
  }

  rows.sort((a, b) => (a.domain || "").localeCompare(b.domain || "") || (a.url || "").localeCompare(b.url || ""));

  fs.mkdirSync(path.dirname(args.outCsv), { recursive: true });
  const header = [
    "url",
    "url_key",
    "domain",
    "sources",
    "cited_runs",
    "additional_runs",
    "rejected_runs",
    "account_types",
    "skip_domain",
    "skip_reason",
    "excel_has_type",
  ];
  const out = [header.join(","), ...rows.map((r) => header.map((k) => csvEscape(r[k])).join(","))].join("\n");
  fs.writeFileSync(args.outCsv, out, "utf8");

  console.log(`Wrote ${rows.length} row(s) -> ${args.outCsv}`);
  console.log(`Notes: --only-missing-type=${args.onlyMissingType} account=${args.account} include=${args.include}`);
  if (!args.xlsx) console.log(`Tip: pass --xlsx geo_updated.xlsx to exclude URLs that already have urls.type filled.`);
}

main().catch((e) => {
  console.error("Fatal:", e?.stack || String(e));
  process.exit(1);
});

