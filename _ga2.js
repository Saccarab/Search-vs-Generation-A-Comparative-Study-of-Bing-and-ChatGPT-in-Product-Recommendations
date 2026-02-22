const fs = require("fs");
const path = require("path");
const BASE = "C:/Users/kayaa/Documents/GitHub/Search-vs-Generation-A-Comparative-Study-of-Bing-and-ChatGPT-in-Product-Recommendations/data";
const resolvedMap = JSON.parse(fs.readFileSync(path.join(BASE, "resolved_grounding_urls.json"), "utf8"));

function normalizeUrl(url) {
  try {
    const u = new URL(url);
    let host = u.hostname.replace(/^www[.]/, "");
    let pathname = u.pathname.replace(/[/]+$/, "");
    const tp = ["utm_source","utm_medium","utm_campaign","utm_term","utm_content","utm_id","fbclid","gclid","ref","source","_ga","_gl","mc_cid","mc_eid","srsltid"];
    const params = new URLSearchParams(u.search);
    for (const p of tp) params.delete(p);
    let search = params.toString();
    let clean = u.protocol + "//" + host + pathname;
    if (search) clean += "?" + search;
    return clean.toLowerCase();
  } catch(e) {
    return url.toLowerCase().replace(/[/]+$/, "");
  }
}
const geminiDir = path.join(BASE, "gemini_raw_responses");
const gFiles = fs.readdirSync(geminiDir).filter(f => f.endsWith(".json"));
const runFileMap = {};
for (const f of gFiles) {
  const m = f.match(/^(P[0-9]+_r[0-9]+)_([0-9]{4}-[0-9]{2}.*)[.]json$/);
  if (m) {
    if (!runFileMap[m[1]]) runFileMap[m[1]] = [];
    runFileMap[m[1]].push({ filename: f, dateStr: m[2] });
  }
}
const latestPerRun = {};
for (const [rid, files] of Object.entries(runFileMap)) {
  files.sort((a,b) => b.dateStr.localeCompare(a.dateStr));
  latestPerRun[rid] = files[0].filename;
}
const serpDir = path.join(BASE, "serpapi_google_results_gemini");
const sFiles = fs.readdirSync(serpDir).filter(f => f.endsWith(".json"));
const serpByRun = {};
for (const f of sFiles) {
  const m = f.match(/^gemini_(P[0-9]+_r[0-9]+)_Q/);
  if (m) {
    if (!serpByRun[m[1]]) serpByRun[m[1]] = [];
    serpByRun[m[1]].push(f);
  }
}
function getSerpUrls(runId) {
  const rf = serpByRun[runId] || [];
  const s = new Set();
  for (const sf of rf) {
    const d = JSON.parse(fs.readFileSync(path.join(serpDir, sf), "utf8"));
    if (d.organic_results) for (const r of d.organic_results) if (r.link) s.add(normalizeUrl(r.link));
    if (d.inline_videos) for (const r of d.inline_videos) if (r.link) s.add(normalizeUrl(r.link));
    if (d.discussions_and_forums) for (const r of d.discussions_and_forums) if (r.link) s.add(normalizeUrl(r.link));
    if (d.related_questions) for (const r of d.related_questions) if (r.link) s.add(normalizeUrl(r.link));
    if (d.knowledge_graph && d.knowledge_graph.website) s.add(normalizeUrl(d.knowledge_graph.website));
    if (d.top_stories) for (const r of d.top_stories) if (r.link) s.add(normalizeUrl(r.link));
  }
  return s;
}
const invisList = [];
for (const [runId, gFile] of Object.entries(latestPerRun)) {
  const gd = JSON.parse(fs.readFileSync(path.join(geminiDir, gFile), "utf8"));
  const chunks = (gd.groundingMetadata && gd.groundingMetadata.groundingChunks) || [];
  if (chunks.length === 0) continue;
  if (!serpByRun[runId] || serpByRun[runId].length === 0) continue;
  const serpSet = getSerpUrls(runId);
  for (const chunk of chunks) {
    const vurl = chunk.web && chunk.web.uri;
    if (!vurl) continue;
    const rurl = resolvedMap[vurl];
    if (!rurl) continue;
    const norm = normalizeUrl(rurl);
    if (!serpSet.has(norm)) {
      invisList.push({ url: rurl, normalized: norm, runId: runId });
    }
  }
}
