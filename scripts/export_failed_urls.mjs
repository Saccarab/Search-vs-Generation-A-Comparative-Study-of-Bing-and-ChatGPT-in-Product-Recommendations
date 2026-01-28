import fs from 'fs';
import path from 'path';

const URL_MAPPING_FILE = path.join(process.cwd(), 'data', 'ingest', 'gemini_urls_master.json');
const OUTPUT_CSV = path.join(process.cwd(), 'data', 'ingest', 'failed_urls_for_extension.csv');

function exportFailedUrls() {
    if (!fs.existsSync(URL_MAPPING_FILE)) {
        console.error('❌ Master URL file not found.');
        return;
    }

    const urlMap = JSON.parse(fs.readFileSync(URL_MAPPING_FILE, 'utf-8'));
    const failedUrls = [];

    Object.values(urlMap).forEach(entry => {
        // Correct check for failures:
        // 1. If 'error' field exists
        // 2. If 'status' is not 200 (and not undefined, assuming 0 or null for failure)
        // 3. If 'char_count' is 0
        if (entry.error || (entry.status && entry.status !== 200) || entry.charCount === 0) {
            // Use resolvedUri if available, otherwise fallback to url or originalUri
            const urlToFetch = entry.resolvedUri || entry.url || entry.originalUri;
            if (urlToFetch) {
                failedUrls.push(urlToFetch);
            }
        }
    });

    if (failedUrls.length === 0) {
        console.log('✨ No failed URLs found! Everything was ingested successfully.');
        return;
    }

    // Create CSV content (header + rows)
    const csvContent = 'url\n' + failedUrls.map(url => `"${url}"`).join('\n');
    fs.writeFileSync(OUTPUT_CSV, csvContent);

    console.log(`✅ Exported ${failedUrls.length} failed URLs to: ${OUTPUT_CSV}`);
    console.log('👉 Load this file into your "URL Content Fetcher" Chrome Extension.');
}

exportFailedUrls();
