const SCRAPER_VERSION = 'google-v1';
console.log(`Google Search Scraper content.js loaded (${SCRAPER_VERSION})`);

// values for timeout and delay
const CONTENT_TIMEOUT = 15000; // 15 seconds
const DEFAULT_CONTENT_DELAY_MS = 1000; // delay between batches
const DEFAULT_MAX_CONCURRENT = 2; // max concurrent content requests

// ================== SELECTORS (GOOGLE SPECIFIC) ==================

const SEARCH_INPUT = 'textarea[name="q"], input[name="q"]';
const SEARCH_BUTTON = 'button[type="submit"], input[type="submit"]';

// target only organic results, exclude ads
// Google organic results are usually in div.g, div[data-sok], or div.tF2Cxc
// Added .A6K0A and .MjjYud based on user DOM inspection
const SEARCH_RESULTS = 'div.g, div.tF2Cxc, div.A6K0A, div.MjjYud, div[data-sok]';
const RESULT_TITLE = 'h3, .LC20lb, .vv779b, .Ww4FFb';
const RESULT_URL = 'a[href]';
const RESULT_SNIPPET = '.VwiC3b, .yXK7lf, .st, .MUF6y, .pI9Wpc, div[style*="-webkit-line-clamp"]';

const NEXT_PAGE_BUTTON = '#pnnext, a[id="pnnext"]';
const CURRENT_PAGE = 'td.cur';

// ================== HELPER FUNCTIONS ==================

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

  element.scrollIntoView({ behavior: 'smooth', block: 'center' });
  await pauseSeconds(0.5);

  element.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true }));
  element.dispatchEvent(new PointerEvent("pointerup", { bubbles: true }));

  const event = new MouseEvent("click", {
    bubbles: true,
    cancelable: true,
    view: window,
  });
  element.dispatchEvent(event);
}

async function simulateTyping(selector, text, clearFirst = true) {
  const element = await waitForSelector(selector);
  if (!element) {
    throw new Error(`Element with selector "${selector}" not found!`);
  }
  
  element.focus();
  element.click();
  await pauseSeconds(0.2);
  
  if (clearFirst) {
    element.value = '';
    element.dispatchEvent(new Event('input', { bubbles: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
    await pauseSeconds(0.2);
  }

  for (const char of text) {
    document.execCommand('insertText', false, char);
    if (!element.value.endsWith(char)) {
      element.value += char;
    }
    element.dispatchEvent(new Event('input', { bubbles: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
    await pauseSeconds(getRandomInt(10, 50) / 1000);
  }
  
  await pauseSeconds(0.5);
}

async function waitForSelector(selector, timeout = 15000) {
  return new Promise((resolve) => {
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

async function waitForResultsToLoad() {
  await waitForSelector(SEARCH_RESULTS, 10000);
  await pauseSeconds(getRandomInt(1, 2));
}

function extractSearchResults() {
  const results = [];
  // Try multiple container selectors
  const resultElements = document.querySelectorAll(SEARCH_RESULTS);
  console.log(`Content Script: Found ${resultElements.length} potential result elements using primary selectors`);
  
  const pageNum = (() => {
    try {
      const t = document.querySelector(CURRENT_PAGE)?.textContent?.trim() || '';
      const n = parseInt(t, 10);
      return Number.isFinite(n) ? n : 1;
    } catch {
      return 1;
    }
  })();
  
  let resultPosition = 1;
  
  resultElements.forEach((resultElement) => {
    try {
      // Basic ad check for Google
      if (resultElement.closest('.ad2-ad') || resultElement.querySelector('.sh-ac__ad-link') || resultElement.querySelector('.admin-note')) {
        return;
      }

      const titleElement = resultElement.querySelector(RESULT_TITLE);
      const title = titleElement?.textContent?.trim() || '';
      
      // Find the link - Google often wraps the title in the <a> or vice versa
      let linkElement = resultElement.querySelector(RESULT_URL);
      // If the container itself is an <a>, use it
      if (resultElement.tagName === 'A') linkElement = resultElement;
      
      const actualUrl = linkElement?.href || '';
      
      // Filter out internal Google links or empty results
      if (!title || !actualUrl || actualUrl.includes('google.com/search') || actualUrl.startsWith('javascript:')) {
        return;
      }
      
      const snippetElement = resultElement.querySelector(RESULT_SNIPPET);
      const snippet = snippetElement?.textContent?.trim() || '';
      
      results.push({
        position: resultPosition++,
        title: title,
        url: actualUrl,
        domain: new URL(actualUrl).hostname.replace('www.', ''),
        displayUrl: actualUrl,
        snippet: snippet,
        page_num: pageNum,
      });
      
    } catch (error) {
      // console.warn('Error extracting result:', error);
    }
  });
  
  // FALLBACK: If still 0, try finding any H3 that looks like a result
  if (results.length === 0) {
    console.log("Content Script: 0 results found with containers, trying H3 fallback...");
    document.querySelectorAll('h3').forEach(h3 => {
      const a = h3.closest('a');
      if (a && a.href && !a.href.includes('google.com')) {
        results.push({
          position: resultPosition++,
          title: h3.textContent.trim(),
          url: a.href,
          domain: new URL(a.href).hostname.replace('www.', ''),
          displayUrl: a.href,
          snippet: '',
          page_num: pageNum
        });
      }
    });
  }
  
  console.log(`Content Script: Successfully extracted ${results.length} results`);
  return results;
}

// ================== COMMUNICATION ==================

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "performSearch") {
    performSearch(message.query)
      .then(result => sendResponse(result))
      .catch(err => sendResponse({ status: 'error', error: err.message }));
    return true;
  }
  
  if (message.action === "scrapePage") {
    scrapeCurrentPage()
      .then(({ results, nextPageUrl }) => sendResponse({ status: 'success', results, nextPageUrl }))
      .catch(err => sendResponse({ status: 'error', error: err.message }));
    return true;
  }

  if (message.action === "clickNextPage") {
    const nextBtn = document.querySelector(NEXT_PAGE_BUTTON);
    if (nextBtn) {
      nextBtn.click();
      sendResponse({ status: 'success', clicked: true });
    } else {
      sendResponse({ status: 'success', clicked: false });
    }
    return true;
  }
});

async function performSearch(query) {
  await simulateTyping(SEARCH_INPUT, query, true);
  await pauseSeconds(0.5);
  
  // Press Enter instead of finding button which can be tricky on Google
  const input = document.querySelector(SEARCH_INPUT);
  input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true }));
  
  return { status: 'ready' };
}

async function scrapeCurrentPage() {
  await waitForResultsToLoad();
  const results = extractSearchResults();
  const nextBtn = document.querySelector(NEXT_PAGE_BUTTON);
  const nextPageUrl = nextBtn ? nextBtn.href : null;
  return { results, nextPageUrl };
}
