(function() {
    console.log('[Interceptor] ChatGPT API Interceptor Active (Full Capture Mode)');

    // Store for intercepted data - will be posted to content script when stream ends
    let currentInterceptedData = null;

    function createEmptyInterceptedData() {
        return {
            search_model_queries: [],
            search_result_groups: [],
            content_references: [],
            sonic_classification_result: null,
            raw_messages: [] // Store ALL raw messages for full forensics
        };
    }

    function processChunk(chunk, interceptedData) {
        const lines = chunk.split('\n');
        for (const line of lines) {
            if (line.startsWith('data: ') && line !== 'data: [DONE]') {
                try {
                    const jsonStr = line.substring(6);
                    if (!jsonStr.trim()) continue;
                    
                    const json = JSON.parse(jsonStr);
                    
                    // Store EVERY raw message (no filter)
                    interceptedData.raw_messages.push(json);

                    // Extract from standard message format
                    const meta = json.message?.metadata;
                    if (meta) {
                        // Capture sonic_classification_result (search decision data)
                        if (meta.sonic_classification_result && !interceptedData.sonic_classification_result) {
                            interceptedData.sonic_classification_result = meta.sonic_classification_result;
                            console.log('[Interceptor] Captured sonic_classification_result:', meta.sonic_classification_result);
                        }
                        
                        if (meta.search_model_queries?.queries) {
                            const queries = meta.search_model_queries.queries;
                            for (const q of queries) {
                                if (!interceptedData.search_model_queries.includes(q)) {
                                    interceptedData.search_model_queries.push(q);
                                }
                            }
                        }
                        if (meta.search_result_groups) {
                            interceptedData.search_result_groups.push(...meta.search_result_groups);
                        }
                        if (meta.content_references) {
                            interceptedData.content_references.push(...meta.content_references);
                        }
                    }

                    // Handle patch format: {"p": "/path", "o": "append", "v": [...]}
                    if (json.p && json.v !== undefined) {
                        const path = json.p;
                        const value = json.v;
                        
                        if (path.includes('search_model_queries') && value?.queries) {
                            for (const q of value.queries) {
                                if (!interceptedData.search_model_queries.includes(q)) {
                                    interceptedData.search_model_queries.push(q);
                                }
                            }
                        }
                        if (path.includes('search_result_groups') && value) {
                            const groups = Array.isArray(value) ? value : [value];
                            interceptedData.search_result_groups.push(...groups);
                        }
                        if (path.includes('content_references') && value) {
                            const refs = Array.isArray(value) ? value : [value];
                            interceptedData.content_references.push(...refs);
                        }
                    }
                    
                    // Extract from delta/patch format (json.v)
                    if (json.v) {
                        // v can be an object with message.metadata
                        if (json.v.message?.metadata) {
                            const vMeta = json.v.message.metadata;
                            
                            // Capture sonic_classification_result from nested format
                            if (vMeta.sonic_classification_result && !interceptedData.sonic_classification_result) {
                                interceptedData.sonic_classification_result = vMeta.sonic_classification_result;
                                console.log('[Interceptor] Captured sonic_classification_result (nested):', vMeta.sonic_classification_result);
                            }
                            
                            if (vMeta.search_model_queries?.queries) {
                                for (const q of vMeta.search_model_queries.queries) {
                                    if (!interceptedData.search_model_queries.includes(q)) {
                                        interceptedData.search_model_queries.push(q);
                                    }
                                }
                            }
                            if (vMeta.search_result_groups) {
                                interceptedData.search_result_groups.push(...vMeta.search_result_groups);
                            }
                            if (vMeta.content_references) {
                                interceptedData.content_references.push(...vMeta.content_references);
                            }
                        }
                        
                        // v can also be an array of patches (nested format)
                        if (Array.isArray(json.v)) {
                            for (const patch of json.v) {
                                // Check patch path for relevant data
                                const path = patch.p || '';
                                const value = patch.v;
                                
                                if (path && value !== undefined) {
                                    if (path.includes('search_model_queries') && value?.queries) {
                                        for (const q of value.queries) {
                                            if (!interceptedData.search_model_queries.includes(q)) {
                                                interceptedData.search_model_queries.push(q);
                                            }
                                        }
                                    }
                                    if (path.includes('search_result_groups') && value) {
                                        const groups = Array.isArray(value) ? value : [value];
                                        interceptedData.search_result_groups.push(...groups);
                                    }
                                    if (path.includes('content_references') && value) {
                                        const refs = Array.isArray(value) ? value : [value];
                                        interceptedData.content_references.push(...refs);
                                    }
                                }
                                
                                // Also check nested metadata in patches
                                if (patch.v?.metadata) {
                                    const pMeta = patch.v.metadata;
                                    
                                    if (pMeta.sonic_classification_result && !interceptedData.sonic_classification_result) {
                                        interceptedData.sonic_classification_result = pMeta.sonic_classification_result;
                                    }
                                    
                                    if (pMeta.search_model_queries?.queries) {
                                        for (const q of pMeta.search_model_queries.queries) {
                                            if (!interceptedData.search_model_queries.includes(q)) {
                                                interceptedData.search_model_queries.push(q);
                                            }
                                        }
                                    }
                                    if (pMeta.search_result_groups) {
                                        interceptedData.search_result_groups.push(...pMeta.search_result_groups);
                                    }
                                    if (pMeta.content_references) {
                                        interceptedData.content_references.push(...pMeta.content_references);
                                    }
                                }
                            }
                        }
                    }
                } catch (e) {
                    // Skip malformed JSON chunks
                }
            }
        }
    }

    // Hook the global fetch
    const originalFetch = window.fetch;
    window.fetch = async function(...args) {
        const url = args[0] ? (typeof args[0] === 'string' ? args[0] : args[0].url) : '';
        
        // Call original fetch
        const response = await originalFetch.apply(this, args);
        
        // Only intercept conversation API calls (can be /backend-api/conversation or /backend-api/f/conversation)
        if (url.includes('/backend-api/') && url.includes('/conversation')) {
            console.log('[Interceptor] Intercepting conversation request:', url);
            
            // Create fresh data store for this conversation
            const interceptedData = createEmptyInterceptedData();
            
            // Clone the response so we can read it without affecting the original consumer
            const clonedResponse = response.clone();
            
            // Process the stream in the background
            (async () => {
                try {
                    const reader = clonedResponse.body.getReader();
                    const decoder = new TextDecoder();
                    let buffer = '';
                    
                    while (true) {
                        const { done, value } = await reader.read();
                        
                        if (done) {
                            // Process any remaining buffer
                            if (buffer.trim()) {
                                processChunk(buffer, interceptedData);
                            }
                            
                            console.log('[Interceptor] Stream complete. Extracted data:', {
                                queries: interceptedData.search_model_queries,
                                result_groups: interceptedData.search_result_groups.length,
                                content_refs: interceptedData.content_references.length,
                                sonic_classification: interceptedData.sonic_classification_result ? 'captured' : 'none',
                                raw_messages_count: interceptedData.raw_messages.length
                            });
                            
                            // Only post if we have meaningful data (at least one of: queries, result_groups, content_refs, or sonic_classification)
                            const hasMeaningfulData = 
                                interceptedData.search_model_queries.length > 0 ||
                                interceptedData.search_result_groups.length > 0 ||
                                interceptedData.content_references.length > 0 ||
                                interceptedData.sonic_classification_result !== null;
                            
                            if (hasMeaningfulData) {
                                console.log('[Interceptor] Posting full data to content script');
                                window.postMessage({
                                    type: 'CHATGPT_API_INTERCEPT',
                                    payload: {
                                        search_model_queries: interceptedData.search_model_queries,
                                        search_result_groups: interceptedData.search_result_groups,
                                        content_references: interceptedData.content_references,
                                        sonic_classification_result: interceptedData.sonic_classification_result,
                                        raw_messages: interceptedData.raw_messages
                                    }
                                }, '*');
                            }
                            
                            break;
                        }
                        
                        // Decode chunk and add to buffer
                        buffer += decoder.decode(value, { stream: true });
                        
                        // Process complete lines
                        const lines = buffer.split('\n');
                        buffer = lines.pop() || ''; // Keep incomplete line in buffer
                        
                        for (const line of lines) {
                            if (line.trim()) {
                                processChunk(line + '\n', interceptedData);
                            }
                        }
                    }
                } catch (e) {
                    console.error('[Interceptor] Error reading stream:', e);
                }
            })();
        }
        
        return response;
    };

    console.log('[Interceptor] Fetch hook installed (Full Capture Mode)');
})();
