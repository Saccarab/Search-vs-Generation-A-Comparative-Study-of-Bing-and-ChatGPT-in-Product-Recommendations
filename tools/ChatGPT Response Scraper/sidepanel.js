// ChatGPT Response Scraper - Sidepanel Controller
// WARNING: This extension may violate OpenAI's Terms of Service
// Use responsibly and consider official APIs for production applications

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
const runsPerQInput = document.getElementById('runsPerQ');
const totalOpsDisplay = document.getElementById('totalOps');
const webSearchToggle = document.getElementById('webSearchToggle');

// Progress elements
const progressStatus = document.getElementById('progressStatus');
const progressFill = document.getElementById('progressFill');
const progressPercent = document.getElementById('progressPercent');
const progressCount = document.getElementById('progressCount');
const currentQuery = document.getElementById('currentQuery');
const completedCount = document.getElementById('completedCount');
const estimatedTime = document.getElementById('estimatedTime');
const errorCountDisplay = document.getElementById('errorCount');
const recentErrors = document.getElementById('recentErrors');
const errorList = document.getElementById('errorList');

// Results elements
const resultsSummary = document.getElementById('resultsSummary');
const downloadFilename = document.getElementById('downloadFilename');
const downloadSize = document.getElementById('downloadSize');
const downloadButton = document.getElementById('downloadButton');
const newCollectionButton = document.getElementById('newCollectionButton');

// State
let uploadedQueries = [];
let scrapingState = {
    isRunning: false,
    startTime: null,
    totalQueries: 0,
    completed: 0,
    errors: 0,
    errorList: [],
    retries: 0,
    currentQueryIndex: -1,
    currentRun: 0,
    runsPerQuery: 1,
    csvData: null,
    forceWebSearch: true
};

// Initialize
document.addEventListener('DOMContentLoaded', initializeApp);

function initializeApp() {
    setupEventListeners();
    updateTotalOperations();
    
    // Initial state - show upload section
    showSection('upload');
}

function setupEventListeners() {
    // File upload events
    dropZone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', (e) => handleFile(e.target.files[0]));
    
    // Drag and drop events
    dropZone.addEventListener('dragover', handleDragOver);
    dropZone.addEventListener('dragleave', handleDragLeave);
    dropZone.addEventListener('drop', handleDrop);
    
    // Control events
    runsPerQInput.addEventListener('input', updateTotalOperations);
    webSearchToggle.addEventListener('change', handleWebSearchToggle);
    startButton.addEventListener('click', startScraping);
    downloadButton.addEventListener('click', downloadResults);
    newCollectionButton.addEventListener('click', resetApp);
    
    // Footer events
    document.getElementById('helpLink').addEventListener('click', showHelp);
}

// File handling
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
    
    // Success - show file info and next steps
    dropZone.classList.add('uploaded');
    showFileInfo(file);
    updateTotalOperations();
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

function updateTotalOperations() {
    const runs = parseInt(runsPerQInput.value) || 1;
    const total = uploadedQueries.length * runs;
    totalOpsDisplay.textContent = total;
    
    // Update estimated time (rough estimate: 30 seconds per operation)
    const estimatedMinutes = Math.ceil((total * 30) / 60);
    if (total > 0) {
        document.querySelector('.input-hint').textContent = `~${estimatedMinutes} min estimated`;
    }
}

function handleWebSearchToggle() {
    scrapingState.forceWebSearch = webSearchToggle.checked;
    console.log('Web search setting:', scrapingState.forceWebSearch ? 'enabled' : 'disabled');
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

// Scraping control
function startScraping() {
    if (uploadedQueries.length === 0) {
        showStatus('Please upload a CSV file first', 'warning');
        return;
    }
    
    const runs = parseInt(runsPerQInput.value) || 1;
    const forceWebSearch = webSearchToggle.checked;
    
    // Initialize scraping state
    scrapingState = {
        isRunning: true,
        startTime: Date.now(),
        totalQueries: uploadedQueries.length,
        totalOperations: uploadedQueries.length * runs,
        completed: 0,
        errors: 0,
        errorList: [],
        retries: 0,
        currentQueryIndex: 0,
        currentRun: 1,
        runsPerQuery: runs,
        csvData: null,
        forceWebSearch: forceWebSearch
    };
    
    // Update UI
    startButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>Scraping...</span>';
    startButton.disabled = true;
    
    // Disable toggle during processing
    webSearchToggle.disabled = true;
    
    hideSection('config');
    hideSection('action');
    showSection('progress');
    
    updateProgressDisplay();
    
    // Send command to content script
    sendCommand({
        action: 'startDataCollection',
        queries: uploadedQueries,
        runs_per_q: runs,
        force_web_search: forceWebSearch
    });
}

function updateProgressDisplay() {
    const { completed, totalOperations, currentQueryIndex, currentRun, runsPerQuery, retries } = scrapingState;
    
    // Progress bar
    const progress = Math.round((completed / totalOperations) * 100);
    progressFill.style.width = progress + '%';
    progressPercent.textContent = progress + '%';
    progressCount.textContent = `${completed} / ${totalOperations}`;
    
    // Current task
    if (currentQueryIndex < uploadedQueries.length) {
        const query = uploadedQueries[currentQueryIndex];
        currentQuery.textContent = query.length > 50 ? query.substring(0, 50) + '...' : query;
        const retryInfo = retries > 0 ? ` • ${retries} retries` : '';
        progressStatus.textContent = `Scraping query ${currentQueryIndex + 1} of ${uploadedQueries.length} (Run ${currentRun}/${runsPerQuery})${retryInfo}`;
    }
    
    // Stats
    completedCount.textContent = completed;
    errorCountDisplay.textContent = scrapingState.errors;
    
    // Estimated time
    if (completed > 0 && scrapingState.startTime) {
        const elapsed = Date.now() - scrapingState.startTime;
        const avgTimePerOp = elapsed / completed;
        const remaining = totalOperations - completed;
        const estimatedRemaining = Math.round((remaining * avgTimePerOp) / 1000 / 60);
        estimatedTime.textContent = estimatedRemaining > 0 ? `${estimatedRemaining} min` : 'Almost done';
    } else {
        estimatedTime.textContent = 'Calculating...';
    }
    
    // Show errors if any
    if (scrapingState.errors > 0) {
        recentErrors.style.display = 'block';
        updateErrorList();
    }
}

function updateErrorList() {
    errorList.innerHTML = '';
    const recentErrorsList = scrapingState.errorList.slice(-3); // Show last 3 errors
    
    recentErrorsList.forEach(error => {
        const errorItem = document.createElement('div');
        errorItem.className = 'error-item';
        errorItem.textContent = `Query ${error.queryIndex}: ${error.message}`;
        errorList.appendChild(errorItem);
    });
}

function showResults(csvData, totalResults) {
    scrapingState.csvData = csvData;
    
    hideSection('progress');
    showSection('results');
    
    // Re-enable toggle
    webSearchToggle.disabled = false;
    
    // Update results info
    const successRate = Math.round(((totalResults - scrapingState.errors) / totalResults) * 100);
    resultsSummary.textContent = `Scraping completed successfully! ${successRate}% success rate (${scrapingState.errors} errors)`;
    
    const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
    const filename = `chatgpt_results_${timestamp}.csv`;
    downloadFilename.textContent = filename;
    
    const sizeKB = Math.round(new Blob([csvData]).size / 1024);
    const resultCount = csvData.split('\n').length - 1; // Minus header
    downloadSize.textContent = `${sizeKB} KB • ${resultCount} results`;
    
    // Auto-download
    downloadCSV(csvData, filename);
}

function downloadResults() {
    if (scrapingState.csvData) {
        const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
        const filename = `chatgpt_results_${timestamp}.csv`;
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
    // Reset state
    uploadedQueries = [];
    scrapingState = {
        isRunning: false,
        startTime: null,
        totalQueries: 0,
        completed: 0,
        errors: 0,
        errorList: [],
        retries: 0,
        currentQueryIndex: -1,
        currentRun: 0,
        runsPerQuery: 1,
        csvData: null,
        forceWebSearch: true
    };
    
    // Reset UI
    resetUploadState();
    hideSection('config');
    hideSection('action');
    hideSection('progress');
    hideSection('results');
    
    startButton.innerHTML = '<i class="fas fa-play"></i><span>Start Scraping</span>';
    startButton.disabled = false;
    webSearchToggle.checked = true;
    webSearchToggle.disabled = false;
    runsPerQInput.value = 1;
    updateTotalOperations();
}

function resetUploadState() {
    dropZone.classList.remove('uploaded', 'dragover');
    status.style.display = 'none';
    fileInfoCard.style.display = 'none';
}

// Communication
function sendCommand(command) {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (!tabs.length) {
            showStatus('Please make sure you have ChatGPT open in the current tab', 'error');
            return;
        }
        
        const activeTabId = tabs[0].id;
        
        // Check if we're on ChatGPT
        if (!tabs[0].url.includes('chatgpt.com')) {
            showStatus('Please navigate to chatgpt.com first', 'error');
            return;
        }
        
        chrome.tabs.sendMessage(activeTabId, command, (response) => {
            if (chrome.runtime.lastError) {
                showStatus('Failed to communicate with ChatGPT tab. Please refresh the page.', 'error');
                resetApp();
            } else {
                console.log('Command sent successfully:', response);
            }
        });
    });
}

// Listen for messages from content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    switch (message.action) {
        case 'dataCollectionComplete':
            scrapingState.isRunning = false;
            showResults(message.csvData, message.totalResults);
            break;
            
        case 'dataCollectionError':
            scrapingState.isRunning = false;
            showStatus(`Scraping failed: ${message.error}`, 'error');
            startButton.innerHTML = '<i class="fas fa-play"></i><span>Start Scraping</span>';
            startButton.disabled = false;
            webSearchToggle.disabled = false;
            hideSection('progress');
            showSection('action');
            break;
            
        case 'progressUpdate':
            if (message.queryIndex !== undefined) {
                scrapingState.currentQueryIndex = message.queryIndex;
            }
            if (message.run !== undefined) {
                scrapingState.currentRun = message.run;
            }
            if (message.completed !== undefined) {
                scrapingState.completed = message.completed;
            }
            if (message.retryAttempt) {
                scrapingState.retries++;
                console.log(`Retry attempt ${message.retryCount}/${message.maxRetries} for current query`);
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

// Helper functions
function showHelp() {
    const helpText = `ChatGPT Response Scraper Help:

LEGAL WARNING: This tool may violate OpenAI's Terms of Service. Use at your own risk.

How to use:
1. Upload a CSV file with a 'query' column
2. Set the number of runs per query (1-10)
3. Toggle 'Force Web Search' on/off (sources are collected regardless)
4. Click 'Start Scraping'
5. Wait for processing to complete
6. Download your results

The extension will:
• Create new temporary chats for each query
• Collect responses and source links from ChatGPT
• Handle multiple runs per query automatically
• Automatically retry up to 3 times if web search is forced but no sources appear
• Export results to CSV

Consider using the official OpenAI API instead:
https://platform.openai.com/docs/api-reference

CSV Output Columns:
• query_index: Query number (1, 2, 3...)
• run_number: Run number for the query (1, 2, 3...)
• retry_count: Number of retries needed (0, 1, 2, 3)
• query: The original search query
• response_text: ChatGPT's full response
• web_search_forced: Whether web search was forced
• sources_cited: URLs from citations section
• sources_additional: URLs from additional sources section
• no_sources_warning: YES if forced web search failed after all retries`;

    alert(helpText);
}

// Export for global access
window.getUploadedQueries = () => uploadedQueries;
window.getScrapingState = () => scrapingState;