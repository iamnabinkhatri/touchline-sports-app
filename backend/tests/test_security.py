"""Security regression tests for the duties/calendar feature and shared API defenses.

Each test is one attack class. These run against the real HTTP server in-process,
so they cover parsing, routing, headers and the database together.
"""
import base64
import json
import socket
from datetime import datetime, timedelta, timezone

from backend import db
from backend.tests.base import ApiTestCase

DUTIES = "/api/v1/duties"
CALENDAR = "/api/v1/calendar"
EVIL = "https://evil.example"


def future(days=4):
    return (datetime.now(timezone.utc) + timedelta(days=days)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class SecurityTestBase(ApiTestCase):
    def admin_token(self):
        return self.data(self.request("POST", "/api/v1/auth/login", {
            "email": "alex@brooklynrangers.club", "password": "touchline-demo",
        }))["token"]

    def raw_authed(self, method, path, body=None, content_type="application/json", token=None):
        """Send exact bytes, bypassing the JSON helper, so malformed bodies can be tested."""
        import http.client

        connection = http.client.HTTPConnection("127.0.0.1", self.httpd.server_address[1], timeout=10)
        headers = {"Authorization": f"Bearer {token or self.admin_token()}"}
        if content_type is not None:
            headers["Content-Type"] = content_type
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        data = response.read()
        connection.close()
        return {"status": response.status, "body": data, "headers": {k.lower(): v for k, v in response.getheaders()}}

    def member(self, name, email):
        session = self.data(self.request("POST", "/api/v1/auth/register", {
            "name": name, "email": email, "password": "Str0ng-pass-123",
        }))
        return session["token"], session["user"]["id"]

    def duty_count(self):
        with db.connect() as connection:
            return connection.execute("SELECT COUNT(*) AS n FROM duties").fetchone()["n"]

    def assert_safe(self, response, label=""):
        self.assertNotEqual(response["status"], 500, f"{label}: {response.get('body')}")
        body = response.get("body") or b""
        self.assertNotIn(b"Traceback", body, label)
        self.assertNotIn(b'File "', body, label)


class InjectionTests(SecurityTestBase):
    SQL_PAYLOADS = [
        "' OR '1'='1",
        "'; DROP TABLE duties;--",
        "1 UNION SELECT id,password_hash FROM users--",
        "\" OR \"\"=\"",
        "x'); DELETE FROM duties; --",
    ]

    def test_sql_in_duty_ids_never_reaches_the_database(self):
        before = self.duty_count()
        for payload in self.SQL_PAYLOADS:
            encoded = payload.replace(" ", "%20").replace("'", "%27").replace('"', "%22")
            for method, suffix in (("POST", "/claim"), ("DELETE", "/claim"), ("DELETE", "")):
                with self.subTest(payload=payload, method=method, suffix=suffix):
                    response = self.authed(method, f"{DUTIES}/{encoded}{suffix}")
                    self.assert_safe(response, payload)
                    self.assertIn(response["status"], (400, 404))
        self.assertEqual(self.duty_count(), before)

    def test_sql_in_body_fields_is_stored_inertly(self):
        before = self.duty_count()
        for payload in self.SQL_PAYLOADS:
            with self.subTest(payload=payload):
                response = self.authed("POST", DUTIES, {
                    "kind": "coffee", "starts_at": future(), "title": payload, "note": payload,
                })
                self.assert_safe(response, payload)
                if response["status"] == 200:
                    created = json.loads(response["body"])["data"]
                    self.assertEqual(created["title"], payload)
        self.assertGreaterEqual(self.duty_count(), before)
        # the table is intact and still answers queries
        self.data(self.authed("GET", "/api/v1/bootstrap"))

    def test_sql_in_calendar_query_is_rejected(self):
        for payload in self.SQL_PAYLOADS:
            with self.subTest(payload=payload):
                encoded = payload.replace(" ", "%20").replace("'", "%27").replace('"', "%22")
                response = self.authed("GET", f"{CALENDAR}?from={encoded}&to=2026-12-01")
                self.assert_safe(response, payload)
                self.assertEqual(response["status"], 400)

    def test_sql_in_event_key_is_rejected_before_any_lookup(self):
        for payload in self.SQL_PAYLOADS:
            with self.subTest(payload=payload):
                response = self.authed("POST", DUTIES, {"kind": "coffee", "starts_at": future(), "event_key": payload})
                self.assert_safe(response, payload)
                self.assertEqual(response["status"], 400)


class StoredXssTests(SecurityTestBase):
    PAYLOADS = [
        "<script>alert(document.cookie)</script>",
        "<img src=x onerror=alert(1)>",
        "\"><svg/onload=alert(1)>",
        "javascript:alert(1)",
        "<iframe src='https://evil.example'></iframe>",
    ]

    def test_payloads_round_trip_as_plain_json_strings(self):
        for payload in self.PAYLOADS:
            with self.subTest(payload=payload):
                response = self.authed("POST", DUTIES, {"kind": "snacks", "starts_at": future(), "title": payload, "note": payload})
                self.assertEqual(response["status"], 200, response.get("body"))
                self.assertEqual(response["headers"]["content-type"].split(";")[0], "application/json")
                self.assertEqual(response["headers"].get("x-content-type-options"), "nosniff")
                self.assertEqual(json.loads(response["body"])["data"]["title"], payload)

    def test_payloads_are_returned_inside_the_calendar_json_only(self):
        self.authed("POST", DUTIES, {"kind": "snacks", "starts_at": future(), "title": self.PAYLOADS[0]})
        day = future()[:10]
        response = self.authed("GET", f"{CALENDAR}?from={day}&to={day}")
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["headers"]["content-type"].split(";")[0], "application/json")


class MassAssignmentAndPrivilegeTests(SecurityTestBase):
    def test_registration_cannot_grant_admin_or_coach_rights(self):
        session = self.data(self.request("POST", "/api/v1/auth/register", {
            "name": "Power User",
            "email": "power@example.com",
            "password": "Str0ng-pass-123",
            "role": "admin",
            "club_role": "Coach",
            "club_points": 99999,
        }))
        self.assertNotEqual(session["user"]["role"], "Coach")
        token = session["token"]
        self.error(self.request("POST", "/api/v1/plans", {"title": "x"}, token=token), 403, "forbidden")
        self.error(self.request("POST", "/api/v1/demo/reset", token=token), 403, "forbidden")

    def test_members_cannot_hijack_someone_elses_duty(self):
        owner, owner_id = self.member("Owner", "owner-sec@example.com")
        thief, thief_id = self.member("Thief", "thief-sec@example.com")
        duty = self.data(self.request("POST", DUTIES, {"kind": "donuts", "starts_at": future()}, token=owner))
        self.data(self.request("POST", f"{DUTIES}/{duty['id']}/claim", token=owner))
        # the thief tries every way of changing the owner's claim
        self.error(self.request("POST", f"{DUTIES}/{duty['id']}/claim", {"claimed_by": thief_id}, token=thief), 409)
        self.error(self.request("DELETE", f"{DUTIES}/{duty['id']}/claim", token=thief), 403)
        self.error(self.request("DELETE", f"{DUTIES}/{duty['id']}", token=thief), 403)
        with db.connect() as connection:
            row = connection.execute("SELECT claimed_by FROM duties WHERE id = ?", (duty["id"],)).fetchone()
        self.assertEqual(row["claimed_by"], owner_id)

    def test_members_cannot_change_duty_fields_by_patch(self):
        token, _ = self.member("Patcher", "patcher@example.com")
        duty = self.data(self.request("POST", DUTIES, {"kind": "coffee", "starts_at": future()}, token=token))
        response = self.request("PATCH", f"{DUTIES}/{duty['id']}", {"title": "pwned", "claimed_by": "alex-kim"}, token=token)
        self.assertIn(response["status"], (404, 405))
        self.assert_safe(response)


class MethodAndPathTests(SecurityTestBase):
    def test_method_override_header_is_ignored(self):
        token, _ = self.member("Override", "override@example.com")
        duty = self.data(self.request("POST", DUTIES, {"kind": "coffee", "starts_at": future()}, token=token))
        response = self.request(
            "POST", f"{DUTIES}/{duty['id']}", {}, token=token,
            headers={"X-HTTP-Method-Override": "DELETE", "X-Method-Override": "DELETE"},
        )
        self.assertIn(response["status"], (404, 405))
        with db.connect() as connection:
            left = connection.execute("SELECT COUNT(*) AS n FROM duties WHERE id = ?", (duty["id"],)).fetchone()["n"]
        self.assertEqual(left, 1)

    def test_path_tricks_never_match_another_resource(self):
        paths = [
            f"{DUTIES}/..%2F..%2Fplayers%2Fava/claim",
            f"{DUTIES}/%2e%2e/claim",
            f"{DUTIES}/%00/claim",
            f"{DUTIES}/x%0A/claim",
            f"{DUTIES}/x%0d%0a/claim",
            f"{DUTIES}/x/claim/",
            f"{DUTIES}//claim",
            f"{DUTIES}/duty-coffee-riverside%2fclaim",
            f"{DUTIES}/%ff%fe/claim",
        ]
        for path in paths:
            with self.subTest(path=path):
                for method in ("POST", "DELETE"):
                    response = self.authed(method, path)
                    self.assert_safe(response, path)
                    self.assertIn(response["status"], (400, 404, 405), path)
        # the riverside coffee duty was never touched by a mangled path
        with db.connect() as connection:
            row = connection.execute("SELECT claimed_by FROM duties WHERE id = 'duty-coffee-riverside'").fetchone()
        self.assertEqual(row["claimed_by"], "alex-kim")

    def test_query_string_token_is_not_accepted(self):
        token = self.data(self.request("POST", "/api/v1/auth/login", {
            "email": "alex@brooklynrangers.club", "password": "touchline-demo",
        }))["token"]
        self.error(self.request("GET", f"{CALENDAR}?token={token}"), 401, "unauthorized")
        self.error(self.request("GET", f"{CALENDAR}?access_token={token}"), 401, "unauthorized")

    def test_non_bearer_auth_schemes_are_rejected(self):
        basic = base64.b64encode(b"alex@brooklynrangers.club:touchline-demo").decode()
        for header in (f"Basic {basic}", "Bearer ", "Bearer", "Token abc", "bearer\x00x"):
            with self.subTest(header=header):
                response = self.request("GET", CALENDAR, headers={"Authorization": header})
                self.assertEqual(response["status"], 401)
                self.assert_safe(response)

    def test_forwarded_for_cannot_reset_the_duty_rate_limit(self):
        from backend import service

        token, _ = self.member("Limit Dodger", "dodger@example.com")
        for _ in range(service.DUTY_CREATE_LIMIT):
            self.request("POST", DUTIES, {"kind": "coffee", "starts_at": future()}, token=token)
        for index in range(3):
            response = self.request(
                "POST", DUTIES, {"kind": "coffee", "starts_at": future()}, token=token,
                headers={"X-Forwarded-For": f"10.0.0.{index}"},
            )
            self.assertEqual(response["status"], 429)


class ParserAbuseTests(SecurityTestBase):
    def test_deeply_nested_json_is_rejected_not_crashed(self):
        bomb = b"[" * 20000 + b"]" * 20000
        raw = self.raw_authed("POST", DUTIES, bomb)
        self.assertIn(raw["status"], (400, 413), raw["body"][:200])
        self.assertNotIn(b"Traceback", raw["body"])

    def test_huge_collections_are_rejected(self):
        body = json.dumps({"kind": "coffee", "starts_at": future(), "title": ["x"] * 50000}).encode()
        raw = self.raw_authed("POST", DUTIES, body)
        self.assertIn(raw["status"], (400, 413))

    def test_oversized_body_is_refused(self):
        body = json.dumps({"kind": "coffee", "starts_at": future(), "note": "x" * 400000}).encode()
        raw = self.raw_authed("POST", DUTIES, body)
        self.assertEqual(raw["status"], 413)

    def test_wrong_or_missing_content_type_does_not_crash(self):
        body = json.dumps({"kind": "coffee", "starts_at": future()}).encode()
        for content_type in ("text/plain", "application/x-www-form-urlencoded", "", "multipart/form-data; boundary=x"):
            with self.subTest(content_type=content_type):
                raw = self.raw_authed("POST", DUTIES, body, content_type=content_type)
                self.assert_safe(raw, content_type)
                self.assertIn(raw["status"], (200, 400, 415))

    def test_malformed_json_bodies_are_rejected(self):
        samples = [b"{", b"null", b"[]", b'"text"', b"\xff\xfe\x00", b"{'kind': 'coffee'}", b"NaN", b"1e999999"]
        for sample in samples:
            with self.subTest(sample=sample[:20]):
                raw = self.raw_authed("POST", DUTIES, sample)
                self.assert_safe(raw, repr(sample))
                self.assertEqual(raw["status"], 400)

    def test_nan_and_infinity_numbers_are_not_accepted_as_times(self):
        for value in (float("nan"), float("inf"), 1e308, -1):
            with self.subTest(value=value):
                raw = self.raw_authed("POST", DUTIES, json.dumps({"kind": "coffee", "starts_at": value}).encode())
                self.assert_safe(raw)
                self.assertEqual(raw["status"], 400)


class HeaderAndInformationTests(SecurityTestBase):
    def test_api_responses_are_not_cacheable_and_not_sniffable(self):
        token, _ = self.member("Cache Check", "cache@example.com")
        response = self.request("GET", CALENDAR, token=token)
        self.assertEqual(response["headers"].get("x-content-type-options"), "nosniff")
        self.assertIn("no-store", response["headers"].get("cache-control", ""))

    def test_server_banner_does_not_reveal_the_python_version(self):
        response = self.request("GET", "/api/v1/health")
        server = response["headers"].get("server", "")
        self.assertNotIn("Python", server)
        self.assertNotRegex(server, r"\d+\.\d+")

    def test_cors_refuses_foreign_origins_on_duty_routes(self):
        token, _ = self.member("Cors Check", "cors@example.com")
        response = self.request("GET", CALENDAR, token=token, origin=EVIL)
        self.assertNotIn("access-control-allow-origin", response["headers"])
        preflight = self.request("OPTIONS", DUTIES, headers={
            "Origin": EVIL, "Access-Control-Request-Method": "DELETE",
        })
        self.assertNotEqual(preflight["headers"].get("access-control-allow-origin"), EVIL)

    def test_errors_never_expose_internals(self):
        probes = [
            ("POST", DUTIES, b"{bad"),
            ("POST", DUTIES, b'{"kind": ["x"], "starts_at": "2026-01-01"}'),
            ("POST", f"{DUTIES}/%00/claim", None),
            ("GET", f"{CALENDAR}?from=bad", None),
        ]
        for method, path, body in probes:
            with self.subTest(path=path):
                raw = self.raw_authed(method, path, body) if body is not None else self.authed(method, path)
                self.assert_safe(raw, path)
                text = raw["body"].decode(errors="replace").lower()
                for leak in ("sqlite", "traceback", "/home/", "site-packages", "password_hash", "pbkdf2"):
                    self.assertNotIn(leak, text, path)


def read_all(sock):
    chunks = []
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks).decode(errors="replace")


class RawSocketTests(SecurityTestBase):
    def test_conflicting_content_length_headers_are_refused(self):
        port = self.httpd.server_address[1]
        payload = b'{"kind":"coffee","starts_at":"2030-01-01T10:00:00Z"}'
        request = (
            f"POST {DUTIES} HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer {self.admin_token()}\r\n"
            f"Content-Type: application/json\r\nContent-Length: 5\r\nContent-Length: {len(payload)}\r\n"
            "Connection: close\r\n\r\n"
        ).encode() + payload
        with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
            sock.sendall(request)
            reply = read_all(sock)
        status_line = reply.split("\r\n", 1)[0]
        self.assertNotIn(" 500 ", status_line)
        self.assertNotIn("Traceback", reply)

    def test_injected_headers_are_not_reflected(self):
        port = self.httpd.server_address[1]
        request = (
            "GET /api/v1/health HTTP/1.1\r\nHost: x\r\n"
            "X-Evil: a\r\nX-Other: b\r\nConnection: close\r\n\r\n"
        ).encode()
        with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
            sock.sendall(request)
            reply = read_all(sock)
        self.assertEqual(reply.split(" ")[1], "200", reply[:120])
        self.assertNotIn("X-Evil", reply)

    def test_foreign_origin_is_refused_before_any_work(self):
        port = self.httpd.server_address[1]
        request = (
            "GET /api/v1/health HTTP/1.1\r\nHost: x\r\nOrigin: https://a.example\r\nConnection: close\r\n\r\n"
        ).encode()
        with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
            sock.sendall(request)
            reply = read_all(sock)
        self.assertEqual(reply.split(" ")[1], "403", reply[:120])
        self.assertIn("cors_forbidden", reply)



if __name__ == "__main__":
    import unittest

    unittest.main()
