console.log("ChatGPT Response Scraper - Content script loaded");

// Debug logging: prints to DevTools console and also streams into the extension sidepanel.
const BUILD_ID = "2026-01-17T15:00Z";
const DEBUG_LOGS_ENABLED = true;
function debugLog(msg) {
  if (!DEBUG_LOGS_ENABLED) return;
  const line = `[debug][${BUILD_ID}] ${msg}`;
  try { console.log(line); } catch {}
  try {
    chrome.runtime.sendMessage({ action: 'debugLog', message: line });
  } catch {}
}

// Manual assist mode for stubborn "+N" citation pills. When enabled, the scraper will pause and ask
// the user to hover/click the popover so we can capture all (N+1) links.
let MANUAL_ASSIST_PLUS_N = false;
let AUTO_CLICK_PLUS_N = false;
const MANUAL_ASSIST_TIMEOUT_MS = 20000;
const MANUAL_ASSIST_POLL_MS = 250;
function reportUserAssist(active, message) {
  // NOTE: extension reload does not always re-inject updated content scripts into already-open tabs.
  // If you keep seeing an old BUILD_ID in logs, refresh the ChatGPT tab.
  try {
    chrome.runtime.sendMessage({ action: 'userAssist', active: !!active, message: message || '' }, () => {
      // Surface send failures; otherwise the sidepanel alert won't show and it looks like we never paused.
      try {
        if (chrome.runtime?.lastError) {
          debugLog(`inline: userAssist sendMessage failed: ${chrome.runtime.lastError.message || chrome.runtime.lastError}`);
        } else {
          debugLog(`inline: userAssist sendMessage ok active=${!!active}`);
        }
      } catch {}
    });
  } catch (e) {
    try { debugLog(`inline: userAssist sendMessage threw: ${String(e && (e.message || e)).slice(0, 200)}`); } catch {}
  }
}
debugLog(`loaded build_id=${BUILD_ID}`);

// selectors
const NEW_CHAT_BTN = 'a[data-testid="create-new-chat-button"]';
const TEMP_CHAT_BTN = 'button[aria-label="Turn on temporary chat"]';
const PLUS_BTN = "#composer-plus-btn";
const SEARCH_WEB_BTN = 'div[role="menuitemradio"]';
const SEARCH_QUERY_BUBBLE = 'div.text-token-text-secondary.dir-ltr'; // Add selector for search query bubble
const TEXT_FIELD = "#prompt-textarea";
const SEND_QUERY_BTN = "#composer-submit-button";
const COPY_RESPONSE_TEXT_BTN = '[data-testid="copy-turn-action-button"]';
const ASSISTANT_MSG = '[data-message-author-role="assistant"]';
const OPEN_SOURCES_BTN = 'button[aria-label="Sources"]';
const CITATION_LINKS = 'a[target="_blank"][rel="noopener"]';
const ADDITONAL_LINKS = 'a[target="_blank"][rel="noopener"]';
const CLOSE_SOURCES_BTN = 'button[data-testid="close-button"]';

// ================== HELPER ==================

function normalizeUrl(u) {
  try {
    return cleanInlineUrl(u);
  } catch {
    return u;
  }
}

function getRandomInt(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

async function pauseSeconds(s) {
  const ms = s * 1000;
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function simulateClick(selector) {
  const element = await waitForSelector(selector);
  if (!element) {
    throw new Error(`Element with selector "${selector}" not found!`);
  }

  // use pointer events first
  element.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true }));
  element.dispatchEvent(new PointerEvent("pointerup", { bubbles: true }));

  // then dispatch click event
  const event = new MouseEvent("click", {
    bubbles: true,
    cancelable: true,
    view: window,
  });
  element.dispatchEvent(event);
}

async function simulateTyping(selector, text, minDelay = 10, maxDelay = 30) {
  const element = await waitForSelector(selector);
  if (!element) {
    throw new Error(`Element with selector "${selector}" not found!`);
  }
  element.focus();

  for (const char of text) {
    element.textContent += char;
    element.dispatchEvent(
      new InputEvent("input", {
        data: char,
        inputType: "insertText",
        bubbles: true,
      })
    );
    await new Promise((r) =>
      setTimeout(
        r,
        Math.floor(Math.random() * (maxDelay - minDelay + 1)) + minDelay
      )
    );
  }
}

async function waitForSelector(selector, timeout = 15000) {
  return new Promise((resolve) => {
    // check immediately
    const el = document.querySelector(selector);
    if (el) return resolve(el);

    const observer = new MutationObserver(() => {
      const found = document.querySelector(selector);
      if (found) {
        clearTimeout(timer);
        observer.disconnect();
        resolve(found);
      }
    });

    observer.observe(document.body, { childList: true, subtree: true });

    const timer = setTimeout(() => {
      observer.disconnect();
      resolve(null);
    }, timeout);
  });
}

async function clickWebSearch() {
  await simulateClick(PLUS_BTN);
  await pauseSeconds(getRandomInt(1, 3));

  const element = Array.from(document.querySelectorAll(SEARCH_WEB_BTN)).find(
    (el) => el.textContent.trim() === "Web search"
  );

  if (element) {
    element.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true }));
    element.dispatchEvent(new PointerEvent("pointerup", { bubbles: true }));

    // dispatch click event
    const event = new MouseEvent("click", {
      bubbles: true,
      cancelable: true,
      view: window,
    });
    element.dispatchEvent(event);
  } else {
    console.error("Web search element not found!");
  }
}

async function waitForResponseFinished(selector, timeoutMs = 240000) {
  return new Promise((resolve, reject) => {
    debugLog(`waitForResponseFinished: start timeoutMs=${timeoutMs}`);
    // Capture search query while waiting
    let capturedSearchQuery = null;
    let webSearchTriggered = false;

    const normalize = (s) => (s || '').replace(/\s+/g, ' ').trim();
    const parseSearchingFor = (s) => {
      const t = normalize(s);
      // Matches:
      // - Searching for X
      // - Searching the web for X
      // - Searched the web for X
      const m = t.match(/(?:Searching|Searched)\s+(?:the\s+web\s+)?for\s+(.+)/i);
      if (!m) return null;
      return normalize(m[1]).replace(/^["“”']+|["“”']+$/g, '') || null;
    };

    // Define search query capturing logic
    const captureSearchQuery = () => {
      // NOTE: We create a fresh temp chat per query, so stale "Searching..." matches across turns are unlikely.
      // Still, we *prefer* the latest assistant scope first (lower noise), then fall back to scanning the full document.
      const msgEls = document.querySelectorAll(ASSISTANT_MSG);
      const scope = (msgEls && msgEls.length) ? msgEls[msgEls.length - 1] : document;

      const scopeText = normalize(scope.textContent);
      const fullText = normalize(document.body?.textContent || '');
      if (
        /Searching\s+the\s+web/i.test(scopeText) ||
        /Searching\s+(?:the\s+web\s+)?for/i.test(scopeText) ||
        /Searching\s+the\s+web/i.test(fullText) ||
        /Searching\s+(?:the\s+web\s+)?for/i.test(fullText)
      ) {
        webSearchTriggered = true;
      }

      if (capturedSearchQuery) return; // Already captured

      // Find explicit "Searching ... for <query>"
      const scan = (root) => {
        const candidates = root.querySelectorAll('div, span, p, button, li');
        let lastMatch = null;
        for (const el of candidates) {
          const q = parseSearchingFor(el.textContent);
          if (q) lastMatch = q;
        }
        if (lastMatch) {
          console.log(`[Search Query] Found during wait: "${lastMatch}"`);
          capturedSearchQuery = lastMatch;
          return true;
        }
        return false;
      };

      if (scope && scope !== document) {
        if (scan(scope)) return;
      }
      scan(document);
    };

    const check = () => {
      captureSearchQuery();

      const btn = document.querySelector(selector);
      if (btn) {
        const dt = (btn.getAttribute("data-testid") || "").toLowerCase();
        const aria = (btn.getAttribute("aria-label") || "").toLowerCase();
        const isStop =
          dt.includes("stop") ||
          aria.includes("stop generating") ||
          aria === "stop" ||
          aria.includes("stop");
        const isSend =
          dt === "send-button" ||
          aria.includes("send") ||
          aria.includes("send message") ||
          aria.includes("send prompt");
        const disabled =
          !!btn.disabled || btn.getAttribute("aria-disabled") === "true";

        // "Finished" means: we are back to a send-capable state (not a stop button).
        if (isSend && !isStop && !disabled) {
          cleanup();
          resolve({ searchQuery: capturedSearchQuery, webSearchTriggered });
          return true;
        }
      }
      return false;
    };

    // Back-compat: older UI used data-testid="send-button" to indicate ready.
    // Keep this after the more robust check above so we don't regress.
    const checkLegacy = () => {
      const btn = document.querySelector(selector);
      if (btn && btn.getAttribute("data-testid") === "send-button") {
        cleanup();
        resolve({ searchQuery: capturedSearchQuery, webSearchTriggered });
        return true;
      }
      return false;
    };

    const observer = new MutationObserver(() => {
      if (check()) return;
      checkLegacy();
    });

    const cleanup = () => {
      observer.disconnect();
      clearInterval(pollId);
      clearTimeout(timer);
    };

    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      // ChatGPT changes these while generating / after completion
      attributeFilter: ["data-testid", "aria-label", "disabled", "aria-disabled", "class"],
    });

    const timer = setTimeout(() => {
      cleanup();
      debugLog(`waitForResponseFinished: TIMEOUT after ${timeoutMs}ms`);
      reject(new Error("Timeout waiting for response to finish"));
    }, timeoutMs);

    // Poll in case the UI updates without triggering a useful mutation at the right time
    const pollId = setInterval(() => {
      try { captureSearchQuery(); } catch {}
      try { check(); } catch {}
    }, 250);

    if (!check()) checkLegacy();
  });
}

// NOTE: This function is now largely redundant but kept for fallback or post-wait checks
async function getSearchQuery(preCapturedQuery) {
  if (preCapturedQuery) return preCapturedQuery;

  await pauseSeconds(1); // Small pause to let UI settle
  try {
    const normalize = (s) => (s || '').replace(/\s+/g, ' ').trim();
    const parseSearchingFor = (s) => {
      const t = normalize(s);
      const m = t.match(/(?:Searching|Searched)\s+(?:the\s+web\s+)?for\s+(.+)/i);
      if (!m) return null;
      return normalize(m[1]).replace(/^["“”']+|["“”']+$/g, '') || null;
    };

    const msgEls = document.querySelectorAll(ASSISTANT_MSG);
    const scope = (msgEls && msgEls.length) ? msgEls[msgEls.length - 1] : document;

    const scan = (root) => {
      const candidates = root.querySelectorAll('div, span, p, button, li');
      let lastMatch = null;
      for (const el of candidates) {
        const q = parseSearchingFor(el.textContent);
        if (q) lastMatch = q;
      }
      return lastMatch;
    };

    const scoped = (scope && scope !== document) ? scan(scope) : null;
    if (scoped) {
      console.log(`[Search Query] Found (post-wait, scoped): "${scoped}"`);
      return scoped;
    }

    const full = scan(document);
    if (full) {
      console.log(`[Search Query] Found (post-wait, full scan): "${full}"`);
      return full;
    }
  } catch (e) {
    console.error("Error getting search query:", e);
  }
  
  return "N/A";
}

async function getResponse(selector) {
  const messageElements = document.querySelectorAll(selector);

  if (messageElements.length > 0) {
    const lastResponse = messageElements[messageElements.length - 1];
    
    // CLONE the element so we can modify it (expand links) without breaking the UI
    const clone = lastResponse.cloneNode(true);
    
    // Find all citation links in the clone
    const links = clone.querySelectorAll('a[target="_blank"]');
    
    links.forEach(link => {
      const url = link.href;
      const text = link.textContent;
      // Replace link text with "Text (URL)"
      // We clean the URL to remove UTM params if possible, or just use full URL
      try {
        const cleanUrlObj = new URL(url);
        // clear common tracking params
        ['utm_source', 'utm_medium', 'utm_campaign'].forEach(p => cleanUrlObj.searchParams.delete(p));
        link.textContent = `${text} [${cleanUrlObj.toString()}]`;
      } catch (e) {
        link.textContent = `${text} [${url}]`;
      }
    });

    const text = clone.textContent || clone.innerText;

    if (navigator.clipboard && window.isSecureContext) {
      try {
        // We still copy the ORIGINAL text to clipboard, not our modified one
        await navigator.clipboard.writeText(lastResponse.textContent);
      } catch (err) {
        //skip
      }
    }

    return text;
  }

  return null;
}

// ================== ITEM-LEVEL (INLINE) EXTRACTION ==================
// Goal: export an ordered array of items + their inline citation chip URLs (including +N carousel)
// into a single JSON column per run (items_json). This avoids rewriting the whole exporter.

function safeText(el) {
  return (el?.textContent || el?.innerText || '').replace(/\s+/g, ' ').trim();
}

function deriveItemName(itemText) {
  if (!itemText) return '';
  const m = itemText.match(/^\s*([^—\-:]{2,80})\s*[—\-:]\s+/);
  if (m) return m[1].trim();
  const words = itemText.split(/\s+/).filter(Boolean);
  return words.slice(0, 3).join(' ').trim();
}

function cleanInlineUrl(url) {
  try {
    const urlObj = new URL(url);
    const params = new URLSearchParams(urlObj.search);
    const trackingParams = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'fbclid', 'gclid', 'ref', 'source'];
    trackingParams.forEach(param => {
      params.delete(param);
      for (const [key] of params) {
        if (key.toLowerCase().startsWith(param.toLowerCase() + '_') || key.toLowerCase().includes('utm_')) {
          params.delete(key);
        }
      }
    });
    urlObj.search = params.toString();
    return urlObj.toString();
  } catch {
    return url;
  }
}

function extractDomainFromUrl(url) {
  try {
    const u = new URL(url);
    const h = (u.hostname || '').toLowerCase();
    return h.startsWith('www.') ? h.slice(4) : h;
  } catch {
    return '';
  }
}

function findVisiblePopoverContainer() {
  const candidates = Array.from(
    document.querySelectorAll(
      // Radix often portals popovers into <body> with wrapper attributes/classes.
      // ChatGPT popovers for "+N" pills frequently use these wrappers and may not set role/aria-describedby.
      'div[role="dialog"], div[role="tooltip"], div[role="menu"], div[class*="popover"], div[class*="tooltip"], [data-radix-popper-content-wrapper], div[id^="radix-"]'
    )
  );
  let best = null;
  let bestScore = 0;
  for (const c of candidates) {
    const rect = c.getBoundingClientRect();
    if (rect.width < 120 || rect.height < 60) continue;
    const links = c.querySelectorAll('a[href^="http"]');
    const txt = safeText(c);
    const score = links.length * 10 + (txt.length > 0 ? 1 : 0);
    if (score > bestScore) {
      bestScore = score;
      best = c;
    }
  }
  return best;
}

function findVisiblePopoverContainerNearPill(pill) {
  const pillRect = pill?.getBoundingClientRect?.();
  const candidates = Array.from(
    document.querySelectorAll(
      'div[role="dialog"], div[role="tooltip"], div[role="menu"], div[class*="popover"], div[class*="tooltip"], [data-radix-popper-content-wrapper], div[id^="radix-"]'
    )
  );

  let best = null;
  let bestScore = -Infinity;
  for (const c of candidates) {
    const rect = c.getBoundingClientRect();
    if (rect.width < 120 || rect.height < 60) continue;
    const links = c.querySelectorAll('a[href^="http"]');
    if (!links || links.length === 0) continue;

    // Prefer popovers close to the pill (Radix portals still appear near the anchor).
    let distScore = 0;
    if (pillRect) {
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const px = pillRect.left + pillRect.width / 2;
      const py = pillRect.top + pillRect.height / 2;
      const dx = cx - px;
      const dy = cy - py;
      const dist = Math.sqrt(dx * dx + dy * dy);
      distScore = -dist; // closer is better
    }

    const txt = safeText(c);
    const score = links.length * 10 + (txt.length > 0 ? 1 : 0) + distScore;
    if (score > bestScore) {
      bestScore = score;
      best = c;
    }
  }
  return best || findVisiblePopoverContainer();
}

async function closePopover() {
  try {
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  } catch {}
  await pauseSeconds(0.2);
}

function extractLinksFromPopover(container) {
  if (!container) return [];
  const out = [];
  const seen = new Set();
  
  // Scrape everything that could be a link: <a> tags, but also anything with data-url, data-href, etc.
  const candidates = Array.from(container.querySelectorAll('a, [data-url], [data-href], [data-link], [role="link"]'));
  
  for (const el of candidates) {
    const urls = extractUrlCandidatesFromElement(el);
    for (const rawUrl of urls) {
      const cleaned = normalizeUrl(rawUrl);
      if (seen.has(cleaned)) continue;
      seen.add(cleaned);
      out.push({
        url: cleaned,
        domain: extractDomainFromUrl(cleaned),
        title: safeText(el) || el.getAttribute('title') || el.getAttribute('alt') || '',
      });
    }
  }
  
  return out;
}

function extractUrlCandidatesFromElement(el) {
  const out = [];
  if (!el) return out;

  const push = (u) => {
    if (!u || typeof u !== 'string') return;
    const s = u.trim();
    if (!/^https?:\/\//i.test(s)) return;
    if (s.includes('chatgpt.com')) return;
    out.push(cleanInlineUrl(s));
  };

  try { push(el.href); } catch {}
  try { push(el.getAttribute?.('href') || ''); } catch {}
  try { push(el.getAttribute?.('data-url') || ''); } catch {}
  try { push(el.getAttribute?.('data-href') || ''); } catch {}
  try { push(el.getAttribute?.('data-link') || ''); } catch {}
  try { push(el.getAttribute?.('alt') || ''); } catch {}
  try { push(el.getAttribute?.('aria-label') || ''); } catch {}
  try { push(el.getAttribute?.('title') || ''); } catch {}

  // Last resort: parse any URL-looking substring from text.
  try {
    const t = safeText(el);
    const m = t.match(/https?:\/\/[^\s<>"')\]]+/i);
    if (m) push(m[0]);
  } catch {}

  return out;
}

async function tryExpandPopoverCarousel(container, maxSteps = 8) {
  if (!container) return [];
  const collected = [];
  const seenUrls = new Set();

  const findNextButtonInPopover = (root) => {
    if (!root) return null;

    // Prefer explicit labels when present.
    const labeled =
      root.querySelector('button[aria-label*="Next"], button[aria-label*="next"], button[title*="Next"], button[title*="next"]') ||
      Array.from(root.querySelectorAll('button')).find(b => /next/i.test(safeText(b) || '') || /next/i.test(b.getAttribute('aria-label') || '') || /next/i.test(b.getAttribute('title') || ''));
    if (labeled) return labeled;

    // Many ChatGPT popover carousels use icon-only arrow buttons (no text/aria-label),
    // shown next to a pager like "1/2". Detect that pager, then pick the *right* arrow.
    const pagerEl = Array.from(root.querySelectorAll('span, div'))
      .find(el => /^\s*\d+\s*\/\s*\d+\s*$/.test(safeText(el)));
    if (pagerEl) {
      const pagerScope = pagerEl.parentElement || root;
      const iconButtons = Array.from(pagerScope.querySelectorAll('button'))
        .filter(b => {
          const hasSvg = !!b.querySelector('svg');
          const txt = safeText(b);
          return hasSvg && (!txt || txt.length <= 1);
        });
      if (iconButtons.length >= 2) {
        // Convention: [prev, next] — pick last as "next"
        return iconButtons[iconButtons.length - 1];
      }
    }

    // Fallback: any icon-only button within the popover; prefer the last one.
    const anyIconButtons = Array.from(root.querySelectorAll('button'))
      .filter(b => {
        const hasSvg = !!b.querySelector('svg');
        const txt = safeText(b);
        return hasSvg && (!txt || txt.length <= 1);
      });
    return anyIconButtons.length ? anyIconButtons[anyIconButtons.length - 1] : null;
  };

  const collect = () => {
    const links = extractLinksFromPopover(container);
    for (const l of links) {
      if (!seenUrls.has(l.url)) {
        seenUrls.add(l.url);
        collected.push(l);
      }
    }
  };

  collect();
  debugLog(`popover: initial links=${collected.length}`);

  for (let i = 0; i < maxSteps; i++) {
    const nextBtn = findNextButtonInPopover(container);
    if (!nextBtn) break;

    const disabled = nextBtn.disabled || nextBtn.getAttribute('aria-disabled') === 'true';
    if (disabled) break;

    debugLog(`popover: click-next step=${i + 1}/${maxSteps}`);
    nextBtn.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
    nextBtn.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }));
    nextBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
    await pauseSeconds(0.25);

    const beforeCount = collected.length;
    collect();
    debugLog(`popover: links after click=${collected.length} (+${collected.length - beforeCount})`);
    if (collected.length === beforeCount) break;
  }

  return collected;
}

function findPopoverForPill(pill) {
  if (!pill) return null;
  const host =
    (pill?.closest && pill.closest('[aria-describedby]')) ||
    pill?.querySelector?.('[aria-describedby]') ||
    pill;
  const id = host?.getAttribute?.('aria-describedby') || '';
  if (id) {
    const el = document.getElementById(id);
    if (el) return el;
  }
  return findVisiblePopoverContainerNearPill(pill);
}

function collectUrlsFromPill(pill, outSet) {
  if (!pill || !outSet) return;

  // Primary: the pill's own anchor href (this is what actually changes when you click the arrow).
  try {
    const a = pill.querySelector('a[href]');
    const candidates = extractUrlCandidatesFromElement(a);
    for (const u of candidates) outSet.add(normalizeUrl(u));
  } catch {}

  // Secondary: sometimes the pill container (or its immediate scope) has multiple anchors.
  try {
    const anchors = pill.querySelectorAll('a[href]');
    anchors.forEach(a => {
      const candidates = extractUrlCandidatesFromElement(a);
      for (const u of candidates) outSet.add(normalizeUrl(u));
    });
  } catch {}
}

function collectUrlsFromPillScope(pill, outSet) {
  if (!pill || !outSet) return;
  try {
    const a = pill.querySelector('a[href^="http"]');
    if (!a) return;
    const scope = findPillCarouselScope(a);
    const hrefs = collectPillHrefsInScope(scope);
    for (const u of hrefs) outSet.add(u);
  } catch {}
}

async function collectPopoverUrlsUntil({ pill, plusN, seedUrls, timeoutMs, requireCount = true }) {
  // Expected sources: normally +N means N extra sources beyond the visible one -> N+1 total.
  // BUT: in practice the UI may remove the "+1" badge after you click next, so we also infer total pages
  // from the popover pager text "1/2" when available.
  let expected = (plusN && plusN > 0) ? (plusN + 1) : 1;
  const urls = seedUrls || new Set();
  const start = Date.now();
  const maxWaitMs = (typeof timeoutMs === 'number' && timeoutMs > 0) ? timeoutMs : 2500;

  // Helpful diagnostic: when manual-assist exits instantly, it's usually because timeoutMs was 0/undefined
  // or because we hit expected count before any polling. This log makes that obvious.
  debugLog(`inline: assist/start plusN=${plusN} expected=${expected} requireCount=${!!requireCount} timeoutMs=${maxWaitMs} seed=${urls.size}`);

  // Observe pill anchor href changes (arrow clicks often mutate the same <a href>).
  let stopObs = null;
  try {
    const a = pill?.querySelector?.('a[href]');
    if (a) {
      let lastHref = a?.href || a?.getAttribute?.('href') || '';
      stopObs = (() => {
        const mo = new MutationObserver(() => {
          const href = a?.href || a?.getAttribute?.('href') || '';
          if (href && href !== lastHref) {
            lastHref = href;
            try { urls.add(normalizeUrl(href)); } catch {}
            debugLog(`inline: href-mutation detected href="${String(href).slice(0, 140)}" collected=${urls.size}`);
          }
        });
        mo.observe(a, { attributes: true, attributeFilter: ['href'] });
        return () => { try { mo.disconnect(); } catch {} };
      })();
    }
  } catch {}

  while (Date.now() - start < maxWaitMs && (!requireCount || urls.size < expected)) {
    // Always collect URLs from the pill itself / its scope (arrow clicks often mutate the pill href).
    collectUrlsFromPill(pill, urls);
    collectUrlsFromPillScope(pill, urls);

    // Diagnostics: show exactly what the pill anchor currently points to (this is what should mutate).
    try {
      const a = pill?.querySelector?.('a[href]');
      const href = a?.href || a?.getAttribute?.('href') || '';
      const alt = a?.getAttribute?.('alt') || '';
      const title = a?.getAttribute?.('title') || '';
      debugLog(`inline: assist/poll pill-href="${String(href).slice(0, 140)}" alt="${String(alt).slice(0, 60)}" title="${String(title).slice(0, 60)}"`);
    } catch {}

    const pop = findPopoverForPill(pill);
    if (pop) {
      // Infer expected page count from pager "1/2" if present.
      try {
        const pagerEl = Array.from(pop.querySelectorAll('span, div'))
          .find(el => /^\s*\d+\s*\/\s*\d+\s*$/.test(safeText(el)));
        if (pagerEl) {
          const m = safeText(pagerEl).match(/^\s*(\d+)\s*\/\s*(\d+)\s*$/);
          const total = m ? parseInt(m[2], 10) : 0;
          if (Number.isFinite(total) && total > expected) {
            expected = total;
            debugLog(`inline: inferred expected=${expected} from pager text="${safeText(pagerEl)}"`);
          }
        }
      } catch {}

      const links = extractLinksFromPopover(pop);
      for (const l of links) urls.add(l.url);
      debugLog(`inline: assist/poll popover-found linksNow=${links.length} collected=${urls.size}/${expected} pillText="${safeText(pill).slice(0, 60)}"`);
    } else {
      debugLog(`inline: assist/poll popover-not-found collected=${urls.size}/${expected} pillText="${safeText(pill).slice(0, 60)}"`);
    }
    await pauseSeconds(MANUAL_ASSIST_POLL_MS / 1000);
  }

  try { stopObs?.(); } catch {}
  return urls;
}

async function extractInlineItemCitations() {
  const messageElements = document.querySelectorAll(ASSISTANT_MSG);
  if (!messageElements || messageElements.length === 0) return [];
  const lastResponse = messageElements[messageElements.length - 1];

  debugLog('inline: start extracting item citations');

  const items = [];
  let currentSection = '';
  let itemPos = 0;

  // Inline citation pills can be a carousel: the visible pill shows "+N" but the extra href(s)
  // are only rendered after clicking a "next" button in the pill container.
  const parsePlusCount = (root) => {
    try {
      // We intentionally look at BOTH innerText (layout-aware; often includes newlines/spaces)
      // and textContent (sometimes concatenated with no whitespace).
      // Important: DO NOT require a word-boundary after the digits; some variants render as "Vozo+2Chrome..."
      // which would fail /\b/ because digit->letter is not a word boundary.
      const texts = [];
      try { if (root?.innerText) texts.push(String(root.innerText)); } catch {}
      try { if (root?.textContent) texts.push(String(root.textContent)); } catch {}
      const combined = texts
        .filter(Boolean)
        .map(t => t.replace(/\s+/g, ' ').trim())
        .join(' | ');

      if (combined) {
        const ms = [...combined.matchAll(/\+(\d{1,3})(?!\d)/g)];
        if (ms.length) {
          const nums = ms.map(m => parseInt(m[1], 10)).filter(n => Number.isFinite(n));
          const maxN = nums.length ? Math.max(...nums) : 0;
          if (maxN > 0) return maxN;
        }
      }

      const candidates = Array.from(root.querySelectorAll('span, div, button'))
        .map(safeText)
        .filter(Boolean);
      let best = 0;
      for (const t of candidates) {
        // exact "+4"
        const m1 = t.match(/^\+(\d{1,3})$/);
        if (m1) best = Math.max(best, parseInt(m1[1], 10) || 0);
        // embedded "+4" (some variants render extra text in same node)
        const ms = [...t.matchAll(/\+(\d{1,3})(?!\d)/g)];
        for (const m of ms) best = Math.max(best, parseInt(m[1], 10) || 0);
      }
      if (best > 0) return best;
    } catch {}
    return 0;
  };

  const dispatchHover = (el) => {
    if (!el) return;
    try {
      const events = ['pointerover', 'pointerenter', 'mouseover', 'mouseenter', 'mousemove'];
      events.forEach(type => {
        el.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, pointerType: 'mouse' }));
        el.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, view: window }));
      });
    } catch {}
  };

  const waitForPopoverByAriaDescribedBy = async (pill, timeoutMs = 2500) => {
    // Radix often wires popovers via aria-describedby="radix-..."
    const host =
      (pill?.closest && pill.closest('[aria-describedby]')) ||
      pill?.querySelector?.('[aria-describedby]') ||
      pill;
    if (!host) return null;

    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      // aria-describedby can appear only after delayed-open triggers, so poll it.
      const id = host?.getAttribute?.('aria-describedby') || '';
      if (id) {
        const el = document.getElementById(id);
        if (el) {
          debugLog(`inline: popover found via aria-describedby id=${id}`);
          return el;
        }
      }
      // Keep the hover "alive" while waiting for delayed-open popovers.
      try { dispatchHover(pill); } catch {}
      await pauseSeconds(0.05);
    }
    const finalId = host?.getAttribute?.('aria-describedby') || '';
    if (finalId) {
      debugLog(`inline: popover NOT found via aria-describedby id=${finalId} within ${timeoutMs}ms`);
    } else {
      debugLog(`inline: popover NOT found (no aria-describedby) within ${timeoutMs}ms`);
    }
    return null;
  };

  const findPillCarouselScope = (anchorEl) => {
    // We try to find the smallest ancestor that contains both the pill(s) and a nav button.
    const pill = anchorEl?.closest?.('[data-testid="webpage-citation-pill"]') || anchorEl;
    let node = pill;
    for (let i = 0; i < 8 && node; i++) {
      const hasPill = !!node.querySelector?.('[data-testid="webpage-citation-pill"]');
      const hasNav =
        !!node.querySelector?.('button[aria-label*="Next"], button[aria-label*="next"], button[title*="Next"], button[title*="next"]') ||
        Array.from(node.querySelectorAll?.('button') || []).some(b => /next/i.test((b.getAttribute('aria-label') || b.getAttribute('title') || safeText(b) || '')));
      if (hasPill && hasNav) return node;
      node = node.parentElement;
    }
    // Fallback: use the pill itself (still lets us collect the currently visible href).
    return pill;
  };

  const collectPillHrefsInScope = (scope) => {
    const out = [];
    const seen = new Set();
    const anchors = scope.querySelectorAll?.('[data-testid="webpage-citation-pill"] a[href^="http"]') || [];
    anchors.forEach(a => {
      const href = a.href || a.getAttribute('href') || '';
      if (!href || href.includes('chatgpt.com')) return;
      const cleaned = normalizeUrl(href);
      if (seen.has(cleaned)) return;
      seen.add(cleaned);
      out.push(cleaned);
    });
    return out;
  };

  const findCarouselNextButton = (scope) => {
    const btn =
      scope.querySelector?.('button[aria-label*="Next"], button[aria-label*="next"], button[title*="Next"], button[title*="next"]') ||
      Array.from(scope.querySelectorAll?.('button') || []).find(b => /next/i.test((b.getAttribute('aria-label') || b.getAttribute('title') || safeText(b) || '')));
    return btn || null;
  };

  const clickButton = async (btn) => {
    if (!btn) return;
    btn.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
    btn.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }));
    btn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
  };

  const expandInlinePillCarouselLinks = async (anchorEl) => {
    const href = anchorEl?.href || anchorEl?.getAttribute?.('href') || '';
    if (!href || !/^https?:\/\//i.test(href)) return [];

    const plusN = parsePlusCount(anchorEl);
    // If no "+N" badge, it is a single pill.
    if (!plusN) return [normalizeUrl(href)];

    const scope = findPillCarouselScope(anchorEl);
    const urls = new Set();
    const collect = () => {
      for (const u of collectPillHrefsInScope(scope)) urls.add(u);
    };

    collect();

    // Click next up to "+N" times (or until no new pills appear).
    const maxSteps = Math.min(plusN, 12);
    for (let i = 0; i < maxSteps; i++) {
      const nextBtn = findCarouselNextButton(scope);
      if (!nextBtn) break;
      const disabled = nextBtn.disabled || nextBtn.getAttribute('aria-disabled') === 'true';
      if (disabled) break;

      const before = urls.size;
      await clickButton(nextBtn);
      await pauseSeconds(0.25);
      collect();
      if (urls.size === before) break;
    }

    return Array.from(urls);
  };

  const walker = document.createTreeWalker(lastResponse, NodeFilter.SHOW_ELEMENT);
  while (walker.nextNode()) {
    const el = walker.currentNode;
    const tag = el.tagName ? el.tagName.toLowerCase() : '';
    if (/^h[1-6]$/.test(tag)) {
      const t = safeText(el);
      if (t) currentSection = t;
      continue;
    }

    // Inline citation pills can appear outside <li> lists (often in intro <p> paragraphs).
    // We treat <p> as an "item" ONLY when it contains citation pills and is not nested in an <li>,
    // to avoid exploding item count.
    const isParagraphCandidate =
      tag === 'p' &&
      !!el.querySelector?.('[data-testid="webpage-citation-pill"]') &&
      !el.closest?.('li');

    if (tag === 'li' || isParagraphCandidate) {
      const clone = el.cloneNode(true);
      clone.querySelectorAll('button, [role="button"], .rounded-full, .badge, .chip').forEach(n => n.remove());
      const itemText = safeText(clone);
      if (!itemText) continue;

      itemPos += 1;
      const itemName = deriveItemName(itemText);

      // Inline citation "pills" are the most reliable indicator of chip groups.
      // They often contain <a target="_blank"> plus a "+N" badge, but the *extra* sources
      // can be inside a popover carousel (1/2, 2/2) that appears only after interacting.
      const pillCandidates = Array.from(el.querySelectorAll('[data-testid="webpage-citation-pill"]'));

      // For paragraph-items, we now also allow regular anchors if they look like citations.
      const otherCandidates = Array.from(el.querySelectorAll('button, [role="button"], a'))
            .filter(c => {
              // avoid adding anchors already covered by pillCandidates
              if (c.closest && c.closest('[data-testid="webpage-citation-pill"]')) return false;
              const t = safeText(c);
              if (!t) return false;
              // Citations are usually short text like "Chrome Web Store" or "microsoftedge...".
              // If it's a paragraph candidate, be a bit stricter to avoid noise.
              if (isParagraphCandidate && t.length > 50) return false;
              if (t.length > 100) return false; 
              if (/copy|share|edit|read more|view/i.test(t)) return false;
              
              // Must be an external link
              if (c.tagName.toLowerCase() === 'a') {
                const href = c.href || '';
                if (!/^https?:\/\//i.test(href) || href.includes('chatgpt.com')) return false;
              }
              return true;
            });

      const chipCandidates = [...pillCandidates, ...otherCandidates].slice(0, 10);

      const chipGroups = [];
      for (const chip of chipCandidates) {
        try {
          // If this is a pill wrapper, interact with it (safe) and use popover carousel if available.
          // If this is an anchor inside a pill, prefer interacting with the pill wrapper to avoid opening a tab.
          const isAnchor = !!(chip && chip.tagName && chip.tagName.toLowerCase() === 'a');
          const pill = (chip?.closest && chip.closest('[data-testid="webpage-citation-pill"]')) || (chip?.getAttribute && chip.getAttribute('data-testid') === 'webpage-citation-pill' ? chip : null);

          if (pill) {
            const plusN = parsePlusCount(pill);
            // If the DOM visually contains a "+N" but parsing yields 0, log both innerText and textContent.
            // This is the common failure mode when textContent is concatenated like "Vozo+2Chrome..." and
            // parsers rely on word boundaries or whitespace.
            try {
              const it = String(pill?.innerText || '').trim();
              const tc = String(pill?.textContent || '').trim();
              const hasPlusVisual = /\+\d{1,3}/.test(it) || /\+\d{1,3}/.test(tc);
              if (hasPlusVisual && (!plusN || plusN <= 0)) {
                debugLog(`inline: WARNING plusN parsed as 0 but pill has +N. innerText="${it.slice(0,120)}" textContent="${tc.slice(0,120)}"`);
              }
            } catch {}
            if (plusN > 0) {
              const host = (pill?.closest && pill.closest('[aria-describedby]')) || pill;
              const state = host?.getAttribute?.('data-state') || pill?.getAttribute?.('data-state') || '';
              const desc = host?.getAttribute?.('aria-describedby') || '';
              debugLog(`inline: +${plusN} pill detected text="${safeText(pill).slice(0, 80)}" data-state="${state}" aria-describedby="${desc}"`);
            }

            // Always include the pill's own href (base URL). We previously lost this when popover scraping succeeded.
            const baseAnchor = pill.querySelector('a[href^="http"]');
            const baseHrefRaw = baseAnchor?.href || baseAnchor?.getAttribute?.('href') || '';
            const baseHref = (baseHrefRaw && /^https?:\/\//i.test(baseHrefRaw)) ? normalizeUrl(baseHrefRaw) : '';
            const expectedCount = plusN > 0 ? (plusN + 1) : 1;
            const collectedUrls = new Set();
            if (baseHref) collectedUrls.add(baseHref);

            // Many "+N" pills only reveal the popover (and its arrow UI) on hover.
            // We try hover first (safe), then fall back to click.
            if (plusN > 0) {
              const plusBadge = Array.from(pill.querySelectorAll('span, div'))
                .find(n => /^\+\d{1,3}$/.test(safeText(n)));
              dispatchHover(plusBadge || pill);
              // also hover the anchor text; some variants attach hover handlers there
              try { dispatchHover(pill.querySelector('a')); } catch {}
              await pauseSeconds(0.15);

              // Log post-hover state (helps confirm delayed-open/instant-open transitions)
              try {
                const host = (pill?.closest && pill.closest('[aria-describedby]')) || pill;
                const state2 = host?.getAttribute?.('data-state') || pill?.getAttribute?.('data-state') || '';
                const desc2 = host?.getAttribute?.('aria-describedby') || '';
                debugLog(`inline: post-hover data-state="${state2}" aria-describedby="${desc2}"`);
              } catch {}
            }

            // Auto-click behavior can race user interaction (and can "steal" the click / cause fast state flips).
            // Only do this when explicitly enabled AND manual assist is off.
            if (AUTO_CLICK_PLUS_N && !MANUAL_ASSIST_PLUS_N) {
              try {
                pill.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
                pill.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }));
                pill.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
              } catch {}
              await pauseSeconds(0.35);
            }

            // Prefer aria-describedby popover when present (more deterministic than heuristic scanning).
            const pop =
              (await waitForPopoverByAriaDescribedBy(pill, plusN > 0 ? 3000 : 1500)) ||
              findVisiblePopoverContainer();
            if (pop) {
              if (plusN > 0 && MANUAL_ASSIST_PLUS_N) {
                // In manual assist mode: pause and wait (do NOT finish early just because we already have baseHref).
                const pillLabel = safeText(pill).slice(0, 120);
                const msg =
                  `Action needed: hover/click the highlighted citation pill and click the right-arrow until the last card.\n` +
                  `Expected ~${expectedCount} links.\n` +
                  `${pillLabel}\n` +
                  `Waiting up to ${(MANUAL_ASSIST_TIMEOUT_MS / 1000).toFixed(0)}s...`;
                reportUserAssist(true, msg);
                debugLog(`inline: popover found, manual-assist mode: waiting for user to click arrows (expected=${expectedCount})`);
                await collectPopoverUrlsUntil({
                  pill,
                  plusN,
                  seedUrls: collectedUrls,
                  timeoutMs: MANUAL_ASSIST_TIMEOUT_MS,
                  requireCount: false, // always wait/poll during manual assist
                });
                reportUserAssist(false, '');
              } else if (plusN > 0 && AUTO_CLICK_PLUS_N) {
                debugLog(`inline: attempting popover carousel auto-expand (maxSteps=10)`);
                const links = await tryExpandPopoverCarousel(pop, 10);
                const urls = (links || []).map(o => o?.url).filter(Boolean);
                for (const u of urls) collectedUrls.add(u);
                if (collectedUrls.size < expectedCount) {
                  await collectPopoverUrlsUntil({ pill, plusN, seedUrls: collectedUrls, timeoutMs: 2500 });
                }
              } else {
                // Auto-click disabled: just do a short poll (may still capture href changes if UI auto-advances)
                await collectPopoverUrlsUntil({ pill, plusN, seedUrls: collectedUrls, timeoutMs: 2500 });
              }

              await closePopover();
              if (collectedUrls.size > 0) {
                const outLinks = Array.from(collectedUrls);
                debugLog(`inline: popover links captured count=${outLinks.length} expected=${expectedCount}`);
                chipGroups.push({ links: outLinks });
                continue;
              }
            } else {
              debugLog(`inline: no popover found (plusN=${plusN}) - falling back`);
              // No popover appeared: fall back to inline carousel (if "+N" reveals other hrefs)
              const a = pill.querySelector('a[href^="http"]');
              if (a) {
                const links = await expandInlinePillCarouselLinks(a);
                if (links && links.length > 0) {
                  for (const u of links) collectedUrls.add(u);
                }
              }

              // Manual assist: ask the user to hover/click the +N pill so the popover opens and we can capture all links.
              if (plusN > 0 && MANUAL_ASSIST_PLUS_N && collectedUrls.size < expectedCount) {
                const pillLabel = safeText(pill).slice(0, 120);
                const msg =
                  `Hover/click the highlighted citation pill now (expected ${expectedCount} links):\n` +
                  `${pillLabel}\n` +
                  `If a popover opens, click the right arrow until it reaches the last card.\n` +
                  `Waiting up to ${(MANUAL_ASSIST_TIMEOUT_MS / 1000).toFixed(0)}s...`;
                debugLog(`inline: manual-assist requested plusN=${plusN} expected=${expectedCount}`);
                reportUserAssist(true, msg);

                // Wait for the user to open/cycle the popover; we continuously collect new URLs while it changes.
                try {
                  debugLog(`inline: manual-assist entering wait loop (timeoutMs=${MANUAL_ASSIST_TIMEOUT_MS})`);
                  await collectPopoverUrlsUntil({
                    pill,
                    plusN,
                    seedUrls: collectedUrls,
                    timeoutMs: MANUAL_ASSIST_TIMEOUT_MS,
                    requireCount: true, // Now we exit early if we get the links!
                  });
                  debugLog(`inline: manual-assist wait loop complete collected=${collectedUrls.size}/${expectedCount}`);
                } catch (e) {
                  debugLog(`inline: manual-assist ERROR in wait loop: ${String(e && (e.stack || e.message || e)).slice(0, 300)}`);
                }
                reportUserAssist(false, '');
                reportUserAssist(false, '');

                reportUserAssist(false, '');
                await closePopover();

                if (collectedUrls.size > 0) {
                  const outLinks = Array.from(collectedUrls);
                  debugLog(`inline: manual-assist links captured count=${outLinks.length} expected=${expectedCount}`);
                  chipGroups.push({ links: outLinks });
                  continue;
                }
              } else if (plusN > 0 && !MANUAL_ASSIST_PLUS_N && collectedUrls.size < expectedCount) {
                debugLog(`inline: manual-assist is OFF (plusN=${plusN}). Enable it in sidepanel to pause and let you hover/click popovers.`);
              }
            }

            // Last resort: if we have an anchor, capture its href as a single-link group.
            if (collectedUrls.size > 0) {
              chipGroups.push({ links: Array.from(collectedUrls) });
            } else {
              const a = pill.querySelector('a[href^="http"]');
              const href = a?.href || a?.getAttribute?.('href') || '';
              if (href && /^https?:\/\//i.test(href)) {
                chipGroups.push({ links: [normalizeUrl(href)] });
              }
            }
            continue;
          }

          // Non-pill anchors: keep old behavior (don't open new tabs).
          if (isAnchor) {
            const links = await expandInlinePillCarouselLinks(chip);
            if (links && links.length > 0) chipGroups.push({ links });
            continue;
          }

          chip.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
          chip.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }));
          chip.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
          await pauseSeconds(0.35);

          const pop = findVisiblePopoverContainer();
          if (!pop) {
            await closePopover();
            continue;
          }
          const links = await tryExpandPopoverCarousel(pop, 10);
          await closePopover();

          if (links && links.length > 0) {
            // group order is the group identifier
            chipGroups.push({ links });
          }
        } catch {
          await closePopover();
        }
      }

      items.push({
        item_section_title: currentSection,
        item_position: itemPos,
        item_name: itemName,
        item_text: itemText,
        chip_groups: chipGroups,
      });
    }
  }

  debugLog(`inline: done items=${items.length}`);
  return items;
}

async function extractSourceLinks() {
  const citations = [];
  const moreLinks = [];
  const seenUrls = new Set();

  // helper function to clean UTM parameters from URLs
  function cleanUrl(url) {
    try {
      const urlObj = new URL(url);
      const params = new URLSearchParams(urlObj.search);
      
      // remove all UTM and tracking parameters
      const trackingParams = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'fbclid', 'gclid', 'ref', 'source'];
      trackingParams.forEach(param => {
        params.delete(param);
        // also remove variations
        for (const [key] of params) {
          if (key.toLowerCase().startsWith(param.toLowerCase() + '_') || key.toLowerCase().includes('utm_')) {
            params.delete(key);
          }
        }
      });
      
      urlObj.search = params.toString();
      return urlObj.toString();
    } catch (error) {
      // console.warn('Failed to parse URL:', url);
      return url;
    }
  }

  // helper function to extract links from a section
  function extractLinksFromSection(sectionElement) {
    if (!sectionElement) return [];
    
    const links = [];
    const linkElements = sectionElement.querySelectorAll('a[target="_blank"][rel="noopener"]');
    
    linkElements.forEach((link) => {
      const url = link.href;
      if (url && url.startsWith("http")) {
        const cleanedUrl = cleanUrl(url);
        if (!seenUrls.has(cleanedUrl)) {
          seenUrls.add(cleanedUrl);
          
          // extract metadata with more fallback selectors
          const titleElement = link.querySelector('.line-clamp-2.text-sm.font-semibold') || 
                              link.querySelector('.font-semibold') ||
                              link.querySelector('h3, h4, h5');
          
          const descElement = link.querySelector('.text-token-text-secondary.line-clamp-2') ||
                             link.querySelector('.text-sm.leading-snug') ||
                             link.querySelector('p');
          
          const domainElement = link.querySelector('.line-clamp-1 .text-xs') ||
                               link.querySelector('.text-xs') ||
                               link.querySelector('img + *');
          
          links.push({
            url: cleanedUrl,
            title: titleElement?.textContent?.trim() || '',
            description: descElement?.textContent?.trim() || '',
            domain: domainElement?.textContent?.trim() || ''
          });
        }
      }
    });
    
    return links;
  }

  try {
    // strategy 1: look for sections by their header structure (most reliable)
    const sectionHeaders = document.querySelectorAll('li.sticky, li[class*="sticky"], .sticky li');
    
    for (const header of sectionHeaders) {
      const headerText = header.textContent?.trim().toLowerCase();
      
      if (headerText === 'citations') {
        console.log('Found Citations section header');
        let nextElement = header.nextElementSibling;
        while (nextElement && nextElement.tagName.toLowerCase() !== 'div') {
          if (nextElement.tagName.toLowerCase() === 'ul') {
            const citationLinks = extractLinksFromSection(nextElement);
            citations.push(...citationLinks);
            console.log(`Extracted ${citationLinks.length} citation links`);
            break;
          }
          nextElement = nextElement.nextElementSibling;
        }
      } else if (headerText === 'more') {
        console.log('Found More section header');
        let nextElement = header.nextElementSibling;
        while (nextElement && nextElement.tagName.toLowerCase() !== 'div') {
          if (nextElement.tagName.toLowerCase() === 'ul') {
            const additionalLinks = extractLinksFromSection(nextElement);
            moreLinks.push(...additionalLinks);
            console.log(`Extracted ${additionalLinks.length} additional links`);
            break;
          }
          nextElement = nextElement.nextElementSibling;
        }
      }
    }

    // strategy 2: search by text content with broader selectors
    if (citations.length === 0 && moreLinks.length === 0) {
      console.log('Fallback: Searching for sections by text content');
      
      const possibleHeaders = document.querySelectorAll('li, h1, h2, h3, h4, h5, .section-header, [class*="header"]');
      
      for (const element of possibleHeaders) {
        const text = element.textContent?.trim().toLowerCase();
        
        if (text === 'citations') {
          console.log('Found Citations section via fallback');
          // look for the next ul element in various ways
          let container = element.nextElementSibling;
          if (!container) container = element.parentElement?.nextElementSibling;
          if (!container && element.parentElement) {
            container = element.parentElement.querySelector('ul');
          }
          
          if (container) {
            if (container.tagName.toLowerCase() !== 'ul') {
              container = container.querySelector('ul');
            }
            if (container) {
              const citationLinks = extractLinksFromSection(container);
              citations.push(...citationLinks);
              console.log(`Fallback extracted ${citationLinks.length} citation links`);
            }
          }
        } else if (text === 'more') {
          console.log('Found More section via fallback');
          let container = element.nextElementSibling;
          if (!container) container = element.parentElement?.nextElementSibling;
          if (!container && element.parentElement) {
            container = element.parentElement.querySelector('ul');
          }
          
          if (container) {
            if (container.tagName.toLowerCase() !== 'ul') {
              container = container.querySelector('ul');
            }
            if (container) {
              const additionalLinks = extractLinksFromSection(container);
              moreLinks.push(...additionalLinks);
              console.log(`Fallback extracted ${additionalLinks.length} additional links`);
            }
          }
        }
      }
    }

    // strategy 3: collect all external links
    if (citations.length === 0 && moreLinks.length === 0) {
      console.log('Ultimate fallback: Collecting all external links');
      
      const allLinks = document.querySelectorAll('a[href^="http"], a[target="_blank"]');
      const collectedLinks = [];
      
      allLinks.forEach((link) => {
        const url = link.href;
        if (url && url.startsWith("http") && !url.includes('chatgpt.com')) {
          const cleanedUrl = cleanUrl(url);
          if (!seenUrls.has(cleanedUrl)) {
            seenUrls.add(cleanedUrl);
            
            const titleElement = link.querySelector('.font-semibold') || link;
            const descElement = link.querySelector('p, .description, [class*="desc"]');
            
            collectedLinks.push({
              url: cleanedUrl,
              title: titleElement?.textContent?.trim() || link.textContent?.trim() || '',
              description: descElement?.textContent?.trim() || '',
              domain: new URL(cleanedUrl).hostname || ''
            });
          }
        }
      });
      
      // if we found some links, assume they're all citations since we can't distinguish
      if (collectedLinks.length > 0) {
        citations.push(...collectedLinks);
        console.log(`Ultimate fallback collected ${collectedLinks.length} links as citations`);
      }
    }

  } catch (error) {
    console.error('Error in extractSourceLinks:', error);
  }

  const result = {
    citations: citations,
    additional: moreLinks,
  };

  console.log(`Final result: ${citations.length} citations, ${moreLinks.length} additional links`);
  return result;
}

function convertToCSV(results) {
  if (results.length === 0) return '';
  
  // get headers from first result
  const headers = Object.keys(results[0]);
  
  // create CSV content
  let csvContent = headers.join(',') + '\n';
  
  results.forEach(result => {
    const row = headers.map(header => {
      // IMPORTANT: don't use `|| ''` here because it converts valid falsy values (0, false) to empty strings.
      // We want to preserve 0/false in the CSV for proper downstream parsing.
      let value = (result[header] ?? '');
      
      // If it's the response text or search query, replace newlines with spaces to keep CSV clean
      if (header === 'response_text' || header === 'query' || header === 'generated_search_query') {
          value = String(value).replace(/[\r\n]+/g, '  ');
      }
      
      // escape quotes and wrap in quotes if contains comma, quote, or newline
      const escapedValue = String(value).replace(/"/g, '""');
      return /[,"\n\r]/.test(escapedValue) ? `"${escapedValue}"` : escapedValue;
    });
    csvContent += row.join(',') + '\n';
  });
  
  return csvContent;
}

// ================== PROGRESS REPORTING ==================

function reportProgress(data) {
  try {
    chrome.runtime.sendMessage({
      action: 'progressUpdate',
      ...data
    });
  } catch (error) {
    // console.warn('Failed to report progress:', error);
  }
}

function reportError(queryIndex, error) {
  try {
    chrome.runtime.sendMessage({
      action: 'queryError',
      queryIndex: queryIndex,
      error: error
    });
  } catch (error) {
    // console.warn('Failed to report error:', error);
  }
}

// ================== AUTOMATIZATION ==================

async function collectQueryResponse(query, force_web_search = true, retryCount = 0, maxRetries = 3) {
  const attemptLabel = retryCount > 0 ? ` (Retry ${retryCount}/${maxRetries})` : '';
  console.log(`[Query Processing] Starting query: "${query.substring(0, 50)}..."${attemptLabel}`);
  
  await pauseSeconds(getRandomInt(0.5, 1));

  // open new chat
  await simulateClick(NEW_CHAT_BTN);
  await pauseSeconds(getRandomInt(0.5, 1));

  // open new temp chat
  await simulateClick(TEMP_CHAT_BTN);
  await pauseSeconds(getRandomInt(0.5, 1));

  // enable web search -> only if force_web_search is true
  if (force_web_search) {
    await clickWebSearch();
    await pauseSeconds(getRandomInt(0.5, 1));
  } else {
    console.log('[Step 3/8] Skipping web search (disabled by user)...');
  }

  // type query
  await simulateTyping(TEXT_FIELD, query);
  await pauseSeconds(getRandomInt(0.2, 0.5));

  // send query
  await simulateClick(SEND_QUERY_BTN);
  await pauseSeconds(getRandomInt(0.5, 1));

  // wait for response end AND capture search query during the wait
  const waitResult = await waitForResponseFinished(SEND_QUERY_BTN);
  await pauseSeconds(getRandomInt(0.5, 1));

  // Fallback: If we missed it during the stream, try one last check
  const generated_search_query = await getSearchQuery(waitResult?.searchQuery);

  // get response text
  const response_text = await getResponse(ASSISTANT_MSG);
  await pauseSeconds(getRandomInt(0.5, 1));

  // prepare return object
  const result = {
    query: query,
    generated_search_query: generated_search_query || "N/A", // Add to result object
    web_search_triggered: !!waitResult?.webSearchTriggered,
    response_text: response_text,
    web_search_forced: force_web_search,
    retry_count: retryCount
  };

  // ALWAYS try to extract source links
  try {
    // 1) First extract inline items to capture hidden carousel links (+N pills)
    const items = await extractInlineItemCitations();
    result.items_json = JSON.stringify(items);
    result.items_count = items.length;
    result.items_with_citations_count = items.filter(it => it.chip_groups && it.chip_groups.length > 0).length;

    // 2) Open sources panel and extract visible sources
    const sourcesButton = document.querySelector(OPEN_SOURCES_BTN);
    if (sourcesButton) {
      console.log('Sources button found - extracting sources');
      await simulateClick(OPEN_SOURCES_BTN);
      await pauseSeconds(getRandomInt(1, 2));
      
      const sourceLinks = await extractSourceLinks();
      
      const closeButton = document.querySelector(CLOSE_SOURCES_BTN);
      if (closeButton) {
        await simulateClick(CLOSE_SOURCES_BTN);
        await pauseSeconds(getRandomInt(0.5, 1));
      }
      
      result.sources_cited = sourceLinks.citations || [];
      result.sources_additional = sourceLinks.additional || [];
    } else {
      console.log(`No sources button found - ChatGPT did not use web search for this query${force_web_search ? ' (despite being forced)' : ''}`);
      result.sources_cited = [];
      result.sources_additional = [];
    }

    // 3) MERGE hidden links from inline carousels into the cited sources list
    const seenUrls = new Set();
    const finalSourcesAll = [];
    const finalSourcesCited = [...(result.sources_cited || [])];

    // Mark existing sources as seen
    finalSourcesCited.forEach(s => seenUrls.add(s.url));
    (result.sources_additional || []).forEach(s => seenUrls.add(s.url));

    // Look through all chip groups in items
    for (const item of items) {
      if (!item.chip_groups) continue;
      for (const group of item.chip_groups) {
        if (!group.links) continue;
        for (const url of group.links) {
          if (!seenUrls.has(url)) {
            seenUrls.add(url);
            // This link was hidden in a carousel; add it to cited list
            const newSource = { url, title: url, domain: extractDomainFromUrl(url) };
            finalSourcesCited.push(newSource);
            debugLog(`sync: added hidden carousel link to cited list: ${url}`);
          }
        }
      }
    }

    result.sources_cited = finalSourcesCited;
    result.sources_all = [...result.sources_cited, ...(result.sources_additional || [])];

    // helper function to extract domain
    const extractDomain = (source) => {
      try {
        const url = new URL(source.url);
        return url.hostname.split('.').slice(-2).join('.');
      } catch { return ''; }
    };
    
    result.domains_cited = result.sources_cited.map(s => extractDomain(s)).filter(Boolean);
    result.domains_additional = result.sources_additional.map(s => extractDomain(s)).filter(Boolean);
    result.domains_all = result.sources_all.map(s => extractDomain(s)).filter(Boolean);
    
    const uniqueDomains = new Set(result.domains_all);
    result.domains_all = Array.from(uniqueDomains);
    
    console.log(`Final sync: ${result.sources_cited.length} citations, ${result.sources_additional.length} additional, ${result.sources_all.length} total`);

    // FAILSAFE: if web search was forced but no sources found, retry
    if (force_web_search && (result.sources_all.length === 0) && retryCount < maxRetries) {
      // console.warn(`[Failsafe] Web search was forced but no sources found. Retrying... (${retryCount + 1}/${maxRetries})`);
      
      // report retry attempt to sidepanel
      reportProgress({
        retryAttempt: true,
        retryCount: retryCount + 1,
        maxRetries: maxRetries
      });
      
      // add a small delay before retry
      await pauseSeconds(getRandomInt(2, 4));
      
      // recursive retry
      return await collectQueryResponse(query, force_web_search, retryCount + 1, maxRetries);
    } else if (force_web_search && retryCount >= maxRetries) {
      console.error(`[Failsafe] Max retries (${maxRetries}) reached. Proceeding without sources.`);
      result.no_sources_warning = true;
    }
  } catch (error) {
    // console.warn('Error extracting sources:', error.message);
    // set empty arrays if source extraction fails
    result.sources_cited = [];
    result.sources_additional = [];
    result.sources_all = [];
    result.domains_cited = [];
    result.domains_additional = [];
    result.domains_all = [];
    result.extraction_error = error.message;
  }

  console.log(`[Query Complete] Successfully processed query with ${result.response_text ? result.response_text.length : 0} characters of response${result.no_sources_warning ? ' (WARNING: No sources despite forced web search)' : ''}`);
  return result;
}

async function processQueries(queries, runs_per_q = 1, force_web_search = true) {
  const results = [];
  const totalOperations = queries.length * runs_per_q;
  let completedOperations = 0;

  // ---------- Fallback helpers (when UI doesn't render <a> tags / <li> lists) ----------
  const extractUrlsFromText = (text) => {
    const s = String(text || '');
    // Match http(s) URLs, stop at whitespace or common trailing punctuation
    const re = /https?:\/\/[^\s<>"')\]]+/gi;
    const found = s.match(re) || [];
    const seen = new Set();
    const out = [];
    for (let u of found) {
      u = u.replace(/[.,;:!?]+$/g, ''); // strip trailing punctuation
      try { u = cleanUrl(u); } catch {}
      if (!u || seen.has(u)) continue;
      seen.add(u);
      out.push(u);
    }
    return out;
  };

  const buildItemsFromTextUrls = (text, urls) => {
    const s = String(text || '').replace(/\s+/g, ' ').trim();
    const items = [];
    let pos = 0;
    for (const u of (urls || [])) {
      pos += 1;
      // Try to capture a short label immediately preceding the URL.
      const idx = s.toLowerCase().indexOf(u.toLowerCase());
      let label = '';
      if (idx > 0) {
        const left = s.slice(0, idx);
        // Take last ~80 chars and trim to last sentence-ish boundary.
        const windowText = left.slice(Math.max(0, left.length - 120));
        const parts = windowText.split(/(?:\.\s+|\|\s+|—\s+|-\s+|\u2022\s+|:\s+)/);
        label = (parts[parts.length - 1] || '').trim();
      }
      if (!label) label = u;
      const name = deriveItemName(label);
      items.push({
        item_section_title: 'response_text_fallback',
        item_position: pos,
        item_name: name,
        item_text: label,
        chip_groups: [{ links: [u] }],
      });
    }
    return items;
  };
  
  console.log(`[Collection Start] Processing ${queries.length} queries with ${runs_per_q} runs each (${totalOperations} total operations), web search: ${force_web_search ? 'forced' : 'optional'}`);
  
  for (let i = 0; i < queries.length; i++) {
    const qObj = queries[i];
    const query = (typeof qObj === 'string') ? qObj : (qObj?.query || '');
    const prompt_id = (typeof qObj === 'object' && qObj) ? (qObj.prompt_id || '') : '';
    
    for (let run = 1; run <= runs_per_q; run++) {
      try {
        console.log(`[Progress] Query ${i + 1}/${queries.length}, Run ${run}/${runs_per_q}`);
        
        // report progress to sidepanel
        reportProgress({
          queryIndex: i,
          run: run,
          completed: completedOperations,
          totalOperations: totalOperations
        });
        
        const result = await collectQueryResponse(query, force_web_search);

        // helper function to safely convert source data to Python list string format
        const formatSources = (sources) => {
          if (!sources) return '[]';
          if (Array.isArray(sources)) {
            if (sources.length === 0) return '[]';
            const urls = sources.map(source => {
              let url;
              if (typeof source === 'string') url = source;
              else if (typeof source === 'object' && source.url) url = source.url;
              else if (typeof source === 'object' && source.link) url = source.link;
              else url = JSON.stringify(source);
              
              // escape single quotes in URL and wrap in quotes
              return `'${url.replace(/'/g, "\\'")}'`;
            });
            return `[${urls.join(', ')}]`;
          }
          if (typeof sources === 'string') return `['${sources.replace(/'/g, "\\'")}']`;
          return '[]';
        };
        
        // add run number and index to result
        const enrichedResult = {
          query_index: i + 1,
          run_number: run,
          prompt_id: prompt_id,
          query: result.query,
          generated_search_query: result.generated_search_query, // Include in enriched result
          response_text: result.response_text,
          web_search_forced: result.web_search_forced,
          web_search_triggered: result.web_search_triggered,
          items_json: result.items_json || '[]',
          items_count: result.items_count || 0,
          items_with_citations_count: result.items_with_citations_count || 0,
          // Keep the existing URL-list columns for easy joins/overlap, but also provide JSON arrays of objects
          // so you can analyze which snippet/title ChatGPT showed per URL (and preserve ordering).
          sources_cited_json: (() => { try { return JSON.stringify(result.sources_cited || []); } catch { return '[]'; } })(),
          sources_additional_json: (() => { try { return JSON.stringify(result.sources_additional || []); } catch { return '[]'; } })(),
          sources_all_json: (() => { try { return JSON.stringify(result.sources_all || []); } catch { return '[]'; } })(),
          sources_cited: formatSources(result.sources_cited),
          sources_additional: formatSources(result.sources_additional),
          sources_all: formatSources(result.sources_all),
          domains_cited: formatSources(result.domains_cited),
          domains_additional: formatSources(result.domains_additional),
          domains_all: formatSources(result.domains_all),
        };
        
        results.push(enrichedResult);
        completedOperations++;
        
        // report completion of this operation
        reportProgress({
          completed: completedOperations,
          totalOperations: totalOperations
        });
        
        console.log(`[Success] Completed operation ${completedOperations}/${totalOperations}`);
        
        // add delay between queries to avoid rate limiting
        if (!(i === queries.length - 1 && run === runs_per_q)) {
          const delaySeconds = getRandomInt(1, 2);
          // console.log(`[Delay] Waiting ${delaySeconds} seconds before next query...`);
          await pauseSeconds(delaySeconds);
        }
        
      } catch (error) {
        console.error(`[Error] Processing query "${query}" (run ${run}):`, error);
        
        // report error to sidepanel
        reportError(i + 1, error.message);
        
        // add error result
        const errorResult = {
          query_index: i + 1,
          run_number: run,
          prompt_id: prompt_id,
          query: query,
          generated_search_query: 'N/A',
          response_text: `ERROR: ${error.message}`,
          web_search_forced: force_web_search,
          web_search_triggered: false,
          items_json: '[]',
          items_count: 0,
          items_with_citations_count: 0,
          sources_cited_json: '[]',
          sources_additional_json: '[]',
          sources_all_json: '[]',
          sources_cited: '',
          sources_additional: '',
          sources_all: '',
        };
        
        results.push(errorResult);
        completedOperations++;
        
        // report completion even for errors
        reportProgress({
          completed: completedOperations,
          totalOperations: totalOperations
        });
        
        // don't stop the entire process for one error, continue with next
        console.log(`[Recovery] Continuing with next query after error...`);
        
        // still add delay after errors
        if (!(i === queries.length - 1 && run === runs_per_q)) {
          await pauseSeconds(getRandomInt(2, 5));
        }
      }
    }
  }
  
  console.log(`[Collection Complete] Processed ${totalOperations} operations with ${results.length} results`);
  return convertToCSV(results);
}


// ================== COMMUNICATION ==================

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "startDataCollection") {
    (async () => {
      try {
        const queries = message.queries || [];
        const runs_per_q = message.runs_per_q || 1;
        const force_web_search = message.force_web_search !== undefined ? message.force_web_search : true;
        MANUAL_ASSIST_PLUS_N = !!message.manual_assist_plusN;
        AUTO_CLICK_PLUS_N = !!message.auto_click_plusN;
        
        console.log(`[Extension] Starting data collection for ${queries.length} queries, ${runs_per_q} runs each, web search: ${force_web_search ? 'forced' : 'optional'}`);
        debugLog(`config: manual_assist_plusN=${MANUAL_ASSIST_PLUS_N}`);
        debugLog(`config: auto_click_plusN=${AUTO_CLICK_PLUS_N}`);
        
        const csvData = await processQueries(queries, runs_per_q, force_web_search);
        
        // send CSV data back to sidepanel
        chrome.runtime.sendMessage({
          action: 'dataCollectionComplete',
          csvData: csvData,
          totalResults: queries.length * runs_per_q
        });
        
        console.log('[Extension] Data collection completed successfully');
        sendResponse("finished!");
      } catch (err) {
        console.error('[Extension] Data collection error:', err);
        chrome.runtime.sendMessage({
          action: 'dataCollectionError',
          error: err.message
        });
        sendResponse("error");
      }
    })();

    return true;
  }
});