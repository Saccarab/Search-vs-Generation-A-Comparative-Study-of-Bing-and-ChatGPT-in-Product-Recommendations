/**
 * Export Gemini failures from data/llm/page_labels_gemini.jsonl to a CSV.
 *
 * Run:
 *   node scripts/llm/export_gemini_failures_csv.js --in data/llm/page_labels_gemini.jsonl --out data/llm/page_labels_gemini_failures.csv
 */

/* eslint-disable no-console */
const fs = require("fs");
const path = require("path");

function parseArgs(argv) {
  const out = { inPath: path.join("data", "llm", "page_labels_gemini.jsonl"), outPath: path.join("data", "llm", "page_labels_gemini_failures.csv") };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--in") out.inPath = argv[++i];
    else if (a === "--out") out.outPath = argv[++i];
  }
  return out;
}

function safeStr(v) {
  return v === null || v === undefined ? "" : String(v);
}

function csvEscape(v) {
  const s = safeStr(v);
  if (/[,"\r\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

function main() {
  const args = parseArgs(process.argv);
  if (!fs.existsSync(args.inPath)) {
    console.error(`Missing input JSONL: ${args.inPath}`);
    process.exit(2);
  }
  fs.mkdirSync(path.dirname(args.outPath), { recursive: true });

  const lines = fs.readFileSync(args.inPath, "utf8").split(/\r?\n/).filter(Boolean);
  const rows = [];
  for (const line of lines) {
    let obj;
    try {
      obj = JSON.parse(line);
    } catch {
      continue;
    }
    if (obj.ok !== false) continue;
    const err = obj.error || {};
    rows.push({
      ts: obj.ts || "",
      url: obj.url || "",
      model: obj.model || "",
      error_type: err.type || "",
      error_message: err.message || "",
      http_status: err.http_status || "",
      http_body_snippet: err.http_body_snippet || "",
    });
  }

  const headers = ["ts", "url", "model", "error_type", "error_message", "http_status", "http_body_snippet"];
  const out = [headers.join(",")];
  for (const r of rows) out.push(headers.map((h) => csvEscape(r[h] ?? "")).join(","));
  fs.writeFileSync(args.outPath, out.join("\n"), "utf8");

  console.log(`Wrote ${rows.length} failure rows -> ${args.outPath}`);
}

main();

