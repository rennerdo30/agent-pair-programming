# Contributing to Pair Desk

Thanks for helping. Bug reports, ideas and pull requests are all welcome.

## Ground rules

- **Standard library only.** The desk, the CLI, the MCP server and the installers run on a plain
  Python 3.11+ with no packages. Please do not add runtime dependencies.
- **No build step, no network.** The web UI is plain HTML, CSS and ES modules served by the desk.
  No CDN, no web fonts from the internet, no telemetry.
- **Local first and safe by default.** The server binds `127.0.0.1` unless the user passes
  `--lan`. Changes that widen what the desk accepts from the network need a clear reason and tests.
- **Game-agnostic.** Pair Desk knows nothing about a particular game or engine. Location commands
  are the game's own text; seeds are optional.
- **Agents never give the owner's verdict.** Nothing an agent can call may mark an item `passed`.
- **Cross-platform.** Windows, macOS and Linux. Start the desk through `bin/pair-desk` /
  `bin/pair-desk.cmd` rather than assuming `python` or `python3` exists.

## Development setup

```
git clone https://github.com/rennerdo30/agent-pair-programming
cd agent-pair-programming
python desk.py --data /tmp/pd-dev serve --open        # a throwaway data folder
python scripts/demo-desk.py --data /tmp/pd-demo       # or start from sample data
```

Use a throwaway `--data` folder (or `PAIR_DESK_DATA`) while developing, so your real desk is
never touched. To try your checkout as the Claude Code plugin:
`claude --plugin-dir /path/to/agent-pair-programming`.

## Checks

```
python -m unittest discover -s tests      # the whole suite; must pass on Windows, macOS and Linux
python scripts/smoke.py                   # a real server process end to end
claude plugin validate .                  # the marketplace manifest
claude plugin validate .claude-plugin/plugin.json
```

UI changes: run the browser check against a throwaway desk (needs Node 22+ and Chrome or Edge):

```
python desk.py --data /tmp/pd-ui serve --detach --port 8799
node scripts/ui-check.mjs http://127.0.0.1:8799 ui-shots
python desk.py --data /tmp/pd-ui stop
```

To refresh the README screenshots, fill the throwaway desk with `scripts/demo-desk.py` first and
pass `mygame` as the third argument; copy the `readme-*.png` files into `docs/images/` (keep each
under about 300 KB).

## Pull requests

- One topic per pull request, with tests for new behaviour and fixed bugs.
- Update `README.md` when behaviour, commands, the HTTP API or the data model change, and add a
  line under *Unreleased* in `CHANGELOG.md`.
- Keep example data neutral (the `mygame` / `MG` example project) and never commit desk data,
  logs or screenshots of a real project.
- Bump the version in `pair_desk/__init__.py`, `.claude-plugin/plugin.json` and
  `.claude-plugin/marketplace.json` together, only when cutting a release.

## Reporting security issues

Please do not open a public issue for a vulnerability; see [SECURITY.md](SECURITY.md).

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By taking part you agree to
uphold it.
