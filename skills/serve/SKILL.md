---
name: serve
description: Start the Pair Desk web UI in the background and print its URL. Use when the user wants to open the desk, see or triage playtest issues in the browser, or when the game needs the desk's HTTP API running.
---

# Start the Pair Desk web UI

The desk command is `pair-desk`: the plugin's `bin/pair-desk`, which is on the Bash tool's PATH
while the plugin is enabled. Elsewhere run it by path from the plugin root, two folders above
this skill's base directory: `"<plugin root>/bin/pair-desk"` in sh or Git Bash, or
`& "<plugin root>/bin/pair-desk.cmd"` in PowerShell.

1. Run, as one foreground command (it returns within a few seconds):

   ```
   pair-desk serve --detach
   ```

   It checks `http://127.0.0.1:8765/api/health` first and only starts a new server when none
   is running. The server keeps running after the command returns (a detached process; its log
   is `server.log` in the data folder). Add `--port N` for another port, `--open` to also open
   the browser. Do not add `--lan` unless the user asks for access from other devices, and warn
   them that `--lan` has no authentication.

2. Print the URL it reports, e.g. `http://127.0.0.1:8765/`, and if a project is linked to the
   current repo, the direct link `http://127.0.0.1:8765/#/<project>`.

To stop it later: `pair-desk stop`.

If the port is taken by something else, say so and offer `--port 8766`. Never start the server
without `--detach` from a tool call: it would block the session.
