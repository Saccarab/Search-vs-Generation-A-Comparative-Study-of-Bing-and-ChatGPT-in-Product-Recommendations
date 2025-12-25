// DOM Elements
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const status = document.getElementById('status');
const fileInfoCard = document.getElementById('fileInfoCard');
const fileName = document.getElementById('fileName');
const queryCount = document.getElementById('queryCount');
const fileSize = document.getElementById('fileSize');
const configSection = document.getElementById('configSection');
const actionSection = document.getElementById('actionSection');
const progressSection = document.getElementById('progressSection');
const resultsSection = document.getElementById('resultsSection');
const startButton = document.getElementById('startButton');
const maxResultsInput = document.getElementById('maxResults');
const totalResultsDisplay = document.getElementById('totalResults');

// content extraction elements
const extractContentCheckbox = document.getElementById('extractContent');
const estimatedDuration = document.getElementById('estimatedDuration');

// progress elements
const progressStatus = document.getElementById('progressStatus');
const progressFill = document.getElementById('progressFill');
const progressPercent = document.getElementById('progressPercent');
const progressCount = document.getElementById('progressCount');
const currentQuery = document.getElementById('currentQuery');
const taskLabel = document.getElementById('taskLabel');
const completedCount = document.getElementById('completedCount');
const estimatedTime = document.getElementById('estimatedTime');
const errorCountDisplay = document.getElementById('errorCount');
const recentErrors = document.getElementById('recentErrors');
const errorList = document.getElementById('errorList');

// phase progress elements
const phaseProgress = document.getElementById('phaseProgress');
const phaseLabel = document.getElementById('phaseLabel');
const phaseStatus = document.getElementById('phaseStatus');
const phaseFill = document.getElementById('phaseFill');

// results elements
const resultsSummary = document.getElementById('resultsSummary');
const searchResultsCount = document.getElementById('searchResultsCount');
const contentExtractedCount = document.getElementById('contentExtractedCount');
const downloadFilename = document.getElementById('downloadFilename');
const downloadSize = document.getElementById('downloadSize');
const downloadButton = document.getElementById('downloadButton');
const newScrapingButton = document.getElementById('newScrapingButton');

// values for timeout and delay
const REQUEST_DELAY = 5000; // 5 seconds between searches

// state
let uploadedQueries = [];
let scrapingState = {
    isRunning: false,
    startTime: null,
    totalQueries: 0,
    completed: 0,
    errors: 0,
    errorList: [],
    currentQueryIndex: -1,
    maxResultsPerQuery: 10,
    extractContent: false,
    collectedResults: [], // Store all results here
    currentPhase: 'search', // 'search', 'content', 'complete'
    contentProgress: 0,
    contentTotal: 0,
    waitingForPageLoad: false
};

// initialize
document.addEventListener('DOMContentLoaded', initializeApp);

function initializeApp() {
    setupEventListeners();
    updateConfiguration();
    showSection('upload');
}

function setupEventListeners() {
    // file upload events
    dropZone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', (e) => handleFile(e.target.files[0]));
    
    // drag and drop events
    dropZone.addEventListener('dragover', handleDragOver);
    dropZone.addEventListener('dragleave', handleDragLeave);
    dropZone.addEventListener('drop', handleDrop);
    
    // configuration events
    maxResultsInput.addEventListener('input', updateConfiguration);
    extractContentCheckbox.addEventListener('change', updateConfiguration);
    
    // control events
    startButton.addEventListener('click', startScraping);
    downloadButton.addEventListener('click', downloadResults);
    newScrapingButton.addEventListener('click', resetApp);
    
    // footer events
    document.getElementById('helpLink').addEventListener('click', showHelp);
}

// file handling (unchanged)
function handleDragOver(e) { e.preventDefault(); dropZone.classList.add('dragover'); }
function handleDragLeave() { dropZone.classList.remove('dragover'); }
function handleDrop(e) {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    handleFile(e.dataTransfer.files[0]);
}

function handleFile(file) {
    if (!file) return;
    resetUploadState();
    if (!file.name.toLowerCase().endsWith('.csv')) {
        showStatus('Please upload a CSV file', 'error');
        return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
        try { parseCSV(e.target.result, file); } catch (error) { showStatus('Error reading file: ' + error.message, 'error'); }
    };
    reader.readAsText(file);
}

function parseCSV(csvText, file) {
    const lines = csvText.trim().split('\n');
    if (lines.length < 2) { showStatus('CSV must have header and at least one data row', 'error'); return; }
    
    const headers = lines[0].split(',').map(h => h.trim().toLowerCase().replace(/['"]/g, ''));
    if (!headers.includes('query')) { showStatus('CSV must have a "query" column', 'error'); return; }
    
    const queryIndex = headers.indexOf('query');
    uploadedQueries = [];
    
    for (let i = 1; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) continue;
        const values = parseCSVLine(line);
        const query = values[queryIndex]?.trim().replace(/['"]/g, '');
        if (query) uploadedQueries.push(query);
    }
    
    if (uploadedQueries.length === 0) { showStatus('No valid queries found in the CSV file', 'error'); return; }
    
    dropZone.classList.add('uploaded');
    showFileInfo(file);
    updateConfiguration();
    showSection('config');
    showSection('action');
    showStatus('File uploaded successfully!', 'success');
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

function showFileInfo(file) {
    fileName.textContent = file.name;
    queryCount.textContent = uploadedQueries.length;
    fileSize.textContent = formatFileSize(file.size);
    fileInfoCard.style.display = 'block';
    fileInfoCard.classList.add('fade-in');
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return Math.round(bytes / 1024) + ' KB';
    return Math.round(bytes / (1024 * 1024)) + ' MB';
}

function updateConfiguration() {
    const maxResults = parseInt(maxResultsInput.value) || 10;
    const extractContent = extractContentCheckbox.checked;
    const total = uploadedQueries.length * maxResults;
    totalResultsDisplay.textContent = total;
    
    let estimatedMinutes = 0;
    if (uploadedQueries.length > 0) {
        estimatedMinutes = uploadedQueries.length * 0.6;
        if (extractContent) {
            const avgSuccessfulResults = Math.ceil(total * 0.8);
            const contentExtractionMinutes = (avgSuccessfulResults * 2.5) / 60;
            estimatedMinutes += contentExtractionMinutes;
        }
    }
    
    if (estimatedMinutes > 0) {
        if (estimatedMinutes < 60) estimatedDuration.textContent = `~${Math.ceil(estimatedMinutes)} minutes`;
        else {
            const hours = Math.floor(estimatedMinutes / 60);
            const mins = Math.ceil(estimatedMinutes % 60);
            estimatedDuration.textContent = mins === 0 ? `~${hours}h` : `~${hours}h ${mins}m`;
        }
    } else estimatedDuration.textContent = 'Upload queries to calculate';
}

function showStatus(message, type) {
    status.textContent = message;
    status.className = `status-message ${type}`;
    status.style.display = 'flex';
    status.classList.add('fade-in');
    if (type === 'success') setTimeout(() => { status.style.display = 'none'; }, 3000);
}

function showSection(section) {
    const sections = { 'config': configSection, 'action': actionSection, 'progress': progressSection, 'results': resultsSection };
    if (sections[section]) { sections[section].style.display = 'block'; sections[section].classList.add('fade-in'); }
}

function hideSection(section) {
    const sections = { 'config': configSection, 'action': actionSection, 'progress': progressSection, 'results': resultsSection };
    if (sections[section]) sections[section].style.display = 'none';
}

// ================== CORE LOGIC ==================

function startScraping() {
    if (uploadedQueries.length === 0) { showStatus('Please upload a CSV file first', 'warning'); return; }
    
    // Initialize State
    scrapingState = {
        isRunning: true,
        startTime: Date.now(),
        totalQueries: uploadedQueries.length,
        completed: 0,
        errors: 0,
        errorList: [],
        currentQueryIndex: -1, // Will start at 0
        currentPageOffset: 0, // Track pagination (0, 10, 20...)
        resultsForCurrentQuery: 0, // Track count for current query
        maxResultsPerQuery: parseInt(maxResultsInput.value) || 10,
        extractContent: extractContentCheckbox.checked,
        collectedResults: [],
        currentPhase: 'search',
        contentProgress: 0,
        contentTotal: 0,
        waitingForPageLoad: false
    };
    
    // UI Updates
    startButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>Running...</span>';
    startButton.disabled = true;
    hideSection('config');
    hideSection('action');
    showSection('progress');
    
    // Start Loop
    processNextQuery();
}

function processNextQuery() {
    if (!scrapingState.isRunning) return;

    // Only move to next query if we are done with the current one (or starting fresh)
    if (scrapingState.currentPageOffset === 0) {
        scrapingState.currentQueryIndex++;
        scrapingState.resultsForCurrentQuery = 0;
    }
    
    // CHECK COMPLETION
    if (scrapingState.currentQueryIndex >= scrapingState.totalQueries) {
        finishScraping();
        return;
    }

    // UPDATE UI
    scrapingState.currentPhase = 'search';
    updateProgressDisplay();

    const query = uploadedQueries[scrapingState.currentQueryIndex];
    const encodedQuery = encodeURIComponent(query);
    
    // Add pagination parameter if offset > 0
    let searchUrl = `https://www.bing.com/search?q=${encodedQuery}`;
    if (scrapingState.currentPageOffset > 0) {
        searchUrl += `&first=${scrapingState.currentPageOffset + 1}`;
    }

    // NAVIGATE
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs[0]) {
            console.log(`Navigating to: ${searchUrl} (Offset: ${scrapingState.currentPageOffset})`);
            scrapingState.waitingForPageLoad = true;
            chrome.tabs.update(tabs[0].id, { url: searchUrl });
            // Now we wait for 'bingPageLoaded' message from background.js
        } else {
            handleQueryError("No active tab found");
            scrapingState.waitingForPageLoad = false;
            scheduleNext();
        }
    });
}

function triggerScrape(tabId) {
    if (!scrapingState.isRunning) return;
    
    console.log("Triggering scrape on tab", tabId);
    scrapingState.currentPhase = 'content';
    updateProgressDisplay();

    // Send Scrape Command
    chrome.tabs.sendMessage(tabId, { 
        action: 'scrapePage', 
        extractContent: scrapingState.extractContent 
    }, (response) => {
        if (chrome.runtime.lastError) {
            handleQueryError(`Connection error: ${chrome.runtime.lastError.message}`);
            // If error, force move to next query to avoid loop
            scrapingState.currentPageOffset = 0;
            scheduleNext();
        } else if (response && response.status === 'success') {
            saveQueryResults(response.results);
            
            // PAGINATION LOGIC:
            // If we found results AND we haven't hit the limit yet, try next page
            if (response.results.length > 0 && scrapingState.resultsForCurrentQuery < scrapingState.maxResultsPerQuery) {
                console.log(`Pagination: Collected ${scrapingState.resultsForCurrentQuery} so far. Target: ${scrapingState.maxResultsPerQuery}. Moving to next page.`);
                scrapingState.currentPageOffset += 10; // Bing steps by 10
                scheduleNext();
            } else {
                // Done with this query
                console.log(`Pagination: Done with query. Collected ${scrapingState.resultsForCurrentQuery} results.`);
                scrapingState.currentPageOffset = 0;
                scrapingState.completed++; // Only increment completed when query is FULLY done
                scheduleNext();
            }
        } else {
            handleQueryError(response ? response.error : "Unknown error");
            scrapingState.currentPageOffset = 0; // Skip to next query on error
            scheduleNext();
        }
    });
}

function saveQueryResults(results) {
    const query = uploadedQueries[scrapingState.currentQueryIndex];
    // Add query metadata to each result and FIX POSITION STRICTLY
    const enrichedResults = results.map((r, index) => ({
        query: query,
        ...r,
        // STRICT SEQUENTIAL POSITION
        // Ignore r.position and Bing offset. Just count what we have collected.
        position: scrapingState.resultsForCurrentQuery + index + 1
    }));
    scrapingState.collectedResults.push(...enrichedResults);
    scrapingState.resultsForCurrentQuery += results.length;
    // Don't increment scrapingState.completed here anymore, done in pagination logic
    updateProgressDisplay();
}

function handleQueryError(errorMsg) {
    scrapingState.errors++;
    scrapingState.errorList.push({
        queryIndex: scrapingState.currentQueryIndex + 1,
        message: errorMsg
    });
    // Add a placeholder result to keep CSV structure? Optional.
    // scrapingState.collectedResults.push({ query: uploadedQueries[scrapingState.currentQueryIndex], error: errorMsg });
    updateProgressDisplay();
}

function scheduleNext() {
    if (!scrapingState.isRunning) return;
    
    let delay = REQUEST_DELAY;
    // Add random jitter
    delay += Math.floor(Math.random() * 2000); 

    console.log(`Waiting ${delay}ms before next query...`);
    setTimeout(() => {
        processNextQuery();
    }, delay);
}

function finishScraping() {
    scrapingState.isRunning = false;
    scrapingState.currentPhase = 'complete';
    
    // Generate CSV
    const csvContent = generateCSV(scrapingState.collectedResults);
    showResults(csvContent, scrapingState.totalQueries);
}

function generateCSV(results) {
    if (!results || results.length === 0) return "query,error\nNo results found,";
    
    // Dynamic headers based on all keys found
    const allKeys = new Set();
    results.forEach(r => Object.keys(r).forEach(k => allKeys.add(k)));
    const headers = Array.from(allKeys).sort();
    
    // Ensure 'query' and 'position' are first
    const orderedHeaders = ['query', 'position', ...headers.filter(h => h!=='query' && h!=='position')];
    
    let csv = orderedHeaders.join(',') + '\n';
    
    results.forEach(row => {
        const line = orderedHeaders.map(header => {
            let val = row[header] || '';
            // Escape CSV injection and special chars
            val = String(val).replace(/"/g, '""'); 
            // Replace newlines in content with space to keep CSV clean
            val = val.replace(/[\r\n]+/g, ' '); 
            return `"${val}"`;
        });
        csv += line.join(',') + '\n';
    });
    
    return csv;
}


// ================== LISTENERS ==================

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    // 1. Page Load Event (from Background)
    if (message.action === 'bingPageLoaded') {
        if (scrapingState.isRunning && scrapingState.waitingForPageLoad) {
            console.log("Page loaded detected. Resuming...");
            scrapingState.waitingForPageLoad = false;
            // Add small delay to ensure DOM is truly ready/stable
            setTimeout(() => triggerScrape(message.tabId), 1500); 
        }
    }

    // 2. Progress Updates (from Content Script during Extraction)
    if (message.action === 'progressUpdate') {
        if (message.contentPhase) {
            scrapingState.currentPhase = 'content';
            if (message.contentProgress !== undefined) scrapingState.contentProgress = message.contentProgress;
            if (message.contentTotal !== undefined) scrapingState.contentTotal = message.contentTotal;
            if (message.currentUrl) currentQuery.textContent = new URL(message.currentUrl).hostname;
            updateProgressDisplay();
        }
    }
});


// ================== UI HELPERS (Unchanged mostly) ==================

function updateProgressDisplay() {
    const { completed, totalQueries, currentQueryIndex, currentPhase } = scrapingState;
    const progress = Math.round((completed / totalQueries) * 100);
    progressFill.style.width = progress + '%';
    progressPercent.textContent = progress + '%';
    progressCount.textContent = `${completed} / ${totalQueries}`;
    
    if (currentQueryIndex >= 0 && currentQueryIndex < uploadedQueries.length) {
        const query = uploadedQueries[currentQueryIndex];
        currentQuery.textContent = query.length > 50 ? query.substring(0, 50) + '...' : query;
        
        if (currentPhase === 'search') {
            taskLabel.textContent = 'Searching...';
            progressStatus.textContent = `Processing query ${currentQueryIndex + 1} of ${totalQueries}`;
            phaseProgress.style.display = 'none';
        } else if (currentPhase === 'content') {
            taskLabel.textContent = 'Extracting content...';
            phaseProgress.style.display = 'block';
            phaseLabel.textContent = 'Page Content';
            phaseStatus.textContent = `${scrapingState.contentProgress} / ${scrapingState.contentTotal}`;
            const pp = Math.round((scrapingState.contentProgress / Math.max(1, scrapingState.contentTotal)) * 100);
            phaseFill.style.width = pp + '%';
        }
    }
    
    completedCount.textContent = completed;
    errorCountDisplay.textContent = scrapingState.errors;
    
    if (completed > 0 && scrapingState.startTime) {
        const elapsed = Date.now() - scrapingState.startTime;
        const avgTime = elapsed / completed;
        const remaining = totalQueries - completed;
        const estMins = Math.round((remaining * avgTime) / 60000);
        estimatedTime.textContent = estMins > 0 ? `~${estMins} min` : 'Almost done';
    }
}

function updateErrorList() {
    errorList.innerHTML = '';
    const recent = scrapingState.errorList.slice(-3);
    recent.forEach(e => {
        const div = document.createElement('div');
        div.className = 'error-item';
        div.textContent = `Q${e.queryIndex}: ${e.message}`;
        errorList.appendChild(div);
    });
}

function showResults(csvData, totalQueries) {
    scrapingState.csvData = csvData;
    hideSection('progress');
    showSection('results');
    
    const lines = csvData.split('\n').filter(l => l.trim());
    const totalResults = Math.max(0, lines.length - 1);
    
    resultsSummary.textContent = `Complete! Processed ${totalQueries} queries.`;
    searchResultsCount.textContent = totalResults;
    contentExtractedCount.textContent = scrapingState.extractContent ? "Yes" : "No";
    
    const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
    const filename = `bing_results_${timestamp}.csv`;
    downloadFilename.textContent = filename;
    downloadSize.textContent = `${Math.round(csvData.length / 1024)} KB`;
    
    downloadCSV(csvData, filename);
}

function downloadResults() {
    if (scrapingState.csvData) {
        const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
        downloadCSV(scrapingState.csvData, `bing_results_${timestamp}.csv`);
    }
}

function downloadCSV(csvContent, filename) {
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', filename);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

function resetApp() {
    uploadedQueries = [];
    scrapingState = { isRunning: false };
    resetUploadState();
    hideSection('config');
    hideSection('action');
    hideSection('progress');
    hideSection('results');
    startButton.innerHTML = '<i class="fas fa-play"></i><span>Start Scraping</span>';
    startButton.disabled = false;
    maxResultsInput.value = 10;
    extractContentCheckbox.checked = false;
    updateConfiguration();
    showSection('upload');
}

function resetUploadState() {
    dropZone.classList.remove('uploaded', 'dragover');
    status.style.display = 'none';
    fileInfoCard.style.display = 'none';
}

function showHelp() {
    alert("Bing Scraper v2.1\n\n1. Upload CSV with 'query' column.\n2. Click Start.\n3. The tool will navigate Bing automatically.\n4. Do not close the side panel while running.\n\nNote: 'Extract Content' visits each result page, which takes longer.");
}

// export
window.getUploadedQueries = () => uploadedQueries;
window.getScrapingState = () => scrapingState;
