/**
 * Fetcher for Gemini Grounding URLs.
 * 1. Reads resolved URLs from data/resolved_grounding_urls.json.
 * 2. Checks against existing enrichment in datapass/page_labels_combined_v2.5.jsonl.
 * 3. Fetches missing HTML, cleans it using the EXACT same logic as ChatGPT pipeline.
 * 4. Saves to data/fetched_content/ for comparability.
 */

import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import * as cheerio from 'cheerio';
import Bottleneck from 'bottleneck';

const CONFIG = {
    resolvedUrlsPath: 'data/resolved_grounding_urls.json',
    enrichedPath: 'datapass/page_labels_combined_v2.5.jsonl',
    outDir: 'data/fetched_content',
    logPath: 'data/fetch_results_gemini_missing.jsonl',
    concurrency: 5,
    minTime: 200,
    timeout: 30000,
    minTextChars: 200,
    skipDomains: [
        "wikipedia.org", "reddit.com", "arxiv.org", "github.com", "youtube.com", "youtu.be",
        "apple.com", "apps.apple.com", "microsoft.com", "microsoftstore.com",
        "chrome.google.com", "chromewebstore.google.com", "play.google.com",
        "facebook.com", "instagram.com", "twitter.com", "x.com", "linkedin.com",
        "google.com"
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

/**
 * EXACT SAME extraction logic as ChatGPT pipeline for parity.
 */
function extractText(html) {
    if (!html) return "";
    const $ = cheerio.load(html);
    $("script, style, noscript").remove();
    const nonContent = ["nav", "header", "footer", "aside", ".navigation", ".nav", ".menu", ".sidebar", ".ad", ".ads", ".cookie", ".popup"];
    $(nonContent.join(", ")).remove();
    
    // Get text, collapse whitespace
    let text = $("body").text();
    text = text.replace(/\s+/g, ' ').trim();
    return text;
}

async function getEnrichedUrls(jsonlPath) {
    const urls = new Set();
    if (!fs.existsSync(jsonlPath)) return urls;
    const content = fs.readFileSync(jsonlPath, 'utf8');
    for (const line of content.split('\n')) {
        if (!line.trim()) continue;
        try {
            const d = JSON.parse(line);
            if (d.url) urls.add(normalizeUrlKey(d.url));
        } catch {}
    }
    return urls;
}

async function getGeminiUrls(resolvedPath) {
    if (!fs.existsSync(resolvedPath)) return [];
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

async function fetchUrl(url) {
    const norm = normalizeUrlKey(url);
    const hash = shortHash(norm);
    const outPath = path.join(CONFIG.outDir, `${hash}.txt`);

    if (fs.existsSync(outPath)) {
        return { url, status: 'already_fetched', path: outPath };
    }

    const domain = new URL(url).hostname;
    if (CONFIG.skipDomains.some(d => domain.includes(d))) {
        return { url, status: 'skipped_domain' };
    }

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), CONFIG.timeout);
        
        const res = await fetch(url, { 
            signal: controller.signal,
            headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' }
        });
        clearTimeout(timeoutId);

        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        
        const html = await res.text();
        const text = extractText(html);

        if (text.length < CONFIG.minTextChars) {
            throw new Error(`Text too short (${text.length} chars)`);
        }

        fs.writeFileSync(outPath, text, 'utf8');
        return { url, status: 'success', chars: text.length, path: outPath };
    } catch (err) {
        return { url, status: 'error', error: err.message };
    }
}

async function main() {
    if (!fs.existsSync(CONFIG.outDir)) fs.mkdirSync(CONFIG.outDir, { recursive: true });

    console.log("Loading URLs...");
    const enriched = await getEnrichedUrls(CONFIG.enrichedPath);
    const gemini = await getGeminiUrls(CONFIG.resolvedUrlsPath);

    const toFetch = gemini.filter(u => !enriched.has(normalizeUrlKey(u)));
    console.log(`Total Gemini URLs: ${gemini.length}`);
    console.log(`Already Enriched: ${gemini.length - toFetch.length}`);
    console.log(`To Fetch: ${toFetch.length}`);

    const results = [];
    let count = 0;

    const tasks = toFetch.map(url => 
        limiter.schedule(async () => {
            const res = await fetchUrl(url);
            count++;
            console.log(`[${count}/${toFetch.length}] ${res.status}: ${url}`);
            fs.appendFileSync(CONFIG.logPath, JSON.stringify(res) + '\n');
            return res;
        })
    );

    await Promise.all(tasks);
    console.log("Done.");
}

main().catch(console.error);
