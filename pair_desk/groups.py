"""Grouping proposals for open issues (MCP `suggest_groups`, CLI `suggest-groups`).

Pairs of open items are scored on what the owner would use to spot "the same thing": title
words, area, where in the world (command, place, seed and position) and when they were filed.
Strong pairs are joined into clusters. Nothing is applied: each cluster is a proposal the owner
confirms, either a merge (the items describe one problem) or a group under a parent (related work).
"""

from __future__ import annotations

import datetime as _dt
import math
import re
from typing import Any

STOPWORDS = frozenset("""
a an and are as at be but by can do does for from has have in into is it its no not of on or so
than that the their then there these they this to too was were when where which while with
still again also just very more less some any all one two only after before over under near
""".split())

# How close two positions must be (world units, same seed) to count as the same spot.
NEAR_DISTANCE = 64.0
# Filed within this window counts as "at the same time" (one play session).
SAME_SESSION = _dt.timedelta(hours=3)
LINK_SCORE = 0.45
MERGE_SIMILARITY = 0.5


def title_words(title: str) -> set[str]:
    words = set()
    for w in re.findall(r"[a-z0-9]+", title.lower()):
        if len(w) < 3 or w in STOPWORDS:
            continue
        if len(w) > 4 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        words.add(w)
    return words


def _time(iso: str) -> _dt.datetime | None:
    try:
        return _dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


def _near(a: dict, b: dict) -> bool:
    la, lb = a.get("location") or {}, b.get("location") or {}
    if la.get("seed") is not None and lb.get("seed") is not None and la["seed"] != lb["seed"]:
        return False
    if all(isinstance(la.get(k), (int, float)) and isinstance(lb.get(k), (int, float)) for k in ("x", "z")):
        return math.hypot(la["x"] - lb["x"], la["z"] - lb["z"]) <= NEAR_DISTANCE
    return False


def score_pair(a: dict, b: dict) -> tuple[float, float, list[str]]:
    """(score, title similarity, reasons) for two issues."""
    wa, wb = title_words(a["title"]), title_words(b["title"])
    sim = len(wa & wb) / len(wa | wb) if wa and wb else 0.0
    score, reasons = 0.55 * sim, []
    if sim > 0:
        shared = sorted(wa & wb)
        if shared:
            reasons.append("title words: " + ", ".join(shared[:6]))
    la, lb = a.get("location") or {}, b.get("location") or {}
    where = False
    if la.get("command") and la.get("command") == lb.get("command"):
        score += 0.3
        reasons.append("same location command")
        where = True
    elif la.get("place") and str(la["place"]).lower() == str(lb.get("place", "")).lower():
        score += 0.2
        reasons.append(f"same place: {la['place']}")
        where = True
    elif _near(a, b):
        score += 0.3
        reasons.append("within %d units in the same world" % NEAR_DISTANCE)
        where = True
    if a.get("area") and a["area"].lower() == (b.get("area") or "").lower():
        score += 0.2
        reasons.append(f"area: {a['area']}")
    ta, tb = _time(a.get("created_at", "")), _time(b.get("created_at", ""))
    if ta and tb and abs(ta - tb) <= SAME_SESSION:
        score += 0.1
        reasons.append("filed in the same session")
    if a.get("kind") == b.get("kind"):
        score += 0.05
    if sim < 0.2 and not where:
        score = min(score, LINK_SCORE - 0.01)  # area and timing alone never make a group
    return score, sim, reasons


def suggest(issues: list[dict], limit: int = 20) -> list[dict]:
    """Clusters of related open issues, strongest first. Each proposal names a target (the
    oldest item) and an action: `merge` (duplicates) or `group` (children of the target)."""
    n = len(issues)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    pairs: dict[tuple[int, int], tuple[float, float, list[str]]] = {}
    for i in range(n):
        for j in range(i + 1, n):
            sc = score_pair(issues[i], issues[j])
            if sc[0] >= LINK_SCORE:
                pairs[(i, j)] = sc
                parent[find(i)] = find(j)
    clusters: dict[int, list[int]] = {}
    for i in range(n):
        clusters.setdefault(find(i), []).append(i)
    out = []
    for members in clusters.values():
        if len(members) < 2:
            continue
        linked = [(k, v) for k, v in pairs.items() if k[0] in members and k[1] in members]
        sims = [v[1] for _, v in linked]
        scores = [v[0] for _, v in linked]
        reasons: list[str] = []
        for _, v in sorted(linked, key=lambda kv: -kv[1][0]):
            for r in v[2]:
                if r not in reasons:
                    reasons.append(r)
        items = sorted((issues[i] for i in members), key=lambda x: (x.get("created_at", ""), x.get("number", 0)))
        target = items[0]
        same_cmd = any("same location command" in v[2] for _, v in linked)
        action = "merge" if (sum(sims) / len(sims) >= MERGE_SIMILARITY or same_cmd) else "group"
        proposal: dict[str, Any] = {
            "action": action,
            "target": target["id"],
            "issues": [x["id"] for x in items],
            "titles": {x["id"]: x["title"] for x in items},
            "score": round(sum(scores) / len(scores), 2),
            "reasons": reasons[:6],
        }
        if action == "merge":
            proposal["hint"] = f"merge_issues(target={target['id']}, sources={[x['id'] for x in items[1:]]})"
        else:
            proposal["hint"] = f"link_parent(child, parent={target['id']}) for each of {[x['id'] for x in items[1:]]}"
        out.append(proposal)
    out.sort(key=lambda p: (-p["score"], -len(p["issues"])))
    return out[:max(1, int(limit))]
