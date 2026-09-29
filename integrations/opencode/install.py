"""Install Pair Desk into opencode (global config).

    python integrations/opencode/install.py              # install or update
    python integrations/opencode/install.py --dry-run    # show what would change
    python integrations/opencode/install.py --uninstall  # remove only what this installer added

What it sets up:
- `mcp.pair-desk` in the global config (`~/.config/opencode/opencode.jsonc` or `opencode.json`,
  whichever exists; `opencode.json` is created otherwise): a local stdio server
  `[<desk>, "mcp"]`, where `<desk>` is how this machine starts desk.py
  (integrations.common.desk_command): the `bin/pair-desk` launcher on macOS and Linux, `python`
  or `py -3` plus desk.py on Windows, or `--python X` plus desk.py when given.
- `~/.config/opencode/plugins/pair-desk.js`: a one-line re-export of
  `integrations/opencode/pair-desk-plugin.js`, which adds the Pair Desk rules and the
  session-start summary to the system prompt of sessions in linked folders and shows the summary
  as a toast.
- The skills `pair-desk`, `pair-desk-serve`, `pair-desk-triage` in `~/.agents/skills/` (a folder
  opencode reads, shared with the Codex installer), generated from this repo's `skills/`.

The config file gets a timestamped backup before every change and only the `pair-desk` entry is
touched. A `.jsonc` file is rewritten as plain JSON: comments are dropped (the backup keeps them)
and the installer says so. Re-running is a no-op when everything is current.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from integrations.common import (  # noqa: E402
    DESK_PY, SERVER_NAME, Report, agents_skills_dir, desk_command, fwd, install_skills, read_text,
    shell_line, strip_jsonc, uninstall_skills, update_config_file, write_text)

TOOL = "opencode"
PLUGIN_SRC = Path(os.path.abspath(__file__)).parent / "pair-desk-plugin.js"
PLUGIN_FILE = "pair-desk.js"
PLUGIN_MARK = "// Pair Desk plugin shim, managed by agent-pair-programming/integrations/opencode/install.py"


def config_dir() -> Path:
    env = os.environ.get("XDG_CONFIG_HOME")
    return (Path(env) if env else Path.home() / ".config") / "opencode"


def config_file(folder: Path) -> Path:
    for name in ("opencode.jsonc", "opencode.json"):
        if (folder / name).is_file():
            return folder / name
    return folder / "opencode.json"


def mcp_entry(prefix: list[str]) -> dict:
    return {"type": "local", "command": [*prefix, "mcp"], "enabled": True}


def load_config(text: str | None) -> tuple[dict, bool]:
    if not text or not text.strip():
        return {"$schema": "https://opencode.ai/config.json"}, False
    clean, had_comments = strip_jsonc(text)
    data = json.loads(clean)
    if not isinstance(data, dict):
        raise ValueError("the config is not a JSON object")
    return data, had_comments


def dump(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def merged_config(text: str | None, prefix: list[str]) -> tuple[str | None, bool]:
    """(new text or None when unchanged, whether comments get dropped)."""
    data, had_comments = load_config(text)
    mcp = data.get("mcp")
    if mcp is not None and not isinstance(mcp, dict):
        raise ValueError('"mcp" in the config is not an object')
    want = mcp_entry(prefix)
    if isinstance(mcp, dict) and mcp.get(SERVER_NAME) == want:
        return None, False
    data.setdefault("mcp", {})[SERVER_NAME] = want
    return dump(data), had_comments


def removed_config(text: str | None) -> tuple[str | None, bool]:
    if not text or not text.strip():
        return None, False
    data, had_comments = load_config(text)
    mcp = data.get("mcp")
    if not isinstance(mcp, dict) or SERVER_NAME not in mcp:
        return None, False
    del mcp[SERVER_NAME]
    if not mcp:
        del data["mcp"]
    return dump(data), had_comments


def shim_text(plugin_src: Path = PLUGIN_SRC) -> str:
    url = Path(os.path.abspath(plugin_src)).as_uri()
    return (f"{PLUGIN_MARK}\n"
            f"// Source: {fwd(plugin_src)} (edit there; uninstall with integrations/opencode/install.py --uninstall)\n"
            f'export {{ PairDeskPlugin }} from "{url}"\n')


def install_plugin(plugins_dir: Path, report: Report, force: bool = False) -> None:
    target = plugins_dir / PLUGIN_FILE
    old = read_text(target)
    new = shim_text()
    if old == new:
        report.note(f"plugin: up to date ({target})")
        return
    if old is not None and PLUGIN_MARK not in old and not force:
        report.note(f"plugin: {target} exists and was not written by Pair Desk; left alone (--force replaces it)")
        return
    report.change(f"write plugin {target}")
    if not report.dry_run:
        write_text(target, new)


def uninstall_plugin(plugins_dir: Path, report: Report) -> None:
    target = plugins_dir / PLUGIN_FILE
    old = read_text(target)
    if old is None:
        return
    if PLUGIN_MARK not in old:
        report.note(f"plugin: {target} was not written by Pair Desk; left alone")
        return
    report.change(f"remove plugin {target}")
    if not report.dry_run:
        target.unlink()


def run(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Install Pair Desk (MCP server, plugin, skills) into opencode.")
    ap.add_argument("--uninstall", action="store_true", help="remove what this installer added")
    ap.add_argument("--dry-run", action="store_true", help="show what would change, write nothing")
    ap.add_argument("--config-dir", type=Path, default=None,
                    help="opencode global config folder (default: $XDG_CONFIG_HOME/opencode or ~/.config/opencode)")
    ap.add_argument("--skills-dir", type=Path, default=None, help="skill folder (default: ~/.agents/skills)")
    ap.add_argument("--python", default=None,
                    help="Python command opencode runs desk.py with (default: the bin/pair-desk launcher on "
                         "macOS and Linux; python or py -3, whichever is a Python 3.11+, on Windows)")
    ap.add_argument("--desk", type=Path, default=DESK_PY, help="path to desk.py (default: this repo)")
    ap.add_argument("--no-skills", action="store_true", help="leave the skills alone")
    ap.add_argument("--no-plugin", action="store_true", help="leave the plugin alone")
    ap.add_argument("--force", action="store_true", help="replace a same-named plugin or skills not installed by Pair Desk")
    args = ap.parse_args(argv)

    folder = args.config_dir or config_dir()
    config = config_file(folder)
    skills_dir = args.skills_dir or agents_skills_dir()
    desk = fwd(args.desk)
    report = Report(dry_run=args.dry_run)
    try:
        text = read_text(config)
        if args.uninstall:
            new, had_comments = removed_config(text)
        else:
            if not Path(desk).is_file():
                print(f"error: {desk} does not exist", file=sys.stderr)
                return 1
            prefix = desk_command(desk, args.python)
            new, had_comments = merged_config(text, prefix)
    except ValueError as e:
        print(f"error: {config} could not be read as JSON ({e}); fix it first, nothing was changed", file=sys.stderr)
        return 1
    if new is not None and had_comments:
        report.note(f"note: {config.name} has comments; the rewritten file drops them (the backup keeps them)")
    update_config_file(config, new, report, "opencode MCP server")
    if args.uninstall:
        if not args.no_plugin:
            uninstall_plugin(folder / "plugins", report)
        if not args.no_skills:
            uninstall_skills(skills_dir, TOOL, report)
    else:
        if not args.no_plugin:
            install_plugin(folder / "plugins", report, force=args.force)
        if not args.no_skills:
            install_skills(skills_dir, TOOL, report, shell_line(prefix), force=args.force)
    report.print()
    if not args.uninstall and report.changed and not args.dry_run:
        print("Restart opencode to load it. Verify with: opencode mcp list")
    return 0


if __name__ == "__main__":
    sys.exit(run())
