import { readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { execFileSync } from 'node:child_process';
import { validateTheme, assetTypes } from '../agora/core.mjs';
export function bundleTheme(root, commit) { const files = {}; function walk(dir) { for (const f of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, f.name);
    if (f.isSymbolicLink())
        throw Error('Symlinks forbidden');
    if (f.isDirectory())
        walk(path);
    else {
        const ext = path.split('.').pop(), type = assetTypes[ext];
        files[relative(root, path)] = type ? { base64: readFileSync(path).toString('base64'), type } : readFileSync(path, 'utf8');
    }
} } walk(root); return validateTheme({ commit, files }); }
if (process.argv[1]?.endsWith('bundle-theme.mjs')) {
    const commit = process.argv[3] || execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
    writeFileSync(process.argv[4] || 'agora/theme-bundle.json', JSON.stringify(bundleTheme(process.argv[2] || 'theme', commit)));
}
