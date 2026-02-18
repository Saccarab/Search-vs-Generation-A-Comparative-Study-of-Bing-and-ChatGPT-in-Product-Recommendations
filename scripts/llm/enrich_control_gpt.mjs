import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import Bottleneck from 'bottleneck';
import OpenAI from 'openai';

const CONFIG = {
    // Global queue containing every unique URL from all studies
    rerunQueuePath: 'data/enrichment/drift_enrichment_queue.csv', // Updated to CSV path
    outJsonlPath: 'datapass/page_labels_control_gpt5_mini.jsonl',
    promptPath: 'prompts/page_label_dna_only_v1.txt',
    contentDir: 'data/fetched_content',
    concurrency: 40,
    minTime: 30,
    model: 'gpt-5-mini',
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

const limiter = new Bottleneck({
    maxConcurrent: CONFIG.concurrency,
    minTime: CONFIG.minTime
});

async function gptCall(prompt) {
    const openai = new OpenAI({ apiKey: process.env.OPEN_AI_KEY });
    const completion = await openai.chat.completions.create({
        model: CONFIG.model,
        messages: [{ role: "user", content: prompt }],
        response_format: { type: "json_object" },
        temperature: 1
    });
    return JSON.parse(completion.choices[0].message.content);
}

async function main() {
    if (!process.env.OPEN_AI_KEY) {
        console.error("❌ Error: OPENAI_API_KEY environment variable is not set.");
        process.exit(1);
    }

    // 1. Load the global queue
    let allUrls = [];
    if (!fs.existsSync(CONFIG.rerunQueuePath)) {
        console.error(`❌ Error: Queue file not found at ${CONFIG.rerunQueuePath}`);
        process.exit(1);
    }
    
    if (CONFIG.rerunQueuePath.endsWith('.csv')) {
        const csvContent = fs.readFileSync(CONFIG.rerunQueuePath, 'utf8');
        allUrls = csvContent.split('\n').slice(1).map(l => l.trim()).filter(l => l);
    } else {
        allUrls = JSON.parse(fs.readFileSync(CONFIG.rerunQueuePath, 'utf8'));
    }

    // 2. Check what's already done
    const done = new Set();
    if (fs.existsSync(CONFIG.outJsonlPath)) {
        const content = fs.readFileSync(CONFIG.outJsonlPath, 'utf8');
        content.split('\n').forEach(line => {
            if (!line.trim()) return;
            try {
                const d = JSON.parse(line);
                if (d.url) done.add(d.url);
            } catch {}
        });
    }

    const toProcess = allUrls.filter(u => {
        const raw = u.toLowerCase().trim();
        const norm = normalizeUrlKey(u);
        if (done.has(raw) || done.has(norm)) return false;

        // Skip heuristic domains
        try {
            const domain = new URL(u).hostname.toLowerCase().replace('www.', '');
            if (CONFIG.skipDomains.some(d => domain === d || domain.endsWith('.' + d))) {
                return false;
            }
        } catch (e) { return false; }

        return true;
    });
    console.log(`🧪 GPT-5 mini labeler Control Pass: ${toProcess.length} URLs to process out of ${allUrls.length} total.`);

    const promptTemplate = fs.readFileSync(CONFIG.promptPath, 'utf8');

    const tasks = toProcess.map(url => {
        const norm = normalizeUrlKey(url);
        const hash = shortHash(norm);
        const contentPath = path.join(CONFIG.contentDir, `${hash}.txt`);

        if (!fs.existsSync(contentPath)) {
            return Promise.resolve();
        }

        const domain = new URL(url).hostname;
        // (Domain check already handled in filter)

        return limiter.schedule(async () => {
            try {
                const rawContent = fs.readFileSync(contentPath, 'utf8');
                const sanitizedContent = rawContent
                    .replace(/"/g, "'")
                    .replace(/\s+/g, ' ')
                    .trim()
                    .slice(0, 10000);
                
                 const prompt = promptTemplate
                     .replace(/{URL}/g, url)
                     .replace(/{TITLE}/g, "N/A")
                     .replace(/{SNIPPET_OR_META_DESCRIPTION}/g, "N/A")
                     .replace(/{EXTRACTED_TEXT}/g, sanitizedContent)
                     .replace("{{URL}}", url)
                     .replace("{{CONTENT}}", sanitizedContent);
                
                const response = await gptCall(prompt);
                const result = { 
                    url, 
                    ok: true, 
                    response, 
                    model: CONFIG.model,
                    timestamp: new Date().toISOString() 
                };
                
                 fs.appendFileSync(CONFIG.outJsonlPath, JSON.stringify(result) + '\n');
                 const doneCount = fs.readFileSync(CONFIG.outJsonlPath, 'utf8').split('\n').filter(Boolean).length;
                 console.log(`[${doneCount}/${toProcess.length}] SUCCESS: ${url}`);
             } catch (err) {
                 console.error(`\n❌ FAILED ${url}: ${err.message}`);
             }
         });
     });

     console.log(`🚀 Starting processing with concurrency ${CONFIG.concurrency}...`);
     await Promise.all(tasks);
     console.log("\n🏁 GPT Control Enrichment Complete.");
 }

main().catch(console.error);
