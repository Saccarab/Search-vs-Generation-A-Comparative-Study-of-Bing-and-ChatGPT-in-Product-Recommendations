/**
 * Fetch content for URLs in the enrichment queue that haven't been fetched yet.
 * 
 * Logic:
 * 1. Load already-fetched URLs from geo_updated.xlsx (to avoid duplicates).
 * 2. Load the enrichment queue (Cited, Additional, Rejected).
 * 3. Fetch missing URLs using extension-like extraction logic.
 * 4. Save content (.txt) and metadata (.json) to data/fetched_content/.
 * 5. Append results to data/fetch_results.jsonl.
 */

import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import ExcelJS from 'exceljs';
import Bottleneck from 'bottleneck';
import * as cheerio from 'cheerio';
import csv from 'csv-parser';

const CONFIG = {
    xlsxPath: 'datapass/geo-enterprise-master.xlsx',
    queuePath: 'data/enrichment/missing_drift_urls.csv',
    outDir: 'data/fetched_content',
    logPath: 'data/fetch_results.jsonl',
    concurrency: 5,
    minTime: 200,
    timeout: 30000,
    minTextChars: 200,
    max: 0, // set to > 0 to limit
    skipDomains: [
        "wikipedia.org", 
        "reddit.com", 
        "arxiv.org", 
        "github.com", 
        "youtube.com", 
        "youtu.be",
        "apple.com",
        "apps.apple.com",
        "microsoft.com",
        "microsoftstore.com",
        "chrome.google.com",
        "chromewebstore.google.com",
        "play.google.com",
        "facebook.com",
        "instagram.com",
        "twitter.com",
        "x.com",
        "linkedin.com",
        "tiktok.com",
        "quora.com"
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

async function getAlreadyFetchedUrls(xlsxPath) {
    const fetched = new Set();
    if (!fs.existsSync(xlsxPath)) return fetched;
    
    const wb = new ExcelJS.Workbook();
    await wb.xlsx.readFile(xlsxPath);
    const ws = wb.getWorksheet('urls');
    if (!ws) return fetched;

    const hMap = new Map();
    ws.getRow(1).eachCell((cell, col) => {
        hMap.set(cell.value, col);
    });

    const urlCol = hMap.get('url');
    const pathCol = hMap.get('content_path');

    if (!urlCol || !pathCol) return fetched;

    ws.eachRow((row, i) => {
        if (i === 1) return;
        const url = row.getCell(urlCol).value;
        const cPath = row.getCell(pathCol).value;
        if (url && cPath) {
            fetched.add(normalizeUrlKey(String(url)));
        }
    });
    return fetched;
}

async function loadQueue(csvPath) {
    const rows = [];
    return new Promise((resolve) => {
        if (!fs.existsSync(csvPath)) return resolve(rows);
        fs.createReadStream(csvPath)
            .pipe(csv())
            .on('data', (data) => rows.push(data))
            .on('end', () => resolve(rows));
    });
}

function extractText(html) {
    if (!html) return "";
    const $ = cheerio.load(html);
    $("script, style, noscript").remove();
    const nonContent = ["nav", "header", "footer", "aside", ".navigation", ".nav", ".menu", ".sidebar", ".ad", ".ads", ".cookie", ".popup"];
    $(nonContent.join(", ")).remove();
    let text = $("body").text() || "";
    return text.replace(/\u00a0/g, " ").replace(/\s+/g, " ").trim();
}

async function fetchUrl(url) {
    const controller = new AbortController();
    const t = setTimeout(() => controller.abort(), CONFIG.timeout);
    try {
        const res = await fetch(url, {
            headers: { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36" },
            signal: controller.signal
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const html = await res.text();
        return { ok: true, html, finalUrl: res.url, status: res.status };
    } catch (e) {
        return { ok: false, error: e.message };
    } finally {
        clearTimeout(t);
    }
}

async function main() {
    console.log("Starting fetch process...");
    if (!fs.existsSync(CONFIG.outDir)) fs.mkdirSync(CONFIG.outDir, { recursive: true });

    const alreadyFetched = new Set();
    // Also check local directory for existing files to avoid re-fetching
    if (fs.existsSync(CONFIG.outDir)) {
        const files = fs.readdirSync(CONFIG.outDir);
        files.forEach(f => {
            if (f.endsWith('.json')) {
                try {
                    const data = JSON.parse(fs.readFileSync(path.join(CONFIG.outDir, f), 'utf8'));
                    if (data.normalized_url) alreadyFetched.add(data.normalized_url);
                } catch (e) {}
            }
        });
    }
    console.log(`Loaded ${alreadyFetched.size} already fetched URLs from local storage.`);

    const queue = await loadQueue(CONFIG.queuePath);
    console.log(`Loaded ${queue.length} URLs from queue.`);

    const missing = queue.filter(r => {
        const key = normalizeUrlKey(r.url);
        if (alreadyFetched.has(key)) return false;
        
        const domain = key.split('/')[0].toLowerCase();
        if (CONFIG.skipDomains.some(sd => domain === sd || domain.endsWith('.' + sd))) {
            return false;
        }
        return true;
    });
    console.log(`Found ${missing.length} URLs that need fetching (after skipping common domains).`);

    const toFetch = CONFIG.max > 0 ? missing.slice(0, CONFIG.max) : missing;
    if (CONFIG.max > 0) console.log(`Limiting to first ${CONFIG.max} URLs.`);

    // Increase concurrency for faster fetching
    const limiter = new Bottleneck({ maxConcurrent: 10, minTime: 100 });
    let count = 0;

    const tasks = toFetch.map(row => limiter.schedule(async () => {
        const url = row.url;
        const key = normalizeUrlKey(url);
        const hash = shortHash(key);
        const txtPath = path.join(CONFIG.outDir, `${hash}.txt`);
        const jsonPath = path.join(CONFIG.outDir, `${hash}.json`);

        // Skip if files already exist locally
        if (fs.existsSync(txtPath) && fs.existsSync(jsonPath)) {
            return;
        }

        const res = await fetchUrl(url);
        const now = new Date().toISOString();

        const result = {
            url,
            normalized_url: key,
            hash,
            fetched_at: now,
            status: res.status || 0,
            ok: res.ok || false,
            error: res.error || ""
        };

        if (res.ok) {
            const text = extractText(res.html);
            if (text.length >= CONFIG.minTextChars) {
                fs.writeFileSync(txtPath, text);
                result.word_count = text.split(/\s+/).length;
                result.char_count = text.length;
                fs.writeFileSync(jsonPath, JSON.stringify(result, null, 2));
                console.log(`[ok] Fetched: ${url} (${result.word_count} words)`);
            } else {
                result.ok = false;
                result.error = "Content too short";
                console.log(`[fail] Short content: ${url}`);
            }
        } else {
            console.log(`[fail] Error: ${url} - ${res.error}`);
        }

        fs.appendFileSync(CONFIG.logPath, JSON.stringify(result) + "\n");
        count++;
        if (count % 10 === 0) console.log(`Progress: ${count}/${missing.length}`);
    }));

    await Promise.allSettled(tasks);
    console.log("Fetch complete.");
}

main().catch(console.error);
