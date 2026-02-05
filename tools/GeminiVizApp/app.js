let masterBundle = null;
const SURVIVAL_TOP_N = 20;

document.addEventListener('DOMContentLoaded', () => {
    // Check if data is already embedded
    if (window.EMBEDDED_BUNDLE) {
        console.log("Found embedded data, loading immediately...");
        masterBundle = window.EMBEDDED_BUNDLE;
        renderRunList();
        const statusEl = document.getElementById('loadDataBtn');
        if (statusEl) {
            statusEl.textContent = 'Data Loaded ✅';
            statusEl.classList.add('success');
        }
    } else {
        console.log("No embedded data found, waiting for manual load or auto-fetch...");
        // Auto-load fallback
        setTimeout(() => {
            if (!masterBundle) loadBundle();
        }, 100);
    }

    const loadBtn = document.getElementById('loadDataBtn');
    if (loadBtn) loadBtn.addEventListener('click', loadBundle);
    
    const showStatsBtn = document.getElementById('showStatsBtn');
    if (showStatsBtn) showStatsBtn.addEventListener('click', showStats);
    
    const closeStatsBtn = document.getElementById('closeStatsBtn');
    if (closeStatsBtn) {
        closeStatsBtn.addEventListener('click', () => {
            document.getElementById('statsOverlay').style.display = 'none';
        });
    }

    const invisibleBtn = document.getElementById('invisibleExplorerBtn');
    if (invisibleBtn) {
        invisibleBtn.addEventListener('click', showInvisibleExplorer);
    }

    const closeInvisibleBtn = document.getElementById('closeInvisibleBtn');
    if (closeInvisibleBtn) {
        closeInvisibleBtn.addEventListener('click', () => {
            document.getElementById('invisibleExplorerOverlay').style.display = 'none';
        });
    }

    const showUrlExplorerBtn = document.getElementById('showUrlExplorerBtn');
    if (showUrlExplorerBtn) {
        showUrlExplorerBtn.addEventListener('click', showUrlExplorer);
    }

    const closeUrlExplorerBtn = document.getElementById('closeUrlExplorerBtn');
    if (closeUrlExplorerBtn) {
        closeUrlExplorerBtn.addEventListener('click', () => {
            document.getElementById('urlExplorerOverlay').style.display = 'none';
        });
    }

    // Filter listeners
    ['filterType', 'filterTone', 'filterFeature', 'filterScoreKey', 'filterScoreValue', 'filterSearch'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            if (id === 'filterSearch') {
                el.addEventListener('input', updateUrlExplorerTable);
            } else {
                el.addEventListener('change', updateUrlExplorerTable);
            }
        }
    });
});

function showStats() {
    if (!masterBundle) return;
    
    const overlay = document.getElementById('statsOverlay');
    overlay.style.display = 'flex';
    
    let totalChunks = 0;
    let totalMatchesAny = 0;
    const tableBody = document.getElementById('statsTableBody');
    tableBody.innerHTML = '';
    
    masterBundle.runs.forEach(run => {
        // Calculate matches for this run (ANY rank in SERP)
        const allSerpUrls = new Set();
        Object.values(run.serps || {}).forEach(results => {
            (results || []).forEach(r => allSerpUrls.add(normalizeUrl(r.link)));
        });
        
        const chunks = run.groundingChunks || [];
        const matchesAny = chunks.filter(c => allSerpUrls.has(normalizeUrl(c.web?.resolvedUri || c.web?.uri))).length;
        const rate = chunks.length > 0 ? (matchesAny / chunks.length * 100) : 0;
        
        totalChunks += chunks.length;
        totalMatchesAny += matchesAny;
        
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${run.runId}</strong></td>
            <td>${chunks.length}</td>
            <td>${matchesAny}</td>
            <td>
                <div class="survival-bar-bg"><div class="survival-bar-fill" style="width: ${rate}%"></div></div>
                ${rate.toFixed(1)}%
            </td>
        `;
        tableBody.appendChild(tr);
    });
    
    document.getElementById('statTotalRuns').textContent = masterBundle.runs.length;
    document.getElementById('statTotalChunks').textContent = totalChunks;
    const globalRate = totalChunks > 0 ? (totalMatchesAny / totalChunks * 100) : 0;
    document.getElementById('statSurvivalRate').textContent = globalRate.toFixed(1) + '%';

    // RENDER RANK DISTRIBUTION CHART
    renderRankChart();

    // RENDER QUERY OVERLAP STATS
    renderQueryOverlapStats();
}

let explorerData = [];

function showUrlExplorer() {
    if (!masterBundle || !masterBundle.enrichedData) return;
    
    const overlay = document.getElementById('urlExplorerOverlay');
    overlay.style.display = 'flex';
    
    // Prepare data once
    if (explorerData.length === 0) {
        const types = new Set();
        const tones = new Set();
        
        explorerData = Object.entries(masterBundle.enrichedData).map(([norm, dnaRaw]) => {
            const dna = dnaRaw.urls || dnaRaw;
            const type = dna.type || dna.content_format || 'unknown';
            const tone = dna.tone || 'unknown';
            const length = dnaRaw.raw_content_length || 0;
            types.add(type);
            tones.add(tone);
            return {
                url: dna.url || norm,
                type,
                tone,
                intent: dna.primary_intent || 'N/A',
                length,
                ...dna // Spread all DNA properties (has_tables, etc.)
            };
        });

        // Populate filter dropdowns
        const typeSelect = document.getElementById('filterType');
        Array.from(types).sort().forEach(t => {
            const opt = document.createElement('option');
            opt.value = t;
            opt.textContent = t;
            typeSelect.appendChild(opt);
        });

        const toneSelect = document.getElementById('filterTone');
        Array.from(tones).sort().forEach(t => {
            const opt = document.createElement('option');
            opt.value = t;
            opt.textContent = t;
            toneSelect.appendChild(opt);
        });
    }

    updateUrlExplorerTable();
}

function updateUrlExplorerTable() {
    const typeFilter = document.getElementById('filterType').value;
    const toneFilter = document.getElementById('filterTone').value;
    const featureFilter = document.getElementById('filterFeature').value;
    const scoreKey = document.getElementById('filterScoreKey').value;
    const scoreVal = parseInt(document.getElementById('filterScoreValue').value);
    const searchFilter = document.getElementById('filterSearch').value.toLowerCase();
    
    const filtered = explorerData.filter(d => {
        // Handle nested 'urls' property if it exists
        const data = d.urls || d;
        
        const matchesType = typeFilter === 'all' || data.type === typeFilter;
        const matchesTone = toneFilter === 'all' || data.tone === toneFilter;
        const matchesFeature = featureFilter === 'all' || !!data[featureFilter];
        const matchesScore = scoreKey === 'none' || (data[scoreKey] || 0) >= scoreVal;
        const matchesSearch = d.url.toLowerCase().includes(searchFilter);
        return matchesType && matchesTone && matchesFeature && matchesScore && matchesSearch;
    });

    const body = document.getElementById('explorerTableBody');
    body.innerHTML = filtered.map(d => {
        const data = d.urls || d;
        const features = [];
        if (data.has_tables) features.push('📊 Table');
        if (data.has_numbered_lists) features.push('1. List');
        if (data.has_bullet_points) features.push('• Bullet');
        if (data.has_pros_cons) features.push('⚖️ Pros/Cons');
        if (data.is_vendor_owned) features.push('🏢 Vendor');
        if (data.is_current_year_2026) features.push('📅 2026');

        return `
            <tr>
                <td style="max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                    <a href="${d.url}" target="_blank" title="${d.url}">${d.url}</a>
                </td>
                <td><span class="badge" style="background: #e0e0e0; color: #333;">${data.type || 'other'}</span></td>
                <td><span class="badge" style="background: #f0f0f0; color: #666;">${data.tone || 'neutral'}</span></td>
                <td><div class="feature-tags">${features.map(f => `<span class="feat-tag">${f}</span>`).join('')}</div></td>
                <td>
                    <div class="score-mini">Exp: ${data.expertise_signal_score || 0}</div>
                    <div class="score-mini">Frsh: ${data.freshness_cue_strength || 0}</div>
                </td>
                <td>
                    <button class="btn-mini" onclick="findUrlInRuns('${d.url}')">Find Usage</button>
                </td>
            </tr>
        `;
    }).join('');

    document.getElementById('explorerCount').textContent = `Showing ${filtered.length} URLs`;
}

window.findUrlInRuns = (url) => {
    const normTarget = normalizeUrl(url);
    const run = masterBundle.runs.find(r => {
        return (r.groundingChunks || []).some(c => normalizeUrl(c.web?.resolvedUri || c.web?.uri) === normTarget);
    });
    
    if (run) {
        document.getElementById('urlExplorerOverlay').style.display = 'none';
        // Find the run element and click it
        const runItems = document.querySelectorAll('.run-item');
        for (const item of runItems) {
            if (item.querySelector('strong').textContent === run.runId) {
                item.click();
                // Scroll to the chunk
                setTimeout(() => {
                    const cards = document.querySelectorAll('.chunk-card');
                    for (const card of cards) {
                        if (normalizeUrl(card.querySelector('.url-line.resolved a').href) === normTarget) {
                            card.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            card.style.boxShadow = '0 0 15px rgba(52, 152, 219, 0.5)';
                            setTimeout(() => card.style.boxShadow = '', 2000);
                            break;
                        }
                    }
                }, 300);
                break;
            }
        }
    } else {
        alert("This URL was not cited in any bundled runs.");
    }
};

function showInvisibleExplorer() {
    const activeRunItem = document.querySelector('.run-item.active');
    if (!activeRunItem || !masterBundle) return;
    
    // Find the current run object
    const runId = activeRunItem.querySelector('strong').textContent;
    const run = masterBundle.runs.find(r => r.runId === runId);
    if (!run) return;

    const overlay = document.getElementById('invisibleExplorerOverlay');
    overlay.style.display = 'flex';
    
    const tableBody = document.getElementById('invisibleTableBody');
    tableBody.innerHTML = '';

    // Collect ALL SERP URLs for this run
    const allSerpUrls = new Set();
    Object.values(run.serps || {}).forEach(results => {
        (results || []).forEach(r => allSerpUrls.add(normalizeUrl(r.link)));
    });

    const invisibleChunks = (run.groundingChunks || []).filter(chunk => {
        const url = normalizeUrl(chunk.web?.resolvedUri || chunk.web?.uri);
        return !allSerpUrls.has(url);
    });

    if (invisibleChunks.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="3" style="text-align:center; padding: 20px;">No "Invisible" citations found. All sources were present in the SERP.</td></tr>';
        return;
    }

    invisibleChunks.forEach(chunk => {
        const resolvedUri = chunk.web?.resolvedUri || chunk.web?.uri;
        const dna = masterBundle.enrichedData ? masterBundle.enrichedData[normalizeUrlKey(resolvedUri)] : null;
        
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${chunk.web?.title || 'Untitled'}</strong></td>
            <td><a href="${resolvedUri}" target="_blank" style="word-break: break-all;">${resolvedUri}</a></td>
            <td>
                ${dna ? `
                    <div style="font-size: 0.75rem; color: #666;">
                        <strong>Intent:</strong> ${dna.primary_intent}<br>
                        <strong>Format:</strong> ${dna.content_format}<br>
                        <strong>Tone:</strong> ${dna.tone}
                    </div>
                ` : '<span style="color: #999;">No DNA Label</span>'}
            </td>
        `;
        tableBody.appendChild(tr);
    });
}

function renderQueryOverlapStats() {
    const container = document.getElementById('queryOverlapStats');
    if (!container || !masterBundle) return;

    const queryPositionCounts = {}; // index -> count
    let totalCitations = 0;

    masterBundle.runs.forEach(run => {
        const chunks = run.groundingChunks || [];
        const queries = run.webSearchQueries || [];
        if (queries.length === 0) return;

        // Map normalized URL to the FIRST query index it appeared in for this run
        const urlToFirstQueryIdx = {};
        queries.forEach((q, idx) => {
            (run.serps[q] || []).forEach(r => {
                const norm = normalizeUrl(r.link);
                if (!(norm in urlToFirstQueryIdx)) {
                    urlToFirstQueryIdx[norm] = idx;
                }
            });
        });

        chunks.forEach(chunk => {
            const url = normalizeUrl(chunk.web?.resolvedUri || chunk.web?.uri);
            totalCitations++;
            const firstIdx = urlToFirstQueryIdx[url];
            if (firstIdx !== undefined) {
                queryPositionCounts[firstIdx] = (queryPositionCounts[firstIdx] || 0) + 1;
            }
        });
    });

    const sortedIndices = Object.keys(queryPositionCounts).map(Number).sort((a, b) => a - b);
    const maxIdx = sortedIndices.length > 0 ? Math.max(...sortedIndices) : 0;

    let html = `
        <div class="overlap-stats-grid" style="grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));">
    `;

    for (let i = 0; i <= Math.max(maxIdx, 2); i++) {
        const count = queryPositionCounts[i] || 0;
        const rate = totalCitations > 0 ? (count / totalCitations * 100) : 0;
        html += `
            <div class="overlap-stat-card">
                <div class="stat-value">${rate.toFixed(1)}%</div>
                <div class="stat-label">Query Q${i + 1}</div>
                <div class="stat-sub">${count} citations</div>
            </div>
        `;
    }

    html += `
        </div>
        <div class="overlap-note" style="margin-top: 15px; font-size: 0.85rem; color: #666;">
            * Attribution is based on the <strong>first</strong> query in the sequence where the cited URL appeared.
        </div>
    `;
    container.innerHTML = html;
}

function renderRankChart() {
    const container = document.getElementById('rankDistributionChart');
    if (!container || !masterBundle || !masterBundle.rankDistribution) return;

    const dist = masterBundle.rankDistribution;
    const maxCount = Math.max(...dist.map(d => d.count));
    
    // Show up to rank 30 or max available
    const displayLimit = Math.min(30, dist.length);
    
    container.innerHTML = `
        <div class="rank-bars-container">
            ${dist.slice(0, displayLimit).map(d => {
                const height = maxCount > 0 ? (d.count / maxCount * 100) : 0;
                return `
                    <div class="rank-bar-wrapper">
                        <div class="rank-bar-value">${d.count}</div>
                        <div class="rank-bar" style="height: ${height}%" title="Rank ${d.rank}: ${d.count} citations (${d.percentage}%)"></div>
                        <div class="rank-label">${d.rank}</div>
                    </div>
                `;
            }).join('')}
        </div>
    `;
}

async function loadBundle() {
    const statusEl = document.getElementById('loadDataBtn');
    if (statusEl) statusEl.textContent = 'Loading...';
    
    try {
        // Use the globally embedded data if available, otherwise fetch
        if (window.EMBEDDED_BUNDLE) {
            masterBundle = window.EMBEDDED_BUNDLE;
            console.log("Using embedded bundle data.");
        } else {
            const response = await fetch('/api/bundle');
            if (!response.ok) throw new Error('Bundle not found.');
            masterBundle = await response.json();
        }
        
        renderRunList();
        
        if (statusEl) {
            statusEl.textContent = 'Data Loaded ✅';
            statusEl.classList.add('success');
        }
    } catch (err) {
        console.error(err);
        if (statusEl) statusEl.textContent = 'Load Failed ❌';
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

    // Collect SERP URLs from all queries for this run (TOP-N for "survival", but we also keep absolute rank)
    const serpMatchesTopN = {}; // normalizedUrl -> { query, absRank, page }
    const serpMatchesAll = {};  // normalizedUrl -> { query, absRank, page }
    Object.entries(run.serps || {}).forEach(([query, results]) => {
        results.forEach((r, idx) => {
            const norm = normalizeUrl(r.link);
            const absRank = idx + 1;
            const page = Math.floor(idx / 10) + 1;
            if (!serpMatchesAll[norm]) serpMatchesAll[norm] = { query, absRank, page };
            if (absRank <= SURVIVAL_TOP_N && !serpMatchesTopN[norm]) serpMatchesTopN[norm] = { query, absRank, page };
        });
    });

    container.innerHTML = chunks.map((chunk, idx) => {
        const rawUri = chunk.web?.uri || '';
        const resolvedUri = chunk.web?.resolvedUri || rawUri;
        const isResolved = resolvedUri !== rawUri;
        
        // Check if this chunk matches TOP-N (survival) and/or any SERP result
        const normalizedChunkUrl = normalizeUrl(resolvedUri);
        const matchTopN = serpMatchesTopN[normalizedChunkUrl];
        const matchAny = serpMatchesAll[normalizedChunkUrl];
        const matchesTopN = !!matchTopN;
        const matchesAny = !!matchAny;

        // DNA DATA
        const dnaRaw = masterBundle.enrichedData ? masterBundle.enrichedData[normalizeUrlKey(resolvedUri)] : null;
        let dnaHtml = '';
        if (dnaRaw) {
            // The DNA data is nested under a 'urls' key in the enrichment response
            const dna = dnaRaw.urls || dnaRaw; 
            dnaHtml = `
                <div class="dna-box">
                    <div class="dna-header"><i class="fas fa-fingerprint"></i> CONTENT DNA</div>
                    <div class="dna-grid">
                        <div class="dna-item"><strong>Type:</strong> ${dna.type || 'N/A'}</div>
                        <div class="dna-item"><strong>Intent:</strong> ${dna.primary_intent || 'N/A'}</div>
                        <div class="dna-item"><strong>Format:</strong> ${dna.content_format || 'N/A'}</div>
                        <div class="dna-item"><strong>Tone:</strong> ${dna.tone || 'N/A'}</div>
                        <div class="dna-item"><strong>Freshness:</strong> ${dna.freshness_cue_strength ? dna.freshness_cue_strength + '/5' : (dna.freshness || 'N/A')}</div>
                    </div>
                    ${dnaRaw.listicle_products && dnaRaw.listicle_products.length > 0 ? `<div class="dna-listicle"><strong>Listicle Products:</strong> ${dnaRaw.listicle_products.length} found</div>` : ''}
                </div>
            `;
        }
        
        return `
            <div class="chunk-card ${matchesTopN ? 'chunk-matched' : ''}">
                <div class="chunk-header">
                    <span class="chunk-index">[${idx}]</span>
                    <span class="chunk-title-text">${chunk.web?.title || 'Untitled Source'}</span>
                    ${
                        matchesTopN
                            ? `<span class="serp-match-badge">IN TOP ${SURVIVAL_TOP_N} ✓ (#${matchTopN.absRank})</span>`
                            : (matchesAny
                                ? `<span class="serp-match-badge serp-match-badge--weak">IN SERP (#${matchAny.absRank})</span>`
                                : `<span class="no-match-badge">NOT IN TOP ${SURVIVAL_TOP_N}</span>`
                              )
                    }
                </div>
                <div class="chunk-url-box">
                    <div class="url-line">
                        <strong>Raw:</strong> <a href="${rawUri}" target="_blank" class="raw-link">${rawUri}</a>
                    </div>
                    <div class="url-line ${isResolved ? 'resolved' : ''}">
                        <strong>Final:</strong> <a href="${resolvedUri}" target="_blank">${resolvedUri}</a>
                        ${isResolved ? '<span class="resolved-tag">RESOLVED</span>' : ''}
                    </div>
                    ${matchesAny ? `
                    <div class="match-details">
                        <i class="fas fa-search"></i> Found in SERP for: <em>"${matchAny.query}"</em> (rank #${matchAny.absRank}, page ${matchAny.page})
                    </div>
                    ` : ''}
                </div>
                ${dnaHtml}
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
                <span class="rank">#${index + 1}</span>
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

function normalizeUrlKey(rawUrl) {
    if (!rawUrl) return "";
    let url = rawUrl.trim();
    if (!url.includes("://")) url = `https://${url}`;
    try {
        const p = new URL(url);
        let host = (p.hostname || "").toLowerCase();
        if (host.startsWith("www.")) host = host.slice(4);
        let pathname = p.pathname || "/";
        if (pathname.length > 1 && pathname.endsWith("/")) pathname = pathname.slice(0, -1);
        const dropExact = new Set(["gclid", "fbclid", "msclkid", "yclid", "mc_cid", "mc_eid", "igshid"]);
        const kept = [];
        for (const [k, v] of p.searchParams.entries()) {
            const lk = k.toLowerCase();
            if (lk.startsWith("utm_") || dropExact.has(lk)) continue;
            kept.push([k, v]);
        }
        const q = new URLSearchParams(kept).toString();
        return `${host}${pathname}${q ? `?${q}` : ""}`;
    } catch {
        return rawUrl.toLowerCase();
    }
}
