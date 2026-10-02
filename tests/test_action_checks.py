import contextlib
import io
import json
import unittest

from helpers import StoreCase

from pair_desk.cli import main
from pair_desk.store import handover_problem


class ActionCheckTests(StoreCase):
    """PD-3: a check that is an action, not a place, carries location.action instead of a command."""

    def issue(self, **fields):
        return self.store.create_issue("mygame", {"title": "check", "source": "agent", **fields})

    def test_an_action_stands_in_for_the_location_command(self):
        issue = self.issue(location={"action": "Continue from the title", "seed": 4291})
        self.assertIsNone(handover_problem(issue))
        self.assertEqual(issue["location"]["action"], "Continue from the title")

    def test_a_check_with_neither_command_nor_action_cannot_be_handed_over(self):
        problem = handover_problem(self.issue(location={"seed": 4291}))
        self.assertIn("no location command", problem)
        self.assertIn("location.action", problem)

    def test_a_blank_action_is_not_an_action(self):
        self.assertIsNotNone(handover_problem(self.issue(location={"action": "   ", "seed": 1})))


class CliBodyAndActionTests(StoreCase):
    """PD-2: `add` and `edit` take --text like `comment`; a wrong flag fails with a short error."""

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = main(["--data", str(self.tmp), *argv])
            except SystemExit as stop:
                code = stop.code
        return code, out.getvalue(), err.getvalue()

    def test_add_takes_text_as_the_body_and_action_as_the_location(self):
        self.store.close()
        code, out, _ = self.run_cli("add", "--project", "mygame", "--title", "Quit", "--text", "**Quit closes.**",
                                    "--action", "Quit the game", "--json")
        self.assertEqual(code, 0)
        issue = json.loads(out)
        self.assertEqual(issue["body"], "**Quit closes.**")
        self.assertEqual(issue["location"]["action"], "Quit the game")

    def test_edit_clears_an_action_with_an_empty_value(self):
        self.store.close()
        _, out, _ = self.run_cli("add", "--project", "mygame", "--title", "Quit", "--action", "Quit the game", "--json")
        key = json.loads(out)["id"]
        code, out, _ = self.run_cli("edit", key, "--action", "", "--json")
        self.assertEqual(code, 0)
        self.assertNotIn("action", json.loads(out)["location"])

    def test_an_unknown_flag_fails_with_a_short_error(self):
        self.store.close()
        body = "\n".join(f"line {n} of a long markdown body" for n in range(60))
        code, out, err = self.run_cli("add", "--project", "mygame", "--title", "x", "--tetx", body)
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("unrecognized arguments", err)
        self.assertLess(len(err.splitlines()[-1]), 400, "the error line must not echo the whole body")


if __name__ == "__main__":
    unittest.main()
