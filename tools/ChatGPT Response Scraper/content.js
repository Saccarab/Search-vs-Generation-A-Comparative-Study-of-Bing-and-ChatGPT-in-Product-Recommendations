console.log("ChatGPT Response Scraper - Content script loaded");

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

async function waitForResponseFinished(selector, timeoutMs = 120000) {
  return new Promise((resolve, reject) => {
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
      if (btn && btn.getAttribute("data-testid") === "send-button") {
        cleanup();
        resolve({ searchQuery: capturedSearchQuery, webSearchTriggered });
        return true;
      }
      return false;
    };

    const observer = new MutationObserver(() => check());

    const cleanup = () => {
      observer.disconnect();
      clearInterval(pollId);
      clearTimeout(timer);
    };

    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["data-testid"],
    });

    const timer = setTimeout(() => {
      cleanup();
      reject(new Error("Timeout waiting for response to finish"));
    }, timeoutMs);

    // Poll in case the UI updates without triggering a useful mutation at the right time
    const pollId = setInterval(() => {
      try { captureSearchQuery(); } catch {}
    }, 250);

    check();
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
      'div[role="dialog"], div[role="tooltip"], div[role="menu"], div[class*="popover"], div[class*="tooltip"]'
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
  const linkEls = container.querySelectorAll('a[href^="http"]');
  linkEls.forEach(a => {
    const href = a.href;
    if (!href || href.includes('chatgpt.com')) return;
    const cleaned = cleanInlineUrl(href);
    if (seen.has(cleaned)) return;
    seen.add(cleaned);
    out.push({
      url: cleaned,
      domain: extractDomainFromUrl(cleaned),
      title: safeText(a) || '',
    });
  });
  return out;
}

async function tryExpandPopoverCarousel(container, maxSteps = 8) {
  if (!container) return [];
  const collected = [];
  const seenUrls = new Set();

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

  for (let i = 0; i < maxSteps; i++) {
    const nextBtn =
      container.querySelector('button[aria-label*="Next"], button[aria-label*="next"], button[title*="Next"], button[title*="next"]') ||
      Array.from(container.querySelectorAll('button')).find(b => /next/i.test(safeText(b)));
    if (!nextBtn) break;

    const disabled = nextBtn.disabled || nextBtn.getAttribute('aria-disabled') === 'true';
    if (disabled) break;

    nextBtn.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
    nextBtn.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }));
    nextBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
    await pauseSeconds(0.25);

    const beforeCount = collected.length;
    collect();
    if (collected.length === beforeCount) break;
  }

  return collected;
}

async function extractInlineItemCitations() {
  const messageElements = document.querySelectorAll(ASSISTANT_MSG);
  if (!messageElements || messageElements.length === 0) return [];
  const lastResponse = messageElements[messageElements.length - 1];

  const items = [];
  let currentSection = '';
  let itemPos = 0;

  const normalizeUrl = (u) => {
    try { return cleanUrl(u); } catch { return u; }
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

    if (tag === 'li') {
      const clone = el.cloneNode(true);
      clone.querySelectorAll('button, [role="button"], .rounded-full, .badge, .chip').forEach(n => n.remove());
      const itemText = safeText(clone);
      if (!itemText) continue;

      itemPos += 1;
      const itemName = deriveItemName(itemText);

      const chipCandidates = Array.from(el.querySelectorAll('button, [role="button"], a'))
        .filter(c => {
          const t = safeText(c);
          if (!t) return false;
          if (t.length > 50) return false;
          if (/copy|share|edit/i.test(t)) return false;
          return true;
        })
        .slice(0, 6);

      const chipGroups = [];
      for (const chip of chipCandidates) {
        try {
          // IMPORTANT: Never click anchor links; ChatGPT source links are <a target="_blank"> and will open tabs.
          // For anchors, just read the href and treat it as a single-link group.
          if (chip && chip.tagName && chip.tagName.toLowerCase() === 'a') {
            const href = chip.href || chip.getAttribute('href') || '';
            if (href && /^https?:\/\//i.test(href)) {
              chipGroups.push({ links: [normalizeUrl(href)] });
            }
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
      let value = result[header] || '';
      
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
    // check if sources button exists before trying to click it
    const sourcesButton = document.querySelector(OPEN_SOURCES_BTN);
    if (sourcesButton) {
      console.log('Sources button found - extracting sources');
      await simulateClick(OPEN_SOURCES_BTN);
      await pauseSeconds(getRandomInt(1, 2));
      
      const sourceLinks = await extractSourceLinks();
      
      // try to close the sources panel
      const closeButton = document.querySelector(CLOSE_SOURCES_BTN);
      if (closeButton) {
        await simulateClick(CLOSE_SOURCES_BTN);
        await pauseSeconds(getRandomInt(0.5, 1));
      }
      
      // add source data to result
      result.sources_cited = sourceLinks.citations || [];
      result.sources_additional = sourceLinks.additional || [];
      
      // create union of cited and additional sources
      const seenUrls = new Set();
      result.sources_all = [];
      
      for (const source of [...result.sources_cited, ...result.sources_additional]) {
        if (!seenUrls.has(source.url)) {
          seenUrls.add(source.url);
          result.sources_all.push(source);
        }
      }
      
      // helper function to extract domain in format domain.something (second-level domain + TLD)
      const extractDomain = (source) => {
        try {
          const url = new URL(source.url);
          const hostname = url.hostname || '';
          
          // split hostname by dots
          const parts = hostname.split('.');
          
          // if less than 2 parts, return as is
          if (parts.length < 2) return hostname;
          
          // return last two parts (domain.tld)
          return parts.slice(-2).join('.');
        } catch (e) {
          return '';
        }
      };
      
      // extract domains from each source type
      result.domains_cited = result.sources_cited.map(source => extractDomain(source)).filter(Boolean);
      result.domains_additional = result.sources_additional.map(source => extractDomain(source)).filter(Boolean);
      result.domains_all = result.sources_all.map(source => extractDomain(source)).filter(Boolean);
      
      // remove duplicate domains for domains_all
      const uniqueDomains = new Set(result.domains_all);
      result.domains_all = Array.from(uniqueDomains);
      
      console.log(`Found ${result.sources_cited.length} citations, ${result.sources_additional.length} additional sources, ${result.sources_all.length} total unique sources`);
    } else {
      console.log(`No sources button found - ChatGPT did not use web search for this query${force_web_search ? ' (despite being forced)' : ''}`);
      result.sources_cited = [];
      result.sources_additional = [];
      result.sources_all = [];
      result.domains_cited = [];
      result.domains_additional = [];
      result.domains_all = [];
      
      // FAILSAFE: if web search was forced but no sources found, retry
      if (force_web_search && retryCount < maxRetries) {
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

        // Item-level inline extraction (chips/+N) serialized as JSON. We keep the exporter 1-row-per-run.
        let items = [];
        try {
          items = await extractInlineItemCitations();
        } catch (e) {
          items = [];
        }
        
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
          items_json: (() => { try { return JSON.stringify(items); } catch { return '[]'; } })(),
          items_count: Array.isArray(items) ? items.length : 0,
          items_with_citations_count: Array.isArray(items)
            ? items.filter(it => Array.isArray(it.chip_groups) && it.chip_groups.some(g => Array.isArray(g.links) && g.links.length > 0)).length
            : 0,
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
        
        console.log(`[Extension] Starting data collection for ${queries.length} queries, ${runs_per_q} runs each, web search: ${force_web_search ? 'forced' : 'optional'}`);
        
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