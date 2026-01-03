// console.log("Bing Search Scraper with Content Extraction - Content script loaded");

// values for timeout and delay
const CONTENT_TIMEOUT = 15000; // 15 seconds
const REQUEST_DELAY = 5000; // 5 seconds between requests
const MAX_CONCURRENT = 1; // max concurrent content requests

// ================== SELECTORS ==================

const SEARCH_INPUT = '#sb_form_q';
const SEARCH_BUTTON = '#sb_form_go';

// target only organic results, exclude ads
const SEARCH_RESULTS = '.b_algo:not(.b_adTop):not(.b_adBottom):not([data-apurl])';
const RESULT_TITLE = 'h2 a';
const RESULT_URL = 'cite';
const RESULT_SNIPPET = '.b_caption p, .b_caption .b_dList';
const NEXT_PAGE_BUTTON = '.sb_pagN';
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

  // scroll element into view
  element.scrollIntoView({ behavior: 'smooth', block: 'center' });
  await pauseSeconds(0.5);

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

async function simulateTyping(selector, text, clearFirst = true) {
  const element = await waitForSelector(selector);
  if (!element) {
    throw new Error(`Element with selector "${selector}" not found!`);
  }
  
  element.focus();
  element.click(); // Ensure focus
  await pauseSeconds(0.2);
  
  if (clearFirst) {
    // clear existing text
    element.value = '';
    element.dispatchEvent(new Event('input', { bubbles: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
    await pauseSeconds(0.2);
  }

  // Set value directly first to ensure it sticks
  // element.value = text;
  
  // Then "type" it for visual effect and event triggers
  for (const char of text) {
    // element.value += char; // This appends if we don't clear perfectly
    // Better: update value incrementally
    const currentLen = element.value.length;
    // element.value = text.substring(0, currentLen + 1); // This might be buggy if we didn't start empty
    
    // Simplest reliable way for React inputs:
    document.execCommand('insertText', false, char);
    
    // Fallback if execCommand doesn't work (deprecated but effective)
    if (!element.value.endsWith(char)) {
    element.value += char;
    }

    element.dispatchEvent(new Event('input', { bubbles: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
    element.dispatchEvent(new KeyboardEvent('keydown', { key: char, bubbles: true }));
    element.dispatchEvent(new KeyboardEvent('keyup', { key: char, bubbles: true }));
    
    await pauseSeconds(getRandomInt(10, 50) / 1000); // faster typing
  }
  
  // Final verification
  await pauseSeconds(0.5);
  if (element.value !== text) {
      console.log(`Typing mismatch. Wanted: "${text}", Got: "${element.value}". Forcing value.`);
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
  // wait for search results to appear and stabilize
  await waitForSelector(SEARCH_RESULTS, 10000);
  await pauseSeconds(getRandomInt(2, 4));
  
  // wait a bit more to ensure all results are loaded
  let previousCount = 0;
  let stableCount = 0;
  
  for (let i = 0; i < 10; i++) {
    const currentCount = document.querySelectorAll(SEARCH_RESULTS).length;
    if (currentCount === previousCount && currentCount > 0) {
      stableCount++;
      if (stableCount >= 3) break; // results are stable
    } else {
      stableCount = 0;
    }
    previousCount = currentCount;
    await pauseSeconds(0.5);
  }
}

function getActualUrl(linkElement) {
  const originalUrl = linkElement.href;
  
  try {
    // method 1: try to parse Bing redirect parameters
    if (originalUrl.includes('bing.com')) {
      const url = new URL(originalUrl);
      
      // pattern 1: check 'u' parameter with base64 decoding
      if (url.searchParams.has('u')) {
        let encodedUrl = url.searchParams.get('u');
        
        // try URL decoding first
        try {
          const urlDecoded = decodeURIComponent(encodedUrl);
          if (urlDecoded.startsWith('http')) {
            console.log(`URL decoded: ${originalUrl.substring(0, 50)}... -> ${urlDecoded}`);
            return cleanUrl(urlDecoded);
          }
        } catch (e) {
          // URL decoding failed, continue to base64
        }
        
        // try base64 decoding (Bing often uses this)
        try {
          // remove common prefixes that Bing adds before base64
          if (encodedUrl.startsWith('a1')) {
            encodedUrl = encodedUrl.substring(2);
          } else if (encodedUrl.match(/^[a-zA-Z0-9]{1,4}/)) {
            // try removing first 1-4 characters if they look like prefixes
            for (let prefixLen = 1; prefixLen <= 4; prefixLen++) {
              try {
                const testUrl = encodedUrl.substring(prefixLen);
                const decoded = atob(testUrl);
                if (decoded.startsWith('http')) {
                  console.log(`Base64 decoded (prefix ${prefixLen}): ${originalUrl.substring(0, 50)}... -> ${decoded}`);
                  return cleanUrl(decoded);
                }
              } catch (e) {
                // continue trying different prefix lengths
              }
            }
          }
          
          // try direct base64 decode
          const directDecoded = atob(encodedUrl);
          if (directDecoded.startsWith('http')) {
            console.log(`Base64 decoded: ${originalUrl.substring(0, 50)}... -> ${directDecoded}`);
            return cleanUrl(directDecoded);
          }
        } catch (e) {
          // console.warn('Base64 decoding failed:', e.message);
        }
        
        // try hex decoding as fallback
        try {
          if (encodedUrl.match(/^[0-9a-f]+$/i)) {
            const hexDecoded = encodedUrl.match(/.{1,2}/g).map(byte => String.fromCharCode(parseInt(byte, 16))).join('');
            if (hexDecoded.includes('http')) {
              console.log(`Hex decoded: ${originalUrl.substring(0, 50)}... -> ${hexDecoded}`);
              return cleanUrl(hexDecoded);
            }
          }
        } catch (e) {
          // continue to next method
        }
      }
      
      // pattern 2: check URL in pathname
      const pathMatch = originalUrl.match(/\/(?:aclick|ck)\/.*?u=([^&]+)/);
      if (pathMatch) {
        const encodedUrl = decodeURIComponent(pathMatch[1]);
        try {
          const base64Decoded = atob(encodedUrl.replace(/^a1/, ''));
          if (base64Decoded.startsWith('http')) {
            console.log(`Path base64 decoded: ${originalUrl.substring(0, 50)}... -> ${base64Decoded}`);
            return cleanUrl(base64Decoded);
          }
        } catch (e) {
          if (encodedUrl.startsWith('http')) {
            console.log(`Path URL decoded: ${originalUrl.substring(0, 50)}... -> ${encodedUrl}`);
            return cleanUrl(encodedUrl);
          }
        }
      }
      
      // console.warn(`Could not parse Bing redirect: ${originalUrl.substring(0, 100)}...`);
      // console.warn(`  u parameter value: ${url.searchParams.get('u') || 'not found'}`);
    }
    
    // if URL doesn't need processing or parsing failed, return cleaned original
    return cleanUrl(originalUrl);
    
  } catch (error) {
    // console.error('Error processing URL:', error);
    return cleanUrl(originalUrl);
  }
}

function cleanUrl(url) {
  try {
    if (!url.startsWith('http')) return url;
    
    const urlObj = new URL(url);
    const params = new URLSearchParams(urlObj.search);
    
    // remove tracking parameters
    const trackingParams = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'fbclid', 'gclid', 'ref', 'source'];
    trackingParams.forEach(param => params.delete(param));
    
    urlObj.search = params.toString();
    return urlObj.toString();
  } catch (error) {
    return url;
  }
}

function extractDomain(url) {
  try {
    return new URL(url).hostname.replace('www.', '');
  } catch {
    return url;
  }
}

function extractSearchResults() {
  const results = [];
  const resultElements = document.querySelectorAll(SEARCH_RESULTS);
  
  console.log(`Found ${resultElements.length} organic search results on current page`);
  
  // first, let's verify we're only getting organic results
  const allResultElements = document.querySelectorAll('.b_algo');
  const adElements = document.querySelectorAll('.b_ad, .b_adTop, .b_adBottom, [data-apurl]');
  console.log(`Total .b_algo elements: ${allResultElements.length}, Ad elements: ${adElements.length}, Organic: ${resultElements.length}`);
  
  let resultPosition = 1;
  
  resultElements.forEach((resultElement, index) => {
    try {
      // double-check this isn't an ad
      if (resultElement.classList.contains('b_ad') || 
          resultElement.classList.contains('b_adTop') || 
          resultElement.classList.contains('b_adBottom') ||
          resultElement.hasAttribute('data-apurl') ||
          resultElement.querySelector('.b_ad')) {
        console.log(`Skipping ad element at position ${index + 1}`);
        return;
      }
      
      // extract title and URL
      const titleElement = resultElement.querySelector(RESULT_TITLE);
      const title = titleElement?.textContent?.trim() || '';
      
      if (!title || !titleElement) {
        // console.warn(`Skipping result ${index + 1}: No title found`);
        return;
      }
      
      console.log(`Processing organic result ${index + 1}: ${title}`);
      
      // get the actual URL by parsing redirect
      const actualUrl = getActualUrl(titleElement);
      
      // extract snippet
      const snippetElement = resultElement.querySelector(RESULT_SNIPPET);
      const snippet = snippetElement?.textContent?.trim() || '';
      
      // extract displayed URL/domain
      const citeElement = resultElement.querySelector(RESULT_URL);
      const displayUrl = citeElement?.textContent?.trim() || extractDomain(actualUrl);
      
      // only add if we have title and URL
      if (title && actualUrl) {
        results.push({
          position: resultPosition++,
          title: title,
          url: actualUrl,
          domain: extractDomain(actualUrl),
          displayUrl: displayUrl,
          snippet: snippet
        });
        
        // console.log(`Extracted organic result ${resultPosition - 1}: ${actualUrl}`);
      } else {
        // console.warn(`Skipped result ${index + 1}: Missing data`);
      }
      
    } catch (error) {
      // console.warn(`Error extracting result ${index + 1}:`, error);
    }
  });
  
  console.log(`Successfully extracted ${results.length} organic results`);
  return results;
}

// ================== CONTENT EXTRACTION ==================

async function fetchUrlContent(url, timeout = CONTENT_TIMEOUT) {
  return new Promise((resolve) => {
    const timeoutId = setTimeout(() => {
      resolve({ content: '', error: 'Timeout' });
    }, timeout);

    // send message to background script to fetch content
    chrome.runtime.sendMessage({
      action: 'fetchContent',
      url: url,
      timeout: timeout
    }, (response) => {
      clearTimeout(timeoutId);
      if (chrome.runtime.lastError) {
        resolve({ content: '', error: chrome.runtime.lastError.message });
      } else {
        resolve(response || { content: '', error: 'No response' });
      }
    });
  });
}

function extractTextFromHtml(html) {
  try {
    // create a temporary element to parse HTML
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = html;
    
    // remove script and style elements
    const scripts = tempDiv.querySelectorAll('script, style, noscript');
    scripts.forEach(el => el.remove());

    // remove obviously hidden elements (best-effort)
    // Note: this is heuristic (we don't have computed styles here), but it reduces
    // false positives where text exists in source but isn't visible to users.
    const hiddenSelectors = [
      '[hidden]',
      '[aria-hidden="true"]',
      '[style*="display:none"]',
      '[style*="display: none"]',
      '[style*="visibility:hidden"]',
      '[style*="visibility: hidden"]',
      // common utility classes
      '.sr-only',
      '.visually-hidden',
      '.hidden',
      '.invisible'
    ];
    hiddenSelectors.forEach(selector => {
      const elements = tempDiv.querySelectorAll(selector);
      elements.forEach(el => el.remove());
    });
    
    // remove common non-content elements
    const nonContentSelectors = [
      'nav', 'header', 'footer', 'aside', 
      '.navigation', '.nav', '.menu', '.sidebar',
      '.advertisement', '.ad', '.ads', '.cookie',
      '.popup', '.modal', '.overlay'
    ];
    
    nonContentSelectors.forEach(selector => {
      const elements = tempDiv.querySelectorAll(selector);
      elements.forEach(el => el.remove());
    });
    
    // get text content
    let text = tempDiv.textContent || tempDiv.innerText || '';
    
    // clean up the text
    text = text
      .replace(/\s+/g, ' ') // replace multiple whitespace with single space
      .replace(/\n\s*\n/g, '\n') // remove empty lines
      .trim();
    
    // limit text length to prevent huge content
    const maxLength = Infinity;
    if (text.length > maxLength) {
      text = text.substring(0, maxLength) + '...';
    }
    
    return text;
  } catch (error) {
    // console.error('Error extracting text from HTML:', error);
    return '';
  }
}

function extractMetadataFromHtml(html) {
  const meta = {
    page_title: '',
    meta_description: '',
    canonical_url: '',
    has_schema_markup: false,
    schema_types: '',
    table_count: 0,
    has_table: false,
    published_date: '',
    modified_date: '',
    js_render_suspected: false,
  };

  try {
    const doc = new DOMParser().parseFromString(html, 'text/html');

    // title
    meta.page_title =
      (doc.querySelector('meta[property="og:title"]')?.getAttribute('content') || '').trim() ||
      (doc.querySelector('title')?.textContent || '').trim();

    // description
    meta.meta_description =
      (doc.querySelector('meta[name="description"]')?.getAttribute('content') || '').trim() ||
      (doc.querySelector('meta[property="og:description"]')?.getAttribute('content') || '').trim();

    // canonical
    meta.canonical_url = (doc.querySelector('link[rel="canonical"]')?.getAttribute('href') || '').trim();

    // tables
    meta.table_count = doc.querySelectorAll('table').length;
    meta.has_table = meta.table_count > 0;

    // schema
    const schemaScripts = Array.from(doc.querySelectorAll('script[type="application/ld+json"]'));
    if (schemaScripts.length > 0) meta.has_schema_markup = true;

    const schemaTypes = new Set();
    const dateCandidates = { published: [], modified: [] };

    const addType = (t) => {
      if (!t) return;
      if (Array.isArray(t)) t.forEach(addType);
      else schemaTypes.add(String(t));
    };

    const walkSchema = (obj) => {
      if (!obj) return;
      if (Array.isArray(obj)) return obj.forEach(walkSchema);
      if (typeof obj !== 'object') return;

      addType(obj['@type']);
      if (obj.datePublished) dateCandidates.published.push(obj.datePublished);
      if (obj.dateModified) dateCandidates.modified.push(obj.dateModified);

      // common container fields
      if (obj['@graph']) walkSchema(obj['@graph']);
      if (obj.mainEntity) walkSchema(obj.mainEntity);
      if (obj.mainEntityOfPage) walkSchema(obj.mainEntityOfPage);
    };

    for (const s of schemaScripts) {
      const raw = (s.textContent || '').trim();
      if (!raw) continue;
      try {
        const parsed = JSON.parse(raw);
        walkSchema(parsed);
      } catch {
        // ignore malformed JSON-LD
      }
    }

    meta.schema_types = Array.from(schemaTypes).slice(0, 20).join('|');

    // meta-based dates
    const metaDateSelectors = [
      'meta[property="article:published_time"]',
      'meta[name="pubdate"]',
      'meta[name="publishdate"]',
      'meta[name="timestamp"]',
      'meta[name="date"]',
      'meta[itemprop="datePublished"]',
    ];
    const metaModSelectors = [
      'meta[property="article:modified_time"]',
      'meta[name="lastmod"]',
      'meta[name="last-modified"]',
      'meta[itemprop="dateModified"]',
    ];

    const firstMetaContent = (selectors) => {
      for (const sel of selectors) {
        const v = (doc.querySelector(sel)?.getAttribute('content') || '').trim();
        if (v) return v;
      }
      return '';
    };

    meta.published_date = firstMetaContent(metaDateSelectors) || (dateCandidates.published[0] || '');
    meta.modified_date = firstMetaContent(metaModSelectors) || (dateCandidates.modified[0] || '');

    // JS-render heuristic (best-effort): low extracted text + SPA markers
    const spaMarkers = [
      '__NEXT_DATA__',
      'data-reactroot',
      'id="app"',
      'id="root"',
      'window.__INITIAL_STATE__',
      'webpackJsonp',
      'ng-version',
    ];
    const markerHit = spaMarkers.some(m => html.includes(m));

    // Approx text length without running full extraction again:
    // Take body textContent quickly and measure.
    const bodyTextLen = (doc.body?.textContent || '').replace(/\s+/g, ' ').trim().length;
    meta.js_render_suspected = bodyTextLen < 400 && markerHit;

  } catch {
    // return defaults
  }

  return meta;
}

async function extractContentFromResults(results, options = {}) {
  const { 
    extractContent = true
  } = options;
  
  if (!extractContent) {
    // Keep schema/metadata columns present even when content extraction is disabled
    // so the CSV has a stable schema across runs.
    return results.map(result => ({
      ...result,
      content: '',
      contentError: '',
      contentLength: 0,
      page_title: '',
      meta_description: '',
      canonical_url: '',
      has_schema_markup: false,
      schema_types: '',
      table_count: 0,
      has_table: false,
      published_date: '',
      modified_date: '',
      js_render_suspected: false,
    }));
  }
  
  console.log(`Starting content extraction for ${results.length} URLs`);
  
  const enrichedResults = [];
  
  // process in batches to avoid overwhelming servers
  for (let i = 0; i < results.length; i += MAX_CONCURRENT) {
    const batch = results.slice(i, i + MAX_CONCURRENT);
    console.log(`Processing content batch ${Math.floor(i / MAX_CONCURRENT) + 1}/${Math.ceil(results.length / MAX_CONCURRENT)}`);
    
    // report progress
    reportProgress({
      contentPhase: true,
      contentProgress: i,
      contentTotal: results.length,
      currentUrl: batch[0]?.url
    });
    
    // process batch concurrently
    const batchPromises = batch.map(async (result, batchIndex) => {
      const globalIndex = i + batchIndex;
      
      try {
        console.log(`Fetching content from: ${result.url}`);
        
        const { content, error } = await fetchUrlContent(result.url, CONTENT_TIMEOUT);
        
        let extractedText = '';
        let contentError = error || '';
        
        if (content && !error) {
          extractedText = extractTextFromHtml(content);
          const meta = extractMetadataFromHtml(content);
          console.log(`Extracted ${extractedText.length} characters from ${result.domain}`);

          return {
            ...result,
            ...meta,
            content: extractedText,
            contentError: contentError,
            contentLength: extractedText.length
          };
        } else {
          // console.warn(`Failed to fetch content from ${result.url}: ${error}`);
        }

        return {
          ...result,
          content: extractedText,
          contentError: contentError,
          contentLength: extractedText.length
        };
        
      } catch (error) {
        // console.error(`Error processing ${result.url}:`, error);
        return {
          ...result,
          content: '',
          contentError: error.message,
          contentLength: 0,
          page_title: '',
          meta_description: '',
          canonical_url: '',
          has_schema_markup: false,
          schema_types: '',
          table_count: 0,
          has_table: false,
          published_date: '',
          modified_date: '',
          js_render_suspected: false,
        };
      }
    });
    
    const batchResults = await Promise.all(batchPromises);
    enrichedResults.push(...batchResults);
    
    // add delay between batches (except for the last batch)
    if (i + MAX_CONCURRENT < results.length) {
      console.log(`Waiting ${REQUEST_DELAY}ms before next batch...`);
      await pauseSeconds(REQUEST_DELAY / 1000);
    }
  }
  
  // final progress update
  reportProgress({
    contentPhase: true,
    contentProgress: results.length,
    contentTotal: results.length,
    contentComplete: true
  });
  
  const successfulExtractions = enrichedResults.filter(r => r.content && !r.contentError).length;
  console.log(`Content extraction completed: ${successfulExtractions}/${results.length} successful`);
  
  return enrichedResults;
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

// ================== ATOMIC ACTIONS ==================

async function performSearch(query) {
  console.log(`Performing search for: "${query}"`);
  
  try {
    // Check if we are already on a result page for this query
    const currentInput = document.querySelector(SEARCH_INPUT);
      
    // Normalize for comparison
    const currentVal = currentInput ? currentInput.value.trim() : '';
    const targetVal = query.trim();
    
    if (currentInput && currentVal === targetVal && document.querySelectorAll(SEARCH_RESULTS).length > 0) {
      console.log('Already on results page for this query');
      return { status: 'ready', method: 'existing' };
    }

    // type and click search
    await simulateTyping(SEARCH_INPUT, query, true);
    await pauseSeconds(0.5);
    
    // VERIFY INPUT BEFORE CLICKING
    const inputAfterTyping = document.querySelector(SEARCH_INPUT);
    if (inputAfterTyping.value !== query) {
         console.warn("Input mismatch before search! Retrying typing...");
         inputAfterTyping.value = query;
         inputAfterTyping.dispatchEvent(new Event('input', { bubbles: true }));
         await pauseSeconds(0.5);
      }
      
    await simulateClick(SEARCH_BUTTON);
    
    // We expect the page to reload here. 
    // If it's an SPA, we wait for results.
    // If it reloads, this script dies (and that's okay, sidepanel handles it).
    
    try {
        await waitForResultsToLoad();
        // If we got here, it was an SPA update!
        return { status: 'ready', method: 'spa' };
    } catch (e) {
        // If it reloaded, we probably won't reach here.
        // Or if it timed out.
        return { status: 'unknown' };
      }
      
    } catch (error) {
    throw error;
  }
}

async function scrapeCurrentPage(extractContent = true) {
  console.log('Scraping current page...');
  
  await waitForResultsToLoad();
  
  let results = extractSearchResults();
  
  if (extractContent && results.length > 0) {
    console.log(`Extracting content for ${results.length} results`);
    results = await extractContentFromResults(results, { extractContent });
  }
  
  return results;
}

// ================== COMMUNICATION ==================

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  // ACTION: SEARCH
  if (message.action === "performSearch") {
    performSearch(message.query)
      .then(result => sendResponse(result))
      .catch(err => sendResponse({ status: 'error', error: err.message }));
    return true; // async response
  }
  
  // ACTION: SCRAPE
  if (message.action === "scrapePage") {
    scrapeCurrentPage(message.extractContent)
      .then(results => sendResponse({ status: 'success', results: results }))
      .catch(err => sendResponse({ status: 'error', error: err.message }));
    return true; // async response
  }
});
