import fs from 'fs';
import path from 'path';

const CONFIG = {
    skippedQueuePath: 'data/enrichment/skipped_urls_to_label.json',
    outJsonlPath: 'datapass/page_labels_gemini_v2.5.jsonl',
    model: 'heuristic-labeler-v1'
};

const DOMAIN_MAP = {
    'wikipedia.org': { type: 'reference', format: 'other', intent: 'informational' },
    'reddit.com': { type: 'forum_ugc', format: 'other', intent: 'informational' },
    'youtube.com': { type: 'other', format: 'other', intent: 'informational' },
    'youtu.be': { type: 'other', format: 'other', intent: 'informational' },
    'github.com': { type: 'documentation', format: 'other', intent: 'informational' },
    'apple.com': { type: 'product_page', format: 'landing_page', intent: 'transactional' },
    'microsoft.com': { type: 'product_page', format: 'landing_page', intent: 'transactional' },
    'google.com': { type: 'product_page', format: 'landing_page', intent: 'transactional' }
};

function getHeuristicLabel(url) {
    const hostname = new URL(url).hostname.toLowerCase();
    let match = { type: 'other', format: 'other', intent: 'informational' };
    
    for (const [domain, label] of Object.entries(DOMAIN_MAP)) {
        if (hostname.includes(domain)) {
            match = label;
            break;
        }
    }

    return {
        urls: {
            url: url,
            type: match.type,
            content_format: match.format,
            tone: 'neutral_informational',
            promotional_intensity_score: 0,
            freshness_cue_strength: 0,
            is_current_year_2026: 0,
            readability_score: 5,
            heading_density: 0,
            has_tables: 0,
            has_numbered_lists: 0,
            has_bullet_points: 0,
            has_pros_cons: 0,
            has_clear_authorship: 0,
            has_sources_or_citations: hostname.includes('wikipedia') ? 1 : 0,
            listicle_has_ranked_order: 0,
            expertise_signal_score: hostname.includes('wikipedia') ? 5 : 3,
            spamminess_score: 0,
            primary_intent: match.intent,
            is_vendor_owned: (hostname.includes('apple') || hostname.includes('microsoft') || hostname.includes('google')) ? 1 : 0
        }
    };
}

async function main() {
    if (!fs.existsSync(CONFIG.skippedQueuePath)) {
        console.error("Queue file not found.");
        return;
    }

    const urls = JSON.parse(fs.readFileSync(CONFIG.skippedQueuePath, 'utf8'));
    console.log(`🏷️ Heuristic Labeler: Processing ${urls.length} skipped URLs...`);

    for (const url of urls) {
        try {
            const response = getHeuristicLabel(url);
            const result = {
                url,
                ok: true,
                response,
                model: CONFIG.model,
                timestamp: new Date().toISOString(),
                note: "Heuristically labeled (skipped domain)"
            };
            fs.appendFileSync(CONFIG.outJsonlPath, JSON.stringify(result) + '\n');
        } catch (err) {
            console.error(`❌ Failed ${url}: ${err.message}`);
        }
    }

    console.log("✅ Heuristic labeling complete.");
}

main().catch(console.error);
