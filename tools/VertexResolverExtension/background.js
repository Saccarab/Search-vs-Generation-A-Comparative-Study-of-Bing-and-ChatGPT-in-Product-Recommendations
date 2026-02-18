chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'RESOLVE_URL') {
    resolveUrl(message.url).then(resolvedUrl => {
      sendResponse({ resolvedUrl });
    });
    return true; // Keep channel open for async
  }
});

async function resolveUrl(url) {
  return new Promise((resolve) => {
    chrome.tabs.create({ url, active: false }, (tab) => {
      const tabId = tab.id;
      
      let checkCount = 0;
      const maxChecks = 20; // 10 seconds (20 * 500ms)
      const interval = setInterval(() => {
        chrome.tabs.get(tabId, (currentTab) => {
          if (chrome.runtime.lastError || !currentTab) {
            clearInterval(interval);
            resolve(url);
            return;
          }

          const currentUrl = currentTab.url || "";
          const isStillRedirect = currentUrl.includes('vertexaisearch.cloud.google.com/grounding-api-redirect');
          const isBlank = currentUrl === 'about:blank' || currentUrl === '';
          const isComplete = currentTab.status === 'complete';

          // SUCCESS CONDITION: 
          // 1. URL has changed away from the Vertex redirect link
          // 2. It's not blank
          // 3. The page load is complete
          if (!isStillRedirect && !isBlank && isComplete) {
            clearInterval(interval);
            chrome.tabs.remove(tabId);
            resolve(currentUrl);
            return;
          }

          checkCount++;
          if (checkCount >= maxChecks) {
            clearInterval(interval);
            chrome.tabs.remove(tabId);
            // If we timed out but the URL changed, return the change, otherwise original
            resolve(!isStillRedirect && !isBlank ? currentUrl : url);
          }
        });
      }, 500);
    });
  });
}
