// URL Content Fetcher - background service worker
// Fetches HTML with basic rate limiting. Extraction happens in sidepanel (DOMParser).
// Also supports browser-based extraction for pages with anti-bot protection.

const DEFAULT_TIMEOUT_MS = 20000;
const DEFAULT_BROWSER_WAIT_MS = 15000;
const RATE_LIMIT_MS = 2500; // per-domain spacing
const domainLastFetch = new Map();

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function domainOf(url) {
  try {
    return new URL(url).hostname.toLowerCase().replace(/^www\./, "");
  } catch {
    return "";
  }
}

async function waitForRateLimit(url) {
  const dom = domainOf(url);
  if (!dom) return;
  while (true) {
    const last = domainLastFetch.get(dom) || 0;
    const now = Date.now();
    const delta = now - last;
    if (delta >= RATE_LIMIT_MS) {
      domainLastFetch.set(dom, now);
      return;
    }
    await sleep(Math.min(200, RATE_LIMIT_MS - delta));
  }
}

async function fetchHtml(url, timeoutMs) {
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      method: "GET",
      redirect: "follow",
      signal: controller.signal,
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
      },
    });
    const ct = (res.headers.get("content-type") || "").toLowerCase();
    const okType = ct.includes("text/html") || ct.includes("application/xhtml") || ct.includes("text/plain");
    const body = okType ? await res.text() : "";
    return {
      ok: res.ok,
      status: res.status,
      statusText: res.statusText || "",
      finalUrl: res.url || url,
      contentType: ct,
      html: body,
      error: res.ok ? "" : `HTTP ${res.status} ${res.statusText}`.trim(),
    };
  } catch (e) {
    const name = e?.name || "Error";
    const msg = String(e?.message || e);
    const err = name === "AbortError" ? "Request timeout" : `${name}: ${msg}`;
    return { ok: false, status: 0, statusText: "", finalUrl: url, contentType: "", html: "", error: err };
  } finally {
    clearTimeout(t);
  }
}

// Browser-based extraction: opens real tab, waits, extracts from live DOM
async function fetchViaBrowser(url, waitMs) {
  let tab = null;
  try {
    // Create tab in FOREGROUND (active: true) so Cloudflare challenges can complete
    // Cloudflare requires user visibility to verify
    tab = await chrome.tabs.create({ url, active: true });
    const tabId = tab.id;

    // Wait for initial load
    await new Promise((resolve) => {
      const timeout = setTimeout(() => {
        chrome.tabs.onUpdated.removeListener(listener);
        resolve();
      }, waitMs + 5000);

      const listener = (updatedTabId, info) => {
        if (updatedTabId === tabId && info.status === "complete") {
          clearTimeout(timeout);
          chrome.tabs.onUpdated.removeListener(listener);
          resolve();
        }
      };
      chrome.tabs.onUpdated.addListener(listener);
    });

    // Wait for Cloudflare challenge to complete (poll until page changes or timeout)
    const startWait = Date.now();
    const maxWait = waitMs;
    while (Date.now() - startWait < maxWait) {
      await sleep(1500);
      // Check if still on Cloudflare challenge
      try {
        const checkResult = await chrome.scripting.executeScript({
          target: { tabId },
          func: () => {
            const title = document.title || "";
            const body = document.body?.innerText || "";
            const isCloudflare =
              title.toLowerCase().includes("just a moment") ||
              body.includes("Verifying you are human") ||
              body.includes("Checking your browser") ||
              body.includes("DDoS protection by");
            return { isCloudflare, title };
          },
        });
        const check = checkResult?.[0]?.result;
        if (!check?.isCloudflare) {
          // Challenge passed, give page a moment to fully render
          await sleep(1500);
          break;
        }
      } catch {
        // Tab might have navigated, that's fine
        break;
      }
    }

    // Get final URL after redirects
    const updatedTab = await chrome.tabs.get(tabId);
    const finalUrl = updatedTab.url || url;

    // Inject extraction script
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: () => {
        // Extract text content
        const clone = document.body.cloneNode(true);
        clone.querySelectorAll("script, style, noscript").forEach((n) => n.remove());
        const nonContentSelectors = [
          "nav", "header", "footer", "aside",
          ".navigation", ".nav", ".menu", ".sidebar",
          ".advertisement", ".ad", ".ads", ".cookie", ".popup", ".modal", ".overlay",
        ];
        nonContentSelectors.forEach((sel) => {
          try { clone.querySelectorAll(sel).forEach((n) => n.remove()); } catch {}
        });
        let text = (clone.textContent || clone.innerText || "")
          .replace(/\u00a0/g, " ")
          .replace(/\s+/g, " ")
          .trim();

        // Extract metadata
        const getMeta = (sel, attr = "content") => {
          try { return (document.querySelector(sel)?.getAttribute(attr) || "").trim(); } catch { return ""; }
        };
        const page_title =
          getMeta('meta[property="og:title"]') ||
          (document.querySelector("title")?.textContent || "").trim();
        const meta_description =
          getMeta('meta[name="description"]') ||
          getMeta('meta[property="og:description"]');
        const canonical_url = getMeta('link[rel="canonical"]', "href");
        const has_schema_markup = document.querySelectorAll('script[type="application/ld+json"]').length > 0 ? 1 : 0;

        // Try to extract dates from JSON-LD
        let published_date = "";
        let modified_date = "";
        const dateSelectors = [
          ['meta[property="article:published_time"]', "content"],
          ['meta[name="pubdate"]', "content"],
          ['meta[name="publishdate"]', "content"],
          ['meta[itemprop="datePublished"]', "content"],
        ];
        for (const [sel, attr] of dateSelectors) {
          const v = getMeta(sel, attr);
          if (v) { published_date = v; break; }
        }
        const modSelectors = [
          ['meta[property="article:modified_time"]', "content"],
          ['meta[name="lastmod"]', "content"],
          ['meta[itemprop="dateModified"]', "content"],
        ];
        for (const [sel, attr] of modSelectors) {
          const v = getMeta(sel, attr);
          if (v) { modified_date = v; break; }
        }
        // Also check JSON-LD
        document.querySelectorAll('script[type="application/ld+json"]').forEach((s) => {
          try {
            const obj = JSON.parse(s.textContent || "");
            const walk = (o) => {
              if (!o) return;
              if (Array.isArray(o)) return o.forEach(walk);
              if (typeof o !== "object") return;
              if (o.datePublished && !published_date) published_date = o.datePublished;
              if (o.dateModified && !modified_date) modified_date = o.dateModified;
              if (o["@graph"]) walk(o["@graph"]);
            };
            walk(obj);
          } catch {}
        });

        return {
          text,
          page_title,
          meta_description,
          canonical_url,
          has_schema_markup,
          published_date,
          modified_date,
          js_render_suspected: 0, // we did render JS
        };
      },
    });

    const extracted = results?.[0]?.result || {};

    return {
      ok: true,
      status: 200,
      statusText: "OK (browser)",
      finalUrl,
      contentType: "text/html",
      html: "", // not needed, we have extracted text
      extractedText: extracted.text || "",
      meta: {
        page_title: extracted.page_title || "",
        meta_description: extracted.meta_description || "",
        canonical_url: extracted.canonical_url || "",
        has_schema_markup: extracted.has_schema_markup || 0,
        published_date: extracted.published_date || "",
        modified_date: extracted.modified_date || "",
        js_render_suspected: 0,
      },
      error: "",
      viaBrowser: true,
    };
  } catch (e) {
    return {
      ok: false,
      status: 0,
      statusText: "",
      finalUrl: url,
      contentType: "",
      html: "",
      extractedText: "",
      meta: {},
      error: `Browser extraction failed: ${String(e?.message || e)}`,
      viaBrowser: true,
    };
  } finally {
    // Close the tab
    if (tab?.id) {
      try { await chrome.tabs.remove(tab.id); } catch {}
    }
  }
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.action === "fetchHtml") {
    const url = String(message.url || "");
    const timeoutMs = Number(message.timeoutMs || DEFAULT_TIMEOUT_MS) || DEFAULT_TIMEOUT_MS;
    (async () => {
      await waitForRateLimit(url);
      const r = await fetchHtml(url, timeoutMs);
      sendResponse(r);
    })();
    return true; // async response
  }

  if (message?.action === "fetchViaBrowser") {
    const url = String(message.url || "");
    const waitMs = Number(message.waitMs || DEFAULT_BROWSER_WAIT_MS) || DEFAULT_BROWSER_WAIT_MS;
    (async () => {
      await waitForRateLimit(url);
      const r = await fetchViaBrowser(url, waitMs);
      sendResponse(r);
    })();
    return true; // async response
  }

  return false;
});

