/**
 * Enrichment V2: Ignore Excel.
 * 1. Read Cited, Additional, Rejected URLs from geo_fresh.db.
 * 2. Skip URLs already in datapass/page_labels_gemini.jsonl (ok: true).
 * 3. Use local content from data/fetched_content/ if available.
 * 4. Call Gemini to label missing URLs.
 * 5. Append results to datapass/page_labels_gemini.jsonl.
 */

import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import Bottleneck from 'bottleneck';
import sqlite3 from 'sqlite3';
import { promisify } from 'util';

const CONFIG = {
    dbPath: 'geo_fresh.db',
    jsonlPath: 'datapass/page_labels_gemini.jsonl',
    contentDir: 'data/fetched_content',
    promptPath: 'prompts/page_label_prompt_v1.txt',
    concurrency: 5,
    minTime: 500,
    model: 'gemini-1.5-flash', // Using Flash for speed/cost
    max: 0, // set to > 0 to limit
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

async function getLabeledUrls(jsonlPath) {
    const labeled = new Set();
    if (!fs.existsSync(jsonlPath)) return labeled;
    const content = fs.readFileSync(jsonlPath, 'utf8');
    for (const line of content.split('\n')) {
        if (!line.trim()) continue;
        try {
            const d = JSON.parse(line);
            if (d.ok === true) labeled.add(normalizeUrlKey(d.url));
        } catch {}
    }
    return labeled;
}

async function getDbUrls(dbPath) {
    const db = new sqlite3.Database(dbPath);
    const all = promisify(db.all.bind(db));
    const rows = await all("SELECT DISTINCT url FROM citations WHERE url IS NOT NULL AND url != ''");
    db.close();
    return rows.map(r => r.url);
}

async function geminiCall(prompt) {
    const apiKey = process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY;
    if (!apiKey) throw new Error("Missing API Key");

    const url = `https://generativelanguage.googleapis.com/v1beta/models/${CONFIG.model}:generateContent?key=${apiKey}`;
    const payload = {
        contents: [{ parts: [{ text: prompt }] }],
        generationConfig: { response_mime_type: "application/json", temperature: 0.1 }
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
    try {
        const text = data.candidates[0].content.parts[0].text;
        return JSON.parse(text);
    } catch (e) {
        throw new Error("Failed to parse Gemini response as JSON");
    }
}

async function main() {
    console.log("Starting Enrichment V2 (Database -> JSONL)...");
    
    const labeled = await getLabeledUrls(CONFIG.jsonlPath);
    console.log(`Loaded ${labeled.size} already labeled URLs.`);

    const dbUrls = await getDbUrls(CONFIG.dbPath);
    console.log(`Loaded ${dbUrls.length} unique URLs from Database.`);

    const missing = dbUrls.filter(url => {
        const key = normalizeUrlKey(url);
        if (labeled.has(key)) return false;
        
        const domain = key.split('/')[0].toLowerCase();
        if (CONFIG.skipDomains.some(sd => domain === sd || domain.endsWith('.' + sd))) return false;
        
        return true;
    });

    console.log(`Found ${missing.length} URLs that need labeling.`);
    const toProcess = CONFIG.max > 0 ? missing.slice(0, CONFIG.max) : missing;

    const promptTemplate = fs.readFileSync(CONFIG.promptPath, 'utf8');
    const limiter = new Bottleneck({ maxConcurrent: CONFIG.concurrency, minTime: CONFIG.minTime });
    let count = 0;

    const tasks = toProcess.map(url => limiter.schedule(async () => {
        const key = normalizeUrlKey(url);
        const hash = shortHash(key);
        const txtPath = path.join(CONFIG.contentDir, `${hash}.txt`);
        
        let content = "";
        if (fs.existsSync(txtPath)) {
            content = fs.readFileSync(txtPath, 'utf8').slice(0, 15000);
        }

        const prompt = promptTemplate
            .replace(/{URL}/g, url)
            .replace(/{EXTRACTED_TEXT}/g, content || "No content available. Use URL and domain to guess.");

        try {
            const response = await geminiCall(prompt);
            const result = {
                ts: new Date().toISOString(),
                url,
                ok: true,
                model: CONFIG.model,
                response
            };
            fs.appendFileSync(CONFIG.jsonlPath, JSON.stringify(result) + "\n");
            console.log(`[ok] Labeled: ${url}`);
        } catch (e) {
            console.log(`[fail] Error labeling ${url}: ${e.message}`);
            const result = {
                ts: new Date().toISOString(),
                url,
                ok: false,
                model: CONFIG.model,
                error: e.message
            };
            fs.appendFileSync(CONFIG.jsonlPath, JSON.stringify(result) + "\n");
        }

        count++;
        if (count % 10 === 0) console.log(`Progress: ${count}/${toProcess.length}`);
    }));

    await Promise.allSettled(tasks);
    console.log("Enrichment complete.");
}

main().catch(console.error);
