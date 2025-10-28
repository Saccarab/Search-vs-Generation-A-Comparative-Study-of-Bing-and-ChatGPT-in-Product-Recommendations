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
const CONTENT_TIMEOUT = 15000; // 15 seconds
const REQUEST_DELAY = 2000; // 2 seconds

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
    extractContent: true,
    csvData: null,
    currentPhase: 'search', // 'search', 'content', 'complete'
    contentProgress: 0,
    contentTotal: 0,
    searchResults: 0,
    contentExtracted: 0
};

// initialize
document.addEventListener('DOMContentLoaded', initializeApp);

function initializeApp() {
    setupEventListeners();
    updateConfiguration();
    
    // initial state - show upload section
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

// file handling
function handleDragOver(e) {
    e.preventDefault();
    dropZone.classList.add('dragover');
}

function handleDragLeave() {
    dropZone.classList.remove('dragover');
}

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
        try {
            parseCSV(e.target.result, file);
        } catch (error) {
            showStatus('Error reading file: ' + error.message, 'error');
        }
    };
    reader.readAsText(file);
}

function parseCSV(csvText, file) {
    const lines = csvText.trim().split('\n');
    
    if (lines.length < 2) {
        showStatus('CSV must have header and at least one data row', 'error');
        return;
    }
    
    const headers = lines[0].split(',').map(h => h.trim().toLowerCase().replace(/['"]/g, ''));
    
    if (!headers.includes('query')) {
        showStatus('CSV must have a "query" column', 'error');
        return;
    }
    
    const queryIndex = headers.indexOf('query');
    uploadedQueries = [];
    
    for (let i = 1; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) continue;
        
        const values = parseCSVLine(line);
        const query = values[queryIndex]?.trim().replace(/['"]/g, '');
        if (query) {
            uploadedQueries.push(query);
        }
    }
    
    if (uploadedQueries.length === 0) {
        showStatus('No valid queries found in the CSV file', 'error');
        return;
    }
    
    // success - show file info and next steps
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
        
        if (char === '"') {
            inQuotes = !inQuotes;
        } else if (char === ',' && !inQuotes) {
            result.push(current);
            current = '';
        } else {
            current += char;
        }
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
    
    // update total results
    const total = uploadedQueries.length * maxResults;
    totalResultsDisplay.textContent = total;
    
    // calculate estimated duration
    let estimatedMinutes = 0;
    if (uploadedQueries.length > 0) {
        // base time estimation based on real performance:
        // - search: ca 30-45 seconds per query (includes pagination, delays, etc.)
        estimatedMinutes = uploadedQueries.length * 0.6; // 0.6 minutes = 36 seconds per query
        
        // add time for content extraction if enabled
        if (extractContent) {
            // content extraction: ca 2-3 seconds per result when batched
            // assuming 80% success rate and 3 concurrent requests
            const avgSuccessfulResults = Math.ceil(total * 0.8);
            const contentExtractionMinutes = (avgSuccessfulResults * 2.5) / 60; // 2.5 seconds per result
            
            estimatedMinutes += contentExtractionMinutes;
        }
    }
    
    if (estimatedMinutes > 0) {
        if (estimatedMinutes < 60) {
            estimatedDuration.textContent = `~${Math.ceil(estimatedMinutes)} minutes`;
        } else {
            const hours = Math.floor(estimatedMinutes / 60);
            const mins = Math.ceil(estimatedMinutes % 60);
            if (mins === 0) {
                estimatedDuration.textContent = `~${hours}h`;
            } else {
                estimatedDuration.textContent = `~${hours}h ${mins}m`;
            }
        }
    } else {
        estimatedDuration.textContent = 'Upload queries to calculate';
    }
}

function showStatus(message, type) {
    status.textContent = message;
    status.className = `status-message ${type}`;
    status.style.display = 'flex';
    status.classList.add('fade-in');
    
    if (type === 'success') {
        setTimeout(() => {
            status.style.display = 'none';
        }, 3000);
    }
}

function showSection(section) {
    const sections = {
        'config': configSection,
        'action': actionSection,
        'progress': progressSection,
        'results': resultsSection
    };
    
    if (sections[section]) {
        sections[section].style.display = 'block';
        sections[section].classList.add('fade-in');
    }
}

function hideSection(section) {
    const sections = {
        'config': configSection,
        'action': actionSection,
        'progress': progressSection,
        'results': resultsSection
    };
    
    if (sections[section]) {
        sections[section].style.display = 'none';
    }
}

// scraping control
function startScraping() {
    if (uploadedQueries.length === 0) {
        showStatus('Please upload a CSV file first', 'warning');
        return;
    }
    
    const maxResults = parseInt(maxResultsInput.value) || 10;
    const extractContent = extractContentCheckbox.checked;
    
    // initialize scraping state
    scrapingState = {
        isRunning: true,
        startTime: Date.now(),
        totalQueries: uploadedQueries.length,
        completed: 0,
        errors: 0,
        errorList: [],
        currentQueryIndex: 0,
        maxResultsPerQuery: maxResults,
        extractContent: extractContent,
        csvData: null,
        currentPhase: 'search',
        contentProgress: 0,
        contentTotal: 0,
        searchResults: 0,
        contentExtracted: 0
    };
    
    // update UI
    startButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>Starting...</span>';
    startButton.disabled = true;
    
    hideSection('config');
    hideSection('action');
    showSection('progress');
    
    updateProgressDisplay();
    
    // send command to content script
    sendCommand({
        action: 'startScraping',
        queries: uploadedQueries,
        maxResultsPerQuery: maxResults,
        extractContent: extractContent,
        contentTimeout: CONTENT_TIMEOUT,
        requestDelay: REQUEST_DELAY
    });
}

function updateProgressDisplay() {
    const { completed, totalQueries, currentQueryIndex, currentPhase } = scrapingState;
    
    // main progress bar (overall completion)
    const progress = Math.round((completed / totalQueries) * 100);
    progressFill.style.width = progress + '%';
    progressPercent.textContent = progress + '%';
    progressCount.textContent = `${completed} / ${totalQueries}`;
    
    // current task
    if (currentQueryIndex < uploadedQueries.length) {
        const query = uploadedQueries[currentQueryIndex];
        currentQuery.textContent = query.length > 50 ? query.substring(0, 50) + '...' : query;
        
        if (currentPhase === 'search') {
            taskLabel.textContent = 'Searching:';
            progressStatus.textContent = `Searching query ${currentQueryIndex + 1} of ${totalQueries}`;
        } else if (currentPhase === 'content') {
            taskLabel.textContent = 'Extracting content for:';
            progressStatus.textContent = `Extracting content for query ${currentQueryIndex + 1}`;
        }
    }
    
    // phase-specific progress
    if (currentPhase === 'content' && scrapingState.contentTotal > 0) {
        phaseProgress.style.display = 'block';
        phaseLabel.textContent = 'Content Extraction';
        phaseStatus.textContent = `${scrapingState.contentProgress} / ${scrapingState.contentTotal}`;
        
        const phaseProgressPercent = Math.round((scrapingState.contentProgress / scrapingState.contentTotal) * 100);
        phaseFill.style.width = phaseProgressPercent + '%';
    } else {
        phaseProgress.style.display = 'none';
    }
    
    // stats
    completedCount.textContent = completed;
    errorCountDisplay.textContent = scrapingState.errors;
    
    // estimated time
    if (completed > 0 && scrapingState.startTime) {
        const elapsed = Date.now() - scrapingState.startTime;
        const avgTimePerQuery = elapsed / completed;
        const remaining = totalQueries - completed;
        const estimatedRemaining = Math.round((remaining * avgTimePerQuery) / 1000 / 60);
        estimatedTime.textContent = estimatedRemaining > 0 ? `${estimatedRemaining} min` : 'Almost done';
    } else {
        estimatedTime.textContent = 'Calculating...';
    }
    
    // show errors if any
    if (scrapingState.errors > 0) {
        recentErrors.style.display = 'block';
        updateErrorList();
    }
}

function updateErrorList() {
    errorList.innerHTML = '';
    const recentErrorsList = scrapingState.errorList.slice(-3); // show last 3 errors
    
    recentErrorsList.forEach(error => {
        const errorItem = document.createElement('div');
        errorItem.className = 'error-item';
        errorItem.textContent = `Query ${error.queryIndex}: ${error.message}`;
        errorList.appendChild(errorItem);
    });
}

function showResults(csvData, totalQueries) {
    scrapingState.csvData = csvData;
    
    hideSection('progress');
    showSection('results');
    
    // count results from CSV
    const lines = csvData.split('\n').filter(line => line.trim() !== '');
    const totalResults = Math.max(0, lines.length - 1); // minus header
    
    // count successful content extractions (look for non-empty content)
    let contentSuccessCount = 0;
    if (scrapingState.extractContent) {
        const contentColumnIndex = lines[0].split(',').indexOf('content');
        if (contentColumnIndex >= 0) {
            for (let i = 1; i < lines.length; i++) {
                const row = parseCSVLine(lines[i]);
                if (row[contentColumnIndex] && row[contentColumnIndex].trim() && 
                    !row[contentColumnIndex].includes('ERROR:')) {
                    contentSuccessCount++;
                }
            }
        }
    }
    
    scrapingState.searchResults = totalResults;
    scrapingState.contentExtracted = contentSuccessCount;
    
    // update results info
    const successRate = Math.round(((totalQueries - scrapingState.errors) / totalQueries) * 100);
    resultsSummary.textContent = `Scraping completed! ${successRate}% success rate`;
    
    // update stats
    searchResultsCount.textContent = totalResults;
    contentExtractedCount.textContent = scrapingState.extractContent ? contentSuccessCount : 'N/A';
    
    const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
    const filename = `bing_results_${timestamp}.csv`;
    downloadFilename.textContent = filename;
    
    const sizeKB = Math.round(new Blob([csvData]).size / 1024);
    downloadSize.textContent = `${sizeKB} KB • ${totalResults} results`;
    
    // auto-download
    downloadCSV(csvData, filename);
}

function downloadResults() {
    if (scrapingState.csvData) {
        const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
        const filename = `bing_results_${timestamp}.csv`;
        downloadCSV(scrapingState.csvData, filename);
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
    // reset state
    uploadedQueries = [];
    scrapingState = {
        isRunning: false,
        startTime: null,
        totalQueries: 0,
        completed: 0,
        errors: 0,
        errorList: [],
        currentQueryIndex: -1,
        maxResultsPerQuery: 10,
        extractContent: true,
        csvData: null,
        currentPhase: 'search',
        contentProgress: 0,
        contentTotal: 0,
        searchResults: 0,
        contentExtracted: 0
    };
    
    // reset UI
    resetUploadState();
    hideSection('config');
    hideSection('action');
    hideSection('progress');
    hideSection('results');
    
    startButton.innerHTML = '<i class="fas fa-play"></i><span>Start Scraping</span>';
    startButton.disabled = false;
    maxResultsInput.value = 10;
    extractContentCheckbox.checked = true;
    updateConfiguration();
}

function resetUploadState() {
    dropZone.classList.remove('uploaded', 'dragover');
    status.style.display = 'none';
    fileInfoCard.style.display = 'none';
}

// communication
function sendCommand(command) {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (!tabs.length) {
            showStatus('Please make sure you have Bing open in the current tab', 'error');
            return;
        }
        
        const activeTabId = tabs[0].id;
        
        // check if we're on Bing
        if (!tabs[0].url.includes('bing.com')) {
            showStatus('Please navigate to bing.com first', 'error');
            return;
        }
        
        chrome.tabs.sendMessage(activeTabId, command, (response) => {
            if (chrome.runtime.lastError) {
                showStatus('Failed to communicate with Bing tab. Please refresh the page.', 'error');
                resetApp();
            } else {
                console.log('Command sent successfully:', response);
            }
        });
    });
}

// listen for messages from content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    switch (message.action) {
        case 'scrapingComplete':
            scrapingState.isRunning = false;
            scrapingState.currentPhase = 'complete';
            showResults(message.csvData, message.totalQueries);
            break;
            
        case 'scrapingError':
            scrapingState.isRunning = false;
            showStatus(`Scraping failed: ${message.error}`, 'error');
            startButton.innerHTML = '<i class="fas fa-play"></i><span>Start Scraping</span>';
            startButton.disabled = false;
            hideSection('progress');
            showSection('action');
            break;
            
        case 'progressUpdate':
            // update query progress
            if (message.queryIndex !== undefined) {
                scrapingState.currentQueryIndex = message.queryIndex;
            }
            if (message.completed !== undefined) {
                scrapingState.completed = message.completed;
            }
            if (message.currentQuery !== undefined) {
                currentQuery.textContent = message.currentQuery.length > 50 ? 
                    message.currentQuery.substring(0, 50) + '...' : 
                    message.currentQuery;
            }
            
            // update phase
            if (message.phase) {
                scrapingState.currentPhase = message.phase;
            }
            
            // update content extraction progress
            if (message.contentPhase) {
                scrapingState.currentPhase = 'content';
                if (message.contentProgress !== undefined) {
                    scrapingState.contentProgress = message.contentProgress;
                }
                if (message.contentTotal !== undefined) {
                    scrapingState.contentTotal = message.contentTotal;
                }
                if (message.currentUrl) {
                    currentQuery.textContent = new URL(message.currentUrl).hostname;
                }
            }
            
            updateProgressDisplay();
            break;
            
        case 'queryError':
            scrapingState.errors++;
            scrapingState.errorList.push({
                queryIndex: message.queryIndex,
                message: message.error
            });
            updateProgressDisplay();
            break;
    }
});

// helper functions
function showHelp() {
    const helpText = `Bing Search Results Scraper with Content Extraction Help:

LEGAL WARNING: This tool may violate Microsoft's Terms of Service and website robots.txt files. Content extraction may be subject to copyright restrictions. Use at your own risk.

How to use:
1. Upload a CSV file with a 'query' column
2. Configure search settings (results per query)
3. Enable/disable content extraction
4. Click 'Start Scraping'
5. Wait for processing to complete
6. Download your enhanced results

The extension will:
• Search each query on Bing
• Extract organic search results (title, URL, snippet, domain)
• Handle pagination automatically
• Optionally fetch and extract text content from each URL
• Export enhanced results to CSV

Content Extraction Features:
• Extracts clean text content from web pages
• Removes navigation, ads, and non-content elements
• Handles timeouts and errors gracefully
• Rate limits requests to be respectful
• Adds content length and error tracking

Consider using the official Bing Web Search API instead:
https://docs.microsoft.com/en-us/bing/search-apis/

Enhanced CSV Output Columns:
• query: Search query used
• position: Result position (1, 2, 3...)
• page: Search results page number
• title: Result title
• url: Clean result URL
• domain: Domain name
• displayUrl: URL shown by Bing
• snippet: Result description/snippet
• content: Extracted text content (if enabled)
• contentLength: Character count of extracted content
• contentError: Any errors during content extraction

Tips:
• Enable content extraction for research and analysis
• Some sites may block automated requests
• Large content extractions take significantly longer
• The tool uses conservative delays to be respectful`;

    alert(helpText);
}

// export for global access
window.getUploadedQueries = () => uploadedQueries;
window.getScrapingState = () => scrapingState;