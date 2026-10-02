"""Session-start autostart of the web desk (ensure_server): start when no desk answers, replace an older desk this
desk started, leave a newer or a foreign server alone, honour PAIR_DESK_AUTOSTART=0."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pair_desk import VERSION, cli


class FakeProc:
    pid = 4242


class AutostartTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name)
        self.spawned = []
        patches = [
            mock.patch.object(cli, "_spawn_server", lambda data_dir, port, lan=False: self.spawned.append(port) or FakeProc()),
            mock.patch.dict(os.environ, {}, clear=False),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        os.environ.pop("PAIR_DESK_AUTOSTART", None)
        os.environ.pop("PAIR_DESK_PORT", None)
        self.addCleanup(self.tmp.cleanup)

    def health(self, *answers):
        it = iter(answers)
        p = mock.patch.object(cli, "_health", lambda port, timeout=0.6: next(it, None))
        p.start()
        self.addCleanup(p.stop)

    def test_starts_when_no_desk_answers(self):
        self.health(None)
        self.assertEqual(cli.ensure_server(self.data), "started")
        self.assertEqual(self.spawned, [8765])
        self.assertEqual((self.data / "server.pid").read_text(), "4242")

    def test_current_desk_is_left_running(self):
        self.health({"ok": True, "version": VERSION})
        self.assertEqual(cli.ensure_server(self.data), "running")
        self.assertEqual(self.spawned, [])

    def test_older_desk_it_started_is_replaced(self):
        self.health({"ok": True, "version": "0.0.1"})
        (self.data / "server.pid").write_text("99", encoding="ascii")
        with mock.patch.object(os, "kill") as kill:
            self.assertEqual(cli.ensure_server(self.data), "restarted")
        kill.assert_called_once()
        self.assertEqual(kill.call_args[0][0], 99)
        self.assertEqual(self.spawned, [8765])

    def test_older_foreign_server_is_not_touched(self):
        self.health({"ok": True, "version": "0.0.1"})
        self.assertEqual(cli.ensure_server(self.data), "foreign-running")
        self.assertEqual(self.spawned, [])

    def test_newer_desk_is_left_alone(self):
        self.health({"ok": True, "version": "999.0.0"})
        self.assertEqual(cli.ensure_server(self.data), "newer-running")
        self.assertEqual(self.spawned, [])

    def test_autostart_can_be_disabled(self):
        os.environ["PAIR_DESK_AUTOSTART"] = "0"
        self.health(None)
        self.assertEqual(cli.ensure_server(self.data), "disabled")
        self.assertEqual(self.spawned, [])


if __name__ == "__main__":
    unittest.main()
