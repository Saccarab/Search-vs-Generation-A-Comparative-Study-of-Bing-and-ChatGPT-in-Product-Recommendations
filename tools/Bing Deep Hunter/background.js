// console.log('Bing Search Scraper with Content Extraction - Background script loaded');

// timeout & delay
const CONTENT_TIMEOUT = 15000; // 15 seconds
const RATE_LIMIT_MS = 3000; // 3 seconds between requests to same domain

// init sidepanel on extension install/startup
chrome.runtime.onInstalled.addListener(() => {
  console.log('Extension installed - Setting up sidepanel');
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
});

// handle extension startup
chrome.runtime.onStartup.addListener(() => {
  console.log('Extension started - Sidepanel ready');
});

// =============== CONTENT FETCHING ===============

async function fetchUrlContent(url, timeout = CONTENT_TIMEOUT) {
  try {
    console.log(`Background: Fetching content from ${url}`);
    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);
    
    try {
      // fetch with minimal headers to avoid blocks
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
          'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        },
        signal: controller.signal,
        redirect: 'follow',
        mode: 'cors', 
        credentials: 'omit'
      });
      
      clearTimeout(timeoutId);
      
      if (!response.ok) {
        // console.warn(`HTTP ${response.status} for ${url}`);
        return {
          content: '',
          error: `HTTP ${response.status}: ${response.statusText}`
        };
      }
      
      const contentType = response.headers.get('content-type') || '';
      if (!contentType.toLowerCase().includes('text/html') && 
          !contentType.toLowerCase().includes('text/plain') &&
          !contentType.toLowerCase().includes('application/xhtml')) {
        // console.warn(`Non-HTML content type: ${contentType} for ${url}`);
        return {
          content: '',
          error: `Unsupported content type: ${contentType.split(';')[0]}`
        };
      }
      
      const html = await response.text();
      console.log(`Background: Successfully fetched ${html.length} characters from ${url}`);
      
      return {
        content: html,
        error: null
      };
      
    } catch (fetchError) {
      clearTimeout(timeoutId);
      throw fetchError;
    }
    
  } catch (error) {
    // console.warn(`Background: Failed to fetch ${url}:`, error.message);
    
    let errorMessage = error.message;
    if (error.name === 'AbortError') {
      errorMessage = 'Request timeout';
    } else if (error.message.includes('Failed to fetch')) {
      errorMessage = 'Network error or blocked';
    } else if (error.message.includes('NetworkError')) {
      errorMessage = 'Network error';
    } else if (error.message.includes('TypeError')) {
      errorMessage = 'Invalid URL or network error';
    }
    
    return {
      content: '',
      error: errorMessage
    };
  }
}

const urlFetchHistory = new Map();

function canFetchUrl(url) {
  try {
    const domain = new URL(url).hostname;
    const lastFetch = urlFetchHistory.get(domain);
    const now = Date.now();
    
    if (!lastFetch || (now - lastFetch) >= RATE_LIMIT_MS) {
      urlFetchHistory.set(domain, now);
      return true;
    }
    
    const waitTime = RATE_LIMIT_MS - (now - lastFetch);
    console.log(`Rate limit: waiting ${waitTime}ms for ${domain}`);
    return false;
  } catch (error) {
    return true; // allow if URL parsing fails
  }
}

async function fetchWithRateLimit(url, timeout) {
  // check rate limit
  while (!canFetchUrl(url)) {
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  
  return fetchUrlContent(url, timeout);
}

// =============== COMMUNICATION RELAY ===============

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log('Background received message:', message.action, 'from:', sender.tab ? 'content script' : 'sidepanel');
  
  // content fetching requests
  if (message.action === 'fetchContent') {
    console.log(`Background: Content fetch request for ${message.url}`);
    
    (async () => {
      try {
        const result = await fetchWithRateLimit(message.url, message.timeout || CONTENT_TIMEOUT);
        console.log(`Background: Content fetch completed for ${message.url}`, 
                    result.error ? `with error: ${result.error}` : 'successfully');
        sendResponse(result);
      } catch (error) {
        // console.error(`Background: Content fetch error for ${message.url}:`, error);
        sendResponse({
          content: '',
          error: error.message || 'Unknown error'
        });
      }
    })();
    
    return true; // keep message channel open for async response
  }
  
  // content to sidepanel relay
  if (sender.tab && (
    message.action === 'scrapingComplete' ||
    message.action === 'scrapingError' ||
    message.action === 'progressUpdate' ||
    message.action === 'queryError'
  )) {
    console.log('Relaying message to sidepanel:', message.action);
    return false; 
  }
  
  // handle direct background script actions
  if (message.action === 'backgroundPing') {
    console.log('Background script ping received');
    sendResponse({ status: 'background active' });
    return true;
  }
  
  if (message.action) {
    console.log('Unhandled message action:', message.action);
  }
  
  return false;
});

// handle tab updates to ensure content script stays connected
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url && tab.url.includes('bing.com')) {
    console.log('Bing tab updated and ready:', tabId);
    
    // Notify sidepanel that page is ready
    chrome.runtime.sendMessage({
      action: 'bingPageLoaded',
      tabId: tabId,
      url: tab.url
    }).catch(err => {
      // Ignore errors if sidepanel is not open
      // console.log('Could not notify sidepanel (might be closed)');
    });
  }
});

// handle connection errors
chrome.runtime.onConnect.addListener((port) => {
  console.log('Extension connection established:', port.name);
  
  port.onDisconnect.addListener(() => {
    if (chrome.runtime.lastError) {
      console.log('Connection disconnected with error:', chrome.runtime.lastError.message);
    } else {
      console.log('Connection disconnected normally');
    }
  });
});

// monitor extension health
setInterval(() => {
  chrome.tabs.query({ url: '*://www.bing.com/*' }, (tabs) => {
    if (tabs.length > 0) {
      console.log(`Health check: ${tabs.length} Bing tab(s) open`);
    }
  });
}, 60000); // check every minute

// handle extension errors
chrome.runtime.onSuspend.addListener(() => {
  console.log('Extension suspending...');
});

chrome.runtime.onSuspendCanceled.addListener(() => {
  console.log('Extension suspension canceled');
});

setInterval(() => {
  const now = Date.now();
  const cutoff = now - (60 * 60 * 1000); // 1 hour ago
  
  for (const [domain, timestamp] of urlFetchHistory.entries()) {
    if (timestamp < cutoff) {
      urlFetchHistory.delete(domain);
    }
  }
  
  console.log(`Rate limit cleanup: ${urlFetchHistory.size} domains tracked`);
}, 10 * 60 * 1000); // clean every 10 minutes

// export for debugging
if (typeof globalThis !== 'undefined') {
  globalThis.backgroundScript = {
    version: '2.1.0',
    status: 'active',
    features: ['content-extraction', 'rate-limiting', 'cors-bypass'],
    fetchUrlContent: fetchUrlContent,
    stats: () => ({
      trackedDomains: urlFetchHistory.size,
      rateLimitHistory: Array.from(urlFetchHistory.entries())
    })
  };
}

// console.log('Background script ready - content fetching enabled');