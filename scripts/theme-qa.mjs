// CI only: execute trusted code, never the candidate's JS on the Node host.
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import http from 'node:http';
import { bundleTheme } from './bundle-theme.mjs';
import { render, assetContent } from '../agora/core.mjs';
import { rooms, posts } from '../agora/demo.mjs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const axe = require('axe-core');
const csstree = require('css-tree');
const bundle = bundleTheme(process.argv[2] || 'theme', process.env.THEME_SHA || '0'.repeat(40));
for (const [path, css] of Object.entries(bundle.files))
    if (path.endsWith('.css'))
        csstree.parse(css, { onParseError: e => { throw e; } });
const config = JSON.parse(bundle.files['theme.json']);
function lum(hex) { const c = hex.replace('#', '').match(/../g).map(x => parseInt(x, 16) / 255).map(x => x <= .04045 ? x / 12.92 : ((x + .055) / 1.055) ** 2.4); return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]; }
for (const [fg, bg] of [[config.colors.text, config.colors.background], [config.colors.dark_text, config.colors.dark_background]]) {
    const a = lum(fg), b = lum(bg);
    if ((Math.max(a, b) + .05) / (Math.min(a, b) + .05) < 4.5)
        throw Error('Insufficient configured contrast');
}
const contexts = { home: { home: true }, room: { room_page: true }, thread: { thread_page: true }, login: { login_page: true } };
const context = { menu: config.menu, room_count: String(rooms.length).padStart(2, '0'), site_name: config.name, title: config.home_title, description: config.home_text, demo: true, guest: true, csrf: 'fake-csrf', rooms, posts: posts.map(p => ({ ...p, initial: p.author[0], date: '29 ott, 10:00', agent: p.kind === 'agent', human: p.kind === 'human', sample: true })), commit: bundle.commit };
const server = http.createServer((req, res) => { const path = new URL(req.url, 'http://localhost').pathname; res.setHeader('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'none'; form-action 'none'; base-uri 'none'"); if (path === '/theme/css/tokens.css') {
    const c = config.colors;
    res.setHeader('Content-Type', 'text/css');
    res.end(`html{--bg:${c.background};--ink:${c.text};--green:${c.accent}}html[data-theme=dark]{--bg:${c.dark_background};--ink:${c.dark_text}}`);
    return;
} if (path.startsWith('/theme/')) {
    const name = path.slice(7);
    if (!Object.hasOwn(bundle.files, name)) {
        res.writeHead(404).end();
        return;
    }
    const content = assetContent(name, bundle.files[name]);
    res.setHeader('Content-Type', content.type);
    res.end(content.body);
    return;
} const name = path.slice(1) || 'home'; if (!contexts[name]) {
    res.writeHead(404).end();
    return;
} res.setHeader('Content-Type', 'text/html'); res.end(render(bundle.files[name + '.mustache'], { ...context, ...contexts[name] })); });
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({ headless: true });
const output = process.env.PREVIEW_DIR || 'outputs/theme-previews';
mkdirSync(output, { recursive: true });
try {
    for (const [size, width, height] of [['desktop', 1440, 1080], ['mobile', 390, 844]])
        for (const mode of ['light', 'dark'])
            for (const name of Object.keys(contexts)) {
                const page = await browser.newPage({ viewport: { width, height }, reducedMotion: 'reduce' });
                await page.route('**/*', route => { if (new URL(route.request().url()).origin === origin)
                    return route.continue(); return route.abort(); });
                await page.goto(origin + '/' + name);
                await page.evaluate(mode => document.documentElement.dataset.theme = mode, mode);
                const report = await page.evaluate(axe.source + `; axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}})`);
                if (report.violations.length) {
                    writeFileSync(join(output, `${name}-${size}-${mode}-axe.json`), JSON.stringify(report.violations, null, 2));
                    throw Error('Accessibility failure: ' + report.violations.map(x => x.id).join(', '));
                }
                const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
                if (overflow)
                    throw Error('Horizontal overflow');
                await page.emulateMedia({ reducedMotion: 'reduce' });
                await page.screenshot({ path: join(output, `${name}-${size}-${mode}.png`), fullPage: true });
                await page.close();
            }
}
finally {
    await browser.close();
    server.close();
}
