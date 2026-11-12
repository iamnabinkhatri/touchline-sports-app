import json
import threading
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

from backend import db, service
from backend.tests.base import ApiTestCase

DUTIES = "/api/v1/duties"
CALENDAR = "/api/v1/calendar"
PASSWORD = "Str0ng-pass-123"


def future(days=3, hours=0):
    return (datetime.now(timezone.utc) + timedelta(days=days, hours=hours)).replace(
        microsecond=0
    ).isoformat().replace("+00:00", "Z")


def past(hours):
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).replace(
        microsecond=0
    ).isoformat().replace("+00:00", "Z")


def raw_post(url, token, path):
    request = urllib.request.Request(
        f"{url}{path}",
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        data=b"{}",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


class DutiesTestBase(ApiTestCase):
    def member(self, name, email):
        session = self.data(self.request("POST", "/api/v1/auth/register", {
            "name": name, "email": email, "password": PASSWORD,
        }))
        return session["token"], session["user"]["id"]

    def make_coach(self, user_id):
        with db.connect() as connection:
            connection.execute("UPDATE users SET role = 'coach' WHERE id = ?", (user_id,))

    def duty(self, token=None, **overrides):
        body = {"kind": "coffee", "starts_at": future()}
        body.update(overrides)
        if token is None:
            return self.authed("POST", DUTIES, body)
        return self.request("POST", DUTIES, body, token=token)

    def create(self, token=None, **overrides):
        return self.data(self.duty(token, **overrides), 200)


class CalendarReadTests(DutiesTestBase):
    def test_seeded_calendar_merges_matches_events_and_duties(self):
        today = date.today()
        url = f"{CALENDAR}?from={(today - timedelta(days=30)).isoformat()}&to={(today + timedelta(days=60)).isoformat()}"
        payload = self.data(self.authed("GET", url))
        sources = {entry["source"] for entry in payload["entries"]}
        self.assertEqual(sources, {"match", "event", "duty"})
        duties = [e for e in payload["entries"] if e["source"] == "duty"]
        self.assertTrue(all(e["duty"] and e["duty"]["id"] == e["id"] for e in duties))
        coffee = next(e for e in duties if e["id"] == "duty-coffee-riverside")
        self.assertEqual(coffee["duty"]["claimedBy"]["id"], "alex-kim")
        self.assertEqual(coffee["duty"]["eventKey"], "fixture-riverside")
        self.assertIn("Alex", coffee["detail"])

    def test_entries_are_sorted_and_inside_the_range(self):
        today = date.today()
        start, end = today.isoformat(), (today + timedelta(days=60)).isoformat()
        payload = self.data(self.authed("GET", f"{CALENDAR}?from={start}&to={end}"))
        times = [datetime.fromisoformat(e["date"].replace("Z", "+00:00")) for e in payload["entries"]]
        self.assertEqual(times, sorted(times))
        lo = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
        hi = datetime.fromisoformat(end).replace(tzinfo=timezone.utc) + timedelta(days=1)
        self.assertTrue(all(lo <= t < hi for t in times))

    def test_default_range_is_the_current_month(self):
        payload = self.data(self.authed("GET", CALENDAR))
        today = date.today()
        self.assertEqual(payload["from"], today.replace(day=1).isoformat())
        last = (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        self.assertEqual(payload["to"], last.isoformat())

    def test_range_validation(self):
        cases = {
            "bad format": "from=2026/11/01&to=2026-11-30",
            "not a date": "from=2026-02-31&to=2026-03-01",
            "end before start": "from=2026-11-10&to=2026-11-01",
            "too wide": "from=2026-01-01&to=2026-12-31",
            "sql in date": "from=2026-11-01%27%20OR%20%271%27%3D%271&to=2026-11-30",
            "null byte": "from=2026-11-01%00&to=2026-11-30",
            "trailing newline": "from=2026-11-01%0A&to=2026-11-30",
        }
        for label, query in cases.items():
            with self.subTest(label):
                self.error(self.authed("GET", f"{CALENDAR}?{query}"), 400)

    def test_calendar_requires_authentication(self):
        self.error(self.request("GET", CALENDAR), 401, "unauthorized")

    def test_bootstrap_includes_recent_and_upcoming_duties(self):
        state = self.data(self.authed("GET", "/api/v1/bootstrap"))
        ids = {d["id"] for d in state["duties"]}
        self.assertIn("duty-coffee-riverside", ids)
        self.assertIn("duty-snacks-training", ids)
        with db.connect() as connection:
            connection.execute(
                "INSERT INTO duties (id, team_id, kind, title, starts_at, created_by, created_at) "
                "SELECT 'duty-old', id, 'coffee', 'Old', ?, NULL, ? FROM teams LIMIT 1",
                (past(24 * 10), past(24 * 10)),
            )
        state = self.data(self.authed("GET", "/api/v1/bootstrap"))
        self.assertNotIn("duty-old", {d["id"] for d in state["duties"]})


class DutyCreateTests(DutiesTestBase):
    def test_batch_creates_multiple_assigned_duties_with_community_scope(self):
        _token, member_id = self.member("Assigned Player", "assigned.player@example.com")
        with db.connect() as connection:
            community_id = connection.execute("SELECT community_id FROM teams ORDER BY rowid LIMIT 1").fetchone()["community_id"]
            connection.execute("INSERT INTO community_members(community_id,user_id,role,joined_at) VALUES(?,?,'Member',?)", (community_id, member_id, future(0)))
        result = self.data(self.authed("POST", DUTIES, {
            "community_id": community_id,
            "items": [
                {"kind": "coffee", "starts_at": future(3), "assigned_to": member_id},
                {"kind": "drinks", "starts_at": future(3, 1)},
            ],
        }))
        self.assertEqual(len(result["duties"]), 2)
        self.assertEqual(result["duties"][0]["assignedTo"]["id"], member_id)
        self.assertIsNone(result["duties"][1]["assignedTo"])
        date_key = datetime.fromisoformat(result["duties"][0]["startsAt"].replace("Z", "+00:00")).date().isoformat()
        calendar = self.data(self.authed("GET", f"{CALENDAR}?community_id={community_id}&from={date_key}&to={date_key}"))
        entry = next(item for item in calendar["entries"] if item["id"] == result["duties"][0]["id"])
        self.assertEqual(entry["communityId"], community_id)
        self.assertEqual(entry["duty"]["assignedTo"]["name"], "Assigned Player")

    def test_regular_member_cannot_assign_a_duty_to_another_member(self):
        token, user_id = self.member("Regular Member", "regular.member@example.com")
        _other_token, other_id = self.member("Other Member", "other.member@example.com")
        with db.connect() as connection:
            community_id = connection.execute("SELECT community_id FROM teams ORDER BY rowid LIMIT 1").fetchone()["community_id"]
            for member_id in (user_id, other_id):
                connection.execute("INSERT INTO community_members(community_id,user_id,role,joined_at) VALUES(?,?,'Member',?)", (community_id, member_id, future(0)))
        response = self.duty(token, community_id=community_id, assigned_to=other_id)
        self.error(response, 403, "forbidden")

    def test_member_can_add_a_duty_and_it_appears_on_the_calendar(self):
        token, _ = self.member("Coffee Parent", "coffee.parent@example.com")
        created = self.create(token, kind="donuts", starts_at=future(2), note="Two dozen, please.")
        self.assertEqual(created["kind"], "donuts")
        self.assertEqual(created["kindLabel"], "Donuts")
        self.assertIsNone(created["claimedBy"])
        day = datetime.fromisoformat(created["startsAt"].replace("Z", "+00:00")).date().isoformat()
        payload = self.data(self.authed("GET", f"{CALENDAR}?from={day}&to={day}"))
        self.assertIn(created["id"], {e["id"] for e in payload["entries"]})

    def test_default_title_comes_from_the_kind(self):
        created = self.create(kind="drinks")
        self.assertEqual(created["title"], "Drinks")

    def test_custom_title_and_match_link(self):
        created = self.create(title="Coffee for the away trip", event_key="fixture-northside")
        self.assertEqual(created["title"], "Coffee for the away trip")
        self.assertEqual(created["eventKey"], "fixture-northside")

    def test_rejects_invalid_input(self):
        cases = {
            "unknown kind": {"kind": "cake"},
            "missing kind": {"kind": None},
            "kind as a list": {"kind": ["coffee"]},
            "kind as an object": {"kind": {"x": 1}},
            "title too long": {"title": "x" * 81},
            "title as a number": {"title": 42},
            "title as a list": {"title": ["a"]},
            "missing start time": {"starts_at": None},
            "start time not a date": {"starts_at": "next tuesday"},
            "start time as a number": {"starts_at": 1700000000},
            "start time as an object": {"starts_at": {"at": "2026-11-07"}},
            "start time too far back": {"starts_at": past(24 * 3)},
            "start time too far ahead": {"starts_at": future(days=400)},
            "note too long": {"note": "n" * 201},
            "note as a list": {"note": ["x"]},
            "unknown match": {"event_key": "fixture-does-not-exist"},
            "match as a number": {"event_key": 7},
            "match with path tricks": {"event_key": "../../etc/passwd"},
            "match with sql": {"event_key": "x' OR '1'='1"},
            "control characters in title": {"title": "Coffee\x00drop"},
        }
        for label, overrides in cases.items():
            with self.subTest(label):
                response = self.duty(**overrides)
                self.assertIn(response["status"], (400,), response.get("body"))
                self.assertNotIn(b"Traceback", response["body"])

    def test_clients_cannot_set_ownership_or_claims_on_create(self):
        token, _ = self.member("Sneaky Member", "sneaky@example.com")
        created = self.data(self.request("POST", DUTIES, {
            "kind": "coffee",
            "starts_at": future(),
            "id": "duty-forged",
            "team_id": "not-a-team",
            "created_by": "alex-kim",
            "created_at": "2001-01-01T00:00:00Z",
            "claimed_by": "alex-kim",
            "claimed_at": "2001-01-01T00:00:00Z",
        }, token=token))
        self.assertNotEqual(created["id"], "duty-forged")
        self.assertIsNone(created["claimedBy"])
        self.assertNotEqual(created["createdById"], "alex-kim")
        self.assertIsNone(created["claimedAt"])

    def test_create_is_rate_limited_per_user(self):
        token, _ = self.member("Spammer", "spammer@example.com")
        for _ in range(service.DUTY_CREATE_LIMIT):
            self.assertEqual(self.duty(token)["status"], 200)
        blocked = self.duty(token)
        self.assertEqual(blocked["status"], 429)
        self.assertGreater(int(blocked["headers"]["retry-after"]), 0)
        # another member is unaffected
        other, _ = self.member("Fine Member", "fine@example.com")
        self.assertEqual(self.duty(other)["status"], 200)


class DutyClaimTests(DutiesTestBase):
    def test_first_come_first_served(self):
        first, first_id = self.member("First Parent", "first@example.com")
        second, _ = self.member("Second Parent", "second@example.com")
        duty = self.create(kind="coffee")
        claimed = self.data(self.request("POST", f"{DUTIES}/{duty['id']}/claim", token=first))
        self.assertEqual(claimed["claimedBy"]["id"], first_id)
        self.error(self.request("POST", f"{DUTIES}/{duty['id']}/claim", token=second), 409, "already_claimed")
        # claiming it again as the same person is a harmless no-op
        again = self.data(self.request("POST", f"{DUTIES}/{duty['id']}/claim", token=first))
        self.assertEqual(again["claimedBy"]["id"], first_id)

    def test_claim_uses_the_caller_not_the_body(self):
        token, user_id = self.member("Body Tamper", "tamper@example.com")
        duty = self.create()
        claimed = self.data(self.request(
            "POST", f"{DUTIES}/{duty['id']}/claim", {"user_id": "alex-kim", "claimed_by": "alex-kim"}, token=token,
        ))
        self.assertEqual(claimed["claimedBy"]["id"], user_id)

    def test_cannot_claim_a_duty_that_already_happened(self):
        duty = self.create()
        with db.connect() as connection:
            connection.execute("UPDATE duties SET starts_at = ? WHERE id = ?", (past(6), duty["id"]))
        self.error(self.authed("POST", f"{DUTIES}/{duty['id']}/claim"), 409, "duty_passed")

    def test_per_day_claim_limit(self):
        token, _ = self.member("Busy Parent", "busy@example.com")
        same_day = future(days=5)
        ids = [self.create(starts_at=same_day)["id"] for _ in range(3)]
        self.data(self.request("POST", f"{DUTIES}/{ids[0]}/claim", token=token))
        self.data(self.request("POST", f"{DUTIES}/{ids[1]}/claim", token=token))
        self.error(self.request("POST", f"{DUTIES}/{ids[2]}/claim", token=token), 409, "claim_limit")

    def test_concurrent_claims_only_one_wins(self):
        duty = self.create()
        tokens = [self.member(f"Racer {i}", f"racer{i}@example.com")[0] for i in range(12)]
        url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        barrier = threading.Barrier(len(tokens))
        results = []
        lock = threading.Lock()

        def attempt(token):
            barrier.wait()
            status = raw_post(url, token, f"{DUTIES}/{duty['id']}/claim")
            with lock:
                results.append(status)

        threads = [threading.Thread(target=attempt, args=(token,)) for token in tokens]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(results.count(200), 1, results)
        self.assertEqual(results.count(409), len(tokens) - 1, results)
        final = self.data(self.authed("GET", "/api/v1/bootstrap"))
        holder = next(d for d in final["duties"] if d["id"] == duty["id"])["claimedBy"]
        self.assertIsNotNone(holder)

    def test_concurrent_claims_cannot_exceed_the_daily_cap(self):
        token, _ = self.member("Greedy Parent", "greedy@example.com")
        same_day = future(days=6)
        ids = [self.create(starts_at=same_day)["id"] for _ in range(6)]
        url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        barrier = threading.Barrier(len(ids))
        results = []
        lock = threading.Lock()

        def attempt(duty_id):
            barrier.wait()
            status = raw_post(url, token, f"{DUTIES}/{duty_id}/claim")
            with lock:
                results.append(status)

        threads = [threading.Thread(target=attempt, args=(i,)) for i in ids]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(results.count(200), 2, results)

    def test_release_rules(self):
        owner, owner_id = self.member("Owner Parent", "owner@example.com")
        stranger, _ = self.member("Stranger Parent", "stranger@example.com")
        duty = self.create()
        self.data(self.request("POST", f"{DUTIES}/{duty['id']}/claim", token=owner))
        self.error(self.request("DELETE", f"{DUTIES}/{duty['id']}/claim", token=stranger), 403, "forbidden")
        released = self.data(self.request("DELETE", f"{DUTIES}/{duty['id']}/claim", token=owner))
        self.assertIsNone(released["claimedBy"])
        # releasing an unclaimed duty is a no-op
        self.assertIsNone(self.data(self.request("DELETE", f"{DUTIES}/{duty['id']}/claim", token=owner))["claimedBy"])

    def test_coach_can_release_anyones_duty(self):
        owner, _ = self.member("Coach Target", "target@example.com")
        coach, coach_id = self.member("Coach Helper", "helper@example.com")
        self.make_coach(coach_id)
        duty = self.create()
        self.data(self.request("POST", f"{DUTIES}/{duty['id']}/claim", token=owner))
        released = self.data(self.request("DELETE", f"{DUTIES}/{duty['id']}/claim", token=coach))
        self.assertIsNone(released["claimedBy"])

    def test_malformed_and_unknown_duty_ids(self):
        self.error(self.authed("POST", f"{DUTIES}/does-not-exist/claim"), 404, "not_found")
        self.error(self.authed("POST", f"{DUTIES}/UPPER/claim"), 400, "invalid_id")
        self.error(self.authed("DELETE", f"{DUTIES}/x/claim"), 400, "invalid_id")


class DutyDeleteTests(DutiesTestBase):
    def test_only_the_creator_or_a_coach_can_delete(self):
        creator, _ = self.member("Creator Parent", "creator@example.com")
        other, _ = self.member("Other Parent", "other@example.com")
        duty = self.create(token=creator)
        self.error(self.request("DELETE", f"{DUTIES}/{duty['id']}", token=other), 403, "forbidden")
        self.assertTrue(self.data(self.request("DELETE", f"{DUTIES}/{duty['id']}", token=creator))["deleted"])
        self.error(self.request("DELETE", f"{DUTIES}/{duty['id']}", token=creator), 404, "not_found")

    def test_coach_can_delete_any_duty(self):
        creator, _ = self.member("Creator Two", "creator2@example.com")
        coach, coach_id = self.member("Coach Two", "coach2@example.com")
        self.make_coach(coach_id)
        duty = self.create(token=creator)
        self.assertTrue(self.data(self.request("DELETE", f"{DUTIES}/{duty['id']}", token=coach))["deleted"])

    def test_deleting_a_claimed_duty_removes_the_claim_too(self):
        creator, _ = self.member("Creator Three", "creator3@example.com")
        taker, _ = self.member("Taker Three", "taker3@example.com")
        duty = self.create(token=creator)
        self.data(self.request("POST", f"{DUTIES}/{duty['id']}/claim", token=taker))
        self.data(self.request("DELETE", f"{DUTIES}/{duty['id']}", token=creator))
        with db.connect() as connection:
            left = connection.execute("SELECT COUNT(*) AS n FROM duties WHERE id = ?", (duty["id"],)).fetchone()["n"]
        self.assertEqual(left, 0)


class DutyAuthAndContractTests(DutiesTestBase):
    def test_all_duty_routes_require_a_token(self):
        duty_id = "duty-coffee-riverside"
        routes = [
            ("POST", DUTIES, {"kind": "coffee", "starts_at": future()}),
            ("POST", f"{DUTIES}/{duty_id}/claim", None),
            ("DELETE", f"{DUTIES}/{duty_id}/claim", None),
            ("DELETE", f"{DUTIES}/{duty_id}", None),
            ("GET", CALENDAR, None),
        ]
        for method, path, body in routes:
            with self.subTest(method=method, path=path):
                self.error(self.request(method, path, body), 401, "unauthorized")

    def test_a_logged_out_token_stops_working(self):
        token, _ = self.member("Logout Parent", "logout@example.com")
        self.data(self.request("POST", DUTIES, {"kind": "coffee", "starts_at": future()}, token=token))
        self.data(self.request("POST", "/api/v1/auth/logout", token=token))
        self.error(self.request("POST", DUTIES, {"kind": "coffee", "starts_at": future()}, token=token), 401)

    def test_openapi_documents_the_duty_contract(self):
        spec = self.data(self.request("GET", "/api/v1/openapi.json", token=self.token))
        paths = spec["paths"]
        self.assertIn("/api/v1/calendar", paths)
        self.assertIn("/api/v1/duties", paths)
        self.assertIn("/api/v1/duties/{duty_id}/claim", paths)
        self.assertIn("delete", paths["/api/v1/duties/{duty_id}/claim"])
        self.assertIn("Duty", spec["components"]["schemas"])
        self.assertIn("CalendarEntry", spec["components"]["schemas"])


if __name__ == "__main__":
    import unittest

    unittest.main()
