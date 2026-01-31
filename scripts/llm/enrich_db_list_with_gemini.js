/**
 * Adapted version of enrich_geo_urls_with_gemini.js
 * 
 * Differences:
 * - Reads URLs from geo_fresh.db (Cited, Additional, Rejected) instead of Excel.
 * - Finds content in data/fetched_content/ using the shortHash(normalizeUrlKey(url)) logic.
 * - Only writes to JSONL (no Excel updates).
 * - Keeps Gemini calling logic and prompt filling EXACTLY the same.
 */

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const Bottleneck = require("bottleneck");
const sqlite3 = require("sqlite3");
const { promisify } = require("util");

// --- CONFIGURATION (Matches original where possible) ---
const CONFIG = {
    dbPath: 'geo_fresh.db',
    jsonlPath: 'datapass/page_labels_gemini.jsonl',
    contentDir: 'data/fetched_content',
    promptPath: 'prompts/page_label_prompt_v1.txt',
    concurrency: Number(process.env.CONCURRENCY || "5"),
    minTimeMs: Number(process.env.MIN_TIME_MS || "400"),
    model: "gemini-3-flash-preview", // Using Flash for speed/cost
    skipDomains: [
        "wikipedia.org", "reddit.com", "arxiv.org", "github.com", "youtube.com", "youtu.be",
        "apple.com", "apps.apple.com", "microsoft.com", "microsoftstore.com",
        "chrome.google.com", "chromewebstore.google.com", "play.google.com",
        "facebook.com", "instagram.com", "twitter.com", "x.com", "linkedin.com"
    ]
};

// --- CORE UTILS (From original script or matching fetcher) ---

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

// --- GEMINI LOGIC (Copied from enrich_geo_urls_with_gemini.js) ---

let _genAiClientPromise = null;
async function getGenAiClient(apiKey) {
    if (_genAiClientPromise) return _genAiClientPromise;
    _genAiClientPromise = (async () => {
        const mod = await import("@google/genai");
        const GoogleGenAI = mod.GoogleGenAI || mod.default?.GoogleGenAI;
        if (!GoogleGenAI) throw new Error("Failed to load GoogleGenAI from @google/genai");
        return new GoogleGenAI({ apiKey });
    })();
    return _genAiClientPromise;
}

function fillPrompt(template, { url, title, snippet, extractedText }) {
    const dom = urlDomain(url);
    return template
        .replaceAll("{URL}", url)
        .replaceAll("{URL_DOMAIN}", dom)
        .replaceAll("{TITLE}", title || "")
        .replaceAll("{SNIPPET_OR_META_DESCRIPTION}", snippet || "")
        .replaceAll("{EXTRACTED_TEXT}", (extractedText || "").slice(0, 12000));
}

async function geminiGenerateJson({ apiKey, model, prompt }) {
    try {
        const client = await getGenAiClient(apiKey);
        const result = await client.models.generateContent({
            model,
            contents: [{ role: "user", parts: [{ text: prompt }] }],
            config: { temperature: 0.0, response_mime_type: "application/json" },
        });
        const outText = result?.text || "";
        
        // Robust JSON extraction
        let cleaned = String(outText).trim();
        
        // 1. Remove markdown code blocks if present
        cleaned = cleaned.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/i, "").trim();
        
        // 2. Find the first '{' and last '}' to handle any stray text before/after
        const startIdx = cleaned.indexOf('{');
        const endIdx = cleaned.lastIndexOf('}');
        if (startIdx !== -1 && endIdx !== -1) {
            cleaned = cleaned.substring(startIdx, endIdx + 1);
        }

        return JSON.parse(cleaned);
    } catch (e) {
        const err = new Error(String(e?.message || e));
        err.name = e?.name || "Error";
        throw err;
    }
}

// --- MAIN RUNNER ---

async function main() {
    const apiKey = process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY;
    if (!apiKey) {
        console.error("Missing GEMINI_API_KEY env var.");
        process.exit(2);
    }

    console.log("Starting adapted Enrichment (Database -> JSONL)...");

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
    const missing = rows.filter(r => {
        const key = normalizeUrlKey(r.url);
        if (okUrls.has(key)) return false;
        const domain = key.split('/')[0].toLowerCase();
        if (CONFIG.skipDomains.some(sd => domain === sd || domain.endsWith('.' + sd))) return false;
        return true;
    });
    console.log(`Found ${missing.length} URLs that need labeling.`);

    const promptTemplate = fs.readFileSync(CONFIG.promptPath, "utf8");
    const apiLimiter = new Bottleneck({
        maxConcurrent: CONFIG.concurrency,
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

        let attempts = 0;
        const maxAttempts = 2;
        let success = false;

        while (attempts < maxAttempts && !success) {
            try {
                const parsed = await geminiGenerateJson({ apiKey, model: CONFIG.model, prompt });
                const result = {
                    ts: new Date().toISOString(),
                    url,
                    ok: true,
                    model: CONFIG.model,
                    response: parsed
                };
                fs.appendFileSync(CONFIG.jsonlPath, JSON.stringify(result) + "\n");
                console.log(`[ok] Labeled: ${url}`);
                success = true;
            } catch (e) {
                attempts++;
                if (attempts < maxAttempts) {
                    console.log(`[retry] Error for ${url}, retrying... (${attempts}/${maxAttempts}) - ${e.message}`);
                    continue;
                }
                console.log(`[fail] Error labeling ${url}: ${e.message}`);
                const result = {
                    ts: new Date().toISOString(),
                    url,
                    ok: false,
                    model: CONFIG.model,
                    error: { type: e.name, message: e.message }
                };
                fs.appendFileSync(CONFIG.jsonlPath, JSON.stringify(result) + "\n");
            }
        }

        count++;
        if (count % 10 === 0) console.log(`Progress: ${count}/${missing.length}`);
    }));

    await Promise.allSettled(tasks);
    console.log("Enrichment complete.");
}

main().catch(console.error);
