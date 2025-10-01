console.log("ChatGPT Response Scraper - Content script loaded");

// selectors
const NEW_CHAT_BTN = 'a[data-testid="create-new-chat-button"]';
const TEMP_CHAT_BTN = 'button[aria-label="Turn on temporary chat"]';
const PLUS_BTN = "#composer-plus-btn";
const SEARCH_WEB_BTN = 'div[role="menuitemradio"]';
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

  // Use pointer events first (works better with modern UI)
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

async function simulateTyping(selector, text, minDelay = 80, maxDelay = 200) {
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
    // Check immediately
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

    // Then dispatch click event
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
    const check = () => {
      const btn = document.querySelector(selector);
      if (btn && btn.getAttribute("data-testid") === "send-button") {
        cleanup();
        resolve(btn);
        return true;
      }
      return false;
    };

    const observer = new MutationObserver(() => check());

    const cleanup = () => {
      observer.disconnect();
      clearTimeout(timer);
    };

    // Observe the body for attribute changes and node replacements
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["data-testid"],
    });

    // Timeout to prevent hanging forever
    const timer = setTimeout(() => {
      cleanup();
      reject(new Error("Timeout waiting for response to finish"));
    }, timeoutMs);

    // Immediate check in case it's already in "finished" state
    check();
  });
}

async function getResponse(selector) {
  const messageElements = document.querySelectorAll(selector);

  if (messageElements.length > 0) {
    const lastResponse = messageElements[messageElements.length - 1];
    const text = lastResponse.textContent || lastResponse.innerText;

    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(text);
      } catch (err) {
        //skip
      }
    }

    return text;
  }

  return null;
}

async function extractSourceLinks() {
  const citations = [];
  const moreLinks = [];
  const seenUrls = new Set();

  // Helper function to clean UTM parameters from URLs
  function cleanUrl(url) {
    try {
      const urlObj = new URL(url);
      const params = new URLSearchParams(urlObj.search);
      
      // Remove all UTM and tracking parameters
      const trackingParams = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'fbclid', 'gclid', 'ref', 'source'];
      trackingParams.forEach(param => {
        params.delete(param);
        // Also remove variations
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

  // Helper function to extract links from a section
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
          
          // Extract metadata with more fallback selectors
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
    // Strategy 1: Look for sections by their header structure (most reliable)
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

    // Strategy 2: Search by text content with broader selectors
    if (citations.length === 0 && moreLinks.length === 0) {
      console.log('Fallback: Searching for sections by text content');
      
      const possibleHeaders = document.querySelectorAll('li, h1, h2, h3, h4, h5, .section-header, [class*="header"]');
      
      for (const element of possibleHeaders) {
        const text = element.textContent?.trim().toLowerCase();
        
        if (text === 'citations') {
          console.log('Found Citations section via fallback');
          // Look for the next ul element in various ways
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

    // Strategy 3: Ultimate fallback - collect all external links
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
      
      // If we found some links, assume they're all citations since we can't distinguish
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
  
  // Get headers from first result
  const headers = Object.keys(results[0]);
  
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

// ================== AUTOMATIZATION ==================

async function collectQueryResponse(query, force_web_search = true, retryCount = 0, maxRetries = 3) {
  const attemptLabel = retryCount > 0 ? ` (Retry ${retryCount}/${maxRetries})` : '';
  console.log(`[Query Processing] Starting query: "${query.substring(0, 50)}..."${attemptLabel}`);
  
  await pauseSeconds(getRandomInt(1, 3));

  // open new chat
  await simulateClick(NEW_CHAT_BTN);
  await pauseSeconds(getRandomInt(1, 3));

  // open new temp chat
  await simulateClick(TEMP_CHAT_BTN);
  await pauseSeconds(getRandomInt(1, 3));

  // enable web search -> only if force_web_search is true
  if (force_web_search) {
    await clickWebSearch();
    await pauseSeconds(getRandomInt(1, 3));
  } else {
    console.log('[Step 3/8] Skipping web search (disabled by user)...');
  }

  // type query
  await simulateTyping(TEXT_FIELD, query);
  await pauseSeconds(getRandomInt(1, 3));

  // send query
  await simulateClick(SEND_QUERY_BTN);
  await pauseSeconds(getRandomInt(1, 3));

  // wait for response end
  await waitForResponseFinished(SEND_QUERY_BTN);
  await pauseSeconds(getRandomInt(1, 3));

  // get response text
  const response_text = await getResponse(ASSISTANT_MSG);
  await pauseSeconds(getRandomInt(1, 3));

  // prepare return object
  const result = {
    query: query,
    response_text: response_text,
    web_search_forced: force_web_search,
    retry_count: retryCount
  };

  // ALWAYS try to extract source links (ChatGPT sometimes uses sources automatically)
  try {
    // Check if sources button exists before trying to click it
    const sourcesButton = document.querySelector(OPEN_SOURCES_BTN);
    if (sourcesButton) {
      console.log('Sources button found - extracting sources');
      await simulateClick(OPEN_SOURCES_BTN);
      await pauseSeconds(getRandomInt(3, 5));
      
      const sourceLinks = await extractSourceLinks();
      
      // Try to close the sources panel
      const closeButton = document.querySelector(CLOSE_SOURCES_BTN);
      if (closeButton) {
        await simulateClick(CLOSE_SOURCES_BTN);
        await pauseSeconds(getRandomInt(1, 3));
      }
      
      // add source data to result
      result.sources_cited = sourceLinks.citations || [];
      result.sources_additional = sourceLinks.additional || [];
      
      console.log(`Found ${result.sources_cited.length} citations and ${result.sources_additional.length} additional sources`);
    } else {
      console.log(`No sources button found - ChatGPT did not use web search for this query${force_web_search ? ' (despite being forced)' : ''}`);
      result.sources_cited = [];
      result.sources_additional = [];
      
      // FAILSAFE: If web search was forced but no sources found, retry
      if (force_web_search && retryCount < maxRetries) {
        // console.warn(`[Failsafe] Web search was forced but no sources found. Retrying... (${retryCount + 1}/${maxRetries})`);
        
        // Report retry attempt to sidepanel
        reportProgress({
          retryAttempt: true,
          retryCount: retryCount + 1,
          maxRetries: maxRetries
        });
        
        // Add a small delay before retry
        await pauseSeconds(getRandomInt(2, 4));
        
        // Recursive retry
        return await collectQueryResponse(query, force_web_search, retryCount + 1, maxRetries);
      } else if (force_web_search && retryCount >= maxRetries) {
        console.error(`[Failsafe] Max retries (${maxRetries}) reached. Proceeding without sources.`);
        result.no_sources_warning = true;
      }
    }
  } catch (error) {
    // console.warn('Error extracting sources:', error.message);
    // Set empty arrays if source extraction fails
    result.sources_cited = [];
    result.sources_additional = [];
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
    const query = queries[i];
    
    for (let run = 1; run <= runs_per_q; run++) {
      try {
        console.log(`[Progress] Query ${i + 1}/${queries.length}, Run ${run}/${runs_per_q}`);
        
        // Report progress to sidepanel
        reportProgress({
          queryIndex: i,
          run: run,
          completed: completedOperations,
          totalOperations: totalOperations
        });
        
        const result = await collectQueryResponse(query, force_web_search);
        
        // Helper function to safely convert source data to string
        const formatSources = (sources) => {
          if (!sources) return '';
          if (Array.isArray(sources)) {
            if (sources.length === 0) return '';
            return sources.map(source => {
              if (typeof source === 'string') return source;
              if (typeof source === 'object' && source.url) return source.url;
              if (typeof source === 'object' && source.link) return source.link;
              return JSON.stringify(source);
            }).join('; ');
          }
          if (typeof sources === 'string') return sources;
          return JSON.stringify(sources);
        };
        
        // Add run number and index to result
        const enrichedResult = {
          query_index: i + 1,
          run_number: run,
          query: result.query,
          response_text: result.response_text,
          web_search_forced: result.web_search_forced,
          sources_cited: formatSources(result.sources_cited),
          sources_additional: formatSources(result.sources_additional),
        };
        
        results.push(enrichedResult);
        completedOperations++;
        
        // Report completion of this operation
        reportProgress({
          completed: completedOperations,
          totalOperations: totalOperations
        });
        
        console.log(`[Success] Completed operation ${completedOperations}/${totalOperations}`);
        
        // Add delay between queries to avoid rate limiting
        if (!(i === queries.length - 1 && run === runs_per_q)) {
          const delaySeconds = getRandomInt(2, 5);
          // console.log(`[Delay] Waiting ${delaySeconds} seconds before next query...`);
          await pauseSeconds(delaySeconds);
        }
        
      } catch (error) {
        console.error(`[Error] Processing query "${query}" (run ${run}):`, error);
        
        // Report error to sidepanel
        reportError(i + 1, error.message);
        
        // Add error result
        const errorResult = {
          query_index: i + 1,
          run_number: run,
          query: query,
          response_text: `ERROR: ${error.message}`,
          web_search_forced: force_web_search,
          sources_cited: '',
          sources_additional: '',
        };
        
        results.push(errorResult);
        completedOperations++;
        
        // Report completion even for errors
        reportProgress({
          completed: completedOperations,
          totalOperations: totalOperations
        });
        
        // Don't stop the entire process for one error, continue with next
        console.log(`[Recovery] Continuing with next query after error...`);
        
        // Still add delay after errors
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
        
        // Send CSV data back to sidepanel
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