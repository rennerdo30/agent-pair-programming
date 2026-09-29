# Changelog

All notable changes to Pair Desk. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project uses [Semantic Versioning](https://semver.org/). The version lives in
`pair_desk/__init__.py`, `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`.

## [Unreleased]

### Changed

- The status follows the plan: a step started moves the issue to `in_progress`, the last step done or dropped moves it to `to_check`.

### Fixed

- Game commands passed to the CLI from Git Bash (`--command "/goto 1 2"`) no longer arrive as `C:/Program Files/Git/goto 1 2`.
- Unsized icons follow the text; the picked-up checkmark is no longer huge.

## [1.2.0] - 2026-09-29

### Added

- `pair-desk install | update | uninstall [claude codex opencode] [--yes] [--dry-run]`: one
  installer for all three tools. It detects which are installed, shows the exact steps, asks per
  tool, runs the official `claude plugin ...` commands and the Codex and opencode integration
  installers, then offers to link the current git repo to a desk project.
- Python packaging (`pyproject.toml`, standard library only), so the installer runs straight from
  GitHub with `uvx` or `pipx run`; `install.sh` and `install.ps1` bootstrap it with nothing but
  Python 3.11+.
- Cross-platform launchers `bin/pair-desk` (macOS, Linux, Git Bash) and `bin/pair-desk.cmd`
  (Windows): they pick a working Python 3.11+ (`python3`, `python`, `py -3` or
  `$PAIR_DESK_PYTHON`) and skip the Windows Store `python3` stub and old system Pythons.
- `scripts/demo-desk.py`: a throwaway desk with neutral sample data; `scripts/ui-check.mjs` takes
  the README screenshots from it.
- Agent formatting rules in the `pair-desk` skill and the MCP tool descriptions; a *Merged* filter.
- GitHub scaffolding: CI on Linux, macOS and Windows with Python 3.11 to 3.13, issue and pull
  request templates, contributing, security and conduct documents.

### Changed

- The plugin's MCP server and hooks start the desk through the launchers instead of `python`,
  which does not exist on many macOS and Linux machines.
- The Codex and opencode installers choose the Python command per OS (the launcher on macOS and
  Linux, `python` or `py -3` on Windows); `--python` still overrides.
- The example project in docs, skills and tests is a neutral `mygame` (`MyGame`, ids `MG-1`).
  World seeds stay an optional per-project setting.

## 1.1.0 - 2026-09-29

### Added

- **Plans** on every issue: ordered steps (`todo`, `doing`, `done`, `dropped`) with commits and
  notes, a verification line, progress in the list; `set_status` refuses `to_check` while steps
  are open.
- **Groups and merges:** "part of" links with child progress and a close offer; merging
  duplicates into one timeline (with unmerge); `suggest_groups` proposals.
- **Backlog:** size (S, M, L), milestone and a `parked` status; a Triage/Backlog switch grouped by
  area.
- **Handoff:** one versioned markdown document per project (state, where work stopped, verified,
  next step, traps) with history and diffs, in the web UI, CLI, HTTP API and MCP tools.
- **Live updates:** a Server-Sent Events stream fed by a database watcher, so writes from the
  game, the CLI, MCP tools or another tab appear within a second, highlighted.
- **Owner activity reaches agents:** a `UserPromptSubmit` hook with per-session cursors, and the
  MCP server as a Claude Code channel that pushes owner comments, verdicts, reports and status
  changes into running sessions. Per-project notify settings.
- **Codex and opencode integrations:** installers for the MCP server, skills, a Codex
  SessionStart hook and an opencode plugin that adds the desk summary to the system prompt.
- A draggable list/detail splitter; multi-select with *Merge into* and *Group under*.

### Changed

- The SessionStart summary also shows the handoff's next step and traps.
- Store schema v3, migrated in place on open.

## 1.0.0 - 2026-09-29

### Added

- A 100% local playtest and issue desk shared by a game owner and coding agents: one data folder
  with a SQLite file and attachments, several games at once.
- Web UI with no build step and no network access: filter chips with counts, triage order, a
  detail pane with the location card and *Send to game*, pasted and dropped screenshots, a
  lightbox, verdict buttons that walk the queue, keyboard control, light and dark themes, a phone
  layout.
- JSON HTTP API for the game (reports with screenshots, a once-only command queue with a
  10-minute expiry), bound to `127.0.0.1` unless `--lan`.
- CLI for agents and scripts, JSON import deduplicated by `external_ref`, export.
- A stdio MCP server; agents cannot mark anything passed.
- The Claude Code plugin: MCP server, skills (`pair-desk`, `serve`, `triage`) and a SessionStart
  summary.
- Optional world seeds on locations and a per-project default seed; attachments by local path
  for agents.

[1.2.0]: https://github.com/rennerdo30/agent-pair-programming/releases/tag/v1.2.0
