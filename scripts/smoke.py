#!/usr/bin/env python3
"""End-to-end smoke test: start `desk.py serve` as a real background process on a free port with a
throwaway data folder, exercise the API the way the game and the UI do, then stop it.

    python scripts/smoke.py            # temp data folder, deleted afterwards
    python scripts/smoke.py --keep     # keep the data folder and print its path
"""

from __future__ import annotations

import argparse
import base64
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PNG = base64.b64encode(base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")).decode()


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def call(base: str, method: str, path: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw and r.headers.get_content_type() == "application/json" else raw)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()
    data = Path(tempfile.mkdtemp(prefix="pairdesk-smoke-"))
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    proc = subprocess.Popen([sys.executable, str(ROOT / "desk.py"), "--data", str(data), "serve", "--port", str(port)],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    checks = []

    def check(name, ok, detail=""):
        checks.append(ok)
        print(f"  [{'ok' if ok else 'FAIL'}] {name}{'  ' + str(detail) if detail and not ok else ''}")

    try:
        for _ in range(100):
            try:
                if call(base, "GET", "/api/health")[0] == 200:
                    break
            except OSError:
                time.sleep(0.1)
        print(f"server pid {proc.pid} on {base}, data {data}")
        st, h = call(base, "GET", "/api/health")
        check("health", st == 200 and h.get("ok"), h)
        st, p = call(base, "POST", "/api/projects", {"slug": "mygame", "name": "MyGame", "prefix": "MG"})
        check("create project", st == 201 and p["prefix"] == "MG", p)
        st, i = call(base, "POST", "/api/projects/mygame/issues", {
            "title": "Shoreline foam flickers", "kind": "bug", "source": "game", "area": "water", "priority": "p1",
            "body": "Seen from the pier at dusk.\n\n- step 1\n- step 2",
            "location": {"command": "/goto 1240 -380 yaw 90; /time 17:30", "x": 1240, "y": 12, "z": -380, "yaw": 90,
                         "place": "Harbor pier", "time": "17:30", "weather": "clear"},
            "attachments": [{"filename": "screenshot.png", "mime": "image/png", "data_base64": PNG}]})
        check("create issue with base64 PNG", st == 201 and i["id"] == "MG-1" and len(i["attachments"]) == 1, i)
        att = i["attachments"][0]
        st, raw = call(base, "GET", att["url"])
        check("fetch attachment bytes", st == 200 and raw == base64.b64decode(PNG))
        st, c = call(base, "POST", "/api/issues/MG-1/comments", {"author": "owner", "text": "Looks fixed", "verdict": "passed"})
        check("comment with verdict moves status", st == 201 and c["issue"]["status"] == "passed", c)
        st, cmd = call(base, "POST", "/api/projects/mygame/commands", {"command": i["location"]["command"], "issue": "MG-1"})
        check("queue command", st == 201 and cmd["state"] == "pending", cmd)
        st, got = call(base, "GET", "/api/projects/mygame/commands/next?client=smoke-game")
        check("game fetches it once", st == 200 and got["id"] == cmd["id"] and got["client"] == "smoke-game", got)
        st, again = call(base, "GET", "/api/projects/mygame/commands/next?client=smoke-game")
        check("second poll is empty (204)", st == 204, st)
        st, state = call(base, "GET", f"/api/commands/{cmd['id']}")
        check("UI sees it delivered", state.get("state") == "delivered", state)
        st, listing = call(base, "GET", "/api/projects/mygame/issues?status=passed")
        check("list filter", listing["total"] == 1 and listing["counts"]["status"].get("passed") == 1, listing)
        st, page = call(base, "GET", "/")
        check("web UI served", st == 200 and b"Pair Desk" in page)
        for asset in ("app.js", "md.js", "app.css", "theme-boot.js", "icon.svg"):
            st, _ = call(base, "GET", "/" + asset)
            check(f"static {asset}", st == 200, st)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        proc.stdout.close()
        print(f"server stopped (exit {proc.returncode})")
        if args.keep:
            print(f"data kept in {data}")
        else:
            shutil.rmtree(data, ignore_errors=True)
    passed = sum(checks)
    print(f"{passed}/{len(checks)} checks passed")
    return 0 if checks and all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
