// sidepanel.js
let huntState = {
  active: false,
  targets: [],
  found: [], // {query, url, rank}
  currentRank: 1,
  maxRank: 200,
  query: "",
  currentQueryIndex: -1,
  totalQueries: 0,
  isRunning: false,
  collectedResults: []
};

// DOM Elements
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const status = document.getElementById('status');
const fileInfoCard = document.getElementById('fileInfoCard');
const fileName = document.getElementById('fileName');
const queryCount = document.getElementById('queryCount');
const configSection = document.getElementById('configSection');
const actionSection = document.getElementById('actionSection');
const progressSection = document.getElementById('progressSection');
const resultsSection = document.getElementById('resultsSection');
const startButton = document.getElementById('startButton');
const maxResultsInput = document.getElementById('maxResults');
const targetUrlsInput = document.getElementById('target-urls');

// progress elements
const progressStatus = document.getElementById('progressStatus');
const progressFill = document.getElementById('progressFill');
const progressPercent = document.getElementById('progressPercent');
const progressCount = document.getElementById('progressCount');
const currentQuery = document.getElementById('currentQuery');
const taskLabel = document.getElementById('taskLabel');

let uploadedQueries = [];

// initialize
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    showSection('upload');
});

function setupEventListeners() {
    dropZone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', (e) => handleFile(e.target.files[0]));
    startButton.addEventListener('click', startScraping);
    document.getElementById('downloadButton').addEventListener('click', downloadResults);
    document.getElementById('newScrapingButton').addEventListener('click', resetApp);
}

function handleFile(file) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
        try { parseCSV(e.target.result, file); } catch (error) { showStatus('Error reading file: ' + error.message, 'error'); }
    };
    reader.readAsText(file);
}

function parseCSV(csvText, file) {
    const lines = csvText.trim().split('\n');
    const headers = lines[0].split(',').map(h => h.trim().toLowerCase().replace(/['"]/g, ''));
    const queryIndex = headers.indexOf('query');
    const runIdIndex = headers.indexOf('run_id');
    
    uploadedQueries = [];
    for (let i = 1; i < lines.length; i++) {
        const values = parseCSVLine(lines[i]);
        const query = values[queryIndex]?.trim().replace(/['"]/g, '');
        const run_id = values[runIdIndex]?.trim().replace(/['"]/g, '');
        if (query) uploadedQueries.push({ query, run_id });
    }
    
    fileName.textContent = file.name;
    queryCount.textContent = uploadedQueries.length;
    fileInfoCard.style.display = 'block';
    showSection('config');
    showSection('action');
}

function parseCSVLine(line) {
    const result = [];
    let current = '';
    let inQuotes = false;
    for (let i = 0; i < line.length; i++) {
        const char = line[i];
        if (char === '"') inQuotes = !inQuotes;
        else if (char === ',' && !inQuotes) { result.push(current); current = ''; }
        else current += char;
    }
    result.push(current);
    return result;
}

function startScraping() {
    const targetText = targetUrlsInput.value;
    huntState.targets = targetText.split('\n').map(u => u.trim().toLowerCase()).filter(u => u);
    huntState.maxRank = parseInt(maxResultsInput.value) || 200;
    huntState.isRunning = true;
    huntState.currentQueryIndex = -1;
    huntState.totalQueries = uploadedQueries.length;
    huntState.collectedResults = [];
    
    hideSection('config');
    hideSection('action');
    showSection('progress');
    processNextQuery();
}

function processNextQuery() {
    if (!huntState.isRunning) return;
    huntState.currentQueryIndex++;
    if (huntState.currentQueryIndex >= huntState.totalQueries) {
        finishScraping();
        return;
    }
    
    huntState.currentRank = 1;
    const qObj = uploadedQueries[huntState.currentQueryIndex];
    huntState.query = qObj.query;
    updateProgressDisplay();
    
    const searchUrl = `https://www.bing.com/search?q=${encodeURIComponent(huntState.query)}`;
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs[0]) {
            chrome.tabs.update(tabs[0].id, { url: searchUrl });
        }
    });
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === 'bingPageLoaded' && huntState.isRunning) {
        setTimeout(() => triggerScrape(message.tabId), 1500);
    }
});

function triggerScrape(tabId) {
    if (!huntState.isRunning) return;
    
    chrome.tabs.sendMessage(tabId, { action: 'scrape', startRank: huntState.currentRank }, (response) => {
        if (response && response.results) {
            saveResults(response.results);
            
            if (huntState.currentRank + 10 <= huntState.maxRank) {
                huntState.currentRank += 10;
                const nextUrl = `https://www.bing.com/search?q=${encodeURIComponent(huntState.query)}&first=${huntState.currentRank}&hunter=true`;
                chrome.tabs.update(tabId, { url: nextUrl });
            } else {
                processNextQuery();
            }
        }
    });
}

function saveResults(results) {
    const qObj = uploadedQueries[huntState.currentQueryIndex];
    results.forEach(r => {
        huntState.collectedResults.push({
            run_id: qObj.run_id,
            query: huntState.query,
            ...r
        });
    });
}

function finishScraping() {
    huntState.isRunning = false;
    showSection('results');
    document.getElementById('searchResultsCount').textContent = huntState.collectedResults.length;
}

function downloadResults() {
    const headers = ["run_id", "query", "position", "url", "page_num"];
    const csv = [headers.join(","), ...huntState.collectedResults.map(r => 
        [r.run_id, `"${r.query}"`, r.position, `"${r.url}"`, r.page_num].join(",")
    )].join("\n");
    
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `bing_deep_hunt_${Date.now()}.csv`;
    a.click();
}

function updateProgressDisplay() {
    const progressFill = document.getElementById('progressFill');
    const progressPercent = document.getElementById('progressPercent');
    const progressCount = document.getElementById('progressCount');
    const currentQuery = document.getElementById('currentQuery');
    if (!progressFill) return;
    const progress = Math.round((huntState.currentQueryIndex / Math.max(1, huntState.totalQueries)) * 100);
    progressFill.style.width = progress + '%';
    if (progressPercent) progressPercent.textContent = progress + '%';
    if (progressCount) progressCount.textContent = `${huntState.currentQueryIndex} / ${huntState.totalQueries}`;
    if (currentQuery) currentQuery.textContent = huntState.query;
}

function showSection(s) { document.getElementById(s + 'Section')?.style.setProperty('display', 'block'); }
function hideSection(s) { document.getElementById(s + 'Section')?.style.setProperty('display', 'none'); }
function resetApp() { location.reload(); }
function showStatus(m, t) { status.textContent = m; status.style.display = 'block'; }
