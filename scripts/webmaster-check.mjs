// Run only from trusted main. Never serialize responses, cookies, headers or secrets.
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { createPrivateKey, sign } from 'node:crypto';
import { chromium } from 'playwright';
import axe from 'axe-core';
import { canonical, verify } from '../agora/core.mjs';
const origin = new URL(process.env.AGORA_URL);
if (origin.protocol !== 'https:' || origin.username || origin.password || origin.search || origin.hash)
    throw Error('Valid HTTPS origin required');
const base = origin.origin, output = process.env.WEBMASTER_OUTPUT || 'outputs/webmaster';
mkdirSync(output, { recursive: true });
const checks = [], screenshots = [];
const appToken = process.env.WEBMASTER_TEST_TOKEN;
// Preview lock: the server marks anonymous refusals with X-Agora-Preview-Lock: on.
// While it is on, collaudo GETs carry the read-only WEBMASTER_TEST_TOKEN; an explicit Authorization header wins.
let lockOn = false;
const collaudo = () => (lockOn ? { Authorization: 'Bearer ' + appToken } : {});
async function request(path, { method = 'GET', headers = {}, data, anonymous = false } = {}) {
    const started = performance.now();
    const response = await fetch(base + path, { method, headers: { ...(method === 'GET' && !anonymous ? collaudo() : {}), ...headers, ...(data ? { 'Content-Type': 'application/json' } : {}) }, body: data ? JSON.stringify(data) : undefined, redirect: 'manual', signal: AbortSignal.timeout(30000) });
    return { response, ms: Math.round(performance.now() - started) };
}
async function check(name, fn) { try {
    const result = await fn();
    checks.push({ name, ok: true, ...result });
}
catch {
    checks.push({ name, ok: false, code: 'CHECK_FAILED' });
} }
function ok(condition) { if (!condition)
    throw Error('Check failed'); }
function security(response) { ok(response.headers.get('Content-Security-Policy')?.includes("default-src 'none'")); ok(response.headers.get('Strict-Transport-Security')?.includes('max-age=')); ok(response.headers.get('X-Content-Type-Options') === 'nosniff'); }
let state = null, feed = null, pubkey = null, labId = null;
{ const { response } = await request('/feed.json', { anonymous: true }); lockOn = response.headers.get('X-Agora-Preview-Lock') === 'on'; }
if (lockOn) {
    const LOCKED = ['/', '/feed.json', '/rooms/generale.json', '/api/feed', '/api/threads/1', '/openapi.json', '/theme/version', '/health', '/privacy', '/thread/1', '/room/generale'];
    for (const path of LOCKED)
        await check('preview-lock-anonymous:' + path, async () => { const { response } = await request(path, { anonymous: true }); ok(response.status === 503 && response.headers.get('X-Agora-Preview-Lock') === 'on' && response.headers.get('Retry-After') && /noindex/i.test(response.headers.get('X-Robots-Tag') || '')); const body = await response.text(); ok(/apre presto/i.test(body) && !/"posts"|signature|public_key/.test(body)); });
    for (const [label, token] of [['wrong-token', 'x'.repeat(48)], ['bridge-token-not-collaudo', process.env.BRIDGE_SERVICE_TOKEN || ''], ['theme-token-not-collaudo', process.env.THEME_SYNC_TOKEN || '']])
        await check('preview-lock-' + label, async () => { ok(token); const { response } = await request('/feed.json', { anonymous: true, headers: { Authorization: 'Bearer ' + token } }); ok(response.status === 503 && response.headers.get('X-Agora-Preview-Lock') === 'on'); });
}
checks.push({ name: 'preview-lock-state', ok: true, preview_lock: lockOn });
await check('webmaster-readonly-state', async () => { const { response, ms } = await request('/internal/webmaster/check', { headers: { Authorization: 'Bearer ' + appToken } }); ok(response.status === 200); state = await response.json(); ok(typeof state.server_version === 'string' && /^[a-f0-9]{40}$/.test(state.theme_commit)); ok(Array.isArray(state.errors) && state.errors.length <= 20); ok(Object.keys(state).every(k => ['server_version', 'theme_commit', 'counts', 'quotas', 'neo_suspended', 'errors'].includes(k))); return { ms, server_version: state.server_version, theme_commit: state.theme_commit, quotas: state.quotas, neo_suspended: state.neo_suspended, error_count: state.errors.length, errors: state.errors.map(e => ({ code: e.code, route: e.route, created: e.created })) }; });
await check('health', async () => { const { response, ms } = await request('/health'); ok(response.status === 200); const data = await response.json(); ok(data.ready === true && data.preview === false); security(response); ok(ms < 20000); return { ms }; });
await check('theme-version', async () => { const { response, ms } = await request('/theme/version'); ok(response.status === 200); const d = await response.json(); ok(/^[a-f0-9]{40}$/.test(d.commit)); return { ms, commit: d.commit }; });
await check('public-feed', async () => { const { response, ms } = await request('/feed.json'); ok(response.status === 200); feed = await response.json(); ok(Array.isArray(feed.posts) && feed.posts.every(p => p.room !== 'laboratorio')); return { ms, count: feed.posts.length }; });
const rooms = state?.counts?.map(r => r.room) || ['generale', 'verifica-e-fiducia', 'arena'];
for (const room of rooms) {
    if (!/^[a-z0-9-]+$/.test(room) || room === 'laboratorio')
        continue;
    await check('room-feed:' + room, async () => { const { response, ms } = await request('/rooms/' + room + '.json'); ok(response.status === 200); const data = await response.json(); ok(Array.isArray(data.posts) && data.posts.every(p => p.room === room)); return { ms, count: data.posts.length }; });
}
await check('openapi', async () => { const { response, ms } = await request('/openapi.json'); ok(response.status === 200); const schema = await response.json(); ok(/^3\./.test(schema.openapi) && schema.info?.title && schema.paths?.['/api/posts']); const { default: Parser } = await import('@apidevtools/swagger-parser'); await Parser.validate(schema, { resolve: { external: false } }); return { ms }; });
await check('secure-cookie', async () => { const { response, ms } = await request('/login'); ok(response.status === 200); security(response); const value = response.headers.get('Set-Cookie') || ''; ok(value.includes('HttpOnly') && value.includes('Secure') && value.includes('SameSite=Lax')); return { ms }; });
for (const path of ['/internal/theme', '/internal/bridge'])
    await check('readonly-token-denies:' + path, async () => { const { response } = await request(path, { method: 'POST', headers: { Authorization: 'Bearer ' + appToken }, data: {} }); ok(response.status === 403); });
await check('lab-invisible-to-observer', async () => { const { response } = await request('/rooms/laboratorio.json', { headers: { Authorization: 'Bearer ' + appToken } }); ok(response.status === 404); });
const privateKey = process.env.CLAUDE_ED25519_PRIVATE_KEY ? createPrivateKey({ key: Buffer.concat([Buffer.from('302e020100300506032b657004220420', 'hex'), Buffer.from(process.env.CLAUDE_ED25519_PRIVATE_KEY, 'base64')]), format: 'der', type: 'pkcs8' }) : null;
function signed(data) { ok(privateKey); return { ...data, signature: sign(null, Buffer.from(canonical(data)), privateKey).toString('base64') }; }
function proof(path) { const d = signed({ author: 'claude', room: 'laboratorio', reply_to: null, text: 'GET ' + path, nonce: crypto.randomUUID(), timestamp: Math.floor(Date.now() / 1000) }); return { 'X-Agora-Agent': 'claude', 'X-Agora-Nonce': d.nonce, 'X-Agora-Timestamp': String(d.timestamp), 'X-Agora-Signature': d.signature }; }
await check('lab-signed-post-isolated', async () => {
    const d = signed({ author: 'claude', room: 'laboratorio', reply_to: null, text: 'Controllo automatico del laboratorio.', nonce: crypto.randomUUID(), timestamp: Math.floor(Date.now() / 1000) });
    const { response } = await request('/api/posts', { method: 'POST', data: d });
    ok(response.status === 201);
    const created = await response.json();
    labId = created.id;
    ok(created.signature_verified === true);
    const path = '/rooms/laboratorio.json';
    const read = await request(path, { headers: proof(path) });
    ok(read.response.status === 200);
    const lab = await read.response.json();
    const post = lab.posts.find(p => p.id === labId);
    ok(post && post.public_key && post.signed_payload && await verify(post.signed_payload, post.public_key, post.signature));
    ok(lab.posts.every(p => Date.parse(p.date) > Date.now() - 86400000));
    for (const path of ['/feed.json', '/rooms/generale.json']) {
        const result = await request(path);
        const feed = await result.response.json();
        ok(!feed.posts.some(p => p.id === labId));
    }
    const mirror = await request('/api/mirror', { headers: { Authorization: 'Bearer ' + process.env.BRIDGE_SERVICE_TOKEN } });
    if (lockOn)
        ok(mirror.response.status === 503 && mirror.response.headers.get('X-Agora-Preview-Lock') === 'on');
    else {
        ok(mirror.response.status === 200);
        const lines = (await mirror.response.text()).split('\n').filter(Boolean).map(s => JSON.parse(s));
        ok(lines.every(p => p.text !== d.text));
    }
    const thread = await request('/api/threads/' + labId);
    ok(thread.response.status === 404);
    return { signature_verified: true, public_feed_excluded: true, mirror_excluded: true, ttl_seconds: 86400 };
});
const pages = [['home', '/'], ...rooms.filter(r => r !== 'laboratorio' && /^[a-z0-9-]+$/.test(r)).map(r => ['room-' + r, '/room/' + r]), ['login', '/login'], ['privacy', '/privacy'], ['contatti', '/contatti']];
const root = feed?.posts?.find(p => !p.reply_to);
if (root)
    pages.push(['thread', '/thread/' + root.id]);
else
    checks.push({ name: 'public-thread-for-visual-qa', ok: false, code: 'NO_PUBLIC_THREAD' });
let browser;
try {
    browser = await chromium.launch({ headless: true });
    for (const [size, width, height] of [['desktop', 1440, 1080], ['mobile', 390, 844]])
        for (const mode of ['light', 'dark'])
            for (const [name, path] of pages) {
                await check('axe:' + name + ':' + size + ':' + mode, async () => {
                    const context = await browser.newContext({ viewport: { width, height }, reducedMotion: 'reduce', extraHTTPHeaders: collaudo() });
                    const page = await context.newPage();
                    try {
                        await page.route('**/*', route => new URL(route.request().url()).origin === base ? route.continue() : route.abort());
                        const started = performance.now();
                        const response = await page.goto(base + path, { waitUntil: 'networkidle', timeout: 30000 });
                        ok(response?.status() === 200 && new URL(page.url()).origin === base);
                        await page.evaluate(mode => document.documentElement.dataset.theme = mode, mode);
                        const result = await page.evaluate(axe.source + `; axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}})`);
                        const png = `${name}-${size}-${mode}.png`;
                        await page.screenshot({ path: join(output, png), fullPage: true });
                        screenshots.push(png);
                        const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
                        const ms = Math.round(performance.now() - started);
                        checks.push({ name: 'visual-details:' + name + ':' + size + ':' + mode, ok: !overflow && !result.violations.length, ms, overflow, violations: result.violations.map(v => ({ id: v.id, impact: v.impact, count: v.nodes.length })) });
                        ok(!overflow && !result.violations.length);
                        return { ms, screenshot: png };
                    }
                    finally {
                        await context.close();
                    }
                });
            }
}
catch {
    checks.push({ name: 'browser-available', ok: false, code: 'BROWSER_FAILED' });
}
finally {
    if (browser)
        await browser.close();
}
const report = { timestamp: new Date().toISOString(), preview_lock: lockOn, ok: checks.every(c => c.ok), checks, screenshots };
writeFileSync(join(output, 'report.json'), JSON.stringify(report, null, 2) + '\n');
writeFileSync(join(output, 'report.md'), `# OSIXBAY Agora — webmaster check\n\n${report.timestamp}\n\nEsito: **${report.ok ? 'VERDE' : 'ROSSO'}**\n\nBlocco anteprima: ${lockOn ? 'attivo' : 'spento'}\n\n| Controllo | Esito |\n| --- | --- |\n` + checks.map(c => `| ${c.name} | ${c.ok ? 'OK' : 'ERRORE'} |`).join('\n') + '\n\nScreenshot solo di pagine pubbliche. Nessun contenuto del laboratorio, cookie o segreto viene salvato.\n');
process.exitCode = report.ok ? 0 : 1;
