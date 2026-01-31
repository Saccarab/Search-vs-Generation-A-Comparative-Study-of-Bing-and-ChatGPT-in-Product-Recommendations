import fs from "fs";
import path from "path";

function safeStr(v) {
  if (v === null || v === undefined) return "";
  const s = String(v).trim();
  return s.toLowerCase() === "nan" ? "" : s;
}

function normalizeUrlKey(rawUrl) {
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
    "gclid", "fbclid", "msclkid", "yclid", "mc_cid", "mc_eid", "igshid", "ref", "ref_src", "spm",
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

async function main() {
  const rawDir = "datapass/raw_network_responses";
  const jsonlPaths = ["datapass/page_labels_gemini.jsonl", "datapass/page_labels_gpt.jsonl"];
  
  console.log("🔍 Scanning existing labels...");
  const labeledKeys = new Set();
  for (const p of jsonlPaths) {
    if (!fs.existsSync(p)) continue;
    const lines = fs.readFileSync(p, "utf8").split("\n");
    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const obj = JSON.parse(line);
        const k = normalizeUrlKey(obj.url);
        if (k && (obj.type || obj.ok === true)) labeledKeys.add(k);
      } catch {}
    }
  }
  console.log(`✅ Found ${labeledKeys.size} unique URLs already labeled in datapass files.`);

  console.log("\n🔍 Scanning all runs for Cited, Additional, and Rejected links...");
  const files = fs.readdirSync(rawDir).filter(f => f.endsWith(".json") && !f.startsWith("_"));
  
  const allUrls = new Map(); // urlKey -> { url, typeSet }

  for (const f of files) {
    const raw = JSON.parse(fs.readFileSync(path.join(rawDir, f), "utf8"));
    const cited = parseJsonMaybeString(raw.sources_cited_json, []);
    const additional = parseJsonMaybeString(raw.sources_additional_json, []);
    const srg = parseJsonMaybeString(raw.search_result_groups_json, []);

    const usedKeys = new Set();

    // Process Cited
    for (const s of cited) {
      if (!s?.url) continue;
      const k = normalizeUrlKey(s.url);
      if (!k) continue;
      usedKeys.add(k);
      if (!allUrls.has(k)) allUrls.set(k, { url: s.url, types: new Set() });
      allUrls.get(k).types.add("cited");
    }

    // Process Additional
    for (const s of additional) {
      if (!s?.url) continue;
      const k = normalizeUrlKey(s.url);
      if (!k) continue;
      usedKeys.add(k);
      if (!allUrls.has(k)) allUrls.set(k, { url: s.url, types: new Set() });
      allUrls.get(k).types.add("additional");
    }

    // Process Rejected
    if (Array.isArray(srg)) {
      for (const group of srg) {
        const entries = group?.entries || (group?.url ? [group] : []);
        for (const entry of entries) {
          if (!entry?.url) continue;
          const k = normalizeUrlKey(entry.url);
          if (!k || usedKeys.has(k)) continue;
          if (!allUrls.has(k)) allUrls.set(k, { url: entry.url, types: new Set() });
          allUrls.get(k).types.add("rejected");
        }
      }
    }
  }

  const totalUnique = allUrls.size;
  let missingCount = 0;
  const missingList = [];

  for (const [k, data] of allUrls.entries()) {
    if (!labeledKeys.has(k)) {
      missingCount++;
      missingList.push({
        url: data.url,
        types: Array.from(data.types).join("|")
      });
    }
  }

  console.log(`\n=== ENRICHMENT AUDIT REPORT ===`);
  console.log(`Total Unique URLs found in runs:  ${totalUnique}`);
  console.log(`Already Enriched (in datapass):   ${totalUnique - missingCount}`);
  console.log(`Missing Enrichment:               ${missingCount}`);
  
  // Breakdown by type for missing
  const missingByType = { cited: 0, additional: 0, rejected: 0 };
  for (const item of missingList) {
    if (item.types.includes("cited")) missingByType.cited++;
    if (item.types.includes("additional")) missingByType.additional++;
    if (item.types.includes("rejected")) missingByType.rejected++;
  }
  
  console.log(`\nBreakdown of Missing URLs (can overlap):`);
  console.log(`- Cited:      ${missingByType.cited}`);
  console.log(`- Additional: ${missingByType.additional}`);
  console.log(`- Rejected:   ${missingByType.rejected}`);

  // Write full list to text file
  const reportPath = "enrichment_audit_report.txt";
  let reportContent = `=== FULL LIST OF URLS REQUIRING ENRICHMENT (${missingCount}) ===\n\n`;
  reportContent += `Format: URL | Source Types\n`;
  reportContent += `--------------------------------------------------\n`;
  for (const item of missingList) {
    reportContent += `${item.url} | ${item.types}\n`;
  }
  
  fs.writeFileSync(reportPath, reportContent, "utf8");
  console.log(`\n✅ Full list written to ${reportPath}`);
}

main();
