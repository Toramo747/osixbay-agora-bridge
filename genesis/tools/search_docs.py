#!/usr/bin/env python3
"""Interrogazione da terminale della biblioteca genesis-godot.

Uso:
  python3 genesis/tools/search_docs.py "GODOT: classe TileMapLayer"
  python3 genesis/tools/search_docs.py cerca procedural noise          (senza prefisso = GODOT: <op> ...)
  python3 genesis/tools/search_docs.py --json "GODOT: metodo AStarGrid2D.get_id_path"
  echo 'extends Node' | python3 genesis/tools/search_docs.py --stdin verifica
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from godot_api import GodotLibrary, to_text  # noqa: E402


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    as_json = '--json' in args
    use_stdin = '--stdin' in args
    args = [a for a in args if a not in ('--json', '--stdin')]
    line = ' '.join(args)
    if use_stdin:
        line = f"{line} {sys.stdin.read()}"
    if not line.strip():
        print(__doc__)
        return 2
    if not line.lstrip().upper().startswith('GODOT:'):
        line = 'GODOT: ' + line
    res = GodotLibrary().handle(line)
    print(json.dumps(res, ensure_ascii=False, indent=2) if as_json else to_text(res))
    return 0 if res['trovato'] else 1


if __name__ == '__main__':
    sys.exit(main())
