import puppeteer from 'puppeteer';
import fs from 'fs';

const MAPPING_FILE = 'data/resolved_grounding_urls.json';

async function resolveFailedUrls() {
    const mapping = JSON.parse(fs.readFileSync(MAPPING_FILE, 'utf8'));
    const failed = Object.entries(mapping)
        .filter(([k, v]) => k === v)
        .map(([k]) => k);

    console.log(`🚀 Resolving ${failed.length} failed URLs with Puppeteer...\n`);

    const browser = await puppeteer.launch({
        headless: 'new',
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    let fixed = 0;
    
    for (let i = 0; i < failed.length; i++) {
        const url = failed[i];
        console.log(`[${i + 1}/${failed.length}] Opening: ...${url.substring(70, 100)}...`);
        
        const page = await browser.newPage();
        
        try {
            // Set a realistic user agent
            await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');
            
            // Navigate and wait for redirect
            await page.goto(url, { 
                waitUntil: 'domcontentloaded',
                timeout: 20000 
            });
            
            // Small delay to let any JS redirects happen
            await new Promise(r => setTimeout(r, 1500));
            
            const finalUrl = page.url();
            
            if (finalUrl !== url && !finalUrl.includes('vertexaisearch.cloud.google.com')) {
                mapping[url] = finalUrl;
                fixed++;
                console.log(`   ✅ -> ${finalUrl.substring(0, 70)}...`);
            } else {
                console.log(`   ⚠️ Still on redirect page or blocked`);
            }
        } catch (error) {
            console.log(`   ❌ Error: ${error.message.substring(0, 50)}`);
        }
        
        await page.close();
        
        // Save every 5 URLs
        if ((i + 1) % 5 === 0) {
            fs.writeFileSync(MAPPING_FILE, JSON.stringify(mapping, null, 2));
            console.log(`   💾 Checkpoint saved\n`);
        }
    }

    await browser.close();
    
    // Final save
    fs.writeFileSync(MAPPING_FILE, JSON.stringify(mapping, null, 2));
    console.log(`\n✨ Done! Resolved ${fixed} of ${failed.length} URLs`);
}

resolveFailedUrls().catch(console.error);
