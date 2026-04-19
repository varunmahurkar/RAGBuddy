/**
 * screenshot.js — Capture all RAGBuddy pages for visual QA.
 *
 * Usage:
 *   node tools/screenshot.js
 *
 * Requires: npm install puppeteer  (from O:/RAGBuddy/)
 * Requires: dev server running at http://localhost:8000
 *
 * Output: O:/RAGBuddy/screenshots/{page}.png
 */
const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

const BASE_URL = 'http://localhost:8000';
const OUT_DIR = path.join(__dirname, '..', 'screenshots');

const PAGES = [
  { name: 'chat',    url: `${BASE_URL}/`,        wait: 'networkidle2' },
  { name: 'upload',  url: `${BASE_URL}/upload`,   wait: 'networkidle2' },
  { name: 'kb',      url: `${BASE_URL}/kb`,        wait: 'networkidle2' },
  { name: 'history', url: `${BASE_URL}/history`,   wait: 'networkidle2' },
];

async function run() {
  // Check server is up
  try {
    const http = require('http');
    await new Promise((resolve, reject) => {
      http.get(`${BASE_URL}/`, (res) => {
        res.statusCode === 200 ? resolve() : reject(new Error(`HTTP ${res.statusCode}`));
      }).on('error', reject);
    });
  } catch (e) {
    console.error('ERROR: Dev server not reachable at', BASE_URL);
    console.error('Run: python -m uvicorn main:app --port 8000  (from backend/)');
    process.exit(1);
  }

  fs.mkdirSync(OUT_DIR, { recursive: true });

  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
    defaultViewport: { width: 1440, height: 900 },
  });

  const page = await browser.newPage();

  // Suppress browser console noise
  page.on('console', () => {});

  for (const p of PAGES) {
    console.log(`Capturing: ${p.name} (${p.url})`);
    try {
      await page.goto(p.url, { waitUntil: p.wait, timeout: 15000 });
      // Wait for Alpine.js to initialize and HTMX to load fragments
      await new Promise(r => setTimeout(r, 1200));
      const file = path.join(OUT_DIR, `${p.name}.png`);
      await page.screenshot({ path: file, fullPage: false });
      console.log(`  Saved → ${file}`);
    } catch (err) {
      console.error(`  Failed to capture ${p.name}:`, err.message);
    }
  }

  await browser.close();
  console.log('\nDone. Screenshots in:', OUT_DIR);
}

run().catch(console.error);
