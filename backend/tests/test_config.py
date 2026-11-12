import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import config, db, security
from backend.config import _load_local_env


class DotEnvTests(unittest.TestCase):
    def test_loads_values_and_quotes_without_overriding_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text('# comment\nTOUCHLINE_TEST_DOTENV="quoted value"\nTOUCHLINE_TEST_KEEP=file value\n', encoding="utf-8")
            os.environ.pop("TOUCHLINE_TEST_DOTENV", None)
            os.environ["TOUCHLINE_TEST_KEEP"] = "process value"
            try:
                _load_local_env(env_file)
                self.assertEqual(os.environ["TOUCHLINE_TEST_DOTENV"], "quoted value")
                self.assertEqual(os.environ["TOUCHLINE_TEST_KEEP"], "process value")
            finally:
                os.environ.pop("TOUCHLINE_TEST_DOTENV", None)
                os.environ.pop("TOUCHLINE_TEST_KEEP", None)


class AdminProvisioningTests(unittest.TestCase):
    def test_configured_admin_promotes_existing_member_and_revokes_old_sessions(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(config, "DB_PATH", Path(directory) / "app.db"), \
             patch.object(config, "ADMIN_EMAIL", ""), \
             patch.object(config, "ADMIN_PASSWORD", ""), \
             patch.object(config, "ADMIN_NAME", "Club Owner"):
            db.init_db()
            with db.connect() as connection:
                connection.execute("""INSERT INTO users
                    (id,name,email,password_hash,role,club_role,avatar_tone,member_since,club_points,email_verified,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (
                    "existing-member", "Club Owner", "owner@example.test",
                    security.hash_password("old-member-password"), "member", "Member", "sage", "2025", 0, 0,
                    security.iso(),
                ))
                connection.execute("INSERT INTO sessions(token_hash,user_id,created_at,expires_at) VALUES(?,?,?,?)", (
                    security.hash_token("old-session"), "existing-member", security.iso(), security.session_expiry(),
                ))
                connection.execute("INSERT INTO auth_tokens(token_hash,user_id,purpose,expires_at,created_at) VALUES(?,?,?,?,?)", (
                    security.hash_token("pending-verification"), "existing-member", "verify_email", security.session_expiry(), security.iso(),
                ))
            with patch.object(config, "ADMIN_EMAIL", "owner@example.test"), \
                 patch.object(config, "ADMIN_PASSWORD", "new-admin-password-123"):
                db.init_db()
            with db.connect() as connection:
                user = connection.execute("SELECT * FROM users WHERE id='existing-member'").fetchone()
                self.assertEqual(user["role"], "admin")
                self.assertEqual(user["club_role"], "Super Admin")
                self.assertEqual(user["email_verified"], 1)
                self.assertTrue(security.verify_password("new-admin-password-123", user["password_hash"]))
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM sessions WHERE user_id='existing-member'").fetchone()[0], 0)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM auth_tokens WHERE user_id='existing-member'").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
