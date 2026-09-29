#!/usr/bin/env python3
"""Fill a throwaway desk with neutral sample data (a made-up game called MyGame), for trying the
web UI, demos and the README screenshots. Refuses a data folder that already holds a desk.

    python scripts/demo-desk.py --data /tmp/pair-desk-demo
    python desk.py --data /tmp/pair-desk-demo serve --open
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pair_desk.store import Store  # noqa: E402

ISSUES = [
    # (title, fields, plan steps [(text, state, commit)], verification, comments [(author, text, verdict)])
    ("Lava flows end in rounded tips", {
        "kind": "check", "status": "to_check", "source": "agent", "priority": "p1", "area": "terrain", "size": "M",
        "milestone": "Volcano region",
        "body": "### Lava flows taper to rounded ends and stay on the ground\n\n"
                "**What changed:**\n- Flow meshes taper over the last 6 m instead of ending square.\n"
                "- Tips are clamped to the terrain, so none float over slopes.\n\n"
                "**Correct:** every flow ends in a soft, rounded tip that touches the ground.\n\n"
                "**Broken:** a square end, or a tip hanging in the air.\n\n**Commit:** `5ea28d6`",
        "command": "/goto 1240 -380 42.5 yaw 90 pitch 8; /time 17:30",
        "location": {"place": "Ember Rift", "time": "17:30", "weather": "clear"},
        "tags": ["lava", "visual"],
    }, [("Taper the flow mesh over its last 6 m", "done", "5ea28d6"),
        ("Clamp the tip vertices to the terrain height", "done", "5ea28d6"),
        ("Stage shot of the three flows at dusk", "done", None)],
     "Stage shot 12 shows three rounded tips on the ground; owner checks in game.",
     [("claude", "**Ready for a look.** Tips are rounded and grounded in the stage shot.", None)]),
    ("Boat wobbles when docking at the harbor", {
        "kind": "bug", "status": "failed", "source": "owner", "priority": "p1", "area": "water", "size": "S",
        "body": "The boat shakes left and right for a few seconds after docking.",
        "command": "/goto 310 -95 yaw 180; /time 09:00",
        "location": {"place": "Harbor pier", "time": "09:00", "weather": "rain"},
    }, [("Damp the buoyancy spring while docked", "done", "a41c09e"),
        ("Recheck in rain (bigger waves)", "done", None)],
     "Owner docks three times in rain without a wobble.",
     [("claude", "**Fixed:** docking now damps the buoyancy spring. See `a41c09e`.", None),
      ("owner", "Still wobbles in the rain, a bit less than before.", "failed")]),
    ("Shoreline foam flickers at dusk", {
        "kind": "bug", "status": "reported", "source": "game", "priority": "p2", "area": "water",
        "body": "Reported from the game with F12.", "command": "/goto 1180 -402 yaw 45; /time 18:10",
        "location": {"place": "Ember Rift coast", "time": "18:10"},
    }, [], None, []),
    ("Footsteps on wooden bridges sound like stone", {
        "kind": "bug", "status": "open", "source": "owner", "priority": "p2", "area": "audio", "size": "S",
        "body": "Bridges near the mill use the stone footstep set.",
    }, [], None, []),
    ("Camera clips into cliffs while gliding", {
        "kind": "bug", "status": "in_progress", "source": "owner", "priority": "p0", "area": "camera", "size": "M",
        "body": "Gliding close to the cliff face pulls the camera inside the rock.",
        "command": "/goto 860 -120 95 yaw 270 pitch -10",
        "location": {"place": "North cliffs"},
    }, [("Sphere-cast from the pivot to the camera", "done", "c19e2f0"),
        ("Pull in smoothly instead of snapping", "doing", None),
        ("Test on the three steepest cliffs", "todo", None)],
     "No clipping on the north cliffs; the pull-in eases over 0.2 s.",
     [("claude", "**Progress:** the sphere-cast works; the pull-in still snaps. Next: easing.", None)]),
    ("Market stalls repeat the same awning", {
        "kind": "idea", "status": "open", "source": "owner", "priority": "p2", "area": "props", "size": "L",
        "milestone": "Town kits", "body": "Neighbouring stalls should differ: colours, poles, cloth shapes.",
    }, [], None, []),
    ("Pause menu: add a photo mode entry", {
        "kind": "task", "status": "open", "source": "owner", "priority": "p3", "area": "ui", "size": "S",
    }, [], None, []),
    ("Night sky stars shimmer too much", {
        "kind": "bug", "status": "parked", "source": "owner", "priority": "p3", "area": "sky",
    }, [], None, []),
    ("Waterfall mist is too dense up close", {
        "kind": "check", "status": "passed", "source": "agent", "priority": "p2", "area": "water",
        "command": "/goto 402 -610 yaw 0; /time 12:00",
    }, [("Halve the mist density near the camera", "done", "77d1a3b")], "Owner walks behind the waterfall.",
     [("owner", "Looks right now.", "passed")]),
]

HANDOFF = """## State

- `5ea28d6` Lava flows taper to rounded tips and stay on the ground (MG-1, waiting for the owner).
- `c19e2f0` Glide camera sphere-casts against cliffs (MG-5, in progress).

## Where work stopped

`camera/glide.py`, `ease_pull_in()`: the easing curve is written but not wired to the collision result. Nothing uncommitted.

## Verified

- Unit tests: 214 passed.
- Stage shot 12 (lava tips) matches the reference. Not verified: the camera change in game.

## Next step

Wire `ease_pull_in()` into the glide camera (MG-5), then recheck the boat in rain (MG-2, failed).

## Traps

- The harbor rain preset spawns bigger waves than the stage harness; test MG-2 in game, not only in the stage.
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", required=True, help="a new, empty data folder")
    args = ap.parse_args()
    data = Path(args.data).expanduser()
    if (data / "desk.sqlite").exists():
        print(f"{data} already holds a desk; pick an empty folder", file=sys.stderr)
        return 1
    with Store(data) as store:
        store.create_project("mygame", "MyGame", "MG")
        store.create_project("puzzle-demo", "Puzzle Demo", "PZ")
        ids = []
        for title, fields, steps, verification, comments in ISSUES:
            status = fields.pop("status")
            issue = store.create_issue("mygame", {"title": title, "status": "open" if steps else status, **fields},
                                       actor=fields.get("source", "owner"))
            if steps:
                store.set_plan(issue["id"], [{"text": t, "state": s, **({"commit": c} if c else {})}
                                             for t, s, c in steps], verification, actor="claude")
                store.set_status(issue["id"], status, actor="claude" if status == "to_check" else "owner")
            for author, text, verdict in comments:
                store.add_comment(issue["id"], author, text, verdict=verdict)
            ids.append(issue["id"])
        dup = store.create_issue("mygame", {"title": "Boat shakes after docking in rain", "status": "reported",
                                            "source": "game", "area": "water"}, actor="game")
        store.merge_issues(ids[1], [dup["id"]], actor="owner")
        epic = store.create_issue("mygame", {"title": "Volcano region polish", "kind": "task", "status": "open",
                                             "area": "terrain", "priority": "p1", "size": "L",
                                             "milestone": "Volcano region"}, actor="owner")
        store.link_parent(ids[0], epic["id"], actor="owner")
        store.set_handoff("mygame", HANDOFF, author="claude", note="end of session")
        store.create_issue("puzzle-demo", {"title": "Hint button overlaps the timer", "area": "ui"}, actor="owner")
    print(f"Sample desk written to {data}. Start it: python desk.py --data \"{data}\" serve --open")
    return 0


if __name__ == "__main__":
    sys.exit(main())
