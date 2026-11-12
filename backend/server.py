import json
import mimetypes
import re
import sqlite3
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import config, db, service
from .errors import ApiError
from .validation import calendar_range
from .ratelimit import limiter
from .openapi import openapi_spec
from .security import hash_token, iso
from .serializers import user_public

SECURITY_HEADERS = {
    "Content-Security-Policy": "; ".join(
        [
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data:",
            "font-src 'self'",
            "connect-src 'self'",
            "object-src 'none'",
            "frame-src 'none'",
            "worker-src 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "frame-ancestors 'none'",
        ]
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "X-Permitted-Cross-Domain-Policies": "none",
    "Cache-Control": "no-cache, no-store, must-revalidate",
}

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}

STATIC_BLOCKED_FILES = {
    "/server.js",
    "/package.json",
    "/package-lock.json",
    "/README.md",
    "/TESTING.md",
}
STATIC_BLOCKED_PREFIXES = ("/backend/", "/data/", "/tests/", "/scripts/", "/.git/")


def _bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _int(value, default=0, minimum=0, maximum=99999):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


ROUTES = [
    ("GET", r"^/api/v1\Z", lambda c, u, m, b, q, t: {
        "name": "Touchline API",
        "version": "v1",
        "docs": "/api/v1/openapi.json",
        "health": "/api/v1/health",
    }, True, None),
    ("GET", r"^/api/v1/theme\Z", lambda c, u, m, b, q, t: service.get_public_app_theme(c), False, None),
    ("GET", r"^/api/v1/auth/google/config\Z", lambda c, u, m, b, q, t: service.google_login_config(c), False, None),
    ("GET", r"^/api/v1/health\Z", None, False, None),
    ("GET", r"^/api/v1/openapi\.json\Z", lambda c, u, m, b, q, t: openapi_spec(), True, None),
    ("POST", r"^/api/v1/auth/admin\Z", lambda c, u, m, b, q, t: service.admin_login(c, b), False, None),
    ("POST", r"^/api/v1/auth/google/start\Z", lambda c, u, m, b, q, t: service.google_login_start(c, b), False, None),
    ("POST", r"^/api/v1/auth/google/callback\Z", lambda c, u, m, b, q, t: service.google_login_complete(c, b), False, None),
    ("POST", r"^/api/v1/auth/login\Z", lambda c, u, m, b, q, t: service.login(c, b), False, None),
    ("POST", r"^/api/v1/auth/register\Z", lambda c, u, m, b, q, t: service.register(c, b), False, None),
    ("POST", r"^/api/v1/auth/verify-email\Z", lambda c, u, m, b, q, t: service.verify_email(c, b), False, None),
    ("POST", r"^/api/v1/auth/verification/resend\Z", lambda c, u, m, b, q, t: service.resend_verification(c, b), False, None),
    ("POST", r"^/api/v1/auth/password/forgot\Z", lambda c, u, m, b, q, t: service.forgot_password(c, b), False, None),
    ("POST", r"^/api/v1/auth/password/reset\Z", lambda c, u, m, b, q, t: service.reset_password(c, b), False, None),
    ("POST", r"^/api/v1/auth/password/change\Z", lambda c, u, m, b, q, t: service.change_password(c, u["id"], t, b), True, None),
    ("POST", r"^/api/v1/auth/2fa/login\Z", lambda c, u, m, b, q, t: service.two_factor_login(c, b), False, None),
    ("POST", r"^/api/v1/auth/2fa/setup\Z", lambda c, u, m, b, q, t: service.two_factor_setup(c, u["id"]), True, None),
    ("POST", r"^/api/v1/auth/2fa/enable\Z", lambda c, u, m, b, q, t: service.two_factor_enable(c, u["id"], b), True, None),
    ("POST", r"^/api/v1/auth/2fa/disable\Z", lambda c, u, m, b, q, t: service.two_factor_disable(c, u["id"], b), True, None),
    ("POST", r"^/api/v1/auth/logout\Z", lambda c, u, m, b, q, t: (service.logout(c, t), {"revoked": True})[1], True, None),
    ("GET", r"^/api/v1/me\Z", lambda c, u, m, b, q, t: user_public(u), True, None),
    ("GET", r"^/api/v1/me/api-key\Z", lambda c, u, m, b, q, t: service.api_key_access_status(c, u["id"]), True, None),
    ("POST", r"^/api/v1/me/api-key-requests\Z", lambda c, u, m, b, q, t: service.request_api_key(c, u["id"], b), True, None),
    ("POST", r"^/api/v1/me/api-key-claim\Z", lambda c, u, m, b, q, t: service.claim_api_key(c, u["id"]), True, None),
    ("DELETE", r"^/api/v1/me/api-key\Z", lambda c, u, m, b, q, t: service.revoke_api_key(c, u["id"]), True, None),
    ("GET", r"^/api/v1/admin/api-key-requests\Z", lambda c, u, m, b, q, t: service.list_api_key_requests(c, u["id"]), True, None),
    ("POST", r"^/api/v1/admin/api-key-requests/([A-Za-z0-9_-]+)/decision\Z", lambda c, u, m, b, q, t: service.decide_api_key_request(c, u["id"], m.group(1), b), True, None),
    ("GET", r"^/api/v1/bootstrap\Z", lambda c, u, m, b, q, t: service.get_bootstrap(c, u["id"]), True, None),
    ("GET", r"^/api/v1/posts\Z", lambda c, u, m, b, q, t: service.list_posts(
        c, u["id"],
        (q.get("community_id") or [None])[0],
        (q.get("tag") or [None])[0],
    ), True, None),
    ("POST", r"^/api/v1/posts\Z", lambda c, u, m, b, q, t: service.create_post(c, u["id"], b), True, None),
    ("DELETE", r"^/api/v1/posts/([A-Za-z0-9_-]+)\Z", lambda c, u, m, b, q, t: service.delete_post(c, u["id"], m.group(1)), True, None),
    ("POST", r"^/api/v1/posts/([A-Za-z0-9_-]+)/like\Z", lambda c, u, m, b, q, t: service.toggle_like(c, u["id"], m.group(1)), True, None),
    ("POST", r"^/api/v1/posts/([A-Za-z0-9_-]+)/comments\Z", lambda c, u, m, b, q, t: service.add_comment(c, u["id"], m.group(1), b), True, None),
    ("GET", r"^/api/v1/polls\Z", lambda c, u, m, b, q, t: service.list_polls(c, u["id"]), True, None),
    ("POST", r"^/api/v1/polls\Z", lambda c, u, m, b, q, t: service.create_poll(c, u["id"], b), True, None),
    ("POST", r"^/api/v1/polls/([A-Za-z0-9_-]+)/vote\Z", lambda c, u, m, b, q, t: service.vote_poll(c, u["id"], m.group(1), b), True, None),
    ("POST", r"^/api/v1/polls/([A-Za-z0-9_-]+)/teams\Z", lambda c, u, m, b, q, t: service.update_poll_teams(c, u["id"], m.group(1), b), True, None),
    ("GET", r"^/api/v1/polls/([A-Za-z0-9_-]+)/feedback\Z", lambda c, u, m, b, q, t: service.get_poll_feedback(c, u["id"], m.group(1)), True, None),
    ("POST", r"^/api/v1/polls/([A-Za-z0-9_-]+)/feedback\Z", lambda c, u, m, b, q, t: service.submit_poll_feedback(c, u["id"], m.group(1), b), True, None),
    ("GET", r"^/api/v1/communities\Z", lambda c, u, m, b, q, t: service.list_communities(c, u["id"]), True, None),
    ("POST", r"^/api/v1/communities\Z", lambda c, u, m, b, q, t: service.create_community(c, u["id"], b), True, None),
    ("GET", r"^/api/v1/communities/([A-Za-z0-9_-]+)/members\Z", lambda c, u, m, b, q, t: service.list_community_members(c, u["id"], m.group(1)), True, None),
    ("GET", r"^/api/v1/communities/([A-Za-z0-9_-]+)/poll-retention-settings\Z", lambda c, u, m, b, q, t: service.get_community_poll_retention(c, u["id"], m.group(1)), True, None),
    ("PATCH", r"^/api/v1/communities/([A-Za-z0-9_-]+)/poll-retention-settings\Z", lambda c, u, m, b, q, t: service.set_community_poll_retention(c, u["id"], m.group(1), b), True, None),
    ("GET", r"^/api/v1/communities/([A-Za-z0-9_-]+)/join-requests\Z", lambda c, u, m, b, q, t: service.list_community_join_requests(c, u["id"], m.group(1)), True, None),
    ("POST", r"^/api/v1/communities/([A-Za-z0-9_-]+)/join-requests\Z", lambda c, u, m, b, q, t: service.request_community_join(c, u["id"], m.group(1)), True, None),
    ("POST", r"^/api/v1/communities/([A-Za-z0-9_-]+)/join-requests/([A-Za-z0-9_-]+)/decision\Z", lambda c, u, m, b, q, t: service.decide_community_join_request(c, u["id"], m.group(1), m.group(2), b), True, None),
    ("POST", r"^/api/v1/communities/([A-Za-z0-9_-]+)/members\Z", lambda c, u, m, b, q, t: service.add_community_member(c, u["id"], m.group(1), b), True, None),
    ("PATCH", r"^/api/v1/communities/([A-Za-z0-9_-]+)\Z", lambda c, u, m, b, q, t: service.update_community_branding(c, u["id"], m.group(1), b), True, None),
    ("PATCH", r"^/api/v1/communities/([A-Za-z0-9_-]+)/theme\Z", lambda c, u, m, b, q, t: service.set_community_profile_theme(c, u["id"], m.group(1), b), True, None),
    ("POST", r"^/api/v1/communities/([A-Za-z0-9_-]+)/fixtures/([A-Za-z0-9_-]+)/ratings/request\Z", lambda c, u, m, b, q, t: service.request_matchday_ratings(c, u["id"], m.group(1), m.group(2)), True, None),
    ("GET", r"^/api/v1/communities/([A-Za-z0-9_-]+)/fixtures/([A-Za-z0-9_-]+)/ratings\Z", lambda c, u, m, b, q, t: service.get_matchday_ratings(c, u["id"], m.group(1), m.group(2)), True, None),
    ("POST", r"^/api/v1/communities/([A-Za-z0-9_-]+)/fixtures/([A-Za-z0-9_-]+)/ratings\Z", lambda c, u, m, b, q, t: service.submit_matchday_ratings(c, u["id"], m.group(1), m.group(2), b), True, None),
    ("DELETE", r"^/api/v1/communities/([A-Za-z0-9_-]+)/members/([A-Za-z0-9_-]+)\Z", lambda c, u, m, b, q, t: service.remove_community_member(c, u["id"], m.group(1), m.group(2)), True, None),
    ("POST", r"^/api/v1/communities/([A-Za-z0-9_-]+)/invites\Z", lambda c, u, m, b, q, t: service.create_community_invite(c, u["id"], m.group(1)), True, None),
    ("POST", r"^/api/v1/community-invites/accept\Z", lambda c, u, m, b, q, t: service.accept_community_invite(c, u["id"], b), True, None),
    ("GET", r"^/api/v1/communities/([A-Za-z0-9_-]+)/deletion-request\Z", lambda c, u, m, b, q, t: service.get_community_deletion_request(c, u["id"], m.group(1)), True, None),
    ("POST", r"^/api/v1/communities/([A-Za-z0-9_-]+)/deletion-requests\Z", lambda c, u, m, b, q, t: service.request_community_deletion(c, u["id"], m.group(1)), True, None),
    ("POST", r"^/api/v1/communities/([A-Za-z0-9_-]+)/deletion-requests/([A-Za-z0-9_-]+)/approve\Z", lambda c, u, m, b, q, t: service.approve_community_deletion(c, u["id"], m.group(1), m.group(2)), True, None),
    ("GET", r"^/api/v1/admin/community-deletions\Z", lambda c, u, m, b, q, t: service.get_super_admin_deletion_panel(c, u["id"]), True, None),
    ("PATCH", r"^/api/v1/admin/community-deletion-settings\Z", lambda c, u, m, b, q, t: service.set_community_deletion_timeout(c, u["id"], b), True, None),
    ("PATCH", r"^/api/v1/admin/poll-retention-settings\Z", lambda c, u, m, b, q, t: service.set_global_poll_retention(c, u["id"], b), True, None),
    ("PATCH", r"^/api/v1/admin/app-theme\Z", lambda c, u, m, b, q, t: service.set_global_app_theme(c, u["id"], b), True, None),
    ("POST", r"^/api/v1/admin/community-deletions/([A-Za-z0-9_-]+)/decision\Z", lambda c, u, m, b, q, t: service.decide_community_deletion(c, u["id"], m.group(1), b), True, None),
    ("PATCH", r"^/api/v1/communities/([A-Za-z0-9_-]+)/members/([A-Za-z0-9_-]+)\Z", lambda c, u, m, b, q, t: service.update_community_member(c, u["id"], m.group(1), m.group(2), b), True, None),
    ("POST", r"^/api/v1/communities/([A-Za-z0-9_-]+)/join\Z", lambda c, u, m, b, q, t: service.join_community(c, u["id"], m.group(1)), True, None),
    ("GET", r"^/api/v1/communities/([A-Za-z0-9_-]+)/messages\Z", lambda c, u, m, b, q, t: service.list_community_messages(c, u["id"], m.group(1)), True, None),
    ("POST", r"^/api/v1/communities/([A-Za-z0-9_-]+)/messages\Z", lambda c, u, m, b, q, t: service.create_community_message(c, u["id"], m.group(1), b), True, None),
    ("PATCH", r"^/api/v1/communities/([A-Za-z0-9_-]+)/messages/([A-Za-z0-9_-]+)\Z", lambda c, u, m, b, q, t: service.update_community_message(c, u["id"], m.group(1), m.group(2), b), True, None),
    ("DELETE", r"^/api/v1/communities/([A-Za-z0-9_-]+)/messages/([A-Za-z0-9_-]+)\Z", lambda c, u, m, b, q, t: service.delete_community_message(c, u["id"], m.group(1), m.group(2)), True, None),
    ("GET", r"^/api/v1/team\Z", lambda c, u, m, b, q, t: service.get_team(c, u["id"]), True, None),
    ("POST", r"^/api/v1/teams\Z", lambda c, u, m, b, q, t: service.create_team(c, u["id"], b), True, None),
    ("PATCH", r"^/api/v1/teams/([A-Za-z0-9_-]+)\Z", lambda c, u, m, b, q, t: service.update_team(c, u["id"], m.group(1), b), True, None),
    ("GET", r"^/api/v1/players\Z", lambda c, u, m, b, q, t: service.list_players(c, u["id"]), True, None),
    ("POST", r"^/api/v1/players\Z", lambda c, u, m, b, q, t: service.create_player(c, u["id"], b), True, None),
    ("GET", r"^/api/v1/players/([A-Za-z0-9_-]+)\Z", lambda c, u, m, b, q, t: service.get_player(c, u["id"], m.group(1)), True, None),
    ("PATCH", r"^/api/v1/players/([A-Za-z0-9_-]+)\Z", lambda c, u, m, b, q, t: service.update_player(c, u["id"], m.group(1), b), True, None),
    ("DELETE", r"^/api/v1/players/([A-Za-z0-9_-]+)\Z", lambda c, u, m, b, q, t: service.delete_player(c, u["id"], m.group(1)), True, None),
    ("POST", r"^/api/v1/players/([A-Za-z0-9_-]+)/ratings\Z", lambda c, u, m, b, q, t: service.rate_player(c, u["id"], m.group(1), b), True, None),
    ("GET", r"^/api/v1/plans\Z", lambda c, u, m, b, q, t: service.list_plans(c, u["id"]), True, None),
    ("POST", r"^/api/v1/plans\Z", lambda c, u, m, b, q, t: service.create_plan(c, u["id"], b), True, None),
    ("GET", r"^/api/v1/plans/([A-Za-z0-9_-]+)\Z", lambda c, u, m, b, q, t: service.get_plan(c, m.group(1), u["id"]), True, None),
    ("PATCH", r"^/api/v1/plans/([A-Za-z0-9_-]+)\Z", lambda c, u, m, b, q, t: service.update_plan(c, u["id"], m.group(1), b), True, None),
    ("PATCH", r"^/api/v1/plans/([A-Za-z0-9_-]+)/checklist/([A-Za-z0-9_-]+)\Z", lambda c, u, m, b, q, t: service.toggle_checklist(c, u["id"], m.group(1), m.group(2), b), True, None),
    ("GET", r"^/api/v1/notifications\Z", lambda c, u, m, b, q, t: service.list_notifications(c, u["id"]), True, None),
    ("POST", r"^/api/v1/notifications/read\Z", lambda c, u, m, b, q, t: service.mark_notifications(c, u["id"], b), True, None),
    ("GET", r"^/api/v1/pickup/teams\Z", lambda c, u, m, b, q, t: service.pickup_teams(
        c, u["id"],
        _bool((q.get("include_doubtful") or ["false"])[0]),
        _bool((q.get("position_aware") or ["true"])[0], True),
        _int((q.get("seed") or ["0"])[0], 0, 0, 99999),
    ), True, None),
    ("GET", r"^/api/v1/calendar\Z", lambda c, u, m, b, q, t: service.list_calendar(c, u["id"], (q.get("community_id") or [""])[0], *calendar_range(q)), True, None),
    ("POST", r"^/api/v1/calendar/events\Z", lambda c, u, m, b, q, t: service.create_calendar_event(c, u["id"], b), True, None),
    ("POST", r"^/api/v1/duties\Z", lambda c, u, m, b, q, t: service.create_duty(c, u, b), True, None),
    ("POST", r"^/api/v1/duties/([A-Za-z0-9_-]+)/claim\Z", lambda c, u, m, b, q, t: service.claim_duty(c, u, m.group(1)), True, None),
    ("DELETE", r"^/api/v1/duties/([A-Za-z0-9_-]+)/claim\Z", lambda c, u, m, b, q, t: service.release_duty(c, u, m.group(1)), True, None),
    ("DELETE", r"^/api/v1/duties/([A-Za-z0-9_-]+)\Z", lambda c, u, m, b, q, t: service.delete_duty(c, u, m.group(1)), True, None),
    ("GET", r"^/api/v1/schedule\Z", lambda c, u, m, b, q, t: service.get_schedule(c, u["id"], (q.get("community_id") or [""])[0]), True, None),
]

COMPILED_ROUTES = [
    (method, re.compile(pattern), handler, auth_required, roles)
    for method, pattern, handler, auth_required, roles in ROUTES
]


class TouchlineHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "Touchline"
    sys_version = ""
    # Close connections that go quiet, so idle or half-sent requests cannot pile up.
    timeout = 10

    def version_string(self):
        return "Touchline"

    def log_message(self, fmt, *args):
        if getattr(self.server, "quiet", False):
            return
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    # ---------- low-level responses ----------

    def _cors_headers(self):
        origin = self.headers.get("Origin")
        if origin:
            origin_host = urlparse(origin).netloc
            if origin not in config.CORS_ORIGINS and origin_host != self.headers.get("Host"):
                return None
        headers = {}
        if origin:
            headers["Access-Control-Allow-Origin"] = origin
            headers["Vary"] = "Origin"
        return headers

    def _send(self, status, body, content_type, extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        response_headers = {
            **SECURITY_HEADERS,
            "Content-Type": content_type,
            "Content-Length": str(len(body)),
        }
        if extra:
            response_headers.update(extra)
        self.send_response(status)
        for key, value in response_headers.items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def _json(self, status, payload, extra=None):
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if extra:
            headers.update(extra)
        self.send_response(status)
        for key, value in {**SECURITY_HEADERS, **headers, "Content-Length": str(len(body))}.items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def _ok(self, data, status=200):
        self._json(status, {"ok": True, "data": data}, self._cors_headers() or {})

    def _error(self, error):
        payload = {
            "ok": False,
            "error": {
                "code": error.code,
                "message": error.message,
                "fields": error.fields,
            },
        }
        extra = self._cors_headers() or {}
        if error.status == 401:
            extra["WWW-Authenticate"] = "Bearer"
        if error.status == 429 and error.fields.get("retryAfter"):
            extra["Retry-After"] = str(error.fields["retryAfter"])
        self._json(error.status, payload, extra)

    # ---------- request helpers ----------

    def _read_body(self):
        length_text = self.headers.get("Content-Length")
        if not length_text:
            return {}
        try:
            length = int(length_text)
        except ValueError:
            raise ApiError(400, "invalid_request", "Invalid Content-Length.")
        if length > config.MAX_BODY_BYTES:
            raise ApiError(413, "payload_too_large", "Request body is too large.")
        if length < 0:
            raise ApiError(400, "invalid_request", "Invalid Content-Length.")
        if length == 0:
            return {}
        content_type = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if content_type != "application/json":
            raise ApiError(415, "unsupported_media_type", "Use application/json for this request.")
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError):
            # RecursionError: deeply nested input must be refused, not crash the handler.
            raise ApiError(400, "invalid_json", "Request body must be valid JSON.")
        if not isinstance(payload, dict):
            raise ApiError(400, "invalid_body", "Request body must be a JSON object.")
        return payload

    def _client_ip(self):
        if config.TRUST_PROXY:
            forwarded = self.headers.get("X-Forwarded-For", "")
            if forwarded:
                return forwarded.split(",")[-1].strip()
        return self.client_address[0]

    def _token(self):
        header = self.headers.get("Authorization", "")
        if not header.lower().startswith("bearer "):
            return None
        return header.split(" ", 1)[1].strip()

    def _api_key(self):
        value = (self.headers.get("X-API-Key") or "").strip()
        return value if value.startswith("tl_live_") and len(value) <= 256 else None

    # ---------- routing ----------

    def do_GET(self):
        self._handle("GET")

    def do_HEAD(self):
        self._handle("HEAD")

    def do_POST(self):
        self._handle("POST")

    def do_PATCH(self):
        self._handle("PATCH")

    def do_DELETE(self):
        self._handle("DELETE")

    def do_OPTIONS(self):
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/v1"):
            self._send(405, "Method not allowed", "text/plain; charset=utf-8", {"Allow": "GET, HEAD"})
            return
        cors = self._cors_headers()
        if cors is None:
            self._json(403, {"ok": False, "error": {"code": "cors_forbidden", "message": "Origin is not allowed.", "fields": {}}})
            return
        self._send(
            204,
            "",
            "text/plain; charset=utf-8",
            {
                **cors,
                "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, HEAD, OPTIONS",
                "Access-Control-Allow-Headers": "Authorization, Content-Type, X-API-Key",
                "Access-Control-Max-Age": "600",
            },
        )

    def _handle(self, method):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/v1"):
            self._handle_api(method, parsed)
        else:
            if method not in {"GET", "HEAD"}:
                self._send(405, "Method not allowed", "text/plain; charset=utf-8", {"Allow": "GET, HEAD"})
                return
            self._serve_static(parsed.path)

    def _throttle_precheck(self, method, path, body):
        """Return throttle bookkeeping for auth routes; raise 429 when locked out."""
        if method != "POST" or path not in {"/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/admin", "/api/v1/auth/2fa/login", "/api/v1/auth/password/forgot", "/api/v1/auth/password/reset", "/api/v1/auth/verification/resend", "/api/v1/auth/google/start", "/api/v1/auth/google/callback"}:
            return None
        ip = self._client_ip()
        if path in {"/api/v1/auth/google/start", "/api/v1/auth/google/callback"}:
            keys = [(f"google-oauth-ip:{ip}", config.AUTH_EMAIL_LIMIT_PER_IP, config.AUTH_EMAIL_WINDOW_SECONDS)]
            kind = "email-action"
        elif path in {"/api/v1/auth/login", "/api/v1/auth/admin", "/api/v1/auth/2fa/login"}:
            email = ""
            if isinstance(body, dict) and isinstance(body.get("email"), str):
                email = body["email"].strip().lower()[:254]
            keys = [
                (f"login-ip:{ip}", config.LOGIN_FAIL_LIMIT_PER_IP, config.LOGIN_WINDOW_SECONDS),
            ]
            if email:
                keys.append((f"login-email:{email}", config.LOGIN_FAIL_LIMIT_PER_EMAIL, config.LOGIN_WINDOW_SECONDS))
            kind = "login"
        elif path in {"/api/v1/auth/password/forgot", "/api/v1/auth/password/reset", "/api/v1/auth/verification/resend"}:
            ip = self._client_ip()
            keys = [(f"email-action-ip:{ip}", config.AUTH_EMAIL_LIMIT_PER_IP, config.AUTH_EMAIL_WINDOW_SECONDS)]
            kind = "email-action"
        else:
            keys = [(f"register-ip:{ip}", config.REGISTER_LIMIT_PER_IP, config.REGISTER_WINDOW_SECONDS)]
            kind = "register"
        for key, limit, window in keys:
            wait = limiter.retry_after(key, limit, window)
            if wait:
                raise ApiError(
                    429,
                    "rate_limited",
                    "Too many attempts. Try again later.",
                    {"retryAfter": wait},
                )
        if kind == "register":
            # every registration attempt counts, successful or not
            for key, _limit, window in keys:
                limiter.record(key, window)
        elif kind == "email-action":
            for key, _limit, window in keys:
                limiter.record(key, window)
        return {"kind": kind, "keys": keys}

    def _throttle_record_failure(self, throttle, error):
        if throttle and throttle["kind"] == "login" and error.status in {400, 401}:
            for key, _limit, window in throttle["keys"]:
                limiter.record(key, window)

    def _throttle_record_success(self, throttle):
        if throttle and throttle["kind"] == "login":
            for key, _limit, _window in throttle["keys"]:
                if key.startswith("login-email:"):
                    limiter.clear(key)

    def _handle_api(self, method, parsed):
        cors = self._cors_headers()
        if cors is None:
            self._json(
                403,
                {"ok": False, "error": {"code": "cors_forbidden", "message": "Origin is not allowed.", "fields": {}}},
            )
            return
        path = parsed.path.rstrip("/") or "/"
        try:
            if method == "GET" and path == "/api/v1/health":
                with db.connect() as connection:
                    row = connection.execute(
                        "SELECT value FROM meta WHERE key = 'schema_version'"
                    ).fetchone()
                    connection.execute("SELECT 1").fetchone()
                self._ok(
                    {
                        "status": "ok",
                        "database": "ok",
                        "schemaVersion": row["value"] if row else "unknown",
                        "time": iso(),
                    }
                )
                return

            route = None
            match = None
            for route_method, pattern, handler, auth_required, roles in COMPILED_ROUTES:
                if route_method == method and pattern.match(path):
                    route = (handler, auth_required, roles)
                    match = pattern.match(path)
                    break
            if route is None:
                for route_method, pattern, handler, auth_required, roles in COMPILED_ROUTES:
                    if pattern.match(path):
                        raise ApiError(405, "method_not_allowed", "Method not allowed for this endpoint.")
                raise ApiError(404, "not_found", "API endpoint not found.")

            handler, auth_required, roles = route
            body = self._read_body() if method in {"POST", "PATCH"} else {}
            throttle_keys = self._throttle_precheck(method, path, body)
            token = self._token()
            api_key = self._api_key()
            token_hash = hash_token(token) if token else None
            user = None
            with db.connect() as connection:
                if auth_required:
                    user = service.user_from_token(connection, token)
                    session_user = user
                    key_auth_allowed = not path.startswith(("/api/v1/auth/", "/api/v1/me/")) and path != "/api/v1/me"
                    if user is None and api_key and key_auth_allowed:
                        user = service.user_from_api_key(connection, api_key)
                    if path.startswith("/api/v1/me/api-key") and session_user is None:
                        raise ApiError(401, "session_required", "Sign in with your account session to manage API keys.")
                    if user is None:
                        raise ApiError(401, "unauthorized", "A valid session Bearer token or approved API key is required.")
                    if roles and user["role"] not in roles:
                        raise ApiError(403, "forbidden", "Your account cannot perform that action.")
                try:
                    data = handler(
                        connection,
                        user,
                        match,
                        body,
                        parse_qs(parsed.query),
                        token_hash,
                    )
                except ApiError as error:
                    self._throttle_record_failure(throttle_keys, error)
                    raise
            self._throttle_record_success(throttle_keys)
            self._ok(data)
        except ApiError as error:
            self._error(error)
        except sqlite3.IntegrityError:
            self._error(ApiError(409, "conflict", "That change conflicts with existing data."))
        except Exception:
            traceback.print_exc()
            self._error(ApiError(500, "internal_error", "Something went wrong."))

    def _serve_static(self, path):
        raw_path = self.path.split("?", 1)[0]
        if (
            "\\" in raw_path
            or "\x00" in raw_path
            or "%00" in raw_path.lower()
            or any(
                segment in {"", ".", ".."} or segment.lower().startswith("%2e")
                for segment in raw_path.split("/")[1:]
                if segment.startswith(".") or segment in {".", ".."} or segment.lower().startswith("%2e")
            )
        ):
            self._send(403, "Forbidden", "text/plain; charset=utf-8")
            return

        try:
            pathname = unquote(path)
        except Exception:
            self._send(400, "Bad request", "text/plain; charset=utf-8")
            return
        if config.ADMIN_PATH and pathname == config.ADMIN_PATH:
            pathname = "/index.html"
        elif pathname.endswith("/"):
            pathname += "index.html"

        if (
            pathname in STATIC_BLOCKED_FILES
            or any(pathname.startswith(prefix) for prefix in STATIC_BLOCKED_PREFIXES)
            or any(
                segment.startswith(".") and segment not in {".", ".."}
                for segment in pathname.split("/")
            )
        ):
            self._send(404, "Not found", "text/plain; charset=utf-8")
            return

        file_path = Path(config.ROOT, pathname.lstrip("/")).resolve()
        try:
            file_path.relative_to(config.ROOT.resolve())
        except ValueError:
            self._send(403, "Forbidden", "text/plain; charset=utf-8")
            return
        if not file_path.is_file():
            self._send(404, "Not found", "text/plain; charset=utf-8")
            return

        mime = MIME.get(file_path.suffix.lower()) or mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        data = file_path.read_bytes()
        self._send(200, data, mime)


def create_server(host=None, port=None):
    host = host or config.HOST
    port = config.PORT if port is None else port
    server = ThreadingHTTPServer((host, port), TouchlineHandler)
    server.daemon_threads = True
    server.request_queue_size = 128
    server.socket.listen(128)
    return server


def run():
    db.init_db()
    server = create_server()
    def sweep_expired_deletions():
        while True:
            time.sleep(15)
            try:
                service.expire_community_deletions()
            except Exception:
                traceback.print_exc()

    threading.Thread(target=sweep_expired_deletions, name="community-deletion-expiry", daemon=True).start()
    def poll_scheduler():
        while True:
            time.sleep(1)
            try:
                service.process_due_polls_once()
            except Exception:
                traceback.print_exc()

    threading.Thread(target=poll_scheduler, name="poll-close-and-feedback-scheduler", daemon=True).start()
    print(f"Touchline API + web app running at http://{config.HOST}:{config.PORT}")
    print(f"OpenAPI: http://{config.HOST}:{config.PORT}/api/v1/openapi.json")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
