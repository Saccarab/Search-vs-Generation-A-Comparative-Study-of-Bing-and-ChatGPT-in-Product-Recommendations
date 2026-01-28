import express from 'express';
import path from 'path';
import open from 'open';
import fs from 'fs';

const app = express();
const PORT = 3000;
const ROOT_DIR = process.cwd();
const APP_DIR = path.join(ROOT_DIR, 'tools', 'GeminiVizApp');

// Serve static files from the app directory
app.use(express.static(APP_DIR));

// Endpoint to get the master bundle directly
app.get('/api/bundle', (req, res) => {
    const bundlePath = path.join(APP_DIR, 'data', 'master_bundle.json');
    if (fs.existsSync(bundlePath)) {
        res.sendFile(bundlePath);
    } else {
        res.status(404).send('Bundle not found. Run node scripts/build_viz_bundle.mjs first.');
    }
});

app.listen(PORT, () => {
    console.log(`\n🚀 Gemini Grounding Viz App is running!`);
    console.log(`🔗 URL: http://localhost:${PORT}`);
    console.log(`\nPress Ctrl+C to stop the server.`);
    
    // Automatically open the browser
    open(`http://localhost:${PORT}`);
});
