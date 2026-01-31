/**
 * Fetch content for URLs that exist in the database (Cited, Additional, Rejected)
 * but are missing from the 'urls' tab of the master Excel sheet.
 */

import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import ExcelJS from 'exceljs';
import Bottleneck from 'bottleneck';
import * as cheerio from 'cheerio';
import sqlite3 from 'sqlite3';
import { promisify } from 'util';

const CONFIG = {
    dbPath: 'geo_fresh.db',
    xlsxPath: 'datapass/geo-enterprise-master.xlsx',
    outDir: 'data/fetched_content',
    logPath: 'data/fetch_results_missing.jsonl',
    concurrency: 5,
    minTime: 200,
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

async function getUrlsFromXlsx(xlsxPath) {
    const urls = new Set();
    if (!fs.existsSync(xlsxPath)) return urls;
    
    const wb = new ExcelJS.Workbook();
    await wb.xlsx.readFile(xlsxPath);
    const ws = wb.getWorksheet('urls');
    if (!ws) return urls;

    const hMap = new Map();
    ws.getRow(1).eachCell((cell, col) => {
        hMap.set(cell.value, col);
    });

    const urlCol = hMap.get('url');
    if (!urlCol) return urls;

    ws.eachRow((row, i) => {
        if (i === 1) return;
        const url = row.getCell(urlCol).value;
        if (url) urls.add(normalizeUrlKey(String(url)));
    });
    return urls;
}

async function getUrlsFromDb(dbPath) {
    const db = new sqlite3.Database(dbPath);
    const all = promisify(db.all.bind(db));
    
    // Get unique URLs from citations table (covers cited, additional, rejected)
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
    console.log("Starting missing content fetch process...");
    if (!fs.existsSync(CONFIG.outDir)) fs.mkdirSync(CONFIG.outDir, { recursive: true });

    const xlsxUrls = await getUrlsFromXlsx(CONFIG.xlsxPath);
    console.log(`Loaded ${xlsxUrls.size} URLs from Excel.`);

    const dbUrls = await getUrlsFromDb(CONFIG.dbPath);
    console.log(`Loaded ${dbUrls.length} unique URLs from Database.`);

    const missing = dbUrls.filter(url => {
        const key = normalizeUrlKey(url);
        if (xlsxUrls.has(key)) return false;
        
        const domain = key.split('/')[0].toLowerCase();
        if (CONFIG.skipDomains.some(sd => domain === sd || domain.endsWith('.' + sd))) {
            return false;
        }
        return true;
    });

    console.log(`Found ${missing.length} URLs in DB that are NOT in Excel and NOT skipped.`);

    const limiter = new Bottleneck({ maxConcurrent: CONFIG.concurrency, minTime: CONFIG.minTime });
    let count = 0;

    const tasks = missing.map(url => limiter.schedule(async () => {
        const key = normalizeUrlKey(url);
        const hash = shortHash(key);
        const txtPath = path.join(CONFIG.outDir, `${hash}.txt`);
        const jsonPath = path.join(CONFIG.outDir, `${hash}.json`);

        if (fs.existsSync(txtPath) && fs.existsSync(jsonPath)) {
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
                console.log(`[ok] Fetched: ${url}`);
            } else {
                result.ok = false;
                result.error = "Content too short";
            }
        }

        fs.appendFileSync(CONFIG.logPath, JSON.stringify(result) + "\n");
        count++;
        if (count % 10 === 0) console.log(`Progress: ${count}/${missing.length}`);
    }));

    await Promise.allSettled(tasks);
    console.log("Fetch complete.");
}

main().catch(console.error);
