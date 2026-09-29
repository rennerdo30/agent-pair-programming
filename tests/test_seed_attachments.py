"""World seeds on locations, the per-project default seed, and attachments named by local path."""

import contextlib
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import unittest
from unittest import mock

from helpers import PNG, ROOT, StoreCase, TempDirCase
from test_api import ApiCase
from test_mcp_cli import McpCase

from pair_desk import store as store_module
from pair_desk.cli import main
from pair_desk.mcp import TOOLS
from pair_desk.store import Invalid, Store, command_with_seed, normalize_seed

# A WebP header is all the sniffer reads (RIFF....WEBP); the rest stands in for the image data.
WEBP = b"RIFF\x1a\x00\x00\x00WEBPVP8L\x0d\x00\x00\x00\x2f\x00\x00\x00\x10\x07\x10\x11\x11\x88\x88\xfe\x07\x00"
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"

COMMAND_CASES = [
    ("/goto 1 2", 1234, "/goto 1 2 seed 1234"),
    ("/goto 120.5 -40 33.2 yaw 90 pitch 8; /time 06:30; /weather rain", 1234,
     "/goto 120.5 -40 33.2 yaw 90 pitch 8 seed 1234; /time 06:30; /weather rain"),
    ("/time 06:30; /goto 1 2 ; /fly on", -7, "/time 06:30; /goto 1 2 seed -7 ; /fly on"),
    ("/goto 1 2 seed 99; /time 06:30", 1234, "/goto 1 2 seed 99; /time 06:30"),
    ("/GOTO 1 2", 5, "/GOTO 1 2 seed 5"),
    ("/goto 1 2; /goto 3 4", 5, "/goto 1 2 seed 5; /goto 3 4"),
    ("/time 06:30; /weather rain", 1234, "/time 06:30; /weather rain"),
    ("/gotomarker 1 2", 1234, "/gotomarker 1 2"),
    ("/goto 1 2", None, "/goto 1 2"),
    ("", 1234, ""),
]


class CommandWithSeedTests(unittest.TestCase):
    def test_cases(self):
        for command, seed, expected in COMMAND_CASES:
            with self.subTest(command=command, seed=seed):
                self.assertEqual(command_with_seed(command, seed), expected)

    def test_javascript_twin_agrees(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        source = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        consts = re.search(r"^const GOTO_COMMAND = .*$", source, re.M).group(0)
        fn = re.search(r"^function commandWithSeed\(.*?^}\n", source, re.M | re.S).group(0)
        cases = [[c, s] for c, s, _ in COMMAND_CASES]
        script = f"{consts}\n{fn}\nconsole.log(JSON.stringify({json.dumps(cases)}.map(([c, s]) => commandWithSeed(c, s))));"
        out = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout
        self.assertEqual(json.loads(out), [e for _, _, e in COMMAND_CASES])


class SeedNormalisationTests(unittest.TestCase):
    def test_accepts_integers_and_numeric_text(self):
        self.assertEqual(normalize_seed(1234), 1234)
        self.assertEqual(normalize_seed(" -12 "), -12)
        self.assertEqual(normalize_seed(7.0), 7)
        self.assertEqual(normalize_seed(2 ** 31 - 1), 2 ** 31 - 1)

    def test_refuses_the_rest(self):
        for bad in ("abc", "1234.5", 1.5, True, None, [], 2 ** 31, "", "12e3"):
            with self.subTest(bad=bad), self.assertRaises(Invalid):
                normalize_seed(bad)

    def test_location_seed(self):
        self.assertEqual(store_module.normalize_location({"seed": "1234", "command": "/goto 1 2"})["seed"], 1234)
        with self.assertRaises(Invalid):
            store_module.normalize_location({"seed": "north"})


class SeedStoreTests(StoreCase):
    def test_default_seed_setting(self):
        self.assertIsNone(self.store.get_project("mygame")["default_seed"])
        self.assertEqual(self.store.update_project("mygame", {"default_seed": "1234"})["default_seed"], 1234)
        self.assertEqual(self.store.list_projects()[0]["default_seed"], 1234)
        self.assertIsNone(self.store.update_project("mygame", {"default_seed": ""})["default_seed"])
        self.store.update_project("mygame", {"default_seed": 5})
        self.assertIsNone(self.store.update_project("mygame", {"default_seed": None})["default_seed"])
        with self.assertRaises(Invalid):
            self.store.update_project("mygame", {"default_seed": "world"})

    def test_inheritance(self):
        self.store.update_project("mygame", {"default_seed": 1234})
        agent = self.store.create_issue("mygame", {"title": "a", "kind": "check", "status": "to_check",
                                                     "source": "agent", "command": "/goto 1 2"})
        self.assertEqual(agent["location"], {"command": "/goto 1 2", "seed": 1234})
        own = self.store.create_issue("mygame", {"title": "b", "source": "agent", "location": {"seed": 7}})
        self.assertEqual(own["location"]["seed"], 7)
        bare = self.store.create_issue("mygame", {"title": "c", "kind": "check", "source": "owner"})
        self.assertEqual(bare["location"], {"seed": 1234})
        game = self.store.create_issue("mygame", {"title": "d", "source": "game", "status": "to_check",
                                                    "command": "/goto 1 2"})
        self.assertNotIn("seed", game["location"])
        report = self.store.create_issue("mygame", {"title": "e", "source": "owner", "kind": "bug"})
        self.assertEqual(report["location"], {})

    def test_no_default_no_seed(self):
        issue = self.store.create_issue("mygame", {"title": "a", "kind": "check", "source": "agent"})
        self.assertEqual(issue["location"], {})

    def test_filter_and_counts(self):
        self.store.create_issue("mygame", {"title": "a", "location": {"seed": 1234}})
        self.store.create_issue("mygame", {"title": "b", "location": {"seed": 1234}})
        self.store.create_issue("mygame", {"title": "c", "location": {"seed": 12}})
        self.store.create_issue("mygame", {"title": "d"})
        res = self.store.list_issues("mygame", {"seed": "1234"})
        self.assertEqual(sorted(i["title"] for i in res["issues"]), ["a", "b"])
        self.assertEqual(res["counts"]["seed"], {"1234": 2, "12": 1})
        with self.assertRaises(Invalid):
            self.store.list_issues("mygame", {"seed": "x"})

    def test_backfill(self):
        self.store.create_issue("mygame", {"title": "check", "kind": "check", "source": "agent",
                                             "command": "/goto 1 2"})
        self.store.create_issue("mygame", {"title": "seeded", "kind": "check", "source": "agent",
                                             "location": {"seed": 9}})
        self.store.create_issue("mygame", {"title": "report", "source": "game"})
        self.store.create_issue("mygame", {"title": "idea", "kind": "idea", "source": "owner"})
        res = self.store.backfill_seed("mygame", 1234)
        self.assertEqual(res["changed"], ["MG-1"])
        self.assertEqual(self.store.get_issue("MG-1")["location"], {"command": "/goto 1 2", "seed": 1234})
        self.assertEqual(self.store.get_issue("MG-2")["location"]["seed"], 9)
        self.assertEqual(self.store.backfill_seed("mygame", 1234)["changed"], [])

    def test_migrates_a_version_1_database(self):
        self.store.close()
        old = self.tmp / "old"
        old.mkdir()
        conn = sqlite3.connect(old / "desk.sqlite")
        conn.executescript(store_module.SCHEMA)  # the version 1 tables: no projects.default_seed
        conn.execute("INSERT INTO projects(slug, name, prefix, created_at) VALUES ('g', 'G', 'G', 'now')")
        conn.commit()
        conn.close()
        with Store(old) as s:
            self.assertIsNone(s.get_project("g")["default_seed"])
            self.assertEqual(s.update_project("g", {"default_seed": 1})["default_seed"], 1)
        self.store = Store(self.tmp, clock=self.clock)


class PathAttachmentTests(StoreCase):
    def setUp(self):
        super().setUp()
        self.files = self.tmp / "repo" / "docs" / "feedback"
        self.files.mkdir(parents=True)
        (self.files / "fog.webp").write_bytes(WEBP)
        (self.files / "shot.png").write_bytes(PNG)
        (self.files / "notes.pdf").write_bytes(PDF)
        (self.files / "fake.png").write_bytes(b"not a picture")
        (self.files / "notes.txt").write_text("hello", encoding="utf-8")
        self.base = [self.tmp / "repo"]

    def test_attaches_images_and_pdfs(self):
        issue = self.store.create_issue("mygame", {"title": "fog", "attachment_paths": [
            "docs/feedback/fog.webp", str(self.files / "shot.png"), "docs/feedback/notes.pdf"]}, path_base=self.base)
        atts = issue["attachments"]
        self.assertEqual([(a["filename"], a["mime"], a["is_image"]) for a in atts], [
            ("fog.webp", "image/webp", True), ("shot.png", "image/png", True), ("notes.pdf", "application/pdf", False)])
        meta, path = self.store.get_attachment(atts[0]["id"])
        self.assertEqual(path.read_bytes(), WEBP)

    def test_refusals(self):
        cases = {
            "docs/feedback/missing.webp": "does not exist",
            "docs/feedback": "not a regular file",
            "docs/feedback/notes.txt": "only images and PDFs",
            "docs/feedback/fake.png": "content is not image/png",
        }
        for path, message in cases.items():
            with self.subTest(path=path), self.assertRaisesRegex(Invalid, message):
                self.store.create_issue("mygame", {"title": "x", "attachment_paths": [path]}, path_base=self.base)
        self.assertEqual(self.store.list_issues("mygame")["total"], 0, "a refused path creates nothing")
        with mock.patch.object(store_module, "MAX_PATH_ATTACHMENT_BYTES", 10), self.assertRaisesRegex(Invalid, "larger than"):
            self.store.create_issue("mygame", {"title": "x", "attachment_paths": ["docs/feedback/fog.webp"]},
                                    path_base=self.base)
        with self.assertRaisesRegex(Invalid, "list"):
            self.store.create_issue("mygame", {"title": "x", "attachment_paths": "docs/feedback/fog.webp"},
                                    path_base=self.base)

    def test_paths_need_a_local_caller(self):
        with self.assertRaisesRegex(Invalid, "CLI and the MCP"):
            self.store.create_issue("mygame", {"title": "x", "attachment_paths": ["docs/feedback/fog.webp"]})

    def test_comment_and_import(self):
        self.store.create_issue("mygame", {"title": "fog"})
        res = self.store.add_comment("MG-1", "claude", "fixed, see", attachment_paths=["docs/feedback/fog.webp"],
                                     path_base=self.base)
        self.assertEqual(res["comment"]["attachments"][0]["mime"], "image/webp")
        summary = self.store.import_data({"project": "mygame", "issues": [
            {"title": "ok", "attachment_paths": ["docs/feedback/shot.png"]},
            {"title": "bad", "attachment_paths": ["docs/feedback/nope.png"]}]}, path_base=self.base)
        self.assertEqual(summary["created"], ["MG-2"])
        self.assertIn("does not exist", summary["errors"][0]["error"])
        self.assertEqual(self.store.get_issue("MG-2")["attachment_count"], 1)


class SeedApiTests(ApiCase):
    def setUp(self):
        super().setUp()
        self.store.create_project("mygame", "MyGame", "MG")

    def test_seed_over_http(self):
        status, p, _ = self.req("PATCH", "/api/projects/mygame", {"default_seed": 1234})
        self.assertEqual((status, p["default_seed"]), (200, 1234))
        status, issue, _ = self.req("POST", "/api/projects/mygame/issues", {
            "title": "from the game", "source": "game", "location": {"command": "/goto 1 2", "seed": "77",
                                                                     "extra": {"seed": "77"}}})
        self.assertEqual((status, issue["location"]["seed"]), (201, 77))
        status, err, _ = self.req("POST", "/api/projects/mygame/issues", {"title": "x", "location": {"seed": "abc"}})
        self.assertEqual(status, 400)
        self.assertIn("seed", err["error"])
        status, check, _ = self.req("POST", "/api/projects/mygame/issues", {"title": "check", "kind": "check", "source": "agent"})
        self.assertEqual(check["location"]["seed"], 1234)
        status, res, _ = self.req("GET", "/api/projects/mygame/issues?seed=77&status=reported,to_check")
        self.assertEqual([i["title"] for i in res["issues"]], ["from the game"])
        self.assertEqual(self.req("GET", "/api/projects/mygame/issues?seed=abc")[0], 400)

    def test_http_never_reads_local_paths(self):
        target = self.tmp / "secret.png"
        target.write_bytes(PNG)
        status, err, _ = self.req("POST", "/api/projects/mygame/issues", {"title": "x", "attachment_paths": [str(target)]})
        self.assertEqual(status, 400)
        self.assertIn("CLI and the MCP", err["error"])

    def test_webp_is_served_inline(self):
        issue = self.store.create_issue("mygame", {"title": "fog"})
        att = self.store.add_attachment(issue["id"], "fog.webp", None, WEBP)
        self.assertTrue(att["is_image"])
        status, body, res = self.req("GET", att["url"])
        self.assertEqual((status, res.getheader("Content-Type")), (200, "image/webp"))
        self.assertTrue(res.getheader("Content-Disposition").startswith("inline"))
        self.assertEqual(body, WEBP)
        status, listing, _ = self.req("GET", "/api/projects/mygame/issues?status=reported")
        self.assertEqual(listing["issues"][0]["attachment_count"], 1)


class SeedMcpTests(McpCase):
    def test_seed_and_paths_over_mcp(self):
        shots = self.repo / "docs" / "feedback"
        shots.mkdir(parents=True)
        (shots / "fog.webp").write_bytes(WEBP)
        with Store(self.tmp) as s:
            s.update_project("mygame", {"default_seed": 1234})
        tools = {t["name"]: t for t in TOOLS}
        self.assertIn("seed", tools["create_issue"]["inputSchema"]["properties"]["location"]["properties"])
        self.assertIn("attachment_paths", tools["comment"]["inputSchema"]["properties"])
        self.assertIn("attachment_paths", tools["import_checks"]["inputSchema"]["properties"]["checks"]["items"]["properties"])
        err, issue = self.call(1, "create_issue", {"title": "Fog", "command": "/goto 1 2; /time 06:30",
                                                   "attachment_paths": ["docs/feedback/fog.webp"]})
        self.assertFalse(err, issue)
        self.assertEqual(issue["location"]["seed"], 1234)
        self.assertEqual(issue["command"], "/goto 1 2 seed 1234; /time 06:30")
        self.assertEqual(issue["attachment_count"], 1)
        err, other = self.call(2, "create_issue", {"title": "Ice", "location": {"command": "/goto 5 5", "seed": 12}})
        self.assertEqual(other["seed"], 12)
        err, listing = self.call(3, "list_issues", {"seed": 12})
        self.assertEqual([i["id"] for i in listing["issues"]], [other["id"]])
        err, res = self.call(4, "comment", {"id": issue["id"], "text": "see", "attachment_paths": ["docs/feedback/fog.webp"]})
        self.assertFalse(err, res)
        self.assertEqual(res["comment"]["attachments"][0]["filename"], "fog.webp")
        err, msg = self.call(5, "comment", {"id": issue["id"], "text": "x", "attachment_paths": ["docs/feedback/none.png"]})
        self.assertTrue(err)
        self.assertIn("does not exist", msg)
        err, summary = self.call(6, "import_checks", {"checks": [
            {"title": "Imported", "external_ref": "r1", "attachment_paths": ["docs/feedback/fog.webp"]}]})
        self.assertEqual(len(summary["created"]), 1, summary)
        err, full = self.call(7, "get_issue", {"id": summary["created"][0]})
        self.assertEqual((full["attachment_count"], full["location"]), (1, {"seed": 1234}))


class SeedCliTests(StoreCase):
    def run_cli(self, *argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            code = main(["--data", str(self.tmp), *argv])
        return code, buf.getvalue()

    def test_project_settings_backfill_and_send(self):
        self.store.create_issue("mygame", {"title": "old check", "kind": "check", "status": "to_check",
                                             "source": "agent", "command": "/goto 3 4 yaw 90; /time 17:30"})
        self.assertEqual(self.run_cli("project-set", "--project", "mygame", "--backfill-seed")[0], 1,
                         "a backfill needs a default seed")
        code, out = self.run_cli("project-set", "--project", "mygame", "--default-seed", "1234", "--backfill-seed", "--json")
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual((data["project"]["default_seed"], data["backfill"]["changed"]), (1234, ["MG-1"]))
        code, out = self.run_cli("send", "--issue", "MG-1")
        self.assertIn("/goto 3 4 yaw 90 seed 1234; /time 17:30", out)
        code, out = self.run_cli("show", "MG-1")
        self.assertIn("world seed: 1234", out)
        code, out = self.run_cli("list", "--project", "mygame", "--seed", "1234", "--json")
        self.assertEqual(json.loads(out)["total"], 1)
        code, out = self.run_cli("add", "--project", "mygame", "--title", "other world", "--seed", "8", "--json")
        self.assertEqual(json.loads(out)["location"], {"seed": 8})
        code, out = self.run_cli("edit", "MG-2", "--seed", "9", "--json")
        self.assertEqual(json.loads(out)["location"], {"seed": 9})
        code, out = self.run_cli("project-set", "--project", "mygame", "--default-seed", "none")
        self.assertIn("default seed none", out)
        code, out = self.run_cli("projects")
        self.assertNotIn("default seed", out)

    def test_import_json_reads_paths_next_to_the_file(self):
        folder = self.tmp / "checks"
        folder.mkdir()
        (folder / "shot.webp").write_bytes(WEBP)
        path = folder / "checks.json"
        path.write_text(json.dumps([{"title": "Fog", "kind": "check", "attachment_paths": ["shot.webp"]}]), encoding="utf-8")
        cwd = os.getcwd()
        os.chdir(self.tmp)
        try:
            code, out = self.run_cli("import-json", str(path), "--project", "mygame", "--json")
        finally:
            os.chdir(cwd)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.store.get_issue("MG-1")["attachments"][0]["mime"], "image/webp")


if __name__ == "__main__":
    unittest.main()
