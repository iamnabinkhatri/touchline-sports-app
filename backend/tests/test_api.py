import json
import sqlite3
from datetime import timedelta

from backend import db
from backend.security import hash_token, iso, utc_now
from backend.tests.base import ApiTestCase


class AuthApiTests(ApiTestCase):
    def test_health_is_public_and_openapi_requires_authentication(self):
        health = self.request("GET", "/api/v1/health")
        data = self.data(health)
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["schemaVersion"], "9")

        self.error(self.request("GET", "/api/v1/openapi.json"), 401, "unauthorized")
        spec = self.data(self.request("GET", "/api/v1/openapi.json", token=self.token))
        self.assertEqual(spec["openapi"], "3.0.3")
        self.assertIn("/api/v1/bootstrap", spec["paths"])
        self.assertIn("BearerAuth", spec["components"]["securitySchemes"])
        self.assertIn("ApiKeyAuth", spec["components"]["securitySchemes"])
        self.assertIn("/api/v1/communities/{community_id}/fixtures/{fixture_id}/ratings", spec["paths"])

    def test_demo_login_and_me(self):
        me = self.data(self.authed("GET", "/api/v1/me"))
        self.assertEqual(me["name"], "Alex Kim")
        self.assertEqual(me["role"], "Club admin")
        self.assertEqual(me["email"], "alex@brooklynrangers.club")

    def test_invalid_token_is_rejected(self):
        response = self.request("GET", "/api/v1/bootstrap", token="not-a-real-token")
        self.error(response, 401, "unauthorized")
        self.assertIn("bearer", response["headers"].get("www-authenticate", "").lower())

    def test_logout_revokes_session(self):
        self.data(self.authed("POST", "/api/v1/auth/logout"))
        self.error(self.authed("GET", "/api/v1/me"), 401, "unauthorized")

    def test_register_login_duplicate_and_password_storage(self):
        payload = {"name": "Mobile User", "email": "mobile@example.com", "password": "correct-horse-1"}
        registration = self.request("POST", "/api/v1/auth/register", payload)
        session = self.data(registration)
        self.assertEqual(session["user"]["name"], "Mobile User")

        with db.connect() as connection:
            row = connection.execute(
                "SELECT password_hash FROM users WHERE email = ?", ("mobile@example.com",)
            ).fetchone()
        self.assertNotEqual(row["password_hash"], payload["password"])
        self.assertTrue(row["password_hash"].startswith("pbkdf2_sha256$"))

        login = self.data(self.request("POST", "/api/v1/auth/login", {
            "email": "mobile@example.com", "password": "correct-horse-1"
        }))
        self.assertTrue(login["token"])
        self.assertEqual(login["user"]["email"], "mobile@example.com")

        duplicate = self.request("POST", "/api/v1/auth/register", payload)
        self.error(duplicate, 409, "email_exists")

    def test_invalid_login_and_weak_password(self):
        self.error(self.request("POST", "/api/v1/auth/login", {
            "email": "alex@brooklynrangers.club", "password": "wrong"
        }), 401, "invalid_credentials")
        self.error(self.request("POST", "/api/v1/auth/register", {
            "name": "Weak", "email": "weak@example.com", "password": "short"
        }), 400, "invalid_field")

    def test_token_is_stored_hashed(self):
        with db.connect() as connection:
            rows = connection.execute("SELECT token_hash FROM sessions").fetchall()
        self.assertTrue(rows)
        self.assertNotIn(self.token, [row["token_hash"] for row in rows])
        self.assertIn(hash_token(self.token), [row["token_hash"] for row in rows])

    def test_cors_preflight(self):
        allowed = self.request(
            "OPTIONS",
            "/api/v1/bootstrap",
            origin="http://127.0.0.1:4173",
        )
        self.assertEqual(allowed["status"], 204)
        self.assertEqual(allowed["headers"].get("access-control-allow-origin"), "http://127.0.0.1:4173")
        self.assertIn("authorization", allowed["headers"].get("access-control-allow-headers", "").lower())

        rejected = self.request(
            "OPTIONS",
            "/api/v1/bootstrap",
            origin="https://evil.example",
        )
        self.assertEqual(rejected["status"], 403)


class ContentApiTests(ApiTestCase):
    def test_bootstrap_shape(self):
        state = self.data(self.authed("GET", "/api/v1/bootstrap"))
        self.assertEqual(state["version"], 2)
        self.assertEqual(state["user"]["name"], "Alex Kim")
        self.assertEqual(len(state["teams"][0]["players"]), 18)
        self.assertEqual(len(state["communities"]), 8)
        self.assertEqual(len(state["polls"]), 4)
        self.assertEqual(len(state["plans"]), 3)
        self.assertTrue(state["nextFixtures"])
        self.assertTrue(state["leaders"])
        self.assertIsInstance(state["serverTime"], str)

    def test_post_like_and_comment_flow(self):
        state = self.data(self.authed("GET", "/api/v1/bootstrap"))
        post = self.data(self.authed("POST", "/api/v1/posts", {
            "community_id": "brooklyn",
            "text": "A new API post",
            "tag": "club",
        }))
        self.assertEqual(post["text"], "A new API post")
        self.assertFalse(post["liked"])

        liked = self.data(self.authed("POST", f"/api/v1/posts/{post['id']}/like"))
        self.assertTrue(liked["liked"])
        unliked = self.data(self.authed("POST", f"/api/v1/posts/{post['id']}/like"))
        self.assertFalse(unliked["liked"])

        commented = self.data(self.authed("POST", f"/api/v1/posts/{post['id']}/comments", {
            "text": "A server-side comment"
        }))
        self.assertEqual(commented["comments"][-1]["text"], "A server-side comment")
        later = self.data(self.authed("GET", "/api/v1/bootstrap"))
        self.assertTrue(any(item["text"] == "A new API post" for item in later["posts"]))
        self.assertGreaterEqual(len(later["posts"]), len(state["posts"]) + 1)

    def test_post_requires_membership_and_auth(self):
        self.error(self.request("POST", "/api/v1/posts", {
            "community_id": "brooklyn", "text": "Nope"
        }), 401, "unauthorized")

        session = self.data(self.request("POST", "/api/v1/auth/register", {
            "name": "Outsider", "email": "outsider@example.com", "password": "password-123"
        }))
        outsider = session["token"]
        # Registration joins the first community automatically; another community
        # is still closed to this member.
        self.error(self.request("POST", "/api/v1/posts", {
            "community_id": "hardwood", "text": "Not a member"
        }, token=outsider), 403, "forbidden")

    def test_poll_create_vote_and_change(self):
        poll = self.data(self.authed("POST", "/api/v1/polls", {
            "question": "API poll?",
            "category": "Club",
            "duration_hours": 24,
            "options": ["Yes", "No"],
        }))
        self.assertEqual(len(poll["options"]), 2)
        option_one, option_two = poll["options"][0]["id"], poll["options"][1]["id"]
        voted = self.data(self.authed("POST", f"/api/v1/polls/{poll['id']}/vote", {
            "option_id": option_one
        }))
        self.assertEqual(voted["userVote"], option_one)
        changed = self.data(self.authed("POST", f"/api/v1/polls/{poll['id']}/vote", {
            "option_id": option_two
        }))
        self.assertEqual(changed["userVote"], option_two)

    def test_closed_poll_rejects_votes(self):
        poll = self.data(self.authed("POST", "/api/v1/polls", {
            "question": "Closed poll?", "category": "Club", "options": ["A", "B"]
        }))
        with db.connect() as connection:
            connection.execute(
                "UPDATE polls SET closes_at = ? WHERE id = ?",
                (iso(utc_now() - timedelta(hours=1)), poll["id"]),
            )
        self.error(self.authed("POST", f"/api/v1/polls/{poll['id']}/vote", {
            "option_id": poll["options"][0]["id"]
        }), 409, "poll_closed")

    def test_community_create_join_and_starter_poll(self):
        before = self.data(self.authed("GET", "/api/v1/polls"))
        community = self.data(self.authed("POST", "/api/v1/communities", {
            "name": "API Community",
            "sport": "Soccer",
            "description": "A server-created community",
            "privacy": "Public",
            "create_poll": True,
        }))
        self.assertTrue(community["joined"])
        self.assertEqual(community["memberCount"], 1)
        after = self.data(self.authed("GET", "/api/v1/polls"))
        self.assertEqual(len(after), len(before) + 1)

        hardwood = next(
            item for item in self.data(self.authed("GET", "/api/v1/communities"))
            if item["id"] == "hardwood"
        )
        count = hardwood["memberCount"]
        joined = self.data(self.authed("POST", "/api/v1/communities/hardwood/join"))
        self.assertTrue(joined["joined"])
        self.assertEqual(joined["memberCount"], count + 1)
        again = self.data(self.authed("POST", "/api/v1/communities/hardwood/join"))
        self.assertEqual(again["memberCount"], count + 1)

    def test_player_add_update_and_rate(self):
        team = self.data(self.authed("GET", "/api/v1/team"))
        original = team["players"][0]
        created = self.data(self.authed("POST", "/api/v1/players", {
            "email": self.unique_player_email(), "name": "API Player", "number": 42, "pos": "ST", "foot": "Left", "status": "available",
            "image_data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l7sAAAAASUVORK5CYII=",
        }))
        self.assertEqual(created["name"], "API Player")
        self.assertTrue(created["imageData"].startswith("data:image/png;base64,"))
        self.assertEqual(created["ratingCount"], 0)
        self.error(self.authed("POST", "/api/v1/players", {
            "email": self.unique_player_email(), "name": "Duplicate", "number": 42, "pos": "CM"
        }), 409, "number_taken")

        updated = self.data(self.authed("PATCH", f"/api/v1/players/{created['id']}", {
            "status": "doubtful", "pos": "LW"
        }))
        self.assertEqual(updated["status"], "doubtful")
        self.assertEqual(updated["pos"], "LW")
        self.assertEqual(updated["group"], "FWD")

        rated = self.data(self.authed("POST", f"/api/v1/players/{original['id']}/ratings", {
            "value": 10
        }))
        self.assertEqual(rated["userRating"], 10)
        self.assertGreaterEqual(rated["ratingCount"], original["ratingCount"] + 1)
        self.assertGreater(rated["rating"], original["rating"])
        updated_rating = self.data(self.authed("POST", f"/api/v1/players/{original['id']}/ratings", {
            "value": 1
        }))
        self.assertEqual(updated_rating["ratingCount"], rated["ratingCount"])
        self.assertEqual(updated_rating["userRating"], 1)

    def test_member_cannot_manage_team(self):
        session = self.data(self.request("POST", "/api/v1/auth/register", {
            "name": "Member", "email": "member@example.com", "password": "password-123"
        }))
        token = session["token"]
        self.error(self.request("POST", "/api/v1/players", {
            "name": "Nope", "number": 77, "pos": "ST"
        }, token=token), 403, "forbidden")
        self.error(self.request("PATCH", "/api/v1/teams/brooklyn-u16", {
            "formation": "4-3-3"
        }, token=token), 403, "forbidden")

    def test_lineup_update(self):
        team = self.data(self.authed("GET", "/api/v1/team"))
        lineup = team["startingXI"]
        updated = self.data(self.authed("PATCH", f"/api/v1/teams/{team['id']}", {
            "formation": "4-2-3-1",
            "starting_xi": lineup,
            "publish": True,
        }))
        self.assertEqual(updated["formation"], "4-2-3-1")
        self.assertIsNotNone(updated["lineupSavedAt"])
        self.error(self.authed("PATCH", f"/api/v1/teams/{team['id']}", {
            "starting_xi": ["ava"]
        }), 400, "invalid_lineup")

    def test_game_plan_create_and_checklist(self):
        plan = self.data(self.authed("POST", "/api/v1/plans", {
            "title": "API Plan",
            "opponent": "Test United",
            "date": "2026-12-01T14:30:00Z",
            "venue": "Test Park",
            "formation": "4-3-3",
            "objective": "Test the plan API end to end.",
        }))
        self.assertEqual(plan["status"], "Draft")
        self.assertTrue(plan["checklist"])
        item = plan["checklist"][0]
        toggled = self.data(self.authed(
            "PATCH", f"/api/v1/plans/{plan['id']}/checklist/{item['id']}", {"done": True}
        ))
        self.assertTrue(toggled["checklist"][0]["done"])
        self.error(self.authed("POST", "/api/v1/plans", {
            "title": "Bad date", "opponent": "X", "date": "not-a-date", "venue": "Y", "objective": "Z"
        }), 400, "invalid_field")

    def test_notifications_mark_all_read(self):
        before = self.data(self.authed("GET", "/api/v1/notifications"))
        self.assertTrue(any(item["unread"] for item in before))
        after = self.data(self.authed("POST", "/api/v1/notifications/read", {"all": True}))
        self.assertFalse(any(item["unread"] for item in after))

    def test_pickup_teams(self):
        result = self.data(self.authed(
            "GET", "/api/v1/pickup/teams?include_doubtful=false&position_aware=true&seed=1"
        ))
        self.assertEqual(result["poolSize"], 14)
        self.assertEqual(len(result["teamA"]["players"]), 7)
        self.assertEqual(len(result["teamB"]["players"]), 7)
        self.assertLessEqual(result["gap"], 0.5)
        self.assertEqual(result["teamA"]["counts"]["GK"], 1)
        self.assertEqual(result["teamB"]["counts"]["GK"], 1)
        bigger = self.data(self.authed(
            "GET", "/api/v1/pickup/teams?include_doubtful=true&position_aware=true&seed=1"
        ))
        self.assertEqual(bigger["poolSize"], 16)
        self.assertEqual(len(bigger["teamA"]["players"]), 8)

    def test_schedule_endpoint(self):
        payload = self.data(self.authed("GET", "/api/v1/schedule"))
        self.assertEqual(len(payload["nextFixtures"]), 2)
        self.assertEqual(len(payload["schedule"]), 3)

    def test_demo_reset(self):
        old_token = self.token
        reset = self.data(self.authed("POST", "/api/v1/demo/reset"))
        self.assertTrue(reset["token"])
        self.assertNotEqual(reset["token"], old_token)
        self.error(self.request("GET", "/api/v1/me", token=old_token), 401, "unauthorized")
        state = self.data(self.request("GET", "/api/v1/bootstrap", token=reset["token"]))
        self.assertEqual(len(state["posts"]), 4)

    def test_sql_injection_payloads_are_inert_and_data_survives(self):
        payload = "' OR 1=1; DROP TABLE posts; --"
        post = self.data(self.authed("POST", "/api/v1/posts", {
            "community_id": "brooklyn", "text": payload, "tag": "club"
        }))
        self.assertEqual(post["text"], payload)
        community = self.data(self.authed("POST", "/api/v1/communities", {
            "name": payload,
            "sport": "Soccer",
            "description": payload,
            "create_poll": False,
        }))
        player = self.data(self.authed("POST", "/api/v1/players", {
            "email": self.unique_player_email(), "name": payload, "number": 91, "pos": "ST"
        }))
        plan = self.data(self.authed("POST", "/api/v1/plans", {
            "title": payload,
            "opponent": payload,
            "date": "2026-12-10T14:30:00Z",
            "venue": payload,
            "objective": payload,
        }))
        self.assertEqual(community["name"], payload)
        self.assertEqual(player["name"], payload)
        self.assertEqual(plan["title"], payload)
        state = self.data(self.authed("GET", "/api/v1/bootstrap"))
        self.assertTrue(any(item["text"] == payload for item in state["posts"]))
        self.assertTrue(any(item["name"] == payload for item in state["communities"]))
        self.assertTrue(any(item["name"] == payload for item in state["teams"][0]["players"]))
        self.assertTrue(any(item["title"] == payload for item in state["plans"]))
        # Filter parameters remain parameterized, and the tables still accept writes.
        filtered = self.data(self.authed("GET", "/api/v1/posts?tag=%27%20OR%201%3D1%20--"))
        self.assertIsInstance(filtered, list)
        self.data(self.authed("POST", "/api/v1/posts", {
            "community_id": "brooklyn", "text": "after injection", "tag": "club"
        }))

    def test_validation_and_content_type_errors(self):
        wrong_type = self.request(
            "POST", "/api/v1/posts",
            headers={"Content-Type": "text/plain"},
            body="not json",
        )
        self.assertEqual(wrong_type["status"], 415)
        malformed = self.authed(
            "POST", "/api/v1/posts",
            body={"text": "x"},
        )
        self.error(malformed, 400)
        invalid_rating = self.authed("POST", "/api/v1/players/ava/ratings", {"value": 11})
        self.error(invalid_rating, 400, "invalid_field")


class StaticAndMethodTests(ApiTestCase):
    def test_static_app_and_security_headers(self):
        response = self.request("GET", "/")
        self.assertEqual(response["status"], 200)
        self.assertIn("text/html", response["content_type"])
        self.assertIn("script-src 'self'", response["headers"]["content-security-policy"])
        self.assertEqual(response["headers"]["x-frame-options"], "DENY")
        self.assertEqual(response["headers"]["x-content-type-options"], "nosniff")

    def test_static_methods_and_traversal(self):
        self.assertEqual(self.request("POST", "/")["status"], 405)
        self.assertEqual(self.request("GET", "/%2e%2e/%2e%2e/etc/passwd")["status"], 403)
        self.assertEqual(self.request("GET", "/backend/server.py")["status"], 404)
        self.assertEqual(self.request("GET", "/package.json")["status"], 404)
        self.assertEqual(self.request("GET", "/.git/config")["status"], 404)

    def test_api_404_and_405(self):
        self.error(self.authed("GET", "/api/v1/nope"), 404, "not_found")
        response = self.authed("DELETE", "/api/v1/bootstrap")
        self.assertEqual(response["status"], 405)
        self.assertFalse(response["json"]["ok"])

    def test_body_limit(self):
        big = "x" * (300 * 1024)
        response = self.request(
            "POST",
            "/api/v1/posts",
            body={"community_id": "brooklyn", "text": big},
        )
        self.assertEqual(response["status"], 413)


class ConcurrencyTests(ApiTestCase):
    def test_parallel_reads_and_writes(self):
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=8) as pool:
            reads = list(pool.map(lambda _: self.authed("GET", "/api/v1/bootstrap"), range(10)))
        self.assertTrue(all(response["status"] == 200 for response in reads))

        def write(index):
            return self.authed("POST", "/api/v1/posts", {
                "community_id": "brooklyn",
                "text": f"Concurrent post {index}",
                "tag": "club",
            })

        with ThreadPoolExecutor(max_workers=5) as pool:
            writes = list(pool.map(write, range(5)))
        self.assertTrue(all(response["status"] == 200 for response in writes), [w["status"] for w in writes])
        state = self.data(self.authed("GET", "/api/v1/bootstrap"))
        for index in range(5):
            self.assertTrue(any(post["text"] == f"Concurrent post {index}" for post in state["posts"]))


class SessionAndAuthorizationTests(ApiTestCase):
    def test_expired_session_is_rejected(self):
        with db.connect() as connection:
            connection.execute(
                "UPDATE sessions SET expires_at = ? WHERE token_hash = ?",
                (iso(utc_now() - timedelta(minutes=1)), hash_token(self.token)),
            )
        self.error(self.authed("GET", "/api/v1/me"), 401, "unauthorized")

    def test_member_cannot_create_plans_or_reset_demo(self):
        session = self.data(self.request("POST", "/api/v1/auth/register", {
            "name": "Regular Member",
            "email": "regular@example.com",
            "password": "password-123",
        }))
        token = session["token"]
        self.error(self.request("POST", "/api/v1/plans", {
            "title": "No plan",
            "opponent": "Nobody",
            "date": "2026-12-01T14:30:00Z",
            "venue": "Nowhere",
            "objective": "Should not be allowed.",
        }, token=token), 403, "forbidden")
        self.error(self.request("POST", "/api/v1/demo/reset", token=token), 403, "forbidden")

    def test_same_origin_is_allowed_on_a_changed_port(self):
        # The test server host is the current 127.0.0.1:<ephemeral port>.
        origin = f"http://127.0.0.1:{self.port}"
        response = self.request("OPTIONS", "/api/v1/bootstrap", origin=origin)
        self.assertEqual(response["status"], 204)
        self.assertEqual(response["headers"].get("access-control-allow-origin"), origin)

    def test_head_static_response_has_no_body(self):
        response = self.request("HEAD", "/")
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"], b"")


class ReadEndpointTests(ApiTestCase):
    def test_read_endpoints_return_serialized_resources(self):
        index = self.data(self.request("GET", "/api/v1"))
        self.assertEqual(index["name"], "Touchline API")
        self.assertIn("openapi.json", index["docs"])

        posts = self.data(self.authed("GET", "/api/v1/posts"))
        self.assertGreaterEqual(len(posts), 4)
        self.assertTrue(all("comments" in post for post in posts))

        team = self.data(self.authed("GET", "/api/v1/team"))
        player = self.data(self.authed("GET", f"/api/v1/players/{team['players'][0]['id']}"))
        self.assertEqual(player["id"], team["players"][0]["id"])

        plans = self.data(self.authed("GET", "/api/v1/plans"))
        plan = self.data(self.authed("GET", f"/api/v1/plans/{plans[0]['id']}"))
        self.assertEqual(plan["id"], plans[0]["id"])

        community = self.data(self.authed("GET", "/api/v1/communities"))[0]
        self.assertIn("joined", community)
