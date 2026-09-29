---
name: triage
description: Summarise new playtest reports and failed checks from Pair Desk for the current project, so the user can decide what to work on. Use when the user asks what is new on the desk, what the owner reported, what failed, or wants a triage pass.
---

# Triage the desk

Read-only unless the user asks for changes.

1. Resolve the project: `list_projects` (the `pair-desk` MCP tools) shows `linked_project` for
   this repo. If none is linked and there are several projects, ask which one, or use the
   argument the user gave.
2. `list_issues` with `status: "failed"`, then with `status: "reported"`, `full: true`.
   Also note the `status_counts` (how many `to_check` are waiting for the owner).
3. For every failed check, `get_issue` and read the latest comment with verdict `failed`:
   that is the owner's description of what is still wrong. Note screenshots
   (attachments) exist; you cannot see them, so say "has N screenshots" and give the
   web link `http://127.0.0.1:8765/#/<project>/<ID>`.
4. Report, in this order, grouped by area:
   - **Failed checks** (regressions of claimed work): id, title, the owner's complaint in one
     line, the location command if any.
   - **New reports**: id, kind, priority, title, one-line gist; flag duplicates of each other
     or of open work, and anything P0/P1.
   - **Waiting for the owner**: just the count of `to_check`.
   - **Suggested order of work**: failed checks first, then P0/P1 reports, with a reason each.
5. `suggest_groups` for the project: list its proposals (merges of duplicates, groups under a
   parent) with their reasons, so the owner can confirm them in one step.
6. Offer, do not do: moving reports to `open` or `in_progress`, commenting, merging or grouping.
   Never set `passed`.

If the MCP tools are unavailable, use the desk CLI: `pair-desk list --status failed,reported --json`
and `pair-desk show <ID> --json` (`pair-desk` is the plugin's `bin/pair-desk`, on the Bash tool's
PATH while the plugin is enabled; by path it is `"<plugin root>/bin/pair-desk"`, the plugin root
being two folders above this skill).
