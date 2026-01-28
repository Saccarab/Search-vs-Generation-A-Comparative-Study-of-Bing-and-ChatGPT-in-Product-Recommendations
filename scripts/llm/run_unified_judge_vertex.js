const fs = require('fs');
const path = require('path');
const { VertexAI } = require('@google-cloud/vertexai');

// --- CONFIGURATION ---
const PROJECT_ID = process.env.GCP_PROJECT_ID || 'YOUR_PROJECT_ID';
const LOCATION = 'us-central1';
const DNA_MODEL = 'gemini-2.5-flash-preview';  // 2.5 Flash - no thinking for classification
const AUDIT_MODEL = 'gemini-2.5-flash-preview'; // 2.5 Flash - WITH thinking for semantic matching

const MASTER_JSON = 'data/ingest/gemini_urls_master.json';
const RESPONSES_DIR = 'data/gemini_raw_responses';
const RESOLVED_URLS = 'data/resolved_grounding_urls.json';
const OUTPUT_DNA = 'data/llm/page_dna_results.json';
const OUTPUT_AUDIT = 'data/llm/semantic_audit_results.json';

// Initialize Vertex AI
const vertexAI = new VertexAI({ project: PROJECT_ID, location: LOCATION });

// --- JSON SCHEMAS FOR STRUCTURED OUTPUT ---

const DNA_SCHEMA = {
    type: "object",
    properties: {
        page_type: {
            type: "string",
            enum: ["listicle", "product_page", "review", "forum", "news", "homepage", "other"]
        },
        tone: {
            type: "string",
            enum: ["promotional", "informational", "neutral", "salesy"]
        },
        structure: {
            type: "string",
            enum: ["table", "numbered_list", "bullet_list", "paragraphs", "mixed"]
        },
        has_pros_cons: { type: "boolean" },
        has_pricing_info: { type: "boolean" },
        has_author_byline: { type: "boolean" },
        estimated_word_count: { type: "integer" }
    },
    required: ["page_type", "tone", "structure"]
};

const AUDIT_SCHEMA = {
    type: "object",
    properties: {
        verifications: {
            type: "array",
            items: {
                type: "object",
                properties: {
                    claim_index: { type: "integer" },
                    is_supported: { type: "boolean" },
                    source_footprint: { type: "string", description: "Exact text from source page" },
                    confidence: { type: "integer", minimum: 0, maximum: 100 }
                },
                required: ["claim_index", "is_supported", "source_footprint", "confidence"]
            }
        }
    },
    required: ["verifications"]
};

// --- MAIN LOGIC ---

async function runUnifiedJudge() {
    console.log('⚖️ Unified Judge (Vertex AI + Structured Output)');
    console.log(`   DNA Model: ${DNA_MODEL} (no thinking)`);
    console.log(`   Audit Model: ${AUDIT_MODEL} (with thinking, budget: 2048)`);
    console.log(`   Project: ${PROJECT_ID}\n`);

    // Ensure output directories exist
    fs.mkdirSync('data/llm', { recursive: true });

    const masterData = JSON.parse(fs.readFileSync(MASTER_JSON, 'utf-8'));
    const resolvedUrls = fs.existsSync(RESOLVED_URLS) 
        ? JSON.parse(fs.readFileSync(RESOLVED_URLS, 'utf-8')) 
        : {};

    // Collect unique URLs and claims grouped by URL
    const uniqueUrls = new Set();
    const pageClaims = {}; // { url: [{ runId, text }] }

    const files = fs.readdirSync(RESPONSES_DIR).filter(f => {
        const pNum = parseInt(f.split('_')[0].replace('P', ''));
        return pNum >= 4 && pNum <= 7 && f.endsWith('.json');
    });

    // Deduplicate to latest file per runId
    const latestFiles = {};
    files.forEach(f => {
        const runId = f.split('_').slice(0, 2).join('_');
        if (!latestFiles[runId] || f > latestFiles[runId]) {
            latestFiles[runId] = f;
        }
    });

    Object.values(latestFiles).forEach(file => {
        const runId = file.split('_').slice(0, 2).join('_');
        const content = JSON.parse(fs.readFileSync(path.join(RESPONSES_DIR, file), 'utf-8'));
        const supports = content.groundingMetadata?.groundingSupports || [];
        const chunks = content.groundingMetadata?.groundingChunks || [];

        supports.forEach(support => {
            (support.groundingChunkIndices || []).forEach(cIdx => {
                const rawUri = chunks[cIdx]?.web?.uri;
                const finalUri = resolvedUrls[rawUri] || rawUri;
                uniqueUrls.add(finalUri);

                if (!pageClaims[finalUri]) pageClaims[finalUri] = [];
                pageClaims[finalUri].push({
                    runId,
                    text: support.segment?.text
                });
            });
        });
    });

    console.log(`📊 Found ${uniqueUrls.size} unique URLs with ${Object.values(pageClaims).flat().length} total claims.\n`);

    // ========== STAGE 1: DNA ENRICHMENT ==========
    console.log('🧬 STAGE 1: Page DNA Enrichment...');
    const dnaResults = fs.existsSync(OUTPUT_DNA) 
        ? JSON.parse(fs.readFileSync(OUTPUT_DNA, 'utf-8')) 
        : {};

    let dnaCount = 0;
    for (const url of uniqueUrls) {
        if (dnaResults[url]) {
            console.log(`   ⏭️ Skipping (cached): ${url.substring(0, 50)}`);
            continue;
        }

        const page = masterData[url];
        if (!page || page.status !== 'success') continue;

        const pageText = fs.readFileSync(page.content_path, 'utf-8');
        console.log(`   [${++dnaCount}] Enriching: ${url.substring(0, 50)}...`);

        try {
            const dna = await callDnaModel(
                `Analyze this webpage and classify its characteristics.\n\nWEBPAGE TEXT:\n"""\n${pageText.substring(0, 25000)}\n"""`,
                DNA_SCHEMA
            );
            dnaResults[url] = dna;
            fs.writeFileSync(OUTPUT_DNA, JSON.stringify(dnaResults, null, 2));
        } catch (e) {
            console.error(`   ❌ Error: ${e.message}`);
            dnaResults[url] = { error: e.message };
        }

        await sleep(500); // Small delay between calls
    }

    // ========== STAGE 2: SEMANTIC AUDIT ==========
    console.log('\n⚖️ STAGE 2: Semantic Footprint Matching...');
    const auditResults = fs.existsSync(OUTPUT_AUDIT)
        ? JSON.parse(fs.readFileSync(OUTPUT_AUDIT, 'utf-8'))
        : [];

    const processedKeys = new Set(auditResults.map(r => r.url));

    for (const [url, claims] of Object.entries(pageClaims)) {
        if (processedKeys.has(url)) {
            console.log(`   ⏭️ Skipping (cached): ${url.substring(0, 50)}`);
            continue;
        }

        const page = masterData[url];
        if (!page || page.status !== 'success') continue;

        const pageText = fs.readFileSync(page.content_path, 'utf-8');
        const claimTexts = claims.map((c, i) => `${i + 1}. "${c.text}"`).join('\n');

        console.log(`   Auditing ${claims.length} claims for: ${url.substring(0, 50)}...`);

        try {
            const audit = await callAuditModel(
                `STRICT VERIFICATION TASK:
Find the EXACT text in the SOURCE PAGE that supports each AI CLAIM below.

RULES:
- "source_footprint" MUST be a verbatim or near-verbatim excerpt from the SOURCE PAGE.
- If a claim is NOT supported by the text, set "is_supported" to false and "source_footprint" to empty string.
- Do NOT summarize. Extract the actual text.

SOURCE PAGE:
"""
${pageText.substring(0, 25000)}
"""

AI CLAIMS TO VERIFY:
${claimTexts}`,
                AUDIT_SCHEMA
            );

            auditResults.push({
                url,
                claims: claims.map(c => ({ runId: c.runId, text: c.text })),
                ...audit
            });
            fs.writeFileSync(OUTPUT_AUDIT, JSON.stringify(auditResults, null, 2));
        } catch (e) {
            console.error(`   ❌ Error: ${e.message}`);
        }

        await sleep(500);
    }

    console.log('\n✨ Unified Judge complete!');
    console.log(`   DNA Results: ${OUTPUT_DNA}`);
    console.log(`   Audit Results: ${OUTPUT_AUDIT}`);
}

// --- VERTEX AI HELPERS ---

// DNA Enrichment: No thinking needed (simple classification)
async function callDnaModel(prompt, schema) {
    const generativeModel = vertexAI.getGenerativeModel({
        model: DNA_MODEL,
        generationConfig: {
            responseMimeType: "application/json",
            responseSchema: schema
        }
    });

    const result = await generativeModel.generateContent({
        contents: [{ role: 'user', parts: [{ text: prompt }] }]
    });

    const responseText = result.response.candidates[0].content.parts[0].text;
    return JSON.parse(responseText);
}

// Semantic Audit: 2.5 Flash with thinking enabled for precision matching
async function callAuditModel(prompt, schema) {
    const generativeModel = vertexAI.getGenerativeModel({
        model: AUDIT_MODEL,
        generationConfig: {
            responseMimeType: "application/json",
            responseSchema: schema,
            thinkingConfig: {
                thinkingBudget: 2048  // Enable thinking for careful verification
            }
        }
    });

    const result = await generativeModel.generateContent({
        contents: [{ role: 'user', parts: [{ text: prompt }] }]
    });

    const responseText = result.response.candidates[0].content.parts[0].text;
    return JSON.parse(responseText);
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// --- RUN ---
runUnifiedJudge().catch(console.error);
