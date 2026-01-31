/**
 * Vertex AI version of the enrichment pipeline.
 * 
 * What it does:
 * - Reads unique URLs from geo_fresh.db (Cited, Additional, Rejected).
 * - Skips URLs already successfully labeled in datapass/page_labels_gemini.jsonl.
 * - Loads local content from data/fetched_content/ (<hash>.txt and <hash>.json).
 * - Calls Vertex AI (Gemini) with prompts/page_label_prompt_v1.txt.
 * - Appends results to datapass/page_labels_gemini.jsonl.
 * 
 * API Auth: Uses Google Cloud Application Default Credentials (ADC) or env vars.
 *   GCP_PROJECT_ID, GCP_LOCATION (default: us-central1)
 */

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const Bottleneck = require("bottleneck");
const sqlite3 = require("sqlite3");
const { promisify } = require("util");
const { VertexAI } = require("@google-cloud/vertexai");

// --- CONFIGURATION ---
const CONFIG = {
    dbPath: 'geo_fresh.db',
    jsonlPath: 'datapass/page_labels_gemini_v2.5.jsonl',
    contentDir: 'data/fetched_content',
    promptPath: 'prompts/page_label_prompt_v1.txt',
    projectId: process.env.GOOGLE_CLOUD_PROJECT || process.env.GCP_PROJECT_ID || 'your-project-id',
    location: process.env.GCP_LOCATION || 'us-central1',
    model: process.env.GEMINI_MODEL || 'gemini-2.5-flash', 
    xac: Number(process.env.CONCURRENCY || "10"), 
    minTimeMs: Number(process.env.MIN_TIME_MS || "200"),
    skipDomains: [
        "wikipedia.org", "reddit.com", "arxiv.org", "github.com", "youtube.com", "youtu.be",
        "apple.com", "apps.apple.com", "microsoft.com", "microsoftstore.com",
        "chrome.google.com", "chromewebstore.google.com", "play.google.com",
        "facebook.com", "instagram.com", "twitter.com", "x.com", "linkedin.com"
    ]
};

// --- CORE UTILS ---

function shortHash(text) {
    return crypto.createHash('sha256').update(text, 'utf8').digest('hex').slice(0, 16);
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

function urlDomain(u) {
    try {
        const url = new URL(u.includes("://") ? u : `https://${u}`);
        const host = (url.hostname || "").toLowerCase();
        return host.startsWith("www.") ? host.slice(4) : host;
    } catch {
        return "";
    }
}

// --- VERTEX LOGIC ---

const vertexAI = new VertexAI({ project: CONFIG.projectId, location: CONFIG.location });
const generativeModel = vertexAI.getGenerativeModel({
    model: CONFIG.model,
    generationConfig: { 
        temperature: 0.0,
        responseMimeType: "application/json",
        maxOutputTokens: 8192
    },
});

function fillPrompt(template, { url, title, snippet, extractedText }) {
    const dom = urlDomain(url);
    return template
        .replaceAll("{URL}", url)
        .replaceAll("{URL_DOMAIN}", dom)
        .replaceAll("{TITLE}", title || "")
        .replaceAll("{SNIPPET_OR_META_DESCRIPTION}", snippet || "")
        .replaceAll("{EXTRACTED_TEXT}", (extractedText || "").slice(0, 25000)); // Vertex handles larger context better
}

async function vertexGenerateJson(prompt, mode = "full") {
    let finalPrompt = prompt;
    if (mode === "metadata_only") {
        finalPrompt = prompt + "\n\nIMPORTANT: For this request, ONLY fill the 'urls' and 'listicles' objects. Leave 'listicle_products' as an empty array []. This is to avoid token limits.";
    } else if (mode === "products_only") {
        finalPrompt = prompt + "\n\nIMPORTANT: For this request, ONLY fill the 'listicle_products' array. Leave 'urls' and 'listicles' as null or empty objects. Focus on extracting up to 25 products.";
    }

    const result = await generativeModel.generateContent({
        contents: [{ role: 'user', parts: [{ text: finalPrompt }] }]
    });
    const response = result.response;
    const text = response.candidates[0].content.parts[0].text;
    
    // Robust JSON extraction
    let cleaned = String(text).trim();
    
    // 1. Remove markdown code blocks if present
    cleaned = cleaned.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/i, "").trim();
    
    // 2. Find the first '{' or '[' and last '}' or ']' to handle any stray text before/after
    const startCharIdx = cleaned.indexOf('{');
    const startArrayIdx = cleaned.indexOf('[');
    const startIdx = (startCharIdx !== -1 && (startArrayIdx === -1 || startCharIdx < startArrayIdx)) ? startCharIdx : startArrayIdx;

    const endCharIdx = cleaned.lastIndexOf('}');
    const endArrayIdx = cleaned.lastIndexOf(']');
    const endIdx = Math.max(endCharIdx, endArrayIdx);

    if (startIdx !== -1 && endIdx !== -1) {
        cleaned = cleaned.substring(startIdx, endIdx + 1);
    }

    try {
        const parsed = JSON.parse(cleaned);
        // If it's just an array and we're in products_only mode, wrap it
        if (Array.isArray(parsed) && mode === "products_only") {
            return { listicle_products: parsed };
        }
        return parsed;
    } catch (e) {
        // Log the raw text for debugging if parsing fails
        console.error(`[debug] JSON Parse Failed. Raw text snippet: ${text.substring(0, 200)}...`);
        throw new Error(`JSON Parse Error: ${e.message} at position ${e.at || 'unknown'}`);
    }
}

// --- MAIN RUNNER ---

async function main() {
    console.log("⚖️ Starting Vertex AI Enrichment (Database -> JSONL)...");
    console.log(`   Project: ${CONFIG.projectId}`);
    console.log(`   Model: ${CONFIG.model}`);

    // 1. Load already labeled URLs
    const okUrls = new Set();
    if (fs.existsSync(CONFIG.jsonlPath)) {
        const lines = fs.readFileSync(CONFIG.jsonlPath, "utf8").split(/\r?\n/);
        for (const line of lines) {
            if (!line.trim()) continue;
            try {
                const obj = JSON.parse(line);
                if (obj.ok === true) okUrls.add(normalizeUrlKey(obj.url));
            } catch {}
        }
    }
    console.log(`Loaded ${okUrls.size} already labeled URLs.`);

    // 2. Get URLs from DB
    const db = new sqlite3.Database(CONFIG.dbPath);
    const all = promisify(db.all.bind(db));
    const rows = await all("SELECT DISTINCT url FROM citations WHERE url IS NOT NULL AND url != ''");
    db.close();
    console.log(`Loaded ${rows.length} unique URLs from Database.`);

    // 3. Filter missing
    const missing = rows.filter(row => {
        const key = normalizeUrlKey(row.url);
        if (okUrls.has(key)) return false;
        const domain = key.split('/')[0].toLowerCase();
        if (CONFIG.skipDomains.some(sd => domain === sd || domain.endsWith('.' + sd))) return false;
        return true;
    });
    console.log(`Found ${missing.length} URLs that need labeling.`);

    const promptTemplate = fs.readFileSync(CONFIG.promptPath, "utf8");
    const apiLimiter = new Bottleneck({
        maxConcurrent: CONFIG.xac,
        minTime: CONFIG.minTimeMs,
    });

    let count = 0;
    const tasks = missing.map(row => apiLimiter.schedule(async () => {
        const url = row.url;
        const key = normalizeUrlKey(url);
        const hash = shortHash(key);
        const txtPath = path.join(CONFIG.contentDir, `${hash}.txt`);
        const jsonPath = path.join(CONFIG.contentDir, `${hash}.json`);

        let extractedText = "";
        let title = "";
        let snippet = "";

        if (fs.existsSync(txtPath)) {
            extractedText = fs.readFileSync(txtPath, "utf8");
        }
        if (fs.existsSync(jsonPath)) {
            try {
                const meta = JSON.parse(fs.readFileSync(jsonPath, "utf8"));
                title = meta.page_title || "";
                snippet = meta.meta_description || "";
            } catch {}
        }

        const prompt = fillPrompt(promptTemplate, { url, title, snippet, extractedText });

        let success = false;

        try {
            // Attempt 1: Full extraction
            try {
                const parsed = await vertexGenerateJson(prompt, "full");
                const result = {
                    ts: new Date().toISOString(),
                    url,
                    ok: true,
                    model: CONFIG.model,
                    response: parsed,
                    provider: "vertex"
                };
                fs.appendFileSync(CONFIG.jsonlPath, JSON.stringify(result) + "\n");
                console.log(`[ok] Labeled (Full): ${url}`);
                success = true;
            } catch (e) {
                console.log(`[retry] Full extraction failed for ${url}, trying split task...`);
                
                // Attempt 2: Split task (Metadata then Products)
                const metaParsed = await vertexGenerateJson(prompt, "metadata_only");
                const productsParsed = await vertexGenerateJson(prompt, "products_only");
                
                const combined = {
                    ...metaParsed,
                    listicle_products: productsParsed.listicle_products || []
                };
                
                const result = {
                    ts: new Date().toISOString(),
                    url,
                    ok: true,
                    model: CONFIG.model,
                    response: combined,
                    provider: "vertex"
                };
                fs.appendFileSync(CONFIG.jsonlPath, JSON.stringify(result) + "\n");
                console.log(`[ok] Labeled (Split): ${url}`);
                success = true;
            }
        } catch (e) {
            console.log(`[fail] Error labeling ${url}: ${e.message}`);
            const result = {
                ts: new Date().toISOString(),
                url,
                ok: false,
                model: CONFIG.model,
                error: { type: e.name, message: e.message },
                provider: "vertex"
            };
            fs.appendFileSync(CONFIG.jsonlPath, JSON.stringify(result) + "\n");
        }

        count++;
        if (count % 10 === 0) console.log(`Progress: ${count}/${missing.length}`);
    }));

    await Promise.allSettled(tasks);
    console.log("Vertex Enrichment complete.");
}

main().catch(console.error);
