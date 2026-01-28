import fs from 'fs';
import path from 'path';

const RAW_RESPONSES_DIR = 'datapass/raw_network_responses';
const OUTPUT_DIR = 'datapass/citation_mappings';
const ENTERPRISE_CSV = 'datapass/chatgpt_results_2026-01-27T11-23-04-enterprise.csv';
const PERSONAL_CSV = 'datapass/personal_data_run/chatgpt_results_2026-01-28T02-25-34.csv';

// Ensure output directory exists
if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

/**
 * Parse content_references_json to extract citation mappings
 * 
 * Strategy: 
 * 1. Find ALL [URL] tags in response_text and assign each a sequential index
 * 2. For each URL, extract the claim text (text between previous URL and this one)
 * 3. Match citation tokens to URLs based on position proximity
 * 4. Enrich with source metadata from search_result_groups
 */
function parseContentReferences(contentRefsJson, responseText, searchResultGroups) {
    if (!contentRefsJson) return [];
    
    let refs;
    try {
        refs = typeof contentRefsJson === 'string' ? JSON.parse(contentRefsJson) : contentRefsJson;
    } catch (e) {
        console.error('Failed to parse content_references_json:', e.message);
        return [];
    }
    
    if (!Array.isArray(refs)) return [];
    
    // Build ref_index -> source mapping from search_result_groups
    const refIndexMap = buildRefIndexMap(searchResultGroups);
    
    // Step 1: Find ALL [URL] positions in the response_text (ordered by position)
    const urlPositions = [];
    const urlRegex = /\[(https?:\/\/[^\]\s]+)\]/g;
    let match;
    while ((match = urlRegex.exec(responseText)) !== null) {
        urlPositions.push({
            url: match[1],
            start: match.index,
            end: match.index + match[0].length,
            fullMatch: match[0],
            index: urlPositions.length
        });
    }
    
    // Step 2: Pre-compute claim text for each URL position
    for (let i = 0; i < urlPositions.length; i++) {
        const currentUrlPos = urlPositions[i];
        let blockStart = 0;
        if (i > 0) {
            blockStart = urlPositions[i - 1].end;
        }
        
        let claimText = responseText.substring(blockStart, currentUrlPos.start);
        claimText = claimText
            .replace(/^\s*\]\s*/, '')
            .replace(/\s*\[$/, '')
            .replace(/^\s+/, '')
            .replace(/\s+$/, '')
            .replace(/\n+/g, ' ')
            .replace(/\s{2,}/g, ' ')
            .trim();
        
        urlPositions[i].claimText = claimText;
    }
    
    // Step 3: Process each citation token
    const citations = [];
    const usedUrlIndices = new Set(); // Track which URLs have been assigned
    
    for (const ref of refs) {
        if (typeof ref !== 'object' || ref === null) continue;
        if (ref.type === 'sources_footnote') continue;
        if (typeof ref.start_idx !== 'number') continue;
        
        const citation = {
            token_position: {
                start_idx: ref.start_idx,
                end_idx: ref.end_idx || ref.start_idx
            },
            citation_token: ref.matched_text || '',
            type: ref.type || 'unknown',
            sources: []
        };
        
        // Parse ref indices
        const refIndices = extractRefIndices(ref.matched_text);
        
        // Map to sources from search_result_groups
        for (const idx of refIndices) {
            const key = `${idx.turn_index}_${idx.ref_type}_${idx.ref_index}`;
            if (refIndexMap[key]) {
                citation.sources.push({
                    ...refIndexMap[key],
                    ref_key: key
                });
            }
        }
        
        // Check for direct items
        if (ref.items && Array.isArray(ref.items)) {
            for (const item of ref.items) {
                citation.sources.push({
                    url: item.url,
                    title: item.title,
                    snippet: item.snippet,
                    domain: item.attribution || item.domain,
                    ref_type: 'direct_item'
                });
            }
        }
        
        // Step 4: Find the best matching URL for this citation
        if (responseText && urlPositions.length > 0) {
            const targetUrls = citation.sources.map(s => s.url).filter(Boolean);
            
            let bestUrlIdx = -1;
            let bestScore = -Infinity;
            
            for (let i = 0; i < urlPositions.length; i++) {
                const pos = urlPositions[i];
                
                // Calculate a score based on:
                // 1. URL match (highest priority)
                // 2. Position proximity
                // 3. Penalty for already-used URLs
                
                let score = 0;
                const dist = Math.abs(pos.start - ref.start_idx);
                
                // Check URL match
                const normalizedPosUrl = pos.url.replace(/https?:\/\/(www\.)?/, '').split('?')[0].replace(/\/$/, '');
                let urlMatched = false;
                
                for (const targetUrl of targetUrls) {
                    const normalizedTarget = targetUrl.replace(/https?:\/\/(www\.)?/, '').split('?')[0].replace(/\/$/, '');
                    if (normalizedPosUrl === normalizedTarget || 
                        normalizedPosUrl.includes(normalizedTarget) || 
                        normalizedTarget.includes(normalizedPosUrl)) {
                        urlMatched = true;
                        score += 10000; // High bonus for URL match
                        break;
                    }
                }
                
                // Position score (inverse of distance, max 1000 points)
                score += Math.max(0, 1000 - dist);
                
                // Penalty for used URLs (prefer unused ones)
                if (usedUrlIndices.has(i)) {
                    score -= 500;
                }
                
                if (score > bestScore) {
                    bestScore = score;
                    bestUrlIdx = i;
                }
            }
            
            if (bestUrlIdx !== -1) {
                const bestUrl = urlPositions[bestUrlIdx];
                citation.inline_url = bestUrl.url;
                citation.url_position = bestUrl.start;
                citation.claim_text = bestUrl.claimText;
                citation.url_index = bestUrlIdx;
                usedUrlIndices.add(bestUrlIdx);
            }
        }
        
        if (citation.claim_text || citation.sources.length > 0 || citation.citation_token || citation.inline_url) {
            citations.push(citation);
        }
    }
    
    return citations;
}

/**
 * Extract ref_indices from matched_text like "citeturn0search0turn0search2"
 * Returns array of {turn_index, ref_type, ref_index}
 */
function extractRefIndices(matchedText) {
    if (!matchedText) return [];
    
    const indices = [];
    // Pattern: turn<N>search<M> or turn<N>news<M> or turn<N>academia<M>
    const pattern = /turn(\d+)(search|news|academia)(\d+)/g;
    let match;
    
    while ((match = pattern.exec(matchedText)) !== null) {
        indices.push({
            turn_index: parseInt(match[1]),
            ref_type: match[2],
            ref_index: parseInt(match[3])
        });
    }
    
    return indices;
}

/**
 * Build a map from "turn_ref_type_ref_index" -> source info from search_result_groups
 */
function buildRefIndexMap(searchResultGroupsJson) {
    const map = {};
    
    if (!searchResultGroupsJson) return map;
    
    let groups;
    try {
        groups = typeof searchResultGroupsJson === 'string' 
            ? JSON.parse(searchResultGroupsJson) 
            : searchResultGroupsJson;
    } catch (e) {
        return map;
    }
    
    if (!Array.isArray(groups)) return map;
    
    for (const group of groups) {
        // Handle grouped entries
        if (group.entries && Array.isArray(group.entries)) {
            for (const entry of group.entries) {
                if (entry.ref_id) {
                    const key = `${entry.ref_id.turn_index}_${entry.ref_id.ref_type}_${entry.ref_id.ref_index}`;
                    map[key] = {
                        url: entry.url,
                        title: entry.title,
                        snippet: entry.snippet,
                        domain: entry.attribution || group.domain,
                        ref_type: entry.ref_id.ref_type,
                        ref_index: entry.ref_id.ref_index,
                        turn_index: entry.ref_id.turn_index,
                        pub_date: entry.pub_date
                    };
                }
            }
        }
        
        // Handle direct search_result type entries at group level
        if (group.ref_id && group.type === 'search_result') {
            const key = `${group.ref_id.turn_index}_${group.ref_id.ref_type}_${group.ref_id.ref_index}`;
            map[key] = {
                url: group.url,
                title: group.title,
                snippet: group.snippet,
                domain: group.attribution,
                ref_type: group.ref_id.ref_type,
                ref_index: group.ref_id.ref_index,
                turn_index: group.ref_id.turn_index,
                pub_date: group.pub_date
            };
        }
    }
    
    return map;
}

/**
 * Parse raw enterprise websocket stream to extract structured data
 */
function parseRawStream(rawJson) {
    let events;
    try {
        events = typeof rawJson === 'string' ? JSON.parse(rawJson) : rawJson;
    } catch (e) {
        return null;
    }
    
    if (!Array.isArray(events)) return null;
    
    const result = {
        search_result_groups: [],
        content_references: [],
        response_text: '',
        sonic_classification: null,
        hidden_queries: []
    };
    
    for (const event of events) {
        if (typeof event !== 'object' || event === null) continue;
        
        // Look for message objects with metadata
        if (event.v?.message?.metadata) {
            const meta = event.v.message.metadata;
            
            // Search result groups
            if (meta.search_result_groups) {
                result.search_result_groups = meta.search_result_groups;
            }
            
            // Content references
            if (meta.content_references) {
                result.content_references = meta.content_references;
            }
            
            // Sonic classification
            if (meta.sonic_classification_result) {
                result.sonic_classification = meta.sonic_classification_result;
            }
            
            // Hidden queries
            if (meta.search_model_queries?.queries) {
                result.hidden_queries = meta.search_model_queries.queries;
            }
        }
        
        // Look for response text in message content
        if (event.v?.message?.content?.parts) {
            const text = event.v.message.content.parts.join('');
            if (text.length > result.response_text.length) {
                result.response_text = text;
            }
        }
        
        // Handle patch operations that append to content
        if (event.p?.includes('/message/content/parts/0') && event.o === 'append') {
            result.response_text += event.v || '';
        }
    }
    
    return result;
}

/**
 * Process a single run and create the mapping output
 */
function processRun(data, runId, accountType) {
    const output = {
        run_id: runId,
        account_type: accountType,
        prompt: data.query || data.prompt || '',
        metadata: {
            hidden_queries: [],
            sonic_classification: null,
            web_search_triggered: false,
            web_search_forced: false,
            generated_search_query: data.generated_search_query || ''
        },
        citation_mappings: [],
        source_summary: {
            cited: [],
            additional: [],
            total_cited: 0,
            total_additional: 0,
            total_all: 0
        }
    };
    
    // Parse hidden queries
    try {
        output.metadata.hidden_queries = data.hidden_queries_json 
            ? JSON.parse(data.hidden_queries_json) 
            : (data.hidden_queries || []);
    } catch (e) {
        output.metadata.hidden_queries = [];
    }
    
    // Parse sonic classification
    try {
        output.metadata.sonic_classification = data.sonic_classification_json 
            ? JSON.parse(data.sonic_classification_json) 
            : (data.sonic_classification || null);
    } catch (e) {
        output.metadata.sonic_classification = null;
    }
    
    output.metadata.web_search_triggered = data.web_search_triggered === 'true' || data.web_search_triggered === true;
    output.metadata.web_search_forced = data.web_search_forced === 'true' || data.web_search_forced === true;
    
    // Get response text
    const responseText = data.response_text || '';
    
    // Parse search result groups
    let searchResultGroups = null;
    try {
        searchResultGroups = data.search_result_groups_json 
            ? JSON.parse(data.search_result_groups_json) 
            : (data.search_result_groups || null);
    } catch (e) {}
    
    // Parse content references and create mappings
    const contentRefs = data.content_references_json || data.content_references || '[]';
    output.citation_mappings = parseContentReferences(contentRefs, responseText, data.search_result_groups_json);
    
    // Parse sources
    try {
        const cited = data.sources_cited_json ? JSON.parse(data.sources_cited_json) : [];
        output.source_summary.cited = cited.map(s => ({
            url: s.url,
            title: s.title,
            domain: s.domain
        }));
        output.source_summary.total_cited = cited.length;
    } catch (e) {}
    
    try {
        const additional = data.sources_additional_json ? JSON.parse(data.sources_additional_json) : [];
        output.source_summary.additional = additional.map(s => ({
            url: s.url,
            title: s.title,
            domain: s.domain
        }));
        output.source_summary.total_additional = additional.length;
    } catch (e) {}
    
    try {
        const all = data.sources_all_json ? JSON.parse(data.sources_all_json) : [];
        output.source_summary.total_all = all.length;
    } catch (e) {}
    
    // Add response text length stats
    output.response_stats = {
        total_length: responseText.length,
        citation_count: output.citation_mappings.length,
        chars_with_citations: output.citation_mappings.reduce((sum, c) => {
            const pos = c.token_position || {};
            return sum + ((pos.end_idx || 0) - (pos.start_idx || 0));
        }, 0)
    };
    
    return output;
}

/**
 * Load CSV and parse into rows
 */
function loadCSV(filepath) {
    if (!fs.existsSync(filepath)) return [];
    
    const content = fs.readFileSync(filepath, 'utf-8');
    const lines = content.split('\n');
    if (lines.length < 2) return [];
    
    const headers = parseCSVLine(lines[0]);
    const rows = [];
    
    for (let i = 1; i < lines.length; i++) {
        if (!lines[i].trim()) continue;
        const values = parseCSVLine(lines[i]);
        const row = {};
        headers.forEach((h, idx) => {
            row[h] = values[idx] || '';
        });
        rows.push(row);
    }
    
    return rows;
}

/**
 * Parse a CSV line handling quoted fields
 */
function parseCSVLine(line) {
    const result = [];
    let current = '';
    let inQuotes = false;
    
    for (let i = 0; i < line.length; i++) {
        const char = line[i];
        
        if (char === '"') {
            if (inQuotes && line[i + 1] === '"') {
                current += '"';
                i++;
            } else {
                inQuotes = !inQuotes;
            }
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

// Main execution
async function main() {
    console.log('📊 Extracting citation mappings from all runs...\n');
    
    const allMappings = [];
    
    // Process personal data from JSON files (already structured)
    console.log('Processing personal data...');
    const personalFiles = fs.readdirSync(RAW_RESPONSES_DIR)
        .filter(f => f.endsWith('_personal.json'));
    
    for (const file of personalFiles) {
        const filepath = path.join(RAW_RESPONSES_DIR, file);
        const runId = file.replace('_personal.json', '').replace('.json', '');
        
        try {
            const data = JSON.parse(fs.readFileSync(filepath, 'utf-8'));
            const mapping = processRun(data, runId, 'personal');
            allMappings.push(mapping);
            
            // Save individual file
            const outputPath = path.join(OUTPUT_DIR, `${runId}_personal_mapping.json`);
            fs.writeFileSync(outputPath, JSON.stringify(mapping, null, 2));
        } catch (e) {
            console.error(`  Failed to process ${file}:`, e.message);
        }
    }
    console.log(`  Processed ${personalFiles.length} personal runs`);
    
    // Process enterprise data from JSON files (raw stream) or CSV
    console.log('\nProcessing enterprise data...');
    const enterpriseFiles = fs.readdirSync(RAW_RESPONSES_DIR)
        .filter(f => f.endsWith('.json') && !f.includes('_personal'));
    
    // Also load enterprise CSV for structured data
    const enterpriseCSVData = loadCSV(ENTERPRISE_CSV);
    const csvByRunId = {};
    for (const row of enterpriseCSVData) {
        const runId = `P${String(row.query_index).padStart(3, '0')}_r${row.run_number}`;
        csvByRunId[runId] = row;
    }
    
    for (const file of enterpriseFiles) {
        const filepath = path.join(RAW_RESPONSES_DIR, file);
        const runId = file.replace('.json', '');
        
        try {
            const rawContent = fs.readFileSync(filepath, 'utf-8');
            
            // Try to use CSV data first (more reliable parsed data)
            if (csvByRunId[runId]) {
                const mapping = processRun(csvByRunId[runId], runId, 'enterprise');
                allMappings.push(mapping);
                
                const outputPath = path.join(OUTPUT_DIR, `${runId}_enterprise_mapping.json`);
                fs.writeFileSync(outputPath, JSON.stringify(mapping, null, 2));
            } else {
                // Fall back to parsing raw stream
                const parsed = parseRawStream(rawContent);
                if (parsed) {
                    const data = {
                        search_result_groups_json: JSON.stringify(parsed.search_result_groups),
                        content_references_json: JSON.stringify(parsed.content_references),
                        response_text: parsed.response_text,
                        sonic_classification_json: JSON.stringify(parsed.sonic_classification),
                        hidden_queries_json: JSON.stringify(parsed.hidden_queries)
                    };
                    const mapping = processRun(data, runId, 'enterprise');
                    allMappings.push(mapping);
                    
                    const outputPath = path.join(OUTPUT_DIR, `${runId}_enterprise_mapping.json`);
                    fs.writeFileSync(outputPath, JSON.stringify(mapping, null, 2));
                }
            }
        } catch (e) {
            console.error(`  Failed to process ${file}:`, e.message);
        }
    }
    console.log(`  Processed ${enterpriseFiles.length} enterprise runs`);
    
    // Create summary file
    const summary = {
        generated_at: new Date().toISOString(),
        total_runs: allMappings.length,
        by_account_type: {
            enterprise: allMappings.filter(m => m.account_type === 'enterprise').length,
            personal: allMappings.filter(m => m.account_type === 'personal').length
        },
        aggregate_stats: {
            total_citations: allMappings.reduce((sum, m) => sum + m.citation_mappings.length, 0),
            avg_citations_per_run: (allMappings.reduce((sum, m) => sum + m.citation_mappings.length, 0) / allMappings.length).toFixed(2),
            total_cited_sources: allMappings.reduce((sum, m) => sum + m.source_summary.total_cited, 0),
            total_additional_sources: allMappings.reduce((sum, m) => sum + m.source_summary.total_additional, 0)
        },
        runs: allMappings.map(m => ({
            run_id: m.run_id,
            account_type: m.account_type,
            citation_count: m.citation_mappings.length,
            cited_sources: m.source_summary.total_cited,
            web_search_triggered: m.metadata.web_search_triggered
        }))
    };
    
    fs.writeFileSync(
        path.join(OUTPUT_DIR, '_summary.json'),
        JSON.stringify(summary, null, 2)
    );
    
    // Also save all mappings in one file
    fs.writeFileSync(
        path.join(OUTPUT_DIR, '_all_mappings.json'),
        JSON.stringify(allMappings, null, 2)
    );
    
    console.log(`\n✅ Done! Output saved to ${OUTPUT_DIR}/`);
    console.log(`   - ${allMappings.length} individual mapping files`);
    console.log(`   - _summary.json (aggregate stats)`);
    console.log(`   - _all_mappings.json (combined data)`);
    console.log(`\n📈 Summary:`);
    console.log(`   Total citations extracted: ${summary.aggregate_stats.total_citations}`);
    console.log(`   Avg citations per run: ${summary.aggregate_stats.avg_citations_per_run}`);
}

main().catch(console.error);
