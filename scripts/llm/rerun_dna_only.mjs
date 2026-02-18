import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import Bottleneck from 'bottleneck';

const CONFIG = {
    rerunQueuePath: 'data/enrichment/rerun_global_gemini.json',
    outJsonlPath: 'datapass/page_labels_gemini_v2.5.jsonl',
    promptPath: 'prompts/page_label_dna_only_v1.txt',
    contentDir: 'data/fetched_content',
    concurrency: 30, // Increased for parallel speed
    minTime: 50,     // Reduced for parallel speed
    model: 'gemini-2.5-flash'
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
        return `${host}${pathname}`;
    } catch { return rawUrl.toLowerCase(); }
}

const limiter = new Bottleneck({
    maxConcurrent: CONFIG.concurrency,
    minTime: CONFIG.minTime
});

async function geminiCall(prompt) {
    const apiKey = process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY;
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${CONFIG.model}:generateContent?key=${apiKey}`;
    const payload = {
        contents: [{ parts: [{ text: prompt }] }],
        generationConfig: { response_mime_type: "application/json", temperature: 0 }
    };
    const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    const data = await res.json();
    const text = data.candidates?.[0]?.content?.parts?.[0]?.text;
    return JSON.parse(text.trim().replace(/^```json\s*/, "").replace(/\s*```$/, ""));
}

async function main() {
    const toRerun = JSON.parse(fs.readFileSync(CONFIG.rerunQueuePath, 'utf8'));
    const promptTemplate = fs.readFileSync(CONFIG.promptPath, 'utf8');
    console.log(`🚀 Rerunning ${toRerun.length} URLs with DNA-only prompt...`);

    const tasks = toRerun.map(url => {
        const norm = normalizeUrlKey(url);
        const hash = shortHash(norm);
        const contentPath = path.join(CONFIG.contentDir, `${hash}.txt`);

        if (!fs.existsSync(contentPath)) return Promise.resolve();

        return limiter.schedule(async () => {
            try {
                const content = fs.readFileSync(contentPath, 'utf8').slice(0, 10000);
                const prompt = promptTemplate.replace("{{URL}}", url).replace("{{CONTENT}}", content);
                const response = await geminiCall(prompt);
                
                // Update the file: Remove old entry and append new one
                let lines = fs.readFileSync(CONFIG.outJsonlPath, 'utf8').split('\n');
                lines = lines.filter(l => {
                    try { return JSON.parse(l).url !== url; } catch { return true; }
                });
                
                const result = { url, ok: true, response, timestamp: new Date().toISOString(), rerun: true };
                lines.push(JSON.stringify(result));
                fs.writeFileSync(CONFIG.outJsonlPath, lines.join('\n'));
                
                console.log(`✅ FIXED: ${url}`);
            } catch (err) {
                console.error(`❌ FAILED ${url}: ${err.message}`);
            }
        });
    });

    await Promise.all(tasks);
    console.log("🎯 Rerun complete.");
}

main().catch(console.error);
