let masterBundle = null;

document.addEventListener('DOMContentLoaded', () => {
    const loadBtn = document.getElementById('loadDataBtn');
    loadBtn.addEventListener('click', loadBundle);
    
    const showStatsBtn = document.getElementById('showStatsBtn');
    showStatsBtn.addEventListener('click', showStats);
    
    const closeStatsBtn = document.getElementById('closeStatsBtn');
    closeStatsBtn.addEventListener('click', () => {
        document.getElementById('statsOverlay').style.display = 'none';
    });

    // Auto-load on startup since we are running as a server now
    loadBundle();
});

function showStats() {
    if (!masterBundle) return;
    
    const overlay = document.getElementById('statsOverlay');
    overlay.style.display = 'flex';
    
    let totalChunks = 0;
    let totalMatches = 0;
    const tableBody = document.getElementById('statsTableBody');
    tableBody.innerHTML = '';
    
    masterBundle.runs.forEach(run => {
        // Calculate matches for this run
        const allSerpUrls = new Set();
        Object.values(run.serps || {}).forEach(results => {
            results.forEach(r => allSerpUrls.add(normalizeUrl(r.link)));
        });
        
        const chunks = run.groundingChunks || [];
        const matches = chunks.filter(c => allSerpUrls.has(normalizeUrl(c.web?.resolvedUri || c.web?.uri))).length;
        const rate = chunks.length > 0 ? (matches / chunks.length * 100) : 0;
        
        totalChunks += chunks.length;
        totalMatches += matches;
        
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${run.runId}</strong></td>
            <td>${chunks.length}</td>
            <td>${matches}</td>
            <td>
                <div class="survival-bar-bg"><div class="survival-bar-fill" style="width: ${rate}%"></div></div>
                ${rate.toFixed(1)}%
            </td>
        `;
        tableBody.appendChild(tr);
    });
    
    document.getElementById('statTotalRuns').textContent = masterBundle.runs.length;
    document.getElementById('statTotalChunks').textContent = totalChunks;
    const globalRate = totalChunks > 0 ? (totalMatches / totalChunks * 100) : 0;
    document.getElementById('statSurvivalRate').textContent = globalRate.toFixed(1) + '%';
}

async function loadBundle() {
    const statusEl = document.getElementById('loadDataBtn');
    statusEl.textContent = 'Loading...';
    
    try {
        // Fetch from our new API endpoint to bypass all CORS/File issues
        const response = await fetch('/api/bundle');
        if (!response.ok) throw new Error('Bundle not found. Run node scripts/build_viz_bundle.mjs first.');
        
        masterBundle = await response.json();
        renderRunList();
        
        statusEl.textContent = 'Data Loaded ✅';
        statusEl.classList.add('success');
    } catch (err) {
        console.error(err);
        statusEl.textContent = 'Load Failed ❌';
    }
}

function renderRunList() {
    const list = document.getElementById('runList');
    list.innerHTML = '';
    
    masterBundle.runs.forEach(run => {
        const div = document.createElement('div');
        div.className = 'run-item';
        div.innerHTML = `<strong>${run.runId}</strong><br><small>${run.promptText.substring(0, 30)}...</small>`;
        div.onclick = (e) => selectRun(run, e);
        list.appendChild(div);
    });
}

function selectRun(run, event) {
    document.querySelectorAll('.run-item').forEach(el => el.classList.remove('active'));
    if (event) event.currentTarget.classList.add('active');
    
    document.getElementById('welcomeScreen').style.display = 'none';
    document.getElementById('dashboard').style.display = 'flex';
    
    document.getElementById('displayPrompt').textContent = run.promptText;
    document.getElementById('displayRunId').textContent = run.runId;

    renderGeminiResponse(run);
    renderFanOutQueries(run);
    renderGroundingChunks(run); // New function to show all chunks
    renderSerpTabs(run);
}

function renderGroundingChunks(run) {
    const container = document.getElementById('groundingChunksList');
    if (!container) return;
    
    const chunks = run.groundingChunks || [];
    
    if (chunks.length === 0) {
        container.innerHTML = '<p class="info">No grounding chunks found in metadata.</p>';
        return;
    }

    // Collect ALL SERP URLs from all queries for this run
    const serpMatches = {}; // Map normalizedUrl -> { query, rank }
    Object.entries(run.serps || {}).forEach(([query, results]) => {
        results.forEach((r, idx) => {
            const norm = normalizeUrl(r.link);
            if (!serpMatches[norm]) {
                serpMatches[norm] = { query, rank: r.position || (idx + 1) };
            }
        });
    });

    container.innerHTML = chunks.map((chunk, idx) => {
        const rawUri = chunk.web?.uri || '';
        const resolvedUri = chunk.web?.resolvedUri || rawUri;
        const isResolved = resolvedUri !== rawUri;
        
        // Check if this chunk matches ANY SERP result
        const normalizedChunkUrl = normalizeUrl(resolvedUri);
        const matchData = serpMatches[normalizedChunkUrl];
        const matchesSERP = !!matchData;
        
        return `
            <div class="chunk-card ${matchesSERP ? 'chunk-matched' : ''}">
                <div class="chunk-header">
                    <span class="chunk-index">[${idx}]</span>
                    <span class="chunk-title-text">${chunk.web?.title || 'Untitled Source'}</span>
                    ${matchesSERP ? `<span class="serp-match-badge">IN TOP 20 ✓ (#${matchData.rank})</span>` : '<span class="no-match-badge">NOT IN TOP 20</span>'}
                </div>
                <div class="chunk-url-box">
                    <div class="url-line">
                        <strong>Raw:</strong> <a href="${rawUri}" target="_blank" class="raw-link">${rawUri}</a>
                    </div>
                    <div class="url-line ${isResolved ? 'resolved' : ''}">
                        <strong>Final:</strong> <a href="${resolvedUri}" target="_blank">${resolvedUri}</a>
                        ${isResolved ? '<span class="resolved-tag">RESOLVED</span>' : ''}
                    </div>
                    ${matchesSERP ? `
                    <div class="match-details">
                        <i class="fas fa-search"></i> Found in SERP for: <em>"${matchData.query}"</em>
                    </div>
                    ` : ''}
                </div>
            </div>
        `;
    }).join('');
}

function renderFanOutQueries(run) {
    const container = document.getElementById('fanOutQueries');
    const queries = run.webSearchQueries || [];
    
    if (queries.length === 0) {
        container.innerHTML = '<p class="info">No fan-out queries triggered.</p>';
        return;
    }

    container.innerHTML = queries.map((q, idx) => `
        <div class="fanout-item">
            <span class="num">${idx + 1}</span>
            <span class="text">${q}</span>
        </div>
    `).join('');
}

function renderGeminiResponse(run) {
    const container = document.getElementById('geminiResponse');
    let text = run.geminiResponse;
    
    // Links are already resolved at build time in the markdown text
    text = text.replace(/\[(.*?)\]\((.*?)\)/g, (match, title, url) => {
        return `<a href="${url}" target="_blank" class="gemini-link">${title}</a>`;
    });

    // Handle newlines and bolding
    text = text.replace(/\n/g, '<br>');
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    container.innerHTML = text;
}

function renderSerpTabs(run) {
    const tabsContainer = document.getElementById('serpTabs');
    tabsContainer.innerHTML = '';
    
    const queries = run.webSearchQueries || [];
    
    // We don't need finalGroundingUrls here anymore as displaySerpResults 
    // calculates matches dynamically from groundingChunks
    queries.forEach((query, idx) => {
        const tab = document.createElement('div');
        tab.className = `serp-tab ${idx === 0 ? 'active' : ''}`;
        tab.textContent = `Q${idx + 1}`;
        tab.title = query;
        tab.onclick = (e) => displaySerpResults(query, run, e.currentTarget);
        tabsContainer.appendChild(tab);
    });

    if (queries.length > 0) {
        displaySerpResults(queries[0], run, tabsContainer.firstChild);
    }
}

function displaySerpResults(query, run, tabEl) {
    document.querySelectorAll('.serp-tab').forEach(el => el.classList.remove('active'));
    if (tabEl) tabEl.classList.add('active');

    const container = document.getElementById('serpResults');
    const results = run.serps[query] || [];

    if (results.length === 0) {
        container.innerHTML = `<p class='error'>No SERP data found for: <br><i>${query}</i></p>`;
        return;
    }

    // Get ALL grounding chunks for this run
    const runChunks = run.groundingChunks || [];

    container.innerHTML = '';
    results.forEach((res, index) => {
        const normalizedSerpUrl = normalizeUrl(res.link);
        
        // Find if this SERP link matches any grounding chunk using the PRE-RESOLVED URI
        const matchedChunk = runChunks.find(chunk => {
            const finalUri = chunk.web?.resolvedUri || chunk.web?.uri || '';
            return normalizeUrl(finalUri) === normalizedSerpUrl;
        });

        const isSurvived = !!matchedChunk;
        
        // Page break logic (every 10 results usually indicates a new page in SerpApi)
        if (index > 0 && index % 10 === 0) {
            const pageBreak = document.createElement('div');
            pageBreak.className = 'page-divider';
            pageBreak.innerHTML = `<span>PAGE ${Math.floor(index / 10) + 1}</span>`;
            container.appendChild(pageBreak);
        }

        const div = document.createElement('div');
        div.className = `serp-item ${isSurvived ? 'survived' : ''} ${res.result_type ? 'type-' + res.result_type : ''}`;
        
        let typeBadge = '';
        if (res.result_type === 'video') typeBadge = '<span class="type-badge video"><i class="fas fa-video"></i> VIDEO</span>';
        if (res.result_type === 'discussion') typeBadge = '<span class="type-badge forum"><i class="fas fa-comments"></i> FORUM</span>';

        let chunkHtml = '';
        if (matchedChunk) {
            chunkHtml = `
                <div class="grounding-chunk-info">
                    <i class="fas fa-link"></i> <strong>Grounding Chunk Match:</strong>
                    <p class="chunk-title">${matchedChunk.web?.title || 'No Title'}</p>
                    <div class="chunk-meta">Matched via: ${matchedChunk.web?.uri.includes('vertex') ? 'Resolved Redirect' : 'Direct URL'}</div>
                </div>
            `;
        }

        div.innerHTML = `
            <div class="serp-main">
                <span class="rank">#${res.position || (index + 1)}</span>
                <div class="serp-content">
                    <div class="title-row">
                        <a href="${res.link}" target="_blank" class="title">${res.title}</a>
                        ${typeBadge}
                        ${isSurvived ? '<span class="survived-badge"><i class="fas fa-check-circle"></i> CITED BY AI</span>' : ''}
                    </div>
                    <span class="url">${res.link}</span>
                    <p class="snippet">${res.snippet || ''}</p>
                </div>
            </div>
            ${chunkHtml}
        `;
        container.appendChild(div);
    });
}

function normalizeUrl(url) {
    try {
        const u = new URL(url);
        return (u.hostname.replace('www.', '') + u.pathname.replace(/\/$/, '')).toLowerCase();
    } catch (e) {
        return url.toLowerCase();
    }
}
