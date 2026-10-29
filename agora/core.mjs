// No eval, executable templates, HTML from users, or ambient context.
export function escape(value) { return String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
export function render(source, data) {
    const pattern = /{{([\s\S]*?)}}/g;
    const root = [], stack = [{ name: null, nodes: root }];
    let end = 0, match;
    while ((match = pattern.exec(source))) {
        const current = stack.at(-1);
        current.nodes.push({ literal: source.slice(end, match.index) });
        const tag = match[1];
        if (!/^[#/]?[a-zA-Z_][\w]*$/.test(tag) || source[match.index + 2] === '{')
            throw Error('Unsupported template syntax');
        if (tag[0] === '#') {
            const node = { section: tag.slice(1), nodes: [] };
            current.nodes.push(node);
            stack.push({ name: node.section, nodes: node.nodes });
        }
        else if (tag[0] === '/') {
            if (stack.length === 1 || current.name !== tag.slice(1))
                throw Error('Mismatched section');
            stack.pop();
        }
        else
            current.nodes.push({ variable: tag });
        end = pattern.lastIndex;
    }
    if (stack.length !== 1 || source.slice(end).includes('{{'))
        throw Error('Unclosed template');
    root.push({ literal: source.slice(end) });
    const resolve = (scope, key) => Object.hasOwn(scope, key) && !['__proto__', 'prototype', 'constructor'].includes(key) ? scope[key] : '';
    function draw(nodes, scope) {
        return nodes.map(n => {
            if ('literal' in n)
                return n.literal;
            if (n.variable)
                return escape(resolve(scope, n.variable));
            const value = resolve(scope, n.section);
            return Array.isArray(value) ? value.map(item => draw(n.nodes, { ...scope, ...item })).join('') : value ? draw(n.nodes, scope) : '';
        }).join('');
    }
    return draw(root, data);
}
export const assetTypes = { png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', webp: 'image/webp', woff: 'font/woff', woff2: 'font/woff2' };
export function assetContent(path, value) {
    if (typeof value === 'string')
        return { body: value, type: path.endsWith('.css') ? 'text/css' : path.endsWith('.js') ? 'text/javascript' : path.endsWith('.svg') ? 'image/svg+xml' : 'text/plain' };
    const ext = path.split('.').pop(), type = assetTypes[ext];
    if (!path.startsWith('assets/') || !type || !value || typeof value.base64 !== 'string' || value.base64.length > 2000000 || value.type !== type)
        throw Error('Invalid binary asset');
    const bytes = Uint8Array.from(atob(value.base64), x => x.charCodeAt(0));
    const magic = String.fromCharCode(...bytes.slice(0, 12));
    if ((ext === 'png' && !magic.startsWith('\x89PNG')) || (['jpg', 'jpeg'].includes(ext) && !(bytes[0] === 255 && bytes[1] === 216)) || (ext === 'webp' && !(magic.startsWith('RIFF') && magic.endsWith('WEBP'))) || (ext === 'woff2' && !magic.startsWith('wOF2')) || (ext === 'woff' && !magic.startsWith('wOFF')))
        throw Error('Invalid asset header');
    return { body: bytes, type };
}
export function validateTheme(bundle) {
    if (!bundle || !/^[a-f0-9]{40}$/.test(bundle.commit))
        throw Error('A full commit SHA is required');
    const allowed = /^(theme\.json|(?:home|room|thread|login|admin|page)\.mustache|(?:css|js|assets|pages)\/[a-zA-Z0-9_./-]+)$/;
    let size = 0;
    for (const [path, value] of Object.entries(bundle.files || {})) {
        if (!allowed.test(path) || path.includes('..'))
            throw Error('Forbidden theme path');
        if (typeof value !== 'string') {
            assetContent(path, value);
            size += value.base64.length;
            continue;
        }
        size += value.length;
        if (/javascript:|data:|https?:\/\/|\/\/[^\s<]|@import|url\(\s*["']?(?:data:|javascript:)|<iframe|<object|<embed|<base|<form[^>]*action\s*=\s*["'](?!\/)|\bon\w+\s*=|<script(?!\s+src=["']\/theme\/js\/)/i.test(value.replace('xmlns="http://www.w3.org/2000/svg"', '')))
            throw Error('External resources or executable markup forbidden');
        if (path.endsWith('.mustache'))
            render(value, {});
    }
    if (size > 2500000)
        throw Error('Theme too large');
    const config = JSON.parse(bundle.files['theme.json']);
    for (const value of Object.values(config.colors || {}))
        if (!/^#[a-fA-F0-9]{6}$/.test(value))
            throw Error('Colors must be six-digit hex');
    for (const key of ['background', 'text', 'accent', 'dark_background', 'dark_text'])
        if (!config.colors?.[key])
            throw Error('Missing color');
    if (!Array.isArray(config.menu) || config.menu.length > 10 || config.menu.some(m => !/^\/(?:[a-z0-9/-]*)$/.test(m.href) || typeof m.label !== 'string'))
        throw Error('Menu must use local paths');
    for (const k of ['name', 'home_title', 'home_text'])
        if (typeof config[k] !== 'string')
            throw Error('Invalid configuration');
    for (const page of ['home', 'room', 'thread', 'login', 'admin', 'page'])
        if (!bundle.files[page + '.mustache'])
            throw Error('Missing template ' + page);
    return bundle;
}
export const canonical = (p) => JSON.stringify({ author: p.author, room: p.room, reply_to: p.reply_to ?? null, text: p.text, nonce: p.nonce, timestamp: p.timestamp });
export function decode64(s) {
    if (typeof s !== 'string' || s.length > 10000)
        throw Error('Invalid base64');
    return Uint8Array.from(atob(s), x => x.charCodeAt(0));
}
export async function verify(p, publicKey, signature) {
    try {
        const key = await crypto.subtle.importKey('raw', decode64(publicKey), { name: 'Ed25519' }, false, ['verify']);
        return await crypto.subtle.verify('Ed25519', key, decode64(signature), new TextEncoder().encode(canonical(p)));
    }
    catch {
        return false;
    }
}
export function limits(name, history, now) {
    if (history.some(t => now - t < 30))
        return 'Attendi 30 secondi';
    if (history.filter(t => t >= Math.floor(now / 86400) * 86400).length >= (name === 'neo' ? 40 : 20))
        return 'Limite giornaliero raggiunto';
    return null;
}
export const hash = async (s) => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s)))).map(x => x.toString(16).padStart(2, '0')).join('');
export const token = () => crypto.randomUUID() + crypto.randomUUID();
