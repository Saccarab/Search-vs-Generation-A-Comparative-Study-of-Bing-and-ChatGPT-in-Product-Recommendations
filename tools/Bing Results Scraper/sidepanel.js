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
const contentMaxCharsInput = document.getElementById('contentMaxChars');
const contentLimitsSection = document.getElementById('contentLimitsSection');
// speed controls
const queryDelayMsInput = document.getElementById('queryDelayMs');
const contentDelayMsInput = document.getElementById('contentDelayMs');
const contentConcurrencyInput = document.getElementById('contentConcurrency');

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

// defaults (UI can override)
const DEFAULT_QUERY_DELAY_MS = 1500;

// state
// Each entry is: { query: string, run_id?: string }
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
    contentMaxChars: 20000,
    queryDelayMs: DEFAULT_QUERY_DELAY_MS,
    contentDelayMs: 1000,
    contentConcurrency: 2,
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
    if (contentMaxCharsInput) contentMaxCharsInput.addEventListener('input', updateConfiguration);
    if (queryDelayMsInput) queryDelayMsInput.addEventListener('input', updateConfiguration);
    if (contentDelayMsInput) contentDelayMsInput.addEventListener('input', updateConfiguration);
    if (contentConcurrencyInput) contentConcurrencyInput.addEventListener('input', updateConfiguration);
    
    // control events
    startButton.addEventListener('click', startScraping);
    downloadButton.addEventListener('click', downloadResults);
    newScrapingButton.addEventListener('click', resetApp);

    // Add "Download Checkpoint" button listener
    const checkpointBtn = document.getElementById('checkpointDownloadButton');
    if (checkpointBtn) {
        checkpointBtn.addEventListener('click', downloadCheckpoint);
    }

    // Add "Stop Run" button listener
    const stopBtn = document.getElementById('stopRunButton');
    if (stopBtn) {
        stopBtn.addEventListener('click', stopRun);
    }
    
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
    const hasQuery = headers.includes('query');
    if (!hasQuery) {
        showStatus('CSV must have a "query" column', 'error');
        return;
    }
    
    const queryIndex = headers.indexOf('query');
    const runIdIndex = headers.includes('run_id') ? headers.indexOf('run_id') : -1;
    uploadedQueries = [];
    
    for (let i = 1; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) continue;
        const values = parseCSVLine(line);
        const query = queryIndex >= 0 ? (values[queryIndex]?.trim().replace(/['"]/g, '') || '') : '';
        const run_id = runIdIndex >= 0 ? (values[runIdIndex]?.trim().replace(/['"]/g, '') || '') : '';
        if (query) uploadedQueries.push({ query, run_id });
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
    const contentMaxChars = Math.max(0, parseInt(contentMaxCharsInput?.value || '20000', 10) || 0);
    const queryDelayMs = Math.max(0, Math.min(20000, parseInt(queryDelayMsInput?.value || String(DEFAULT_QUERY_DELAY_MS), 10) || DEFAULT_QUERY_DELAY_MS));
    const contentDelayMs = Math.max(0, Math.min(20000, parseInt(contentDelayMsInput?.value || '1000', 10) || 1000));
    const contentConcurrency = Math.max(1, Math.min(5, parseInt(contentConcurrencyInput?.value || '2', 10) || 2));
    const total = uploadedQueries.length * maxResults;
    totalResultsDisplay.textContent = total;
    
    // Show/hide the content limiter UI when extraction is on/off
    if (contentLimitsSection) {
        contentLimitsSection.style.display = extractContent ? 'grid' : 'none';
    }
    
    let estimatedMinutes = 0;
    if (uploadedQueries.length > 0) {
        // Rough estimate: navigation + wait; use configured delay as a proxy
        estimatedMinutes = (uploadedQueries.length * (0.6 + (queryDelayMs / 1000) * 0.15));
        if (extractContent) {
            const avgSuccessfulResults = Math.ceil(total * 0.8);
            // content delay is the dominant knob; keep estimate conservative
            const perUrlSeconds = 1.5 + (contentDelayMs / 1000) * 0.6;
            const effConcurrency = Math.max(1, contentConcurrency);
            const contentExtractionMinutes = (avgSuccessfulResults * perUrlSeconds) / 60 / effConcurrency;
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
        contentMaxChars: Math.max(0, parseInt(contentMaxCharsInput?.value || '20000', 10) || 0),
        queryDelayMs: Math.max(0, Math.min(20000, parseInt(queryDelayMsInput?.value || String(DEFAULT_QUERY_DELAY_MS), 10) || DEFAULT_QUERY_DELAY_MS)),
        contentDelayMs: Math.max(0, Math.min(20000, parseInt(contentDelayMsInput?.value || '1000', 10) || 1000)),
        contentConcurrency: Math.max(1, Math.min(5, parseInt(contentConcurrencyInput?.value || '2', 10) || 2)),
        collectedResults: [],
        currentPhase: 'search',
        contentProgress: 0,
        contentTotal: 0,
        waitingForPageLoad: false,
        nextPageUrl: null // Store actual next page URL from Bing
    };
    
    // UI Updates
    startButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>Running...</span>';
    startButton.disabled = true;
    
    const checkpointBtn = document.getElementById('checkpointDownloadButton');
    if (checkpointBtn) checkpointBtn.disabled = false;

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
        scrapingState.nextPageUrl = null; // Reset for new query
    }
    
    // CHECK COMPLETION
    if (scrapingState.currentQueryIndex >= scrapingState.totalQueries) {
        finishScraping();
        return;
    }

    // UPDATE UI
    scrapingState.currentPhase = 'search';
    updateProgressDisplay();

    const qObj = uploadedQueries[scrapingState.currentQueryIndex];
    const query = (typeof qObj === 'string') ? qObj : (qObj?.query || '');
    
    // Only navigate for first page; pagination is handled by clicking Next
    const searchUrl = `https://www.bing.com/search?q=${encodeURIComponent(query)}`;
    console.log('Starting fresh search:', searchUrl);

    // NAVIGATE
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs[0]) {
            console.log(`Navigating to: ${searchUrl}`);
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
        extractContent: scrapingState.extractContent,
        contentMaxChars: scrapingState.contentMaxChars,
        contentDelayMs: scrapingState.contentDelayMs,
        contentConcurrency: scrapingState.contentConcurrency
    }, (response) => {
        if (chrome.runtime.lastError) {
            handleQueryError(`Connection error: ${chrome.runtime.lastError.message}`);
            // If error, force move to next query to avoid loop
            scrapingState.currentPageOffset = 0;
            scrapingState.nextPageUrl = null;
            scheduleNext();
        } else if (response && response.status === 'success') {
            saveQueryResults(response.results);
            // Store the next page URL from Bing
            scrapingState.nextPageUrl = response.nextPageUrl || null;
            
            // PAGINATION LOGIC:
            // If we found results AND we haven't hit the limit yet, try clicking next
            if (response.results.length > 0 && scrapingState.resultsForCurrentQuery < scrapingState.maxResultsPerQuery) {
                console.log(`Pagination: Collected ${scrapingState.resultsForCurrentQuery} so far. Target: ${scrapingState.maxResultsPerQuery}. Clicking next page.`);
                // Click the Next button instead of navigating
                chrome.tabs.sendMessage(tabId, { action: 'clickNextPage' }, (clickResponse) => {
                    console.log('Click response:', clickResponse, 'lastError:', chrome.runtime.lastError);
                    if (chrome.runtime.lastError || !clickResponse?.clicked) {
                        // No next page or error - done with this query
                        console.log('No next page available or click failed');
                        scrapingState.currentPageOffset = 0;
                        scrapingState.nextPageUrl = null;
                        scrapingState.completed++;
                        scheduleNext();
                    } else {
                        // Clicked successfully - wait for content to update then scrape again
                        console.log('Click successful, waiting 3s for page to update...');
                        scrapingState.currentPageOffset += 10;
                        // Wait 3 seconds then scrape directly (Bing might not do a full reload)
                        setTimeout(() => {
                            console.log('Timeout done, triggering scrape...');
                            triggerScrape(tabId);
                        }, 3000);
                    }
                });
            } else {
                // Done with this query
                console.log(`Pagination: Done with query. Collected ${scrapingState.resultsForCurrentQuery} results.`);
                scrapingState.currentPageOffset = 0;
                scrapingState.nextPageUrl = null;
                scrapingState.completed++; // Only increment completed when query is FULLY done
                scheduleNext();
            }
        } else {
            handleQueryError(response ? response.error : "Unknown error");
            scrapingState.currentPageOffset = 0; // Skip to next query on error
            scrapingState.nextPageUrl = null;
            scheduleNext();
        }
    });
}

function saveQueryResults(results) {
    const qObj = uploadedQueries[scrapingState.currentQueryIndex];
    const query = (typeof qObj === 'string') ? qObj : (qObj?.query || '');
    const run_id = (typeof qObj === 'object' && qObj) ? (qObj.run_id || '') : '';
    
    // Stop exactly at maxResultsPerQuery - don't overshoot
    const remaining = scrapingState.maxResultsPerQuery - scrapingState.resultsForCurrentQuery;
    if (remaining <= 0) {
        console.log('Already have enough results, skipping this batch');
        return;
    }
    results = results.slice(0, remaining);
    
    // Add query metadata to each result and FIX POSITION STRICTLY
    const maxChars = Math.max(0, parseInt(scrapingState.contentMaxChars || 0, 10) || 0);
    const enrichedResults = results.map((r, index) => {
        // Safety: even if content script returns full text, keep memory bounded.
        // 0 means "metadata only" (drop stored text).
        let content = r.content || '';
        let contentTruncated = r.content_truncated || '';
        if (typeof content !== 'string') content = String(content || '');
        if (maxChars === 0 && content) {
            content = '';
            contentTruncated = contentTruncated || '1';
        } else if (maxChars > 0 && content.length > maxChars) {
            content = content.slice(0, maxChars);
            contentTruncated = contentTruncated || '1';
        }

        return ({
        run_id: run_id,
        query: query,
        ...r,
        // STRICT SEQUENTIAL POSITION
        // Ignore r.position and Bing offset. Just count what we have collected.
            position: scrapingState.resultsForCurrentQuery + index + 1,
            content: content,
            content_truncated: contentTruncated
        });
    });
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
    
    // Configurable delay between query navigations.
    // Add small jitter to avoid looking perfectly robotic.
    let delay = Math.max(0, parseInt(scrapingState.queryDelayMs || DEFAULT_QUERY_DELAY_MS, 10) || DEFAULT_QUERY_DELAY_MS);
    delay += Math.floor(Math.random() * 750);

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

function downloadCheckpoint() {
    if (scrapingState.collectedResults && scrapingState.collectedResults.length > 0) {
        const csvData = generateCSV(scrapingState.collectedResults);
        const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
        downloadCSV(csvData, `bing_partial_${timestamp}.csv`);
        showStatus(`Downloaded ${scrapingState.collectedResults.length} results`, 'success');
    } else {
        showStatus('No data collected yet to download', 'warning');
    }
}

function stopRun() {
    if (!scrapingState.isRunning) {
        showStatus('No run in progress', 'warning');
        return;
    }
    
    scrapingState.isRunning = false;
    showStatus('Stopping run... (partial results preserved)', 'warning');
    
    // If we have results, show them
    if (scrapingState.collectedResults && scrapingState.collectedResults.length > 0) {
        const csvContent = generateCSV(scrapingState.collectedResults);
        showResults(csvContent, scrapingState.completed);
    } else {
        // Reset UI
        hideSection('progress');
        showSection('config');
        showSection('action');
        startButton.innerHTML = '<i class="fas fa-play"></i><span>Start Scraping</span>';
        startButton.disabled = false;
    }
}

function generateCSV(results) {
    if (!results || results.length === 0) return "query,error\nNo results found,";
    
    // Dynamic headers based on all keys found
    const allKeys = new Set();
    results.forEach(r => Object.keys(r).forEach(k => allKeys.add(k)));
    const headers = Array.from(allKeys).sort();
    
    // Stable, analysis-friendly header order (always include expected metadata fields)
    const preferred = [
        'query',
        'position',
        'run_id',
        'title',
        'snippet',
        'displayUrl',
        'domain',
        'url',
        'page_num',
        // content + extraction status
        'content',
        'contentLength',
        'contentError',
        'content_truncated',
        // page metadata/features we rely on later
        'page_title',
        'meta_description',
        'canonical_url',
        'has_schema_markup',
        'schema_types',
        'table_count',
        'has_table',
        'published_date',
        'modified_date',
        'js_render_suspected',
    ];
    const preferredSet = new Set(preferred);
    // Ensure preferred columns exist in the header list even if some rows don't contain them
    preferred.forEach(k => allKeys.add(k));
    const all = Array.from(allKeys);
    const orderedHeaders = [
        ...preferred,
        ...all.filter(h => !preferredSet.has(h)).sort()
    ];
    
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
        const qObj = uploadedQueries[currentQueryIndex];
        const qText = (typeof qObj === 'object' && qObj) ? (qObj.query || qObj.url || '') : String(qObj || '');
        currentQuery.textContent = qText.length > 50 ? qText.substring(0, 50) + '...' : qText;
        
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
    alert("Bing Scraper\n\nInput:\n- CSV with 'query' column (optional: 'run_id')\n\n1. Click Start.\n2. The tool will navigate Bing automatically and collect organic results.\n\nNote: Content extraction can take longer; use concurrency/delay controls to tune.");
}

// export
window.getUploadedQueries = () => uploadedQueries;
window.getScrapingState = () => scrapingState;
