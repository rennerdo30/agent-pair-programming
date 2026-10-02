"""PD-4: a desk write from a sandbox that can only read the desk is queued in the job's outbox, never lost, and
the merging session replays it."""
import contextlib
import io
import json
import os
import sqlite3
from unittest import mock

from helpers import TempDirCase

from pair_desk import cli
from pair_desk.store import Store


class OutboxTests(TempDirCase):
    def setUp(self):
        super().setUp()
        self.data = self.tmp / "data"
        with Store(self.data) as store:
            store.create_project("mygame", "MyGame", "MG")
            store.create_issue("mygame", {"title": "first", "source": "agent"})
        self.outbox = self.tmp / "work" / ".cache" / "pair-desk-outbox.jsonl"
        os.environ[cli.OUTBOX_ENV] = str(self.outbox)
        self.addCleanup(os.environ.pop, cli.OUTBOX_ENV, None)

    def run_cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = cli.main(["--data", str(self.data), *argv])
        return code, out.getvalue()

    def read_only(self):
        real = Store.__enter__

        def enter(store):
            entered = real(store)
            raise sqlite3.OperationalError("attempt to write a readonly database")
        return mock.patch.object(Store, "__enter__", enter)

    def test_a_read_only_write_is_queued_not_lost(self):
        with self.read_only():
            code, out = self.run_cli("comment", "MG-1", "--text", "plan posted from a sandbox")
        self.assertEqual(code, 0)
        self.assertIn("queued", out)
        entries = [json.loads(line) for line in self.outbox.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(entries), 1)
        self.assertIn("plan posted from a sandbox", entries[0]["argv"])

    def test_reads_are_not_queued(self):
        with self.read_only():
            code, _ = self.run_cli("list", "--project", "mygame")
        self.assertEqual(code, 1)
        self.assertFalse(self.outbox.exists())

    def test_replay_applies_the_queued_writes_and_retires_the_outbox(self):
        with self.read_only():
            self.run_cli("add", "--project", "mygame", "--title", "found in a sandbox", "--text", "evidence")
        code, out = self.run_cli("outbox", "replay", str(self.outbox))
        self.assertEqual(code, 0, out)
        self.assertFalse(self.outbox.exists())
        with Store(self.data) as store:
            titles = [i["title"] for i in store.list_issues("mygame")["issues"]]
        self.assertIn("found in a sandbox", titles)
