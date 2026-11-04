"""Esecuzione isolata del binario Godot fissato (headless), per validare esempi e controllare codice.

Isolamento applicato:
- progetto temporaneo usa-e-getta (copie dei file, mai il repository);
- HOME e cartelle XDG temporanee: user:// e la configurazione dell'editor finiscono lì;
- variabili d'ambiente ridotte al minimo (nessun segreto ereditato);
- timeout rigido;
- se disponibile `unshare`, nessuna rete (namespace di rete vuoto; con allow_loopback=True solo localhost).
Per il codice NON fidato si usa solo --check-only (analisi sintattica e di tipo, nessuna esecuzione).
"""
import shutil, subprocess, sys, tempfile, time
from pathlib import Path

from common import godot_binary

PROJECT = 'config_version=5\n\n[application]\n\nconfig/name="genesis-library-sandbox"\n'


def _netns_prefix(allow_loopback):
    if not shutil.which('unshare'):
        return [], 'nessun isolamento di rete (unshare assente)'
    try:
        subprocess.run(['unshare', '-rn', 'true'], check=True, capture_output=True, timeout=10)
    except Exception:
        return [], 'nessun isolamento di rete (unshare non permesso)'
    if allow_loopback:
        helper = Path(__file__).resolve().parent / 'netns_lo_exec.py'
        return ['unshare', '-rn', sys.executable, '-I', str(helper)], 'rete isolata: solo loopback'
    return ['unshare', '-rn'], 'rete isolata: nessuna interfaccia'


def run_godot(files, script, check_only=False, timeout=60, allow_loopback=False):
    """files: {percorso_relativo: contenuto str|bytes}; script: percorso relativo da eseguire/controllare."""
    binary = godot_binary()
    if binary is None:
        return {'eseguito': False, 'motivo': 'binario Godot assente: eseguire acquire_docs.py --with-godot'}
    with tempfile.TemporaryDirectory(prefix="genesis-library-") as tmp:
        tmp = Path(tmp)
        proj = tmp / 'project'
        proj.mkdir()
        (proj / 'project.godot').write_text(PROJECT)
        for rel, content in files.items():
            dest = (proj / rel).resolve()
            if not str(dest).startswith(str(proj.resolve())):
                raise ValueError(f'percorso non ammesso: {rel}')
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content.encode() if isinstance(content, str) else content)
        env = {'PATH': '/usr/bin:/bin', 'HOME': str(tmp / 'home'), 'XDG_DATA_HOME': str(tmp / 'xdg'),
               'XDG_CONFIG_HOME': str(tmp / 'xdg'), 'XDG_CACHE_HOME': str(tmp / 'xdg'), 'LANG': 'C.UTF-8'}
        prefix, net = _netns_prefix(allow_loopback)
        cmd = prefix + [str(binary), '--headless', '--path', str(proj)]
        cmd += ['--check-only', '--script', f'res://{script}'] if check_only else ['--script', f'res://{script}']
        t0 = time.time()
        try:
            p = subprocess.run(cmd, env=env, cwd=proj, capture_output=True, text=True, timeout=timeout)
            code, out = p.returncode, (p.stdout + p.stderr)
        except subprocess.TimeoutExpired as e:
            code, out = None, f'TIMEOUT dopo {timeout}s\n' + ((e.stdout or b'').decode(errors='replace') if isinstance(e.stdout, bytes) else (e.stdout or ''))
        out = out.replace(str(proj), '<progetto>').replace(str(tmp), '<tmp>')
        return {'eseguito': True, 'exit_code': code, 'output': out, 'secondi': round(time.time() - t0, 2),
                'isolamento_rete': net, 'binario': binary.name, 'modalita': 'check-only' if check_only else 'script'}
