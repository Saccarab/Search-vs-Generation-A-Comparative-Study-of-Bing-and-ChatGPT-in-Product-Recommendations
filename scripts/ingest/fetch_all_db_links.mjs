/**
 * Total Fetch: Ignore all Excel sheets.
 * Pull every unique Cited, Additional, and Rejected URL from geo_fresh.db
 * and fetch content for them if not already saved locally.
 */

import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import Bottleneck from 'bottleneck';
import * as cheerio from 'cheerio';
import sqlite3 from 'sqlite3';
import { promisify } from 'util';

const CONFIG = {
    dbPath: 'geo_fresh.db',
    outDir: 'data/fetched_content',
    logPath: 'data/fetch_results_total.jsonl',
    concurrency: 10, // Increased for speed
    minTime: 100,
    timeout: 30000,
    minTextChars: 200,
    skipDomains: [
        "wikipedia.org", "reddit.com", "arxiv.org", "github.com", "youtube.com", "youtu.be",
        "apple.com", "apps.apple.com", "microsoft.com", "microsoftstore.com",
        "chrome.google.com", "chromewebstore.google.com", "play.google.com",
        "facebook.com", "instagram.com", "twitter.com", "x.com", "linkedin.com"
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

async function getUrlsFromDb(dbPath) {
    const db = new sqlite3.Database(dbPath);
    const all = promisify(db.all.bind(db));
    // Get unique URLs from citations table (Cited, Additional, Rejected)
    const rows = await all("SELECT DISTINCT url FROM citations WHERE url IS NOT NULL AND url != ''");
    db.close();
    return rows.map(r => r.url);
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
    console.log("Starting TOTAL fetch process (ignoring all Excel sheets)...");
    if (!fs.existsSync(CONFIG.outDir)) fs.mkdirSync(CONFIG.outDir, { recursive: true });

    const dbUrls = await getUrlsFromDb(CONFIG.dbPath);
    console.log(`Loaded ${dbUrls.length} unique URLs from Database.`);

    const toProcess = dbUrls.filter(url => {
        const key = normalizeUrlKey(url);
        const domain = key.split('/')[0].toLowerCase();
        if (CONFIG.skipDomains.some(sd => domain === sd || domain.endsWith('.' + sd))) {
            return false;
        }
        return true;
    });

    console.log(`Filtered down to ${toProcess.length} URLs (after skipping common domains).`);

    const limiter = new Bottleneck({ maxConcurrent: CONFIG.concurrency, minTime: CONFIG.minTime });
    let count = 0;
    let okCount = 0;
    let skipCount = 0;
    let failCount = 0;

    const tasks = toProcess.map(url => limiter.schedule(async () => {
        const key = normalizeUrlKey(url);
        const hash = shortHash(key);
        const txtPath = path.join(CONFIG.outDir, `${hash}.txt`);
        const jsonPath = path.join(CONFIG.outDir, `${hash}.json`);

        if (fs.existsSync(txtPath) && fs.existsSync(jsonPath)) {
            skipCount++;
            return;
        }

        const res = await fetchUrl(url);
        const now = new Date().toISOString();
        const result = { url, normalized_url: key, hash, fetched_at: now, status: res.status || 0, ok: res.ok || false, error: res.error || "" };

        if (res.ok) {
            const text = extractText(res.html);
            if (text.length >= CONFIG.minTextChars) {
                fs.writeFileSync(txtPath, text);
                result.word_count = text.split(/\s+/).length;
                fs.writeFileSync(jsonPath, JSON.stringify(result, null, 2));
                okCount++;
            } else {
                result.ok = false;
                result.error = "Content too short";
                failCount++;
            }
        } else {
            failCount++;
        }

        fs.appendFileSync(CONFIG.logPath, JSON.stringify(result) + "\n");
        count++;
        if (count % 20 === 0) {
            console.log(`Progress: ${count}/${toProcess.length} | OK: ${okCount} | Skipped: ${skipCount} | Failed: ${failCount}`);
        }
    }));

    await Promise.allSettled(tasks);
    console.log("TOTAL Fetch complete.");
    console.log(`Summary: Total=${toProcess.length}, OK=${okCount}, Skipped=${skipCount}, Failed=${failCount}`);
}

main().catch(console.error);
