import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { chromium } from '../website/node_modules/playwright/index.mjs';

const BASE_URL = process.env.BEAGLE_SITE_CAPTURE_BASE_URL || 'http://127.0.0.1:4173';
const OUTPUT_DIR = resolve(process.cwd(), process.env.BEAGLE_DOCS_SITE_DIR || 'public-site/assets/img/docs/site');

const SHOTS = [
  { name: 'site-home.png', path: '/' },
  { name: 'site-download.png', path: '/download/' },
  { name: 'site-docs-hub.png', path: '/docs/' },
  { name: 'site-getting-started.png', path: '/docs/getting-started/' },
  { name: 'site-webui-guide.png', path: '/docs/webui/' },
  { name: 'site-contact.png', path: '/contact/' }
];

mkdirSync(OUTPUT_DIR, { recursive: true });

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1600, height: 1100 } });
const page = await context.newPage();

for (const shot of SHOTS) {
  await page.goto(BASE_URL + shot.path, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await page.waitForTimeout(900);
  await page.screenshot({ path: resolve(OUTPUT_DIR, shot.name), fullPage: true });
}

await context.close();
await browser.close();
console.log('Captured', SHOTS.length, 'site screenshots in', OUTPUT_DIR);
