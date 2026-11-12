import re
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from backend import config, db
from backend.security import hash_token
from backend.tests.base import ApiTestCase


class CommunityAdministrationTests(ApiTestCase):
    @classmethod
    def setUpClass(cls):
        config.ADMIN_EMAIL = "owner@community-admin.test"
        config.ADMIN_PASSWORD = "owner-password-123"
        config.ADMIN_NAME = "Platform Owner"
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
        token = re.search(r"[?&]verify_token=([A-Za-z0-9_-]+)", link).group(1)
        self.data(self.request("POST", "/api/v1/auth/verify-email", {"token": token}))
        return self.data(self.request("POST", "/api/v1/auth/login", {
            "email": email, "password": "member-password-123",
        }))['token']

    def create_community(self, token, name, privacy="Private"):
        return self.data(self.request("POST", "/api/v1/communities", {
            "name": name, "sport": "Soccer", "kind": "Club",
            "description": "Community role isolation test", "privacy": privacy,
        }, token=token))

    def create_team(self, token, community_id):
        return self.data(self.request("POST", "/api/v1/teams", {
            "community_id": community_id, "name": "Community FC", "age_group": "U18",
            "league": "Local League", "coach": "Coach One", "formation": "4-3-3",
        }, token=token))

    def test_community_admin_can_set_profile_theme_but_members_cannot(self):
        owner = self.create_member("theme-owner@example.test", "Theme Owner")
        member = self.create_member("theme-member@example.test", "Theme Member")
        community = self.create_community(owner, "Theme Club")
        self.data(self.request("POST", f"/api/v1/communities/{community['id']}/members", {
            "email": "theme-member@example.test",
        }, token=owner))

        updated = self.data(self.request("PATCH", f"/api/v1/communities/{community['id']}/theme", {
            "theme": "dark",
        }, token=owner))
        self.assertEqual(updated["profileTheme"], "dark")
        member_state = self.data(self.request("GET", "/api/v1/bootstrap", token=member))
        self.assertEqual(next(item for item in member_state["communities"] if item["id"] == community["id"])["profileTheme"], "dark")
        self.error(self.request("PATCH", f"/api/v1/communities/{community['id']}/theme", {
            "theme": "light",
        }, token=member), 403, "forbidden")
        self.error(self.request("PATCH", f"/api/v1/communities/{community['id']}/theme", {
            "theme": "neon",
        }, token=owner), 400, "invalid_field")

    def test_super_admin_can_set_global_app_theme_only(self):
        self.assertEqual(self.data(self.request("GET", "/api/v1/theme"))["theme"], "light")
        result = self.data(self.request("PATCH", "/api/v1/admin/app-theme", {
            "theme": "dark",
        }, token=self.super_token))
        self.assertEqual(result["theme"], "dark")
        self.assertEqual(self.data(self.request("GET", "/api/v1/theme"))["theme"], "dark")
        member = self.create_member("theme-nonadmin@example.test", "Theme Member")
        self.error(self.request("PATCH", "/api/v1/admin/app-theme", {
            "theme": "light",
        }, token=member), 403, "forbidden")
        state = self.data(self.request("GET", "/api/v1/bootstrap", token=member))
        self.assertEqual(state["appTheme"], "dark")

    def test_community_creator_can_create_team_and_players_for_their_group(self):
        owner = self.create_member("club-owner@example.test", "Club Owner")
        community = self.create_community(owner, "Owner Club")
        team = self.create_team(owner, community['id'])
        self.assertEqual(team['communityId'], community['id'])
        player = self.data(self.request("POST", "/api/v1/players", {
            "email": "club-owner@example.test", "name": "First Player", "number": 9, "pos": "ST",
        }, token=owner))
        self.assertEqual(player['name'], "First Player")

    def test_posts_can_only_be_deleted_by_author_community_admin_or_super_admin(self):
        owner = self.create_member("post-owner@example.test", "Post Owner")
        member = self.create_member("post-member@example.test", "Post Member")
        community = self.create_community(owner, "Post Permissions")
        self.data(self.request("POST", f"/api/v1/communities/{community['id']}/members", {"email": "post-member@example.test"}, token=owner))
        post = self.data(self.request("POST", "/api/v1/posts", {
            "community_id": community["id"], "text": "A post by the owner",
        }, token=owner))
        path = f"/api/v1/posts/{post['id']}"
        self.error(self.request("DELETE", path, token=member), 403, "forbidden")
        self.data(self.request("DELETE", path, token=owner))
        self.error(self.request("DELETE", path, token=owner), 404, "not_found")
        post = self.data(self.request("POST", "/api/v1/posts", {
            "community_id": community["id"], "text": "A post for admin removal",
        }, token=owner))
        members = self.data(self.request("GET", f"/api/v1/communities/{community['id']}/members", token=owner))
        member_id = next(row["id"] for row in members if row["email"] == "post-member@example.test")
        self.data(self.request("PATCH", f"/api/v1/communities/{community['id']}/members/{member_id}", {"role": "Admin"}, token=owner))
        self.data(self.request("DELETE", f"/api/v1/posts/{post['id']}", token=member))
        post = self.data(self.request("POST", "/api/v1/posts", {
            "community_id": community["id"], "text": "A post for super admin removal",
        }, token=owner))
        self.data(self.request("DELETE", f"/api/v1/posts/{post['id']}", token=self.super_token))

    def test_public_community_join_requires_admin_approval(self):
        owner = self.create_member("join-admin@example.test", "Join Admin")
        applicant = self.create_member("join-applicant@example.test", "Join Applicant")
        community = self.create_community(owner, "Approval Required", privacy="Public")
        private = self.create_community(owner, "Invite Only")
        with db.connect() as connection:
            applicant_id = connection.execute("SELECT id FROM users WHERE email=?", ("join-applicant@example.test",)).fetchone()["id"]
        visible = self.data(self.request("GET", "/api/v1/communities", token=applicant))
        self.assertIn(community["id"], [row["id"] for row in visible])
        self.assertNotIn(private["id"], [row["id"] for row in visible])
        boot = self.data(self.request("GET", "/api/v1/bootstrap", token=applicant))
        self.assertNotIn(private["id"], [row["id"] for row in boot["communities"]])
        self.error(self.request("POST", f"/api/v1/communities/{private['id']}/join-requests", token=applicant), 403, "invite_required")
        request = self.data(self.request("POST", f"/api/v1/communities/{community['id']}/join", token=applicant))
        self.assertEqual(request["joinRequestStatus"], "pending")
        self.assertFalse(request["joined"])
        self.assertEqual(request["memberCount"], 1)
        self.assertEqual(len(self.data(self.request("GET", f"/api/v1/communities/{community['id']}/members", token=owner))), 1)
        self.data(self.request("POST", f"/api/v1/communities/{community['id']}/join-requests", token=applicant))
        self.error(self.request("GET", f"/api/v1/communities/{community['id']}/messages", token=applicant), 403, "forbidden")
        self.error(self.request("GET", f"/api/v1/posts?community_id={community['id']}", token=applicant), 403, "forbidden")
        requests = self.data(self.request("GET", f"/api/v1/communities/{community['id']}/join-requests", token=owner))
        self.assertEqual([item["userId"] for item in requests], [applicant_id])
        self.error(self.request("GET", f"/api/v1/communities/{community['id']}/join-requests", token=applicant), 403, "forbidden")
        self.error(self.request("POST", f"/api/v1/communities/{community['id']}/join-requests/{applicant_id}/decision", {"decision": "approve"}, token=applicant), 403, "forbidden")
        approved = self.data(self.request("POST", f"/api/v1/communities/{community['id']}/join-requests/{applicant_id}/decision", {"decision": "approve"}, token=owner))
        self.assertEqual(approved["status"], "approved")
        self.assertTrue(next(item for item in self.data(self.request("GET", "/api/v1/communities", token=applicant)) if item["id"] == community["id"])["joined"])

        declined = self.create_member("join-declined@example.test", "Join Declined")
        with db.connect() as connection:
            declined_id = connection.execute("SELECT id FROM users WHERE email=?", ("join-declined@example.test",)).fetchone()["id"]
        self.data(self.request("POST", f"/api/v1/communities/{community['id']}/join-requests", token=declined))
        denied = self.data(self.request("POST", f"/api/v1/communities/{community['id']}/join-requests/{declined_id}/decision", {"decision": "deny"}, token=owner))
        self.assertEqual(denied["status"], "denied")
        retry = self.data(self.request("POST", f"/api/v1/communities/{community['id']}/join-requests", token=declined))
        self.assertEqual(retry["joinRequestStatus"], "pending")

    def test_community_admin_can_promote_members_and_manage_team(self):
        owner = self.create_member("club-owner2@example.test", "Club Owner")
        member = self.create_member("club-member@example.test", "Club Member")
        community = self.create_community(owner, "Admin Club")
        team = self.create_team(owner, community['id'])
        self.data(self.request("POST", f"/api/v1/communities/{community['id']}/members", {"email": "club-member@example.test"}, token=owner))
        members = self.data(self.request("GET", f"/api/v1/communities/{community['id']}/members", token=owner))
        member_row = next(row for row in members if row['email'] == "club-member@example.test")
        self.data(self.request("PATCH", f"/api/v1/communities/{community['id']}/members/{member_row['id']}", {
            "role": "Admin",
        }, token=owner))
        updated = self.data(self.request("PATCH", f"/api/v1/teams/{team['id']}", {
            "formation": "4-2-3-1",
        }, token=member))
        self.assertEqual(updated['formation'], "4-2-3-1")

    def test_community_admin_cannot_manage_another_community_or_promote_nonmembers(self):
        owner_a = self.create_member("owner-a@example.test", "Owner A")
        owner_b = self.create_member("owner-b@example.test", "Owner B")
        community_a = self.create_community(owner_a, "Community A")
        community_b = self.create_community(owner_b, "Community B")
        team = self.create_team(owner_b, community_b['id'])
        self.error(self.request("GET", f"/api/v1/communities/{community_b['id']}/members", token=owner_a), 403, "forbidden")
        self.error(self.request("PATCH", f"/api/v1/teams/{team['id']}", {
            "formation": "4-2-3-1",
        }, token=owner_a), 403, "forbidden")
        self.error(self.request("PATCH", f"/api/v1/communities/{community_a['id']}/members/not-a-member", {
            "role": "Admin",
        }, token=owner_a), 404, "not_found")

    def test_cannot_remove_the_last_community_admin(self):
        owner = self.create_member("last-admin@example.test", "Last Admin")
        community = self.create_community(owner, "Last Admin Club")
        owner_id = self.data(self.request("GET", f"/api/v1/communities/{community['id']}/members", token=owner))[0]['id']
        self.error(self.request("PATCH", f"/api/v1/communities/{community['id']}/members/{owner_id}", {
            "role": "Member",
        }, token=owner), 409, "last_admin")

    def test_community_admin_can_add_an_existing_verified_user_by_email(self):
        owner = self.create_member("member-manager@example.test", "Member Manager")
        target = self.create_member("new-member@example.test", "New Member")
        community = self.create_community(owner, "Member Add Club")
        added = self.data(self.request("POST", f"/api/v1/communities/{community['id']}/members", {
            "email": "NEW-MEMBER@example.test",
        }, token=owner))
        self.assertEqual(added["email"], "new-member@example.test")
        self.assertEqual(added["role"], "Member")
        self.assertEqual(len(self.data(self.request("GET", f"/api/v1/communities/{community['id']}/members", token=owner))), 2)

    def test_polls_created_from_a_community_are_scoped_to_that_community(self):
        community = self.create_community(self.super_token, "Poll House")
        poll = self.data(self.request("POST", "/api/v1/polls", {
            "question": "Which kickoff time works?", "category": "Club", "duration_hours": 24,
            "community_id": community["id"], "options": ["Morning", "Afternoon"],
        }, token=self.super_token))
        self.assertEqual(poll["communityId"], community["id"])
        bootstrap = self.data(self.request("GET", "/api/v1/bootstrap", token=self.super_token))
        self.assertEqual(next(item for item in bootstrap["polls"] if item["id"] == poll["id"])["communityId"], community["id"])
        other = self.create_member("outside-poll@example.test", "Outside Member")
        visible = self.data(self.request("GET", "/api/v1/polls", token=other))
        self.assertNotIn(poll["id"], {item["id"] for item in visible})
        self.error(self.request("GET", f"/api/v1/posts?community_id={community['id']}", token=other), 403, "forbidden")

    def test_community_admin_can_remove_a_member_but_cannot_remove_an_admin_directly(self):
        owner = self.create_member("remove-owner@example.test", "Remove Owner")
        member = self.create_member("remove-member@example.test", "Remove Member")
        community = self.create_community(owner, "Removal Club")
        added = self.data(self.request("POST", f"/api/v1/communities/{community['id']}/members", {"email": "remove-member@example.test"}, token=owner))
        removed = self.data(self.request("DELETE", f"/api/v1/communities/{community['id']}/members/{added['id']}", token=owner))
        self.assertTrue(removed["removed"])
        self.assertEqual(len(self.data(self.request("GET", f"/api/v1/communities/{community['id']}/members", token=owner))), 1)
        admin_id = self.data(self.request("GET", f"/api/v1/communities/{community['id']}/members", token=owner))[0]["id"]
        self.error(self.request("DELETE", f"/api/v1/communities/{community['id']}/members/{admin_id}", token=owner), 409, "admin_must_be_demoted")
        self.error(self.request("DELETE", f"/api/v1/communities/{community['id']}/members/{admin_id}", token=member), 403, "forbidden")

    def test_community_invite_link_can_be_shared_and_accepted(self):
        owner = self.create_member("invite-owner@example.test", "Invite Owner")
        target = self.create_member("invite-target@example.test", "Invite Target")
        community = self.create_community(owner, "Invite Club")
        invitation = self.data(self.request("POST", f"/api/v1/communities/{community['id']}/invites", token=owner))
        self.assertIn("community_invite=", invitation["url"])
        with db.connect() as connection:
            stored = connection.execute("SELECT token_hash FROM community_invites").fetchone()["token_hash"]
        self.assertEqual(stored, hash_token(invitation["token"]))
        self.assertNotEqual(stored, invitation["token"])
        accepted = self.data(self.request("POST", "/api/v1/community-invites/accept", {
            "token": invitation["token"],
        }, token=target))
        self.assertTrue(accepted["joined"])
        self.assertEqual(accepted["id"], community["id"])
        self.error(self.request("POST", "/api/v1/community-invites/accept", {
            "token": "invalid-token",
        }, token=target), 404, "invite_not_found")

    def test_calendar_events_are_private_to_each_community(self):
        owner_a = self.create_member("calendar-a@example.test", "Calendar A")
        owner_b = self.create_member("calendar-b@example.test", "Calendar B")
        community_a = self.create_community(owner_a, "Calendar Club A")
        community_b = self.create_community(owner_b, "Calendar Club B")
        date_value = (datetime.now(timezone.utc) + timedelta(days=4)).replace(microsecond=0).isoformat()
        event = self.data(self.request("POST", "/api/v1/calendar/events", {
            "community_id": community_a["id"], "title": "Private training", "type": "Training", "date": date_value,
        }, token=owner_a))
        day = date_value[:10]
        own = self.data(self.request("GET", f"/api/v1/calendar?community_id={community_a['id']}&from={day}&to={day}", token=owner_a))
        other = self.data(self.request("GET", f"/api/v1/calendar?community_id={community_b['id']}&from={day}&to={day}", token=owner_b))
        self.assertIn(event["id"], {entry["id"] for entry in own["entries"]})
        self.assertNotIn(event["id"], {entry["id"] for entry in other["entries"]})
        self.error(self.request("GET", f"/api/v1/calendar?community_id={community_a['id']}&from={day}&to={day}", token=owner_b), 403, "forbidden")
        schedule_b = self.data(self.request("GET", f"/api/v1/schedule?community_id={community_b['id']}", token=owner_b))
        self.assertNotIn(event["id"], {row["id"] for row in schedule_b["schedule"]})
        bootstrap_b = self.data(self.request("GET", "/api/v1/bootstrap", token=owner_b))
        self.assertNotIn(event["id"], {row["id"] for row in bootstrap_b["schedule"]})

    def test_super_admin_role_is_reported_consistently_after_bootstrap(self):
        payload = self.data(self.request("GET", "/api/v1/bootstrap", token=self.super_token))
        self.assertEqual(payload["user"]["role"], "Super Admin")
