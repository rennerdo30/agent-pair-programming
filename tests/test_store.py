import json
import threading
import unittest

from helpers import PNG, PNG_B64, StoreCase

from pair_desk.store import Conflict, Invalid, NotFound, Store


class ProjectTests(StoreCase):
    def test_create_and_list(self):
        self.store.create_project("other-game", "Other Game", "OG")
        slugs = [p["slug"] for p in self.store.list_projects()]
        self.assertEqual(slugs, ["mygame", "other-game"])
        self.assertEqual(self.store.get_project("mygame")["prefix"], "MG")

    def test_duplicates_and_validation(self):
        with self.assertRaises(Conflict):
            self.store.create_project("mygame", "Again", "AX")
        with self.assertRaises(Conflict):
            self.store.create_project("new", "New", "MG")
        with self.assertRaises(Invalid):
            self.store.create_project("Bad Slug", "x", "BS")
        with self.assertRaises(Invalid):
            self.store.create_project("ok", "x", "1A")

    def test_default_prefix(self):
        p = self.store.create_project("moon", "Moon Base")
        self.assertEqual(p["prefix"], "MO")


class IssueTests(StoreCase):
    def test_numbering_is_per_project(self):
        self.store.create_project("other", "Other", "OT")
        a1 = self.store.create_issue("mygame", {"title": "one"})
        o1 = self.store.create_issue("other", {"title": "first other"})
        a2 = self.store.create_issue("mygame", {"title": "two"})
        self.assertEqual((a1["id"], a2["id"], o1["id"]), ("MG-1", "MG-2", "OT-1"))

    def test_numbers_never_reused_after_delete(self):
        self.store.create_issue("mygame", {"title": "one"})
        self.store.delete_issue("MG-1")
        self.assertEqual(self.store.create_issue("mygame", {"title": "two"})["id"], "MG-2")

    def test_defaults_and_fields(self):
        i = self.store.create_issue("mygame", {
            "title": "  Lava   ends  ", "tags": "terrain, #lava, Terrain", "command": "/goto 1 2 3",
            "location": {"x": "1.5", "place": "Ember Rift", "biome": "volcanic"}})
        self.assertEqual(i["title"], "Lava ends")
        self.assertEqual((i["kind"], i["status"], i["priority"], i["source"]), ("bug", "reported", "p2", "owner"))
        self.assertEqual(i["tags"], ["terrain", "lava"])
        self.assertEqual(i["location"], {"x": 1.5, "place": "Ember Rift", "extra": {"biome": "volcanic"},
                                         "command": "/goto 1 2 3"})
        self.assertEqual(i["activity"][0]["action"], "created")

    def test_validation(self):
        with self.assertRaises(Invalid):
            self.store.create_issue("mygame", {"title": ""})
        with self.assertRaises(Invalid):
            self.store.create_issue("mygame", {"title": "x", "kind": "feature"})
        with self.assertRaises(Invalid):
            self.store.create_issue("mygame", {"title": "x", "location": {"x": "far"}})
        with self.assertRaises(NotFound):
            self.store.create_issue("nope", {"title": "x"})
        with self.assertRaises(NotFound):
            self.store.get_issue("MG-99")
        with self.assertRaises(Invalid):
            self.store.get_issue("garbage")

    def test_key_is_case_insensitive(self):
        self.store.create_issue("mygame", {"title": "one"})
        self.assertEqual(self.store.get_issue("mg-1")["id"], "MG-1")

    def test_update_records_activity_and_closed_at(self):
        self.store.create_issue("mygame", {"title": "one", "command": "/goto 1 2 3", "location": {"place": "Harbor"}})
        self.clock.advance(minutes=1)
        i = self.store.update_issue("MG-1", {"status": "closed", "priority": "p0", "command": "/goto 4 5 6"})
        self.assertEqual(i["status"], "closed")
        self.assertIsNotNone(i["closed_at"])
        self.assertEqual(i["location"], {"place": "Harbor", "command": "/goto 4 5 6"})
        actions = [a["action"] for a in i["activity"]]
        self.assertEqual(actions, ["created", "status", "edited"])
        self.assertEqual(i["activity"][1]["detail"], {"from": "reported", "to": "closed"})
        i = self.store.update_issue("MG-1", {"status": "open"})
        self.assertIsNone(i["closed_at"])

    def test_noop_update_records_nothing(self):
        self.store.create_issue("mygame", {"title": "one"})
        i = self.store.update_issue("MG-1", {"title": "one"})
        self.assertEqual(len(i["activity"]), 1)

    def test_list_filters_counts_and_search(self):
        s = self.store
        s.create_issue("mygame", {"title": "Lava", "kind": "check", "status": "to_check", "area": "terrain"})
        s.create_issue("mygame", {"title": "Boat sinks", "status": "reported", "area": "water", "priority": "p0"})
        s.create_issue("mygame", {"title": "Old", "status": "closed", "area": "terrain"})
        s.add_comment("MG-3", "owner", "the kraken ate it")
        res = s.list_issues("mygame", {"status": "to_check,reported"})
        self.assertEqual([i["id"] for i in res["issues"]], ["MG-1", "MG-2"])  # triage order: to_check first
        self.assertEqual(res["counts"]["status"], {"to_check": 1, "reported": 1, "closed": 1})
        self.assertEqual(res["counts"]["area"], {"terrain": 1, "water": 1})
        self.assertEqual(s.list_issues("mygame", {"q": "kraken"})["issues"][0]["id"], "MG-3")
        self.assertEqual(s.list_issues("mygame", {"q": "MG-2"})["total"], 1)
        self.assertEqual(s.list_issues("mygame", {"area": "TERRAIN"})["total"], 2)
        self.assertEqual(s.list_issues("mygame", {"priority": "p0"})["issues"][0]["title"], "Boat sinks")
        self.assertEqual(s.list_issues("mygame", {"q": "100%_"})["total"], 0)
        with self.assertRaises(Invalid):
            s.list_issues("mygame", {"status": "bogus"})

    def test_list_limit_and_offset(self):
        for n in range(30):
            self.store.create_issue("mygame", {"title": f"issue {n}"})
        res = self.store.list_issues("mygame", {"limit": 10, "offset": 25, "sort": "number"})
        self.assertEqual(res["total"], 30)
        self.assertEqual(len(res["issues"]), 5)


class CommentTests(StoreCase):
    def test_verdict_moves_status(self):
        self.store.create_issue("mygame", {"title": "check", "kind": "check", "status": "to_check"})
        res = self.store.add_comment("MG-1", "owner", "looks right", "passed")
        self.assertEqual(res["issue"]["status"], "passed")
        self.assertIsNotNone(res["issue"]["closed_at"])
        self.assertEqual(res["comment"]["verdict"], "passed")
        res = self.store.add_comment("MG-1", "owner", "no, broken at night", "failed")
        self.assertEqual(res["issue"]["status"], "failed")
        self.assertIsNone(res["issue"]["closed_at"])
        status_events = [a for a in res["issue"]["activity"] if a["action"] == "status"]
        self.assertEqual([e["detail"]["reason"] for e in status_events], ["verdict", "verdict"])
        self.assertEqual(self.store.list_issues("mygame")["issues"][0]["last_verdict"], "failed")

    def test_plain_comment_keeps_status(self):
        self.store.create_issue("mygame", {"title": "x", "status": "open"})
        res = self.store.add_comment("MG-1", "claude", "fixed in abc123")
        self.assertEqual(res["issue"]["status"], "open")

    def test_comment_needs_content_and_valid_verdict(self):
        self.store.create_issue("mygame", {"title": "x"})
        with self.assertRaises(Invalid):
            self.store.add_comment("MG-1", "owner", "   ")
        with self.assertRaises(Invalid):
            self.store.add_comment("MG-1", "owner", "x", "maybe")

    def test_comment_attachments(self):
        self.store.create_issue("mygame", {"title": "x"})
        res = self.store.add_comment("MG-1", "owner", "", "failed",
                                     [{"filename": "shot.png", "data_base64": "data:image/png;base64," + PNG_B64}])
        att = res["comment"]["attachments"][0]
        self.assertEqual((att["mime"], att["size"], att["is_image"]), ("image/png", len(PNG), True))


class AttachmentTests(StoreCase):
    def test_store_and_read_back(self):
        i = self.store.create_issue("mygame", {"title": "x", "attachments": [
            {"filename": "../../evil name.png", "mime": "text/html", "data_base64": PNG_B64}]})
        att = i["attachments"][0]
        self.assertEqual(att["filename"], "evil name.png")
        self.assertEqual(att["mime"], "image/png")  # sniffed, not trusted
        meta, path = self.store.get_attachment(att["id"])
        self.assertEqual(path.read_bytes(), PNG)
        self.assertTrue(path.resolve().is_relative_to(self.tmp.resolve()))
        self.store.delete_attachment(att["id"])
        self.assertFalse(path.exists())
        self.assertEqual(self.store.get_issue("MG-1")["attachments"], [])

    def test_rejects_bad_base64(self):
        with self.assertRaises(Invalid):
            self.store.create_issue("mygame", {"title": "x", "attachments": [{"filename": "a", "data_base64": "@@@"}]})
        self.assertEqual(self.store.list_issues("mygame")["total"], 0)


class CommandQueueTests(StoreCase):
    def test_delivered_once_in_order(self):
        self.store.create_issue("mygame", {"title": "x", "command": "/goto 1 2 3"})
        a = self.store.queue_command("mygame", "/goto 1 2 3", "MG-1")
        b = self.store.queue_command("mygame", "/time 12:00")
        self.assertEqual(a["state"], "pending")
        first = self.store.next_command("mygame", "mygame-client")
        second = self.store.next_command("mygame", "mygame-client")
        self.assertEqual((first["id"], second["id"]), (a["id"], b["id"]))
        self.assertIsNone(self.store.next_command("mygame", "mygame-client"))
        got = self.store.get_command(a["id"])
        self.assertEqual((got["state"], got["client"]), ("delivered", "mygame-client"))
        actions = [x["action"] for x in self.store.get_issue("MG-1")["activity"]]
        self.assertIn("command_sent", actions)
        self.assertIn("command_delivered", actions)

    def test_expiry(self):
        c = self.store.queue_command("mygame", "/goto 1 2 3")
        self.clock.advance(minutes=9, seconds=59)
        self.assertEqual(self.store.get_command(c["id"])["state"], "pending")
        self.clock.advance(seconds=2)
        self.assertEqual(self.store.get_command(c["id"])["state"], "expired")
        self.assertIsNone(self.store.next_command("mygame"))

    def test_queue_is_per_project(self):
        self.store.create_project("other", "Other", "OT")
        self.store.queue_command("other", "/fly")
        self.assertIsNone(self.store.next_command("mygame"))
        self.assertEqual(self.store.next_command("other")["command"], "/fly")

    def test_concurrent_pollers_get_each_command_once(self):
        for n in range(20):
            self.store.queue_command("mygame", f"/cmd {n}")
        got, lock = [], threading.Lock()

        def worker():
            while True:
                c = self.store.next_command("mygame", "t")
                if c is None:
                    return
                with lock:
                    got.append(c["id"])

        threads = [threading.Thread(target=worker) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sorted(got), sorted(set(got)))
        self.assertEqual(len(got), 20)

    def test_two_store_instances_share_the_queue(self):
        other = Store(self.tmp, clock=self.clock)
        try:
            self.store.queue_command("mygame", "/goto 0 0 0")
            self.assertEqual(other.next_command("mygame")["command"], "/goto 0 0 0")
            self.assertIsNone(self.store.next_command("mygame"))
        finally:
            other.close()

    def test_issue_must_match_project(self):
        self.store.create_project("other", "Other", "OT")
        self.store.create_issue("other", {"title": "x"})
        with self.assertRaises(Invalid):
            self.store.queue_command("mygame", "/x", "OT-1")


class ImportExportTests(StoreCase):
    def test_import_dedupes_by_external_ref(self):
        payload = {"project": "mygame", "issues": [
            {"title": "Check lava", "kind": "check", "status": "to_check", "external_ref": "TODO: lava ends"},
            {"title": "Check boats", "external_ref": "TODO: boats",
             "comments": [{"author": "claude", "text": "see commit abc"}]},
            {"title": "No ref"},
        ]}
        first = self.store.import_data(payload)
        self.assertEqual(first["created"], ["MG-1", "MG-2", "MG-3"])
        second = self.store.import_data(payload)
        self.assertEqual(second["created"], ["MG-4"])  # the item without a ref cannot be deduped
        self.assertEqual([s["existing"] for s in second["skipped"]], ["MG-1", "MG-2"])
        self.assertEqual(self.store.get_issue("MG-2")["comments"][0]["author"], "claude")

    def test_import_reports_errors_and_creates_projects(self):
        res = self.store.import_data({
            "projects": [{"slug": "newgame", "name": "New Game", "prefix": "NG"}],
            "issues": [{"project": "newgame", "title": "a"}, {"title": "no project"}, {"project": "mygame", "title": ""}],
        })
        self.assertEqual(res["projects_created"], ["newgame"])
        self.assertEqual(res["created"], ["NG-1"])
        self.assertEqual(len(res["errors"]), 2)

    def test_export_roundtrip_shape(self):
        self.store.create_issue("mygame", {"title": "x", "attachments": [{"filename": "a.png", "data_base64": PNG_B64}]})
        self.store.add_comment("MG-1", "owner", "hi")
        data = self.store.export_project("mygame")
        self.assertEqual(data["format"], "pair-desk-export")
        self.assertEqual(len(data["issues"]), 1)
        self.assertEqual(data["issues"][0]["comments"][0]["text"], "hi")
        json.dumps(data)

    def test_overview(self):
        self.store.create_issue("mygame", {"title": "x", "area": "terrain", "tags": ["lava"]})
        o = self.store.project_overview("mygame")
        self.assertEqual((o["areas"], o["tags"], o["counts"]["reported"]), (["terrain"], ["lava"], 1))
        self.assertIsNotNone(o["last_change"])


if __name__ == "__main__":
    unittest.main()
