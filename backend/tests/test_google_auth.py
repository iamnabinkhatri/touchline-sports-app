import urllib.parse
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import config, db, service
from backend.errors import ApiError
from backend.security import hash_token


class GoogleAuthTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original = {
            "DB_PATH": config.DB_PATH,
            "GOOGLE_CLIENT_ID": config.GOOGLE_CLIENT_ID,
            "GOOGLE_CLIENT_SECRET": config.GOOGLE_CLIENT_SECRET,
            "GOOGLE_REDIRECT_URI": config.GOOGLE_REDIRECT_URI,
            "PBKDF2_ITERATIONS": config.PBKDF2_ITERATIONS,
        }
        config.DB_PATH = Path(self.temp_dir.name) / "google-auth.db"
        config.GOOGLE_CLIENT_ID = "google-client-id.apps.googleusercontent.com"
        config.GOOGLE_CLIENT_SECRET = "test-secret"
        config.GOOGLE_REDIRECT_URI = "https://touchline.example/"
        config.PBKDF2_ITERATIONS = 1000
        db.reset_database()
        self.connection = db.connect()

    def tearDown(self):
        self.connection.close()
        for key, value in self.original.items():
            setattr(config, key, value)
        self.temp_dir.cleanup()

    def begin(self, extra=None):
        result = service.google_login_start(self.connection, extra or {})
        query = urllib.parse.parse_qs(urllib.parse.urlparse(result["authorizationUrl"]).query)
        self.assertEqual(query["client_id"][0], config.GOOGLE_CLIENT_ID)
        self.assertEqual(query["redirect_uri"][0], config.GOOGLE_REDIRECT_URI)
        self.assertEqual(query["code_challenge_method"][0], "S256")
        state = query["state"][0]
        nonce = self.connection.execute("SELECT nonce FROM google_login_states WHERE state_hash=?", (hash_token(state),)).fetchone()["nonce"]
        return state, nonce

    def complete(self, state, nonce, *, email="google-user@example.test", verified=True, subject="google-subject-1"):
        claims = {"sub": subject, "email": email, "email_verified": verified, "name": "Google User", "nonce": nonce}
        with patch("backend.service._exchange_google_code", return_value="mock-google-id-token"), patch("backend.service._verify_google_id_token", return_value=claims):
            return service.google_login_complete(self.connection, {"code": "mock-code", "state": state})

    def test_google_login_creates_verified_user_and_reuses_identity(self):
        state, nonce = self.begin()
        created = self.complete(state, nonce)
        self.assertTrue(created["created"])
        self.assertEqual(created["user"]["email"], "google-user@example.test")
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM users WHERE email='google-user@example.test'").fetchone()[0], 1)
        state, nonce = self.begin()
        returning = self.complete(state, nonce)
        self.assertFalse(returning["created"])
        self.assertEqual(returning["user"]["id"], created["user"]["id"])

    def test_google_oauth_state_is_one_time_and_email_must_be_verified(self):
        state, nonce = self.begin()
        self.complete(state, nonce)
        with self.assertRaises(ApiError) as replay:
            self.complete(state, nonce)
        self.assertEqual(replay.exception.code, "invalid_oauth_state")
        state, nonce = self.begin()
        with self.assertRaises(ApiError) as unverified:
            self.complete(state, nonce, email="unverified@example.test", verified=False)
        self.assertEqual(unverified.exception.code, "google_email_unverified")
        self.assertIsNone(self.connection.execute("SELECT 1 FROM users WHERE email='unverified@example.test'").fetchone())

    def test_google_signin_is_hidden_and_rejected_until_credentials_exist(self):
        config.GOOGLE_CLIENT_ID = ""
        self.assertFalse(service.google_login_config()["enabled"])
        with self.assertRaises(ApiError) as disabled:
            service.google_login_start(self.connection, {})
        self.assertEqual(disabled.exception.status, 503)


if __name__ == "__main__":
    unittest.main()
