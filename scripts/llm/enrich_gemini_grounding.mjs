/**
 * Dedicated Enrichment for Gemini Grounding URLs.
 * 1. Reads resolved URLs from Gemini data.
 * 2. Skips already enriched URLs (from combined v2.5 AND local gemini v2.5).
 * 3. Uses gemini-2.5-flash and the parity prompt.
 * 4. Appends to datapass/page_labels_gemini_v2.5.jsonl.
 */

import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import Bottleneck from 'bottleneck';

const CONFIG = {
    resolvedUrlsPath: 'data/enrichment/drift_enrichment_queue.csv', // Using the new drift queue
    enrichedPath: 'datapass/page_labels_combined_v2.5.jsonl', 
    outJsonlPath: 'datapass/page_labels_gemini_v2.5.jsonl', // Gemini-specific file
    contentDir: 'data/fetched_content',
    promptPath: 'prompts/page_label_dna_only_v1.txt', // NEW PROMPT
    concurrency: 15,
    minTime: 100,
    model: 'gemini-2.5-flash',
    skipDomains: [
        "wikipedia.org", "reddit.com", "arxiv.org", "github.com", "youtube.com", "youtu.be",
        "apple.com", "apps.apple.com", "microsoft.com", "microsoftstore.com",
        "chrome.google.com", "chromewebstore.google.com", "play.google.com",
        "facebook.com", "instagram.com", "twitter.com", "x.com", "linkedin.com",
        "google.com", "apps.microsoft.com", "support.microsoft.com", "support.apple.com",
        "support.google.com"
    ]
};

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

async function getEnrichedUrls(paths) {
    const urls = new Set();
    for (const jsonlPath of paths) {
        if (!fs.existsSync(jsonlPath)) continue;
        const content = fs.readFileSync(jsonlPath, 'utf8');
        for (const line of content.split('\n')) {
            if (!line.trim()) continue;
            try {
                const d = JSON.parse(line);
                if (d.url) {
                    urls.add(d.url.toLowerCase().trim());
                    urls.add(normalizeUrlKey(d.url));
                }
            } catch {}
        }
    }
    return urls;
}

async function getGeminiUrls(resolvedPath) {
    if (!fs.existsSync(resolvedPath)) return [];
    
    // Check if it's CSV or JSON
    if (resolvedPath.endsWith('.csv')) {
        const csv = fs.readFileSync(resolvedPath, 'utf8');
        const lines = csv.split('\n');
        const urls = new Set();
        for (let i = 1; i < lines.length; i++) {
            const line = lines[i].trim();
            if (line) urls.add(line);
        }
        return Array.from(urls);
    }

    const data = JSON.parse(fs.readFileSync(resolvedPath, 'utf8'));
    const urls = new Set();
    for (const [vertex, resolved] of Object.entries(data)) {
        if (resolved && !resolved.includes('google.com/search')) {
            urls.add(resolved);
        }
    }
    return Array.from(urls);
}

const limiter = new Bottleneck({
    maxConcurrent: CONFIG.concurrency,
    minTime: CONFIG.minTime
});

async function geminiCall(prompt) {
    const apiKey = process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY;
    if (!apiKey) throw new Error("Missing API Key");

    const url = `https://generativelanguage.googleapis.com/v1beta/models/${CONFIG.model}:generateContent?key=${apiKey}`;
    const payload = {
        contents: [{ parts: [{ text: prompt }] }],
        generationConfig: { 
            response_mime_type: "application/json", 
            temperature: 0,
            maxOutputTokens: 4096 // Doubled from 2048
        }
    };

    const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });

    if (!res.ok) {
        const err = await res.text();
        throw new Error(`Gemini API Error: ${res.status} - ${err}`);
    }

    const data = await res.json();
    const text = data.candidates?.[0]?.content?.parts?.[0]?.text;
    if (!text) throw new Error("Empty response from Gemini");
    
    let cleanText = text.trim();
    // Strip markdown fences
    cleanText = cleanText.replace(/^```json\s*/, "").replace(/\s*```$/, "");
    
    try {
        return JSON.parse(cleanText);
    } catch (e) {
        // Attempt truncated JSON repair
        try {
            let repaired = cleanText;
            const opens = (repaired.match(/{/g) || []).length;
            const closes = (repaired.match(/}/g) || []).length;
            if (opens > closes) {
                repaired += "}".repeat(opens - closes);
            }
            return JSON.parse(repaired);
        } catch (e2) {
            // Final attempt: find the largest valid JSON object in the string
            const firstBrace = cleanText.indexOf('{');
            const lastBrace = cleanText.lastIndexOf('}');
            if (firstBrace !== -1 && lastBrace !== -1) {
                try {
                    return JSON.parse(cleanText.substring(firstBrace, lastBrace + 1));
                } catch (e3) {
                    throw new Error(`JSON Parse Error: ${e.message} (Original: ${text.substring(0, 100)}...)`);
                }
            }
            throw e;
        }
    }
}

async function main() {
    const args = process.argv.slice(2);
    if (args.length > 0) {
        const targetUrl = args[0];
        console.log(`🎯 DEBUG MODE: Enriching single URL: ${targetUrl}`);
        
        const norm = normalizeUrlKey(targetUrl);
        const hash = shortHash(norm);
        const contentPath = path.join(CONFIG.contentDir, `${hash}.txt`);

        if (!fs.existsSync(contentPath)) {
            console.error(`❌ No content found for hash ${hash} at ${contentPath}`);
            process.exit(1);
        }

        const promptTemplate = fs.readFileSync(CONFIG.promptPath, 'utf8');
        const rawContent = fs.readFileSync(contentPath, 'utf8');
        const sanitizedContent = rawContent
            .replace(/"/g, "'")
            .replace(/\s+/g, ' ')
            .trim()
            .slice(0, 8000);

        const prompt = promptTemplate
            .replace(/{URL}/g, targetUrl)
            .replace(/{TITLE}/g, "N/A")
            .replace(/{SNIPPET_OR_META_DESCRIPTION}/g, "N/A")
            .replace(/{EXTRACTED_TEXT}/g, sanitizedContent)
            .replace("{{URL}}", targetUrl)
            .replace("{{CONTENT}}", sanitizedContent);
        
        try {
            const response = await geminiCall(prompt);
            console.log("--- GEMINI RESPONSE ---");
            console.log(JSON.stringify(response, null, 2));
            
            // Ask if user wants to save it
            console.log("\n(Note: This debug run was NOT saved to the jsonl file)");
        } catch (err) {
            console.error(`❌ FAILED: ${err.message}`);
        }
        return;
    }

    console.log("Loading data...");
    // Check BOTH the master file and the new Gemini-specific file to avoid duplicates
    const enriched = await getEnrichedUrls([CONFIG.enrichedPath, CONFIG.outJsonlPath]);
    const gemini = await getGeminiUrls(CONFIG.resolvedUrlsPath);
    const promptTemplate = fs.readFileSync(CONFIG.promptPath, 'utf8');

    const toEnrich = gemini.filter(u => {
        const raw = u.toLowerCase().trim();
        const norm = normalizeUrlKey(u);
        
        // Skip if already in combined or gemini jsonl
        if (enriched.has(raw) || enriched.has(norm)) return false;

        // Skip if heuristic domain
        try {
            const domain = new URL(u).hostname.toLowerCase().replace('www.', '');
            if (CONFIG.skipDomains.some(d => domain === d || domain.endsWith('.' + d))) {
                return false;
            }
        } catch (e) {
            return false;
        }

        return true;
    });

    console.log(`Total Gemini URLs: ${gemini.length}`);
    console.log(`Already Enriched:  ${gemini.length - toEnrich.length}`);
    console.log(`To Enrich:         ${toEnrich.length}`);

    let count = 0;
    // Use Promise.all to actually run tasks in parallel up to the concurrency limit
    const tasks = toEnrich.map(url => {
        const norm = normalizeUrlKey(url);
        const hash = shortHash(norm);
        const contentPath = path.join(CONFIG.contentDir, `${hash}.txt`);

        if (!fs.existsSync(contentPath)) {
            console.log(`[SKIP] No content for: ${url}`);
            return Promise.resolve();
        }

        const domain = new URL(url).hostname;
        // (Skip domain check already handled in filter)

        return limiter.schedule(async () => {
            try {
                const rawContent = fs.readFileSync(contentPath, 'utf8');
                const sanitizedContent = rawContent
                    .replace(/"/g, "'")
                    .replace(/\s+/g, ' ')
                    .trim()
                    .slice(0, 8000); // Aggressive slice for persistent failures

                const prompt = promptTemplate
                    .replace(/{URL}/g, url)
                    .replace(/{TITLE}/g, "N/A")
                    .replace(/{SNIPPET_OR_META_DESCRIPTION}/g, "N/A")
                    .replace(/{EXTRACTED_TEXT}/g, sanitizedContent)
                    .replace("{{URL}}", url)
                    .replace("{{CONTENT}}", sanitizedContent);
                
                const response = await geminiCall(prompt);
                const result = { url, ok: true, response, timestamp: new Date().toISOString() };
                
                fs.appendFileSync(CONFIG.outJsonlPath, JSON.stringify(result) + '\n');
                count++;
                console.log(`[${count}/${toEnrich.length}] SUCCESS: ${url}`);
            } catch (err) {
                console.error(`[ERROR] ${url}: ${err.message}`);
                const fail = { url, ok: false, error: err.message, timestamp: new Date().toISOString() };
                fs.appendFileSync(CONFIG.outJsonlPath, JSON.stringify(fail) + '\n');
            }
        });
    });

    await Promise.all(tasks);
    console.log("Enrichment complete.");
}

main().catch(console.error);
