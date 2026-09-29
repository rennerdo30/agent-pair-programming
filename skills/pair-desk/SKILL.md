---
name: pair-desk
description: How to work with Pair Desk, the game owner's local playtest desk, backlog and handoff. Use at the start of a session in a game repo (read the handoff, failed checks and new reports), before coding an issue (write its plan), while working (tick plan steps, post progress live), after a change the owner should verify in game (file a to_check item with a location command), when fixing something the owner reported, and before the session ends (update the handoff). Also use when the user mentions the desk, the handoff, the backlog, plans, playtest checks, reports, verdicts, "to check", "still broken", or a <channel source="pair-desk"> message arrives.
---

# Working with Pair Desk

Pair Desk is where the game owner and coding agents meet, and the one place the project's state
lives: the **handoff** (what to do right now, what will bite), the **backlog** (every open item,
sized and prioritised), a **plan** on every issue, and the playtest loop of **checks**, **reports**
and **verdicts**. The owner watches it live: everything you write appears in the web UI within a
second. Everything is local: one data folder, no server needed for agents.

Use the `pair-desk` MCP tools. If they are unavailable, the same operations exist as a CLI:
`pair-desk list|show|add|comment|status|plan|step|parent|merge|unmerge|suggest-groups|handoff ...`
(`--json` for machine-readable output). `pair-desk` is the plugin's `bin/pair-desk`, on the Bash
tool's PATH while the plugin is enabled; by path it is `"<plugin root>/bin/pair-desk"`
(`bin/pair-desk.cmd` from cmd or PowerShell), the plugin root being two folders above this skill.

The project is picked from the repo automatically when it is linked (a `.pair-desk.json` with
`{"project": "<slug>"}` in the repo root, or `pair-desk link --project <slug>`). Otherwise pass
`project`. `list_projects` shows what exists and what this repo is linked to.

## The loop

1. **Session start: read before you work.**
   - `get_handoff`: the last session's state, where work stopped, what is verified, the next
     step and the traps. The session-start summary shows its next step and traps already;
     read the whole thing.
   - `list_issues` with `status: "failed"`: checks the owner tried and found still broken.
     `get_issue` each one; the owner's latest comment (verdict `failed`) says what is wrong,
     often with screenshots. These come first: they are regressions of work already claimed done.
   - `list_issues` with `status: "reported"`: new reports from the owner or the game itself.
     Triage them with the user; move the ones you take on to `in_progress` with `set_status`.
   - The backlog is `list_issues` with `status: "open,in_progress"` and `sort: "backlog"`
     (priority, then size, then area). `parked` items are not now; leave them.
   - `to_check` items are waiting for the owner. Do not touch them unless you changed that code again.

2. **Plan before code.** Before you change code for an issue, write its plan with `set_plan`:
   ordered, concrete steps (each one a commit or a check you can tick) and a `verification`
   line saying what proves it works (a stage shot, a test, the in-game check). The owner sees it
   as a checklist above the timeline and may tick or comment on steps. Revise it with `set_plan`
   when the approach changes; steps with the same text keep their state.

3. **Post progress live, as you work.** The owner follows along in the desk, so keep the issue
   current instead of reporting at the end:
   - Mark the step you start `doing`, and tick it `done` with its commit hash as the commit
     lands: `update_step` (`index` 1 = first step), or `progress` which does a step change and a
     short comment in one cheap call.
   - Post a short progress comment when something notable happens (a finding, a blocker, a
     change of approach): `progress` with `text`, or `comment`.
   - A step you no longer need is `dropped`, with a note saying why. Never delete history.

4. **After you finish a change the owner should see in game, file a check** (or move the issue
   to `to_check`, see 5). `create_issue` (defaults: kind `check`, status `to_check`, source `agent`) with:
   - `title`: what to look at, phrased as the thing to verify ("Lava flows end in rounded tips").
   - `body` (markdown): what changed, what "correct" looks like, what would count as broken,
     and the commit hash. Short and concrete; the owner reads it standing in the game.
   - `command`: the game's own chat command text that takes the player to the spot. Make it
     precise, the way the game's `/where` writes it: position, height, camera, hour, weather,
     e.g. `/goto 1240 -380 42.5 yaw 90 pitch 8; /time 17:30; /weather rain`.
     Without it the owner has to hunt for the place. The owner can press "Send to game" and
     the running game executes it.
   - `location.seed` (only for games with generated worlds): the **world seed** the command is
     valid in, when a position only means something in one generated world. Use the project's
     `default_seed` (see below) unless the change needs another world; if you give none, the
     desk fills in the default for agent checks. The desk adds `seed N` to the first `/goto` it
     copies and sends, so the game can refuse to teleport into the wrong world.
   - `attachment_paths`: local screenshots (png, jpg, gif, webp) or PDFs to attach, absolute
     or relative to the repo. **Attach every screenshot you reference** in the body; a path
     written only as text (`docs/feedback/foo.webp`) is invisible to the owner in the desk.
     The same field works on `comment` and on each item of `import_checks`.
   - `area`, `priority`, `size` (S, M, L), `milestone`, `tags` as useful; `external_ref`: the
     TODO item title or commit hash. `import_checks` files many at once and skips any whose
     `external_ref` already exists, so re-running it is safe.

   - **The status follows the plan.** Marking a step `doing` (or `done`) on a reported, open,
     failed or waiting issue moves it to `in_progress`; the last open step done (or dropped)
     moves it to `to_check`. So always tick steps as you go: an issue whose steps stay `todo`
     looks untouched to the owner. Leave a step such as "build and stage shots" open while the
     change is not in a build yet, so the issue only reaches `to_check` when the owner can verify
     it. When the owner fails an issue, add the steps for the rework to its plan and tick them;
     it moves to `in_progress` and back to `to_check` by itself.

5. **Move an issue to `to_check` only when every plan step is `done` (or `dropped` with a
   note).** `set_status` refuses `to_check` while steps are still `todo` or `doing`. When you fix
   something the owner reported or failed: `comment` on it with what you changed (files, commit
   hash, what to look at), then `set_status` to `to_check`, with a location command on the issue
   if it lacks one. Do not open a second issue for the same thing.

6. **Never mark anything `passed`.** Only the owner gives that verdict, in the web UI. The MCP
   tools refuse `passed`. If you believe something is done, `to_check` is the right state.
   You may give `failed` with a comment when you reproduce a problem yourself.

7. **Before the session ends, and whenever a milestone lands, update the handoff.** Do not wait
   to be asked, and do not wait until a usage limit cuts you off. `update_handoff` replaces one
   section, `set_handoff` the whole document; every save is a new version the owner can diff.
   Sections:
   - **State**: what changed since the last handoff (commits by hash, one line each).
   - **Where work stopped**: the file, the function, the half-finished thought. Run `git status`
     first and account for everything in it: say exactly what is uncommitted, and where.
   - **Verified**: what the tests and checks actually reported, with counts, and what a green
     check does not prove.
   - **Next step**: the single next action and why.
   - **Traps**: what the next session would get wrong by default.
   Keep it current rather than complete: history lives in the issues and commits.

## How to write on the desk (formatting)

The owner reads the desk in a browser, often between play sessions. The desk renders markdown
(headings, lists, bold, `code`, fenced blocks, links, issue ids like MG-4 become links). A wall of
prose is unreadable there, so every comment, plan, body and handoff section is formatted:

- **Lead with the outcome in one line**, bold or as a `###` heading: what changed or what you
  found, and whether the owner has to do anything. Details follow below it.
- **One fact per bullet.** Never chain findings with `(1) ... (2) ...` or `;` in one paragraph.
  Enumerations become lists; causes, fixes and files each get their own list.
- **Short labelled blocks** instead of paragraphs, each on its own line, e.g.
  `**Cause:**`, `**Fix:**`, `**Files:**`, `**Verified:**`, `**Not verified:**`, `**Next:**`.
  Leave a blank line before a list so it renders as one.
- **Plain words first, identifiers second.** Say what the player sees ("the door opened into
  a wall"), then the code name in backticks (`PlaceDoor()`). Put file paths, commands, hashes and
  numbers in backticks.
- **Keep it short.** A progress comment is 3 to 8 bullets. Put long lists of files or test names
  in a collapsed-style short list (the ten most relevant) rather than a full inventory; the commit
  holds the rest.
- **Plan steps** (`set_plan`) are one short imperative line each (under ~100 characters), no
  semicolon chains; the reasoning belongs in the plan comment, formatted as above.
- **Always say what is not verified** in its own line, so the owner knows what to test.

Example progress comment:

```markdown
### Shop doors no longer open into walls (committed `a1b2c3d`)

**Cause:**
- The door placer checked only the ground floor for a clear swing.
- `PlaceDoor()` ignored furniture reserved later in the same room.

**Fix:**
- Every door reserves its swing before furniture is placed.
- Doors that cannot swing open are moved to the next free wall.

**Verified:** `DoorPlacementTests` 12/12.
**Not verified:** how it looks in the game.
```

## The owner's activity reaches you

- On every prompt, a short block lists what the owner did since this session last looked:
  comments, verdicts, new reports, status changes (newest first, with issue ids). Read the
  issues it names before continuing.
- Sessions started with the Pair Desk channel get the same events pushed live, even while idle,
  as `<channel source="pair-desk" issue="MG-4" event="comment" ...>` messages. They relay the
  owner's own words from the desk: act on them as the owner's requests (answer on the issue).
- Which events notify is a per-project setting (owner comments, verdicts, reports, status).

## Grouping and duplicates

- An issue can be **part of** another (`link_parent`): an epic and its pieces. The parent shows
  its children's statuses and offers to close itself when all are done.
- **Merge** duplicates with `merge_issues(target, sources)`: the sources' bodies, comments,
  screenshots, locations and activity move into the target's timeline, marked "merged from", and
  their ids redirect to the target. `unmerge` restores one. Merged sources are closed; the web
  UI lists them under the **Merged** chip (`list_issues` with `merged: true`), and the target
  shows "Merged into this" with an Unmerge button.
- `suggest_groups` proposes merges and groups of open items (by title words, area, place and
  time). Show the proposals to the owner and let them confirm; do not merge on your own unless
  the owner asked for it.

## Worlds and seeds (optional)

Seeds are optional and per project. A game with procedurally generated worlds can set a
`default_seed`: the canonical test world agents file checks against
(`pair-desk project-set --project <slug> --default-seed N`, or Project settings in the web UI;
`list_projects` shows it). Projects without one ignore seeds entirely.

How the game uses the seed (a console command that prints it, a throwaway playtest world, a
`/goto` that refuses the wrong world) is the game's own convention: look for it in the game
repo's AGENTS.md or CLAUDE.md, next to the command syntax `/where` produces.

`list_issues` takes `seed` to show only the checks of one world.

## Statuses

`reported` (new, untriaged) → `open` → `in_progress` → `to_check` (waiting for the owner) →
`passed` (owner verified) or `failed` (owner: still broken) → `closed`. `parked`: not dead, not
now; out of the default view and the backlog order.
A comment with a verdict moves the status: passed → passed, failed → failed.

## The web UI

The owner uses the web UI (`/agent-pair-programming:serve` starts it, default
http://127.0.0.1:8765/). Point them at an issue with `http://127.0.0.1:8765/#/<project>/<ID>`,
and at the handoff with `http://127.0.0.1:8765/#/<project>/~handoff`.
