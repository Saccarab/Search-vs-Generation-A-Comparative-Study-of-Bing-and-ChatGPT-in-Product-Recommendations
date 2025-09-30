// Bing Search Results Scraper with Content Extraction - Content Script

console.log("Bing Search Scraper with Content Extraction - Content script loaded");

// Hardcoded values for timeout and delay
const CONTENT_TIMEOUT = 15000; // 15 seconds
const REQUEST_DELAY = 5000; // 5 seconds between requests
const MAX_CONCURRENT = 1; // Maximum concurrent content requests

// ================== SELECTORS ==================
const SEARCH_INPUT = '#sb_form_q';
const SEARCH_BUTTON = '#sb_form_go';

// Target only organic results, exclude ads
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

  // Scroll element into view
  element.scrollIntoView({ behavior: 'smooth', block: 'center' });
  await pauseSeconds(0.5);

  // Use pointer events first
  element.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true }));
  element.dispatchEvent(new PointerEvent("pointerup", { bubbles: true }));

  // Then dispatch click event
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
  
  if (clearFirst) {
    // Clear existing text
    element.value = '';
    element.dispatchEvent(new Event('input', { bubbles: true }));
  }

  // Type character by character
  for (const char of text) {
    element.value += char;
    element.dispatchEvent(new Event('input', { bubbles: true }));
    await pauseSeconds(getRandomInt(50, 150) / 1000); // Random typing speed
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
  // Wait for search results to appear and stabilize
  await waitForSelector(SEARCH_RESULTS, 10000);
  await pauseSeconds(getRandomInt(2, 4));
  
  // Wait a bit more to ensure all results are loaded
  let previousCount = 0;
  let stableCount = 0;
  
  for (let i = 0; i < 10; i++) {
    const currentCount = document.querySelectorAll(SEARCH_RESULTS).length;
    if (currentCount === previousCount && currentCount > 0) {
      stableCount++;
      if (stableCount >= 3) break; // Results are stable
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
    // Method 1: Try to parse Bing redirect parameters
    if (originalUrl.includes('bing.com')) {
      const url = new URL(originalUrl);
      
      // Pattern 1: Check 'u' parameter with base64 decoding
      if (url.searchParams.has('u')) {
        let encodedUrl = url.searchParams.get('u');
        
        // Try URL decoding first
        try {
          const urlDecoded = decodeURIComponent(encodedUrl);
          if (urlDecoded.startsWith('http')) {
            console.log(`URL decoded: ${originalUrl.substring(0, 50)}... -> ${urlDecoded}`);
            return cleanUrl(urlDecoded);
          }
        } catch (e) {
          // URL decoding failed, continue to base64
        }
        
        // Try base64 decoding (Bing often uses this)
        try {
          // Remove common prefixes that Bing adds before base64
          if (encodedUrl.startsWith('a1')) {
            encodedUrl = encodedUrl.substring(2);
          } else if (encodedUrl.match(/^[a-zA-Z0-9]{1,4}/)) {
            // Try removing first 1-4 characters if they look like prefixes
            for (let prefixLen = 1; prefixLen <= 4; prefixLen++) {
              try {
                const testUrl = encodedUrl.substring(prefixLen);
                const decoded = atob(testUrl);
                if (decoded.startsWith('http')) {
                  console.log(`Base64 decoded (prefix ${prefixLen}): ${originalUrl.substring(0, 50)}... -> ${decoded}`);
                  return cleanUrl(decoded);
                }
              } catch (e) {
                // Continue trying different prefix lengths
              }
            }
          }
          
          // Try direct base64 decode
          const directDecoded = atob(encodedUrl);
          if (directDecoded.startsWith('http')) {
            console.log(`Base64 decoded: ${originalUrl.substring(0, 50)}... -> ${directDecoded}`);
            return cleanUrl(directDecoded);
          }
        } catch (e) {
          // console.warn('Base64 decoding failed:', e.message);
        }
        
        // Try hex decoding as fallback
        try {
          if (encodedUrl.match(/^[0-9a-f]+$/i)) {
            const hexDecoded = encodedUrl.match(/.{1,2}/g).map(byte => String.fromCharCode(parseInt(byte, 16))).join('');
            if (hexDecoded.includes('http')) {
              console.log(`Hex decoded: ${originalUrl.substring(0, 50)}... -> ${hexDecoded}`);
              return cleanUrl(hexDecoded);
            }
          }
        } catch (e) {
          // Continue to next method
        }
      }
      
      // Pattern 2: Check URL in pathname
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
    
    // If URL doesn't need processing or parsing failed, return cleaned original
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
    
    // Remove tracking parameters
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
  
  // First, let's verify we're only getting organic results
  const allResultElements = document.querySelectorAll('.b_algo');
  const adElements = document.querySelectorAll('.b_ad, .b_adTop, .b_adBottom, [data-apurl]');
  console.log(`Total .b_algo elements: ${allResultElements.length}, Ad elements: ${adElements.length}, Organic: ${resultElements.length}`);
  
  resultElements.forEach((resultElement, index) => {
    try {
      // Double-check this isn't an ad
      if (resultElement.classList.contains('b_ad') || 
          resultElement.classList.contains('b_adTop') || 
          resultElement.classList.contains('b_adBottom') ||
          resultElement.hasAttribute('data-apurl') ||
          resultElement.querySelector('.b_ad')) {
        console.log(`Skipping ad element at position ${index + 1}`);
        return;
      }
      
      // Extract title and URL
      const titleElement = resultElement.querySelector(RESULT_TITLE);
      const title = titleElement?.textContent?.trim() || '';
      
      if (!title || !titleElement) {
        // console.warn(`Skipping result ${index + 1}: No title found`);
        return;
      }
      
      console.log(`Processing organic result ${index + 1}: ${title}`);
      
      // Get the actual URL by parsing redirect
      const actualUrl = getActualUrl(titleElement);
      
      // Extract snippet
      const snippetElement = resultElement.querySelector(RESULT_SNIPPET);
      const snippet = snippetElement?.textContent?.trim() || '';
      
      // Extract displayed URL/domain
      const citeElement = resultElement.querySelector(RESULT_URL);
      const displayUrl = citeElement?.textContent?.trim() || extractDomain(actualUrl);
      
      // Only add if we have title and URL
      if (title && actualUrl) {
        results.push({
          position: index + 1,
          title: title,
          url: actualUrl,
          domain: extractDomain(actualUrl),
          displayUrl: displayUrl,
          snippet: snippet
        });
        
        // console.log(`Extracted organic result ${index + 1}: ${actualUrl}`);
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

    // Send message to background script to fetch content
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
    // Create a temporary element to parse HTML
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = html;
    
    // Remove script and style elements
    const scripts = tempDiv.querySelectorAll('script, style, noscript');
    scripts.forEach(el => el.remove());
    
    // Remove common non-content elements
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
    
    // Get text content
    let text = tempDiv.textContent || tempDiv.innerText || '';
    
    // Clean up the text
    text = text
      .replace(/\s+/g, ' ') // Replace multiple whitespace with single space
      .replace(/\n\s*\n/g, '\n') // Remove empty lines
      .trim();
    
    // Limit text length to prevent huge content
    const maxLength = 10000; // 10KB of text should be reasonable
    if (text.length > maxLength) {
      text = text.substring(0, maxLength) + '...';
    }
    
    return text;
  } catch (error) {
    console.error('Error extracting text from HTML:', error);
    return '';
  }
}

async function extractContentFromResults(results, options = {}) {
  const { 
    extractContent = true
  } = options;
  
  if (!extractContent) {
    return results.map(result => ({ ...result, content: '', contentError: '' }));
  }
  
  console.log(`Starting content extraction for ${results.length} URLs`);
  
  const enrichedResults = [];
  
  // Process in batches to avoid overwhelming servers
  for (let i = 0; i < results.length; i += MAX_CONCURRENT) {
    const batch = results.slice(i, i + MAX_CONCURRENT);
    console.log(`Processing content batch ${Math.floor(i / MAX_CONCURRENT) + 1}/${Math.ceil(results.length / MAX_CONCURRENT)}`);
    
    // Report progress
    reportProgress({
      contentPhase: true,
      contentProgress: i,
      contentTotal: results.length,
      currentUrl: batch[0]?.url
    });
    
    // Process batch concurrently
    const batchPromises = batch.map(async (result, batchIndex) => {
      const globalIndex = i + batchIndex;
      
      try {
        console.log(`Fetching content from: ${result.url}`);
        
        const { content, error } = await fetchUrlContent(result.url, CONTENT_TIMEOUT);
        
        let extractedText = '';
        let contentError = error || '';
        
        if (content && !error) {
          extractedText = extractTextFromHtml(content);
          console.log(`Extracted ${extractedText.length} characters from ${result.domain}`);
        } else {
          console.warn(`Failed to fetch content from ${result.url}: ${error}`);
        }
        
        return {
          ...result,
          content: extractedText,
          contentError: contentError,
          contentLength: extractedText.length
        };
        
      } catch (error) {
        console.error(`Error processing ${result.url}:`, error);
        return {
          ...result,
          content: '',
          contentError: error.message,
          contentLength: 0
        };
      }
    });
    
    const batchResults = await Promise.all(batchPromises);
    enrichedResults.push(...batchResults);
    
    // Add delay between batches (except for the last batch)
    if (i + MAX_CONCURRENT < results.length) {
      console.log(`Waiting ${REQUEST_DELAY}ms before next batch...`);
      await pauseSeconds(REQUEST_DELAY / 1000);
    }
  }
  
  // Final progress update
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

// ================== SEARCH AND PROCESSING ==================

async function searchAndExtractResults(query, maxResults = 50) {
  console.log(`Starting search for query: "${query}" (max ${maxResults} results)`);
  
  // Navigate to Bing homepage if not already there
  if (!window.location.href.includes('bing.com')) {
    window.location.href = 'https://www.bing.com';
    await pauseSeconds(3);
  }
  
  let allResults = [];
  let pageNumber = 1;
  let attempts = 0;
  const maxAttempts = 3;
  
  try {
    // Perform initial search
    await simulateTyping(SEARCH_INPUT, query, true);
    await pauseSeconds(getRandomInt(1, 2));
    await simulateClick(SEARCH_BUTTON);
    await waitForResultsToLoad();
    
    // Extract results from first page
    let pageResults = extractSearchResults();
    console.log(`Page ${pageNumber}: Found ${pageResults.length} results`);
    
    // Add page number to results
    pageResults = pageResults.map(result => ({
      ...result,
      page: pageNumber,
      position: allResults.length + result.position
    }));
    
    allResults.push(...pageResults);
    
    // Continue to next pages if we need more results
    while (allResults.length < maxResults && pageNumber < 10) { // Limit to 10 pages max
      const nextButton = document.querySelector(NEXT_PAGE_BUTTON);
      
      if (!nextButton) {
        console.log('No more pages available');
        break;
      }
      
      try {
        // Click next page
        await simulateClick(NEXT_PAGE_BUTTON);
        await waitForResultsToLoad();
        
        pageNumber++;
        pageResults = extractSearchResults();
        console.log(`Page ${pageNumber}: Found ${pageResults.length} results`);
        
        if (pageResults.length === 0) {
          console.log('No results found on this page, stopping pagination');
          break;
        }
        
        // Add page number and update positions
        pageResults = pageResults.map(result => ({
          ...result,
          page: pageNumber,
          position: allResults.length + result.position
        }));
        
        allResults.push(...pageResults);
        
        // Add delay between pages
        await pauseSeconds(getRandomInt(2, 4));
        attempts = 0; // Reset attempts counter on successful page
        
      } catch (error) {
        attempts++;
        // console.warn(`Error on page ${pageNumber}, attempt ${attempts}:`, error);
        
        if (attempts >= maxAttempts) {
          // console.log(`Max attempts reached for page ${pageNumber}, stopping pagination`);
          break;
        }
        
        // Wait a bit longer before retrying
        await pauseSeconds(getRandomInt(3, 5));
      }
    }
    
    // Trim to max results if needed
    if (allResults.length > maxResults) {
      allResults = allResults.slice(0, maxResults);
    }
    
    // console.log(`Search completed: ${allResults.length} total results collected`);
    return allResults;
    
  } catch (error) {
    // console.error(`Error during search for "${query}":`, error);
    throw error;
  }
}

function convertToCSV(results) {
  if (results.length === 0) return '';
  
  // CSV headers - now including content fields
  const headers = [
    'query', 'position', 'page', 'title', 'url', 'domain', 'displayUrl', 'snippet',
    'content', 'contentLength', 'contentError'
  ];
  
  // Create CSV content
  let csvContent = headers.join(',') + '\n';
  
  results.forEach(result => {
    const row = headers.map(header => {
      const value = result[header] || '';
      // Escape quotes and wrap in quotes if contains comma, quote, or newline
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

// ================== MAIN PROCESSING ==================

async function processQueries(queries, maxResultsPerQuery = 50, extractContent = true) {
  const allResults = [];
  const totalQueries = queries.length;
  let completedQueries = 0;
  
  console.log(`Starting to process ${totalQueries} queries (${maxResultsPerQuery} results each, content extraction: ${extractContent})`);
  
  for (let i = 0; i < queries.length; i++) {
    const query = queries[i];
    
    try {
      console.log(`Processing query ${i + 1}/${totalQueries}: "${query}"`);
      
      // Report progress
      reportProgress({
        queryIndex: i,
        completed: completedQueries,
        totalQueries: totalQueries,
        currentQuery: query,
        phase: 'search'
      });
      
      const results = await searchAndExtractResults(query, maxResultsPerQuery);
      
      // Add query to each result
      let enrichedResults = results.map(result => ({
        query: query,
        queryIndex: i + 1,
        ...result
      }));
      
      // Extract content if enabled
      if (extractContent && results.length > 0) {
        console.log(`Extracting content for ${results.length} URLs from query "${query}"`);
        
        reportProgress({
          queryIndex: i,
          completed: completedQueries,
          totalQueries: totalQueries,
          currentQuery: query,
          phase: 'content',
          contentPhase: true,
          contentProgress: 0,
          contentTotal: results.length
        });
        
        enrichedResults = await extractContentFromResults(enrichedResults, {
          extractContent: true
        });
      } else {
        // Add empty content fields if content extraction is disabled
        enrichedResults = enrichedResults.map(result => ({
          ...result,
          content: '',
          contentLength: 0,
          contentError: extractContent ? '' : 'Content extraction disabled'
        }));
      }
      
      allResults.push(...enrichedResults);
      completedQueries++;
      
      // Report completion of this query
      reportProgress({
        completed: completedQueries,
        totalQueries: totalQueries,
        phase: 'complete'
      });
      
      console.log(`Completed query ${i + 1}/${totalQueries} with ${results.length} results`);
      
      // Add delay between queries to be respectful
      if (i < queries.length - 1) {
        const delaySeconds = getRandomInt(5, 10);
        console.log(`Waiting ${delaySeconds} seconds before next query...`);
        await pauseSeconds(delaySeconds);
      }
      
    } catch (error) {
      console.error(`Error processing query "${query}":`, error);
      
      reportError(i + 1, error.message);
      
      // Add error result
      const errorResult = {
        query: query,
        queryIndex: i + 1,
        position: 0,
        page: 0,
        title: `ERROR: ${error.message}`,
        url: '',
        domain: '',
        displayUrl: '',
        snippet: '',
        content: '',
        contentLength: 0,
        contentError: error.message
      };
      
      allResults.push(errorResult);
      completedQueries++;
      
      // Continue with next query
      console.log('Continuing with next query after error...');
      
      // Add delay even after errors
      if (i < queries.length - 1) {
        await pauseSeconds(getRandomInt(3, 6));
      }
    }
  }
  
  console.log(`Processing completed: ${allResults.length} total results collected`);
  return convertToCSV(allResults);
}

// ================== COMMUNICATION ==================

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "startScraping") {
    (async () => {
      try {
        const queries = message.queries || [];
        const maxResults = message.maxResultsPerQuery || 50;
        const extractContent = message.extractContent !== false; // Default to true
        
        console.log(`Starting scraping for ${queries.length} queries, max ${maxResults} results each, content extraction: ${extractContent}`);
        
        const csvData = await processQueries(queries, maxResults, extractContent);
        
        // Send CSV data back to sidepanel
        chrome.runtime.sendMessage({
          action: 'scrapingComplete',
          csvData: csvData,
          totalQueries: queries.length
        });
        
        console.log('Scraping completed successfully');
        sendResponse("finished!");
      } catch (err) {
        console.error('Scraping error:', err);
        chrome.runtime.sendMessage({
          action: 'scrapingError',
          error: err.message
        });
        sendResponse("error");
      }
    })();

    return true;
  }
});