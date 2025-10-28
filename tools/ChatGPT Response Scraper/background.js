// console.log('ChatGPT Response Scraper - Background script loaded');

// init sidepanel on extension install/startup
chrome.runtime.onInstalled.addListener(() => {
  console.log('Extension installed - Setting up sidepanel');
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
});

// handle extension startup
chrome.runtime.onStartup.addListener(() => {
  console.log('Extension started - Sidepanel ready');
});

// =============== COMMUNICATION RELAY ===============

// the background script acts as a relay for messages between content script and sidepanel
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log('Background received message:', message.action, 'from:', sender.tab ? 'content script' : 'sidepanel');
  
  // handle messages from content script that need to be forwarded to sidepanel
  if (sender.tab && (
    message.action === 'dataCollectionComplete' ||
    message.action === 'dataCollectionError' ||
    message.action === 'progressUpdate' ||
    message.action === 'queryError'
  )) {
    // these messages from content script should be forwarded to sidepanel
    // the sidepanel is already listening for these messages directly
    console.log('Relaying message to sidepanel:', message.action);
    return false; // Let the message propagate normally
  }
  
  // handle any direct background script actions if needed
  if (message.action === 'backgroundPing') {
    console.log('Background script ping received');
    sendResponse({ status: 'background active' });
    return true;
  }
  
  // log unhandled messages for debugging
  if (message.action) {
    console.log('Unhandled message action:', message.action);
  }
  
  return false;
});

// handle tab updates to ensure content script stays connected
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url && tab.url.includes('chatgpt.com')) {
    console.log('ChatGPT tab updated and ready:', tabId);
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
  chrome.tabs.query({ url: '*://chatgpt.com/*' }, (tabs) => {
    if (tabs.length > 0) {
      console.log(`Health check: ${tabs.length} ChatGPT tab(s) open`);
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

// export for debugging
if (typeof window !== 'undefined') {
  window.backgroundScript = {
    version: '1.0.0',
    status: 'active'
  };
}