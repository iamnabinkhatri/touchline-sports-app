"""Approval and lifecycle tests for API credentials."""
import re
from unittest.mock import patch

from backend import config, db
from backend.tests.base import ApiTestCase


class ApiKeyAccessTests(ApiTestCase):
    @classmethod
    def setUpClass(cls):
        config.ADMIN_EMAIL = "api-key-owner@example.test"
        config.ADMIN_PASSWORD = "api-key-owner-password-123"
        config.ADMIN_NAME = "API Key Super Admin"
        super().setUpClass()

    def setUp(self):
        from backend.ratelimit import limiter
        limiter.reset()
        db.reset_database()
        login = self.data(self.request("POST", "/api/v1/auth/admin", {
            "email": config.ADMIN_EMAIL, "password": config.ADMIN_PASSWORD,
        }))
        self.admin_token = login["token"]
        self.admin_id = login["user"]["id"]
        with patch("backend.service.send_email") as send:
            self.request("POST", "/api/v1/auth/register", {
                "name": "API Caller", "email": "api-caller@example.test", "password": "caller-password-123",
            })
        link = send.call_args.args[2]
        verify_token = re.search(r"[?&]verify_token=([A-Za-z0-9_-]+)", link).group(1)
        self.data(self.request("POST", "/api/v1/auth/verify-email", {"token": verify_token}))
        caller = self.data(self.request("POST", "/api/v1/auth/login", {
            "email": "api-caller@example.test", "password": "caller-password-123",
        }))
        self.caller_token = caller["token"]
        self.caller_id = caller["user"]["id"]

    def test_api_key_requires_super_admin_approval_and_can_be_revoked(self):
        self.error(self.request("GET", "/api/v1/communities"), 401, "unauthorized")
        self.error(self.request("GET", "/api/v1/openapi.json"), 401, "unauthorized")
        self.error(self.request("GET", "/api/v1"), 401, "unauthorized")
        spec = self.data(self.request("GET", "/api/v1/openapi.json", token=self.admin_token))
        self.assertIn("ApiKeyAuth", spec["components"]["securitySchemes"])
        requested = self.data(self.request("POST", "/api/v1/me/api-key-requests", {
            "reason": "Read club data from my private integration.",
        }, token=self.caller_token))
        self.assertEqual(requested["status"], "pending")
        self.error(self.request("POST", "/api/v1/me/api-key-claim", {}, token=self.caller_token), 409, "api_key_not_approved")
        pending = self.data(self.request("GET", "/api/v1/admin/api-key-requests", token=self.admin_token))
        self.assertEqual([row["userId"] for row in pending], [self.caller_id])
        self.error(self.request("GET", "/api/v1/admin/api-key-requests", token=self.caller_token), 403, "forbidden")
        self.error(self.request("POST", f"/api/v1/admin/api-key-requests/{requested['id']}/decision", {"decision": "approve"}, token=self.caller_token), 403, "forbidden")
        approved = self.data(self.request("POST", f"/api/v1/admin/api-key-requests/{requested['id']}/decision", {"decision": "approve"}, token=self.admin_token))
        self.assertEqual(approved["status"], "approved")
        self.assertTrue(self.data(self.request("GET", "/api/v1/me/api-key", token=self.caller_token))["canClaim"])
        claimed = self.data(self.request("POST", "/api/v1/me/api-key-claim", {}, token=self.caller_token))
        self.assertTrue(claimed["apiKey"].startswith("tl_live_"))
        key = claimed["apiKey"]
        with db.connect() as connection:
            stored_hash = connection.execute("SELECT key_hash FROM api_keys WHERE id=?", (claimed["id"],)).fetchone()["key_hash"]
        self.assertNotEqual(stored_hash, key)
        self.assertEqual(self.data(self.request("GET", "/api/v1/communities", headers={"X-API-Key": key})), [])
        self.error(self.request("GET", "/api/v1/communities", headers={"X-API-Key": "tl_live_invalid-key"}), 401, "unauthorized")
        self.error(self.request("GET", "/api/v1/me", headers={"X-API-Key": key}), 401, "unauthorized")
        self.error(self.request("GET", "/api/v1/admin/api-key-requests", headers={"X-API-Key": key}), 403, "forbidden")
        self.error(self.request("POST", "/api/v1/me/api-key-claim", {}, token=self.caller_token), 409, "api_key_already_claimed")
        self.data(self.request("DELETE", "/api/v1/me/api-key", token=self.caller_token))
        self.error(self.request("GET", "/api/v1/communities", headers={"X-API-Key": key}), 401, "unauthorized")

