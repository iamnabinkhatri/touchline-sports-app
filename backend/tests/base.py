import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from backend import config, db, server
from backend.ratelimit import limiter


class ApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()
        config.DB_PATH = Path(cls.tempdir.name) / "touchline-test.db"
        config.PBKDF2_ITERATIONS = 1000
        config.DEMO_MODE = True
        config.CORS_ORIGINS = {
            "http://127.0.0.1:4173",
            "http://localhost:4173",
            "https://app.touchline.test",
            "capacitor://localhost",
            "http://localhost",
            "https://localhost",
        }
        db.init_db()
        cls.httpd = server.create_server("127.0.0.1", 0)
        cls.httpd.quiet = True
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=2)
        cls.tempdir.cleanup()

    def setUp(self):
        limiter.reset()
        self._test_player_account_index = 0
        db.reset_database()
        response = self.request("POST", "/api/v1/auth/demo")
        self.assertEqual(response["status"], 200, response)
        self.assertIn("token", response["json"]["data"])
        self.token = response["json"]["data"]["token"]
        self.user = response["json"]["data"]["user"]

    def unique_player_email(self):
        """Insert a distinct verified account for new player API contracts."""
        self._test_player_account_index += 1
        index = self._test_player_account_index
        email = f"roster-player-{index}@example.test"
        now = "2026-01-01T00:00:00Z"
        with db.connect() as connection:
            connection.execute("INSERT INTO users(id,name,email,password_hash,role,member_since,created_at,email_verified) VALUES(?,?,?,?,?,?,?,1)", (f"roster-player-{index}", f"Roster Player {index}", email, "disabled", "member", "2026", now))
        return email

    def request(self, method, path, body=None, token=None, headers=None, origin=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        request_headers = dict(headers or {})
        payload = None
        if body is not None:
            payload = json.dumps(body).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        if token:
            request_headers["Authorization"] = f"Bearer {token}"
        if origin:
            request_headers["Origin"] = origin
        connection.request(method, path, body=payload, headers=request_headers)
        response = connection.getresponse()
        raw = response.read()
        content_type = response.getheader("Content-Type") or ""
        parsed = None
        if "application/json" in content_type and raw:
            parsed = json.loads(raw.decode("utf-8"))
        result = {
            "status": response.status,
            "headers": {key.lower(): value for key, value in response.getheaders()},
            "body": raw,
            "content_type": content_type,
            "json": parsed,
        }
        connection.close()
        return result

    def authed(self, method, path, body=None, **kwargs):
        return self.request(method, path, body=body, token=self.token, **kwargs)

    def data(self, response, status=200):
        self.assertEqual(response["status"], status, response.get("body"))
        self.assertTrue(response["json"]["ok"], response.get("body"))
        return response["json"]["data"]

    def error(self, response, status, code=None):
        self.assertEqual(response["status"], status, response.get("body"))
        self.assertFalse(response["json"]["ok"])
        if code:
            self.assertEqual(response["json"]["error"]["code"], code)
        return response["json"]["error"]
