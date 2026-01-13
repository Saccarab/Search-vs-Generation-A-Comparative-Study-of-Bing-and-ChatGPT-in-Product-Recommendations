/* eslint-disable no-console */

const elFile = document.getElementById("file");
const elFileInfo = document.getElementById("fileInfo");
const elConcurrency = document.getElementById("concurrency");
const elDelayMs = document.getElementById("delayMs");
const elTimeoutMs = document.getElementById("timeoutMs");
const elMaxChars = document.getElementById("maxChars");
const elBrowserFallback = document.getElementById("browserFallback");
const elBrowserWaitMs = document.getElementById("browserWaitMs");
const elStart = document.getElementById("start");
const elStop = document.getElementById("stop");
const elStatus = document.getElementById("status");
const elBar = document.getElementById("bar");
const elProgressText = document.getElementById("progressText");
const elDownload = document.getElementById("download");
const elSummary = document.getElementById("summary");

let urls = [];
let results = [];
let isRunning = false;

function safeStr(v) {
  return v === null || v === undefined ? "" : String(v);
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function setStatus(s) {
  elStatus.textContent = s;
}

function setProgress(done, total) {
  const pct = total ? Math.round((done / total) * 100) : 0;
  elBar.style.width = `${pct}%`;
  elProgressText.textContent = `${done} / ${total} (${pct}%)`;
}

function parseCsvLine(line) {
  const out = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') inQuotes = !inQuotes;
    else if (ch === "," && !inQuotes) {
      out.push(cur);
      cur = "";
    } else cur += ch;
  }
  out.push(cur);
  return out.map((s) => s.trim().replace(/^"|"$/g, ""));
}

function parseCsv(text) {
  const lines = String(text || "")
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);
  if (lines.length < 2) throw new Error("CSV must have a header and at least one row");
  const headers = parseCsvLine(lines[0]).map((h) => h.toLowerCase());
  const urlIdx = headers.indexOf("url");
  if (urlIdx < 0) throw new Error("CSV must contain a 'url' column");
  const out = [];
  for (let i = 1; i < lines.length; i++) {
    const vals = parseCsvLine(lines[i]);
    const u = (vals[urlIdx] || "").trim();
    if (!u) continue;
    out.push(u);
  }
  return out;
}

function normalizeUrl(raw) {
  const s = safeStr(raw).trim();
  if (!s) return "";
  if (s.startsWith("http://") || s.startsWith("https://")) return s;
  return `https://${s}`;
}

function domainOf(url) {
  try {
    return new URL(url).hostname.toLowerCase().replace(/^www\./, "");
  } catch {
    return "";
  }
}

function extractTextFromHtmlLikeBingExt(html) {
  try {
    const div = document.createElement("div");
    div.innerHTML = html || "";
    div.querySelectorAll("script, style, noscript").forEach((n) => n.remove());
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
    nonContentSelectors.forEach((sel) => div.querySelectorAll(sel).forEach((n) => n.remove()));
    let text = div.textContent || div.innerText || "";
    text = text.replace(/\u00a0/g, " ").replace(/\s+/g, " ").trim();
    return text;
  } catch {
    return "";
  }
}

function extractMetadataFromHtmlLikeBingExt(html) {
  const meta = {
    page_title: "",
    meta_description: "",
    canonical_url: "",
    has_schema_markup: 0,
    published_date: "",
    modified_date: "",
    js_render_suspected: 0,
  };
  try {
    const doc = new DOMParser().parseFromString(html || "", "text/html");
    meta.page_title =
      (doc.querySelector('meta[property="og:title"]')?.getAttribute("content") || "").trim() ||
      (doc.querySelector("title")?.textContent || "").trim();
    meta.meta_description =
      (doc.querySelector('meta[name="description"]')?.getAttribute("content") || "").trim() ||
      (doc.querySelector('meta[property="og:description"]')?.getAttribute("content") || "").trim();
    meta.canonical_url = (doc.querySelector('link[rel="canonical"]')?.getAttribute("href") || "").trim();
    const schemaScripts = Array.from(doc.querySelectorAll('script[type="application/ld+json"]'));
    if (schemaScripts.length > 0) meta.has_schema_markup = 1;
    const dateCandidates = { published: [], modified: [] };
    const walk = (obj) => {
      if (!obj) return;
      if (Array.isArray(obj)) return obj.forEach(walk);
      if (typeof obj !== "object") return;
      if (obj.datePublished) dateCandidates.published.push(obj.datePublished);
      if (obj.dateModified) dateCandidates.modified.push(obj.dateModified);
      if (obj["@graph"]) walk(obj["@graph"]);
      if (obj.mainEntity) walk(obj.mainEntity);
      if (obj.mainEntityOfPage) walk(obj.mainEntityOfPage);
    };
    for (const s of schemaScripts) {
      const raw = (s.textContent || "").trim();
      if (!raw) continue;
      try {
        walk(JSON.parse(raw));
      } catch {
        // ignore
      }
    }
    const firstMeta = (sels) => {
      for (const sel of sels) {
        const v = (doc.querySelector(sel)?.getAttribute("content") || "").trim();
        if (v) return v;
      }
      return "";
    };
    meta.published_date =
      firstMeta([
        'meta[property="article:published_time"]',
        'meta[name="pubdate"]',
        'meta[name="publishdate"]',
        'meta[name="timestamp"]',
        'meta[name="date"]',
        'meta[itemprop="datePublished"]',
      ]) || (dateCandidates.published[0] || "");
    meta.modified_date =
      firstMeta([
        'meta[property="article:modified_time"]',
        'meta[name="lastmod"]',
        'meta[name="last-modified"]',
        'meta[itemprop="dateModified"]',
      ]) || (dateCandidates.modified[0] || "");

    const spaMarkers = ["__NEXT_DATA__", "data-reactroot", 'id="app"', 'id="root"', "window.__INITIAL_STATE__"];
    const markerHit = spaMarkers.some((m) => (html || "").includes(m));
    const bodyTextLen = (doc.body?.textContent || "").replace(/\s+/g, " ").trim().length;
    meta.js_render_suspected = bodyTextLen < 400 && markerHit ? 1 : 0;
  } catch {
    // ignore
  }
  return meta;
}

function toCsv(rows) {
  const headers = [
    "url",
    "final_url",
    "domain",
    "status",
    "error",
    "page_title",
    "meta_description",
    "canonical_url",
    "published_date",
    "modified_date",
    "has_schema_markup",
    "js_render_suspected",
    "content_length",
    "content_truncated",
    "content",
  ];
  const esc = (v) => {
    const s = safeStr(v);
    if (/[\",\\r\\n]/.test(s)) return `"${s.replace(/\"/g, '""')}"`;
    return s;
  };
  const lines = [headers.join(",")];
  for (const r of rows) {
    lines.push(headers.map((h) => esc(r[h] ?? "")).join(","));
  }
  return lines.join("\n");
}

async function fetchOne(url, timeoutMs) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage({ action: "fetchHtml", url, timeoutMs }, (resp) => {
      if (chrome.runtime.lastError) {
        resolve({ ok: false, status: 0, statusText: "", finalUrl: url, contentType: "", html: "", error: chrome.runtime.lastError.message });
      } else {
        resolve(resp);
      }
    });
  });
}

async function fetchViaBrowser(url, waitMs) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage({ action: "fetchViaBrowser", url, waitMs }, (resp) => {
      if (chrome.runtime.lastError) {
        resolve({ ok: false, status: 0, finalUrl: url, extractedText: "", meta: {}, error: chrome.runtime.lastError.message, viaBrowser: true });
      } else {
        resolve(resp);
      }
    });
  });
}

function shouldTryBrowserFallback(status) {
  // Try browser fallback for: 403, 429, 5xx, network errors (0)
  if (status === 403 || status === 429) return true;
  if (status >= 500 && status < 600) return true;
  if (status === 0) return true;
  return false;
}

async function run() {
  isRunning = true;
  results = [];
  elStart.disabled = true;
  elStop.disabled = false;
  elDownload.disabled = true;
  setStatus("Running...");
  setProgress(0, urls.length);

  const concurrency = Math.max(1, Math.min(6, Number(elConcurrency.value || 2) || 2));
  const delayMs = Math.max(0, Math.min(20000, Number(elDelayMs.value || 0) || 0));
  const timeoutMs = Math.max(1000, Math.min(60000, Number(elTimeoutMs.value || 20000) || 20000));
  const maxChars = Math.max(0, Math.min(200000, Number(elMaxChars.value || 20000) || 20000));
  const useBrowserFallback = elBrowserFallback?.checked ?? true;
  const browserWaitMs = Math.max(2000, Math.min(60000, Number(elBrowserWaitMs?.value || 15000) || 15000));

  let done = 0;
  let browserFallbackCount = 0;

  // When using browser fallback, process one URL at a time to avoid tab overload
  const effectiveConcurrency = useBrowserFallback ? 1 : concurrency;

  for (let i = 0; i < urls.length; i += effectiveConcurrency) {
    if (!isRunning) break;
    const batch = urls.slice(i, i + effectiveConcurrency);
    const batchRes = await Promise.all(
      batch.map(async (raw) => {
        const url = normalizeUrl(raw);
        const started = Date.now();
        const dom = domainOf(url);

        // First try normal fetch
        let fr = await fetchOne(url, timeoutMs);
        let usedBrowser = false;

        // If fetch failed and browser fallback is enabled, try browser mode
        if (useBrowserFallback && (!fr.ok || !fr.html) && shouldTryBrowserFallback(fr.status)) {
          setStatus(`Browser fallback: ${dom}...`);
          const br = await fetchViaBrowser(url, browserWaitMs);
          usedBrowser = true;
          browserFallbackCount++;

          if (br.ok && br.extractedText) {
            // Browser extraction succeeded
            const extracted = br.extractedText;
            const fullLen = extracted.length;
            let content = extracted;
            let truncated = 0;
            if (maxChars === 0) {
              content = "";
              truncated = fullLen > 0 ? 1 : 0;
            } else if (fullLen > maxChars) {
              content = extracted.slice(0, maxChars);
              truncated = 1;
            }
            const ms = Date.now() - started;
            return {
              url,
              final_url: br.finalUrl || url,
              domain: dom,
              status: 200,
              error: "",
              page_title: br.meta?.page_title || "",
              meta_description: br.meta?.meta_description || "",
              canonical_url: br.meta?.canonical_url || "",
              published_date: br.meta?.published_date || "",
              modified_date: br.meta?.modified_date || "",
              has_schema_markup: br.meta?.has_schema_markup || 0,
              js_render_suspected: 0,
              content_length: fullLen,
              content_truncated: truncated,
              content,
              ms,
              via_browser: 1,
            };
          } else {
            // Browser extraction also failed
            const ms = Date.now() - started;
            return {
              url,
              final_url: br.finalUrl || url,
              domain: dom,
              status: fr.status || 0,
              error: br.error || fr.error || `HTTP ${fr.status || 0}`,
              page_title: "",
              meta_description: "",
              canonical_url: "",
              published_date: "",
              modified_date: "",
              has_schema_markup: 0,
              js_render_suspected: 0,
              content_length: 0,
              content_truncated: 0,
              content: "",
              ms,
              via_browser: 1,
            };
          }
        }

        const ms = Date.now() - started;

        if (!fr.ok || !fr.html) {
          return {
            url,
            final_url: fr.finalUrl || "",
            domain: dom,
            status: fr.status || 0,
            error: fr.error || `HTTP ${fr.status || 0}`,
            page_title: "",
            meta_description: "",
            canonical_url: "",
            published_date: "",
            modified_date: "",
            has_schema_markup: 0,
            js_render_suspected: 0,
            content_length: 0,
            content_truncated: 0,
            content: "",
            ms,
          };
        }

        const meta = extractMetadataFromHtmlLikeBingExt(fr.html);
        const extracted = extractTextFromHtmlLikeBingExt(fr.html);
        const fullLen = extracted.length;
        let content = extracted;
        let truncated = 0;
        if (maxChars === 0) {
          content = "";
          truncated = fullLen > 0 ? 1 : 0;
        } else if (fullLen > maxChars) {
          content = extracted.slice(0, maxChars);
          truncated = 1;
        }

        return {
          url,
          final_url: fr.finalUrl || "",
          domain: dom,
          status: fr.status || 0,
          error: "",
          page_title: meta.page_title,
          meta_description: meta.meta_description,
          canonical_url: meta.canonical_url,
          published_date: meta.published_date,
          modified_date: meta.modified_date,
          has_schema_markup: meta.has_schema_markup,
          js_render_suspected: meta.js_render_suspected,
          content_length: fullLen,
          content_truncated: truncated,
          content,
          ms,
        };
      })
    );
    results.push(...batchRes);
    done += batch.length;
    setProgress(done, urls.length);
    setStatus(`Fetched ${done}/${urls.length}${browserFallbackCount ? ` (${browserFallbackCount} via browser)` : ""}`);
    if (i + effectiveConcurrency < urls.length && delayMs > 0) await sleep(delayMs);
  }

  isRunning = false;
  elStop.disabled = true;
  elStart.disabled = false;
  elDownload.disabled = results.length === 0;
  setStatus(isRunning ? "Stopped" : "Done");

  const ok = results.filter((r) => !r.error).length;
  const bad = results.length - ok;
  const browserMsg = browserFallbackCount ? ` | browser fallback: ${browserFallbackCount}` : "";
  elSummary.textContent = `Rows: ${results.length} | ok: ${ok} | failed: ${bad}${browserMsg}`;
}

function download() {
  const csv = toCsv(results);
  const ts = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
  const filename = `url_content_${ts}.csv`;
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  chrome.downloads.download({ url, filename, saveAs: true }, () => {
    // ok
  });
}

elFile.addEventListener("change", async (e) => {
  const f = e.target.files?.[0];
  urls = [];
  results = [];
  elStart.disabled = true;
  elDownload.disabled = true;
  if (!f) return;
  const txt = await f.text();
  try {
    urls = parseCsv(txt);
    elFileInfo.textContent = `Loaded ${urls.length} URL(s)`;
    elStart.disabled = urls.length === 0;
    setStatus("");
    setProgress(0, urls.length);
  } catch (err) {
    elFileInfo.textContent = "";
    setStatus(`Error: ${String(err?.message || err)}`);
  }
});

elStart.addEventListener("click", () => {
  if (!urls.length) return;
  run().catch((e) => setStatus(`Fatal: ${String(e?.message || e)}`));
});

elStop.addEventListener("click", () => {
  isRunning = false;
  setStatus("Stopping...");
});

elDownload.addEventListener("click", download);

