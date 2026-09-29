"""Open a build's folder or run it: only the stored path, only from the desk's own page. No process is started."""
import contextlib
import io
import os
import re
import sys
import unittest
from unittest import mock

from helpers import StoreCase
from test_api import ApiCase

from pair_desk import launch
from pair_desk.cli import main

EXE_NAME = "MyGame.exe" if os.name == "nt" else "MyGame"


def make_build(folder):
    folder.mkdir(parents=True, exist_ok=True)
    exe = folder / EXE_NAME
    exe.write_bytes(b"not really a game")
    exe.chmod(0o755)
    return exe


class LocalInfoTests(StoreCase):
    def test_what_a_path_allows(self):
        exe = make_build(self.tmp / "builds")
        self.assertEqual(launch.local_info(str(exe)), {"exists": True, "kind": "file", "open": True, "run": True})
        self.assertEqual(launch.local_info(str(exe.parent)), {"exists": True, "kind": "folder", "open": True, "run": False})
        for nothing in ("0.9.3", "builds/MyGame.exe", str(self.tmp / "gone.exe"), "", None):
            self.assertFalse(launch.local_info(nothing)["open"], nothing)
        notes = self.tmp / "notes.txt"
        notes.write_text("x")
        if os.name == "nt":
            self.assertFalse(launch.local_info(str(notes))["run"])

    def test_run_and_reveal_start_the_right_process(self):
        exe = make_build(self.tmp / "builds")
        with mock.patch.object(launch, "_spawn") as spawn:
            self.assertEqual(launch.run(str(exe))["started"], EXE_NAME)
            spawn.assert_called_once_with([str(exe)], cwd=str(exe.parent))
            spawn.reset_mock()
            res = launch.reveal(str(exe))
            self.assertEqual(res["folder"], str(exe.parent))
            argv = spawn.call_args.args[0]
            self.assertEqual(argv[0], {"win32": "explorer", "darwin": "open"}.get(sys.platform, "xdg-open"))
            self.assertIn(str(exe.parent), " ".join(argv))
            with self.assertRaises(launch.Conflict):
                launch.run(str(exe.parent))
            with self.assertRaises(launch.Conflict):
                launch.reveal("0.9.3")
            self.assertEqual(spawn.call_count, 1)


class LaunchApiTests(ApiCase):
    def setUp(self):
        super().setUp()
        self.store.create_project("mygame", "MyGame", "MG")
        self.exe = make_build(self.tmp / "builds" / "0.9.3")
        self.store.create_issue("mygame", {"title": "x", "status": "to_check", "command": "/goto 1 2"})
        self.store.set_build("mygame", str(self.exe), commit="a2d78b49")
        status, page, _ = self.req("GET", "/")
        self.token = re.search(rb'name="pair-desk-token" content="([^"]+)"', page).group(1).decode()
        self.origin = f"http://127.0.0.1:{self.port}"
        spawner = mock.patch.object(launch, "_spawn")
        self.spawn = spawner.start()
        self.addCleanup(spawner.stop)

    def post(self, path, body=None, **headers):
        h = {"X-Pair-Desk-Token": self.token, "Origin": self.origin, **headers}
        return self.req("POST", path, body if body is not None else {}, headers={k: v for k, v in h.items() if v is not None})

    def test_the_page_carries_a_token_and_the_build_says_what_it_allows(self):
        self.assertEqual(self.token, self.server.token)
        status, p, _ = self.req("GET", "/api/projects/mygame")
        self.assertEqual(p["build"]["local"], {"exists": True, "kind": "file", "open": True, "run": True})
        status, issue, _ = self.req("GET", "/api/issues/MG-1")
        self.assertTrue(issue["build"]["local"]["run"])

    def test_run_and_open_act_on_the_stored_path_only(self):
        status, res, _ = self.post("/api/projects/mygame/build/run", {"path": "C:/Windows/System32/calc.exe"})
        self.assertEqual((status, res["started"]), (200, EXE_NAME))
        self.spawn.assert_called_once_with([str(self.exe)], cwd=str(self.exe.parent))
        status, res, _ = self.post("/api/issues/MG-1/build/open")
        self.assertEqual((status, res["folder"]), (200, str(self.exe.parent)))
        self.assertEqual(self.spawn.call_count, 2)

    def test_foreign_requests_are_refused(self):
        for headers in ({"Origin": "https://evil.example"}, {"Origin": "null"}, {"Origin": "http://127.0.0.1:5173"},
                        {"X-Pair-Desk-Token": None}, {"X-Pair-Desk-Token": "guess"}, {"Sec-Fetch-Site": "cross-site"},
                        {"Sec-Fetch-Site": "same-site"}):
            status, res, _ = self.post("/api/projects/mygame/build/run", **headers)
            self.assertEqual(status, 403, headers)
        self.spawn.assert_not_called()

    def test_folders_versions_and_missing_builds(self):
        self.store.set_build("mygame", str(self.exe.parent))
        self.assertEqual(self.post("/api/projects/mygame/build/run")[0], 409)
        self.assertEqual(self.post("/api/projects/mygame/build/open")[0], 200)
        self.store.set_build("mygame", "0.9.4")
        status, p, _ = self.req("GET", "/api/projects/mygame")
        self.assertFalse(p["build"]["local"]["open"])
        self.assertEqual(self.post("/api/projects/mygame/build/open")[0], 409)
        self.store.clear_build("mygame")
        self.assertEqual(self.post("/api/projects/mygame/build/open")[0], 404)
        self.assertEqual(self.spawn.call_count, 1)

    def test_cross_site_writes_are_refused_everywhere(self):
        status, _, _ = self.req("POST", "/api/projects/mygame/issues", {"title": "from a sandboxed frame"},
                                headers={"Origin": "null"})
        self.assertEqual(status, 403)
        status, _, _ = self.req("PATCH", "/api/issues/MG-1", {"title": "x"}, headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(status, 403)
        # The game and scripts send no Origin; a page of the desk itself is same-origin.
        self.assertEqual(self.req("POST", "/api/projects/mygame/issues", {"title": "from the game"})[0], 201)
        self.assertEqual(self.req("POST", "/api/projects/mygame/issues", {"title": "from the page"},
                                  headers={"Origin": self.origin, "Sec-Fetch-Site": "same-origin"})[0], 201)


class CliLaunchTests(StoreCase):
    def test_build_open_and_run(self):
        exe = make_build(self.tmp / "builds")
        self.store.set_build("mygame", str(exe))
        out = io.StringIO()
        with mock.patch.object(launch, "_spawn") as spawn, contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["--data", str(self.tmp), "build", "run", "--project", "mygame"]), 0)
            self.assertEqual(main(["--data", str(self.tmp), "build", "open", "--project", "mygame"]), 0)
            self.assertEqual(main(["--data", str(self.tmp), "build", "run", "--issue", "MG-9"]), 1)
        self.assertEqual(spawn.call_count, 2)
        self.assertIn(f"Started {EXE_NAME}", out.getvalue())


if __name__ == "__main__":
    unittest.main()
