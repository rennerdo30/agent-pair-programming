import http.client
import json
import unittest
import uuid

from helpers import PNG, PNG_B64, Clock, TempDirCase

from pair_desk import VERSION
from pair_desk.server import start_in_thread
from pair_desk.store import Store


class ApiCase(TempDirCase):
    def setUp(self):
        super().setUp()
        self.clock = Clock()
        self.store = Store(self.tmp, clock=self.clock)
        self.server, self.thread = start_in_thread(self.store, 0)
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.store.close()
        super().tearDown()

    def req(self, method, path, body=None, headers=None, raw=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        h = dict(headers or {})
        data = raw
        if body is not None:
            data = json.dumps(body).encode()
            h.setdefault("Content-Type", "application/json")
        conn.request(method, path, body=data, headers=h)
        res = conn.getresponse()
        payload = res.read()
        conn.close()
        ctype = res.getheader("Content-Type", "")
        parsed = json.loads(payload) if payload and ctype.startswith("application/json") else payload
        return res.status, parsed, res


class ApiTests(ApiCase):
    def make_project(self):
        status, p, _ = self.req("POST", "/api/projects", {"slug": "mygame", "name": "MyGame", "prefix": "MG"})
        self.assertEqual(status, 201)
        return p

    def test_health(self):
        status, data, _ = self.req("GET", "/api/health")
        self.assertEqual((status, data["ok"], data["version"]), (200, True, VERSION))

    def test_projects(self):
        self.make_project()
        status, data, _ = self.req("GET", "/api/projects")
        self.assertEqual(data["projects"][0]["slug"], "mygame")
        status, data, _ = self.req("GET", "/api/projects/mygame")
        self.assertEqual((status, data["prefix"]), (200, "MG"))
        status, data, _ = self.req("POST", "/api/projects", {"slug": "mygame", "name": "dup", "prefix": "ZZ"})
        self.assertEqual(status, 409)
        self.assertIn("error", data)
        self.assertEqual(self.req("GET", "/api/projects/nope")[0], 404)

    def test_issue_lifecycle_with_attachment_and_verdict(self):
        self.make_project()
        status, issue, _ = self.req("POST", "/api/projects/mygame/issues", {
            "title": "Water seam at dusk", "kind": "bug", "source": "game", "area": "water",
            "location": {"command": "/goto 10 20 30", "x": 10, "y": 20, "z": 30, "time": "18:00"},
            "attachments": [{"filename": "shot.png", "mime": "image/png", "data_base64": PNG_B64}]})
        self.assertEqual(status, 201)
        self.assertEqual(issue["id"], "MG-1")
        att = issue["attachments"][0]
        status, body, res = self.req("GET", att["url"])
        self.assertEqual((status, body), (200, PNG))
        self.assertEqual(res.getheader("Content-Type"), "image/png")
        self.assertIn("sandbox", res.getheader("Content-Security-Policy"))

        status, issue, _ = self.req("PATCH", "/api/issues/MG-1", {"status": "to_check", "priority": "p1", "actor": "claude"})
        self.assertEqual((status, issue["status"], issue["priority"]), (200, "to_check", "p1"))
        status, res, _ = self.req("POST", "/api/issues/MG-1/comments", {"author": "owner", "text": "still there", "verdict": "failed"})
        self.assertEqual((status, res["issue"]["status"]), (201, "failed"))

        status, listing, _ = self.req("GET", "/api/projects/mygame/issues?status=failed&limit=5")
        self.assertEqual((listing["total"], listing["issues"][0]["last_verdict"]), (1, "failed"))
        status, listing, _ = self.req("GET", "/api/projects/mygame/issues?q=seam")
        self.assertEqual(listing["total"], 1)

        self.assertEqual(self.req("PATCH", "/api/issues/MG-1", {"kind": "nonsense"})[0], 400)
        self.assertEqual(self.req("GET", "/api/issues/MG-77")[0], 404)
        self.assertEqual(self.req("DELETE", "/api/issues/MG-1")[0], 200)
        self.assertEqual(self.req("GET", "/api/issues/MG-1")[0], 404)

    def test_attachment_upload_json_and_multipart(self):
        self.make_project()
        self.req("POST", "/api/projects/mygame/issues", {"title": "x"})
        status, data, _ = self.req("POST", "/api/issues/MG-1/attachments",
                                   {"filename": "a.png", "data_base64": PNG_B64})
        self.assertEqual((status, len(data["attachments"])), (201, 1))
        boundary = uuid.uuid4().hex
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"author\"\r\n\r\nowner\r\n"
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"b.png\"\r\n"
                f"Content-Type: image/png\r\n\r\n").encode() + PNG + f"\r\n--{boundary}--\r\n".encode()
        status, data, _ = self.req("POST", "/api/issues/MG-1/attachments", raw=body,
                                   headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        self.assertEqual(status, 201, data)
        self.assertEqual((data["attachments"][0]["filename"], data["attachments"][0]["size"]), ("b.png", len(PNG)))
        self.assertEqual(len(self.req("GET", "/api/issues/MG-1")[1]["attachments"]), 2)

    def test_non_image_attachment_is_download_only(self):
        self.make_project()
        self.req("POST", "/api/projects/mygame/issues", {"title": "x", "attachments": [
            {"filename": "x.html", "mime": "text/html", "data_base64": "PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg=="}]})
        att = self.req("GET", "/api/issues/MG-1")[1]["attachments"][0]
        status, _, res = self.req("GET", att["url"])
        self.assertEqual(res.getheader("Content-Type"), "application/octet-stream")
        self.assertTrue(res.getheader("Content-Disposition").startswith("attachment"))

    def test_command_queue(self):
        self.make_project()
        self.req("POST", "/api/projects/mygame/issues", {"title": "x", "command": "/goto 1 2 3"})
        status, empty, _ = self.req("GET", "/api/projects/mygame/commands/next?client=game")
        self.assertEqual(status, 204)
        status, cmd, _ = self.req("POST", "/api/projects/mygame/commands", {"command": "/goto 1 2 3", "issue": "MG-1"})
        self.assertEqual((status, cmd["state"]), (201, "pending"))
        status, got, _ = self.req("GET", "/api/projects/mygame/commands/next?client=mygame-dev")
        self.assertEqual((status, got["id"], got["command"], got["client"]), (200, cmd["id"], "/goto 1 2 3", "mygame-dev"))
        self.assertEqual(self.req("GET", "/api/projects/mygame/commands/next?client=mygame-dev")[0], 204)
        status, state, _ = self.req("GET", f"/api/commands/{cmd['id']}")
        self.assertEqual(state["state"], "delivered")
        self.req("POST", "/api/projects/mygame/commands", {"command": "/late"})
        self.clock.advance(minutes=11)
        self.assertEqual(self.req("GET", "/api/projects/mygame/commands/next")[0], 204)
        status, listing, _ = self.req("GET", "/api/projects/mygame/commands")
        self.assertEqual([c["state"] for c in listing["commands"]], ["expired", "delivered"])

    def test_cors_and_origin_policy(self):
        status, _, res = self.req("GET", "/api/health", headers={"Origin": "http://127.0.0.1:5173"})
        self.assertEqual(status, 200)
        self.assertEqual(res.getheader("Access-Control-Allow-Origin"), "http://127.0.0.1:5173")
        status, _, res = self.req("GET", "/api/health", headers={"Origin": "null"})
        self.assertEqual((status, res.getheader("Access-Control-Allow-Origin")), (200, "null"))
        status, _, _ = self.req("POST", "/api/projects", {"slug": "evil", "name": "e", "prefix": "EV"},
                                headers={"Origin": "https://evil.example"})
        self.assertEqual(status, 403)
        self.assertEqual(self.req("GET", "/api/projects")[1]["projects"], [])
        status, _, _ = self.req("GET", "/api/health", headers={"Host": "evil.example:8765"})
        self.assertEqual(status, 403)
        status, _, res = self.req("OPTIONS", "/api/projects", headers={"Origin": "http://127.0.0.1"})
        self.assertEqual(status, 204)
        self.assertIn("PATCH", res.getheader("Access-Control-Allow-Methods"))

    def test_errors(self):
        self.assertEqual(self.req("GET", "/api/nothing")[0], 404)
        self.assertEqual(self.req("PUT", "/api/projects")[0], 501)
        self.assertEqual(self.req("DELETE", "/api/projects")[0], 405)
        status, data, _ = self.req("POST", "/api/projects", raw=b"{not json", headers={"Content-Type": "application/json"})
        self.assertEqual(status, 400)

    def test_static_ui(self):
        status, body, res = self.req("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Pair Desk", body)
        self.assertIn("script-src 'self'", res.getheader("Content-Security-Policy"))
        status, _, res = self.req("GET", "/app.js")
        self.assertEqual((status, res.getheader("Content-Type").split(";")[0]), (200, "text/javascript"))
        self.assertEqual(self.req("GET", "/../pair_desk/store.py")[0], 404)
        self.assertEqual(self.req("GET", "/%2e%2e/desk.py")[0], 404)

    def test_keep_alive_survives_rejected_body(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("POST", "/api/nowhere", body=b'{"a": 1}', headers={"Content-Type": "application/json"})
        r = conn.getresponse()
        r.read()
        self.assertEqual(r.status, 404)
        conn.close()
        self.assertEqual(self.req("GET", "/api/health")[0], 200)


if __name__ == "__main__":
    unittest.main()
