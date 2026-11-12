"""TDD coverage for email auth, two-factor auth, and community chat APIs."""
import re
from unittest.mock import patch
from datetime import timedelta
from zoneinfo import ZoneInfo

from backend import config, db, service
from backend.mailer import MailDeliveryError
from backend.security import utc_now
from backend.tests.base import ApiTestCase


class AccountAndChatFeatureTests(ApiTestCase):
    @classmethod
    def setUpClass(cls):
        config.ADMIN_EMAIL = "owner@touchline.test"
        config.ADMIN_PASSWORD = "correct-owner-password"
        config.ADMIN_NAME = "Owner"
        config.TWO_FACTOR_ENCRYPTION_KEY = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
        super().setUpClass()

    def setUp(self):
        from backend.ratelimit import limiter
        limiter.reset()
        self._test_player_account_index = 0
        db.reset_database()
        result = self.data(self.request("POST", "/api/v1/auth/admin", {
            "email": config.ADMIN_EMAIL,
            "password": config.ADMIN_PASSWORD,
        }))
        self.token = result["token"]
        self.user = result["user"]

    def create_pending_user(self, email="new@example.test", name="New Member"):
        with patch("backend.service.send_email", create=True) as send:
            result = self.request("POST", "/api/v1/auth/register", {
                "name": name, "email": email, "password": "member-password-123",
            })
        self.assertEqual(result["status"], 200, result["body"])
        sent_body = send.call_args.args[2]
        token_text = re.search(r"[?&]verify_token=([A-Za-z0-9_-]+)", sent_body).group(1)
        return token_text, sent_body, result["json"]["data"]

    def create_community_member(self, community_id, email, name):
        pending = self.create_pending_user(email, name)
        self.data(self.request("POST", "/api/v1/auth/verify-email", {"token": pending[0]}))
        session = self.data(self.request("POST", "/api/v1/auth/login", {
            "email": email, "password": "member-password-123",
        }))
        self.data(self.authed("POST", f"/api/v1/communities/{community_id}/members", {"email": email}))
        return session

    def test_post_notifications_are_scoped_to_each_member_and_mark_read(self):
        community_a = self.data(self.authed("POST", "/api/v1/communities", {
            "name": "North Club", "sport": "Soccer", "kind": "Club", "description": "North side", "privacy": "Public",
        }))
        community_b = self.data(self.authed("POST", "/api/v1/communities", {
            "name": "South Club", "sport": "Soccer", "kind": "Club", "description": "South side", "privacy": "Public",
        }))
        member = self.create_community_member(community_a["id"], "stack-member@example.test", "Stack Member")
        self.data(self.authed("POST", f"/api/v1/communities/{community_b['id']}/members", {"email": "stack-member@example.test"}))
        post_a = self.data(self.authed("POST", "/api/v1/posts", {
            "community_id": community_a["id"], "text": "North match report with the winning goal.",
        }))
        post_b = self.data(self.authed("POST", "/api/v1/posts", {
            "community_id": community_b["id"], "text": "South training moved to Saturday.",
        }))

        notices = self.data(self.request("GET", "/api/v1/notifications", token=member["token"]))
        posts = [notice for notice in notices if notice["kind"] == "post"]
        self.assertEqual({notice["communityId"] for notice in posts}, {community_a["id"], community_b["id"]})
        self.assertEqual({notice["postId"] for notice in posts}, {post_a["id"], post_b["id"]})
        self.assertTrue(all(notice["unread"] for notice in posts))
        self.assertIn("winning goal", next(notice["body"] for notice in posts if notice["postId"] == post_a["id"]))
        self.assertEqual(next(notice["route"] for notice in posts if notice["postId"] == post_a["id"]), f"#/community/{community_a['id']}/posts/{post_a['id']}")
        owner_notices = self.data(self.authed("GET", "/api/v1/notifications"))
        self.assertFalse(any(notice["postId"] in {post_a["id"], post_b["id"]} for notice in owner_notices))

        read_response = self.data(self.request("POST", "/api/v1/notifications/read", {
            "ids": [posts[0]["id"]],
        }, token=member["token"]))
        self.assertFalse(next(notice["unread"] for notice in read_response if notice["id"] == posts[0]["id"]))
        bootstrap = self.data(self.request("GET", "/api/v1/bootstrap", token=member["token"]))
        self.assertEqual(sum(notice["unread"] for notice in bootstrap["notifications"]), 1)

    def test_poll_close_notice_reaches_all_community_members_once(self):
        community = self.data(self.authed("POST", "/api/v1/communities", {
            "name": "Poll Close Club", "sport": "Soccer", "kind": "Club", "description": "Poll close alerts", "privacy": "Public",
        }))
        member = self.create_community_member(community["id"], "poll-close-member@example.test", "Poll Member")
        poll = self.data(self.authed("POST", "/api/v1/polls", {
            "community_id": community["id"], "question": "Saturday pickup?", "category": "Club",
            "closes_at": service.iso(utc_now() + timedelta(hours=1)), "options": ["Yes", "No"],
        }))
        self.data(self.authed("POST", f"/api/v1/polls/{poll['id']}/vote", {"option_id": poll["options"][0]["id"]}))
        now = utc_now()
        with db.connect() as connection:
            connection.execute("UPDATE polls SET closes_at=? WHERE id=?", (service.iso(now - timedelta(seconds=1)), poll["id"]))
            service.process_due_polls(connection, now=now)
            service.process_due_polls(connection, now=now)

        owner_notices = self.data(self.authed("GET", "/api/v1/notifications"))
        member_notices = self.data(self.request("GET", "/api/v1/notifications", token=member["token"]))
        owner_closes = [notice for notice in owner_notices if notice["kind"] == "poll_closed"]
        member_closes = [notice for notice in member_notices if notice["kind"] == "poll_closed"]
        self.assertEqual(len(owner_closes), 1)
        self.assertEqual(len(member_closes), 1)
        self.assertEqual(owner_closes[0]["communityId"], community["id"])
        self.assertEqual(member_closes[0]["body"], "Saturday pickup? is now closed.")

    def test_capacitor_origins_can_preflight_the_same_authenticated_api(self):
        for origin in ("capacitor://localhost", "http://localhost", "https://localhost"):
            with self.subTest(origin=origin):
                response = self.request("OPTIONS", "/api/v1/bootstrap", headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "authorization,content-type",
                })
                self.assertEqual(response["status"], 204)
                self.assertEqual(response["headers"].get("access-control-allow-origin"), origin)
                self.assertIn("Authorization", response["headers"].get("access-control-allow-headers", ""))

    def test_poll_feedback_schedule_uses_local_game_time_rules(self):
        morning = service.poll_feedback_due_at("2026-11-12T06:30:00-05:00", "America/New_York")
        evening = service.poll_feedback_due_at("2026-11-12T19:30:00-05:00", "America/New_York")
        self.assertEqual(morning.astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M"), "2026-11-12 10:00")
        self.assertEqual(evening.astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M"), "2026-11-12 22:00")

    def test_pickup_poll_closes_balances_odd_roster_and_emails_voters(self):
        community = self.data(self.authed("POST", "/api/v1/communities", {
            "name": "Poll Match Club", "sport": "Soccer", "kind": "Club", "description": "Poll scheduler", "privacy": "Public",
        }))
        team = self.data(self.authed("POST", "/api/v1/teams", {
            "community_id": community["id"], "name": "Poll XI", "age_group": "Adult", "league": "Pickup", "coach": "Owner", "formation": "4-3-3",
        }))
        players = []
        for i, pos in enumerate(["GK", "CB", "CM", "ST", "LW"], 1):
            email = f"pickup-in-{i}@example.test"
            pending = self.create_pending_user(email, name=f"Player {i}")
            self.data(self.request("POST", "/api/v1/auth/verify-email", {"token": pending[0]}))
            players.append(self.data(self.authed("POST", "/api/v1/players", {
                "team_id": team["id"], "email": email, "name": f"Player {i}", "number": i, "pos": pos,
            })))
        from backend.security import iso
        now = utc_now()
        poll = self.data(self.authed("POST", "/api/v1/polls", {
            "question": "Who is playing?", "category": "Pickup", "community_id": community["id"],
            "closes_at": iso(now + timedelta(hours=1)), "game_at": iso(now + timedelta(hours=3)), "options": ["Yes", "No"],
        }))
        self.assertEqual([option["label"] for option in poll["options"]], ["Yes", "No"])
        in_sessions = []
        for index, player in enumerate(players, 1):
            email = f"pickup-in-{index}@example.test"
            member = self.data(self.request("POST", "/api/v1/auth/login", {"email": email, "password": "member-password-123"}))
            self.data(self.request("POST", f"/api/v1/polls/{poll['id']}/vote", {"option_id": poll["options"][0]["id"], "player_id": player["id"], "guest_count": 2 if index == 1 else 0}, token=member["token"]))
            in_sessions.append(member)
        self.error(self.request("POST", f"/api/v1/polls/{poll['id']}/vote", {"option_id": poll["options"][0]["id"]}, token=in_sessions[0]["token"]), 400, "player_required")
        out_pending = self.create_pending_user("pickup-out@example.test", name="Pickup Out")
        self.data(self.request("POST", "/api/v1/auth/verify-email", {"token": out_pending[0]}))
        out_session = self.data(self.request("POST", "/api/v1/auth/login", {"email": "pickup-out@example.test", "password": "member-password-123"}))
        self.data(self.authed("POST", f"/api/v1/communities/{community['id']}/members", {"email": "pickup-out@example.test"}))
        self.data(self.request("POST", f"/api/v1/polls/{poll['id']}/vote", {"option_id": poll["options"][1]["id"]}, token=out_session["token"]))
        self.error(self.request("POST", f"/api/v1/polls/{poll['id']}/vote", {"option_id": poll["options"][0]["id"], "player_id": players[0]["id"]}, token=out_session["token"]), 403, "player_not_self")
        with db.connect() as connection:
            connection.execute("UPDATE polls SET closes_at=?,feedback_due_at=? WHERE id=?", (iso(now - timedelta(seconds=1)), iso(now - timedelta(seconds=1)), poll["id"]))
            with patch("backend.service.send_email") as send:
                service.process_due_polls(connection, now=now)
            closed = self.data(self.authed("GET", "/api/v1/polls"))
            saved = next(item for item in closed if item["id"] == poll["id"])
            result = saved["autoTeams"]
            self.assertEqual(result["poolSize"], 7)
            self.assertEqual(len(result["teamA"]) + len(result["teamB"]) + (1 if result["floater"] else 0), 7)
            self.assertEqual(len(result["teamA"]), len(result["teamB"]))
            self.assertIsNotNone(result["floater"])
            self.assertIn(result["floater"], {player["id"] for player in saved["yesPlayers"]})
            self.assertIn(saved["autoTeams"]["teamNames"]["teamA"], {"Yolo Blue", "Yolo Red", "Yolo Green", "Yolo Yellow"})
            self.assertIn(saved["autoTeams"]["teamNames"]["teamB"], {"Yolo Blue", "Yolo Red", "Yolo Green", "Yolo Yellow"})
            self.assertNotEqual(saved["autoTeams"]["teamNames"]["teamA"], saved["autoTeams"]["teamNames"]["teamB"])
            self.assertEqual(send.call_count, 5)
            self.assertEqual({call.args[0] for call in send.call_args_list}, {f"pickup-in-{i}@example.test" for i in range(1, 6)})
            self.assertIn(f"feedbackPoll={poll['id']}", send.call_args.args[2])
            self.assertEqual(saved["noCount"], 1)
            self.assertEqual(saved["guestCount"], 2)
            self.assertEqual(len(saved["yesPlayers"]), 7)
            self.assertEqual(sum(1 for player in saved["yesPlayers"] if player["guest"]), 2)
        all_attendees = result["teamA"] + result["teamB"] + ([result["floater"]] if result["floater"] else [])
        rearranged = self.data(self.authed("POST", f"/api/v1/polls/{poll['id']}/teams", {
            "team_a": all_attendees[:3],
            "team_b": all_attendees[3:6],
            "floater": all_attendees[6],
        }))
        self.assertTrue(rearranged["autoTeams"]["manual"])
        no_floater = self.data(self.authed("POST", f"/api/v1/polls/{poll['id']}/teams", {
            "team_a": all_attendees[:4],
            "team_b": all_attendees[4:],
            "floater": None,
        }))
        self.assertIsNone(no_floater["autoTeams"]["floater"])
        self.assertEqual(len(no_floater["autoTeams"]["teamA"]), 4)
        self.assertEqual(len(no_floater["autoTeams"]["teamB"]), 3)
        late_pending = self.create_pending_user("late-arrival@example.test", name="Late Arrival")
        self.data(self.request("POST", "/api/v1/auth/verify-email", {"token": late_pending[0]}))
        late_player = self.data(self.authed("POST", "/api/v1/players", {
            "team_id": team["id"], "name": "Late Arrival", "email": "late-arrival@example.test", "number": 19, "pos": "CM",
        }))
        expanded_split = self.data(self.authed("POST", f"/api/v1/polls/{poll['id']}/teams", {
            "team_a": no_floater["autoTeams"]["teamA"],
            "team_b": no_floater["autoTeams"]["teamB"] + [late_player["id"]],
            "floater": None,
        }))
        self.assertEqual(len(expanded_split["autoTeams"]["teamA"]), 4)
        self.assertEqual(len(expanded_split["autoTeams"]["teamB"]), 4)
        self.assertNotIn(late_player["id"], {player["id"] for player in expanded_split["yesPlayers"]})
        outsider = self.create_pending_user("poll-outsider@example.test")
        self.data(self.request("POST", "/api/v1/auth/verify-email", {"token": outsider[0]}))
        outsider_session = self.data(self.request("POST", "/api/v1/auth/login", {"email": "poll-outsider@example.test", "password": "member-password-123"}))
        self.error(self.request("POST", f"/api/v1/polls/{poll['id']}/teams", {"team_a": [], "team_b": [], "floater": None}, token=outsider_session["token"]), 403, "forbidden")
        self.error(self.request("GET", f"/api/v1/polls/{poll['id']}/feedback", token=out_session["token"]), 403, "pickup_attendance_required")
        review = self.data(self.request("GET", f"/api/v1/polls/{poll['id']}/feedback", token=in_sessions[0]["token"]))
        self.assertEqual({player["id"] for player in review["players"]}, {player["id"] for player in players})
        submitted = self.data(self.request("POST", f"/api/v1/polls/{poll['id']}/feedback", {
            "ratings": [{"player_id": player["id"], "value": 8, "feedback": "Good game"} for player in players],
        }, token=in_sessions[0]["token"]))
        self.assertEqual(submitted["playerCount"], 5)

    def test_registration_requires_email_verification_before_login(self):
        token_text, message, data = self.create_pending_user()
        self.assertTrue(data["verificationRequired"])
        self.assertNotIn("token", data)
        self.assertIn(token_text, message)
        self.error(self.request("POST", "/api/v1/auth/login", {
            "email": "new@example.test", "password": "member-password-123",
        }), 403, "email_not_verified")
        verified = self.data(self.request("POST", "/api/v1/auth/verify-email", {"token": token_text}))
        self.assertTrue(verified["verified"])
        session = self.data(self.request("POST", "/api/v1/auth/login", {
            "email": "new@example.test", "password": "member-password-123",
        }))
        self.assertTrue(session["token"])

    def test_registration_reports_provider_failure_without_creating_an_account(self):
        with patch("backend.service.send_email", side_effect=MailDeliveryError("delivery_failed")):
            response = self.request("POST", "/api/v1/auth/register", {
                "name": "Mail Failure", "email": "mail-failure@example.test", "password": "member-password-123",
            })
        self.error(response, 503, "email_unavailable")
        self.assertIn("provider", response["json"]["error"]["message"])
        with db.connect() as connection:
            self.assertIsNone(connection.execute("SELECT 1 FROM users WHERE email='mail-failure@example.test'").fetchone())

    def test_verification_token_is_single_use_and_expiring(self):
        token_text, _message, _data = self.create_pending_user("once@example.test")
        with db.connect() as connection:
            connection.execute("UPDATE auth_tokens SET expires_at='2000-01-01T00:00:00Z' WHERE token_hash=?", (service.hash_token(token_text),))
        self.error(self.request("POST", "/api/v1/auth/verify-email", {"token": token_text}), 400, "invalid_token")
        token_text, _message, _data = self.create_pending_user("single-use@example.test")
        self.data(self.request("POST", "/api/v1/auth/verify-email", {"token": token_text}))
        self.error(self.request("POST", "/api/v1/auth/verify-email", {"token": token_text}), 400, "invalid_token")

    def test_forgot_password_is_generic_and_reset_revokes_sessions(self):
        token_text, _message, _data = self.create_pending_user("reset@example.test")
        self.data(self.request("POST", "/api/v1/auth/verify-email", {"token": token_text}))
        logged_in = self.data(self.request("POST", "/api/v1/auth/login", {
            "email": "reset@example.test", "password": "member-password-123",
        }))
        with patch("backend.service.send_email", create=True) as send:
            response = self.data(self.request("POST", "/api/v1/auth/password/forgot", {"email": "reset@example.test"}))
        with patch("backend.service.send_email", create=True) as absent:
            generic = self.data(self.request("POST", "/api/v1/auth/password/forgot", {"email": "missing@example.test"}))
        self.assertEqual(response, generic)
        reset_token = re.search(r"[?&]reset_token=([A-Za-z0-9_-]+)", send.call_args.args[2]).group(1)
        self.data(self.request("POST", "/api/v1/auth/password/reset", {
            "token": reset_token, "password": "updated-password-456",
        }))
        self.error(self.request("GET", "/api/v1/me", token=logged_in["token"]), 401, "unauthorized")
        self.assertTrue(self.data(self.request("POST", "/api/v1/auth/login", {
            "email": "reset@example.test", "password": "updated-password-456",
        }))["token"])

    def test_authenticated_password_change_requires_current_password_and_revokes_other_sessions(self):
        other_session = self.data(self.request("POST", "/api/v1/auth/admin", {
            "email": config.ADMIN_EMAIL, "password": config.ADMIN_PASSWORD,
        }))
        self.error(self.authed("POST", "/api/v1/auth/password/change", {
            "current_password": "wrong-password", "new_password": "updated-password-456",
        }), 401, "invalid_credentials")
        self.data(self.authed("POST", "/api/v1/auth/password/change", {
            "current_password": config.ADMIN_PASSWORD, "new_password": "updated-password-456",
        }))
        self.error(self.request("GET", "/api/v1/me", token=other_session["token"]), 401, "unauthorized")
        self.assertTrue(self.data(self.request("POST", "/api/v1/auth/admin", {
            "email": config.ADMIN_EMAIL, "password": "updated-password-456",
        }))["token"])

    def test_logout_revokes_session(self):
        self.data(self.authed("POST", "/api/v1/auth/logout"))
        self.error(self.request("GET", "/api/v1/me", token=self.token), 401, "unauthorized")

    def test_two_factor_setup_enrollment_login_challenge_and_replay_protection(self):
        setup = self.data(self.authed("POST", "/api/v1/auth/2fa/setup", {}))
        self.assertTrue(setup["secret"])
        self.assertIn("otpauth://totp/", setup["otpauthUri"])
        code = service.totp_code(setup["secret"], utc_now())
        enabled = self.data(self.authed("POST", "/api/v1/auth/2fa/enable", {"code": code}))
        self.assertTrue(enabled["enabled"])
        self.assertTrue(enabled["recoveryCodes"])
        challenge = self.data(self.request("POST", "/api/v1/auth/admin", {
            "email": config.ADMIN_EMAIL, "password": config.ADMIN_PASSWORD,
        }))
        self.assertTrue(challenge["twoFactorRequired"])
        self.assertNotIn("token", challenge)
        complete = self.data(self.request("POST", "/api/v1/auth/2fa/login", {
            "challengeToken": challenge["challengeToken"],
            "code": service.totp_code(setup["secret"], utc_now() + timedelta(seconds=30)),
        }))
        self.assertTrue(complete["token"])
        self.error(self.request("POST", "/api/v1/auth/2fa/login", {
            "challengeToken": challenge["challengeToken"],
            "code": service.totp_code(setup["secret"], utc_now()),
        }), 400, "invalid_challenge")

    def test_two_factor_recovery_code_is_one_time(self):
        setup = self.data(self.authed("POST", "/api/v1/auth/2fa/setup", {}))
        enabled = self.data(self.authed("POST", "/api/v1/auth/2fa/enable", {
            "code": service.totp_code(setup["secret"], utc_now()),
        }))
        code = enabled["recoveryCodes"][0]
        challenge = self.data(self.request("POST", "/api/v1/auth/login", {
            "email": config.ADMIN_EMAIL, "password": config.ADMIN_PASSWORD,
        }))
        self.data(self.request("POST", "/api/v1/auth/2fa/login", {
            "challengeToken": challenge["challengeToken"], "code": code,
        }))
        another = self.data(self.request("POST", "/api/v1/auth/login", {
            "email": config.ADMIN_EMAIL, "password": config.ADMIN_PASSWORD,
        }))
        self.error(self.request("POST", "/api/v1/auth/2fa/login", {
            "challengeToken": another["challengeToken"], "code": code,
        }), 401, "invalid_two_factor_code")

    def test_community_chat_requires_membership_and_escapes_through_api_shape(self):
        community = self.data(self.authed("POST", "/api/v1/communities", {
            "name": "Member Chat", "sport": "Soccer", "kind": "Club",
            "description": "Private chat testing", "privacy": "Private",
        }))
        member_data = self.create_pending_user("chat-member@example.test")
        self.data(self.request("POST", "/api/v1/auth/verify-email", {"token": member_data[0]}))
        member = self.data(self.request("POST", "/api/v1/auth/login", {
            "email": "chat-member@example.test", "password": "member-password-123",
        }))
        self.error(self.request("GET", f"/api/v1/communities/{community['id']}/messages", token=member["token"]), 403, "forbidden")
        self.data(self.authed("POST", f"/api/v1/communities/{community['id']}/members", {"email": "chat-member@example.test"}))
        message = self.data(self.request("POST", f"/api/v1/communities/{community['id']}/messages", {"text": "Hello club"}, token=member["token"]))
        self.assertEqual(message["text"], "Hello club")
        listing = self.data(self.request("GET", f"/api/v1/communities/{community['id']}/messages", token=member["token"]))
        self.assertEqual(listing[0]["id"], message["id"])
        self.error(self.authed("POST", f"/api/v1/communities/{community['id']}/messages", {"text": "x" * 1500}), 400, "invalid_field")

    def test_community_chat_has_a_per_member_send_limit(self):
        community = self.data(self.authed("POST", "/api/v1/communities", {
            "name": "Rate Limited Chat", "sport": "Soccer", "kind": "Club",
            "description": "Message rate limit testing", "privacy": "Public",
        }))
        for index in range(30):
            self.data(self.authed("POST", f"/api/v1/communities/{community['id']}/messages", {"text": f"Message {index}"}))
        self.error(self.authed("POST", f"/api/v1/communities/{community['id']}/messages", {"text": "Too many"}), 429, "rate_limited")

    def test_matchday_review_emails_members_and_accepts_fixture_specific_player_ratings(self):
        from backend.security import iso
        png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l7sAAAAASUVORK5CYII="
        community = self.data(self.authed("POST", "/api/v1/communities", {
            "name": "Review Club", "sport": "Soccer", "kind": "Club",
            "description": "Post match ratings", "privacy": "Public", "logo_data": png, "banner_data": png,
        }))
        self.assertEqual(community["logoData"], png)
        self.assertEqual(community["bannerData"], png)
        updated_community = self.data(self.authed("PATCH", f"/api/v1/communities/{community['id']}", {"logo_data": None}))
        self.assertIsNone(updated_community["logoData"])
        self.error(self.authed("PATCH", f"/api/v1/communities/{community['id']}", {"banner_data": "data:image/svg+xml,<svg/>"}), 400, "invalid_image")
        team = self.data(self.authed("POST", "/api/v1/teams", {
            "community_id": community["id"], "name": "Review XI", "age_group": "Adult",
            "league": "Sunday", "coach": "Owner", "formation": "4-3-3",
        }))
        player = self.data(self.authed("POST", "/api/v1/players", {
            "team_id": team["id"], "email": self.unique_player_email(), "name": "Match Player", "number": 9, "pos": "ST", "image_data": png,
        }))
        self.assertEqual(player["imageData"], png)
        pending = self.create_pending_user("ratings-member@example.test")
        self.data(self.request("POST", "/api/v1/auth/verify-email", {"token": pending[0]}))
        member = self.data(self.request("POST", "/api/v1/auth/login", {
            "email": "ratings-member@example.test", "password": "member-password-123",
        }))
        self.data(self.authed("POST", f"/api/v1/communities/{community['id']}/members", {"email": "ratings-member@example.test"}))
        fixture_id = "review-fixture"
        with db.connect() as connection:
            connection.execute("""INSERT INTO fixtures(id,community_id,opponent,opponent_mark,home_away,date,venue,competition,sort_order)
                VALUES(?,?,?,?,?,?,?,?,?)""", (fixture_id, community["id"], "Test FC", "TF", "Home", iso(utc_now() - timedelta(days=1)), "Ground", "Cup", 0))
        with patch("backend.service.send_email") as send:
            requested = self.data(self.authed("POST", f"/api/v1/communities/{community['id']}/fixtures/{fixture_id}/ratings/request", {}))
        self.assertGreaterEqual(requested["sentTo"], 2)
        self.assertIn(f"rateFixture={fixture_id}", send.call_args.args[2])
        review = self.data(self.request("GET", f"/api/v1/communities/{community['id']}/fixtures/{fixture_id}/ratings", token=member["token"]))
        self.assertEqual(review["players"][0]["id"], player["id"])
        self.assertNotIn("results", review)
        self.error(self.request("POST", f"/api/v1/communities/{community['id']}/fixtures/{fixture_id}/ratings", {"ratings": []}, token=member["token"]), 400, "invalid_ratings")
        submitted = self.data(self.request("POST", f"/api/v1/communities/{community['id']}/fixtures/{fixture_id}/ratings", {
            "ratings": [{"player_id": player["id"], "value": 8, "feedback": "Great movement"}],
        }, token=member["token"]))
        self.assertTrue(submitted["submitted"])
        saved = self.data(self.authed("GET", f"/api/v1/communities/{community['id']}/fixtures/{fixture_id}/ratings"))
        self.assertEqual(saved["results"][0]["rating"], 8)
        self.assertEqual(saved["results"][0]["feedback"], "Great movement")
        self.assertEqual(saved["results"][0]["member"], "New Member")

    def test_chat_mentions_notify_only_valid_community_members(self):
        community = self.data(self.authed("POST", "/api/v1/communities", {
            "name": "Mention Club", "sport": "Soccer", "kind": "Club",
            "description": "Testing member mentions", "privacy": "Public",
        }))
        pending = self.create_pending_user("mention-member@example.test")
        self.data(self.request("POST", "/api/v1/auth/verify-email", {"token": pending[0]}))
        member = self.data(self.request("POST", "/api/v1/auth/login", {
            "email": "mention-member@example.test", "password": "member-password-123",
        }))
        self.data(self.authed("POST", f"/api/v1/communities/{community['id']}/members", {"email": "mention-member@example.test"}))
        sent = self.data(self.authed("POST", f"/api/v1/communities/{community['id']}/messages", {
            "text": "Game at six, @New Member", "mentions": [{"id": member["user"]["id"], "name": "New Member"}],
        }))
        self.assertEqual(sent["text"], "Game at six, @New Member")
        notifications = self.data(self.request("GET", "/api/v1/notifications", token=member["token"]))
        self.assertTrue(any(note["title"] == "You were mentioned" and note["unread"] for note in notifications))
        self.error(self.authed("POST", f"/api/v1/communities/{community['id']}/messages", {
            "text": "Invalid tag", "mentions": ["not-a-member"],
        }), 400, "invalid_field")
        self.error(self.authed("POST", f"/api/v1/communities/{community['id']}/messages", {
            "text": "Plain message", "mentions": [{"id": member["user"]["id"], "name": "New Member"}],
        }), 400, "invalid_field")

    def test_chat_message_owner_can_edit_and_delete_but_other_members_cannot(self):
        community = self.data(self.authed("POST", "/api/v1/communities", {
            "name": "Message Controls", "sport": "Soccer", "kind": "Club",
            "description": "Testing edit and delete permissions", "privacy": "Public",
        }))
        pending = self.create_pending_user("message-owner@example.test")
        self.data(self.request("POST", "/api/v1/auth/verify-email", {"token": pending[0]}))
        member = self.data(self.request("POST", "/api/v1/auth/login", {
            "email": "message-owner@example.test", "password": "member-password-123",
        }))
        self.data(self.authed("POST", f"/api/v1/communities/{community['id']}/members", {"email": "message-owner@example.test"}))
        message = self.data(self.request("POST", f"/api/v1/communities/{community['id']}/messages", {"text": "Original message"}, token=member["token"]))
        path = f"/api/v1/communities/{community['id']}/messages/{message['id']}"
        self.error(self.authed("PATCH", path, {"text": "Changed by another member"}), 403, "forbidden")
        self.error(self.authed("DELETE", path), 403, "forbidden")
        edited = self.data(self.request("PATCH", path, {"text": "Edited message"}, token=member["token"]))
        self.assertEqual(edited["text"], "Edited message")
        self.assertTrue(edited["editedAt"])
        deleted = self.data(self.request("DELETE", path, token=member["token"]))
        self.assertTrue(deleted["deleted"])
        self.assertEqual(self.data(self.request("GET", f"/api/v1/communities/{community['id']}/messages", token=member["token"])), [])

    def test_community_unread_count_excludes_own_messages_and_clears_when_chat_is_read(self):
        community = self.data(self.authed("POST", "/api/v1/communities", {
            "name": "Unread Count Club", "sport": "Soccer", "kind": "Club",
            "description": "Unread message counter testing", "privacy": "Public",
        }))
        pending = self.create_pending_user("unread-member@example.test")
        self.data(self.request("POST", "/api/v1/auth/verify-email", {"token": pending[0]}))
        member = self.data(self.request("POST", "/api/v1/auth/login", {
            "email": "unread-member@example.test", "password": "member-password-123",
        }))
        self.data(self.authed("POST", f"/api/v1/communities/{community['id']}/members", {"email": "unread-member@example.test"}))
        self.data(self.authed("POST", f"/api/v1/communities/{community['id']}/messages", {"text": "Read this message"}))
        bootstrap = self.data(self.request("GET", "/api/v1/bootstrap", token=member["token"]))
        unread = next(item["unreadCount"] for item in bootstrap["communities"] if item["id"] == community["id"])
        self.assertEqual(unread, 1)
        self.data(self.request("GET", f"/api/v1/communities/{community['id']}/messages", token=member["token"]))
        bootstrap = self.data(self.request("GET", "/api/v1/bootstrap", token=member["token"]))
        unread = next(item["unreadCount"] for item in bootstrap["communities"] if item["id"] == community["id"])
        self.assertEqual(unread, 0)
        self.data(self.request("POST", f"/api/v1/communities/{community['id']}/messages", {"text": "My own message"}, token=member["token"]))
        bootstrap = self.data(self.request("GET", "/api/v1/bootstrap", token=member["token"]))
        unread = next(item["unreadCount"] for item in bootstrap["communities"] if item["id"] == community["id"])
        self.assertEqual(unread, 0)
