import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from backend import config, db, server


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_db = config.DB_PATH
        self.original_iterations = config.PBKDF2_ITERATIONS
        config.DB_PATH = Path(self.tempdir.name) / "persist.db"
        config.PBKDF2_ITERATIONS = 1000
        db.init_db()
        self.server = None
        self.thread = None

    def tearDown(self):
        self.stop_server()
        config.DB_PATH = self.original_db
        config.PBKDF2_ITERATIONS = self.original_iterations
        self.tempdir.cleanup()

    def start_server(self):
        self.stop_server()
        self.server = server.create_server("127.0.0.1", 0)
        self.server.quiet = True
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop_server(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        if self.thread:
            self.thread.join(timeout=2)
            self.thread = None

    def request(self, method, path, body=None, token=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        headers = {}
        payload = None
        if body is not None:
            payload = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"
        connection.request(method, path, body=payload, headers=headers)
        response = connection.getresponse()
        raw = response.read()
        connection.close()
        parsed = json.loads(raw.decode()) if raw else None
        return response.status, parsed

    def test_data_and_session_survive_a_server_restart(self):
        self.start_server()
        status, demo = self.request("POST", "/api/v1/auth/demo")
        self.assertEqual(status, 200)
        token = demo["data"]["token"]
        status, post = self.request("POST", "/api/v1/posts", {
            "community_id": "brooklyn",
            "text": "Survives a restart",
            "tag": "club",
        }, token=token)
        self.assertEqual(status, 200, post)
        post_id = post["data"]["id"]

        self.stop_server()
        self.start_server()

        status, bootstrap = self.request("GET", "/api/v1/bootstrap", token=token)
        self.assertEqual(status, 200, bootstrap)
        self.assertTrue(any(item["id"] == post_id for item in bootstrap["data"]["posts"]))
        self.assertEqual(bootstrap["data"]["user"]["name"], "Alex Kim")
