from datetime import timedelta
import re
from unittest.mock import patch

from backend import config, db, service
from backend.security import iso, utc_now
from backend.tests.base import ApiTestCase


class CommunityDeletionTests(ApiTestCase):
    @classmethod
    def setUpClass(cls):
        config.ADMIN_EMAIL = "delete-super@touchline.test"
        config.ADMIN_PASSWORD = "super-admin-password"
        config.ADMIN_NAME = "Deletion Super Admin"
        super().setUpClass()

    def setUp(self):
        from backend.ratelimit import limiter
        limiter.reset()
        db.reset_database()
        self.super_token = self.data(self.request("POST", "/api/v1/auth/admin", {
            "email": config.ADMIN_EMAIL, "password": config.ADMIN_PASSWORD,
        }))['token']

    def create_member(self, email, name):
        with patch("backend.service.send_email") as send:
            self.data(self.request("POST", "/api/v1/auth/register", {
                "name": name, "email": email, "password": "member-password-123",
            }))
        link = send.call_args.args[2]
        token = re.search(r"verify_token=([A-Za-z0-9_-]+)", link).group(1)
        self.data(self.request("POST", "/api/v1/auth/verify-email", {"token": token}))
        return self.data(self.request("POST", "/api/v1/auth/login", {
            "email": email, "password": "member-password-123",
        }))

    def create_community(self, token, name):
        return self.data(self.request("POST", "/api/v1/communities", {
            "name": name, "sport": "Soccer", "kind": "Club", "description": "Deletion approval test community",
        }, token=token))

    def add_admin(self, owner_token, community_id, user_token, email):
        self.data(self.request("POST", f"/api/v1/communities/{community_id}/members", {"email": email}, token=owner_token))
        me = self.data(self.request("GET", "/api/v1/me", token=user_token))
        return self.data(self.request("PATCH", f"/api/v1/communities/{community_id}/members/{me['id']}", {
            "role": "Admin",
        }, token=owner_token))

    def test_all_community_admins_and_super_admin_must_approve(self):
        owner = self.create_member("delete-owner@touchline.test", "Delete Owner")
        second = self.create_member("delete-second@touchline.test", "Second Admin")
        community = self.create_community(owner["token"], "Two Admin Club")
        self.add_admin(owner["token"], community["id"], second["token"], "delete-second@touchline.test")

        request = self.data(self.request("POST", f"/api/v1/communities/{community['id']}/deletion-requests", token=owner["token"]))
        self.assertEqual(request["status"], "pending_admins")
        self.assertEqual(request["approvalCount"], 1)
        self.error(self.request("POST", f"/api/v1/admin/community-deletions/{request['id']}/decision", {
            "decision": "approve",
        }, token=self.super_token), 409, "deletion_not_ready")

        approved = self.data(self.request("POST", f"/api/v1/communities/{community['id']}/deletion-requests/{request['id']}/approve", token=second["token"]))
        self.assertEqual(approved["status"], "pending_super_admin")
        self.assertIsNotNone(approved["superAdminDueAt"])
        self.error(self.request("POST", f"/api/v1/admin/community-deletions/{request['id']}/decision", {
            "decision": "deny",
        }, token=owner["token"]), 403, "forbidden")

        denied = self.data(self.request("POST", f"/api/v1/admin/community-deletions/{request['id']}/decision", {
            "decision": "deny",
        }, token=self.super_token))
        self.assertEqual(denied["status"], "denied")
        self.assertEqual(self.data(self.request("GET", "/api/v1/communities", token=owner["token"]))[0]["id"], community["id"])

    def test_timeout_setting_is_super_admin_only_and_auto_expiry_deletes(self):
        owner = self.create_member("expiry-owner@touchline.test", "Expiry Owner")
        community = self.create_community(owner["token"], "Expiry Club")
        self.error(self.request("PATCH", "/api/v1/admin/community-deletion-settings", {"days": 1}, token=owner["token"]), 403, "forbidden")
        setting = self.data(self.request("PATCH", "/api/v1/admin/community-deletion-settings", {"days": 2}, token=self.super_token))
        self.assertEqual(setting["timeoutDays"], 2)
        request = self.data(self.request("POST", f"/api/v1/communities/{community['id']}/deletion-requests", token=owner["token"]))
        self.assertEqual(request["status"], "pending_super_admin")
        with db.connect() as connection:
            connection.execute("UPDATE community_deletion_requests SET super_admin_due_at=? WHERE id=?", (iso(utc_now() - timedelta(seconds=1)), request["id"]))
        self.assertEqual(service.expire_community_deletions(), 1)
        self.assertEqual(self.data(self.request("GET", "/api/v1/communities", token=owner["token"])), [])

    def test_super_admin_approval_deletes_the_community_and_its_team(self):
        owner = self.create_member("approve-owner@touchline.test", "Approve Owner")
        community = self.create_community(owner["token"], "Approval Club")
        team = self.data(self.request("POST", "/api/v1/teams", {
            "community_id": community["id"], "name": "Approval FC", "age_group": "Adult",
            "league": "Local", "coach": "Coach",
        }, token=owner["token"]))
        request = self.data(self.request("POST", f"/api/v1/communities/{community['id']}/deletion-requests", token=owner["token"]))
        self.assertEqual(request["status"], "pending_super_admin")
        result = self.data(self.request("POST", f"/api/v1/admin/community-deletions/{request['id']}/decision", {
            "decision": "approve",
        }, token=self.super_token))
        self.assertEqual(result["status"], "deleted")
        bootstrap = self.data(self.request("GET", "/api/v1/bootstrap", token=owner["token"]))
        self.assertEqual(bootstrap["communities"], [])
        self.assertNotIn(team["id"], {row["id"] for row in bootstrap["teams"]})

    def test_only_super_admin_can_list_deletion_settings_and_invalid_windows_are_rejected(self):
        owner = self.create_member("panel-owner@touchline.test", "Panel Owner")
        self.error(self.request("GET", "/api/v1/admin/community-deletions", token=owner["token"]), 403, "forbidden")
        self.error(self.request("PATCH", "/api/v1/admin/community-deletion-settings", {"days": 31}, token=self.super_token), 400, "invalid_field")
        panel = self.data(self.request("GET", "/api/v1/admin/community-deletions", token=self.super_token))
        self.assertEqual(panel["timeoutDays"], 7)

    def test_community_admin_cannot_skip_other_admin_approval(self):
        owner = self.create_member("requester@touchline.test", "Requester")
        second = self.create_member("other-admin@touchline.test", "Other Admin")
        member = self.create_member("regular-member@touchline.test", "Regular Member")
        community = self.create_community(owner["token"], "Must Agree Club")
        self.add_admin(owner["token"], community["id"], second["token"], "other-admin@touchline.test")
        self.data(self.request("POST", f"/api/v1/communities/{community['id']}/members", {
            "email": "regular-member@touchline.test",
        }, token=owner["token"]))
        request = self.data(self.request("POST", f"/api/v1/communities/{community['id']}/deletion-requests", token=owner["token"]))
        self.error(self.request("POST", f"/api/v1/communities/{community['id']}/deletion-requests/{request['id']}/approve", token=member["token"]), 403, "forbidden")
        self.error(self.request("POST", f"/api/v1/communities/{community['id']}/deletion-requests/{request['id']}/approve", token=self.super_token), 403, "forbidden")
