const SCRAPER_VERSION = 'deep-hunter-v2';
console.log(`Bing Deep Hunter content.js loaded (${SCRAPER_VERSION})`);

// ================== SELECTORS ==================

const SEARCH_INPUT = '#sb_form_q';
const SEARCH_BUTTON = '#sb_form_go';

// target only organic results, exclude ads
const SEARCH_RESULTS = '.b_algo:not(.b_adTop):not(.b_adBottom):not([data-apurl])';
const RESULT_TITLE = 'h2 a';
const RESULT_URL = 'cite';
const RESULT_SNIPPET = [
  '.b_caption p',
  '.b_caption .b_dList',
  '.b_caption span',
  '.b_caption div',
  '.b_paractl',
  '.b_snippet',
].join(', ');
const CURRENT_PAGE = '.sb_pagS';

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
    element.dispatchEvent(new KeyboardEvent('keydown', { key: char, bubbles: true }));
    element.dispatchEvent(new KeyboardEvent('keyup', { key: char, bubbles: true }));
    await pauseSeconds(getRandomInt(10, 50) / 1000);
  }
  
  await pauseSeconds(0.5);
  if (element.value !== text) {
    element.value = text;
    element.dispatchEvent(new Event('input', { bubbles: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
  }
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
  await pauseSeconds(getRandomInt(2, 4));
  
  let previousCount = 0;
  let stableCount = 0;
  
  for (let i = 0; i < 10; i++) {
    const currentCount = document.querySelectorAll(SEARCH_RESULTS).length;
    if (currentCount === previousCount && currentCount > 0) {
      stableCount++;
      if (stableCount >= 3) break;
    } else {
      stableCount = 0;
    }
    previousCount = currentCount;
    await pauseSeconds(0.5);
  }
}

function base64urlDecode(str) {
  let base64 = str.replace(/-/g, '+').replace(/_/g, '/');
  while (base64.length % 4) base64 += '=';
  return atob(base64);
}

function cleanUrl(url) {
  try {
    if (!url.startsWith('http')) return url;
    const urlObj = new URL(url);
    const params = new URLSearchParams(urlObj.search);
    const trackingParams = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'fbclid', 'gclid', 'ref', 'source'];
    trackingParams.forEach(param => params.delete(param));
    urlObj.search = params.toString();
    return urlObj.toString();
  } catch (error) {
    return url;
  }
}

function getActualUrl(linkElement) {
  const originalUrl = linkElement.href;
  try {
    if (originalUrl.includes('bing.com')) {
      const url = new URL(originalUrl);
      if (url.searchParams.has('u')) {
        let encodedUrl = url.searchParams.get('u');
        try {
          const urlDecoded = decodeURIComponent(encodedUrl);
          if (urlDecoded.startsWith('http')) return cleanUrl(urlDecoded);
        } catch (e) {}
        
        try {
          if (encodedUrl.startsWith('a1')) encodedUrl = encodedUrl.substring(2);
          const directDecoded = base64urlDecode(encodedUrl);
          if (directDecoded.startsWith('http')) return cleanUrl(directDecoded);
        } catch (e) {}
      }
      const pathMatch = originalUrl.match(/\/(?:aclick|ck)\/.*?u=([^&]+)/);
      if (pathMatch) {
        const encodedUrl = decodeURIComponent(pathMatch[1]);
        try {
          const base64Decoded = base64urlDecode(encodedUrl.replace(/^a1/, ''));
          if (base64Decoded.startsWith('http')) return cleanUrl(base64Decoded);
        } catch (e) {}
      }
    }
    return cleanUrl(originalUrl);
  } catch (error) {
    return cleanUrl(originalUrl);
  }
}

function extractDomain(url) {
  try {
    return new URL(url).hostname.replace('www.', '');
  } catch {
    return url;
  }
}

function isAdClickUrl(url) {
  try {
    const u = new URL(url);
    const host = (u.hostname || '').toLowerCase().replace(/^www\./, '');
    const href = u.href.toLowerCase();
    const badHosts = ['ad.doubleclick.net', 'doubleclick.net', 'googleadservices.com', 'googlesyndication.com', 'adservice.google.com'];
    if (badHosts.some(h => host === h || host.endsWith(`.${h}`))) return true;
    if (host.endsWith('bing.com') && (href.includes('/aclick') || href.includes('/clk') || href.includes('/sclk'))) return true;
    return false;
  } catch {
    return false;
  }
}

function isSponsoredResultElement(resultElement) {
  if (!resultElement) return false;
  
  try {
    const text = (resultElement.innerText || '').replace(/\s+/g, ' ').trim();
    if (/^Sponsored\b/i.test(text)) return true;
  } catch (e) {}

  if (resultElement.querySelector('.adsMvCarousel, .adsMvC, .b_ads1line, .ad_em, .mnau')) return true;

  const parentLi = resultElement.closest('li');
  if (parentLi) {
    const parentHtml = parentLi.outerHTML || '';
    if (/adsMv|b_ads|ad_em|mv-data="Ads|sponsored/i.test(parentHtml)) return true;
    
    let sibling = parentLi.previousElementSibling;
    for (let i = 0; i < 3 && sibling; i++) {
      const siblingText = sibling.textContent || '';
      if (/sponsored/i.test(siblingText) && siblingText.length < 100) return true;
      sibling = sibling.previousElementSibling;
    }
  }
  
  const elementsToCheck = [resultElement, ...resultElement.querySelectorAll('*')];
  for (const el of elementsToCheck) {
    try {
      const style = window.getComputedStyle(el, '::before');
      const content = style.content;
      if (content && content !== 'none' && content !== '""' && /sponsored/i.test(content)) return true;
      if (content && /^url\(/i.test(content) && el.tagName === 'P' && el.closest('.b_caption')) {
        const pad = style.padding || '';
        if (/\b0px 1px\b/.test(pad)) return true;
      }
    } catch (e) {}
  }
  
  if (/adsMv|b_ads|ad_em|mv-data="Ads/i.test(resultElement.outerHTML || '')) return true;
  
  return false;
}

function extractSearchResults() {
  const results = [];
  const resultElements = document.querySelectorAll(SEARCH_RESULTS);
  const pageNum = (() => {
    try {
      const t = document.querySelector(CURRENT_PAGE)?.textContent?.trim() || '';
      const n = parseInt(t, 10);
      return Number.isFinite(n) ? n : 1;
    } catch { return 1; }
  })();
  
  let resultPosition = 1;
  resultElements.forEach((resultElement, index) => {
    try {
      if (isSponsoredResultElement(resultElement)) return;
      
      const titleElement = resultElement.querySelector(RESULT_TITLE);
      const title = titleElement?.textContent?.trim() || '';
      if (!title || !titleElement) return;
      
      const actualUrl = getActualUrl(titleElement);
      if (actualUrl && (isAdClickUrl(actualUrl) || actualUrl.includes('bing.com/ck/'))) return;
      
      const snippetElement = resultElement.querySelector(RESULT_SNIPPET);
      let snippet = snippetElement?.textContent?.trim() || '';
      if (!snippet) {
        const pCandidates = Array.from(resultElement.querySelectorAll('p'))
          .map(p => p.textContent?.trim() || '')
          .filter(t => t && t.length > 20 && t.length < 500);
        snippet = pCandidates[0] || '';
      }
      
      const citeElement = resultElement.querySelector(RESULT_URL);
      const displayUrl = citeElement?.textContent?.trim() || extractDomain(actualUrl);
      
      if (title && actualUrl) {
        results.push({
          position: resultPosition++,
          title: title,
          url: actualUrl,
          domain: extractDomain(actualUrl),
          displayUrl: displayUrl,
          snippet: snippet,
          page_num: pageNum,
        });
      }
    } catch (error) {}
  });
  return results;
}

// ================== ATOMIC ACTIONS ==================

async function performSearch(query) {
  try {
    const currentInput = document.querySelector(SEARCH_INPUT);
    const currentVal = currentInput ? currentInput.value.trim() : '';
    if (currentInput && currentVal === query.trim() && document.querySelectorAll(SEARCH_RESULTS).length > 0) {
      return { status: 'ready', method: 'existing' };
    }
    await simulateTyping(SEARCH_INPUT, query, true);
    await pauseSeconds(0.5);
    await simulateClick(SEARCH_BUTTON);
    try {
      await waitForResultsToLoad();
      return { status: 'ready', method: 'spa' };
    } catch (e) {
      return { status: 'unknown' };
    }
  } catch (error) {
    throw error;
  }
}

async function scrapeCurrentPage() {
  await waitForResultsToLoad();
  const results = extractSearchResults();
  const nextBtn = document.querySelector('.sb_pagN');
  const nextPageUrl = nextBtn ? nextBtn.href : null;
  return { results, nextPageUrl };
}

// ================== COMMUNICATION ==================

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "performSearch") {
    performSearch(message.query)
      .then(result => sendResponse(result))
      .catch(err => sendResponse({ status: 'error', error: err.message }));
    return true;
  }
  
  if (message.action === "scrapePage" || message.action === "scrape") {
    scrapeCurrentPage()
      .then(({ results, nextPageUrl }) => sendResponse({ status: 'success', results, nextPageUrl }))
      .catch(err => sendResponse({ status: 'error', error: err.message }));
    return true;
  }
  
  if (message.action === "clickNextPage") {
    const nextBtn = document.querySelector('.sb_pagN');
    if (nextBtn) {
      nextBtn.click();
      sendResponse({ status: 'success', clicked: true });
    } else {
      sendResponse({ status: 'success', clicked: false });
    }
    return true;
  }
});
