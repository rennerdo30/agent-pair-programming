"""Which project does a working directory belong to?

Two ways to link a repo to a project, checked in this order:
1. a `.pair-desk.json` file in the repo (or any parent folder): {"project": "mygame"}
2. `projects.json` in the data folder: {"/path/to/mygame": "mygame", ...}
   (`python desk.py link --project mygame --path /path/to/mygame` writes it)
"""

from __future__ import annotations

import json
import os
from pathlib import Path

MARKER = ".pair-desk.json"
LINKS_FILE = "projects.json"


def _norm(p: str | os.PathLike) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(p))).rstrip("\\/")


def _variants(p: str | os.PathLike) -> set[str]:
    out = {_norm(p)}
    try:
        out.add(_norm(Path(p).resolve()))
    except OSError:
        pass
    return out


def find_marker(start: str | os.PathLike) -> tuple[Path, dict] | None:
    try:
        here = Path(os.path.abspath(start))
    except (OSError, ValueError):
        return None
    for folder in (here, *here.parents):
        f = folder / MARKER
        try:
            if f.is_file():
                data = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("project"):
                    return f, data
        except (OSError, ValueError):
            continue
    return None


def load_links(data_dir: Path) -> dict[str, str]:
    f = Path(data_dir) / LINKS_FILE
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if isinstance(data, dict) and isinstance(data.get("links"), dict):
        data = data["links"]
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items() if isinstance(v, str)}


def save_link(data_dir: Path, path: str | os.PathLike, slug: str) -> Path:
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    links = load_links(data_dir)
    target = os.path.abspath(os.fspath(path))
    links = {k: v for k, v in links.items() if _norm(k) != _norm(target)}
    links[target] = slug
    f = data_dir / LINKS_FILE
    f.write_text(json.dumps(links, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return f


def resolve_project(data_dir: Path, cwd: str | os.PathLike | None = None) -> str | None:
    cwd = cwd or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    marker = find_marker(cwd)
    if marker:
        return str(marker[1]["project"]).strip().lower()
    best: tuple[int, str] | None = None
    here = _variants(cwd)
    for path, slug in load_links(data_dir).items():
        for base in _variants(path):
            for h in here:
                if h == base or h.startswith(base + os.sep):
                    if best is None or len(base) > best[0]:
                        best = (len(base), slug)
    return best[1] if best else None
