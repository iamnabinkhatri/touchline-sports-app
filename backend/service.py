import json
import base64
import binascii
import hashlib
import hmac
import re
import secrets
import sqlite3
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone, time as datetime_time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import config, db
from .mailer import MailDeliveryError, send_email
from .balance import split_squad
from .errors import ApiError
from .ratelimit import limiter
from .security import (
    hash_password,
    hash_token,
    decrypt_totp_secret,
    encrypt_totp_secret,
    initials,
    iso,
    new_id,
    new_token,
    new_totp_secret,
    matching_totp_step,
    totp_code,
    totp_uri,
    parse_iso,
    session_expiry,
    slugify,
    utc_now,
    verify_password,
)
from .serializers import (
    DUTY_KINDS,
    bootstrap,
    duty_dict,
    community_dict,
    notification_dict,
    plan_dict,
    player_dict,
    poll_dict,
    post_dict,
    team_dict,
    user_public,
)
from .validation import (
    boolean,
    email,
    choice,
    email as email_field,
    integer,
    iso_date,
    number,
    password as password_field,
    require_object,
    text,
    text_list,
    valid_id,
)

POSITIONS = {"GK", "RB", "CB", "LB", "LWB", "RWB", "DM", "CM", "AM", "LM", "RM", "RW", "LW", "ST"}
STATUSES = {"available", "doubtful", "out"}
FEET = {"Right", "Left", "Both"}
FORMATIONS = {"4-3-3", "4-2-3-1", "3-5-2"}
SPORTS = {"Soccer", "Basketball", "Running", "Volleyball", "Tennis", "Baseball"}
TAGS = {"club", "matchday", "tactics"}
POLL_CATEGORIES = {"Lineup", "Tactics", "Club", "Pickup", "Competition"}
ACCENTS = ["forest", "lime", "coral", "sky", "violet", "gold", "sage", "red"]


def group_for_position(pos):
    if pos == "GK":
        return "GK"
    if pos in {"RB", "CB", "LB", "LWB", "RWB"}:
        return "DEF"
    if pos in {"DM", "CM", "AM", "LM", "RM"}:
        return "MID"
    return "FWD"


@contextmanager
def transaction(connection):
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise


def _user(connection, user_id):
    row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise ApiError(401, "unauthorized", "Your session is no longer valid.")
    return row


def _team(connection):
    row = connection.execute("SELECT * FROM teams ORDER BY rowid ASC LIMIT 1").fetchone()
    if row is None:
        raise ApiError(404, "not_found", "No team exists.")
    return row


def _is_platform_admin(connection, user_id):
    return _user(connection, user_id)["role"] == "admin"


def _community_role(connection, community_id, user_id):
    row = connection.execute("SELECT role FROM community_members WHERE community_id=? AND user_id=?", (community_id, user_id)).fetchone()
    return row["role"] if row else None


def _require_community_admin(connection, community_id, user_id):
    if _is_platform_admin(connection, user_id):
        return
    if _community_role(connection, community_id, user_id) != "Admin":
        raise ApiError(403, "forbidden", "A community admin must perform this action.")


def _team_for_user(connection, user_id, team_id=None, *, manage=False):
    if team_id:
        row = connection.execute("SELECT * FROM teams WHERE id=?", (team_id,)).fetchone()
    else:
        row = connection.execute("SELECT t.* FROM teams t JOIN community_members m ON m.community_id=t.community_id WHERE m.user_id=? ORDER BY t.rowid LIMIT 1", (user_id,)).fetchone()
        if _is_platform_admin(connection, user_id) and row is None:
            row = connection.execute("SELECT * FROM teams ORDER BY rowid LIMIT 1").fetchone()
    if row is None:
        raise ApiError(404, "not_found", "That team does not exist.")
    if row["community_id"] is None:
        if not _is_platform_admin(connection, user_id):
            raise ApiError(403, "forbidden", "This team is not assigned to a community.")
    elif manage:
        _require_community_admin(connection, row["community_id"], user_id)
    else:
        _ensure_member(connection, row["community_id"], user_id)
    return row


def _plan(connection, plan_id):
    row = connection.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
    if row is None:
        raise ApiError(404, "not_found", "That game plan does not exist.")
    return row


def _community(connection, community_id):
    row = connection.execute(
        "SELECT * FROM communities WHERE id = ?", (community_id,)
    ).fetchone()
    if row is None:
        raise ApiError(404, "not_found", "That community does not exist.")
    return row


def _create_notification(connection, user_id, *, icon, title, body, route, created_at=None,
                         community_id=None, post_id=None, kind="", source_key=None):
    created_at = created_at or iso()
    connection.execute(
        """INSERT OR IGNORE INTO notifications
        (id,user_id,icon,title,body,time_label,unread,route,created_at,community_id,post_id,kind,source_key)
        VALUES(?,?,?,?,?,?,1,?,?,?,?,?,?)""",
        (new_id("notification"), user_id, icon, title, body, "Just now", route, created_at,
         community_id, post_id, kind, source_key),
    )


def _post(connection, post_id):
    row = connection.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if row is None:
        raise ApiError(404, "not_found", "That post does not exist.")
    return row


def _poll(connection, poll_id):
    row = connection.execute("SELECT * FROM polls WHERE id = ?", (poll_id,)).fetchone()
    if row is None:
        raise ApiError(404, "not_found", "That poll does not exist.")
    return row


def _player(connection, player_id):
    row = connection.execute("SELECT * FROM players WHERE id = ?", (player_id,)).fetchone()
    if row is None:
        raise ApiError(404, "not_found", "That player does not exist.")
    return row


def _ensure_member(connection, community_id, user_id):
    membership = connection.execute(
        "SELECT 1 FROM community_members WHERE community_id = ? AND user_id = ?",
        (community_id, user_id),
    ).fetchone()
    if membership is None:
        raise ApiError(403, "forbidden", "Join this community before posting there.")


def _player_dict(connection, row, user_id):
    aggregate = connection.execute(
        "SELECT SUM(value) AS total, COUNT(*) AS count FROM player_ratings WHERE player_id = ?",
        (row["id"],),
    ).fetchone()
    own = connection.execute(
        "SELECT value FROM player_ratings WHERE player_id = ? AND user_id = ?",
        (row["id"], user_id),
    ).fetchone()
    return player_dict(row, aggregate, own["value"] if own else None, user_id)


# ---------- Authentication ----------


def create_session(connection, user_id):
    token = new_token()
    connection.execute(
        "INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (hash_token(token), user_id, iso(), session_expiry()),
    )
    connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (iso(),))
    return token


_DUMMY_HASH = {}


def _dummy_hash():
    iterations = config.PBKDF2_ITERATIONS
    if _DUMMY_HASH.get("iterations") != iterations:
        _DUMMY_HASH["iterations"] = iterations
        _DUMMY_HASH["hash"] = hash_password("not-a-real-password")
    return _DUMMY_HASH["hash"]


def _new_auth_token(connection, user_id, purpose, minutes):
    token = new_token()
    connection.execute("DELETE FROM auth_tokens WHERE user_id = ? AND purpose = ?", (user_id, purpose))
    connection.execute("INSERT INTO auth_tokens (token_hash,user_id,purpose,expires_at,created_at) VALUES (?,?,?,?,?)",
                       (hash_token(token), user_id, purpose, iso(utc_now() + timedelta(minutes=minutes)), iso()))
    return token


def _send_token_email(email, purpose, token):
    query = {"verify_email": "verify_token", "password_reset": "reset_token"}[purpose]
    subject = "Verify your Touchline email" if purpose == "verify_email" else "Reset your Touchline password"
    send_email(email, subject, f"Complete this request: {config.APP_BASE_URL}/?{query}={token}\nIf you did not request this, ignore this email.")


def login(connection, data, admin_only=False):
    require_object(data)
    email_value = email_field(data, "email")
    password_value = text(data, "password", required=True, minimum=1, maximum=128, label="Password")
    user = connection.execute(
        "SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email_value,)
    ).fetchone()
    if user is None:
        # burn comparable CPU time so response timing does not reveal unknown emails
        verify_password(password_value, _dummy_hash())
        raise ApiError(401, "invalid_credentials", "Email or password is incorrect.")
    if not verify_password(password_value, user["password_hash"]):
        raise ApiError(401, "invalid_credentials", "Email or password is incorrect.")
    if admin_only and user["role"] != "admin":
        raise ApiError(403, "admin_only", "This sign-in is for administrators only.")
    if not user["email_verified"]:
        raise ApiError(403, "email_not_verified", "Verify your email before signing in.")
    if user["two_factor_enabled"]:
        challenge = _new_auth_token(connection, user["id"], "login_2fa", 5)
        return {"twoFactorRequired": True, "challengeToken": challenge}
    token = create_session(connection, user["id"])
    return {"token": token, "user": user_public(user)}


def admin_login(connection, data):
    return login(connection, data, admin_only=True)


def register(connection, data):
    require_object(data)
    name = text(data, "name", minimum=2, maximum=50, label="Name")
    email_value = email_field(data, "email")
    password_value = password_field(data, "password")
    invite_token = data.get("player_invite")
    invite = None
    if invite_token:
        invite_token = text(data, "player_invite", minimum=20, maximum=256, label="Player invitation")
        invite = connection.execute("SELECT * FROM player_invites WHERE token_hash=? AND expires_at>?", (hash_token(invite_token), iso())).fetchone()
        if not invite or invite["email"].casefold() != email_value.casefold():
            raise ApiError(400, "invalid_player_invite", "This player invitation is invalid, expired, or belongs to another email address.")
    existing = connection.execute(
        "SELECT 1 FROM users WHERE email = ? COLLATE NOCASE", (email_value,)
    ).fetchone()
    if existing:
        raise ApiError(409, "email_exists", "An account already exists for that email.")
    user_id = new_id("user")
    now = iso()
    password_hash = hash_password(password_value)
    try:
        with transaction(connection):
            connection.execute(
                """
                INSERT INTO users
                (id, name, email, password_hash, role, club_role, avatar_tone, member_since, club_points, created_at, email_verified)
                VALUES (?, ?, ?, ?, 'member', 'Member', 'sage', ?, 0, ?, 0)
                """,
                (user_id, name, email_value, password_hash, str(utc_now().year), now),
            )
            if invite:
                player_data = json.loads(invite["player_data_json"])
                team = connection.execute("SELECT * FROM teams WHERE id=?", (invite["team_id"],)).fetchone()
                if not team:
                    raise ApiError(404, "team_not_found", "The invited team no longer exists.")
                community_id = team["community_id"]
                if community_id:
                    connection.execute("INSERT OR IGNORE INTO community_members(community_id,user_id,role,joined_at) VALUES(?,?,'Member',?)", (community_id, user_id, now))
                existing_player_id = player_data.get("existing_player_id")
                if existing_player_id:
                    player = connection.execute("SELECT id,team_id,user_id FROM players WHERE id=?", (existing_player_id,)).fetchone()
                    if not player or player["team_id"] != team["id"] or player["user_id"]:
                        raise ApiError(409, "player_invite_expired", "This player profile is no longer available to link.")
                    if connection.execute("SELECT 1 FROM players WHERE team_id=? AND user_id=?", (team["id"], user_id)).fetchone():
                        raise ApiError(409, "player_profile_exists", "Your account already has a player profile in this squad.")
                    connection.execute("UPDATE players SET user_id=?,name=? WHERE id=?", (user_id, name, existing_player_id))
                else:
                    _insert_player_record(connection, team, player_data, user_id)
            token = _new_auth_token(connection, user_id, "verify_email", 60 * 24)
    except sqlite3.IntegrityError:
        raise ApiError(409, "email_exists", "An account already exists for that email.")
    user = _user(connection, user_id)
    try:
        _send_token_email(email_value, "verify_email", token)
    except MailDeliveryError as error:
        connection.execute("DELETE FROM auth_tokens WHERE user_id = ?", (user_id,))
        connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
        message = "Email delivery is not configured. Add SMTP settings and restart the server." if str(error) == "not_configured" else "The email provider rejected or could not deliver this message. Check SMTP settings and server logs."
        raise ApiError(503, "email_unavailable", message)
    if invite:
        connection.execute("DELETE FROM player_invites WHERE token_hash=?", (invite["token_hash"],))
    return {"verificationRequired": True, "email": email_value, "playerAdded": bool(invite)}


def verify_email(connection, data):
    require_object(data)
    token = text(data, "token", required=True, minimum=20, maximum=256, label="Verification token")
    row = connection.execute("SELECT * FROM auth_tokens WHERE token_hash=? AND purpose='verify_email' AND expires_at>?", (hash_token(token), iso())).fetchone()
    if row is None:
        raise ApiError(400, "invalid_token", "This verification link is invalid or expired.")
    with transaction(connection):
        connection.execute("UPDATE users SET email_verified=1 WHERE id=?", (row["user_id"],))
        connection.execute("DELETE FROM auth_tokens WHERE token_hash=?", (row["token_hash"],))
    return {"verified": True}


def resend_verification(connection, data):
    require_object(data); email_value = email_field(data, "email")
    user = connection.execute("SELECT * FROM users WHERE email=? COLLATE NOCASE", (email_value,)).fetchone()
    if user and not user["email_verified"]:
        token = _new_auth_token(connection, user["id"], "verify_email", 1440)
        try: _send_token_email(user["email"], "verify_email", token)
        except MailDeliveryError: pass
    return {"sent": True}


def forgot_password(connection, data):
    require_object(data); email_value = email_field(data, "email")
    user = connection.execute("SELECT * FROM users WHERE email=? COLLATE NOCASE", (email_value,)).fetchone()
    if user and user["email_verified"]:
        token = _new_auth_token(connection, user["id"], "password_reset", 30)
        try: _send_token_email(user["email"], "password_reset", token)
        except MailDeliveryError: pass
    return {"sent": True}


def reset_password(connection, data):
    require_object(data); token = text(data,"token",required=True,minimum=20,maximum=256,label="Reset token"); password_value=password_field(data,"password")
    row=connection.execute("SELECT * FROM auth_tokens WHERE token_hash=? AND purpose='password_reset' AND expires_at>?",(hash_token(token),iso())).fetchone()
    if not row: raise ApiError(400,"invalid_token","This password reset link is invalid or expired.")
    with transaction(connection):
        connection.execute("UPDATE users SET password_hash=? WHERE id=?",(hash_password(password_value),row["user_id"]))
        connection.execute("DELETE FROM sessions WHERE user_id=?",(row["user_id"],)); connection.execute("DELETE FROM auth_tokens WHERE user_id=?",(row["user_id"],))
    return {"changed":True}


def change_password(connection, user_id, token_hash, data):
    require_object(data); current=text(data,"current_password",required=True,minimum=1,maximum=128,label="Current password"); new=password_field(data,"new_password")
    user=_user(connection,user_id)
    if not verify_password(current,user["password_hash"]): raise ApiError(401,"invalid_credentials","Current password is incorrect.")
    with transaction(connection):
        connection.execute("UPDATE users SET password_hash=? WHERE id=?",(hash_password(new),user_id))
        connection.execute("DELETE FROM sessions WHERE user_id=? AND token_hash<>?",(user_id,token_hash))
        connection.execute("DELETE FROM auth_tokens WHERE user_id=?",(user_id,))
    return {"changed":True}


def two_factor_setup(connection,user_id):
    secret=new_totp_secret()
    try:
        encrypted = encrypt_totp_secret(secret)
    except (ValueError, TypeError):
        raise ApiError(503, "two_factor_unavailable", "Two-factor setup is not configured on this server.")
    connection.execute("UPDATE users SET two_factor_pending_secret=? WHERE id=?",(encrypted,user_id))
    return {"secret":secret,"otpauthUri":totp_uri(secret,_user(connection,user_id)["email"])}


def two_factor_enable(connection,user_id,data):
    require_object(data); code=text(data,"code",required=True,minimum=6,maximum=6,label="Authenticator code"); user=_user(connection,user_id)
    if not user["two_factor_pending_secret"]: raise ApiError(400,"setup_required","Start two-factor setup first.")
    secret=decrypt_totp_secret(user["two_factor_pending_secret"]); step=matching_totp_step(secret,code)
    if step is None: raise ApiError(400,"invalid_two_factor_code","Authenticator code is incorrect.")
    codes=[secrets.token_urlsafe(9) for _ in range(10)]
    with transaction(connection):
        connection.execute("UPDATE users SET two_factor_enabled=1,two_factor_secret=two_factor_pending_secret,two_factor_pending_secret=NULL,two_factor_last_step=? WHERE id=?",(step,user_id))
        connection.execute("DELETE FROM recovery_codes WHERE user_id=?",(user_id,))
        connection.executemany("INSERT INTO recovery_codes(user_id,code_hash,created_at) VALUES(?,?,?)",[(user_id,hash_token(c),iso()) for c in codes])
    return {"enabled":True,"recoveryCodes":codes}


def two_factor_login(connection,data):
    require_object(data); challenge=text(data,"challengeToken",required=True,minimum=20,maximum=256,label="Challenge token"); code=text(data,"code",required=True,minimum=6,maximum=64,label="Authenticator code")
    row=connection.execute("SELECT a.*,u.* FROM auth_tokens a JOIN users u ON u.id=a.user_id WHERE a.token_hash=? AND a.purpose='login_2fa' AND a.expires_at>?",(hash_token(challenge),iso())).fetchone()
    if not row: raise ApiError(400,"invalid_challenge","This sign-in challenge is invalid or expired.")
    recovery=connection.execute("SELECT code_hash FROM recovery_codes WHERE user_id=? AND code_hash=?",(row["user_id"],hash_token(code))).fetchone()
    step = None
    if recovery is None:
        secret = decrypt_totp_secret(row["two_factor_secret"])
        if secret is None:
            raise ApiError(503, "two_factor_unavailable", "Two-factor settings cannot be decrypted. Restore the configured encryption key.")
        step=matching_totp_step(secret,code)
        if step is not None and step<=row["two_factor_last_step"]: step=None
    if step is None and recovery is None: raise ApiError(401,"invalid_two_factor_code","Authenticator code is incorrect.")
    with transaction(connection):
        connection.execute("DELETE FROM auth_tokens WHERE token_hash=?",(hash_token(challenge),))
        if recovery: connection.execute("DELETE FROM recovery_codes WHERE user_id=? AND code_hash=?",(row["user_id"],recovery["code_hash"]))
        else: connection.execute("UPDATE users SET two_factor_last_step=? WHERE id=?",(step,row["user_id"]))
        token=create_session(connection,row["user_id"])
    return {"token":token,"user":user_public(_user(connection,row["user_id"]))}


def two_factor_disable(connection,user_id,data):
    require_object(data); password=text(data,"password",required=True,minimum=1,maximum=128,label="Password"); code=text(data,"code",required=True,minimum=6,maximum=64,label="Authenticator code"); user=_user(connection,user_id)
    if not verify_password(password,user["password_hash"]): raise ApiError(401,"invalid_credentials","Password is incorrect.")
    secret = decrypt_totp_secret(user["two_factor_secret"])
    if secret is None: raise ApiError(503,"two_factor_unavailable","Two-factor settings cannot be decrypted. Restore the configured encryption key.")
    step=matching_totp_step(secret,code)
    if step is None or step <= user["two_factor_last_step"]: raise ApiError(401,"invalid_two_factor_code","Authenticator code is incorrect.")
    with transaction(connection):
        connection.execute("UPDATE users SET two_factor_enabled=0,two_factor_secret=NULL,two_factor_pending_secret=NULL,two_factor_last_step=-1 WHERE id=?",(user_id,)); connection.execute("DELETE FROM recovery_codes WHERE user_id=?",(user_id,)); connection.execute("DELETE FROM auth_tokens WHERE user_id=? AND purpose='login_2fa'",(user_id,))
    return {"enabled":False}


def logout(connection, token_hash):
    connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))


def user_from_token(connection, token):
    if not token:
        return None
    row = connection.execute(
        """
        SELECT u.*
        FROM sessions s JOIN users u ON u.id = s.user_id
        WHERE s.token_hash = ? AND s.expires_at > ?
        """,
        (hash_token(token), iso()),
    ).fetchone()
    return row


def user_from_api_key(connection, api_key):
    if not isinstance(api_key, str) or not api_key.startswith("tl_live_") or len(api_key) > 256:
        return None
    row = connection.execute("""SELECT u.*,k.id AS api_key_id FROM api_keys k
        JOIN users u ON u.id=k.user_id WHERE k.key_hash=? AND k.revoked_at IS NULL""", (hash_token(api_key),)).fetchone()
    if row:
        connection.execute("UPDATE api_keys SET last_used_at=? WHERE id=?", (iso(), row["api_key_id"]))
    return row


def api_key_access_status(connection, user_id):
    request = connection.execute("SELECT * FROM api_key_requests WHERE user_id=? ORDER BY requested_at DESC LIMIT 1", (user_id,)).fetchone()
    active = connection.execute("SELECT id,key_prefix,created_at,last_used_at FROM api_keys WHERE user_id=? AND revoked_at IS NULL", (user_id,)).fetchone()
    can_claim = bool(request and request["status"] == "approved" and request["claimed_at"] is None and not active)
    return {
        "request": {"id": request["id"], "status": request["status"], "reason": request["reason"], "requestedAt": request["requested_at"], "decidedAt": request["decided_at"], "claimed": request["claimed_at"] is not None} if request else None,
        "activeKey": {"id": active["id"], "prefix": active["key_prefix"], "createdAt": active["created_at"], "lastUsedAt": active["last_used_at"]} if active else None,
        "canClaim": can_claim,
    }


def request_api_key(connection, user_id, data):
    require_object(data)
    reason = text(data, "reason", minimum=10, maximum=300, label="Reason")
    active = connection.execute("SELECT 1 FROM api_keys WHERE user_id=? AND revoked_at IS NULL", (user_id,)).fetchone()
    if active:
        raise ApiError(409, "api_key_active", "Revoke your active API key before requesting another one.")
    latest = connection.execute("SELECT * FROM api_key_requests WHERE user_id=? ORDER BY requested_at DESC LIMIT 1", (user_id,)).fetchone()
    if latest and latest["status"] == "pending":
        return api_key_access_status(connection, user_id)["request"]
    if latest and latest["status"] == "approved" and latest["claimed_at"] is None:
        return api_key_access_status(connection, user_id)["request"]
    request_id = new_id("apikeyreq")
    connection.execute("INSERT INTO api_key_requests(id,user_id,reason,status,requested_at) VALUES(?,?,?,'pending',?)", (request_id, user_id, reason, iso()))
    return api_key_access_status(connection, user_id)["request"]


def list_api_key_requests(connection, actor_id):
    if not _is_platform_admin(connection, actor_id):
        raise ApiError(403, "forbidden", "Only the super admin can review API key requests.")
    rows = connection.execute("""SELECT r.id,r.user_id,r.reason,r.requested_at,u.name,u.email
        FROM api_key_requests r JOIN users u ON u.id=r.user_id
        WHERE r.status='pending' ORDER BY r.requested_at ASC""").fetchall()
    return [{"id": row["id"], "userId": row["user_id"], "name": row["name"], "email": row["email"], "reason": row["reason"], "requestedAt": row["requested_at"]} for row in rows]


def decide_api_key_request(connection, actor_id, request_id, data):
    require_object(data)
    if not _is_platform_admin(connection, actor_id):
        raise ApiError(403, "forbidden", "Only the super admin can review API key requests.")
    request_id = valid_id(request_id, "request_id")
    decision = choice(data, "decision", {"approve", "deny"}, label="Decision")
    row = connection.execute("SELECT status FROM api_key_requests WHERE id=?", (request_id,)).fetchone()
    if not row or row["status"] != "pending":
        raise ApiError(404, "not_found", "Pending API key request not found.")
    status = "approved" if decision == "approve" else "denied"
    connection.execute("UPDATE api_key_requests SET status=?,decided_at=?,decided_by=? WHERE id=?", (status, iso(), actor_id, request_id))
    return {"id": request_id, "status": status}


def claim_api_key(connection, user_id):
    active = connection.execute("SELECT 1 FROM api_keys WHERE user_id=? AND revoked_at IS NULL", (user_id,)).fetchone()
    if active:
        raise ApiError(409, "api_key_already_claimed", "An active API key already exists. Revoke it before requesting another.")
    request = connection.execute("""SELECT id FROM api_key_requests WHERE user_id=? AND status='approved' AND claimed_at IS NULL
        ORDER BY requested_at DESC LIMIT 1""", (user_id,)).fetchone()
    if not request:
        raise ApiError(409, "api_key_not_approved", "A super admin must approve your API key request first.")
    secret = "tl_live_" + secrets.token_urlsafe(32)
    now = iso()
    with transaction(connection):
        key_id = new_id("apikey")
        connection.execute("INSERT INTO api_keys(id,request_id,user_id,key_hash,key_prefix,created_at) VALUES(?,?,?,?,?,?)", (key_id, request["id"], user_id, hash_token(secret), secret[:16], now))
        connection.execute("UPDATE api_key_requests SET claimed_at=? WHERE id=?", (now, request["id"]))
    return {"id": key_id, "apiKey": secret, "prefix": secret[:16], "createdAt": now}


def revoke_api_key(connection, user_id):
    cursor = connection.execute("UPDATE api_keys SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL", (iso(), user_id))
    return {"revoked": cursor.rowcount > 0}


# ---------- Reads ----------

def get_public_app_theme(connection):
    row = connection.execute("SELECT value FROM meta WHERE key='app_theme'").fetchone()
    return {"theme": row["value"] if row else "light"}


def google_login_config(connection=None):
    return {"enabled": bool(config.GOOGLE_CLIENT_ID and config.GOOGLE_CLIENT_SECRET)}


def google_login_start(connection, data):
    require_object(data)
    if not config.GOOGLE_CLIENT_ID or not config.GOOGLE_CLIENT_SECRET:
        raise ApiError(503, "google_signin_unavailable", "Google sign-in has not been configured yet.")
    player_invite = data.get("playerInvite")
    community_invite = data.get("communityInvite")
    if player_invite is not None:
        player_invite = text(data, "playerInvite", minimum=20, maximum=256, label="Player invitation")
    if community_invite is not None:
        community_invite = text(data, "communityInvite", minimum=20, maximum=256, label="Community invitation")
    state = new_token()
    nonce = new_token()
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode("ascii").rstrip("=")
    connection.execute("DELETE FROM google_login_states WHERE expires_at<=?", (iso(),))
    connection.execute(
        "INSERT INTO google_login_states(state_hash,nonce,code_verifier,player_invite,community_invite,expires_at,created_at) VALUES(?,?,?,?,?,?,?)",
        (hash_token(state), nonce, verifier, player_invite, community_invite, iso(utc_now() + timedelta(minutes=10)), iso()),
    )
    params = urllib.parse.urlencode({
        "client_id": config.GOOGLE_CLIENT_ID,
        "redirect_uri": config.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "prompt": "select_account",
    })
    return {"authorizationUrl": "https://accounts.google.com/o/oauth2/v2/auth?" + params}


def _exchange_google_code(code, code_verifier):
    payload = urllib.parse.urlencode({
        "code": code,
        "client_id": config.GOOGLE_CLIENT_ID,
        "client_secret": config.GOOGLE_CLIENT_SECRET,
        "redirect_uri": config.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
        "code_verifier": code_verifier,
    }).encode("ascii")
    request = urllib.request.Request(
        "https://oauth2.googleapis.com/token", data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        result = json.loads(response.read(65536).decode("utf-8"))
    token = result.get("id_token")
    if not isinstance(token, str) or not token:
        raise ValueError("Google did not return an identity token")
    return token


def _verify_google_id_token(token):
    from google.auth.transport.requests import Request
    from google.oauth2 import id_token
    return id_token.verify_oauth2_token(token, Request(), config.GOOGLE_CLIENT_ID)


def google_login_complete(connection, data):
    require_object(data)
    if not config.GOOGLE_CLIENT_ID or not config.GOOGLE_CLIENT_SECRET:
        raise ApiError(503, "google_signin_unavailable", "Google sign-in has not been configured yet.")
    code = text(data, "code", minimum=1, maximum=4096, label="Authorization code")
    state = text(data, "state", minimum=20, maximum=256, label="OAuth state")
    state_row = connection.execute(
        "SELECT * FROM google_login_states WHERE state_hash=? AND expires_at>?",
        (hash_token(state), iso()),
    ).fetchone()
    if not state_row:
        raise ApiError(400, "invalid_oauth_state", "This Google sign-in request is invalid or expired. Start again.")
    # Consume state before doing outbound token exchange so callback retries cannot replay it.
    connection.execute("DELETE FROM google_login_states WHERE state_hash=?", (state_row["state_hash"],))
    try:
        raw_id_token = _exchange_google_code(code, state_row["code_verifier"])
        claims = _verify_google_id_token(raw_id_token)
    except Exception:
        raise ApiError(401, "google_signin_failed", "Google sign-in could not be verified. Please try again.")
    if not isinstance(claims, dict) or not hmac.compare_digest(str(claims.get("nonce", "")), state_row["nonce"]):
        raise ApiError(401, "google_signin_failed", "Google sign-in could not be verified. Please try again.")
    if claims.get("email_verified") not in (True, "true", 1):
        raise ApiError(403, "google_email_unverified", "Verify your email with Google before using it to sign in.")
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject or len(subject) > 255:
        raise ApiError(401, "google_signin_failed", "Google sign-in could not be verified. Please try again.")
    email_value = email_field({"email": claims.get("email")}, "email")
    display_name = claims.get("name") if isinstance(claims.get("name"), str) else email_value.split("@", 1)[0]
    display_name = re.sub(r"\s+", " ", display_name).strip()[:50]
    if len(display_name) < 2:
        display_name = email_value.split("@", 1)[0][:50]
    now = iso()
    identity = connection.execute("SELECT user_id FROM user_auth_identities WHERE provider='google' AND subject=?", (subject,)).fetchone()
    user = _user(connection, identity["user_id"]) if identity else connection.execute("SELECT * FROM users WHERE email=? COLLATE NOCASE", (email_value,)).fetchone()
    if user and user["role"] == "admin":
        raise ApiError(403, "admin_only", "Super-admin sign-in is available only through the private web administrator entry.")
    if user and not identity:
        linked_identity = connection.execute("SELECT subject FROM user_auth_identities WHERE provider='google' AND user_id=?", (user["id"],)).fetchone()
        if linked_identity and linked_identity["subject"] != subject:
            raise ApiError(409, "google_identity_linked", "This account is already linked to a different Google account.")

    player_invite = None
    if state_row["player_invite"]:
        player_invite = connection.execute(
            "SELECT * FROM player_invites WHERE token_hash=? AND expires_at>?",
            (hash_token(state_row["player_invite"]), now),
        ).fetchone()
        if not player_invite or player_invite["email"].casefold() != email_value.casefold():
            raise ApiError(400, "invalid_player_invite", "This player invitation is invalid, expired, or belongs to another email address.")
    community_invite = None
    if state_row["community_invite"]:
        community_invite = connection.execute(
            "SELECT community_id,expires_at FROM community_invites WHERE token_hash=?",
            (hash_token(state_row["community_invite"]),),
        ).fetchone()
        if not community_invite or parse_iso(community_invite["expires_at"]) <= utc_now():
            raise ApiError(404, "invite_not_found", "This community invitation is invalid or has expired.")

    created = user is None
    with transaction(connection):
        if created:
            user_id = new_id("user")
            connection.execute(
                """INSERT INTO users(id,name,email,password_hash,role,club_role,avatar_tone,member_since,club_points,created_at,email_verified)
                VALUES(?,?,?,?, 'member','Member','sage',?,0,?,1)""",
                (user_id, display_name, email_value, hash_password(new_token()), str(utc_now().year), now),
            )
            user = _user(connection, user_id)
        else:
            user_id = user["id"]
            connection.execute("UPDATE users SET email_verified=1 WHERE id=?", (user_id,))
        connection.execute(
            "INSERT OR IGNORE INTO user_auth_identities(provider,subject,user_id,created_at) VALUES('google',?,?,?)",
            (subject, user_id, now),
        )
        if player_invite:
            player_data = json.loads(player_invite["player_data_json"])
            team = connection.execute("SELECT * FROM teams WHERE id=?", (player_invite["team_id"],)).fetchone()
            if not team:
                raise ApiError(404, "team_not_found", "The invited team no longer exists.")
            if team["community_id"]:
                connection.execute("INSERT OR IGNORE INTO community_members(community_id,user_id,role,joined_at) VALUES(?,?,'Member',?)", (team["community_id"], user_id, now))
            existing_player_id = player_data.get("existing_player_id")
            if existing_player_id:
                player = connection.execute("SELECT id,team_id,user_id FROM players WHERE id=?", (existing_player_id,)).fetchone()
                if not player or player["team_id"] != team["id"] or (player["user_id"] and player["user_id"] != user_id):
                    raise ApiError(409, "player_invite_expired", "This player profile is no longer available to link.")
                connection.execute("UPDATE players SET user_id=?,name=? WHERE id=?", (user_id, display_name, existing_player_id))
            elif not connection.execute("SELECT 1 FROM players WHERE team_id=? AND user_id=?", (team["id"], user_id)).fetchone():
                _insert_player_record(connection, team, player_data, user_id)
            connection.execute("DELETE FROM player_invites WHERE token_hash=?", (player_invite["token_hash"],))
        if community_invite:
            already_member = connection.execute("SELECT 1 FROM community_members WHERE community_id=? AND user_id=?", (community_invite["community_id"], user_id)).fetchone()
            if not already_member:
                connection.execute("INSERT INTO community_members(community_id,user_id,role,joined_at) VALUES(?,?,'Member',?)", (community_invite["community_id"], user_id, now))
                connection.execute("UPDATE communities SET member_count=member_count+1 WHERE id=?", (community_invite["community_id"],))
            connection.execute("DELETE FROM community_invites WHERE token_hash=?", (hash_token(state_row["community_invite"]),))
    user = _user(connection, user_id)
    if user["two_factor_enabled"]:
        challenge = _new_auth_token(connection, user_id, "login_2fa", 5)
        return {"twoFactorRequired": True, "challengeToken": challenge, "created": created}
    session = create_session(connection, user_id)
    return {"token": session, "user": user_public(user), "created": created}

def get_bootstrap(connection, user_id):
    process_due_polls(connection)
    state = bootstrap(connection, user_id)
    if state is None:
        raise ApiError(401, "unauthorized", "Your account is no longer available.")
    return state


def list_posts(connection, user_id, community_id=None, tag=None):
    query = "SELECT * FROM posts"
    clauses = []
    args = []
    if community_id:
        community_id = valid_id(community_id, "community_id")
        _community(connection, community_id)
        if not _is_platform_admin(connection, user_id):
            _ensure_member(connection, community_id, user_id)
        clauses.append("community_id = ?")
        args.append(community_id)
    elif not _is_platform_admin(connection, user_id):
        clauses.append("community_id IN (SELECT community_id FROM community_members WHERE user_id = ?)")
        args.append(user_id)
    if tag:
        clauses.append("tags_json LIKE ?")
        args.append(f'%"{tag}"%')
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_at DESC"
    rows = connection.execute(query, args).fetchall()
    return [post_dict(connection, row, user_id) for row in rows]


def list_polls(connection, user_id):
    process_due_polls(connection)
    rows = connection.execute(
        """SELECT * FROM polls WHERE community_id IS NULL OR community_id IN
        (SELECT community_id FROM community_members WHERE user_id=?)
        OR (SELECT role FROM users WHERE id=?)='admin'
        ORDER BY created_at DESC, rowid ASC""",
        (user_id, user_id),
    ).fetchall()
    return [poll_dict(connection, row, user_id) for row in rows]


def list_communities(connection, user_id):
    rows = connection.execute("""SELECT * FROM communities WHERE privacy='Public'
        OR id IN (SELECT community_id FROM community_members WHERE user_id=?)
        OR (SELECT role FROM users WHERE id=?)='admin' ORDER BY rowid ASC""", (user_id, user_id)).fetchall()
    return [community_dict(connection, row, user_id) for row in rows]


def list_plans(connection, user_id):
    rows = connection.execute(
        """SELECT * FROM plans WHERE (SELECT role FROM users WHERE id=?)='admin'
        OR community_id IN (SELECT community_id FROM community_members WHERE user_id=?)
        ORDER BY date ASC, rowid ASC""", (user_id, user_id)
    ).fetchall()
    return [plan_dict(row) for row in rows]


def list_notifications(connection, user_id):
    rows = connection.execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY rowid ASC",
        (user_id,),
    ).fetchall()
    return [notification_dict(row) for row in rows]


def get_team(connection, user_id):
    return team_dict(connection, _team_for_user(connection, user_id), user_id)


def list_players(connection, user_id):
    team = _team_for_user(connection, user_id)
    return team_dict(connection, team, user_id)["players"]


def get_player(connection, user_id, player_id):
    player = _player(connection, valid_id(player_id, "player_id"))
    team = connection.execute("SELECT * FROM teams WHERE id=?", (player["team_id"],)).fetchone()
    if team and team["community_id"]:
        _ensure_member(connection, team["community_id"], user_id)
    elif not _is_platform_admin(connection, user_id):
        raise ApiError(403, "forbidden", "You cannot view this player.")
    return _player_dict(connection, player, user_id)


def get_plan(connection, plan_id, user_id):
    plan = _plan(connection, valid_id(plan_id, "plan_id"))
    if plan["community_id"] and not _is_platform_admin(connection, user_id):
        _ensure_member(connection, plan["community_id"], user_id)
    elif not _is_platform_admin(connection, user_id):
        raise ApiError(403, "forbidden", "You cannot view this game plan.")
    return plan_dict(plan)


def get_schedule(connection, user_id, community_id):
    community_id = valid_id(community_id, "community_id")
    _community(connection, community_id)
    if not _is_platform_admin(connection, user_id):
        _ensure_member(connection, community_id, user_id)
    events = connection.execute("SELECT * FROM events WHERE community_id=? ORDER BY sort_order ASC", (community_id,)).fetchall()
    fixtures = connection.execute("SELECT * FROM fixtures WHERE community_id=? ORDER BY sort_order ASC", (community_id,)).fetchall()
    return {
        "schedule": [
            {
                "id": row["id"],
                "date": row["date"],
                "type": row["type"],
                "title": row["title"],
                "detail": row["detail"],
                "accent": row["accent"],
            }
            for row in events
        ],
        "nextFixtures": [
            {
                "id": row["id"],
                "opponent": row["opponent"],
                "opponentMark": row["opponent_mark"],
                "homeAway": row["home_away"],
                "date": row["date"],
                "venue": row["venue"],
                "competition": row["competition"],
            }
            for row in fixtures
        ],
    }


# ---------- Posts and community feed ----------

def create_post(connection, user_id, data):
    require_object(data)
    community_id = valid_id(data.get("community_id", ""), "community_id")
    _community(connection, community_id)
    _ensure_member(connection, community_id, user_id)
    body = text(data, "text", minimum=1, maximum=500, label="Post")
    tag = choice(data, "tag", TAGS, required=False, default="club", label="Tag")
    image_data = _image_data(data.get("image_data"), "Post photo") if "image_data" in data else None
    post_id = new_id("post")
    media = {"type": "image", "data": image_data} if image_data else None
    created_at = iso()
    community = _community(connection, community_id)
    author = _user(connection, user_id)
    excerpt = " ".join(body.split())
    if len(excerpt) > 180:
        excerpt = excerpt[:177].rstrip() + "…"
    with transaction(connection):
        connection.execute(
            """
            INSERT INTO posts (id, author_id, community_id, text, tags_json, seed_likes, media_json, created_at)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (post_id, user_id, community_id, body, json.dumps([tag]), json.dumps(media) if media else None, created_at),
        )
        recipients = connection.execute(
            "SELECT user_id FROM community_members WHERE community_id=? AND user_id<>? ORDER BY joined_at,user_id",
            (community_id, user_id),
        ).fetchall()
        for recipient in recipients:
            _create_notification(
                connection, recipient["user_id"], icon="message", title=f"New post · {community['name']}",
                body=f"{author['name']}: {excerpt}",
                route=f"#/community/{community_id}/posts/{post_id}", created_at=created_at,
                community_id=community_id, post_id=post_id, kind="post",
                source_key=f"post:{post_id}:{recipient['user_id']}",
            )
    return post_dict(connection, _post(connection, post_id), user_id)


def delete_post(connection, user_id, post_id):
    post_id = valid_id(post_id, "post_id")
    row = _post(connection, post_id)
    if row["author_id"] != user_id:
        _require_community_admin(connection, row["community_id"], user_id)
    connection.execute("DELETE FROM posts WHERE id=?", (post_id,))
    return {"id": post_id, "deleted": True}


def toggle_like(connection, user_id, post_id):
    row = _post(connection, valid_id(post_id, "post_id"))
    existing = connection.execute(
        "SELECT 1 FROM post_likes WHERE post_id = ? AND user_id = ?",
        (row["id"], user_id),
    ).fetchone()
    if existing:
        connection.execute(
            "DELETE FROM post_likes WHERE post_id = ? AND user_id = ?",
            (row["id"], user_id),
        )
    else:
        connection.execute(
            "INSERT INTO post_likes (post_id, user_id, created_at) VALUES (?, ?, ?)",
            (row["id"], user_id, iso()),
        )
    return post_dict(connection, _post(connection, row["id"]), user_id)


def add_comment(connection, user_id, post_id, data):
    require_object(data)
    row = _post(connection, valid_id(post_id, "post_id"))
    body = text(data, "text", minimum=1, maximum=220, label="Comment")
    comment_id = new_id("comment")
    connection.execute(
        "INSERT INTO comments (id, post_id, author_id, text, created_at) VALUES (?, ?, ?, ?, ?)",
        (comment_id, row["id"], user_id, body, iso()),
    )
    return post_dict(connection, _post(connection, row["id"]), user_id)


# ---------- Polls ----------

def poll_feedback_due_at(game_at, timezone_name=None):
    game_time = parse_iso(game_at)
    if game_time is None:
        raise ValueError("game_at must be a valid ISO datetime")
    try:
        local_zone = ZoneInfo(timezone_name or config.TIMEZONE)
    except ZoneInfoNotFoundError:
        local_zone = timezone.utc
    local_game = game_time.astimezone(local_zone)
    morning = datetime_time(5, 0) <= local_game.timetz().replace(tzinfo=None) <= datetime_time(8, 0)
    send_at = datetime.combine(local_game.date(), datetime_time(10 if morning else 22, 0), tzinfo=local_zone)
    return send_at.astimezone(timezone.utc)


def _pickup_poll_result(connection, community_id, poll_id):
    colors = secrets.SystemRandom().sample(["Blue", "Red", "Green", "Yellow"], 2)
    team_names = {"teamA": f"Yolo {colors[0]}", "teamB": f"Yolo {colors[1]}"}
    team = connection.execute("SELECT * FROM teams WHERE community_id=?", (community_id,)).fetchone()
    if team is None:
        return {"teamA": [], "teamB": [], "floater": None, "poolSize": 0, "gap": 0, "positionGap": 0, "teamNames": team_names}
    # Only players and guests attached to a Yes vote are eligible for this game's split.
    participants = _pickup_poll_participants(connection, community_id, poll_id)
    if not participants:
        return {"teamA": [], "teamB": [], "floater": None, "poolSize": 0, "gap": 0, "positionGap": 0, "balanceScore": 100, "manual": False, "teamNames": team_names}
    result = split_squad(participants, position_aware=True)
    return {
        "teamA": [player["id"] for player in result["teamA"]["players"]],
        "teamB": [player["id"] for player in result["teamB"]["players"]],
        "floater": result["floater"]["id"] if result["floater"] else None,
        "poolSize": result["poolSize"], "gap": result["gap"],
        "positionGap": result["positionGap"], "balanceScore": result["balanceScore"],
        "manual": False, "teamNames": team_names,
    }


def _pickup_poll_participants(connection, community_id, poll_id):
    rows = connection.execute("""SELECT p.*,COALESCE(SUM(r.value),0) AS member_rating_sum,COUNT(r.value) AS member_rating_count,
        v.user_id,v.guest_count
        FROM poll_votes v JOIN poll_options o ON o.id=v.option_id JOIN players p ON p.id=v.player_id
        JOIN teams t ON t.id=p.team_id LEFT JOIN player_ratings r ON r.player_id=p.id
        WHERE v.poll_id=? AND lower(o.label)='yes' AND t.community_id=? AND p.status<>'out'
        GROUP BY p.id ORDER BY p.sort_order,p.number""", (poll_id, community_id)).fetchall()
    players = []
    for row in rows:
        count = int(row["rating_count"]) + int(row["member_rating_count"])
        rating = (float(row["rating_sum"]) + float(row["member_rating_sum"])) / count if count else 6.5
        host = {"id": row["id"], "name": row["name"], "number": row["number"], "pos": row["pos"], "group": row["group_name"], "rating": rating, "apps": row["apps"], "status": row["status"], "guest": False}
        players.append(host)
        for index in range(1, int(row["guest_count"]) + 1):
            players.append({**host, "id": f"guest-{poll_id}-{row['user_id']}-{index}", "name": f"{row['name']} · Guest {index}", "number": 0, "apps": 0, "guest": True})
    return players


def process_due_polls(connection, now=None):
    now = now or utc_now()
    now_text = iso(now)
    closing = connection.execute(
        """SELECT p.id,p.community_id,p.category,p.question,c.name AS community_name
        FROM polls p LEFT JOIN communities c ON c.id=p.community_id
        WHERE p.closes_at<=? AND p.result_json IS NULL""", (now_text,),
    ).fetchall()
    for poll in closing:
        if poll["community_id"] and poll["community_name"]:
            recipients = connection.execute(
                "SELECT user_id FROM community_members WHERE community_id=? ORDER BY joined_at,user_id",
                (poll["community_id"],),
            ).fetchall()
            for recipient in recipients:
                _create_notification(
                    connection, recipient["user_id"], icon="poll",
                    title=f"Poll closed · {poll['community_name']}",
                    body=f"{poll['question']} is now closed.", route="#/polls", created_at=now_text,
                    community_id=poll["community_id"], kind="poll_closed",
                    source_key=f"poll-closed:{poll['id']}:{recipient['user_id']}",
                )
        result = _pickup_poll_result(connection, poll["community_id"], poll["id"]) if poll["category"] == "Pickup" and poll["community_id"] else {}
        connection.execute("UPDATE polls SET result_json=? WHERE id=? AND result_json IS NULL", (json.dumps(result), poll["id"]))
    empty_closed = connection.execute(
        """DELETE FROM polls WHERE closes_at<=?
        AND NOT EXISTS (SELECT 1 FROM poll_votes WHERE poll_votes.poll_id=polls.id)""",
        (now_text,),
    ).rowcount

    # A Yes vote is the pickup attendance confirmation. Apply each completed
    # game once; the unique poll/player key also makes retries safe.
    played_polls = connection.execute("""SELECT id,game_at,community_id FROM polls
        WHERE category='Pickup' AND game_at IS NOT NULL AND game_at<=? AND closes_at<=?""", (now_text, now_text)).fetchall()
    for poll in played_polls:
        participants = connection.execute("""SELECT DISTINCT p.id,p.team_id
            FROM poll_votes v JOIN poll_options o ON o.id=v.option_id
            JOIN players p ON p.id=v.player_id JOIN teams t ON t.id=p.team_id
            WHERE v.poll_id=? AND lower(o.label)='yes' AND t.community_id=?""", (poll["id"],poll["community_id"])).fetchall()
        for player in participants:
            inserted = connection.execute("INSERT OR IGNORE INTO player_match_appearances(poll_id,player_id,played_at,minutes,started) VALUES(?,?,?,90,0)", (poll["id"],player["id"],now_text)).rowcount
            if inserted:
                connection.execute("UPDATE players SET apps=apps+1,minutes=minutes+90 WHERE id=?", (player["id"],))

    due = connection.execute("SELECT * FROM polls WHERE feedback_due_at IS NOT NULL AND feedback_due_at<=? AND feedback_completed_at IS NULL", (now_text,)).fetchall()
    for poll in due:
        if poll["category"] == "Pickup":
            voters = connection.execute(
                """SELECT DISTINCT u.id,u.email FROM poll_votes v JOIN poll_options o ON o.id=v.option_id
                JOIN users u ON u.id=v.user_id JOIN players p ON p.id=v.player_id
                WHERE v.poll_id=? AND lower(o.label)='yes' AND p.status<>'out' AND u.email_verified=1""", (poll["id"],),
            ).fetchall()
        else:
            voters = connection.execute(
                """SELECT DISTINCT u.id,u.email FROM poll_votes v JOIN users u ON u.id=v.user_id
                WHERE v.poll_id=? AND u.email_verified=1""", (poll["id"],),
            ).fetchall()
        for voter in voters:
            connection.execute("INSERT OR IGNORE INTO poll_feedback_deliveries(poll_id,user_id) VALUES(?,?)", (poll["id"], voter["id"]))
        if poll["category"] == "Pickup":
            connection.execute("""DELETE FROM poll_feedback_deliveries WHERE poll_id=? AND user_id NOT IN (
                SELECT v.user_id FROM poll_votes v JOIN poll_options o ON o.id=v.option_id JOIN players p ON p.id=v.player_id
                WHERE v.poll_id=? AND lower(o.label)='yes' AND p.status<>'out')""", (poll["id"], poll["id"]))
        deliveries = connection.execute(
            """SELECT d.user_id,d.attempts,u.email FROM poll_feedback_deliveries d
            JOIN users u ON u.id=d.user_id WHERE d.poll_id=? AND d.sent_at IS NULL
            AND (d.next_attempt_at IS NULL OR d.next_attempt_at<=?) ORDER BY d.user_id""",
            (poll["id"], now_text),
        ).fetchall()
        for delivery in deliveries:
            link = f"{config.APP_BASE_URL}/#/polls?feedbackPoll={poll['id']}"
            try:
                send_email(delivery["email"], f"Rate the players from {poll['question']}",
                    f"Thanks for taking part in the {poll['category'].lower()} poll. Please sign in to rate each player and leave feedback after the game:\n\n{link}\n")
                connection.execute("UPDATE poll_feedback_deliveries SET sent_at=?,attempts=attempts+1 WHERE poll_id=? AND user_id=?", (now_text, poll["id"], delivery["user_id"]))
            except MailDeliveryError:
                attempts = int(delivery["attempts"]) + 1
                retry_minutes = min(60, 5 * (2 ** min(attempts - 1, 4)))
                connection.execute("UPDATE poll_feedback_deliveries SET attempts=?,next_attempt_at=? WHERE poll_id=? AND user_id=?", (attempts, iso(now + timedelta(minutes=retry_minutes)), poll["id"], delivery["user_id"]))
        remaining = connection.execute("SELECT COUNT(*) AS n FROM poll_feedback_deliveries WHERE poll_id=? AND sent_at IS NULL", (poll["id"],)).fetchone()["n"]
        if not remaining:
            connection.execute("UPDATE polls SET feedback_completed_at=? WHERE id=? AND feedback_completed_at IS NULL", (now_text, poll["id"]))
    global_days = _global_poll_retention_days(connection)
    global_cutoff = iso(now - timedelta(days=global_days))
    expired = connection.execute(
        """DELETE FROM polls WHERE created_at < ?
        AND (community_id IS NULL OR community_id NOT IN (SELECT community_id FROM community_settings))""",
        (global_cutoff,),
    ).rowcount
    for setting in connection.execute("SELECT community_id,poll_retention_days FROM community_settings").fetchall():
        cutoff = iso(now - timedelta(days=int(setting["poll_retention_days"])))
        expired += connection.execute("DELETE FROM polls WHERE community_id=? AND created_at<?", (setting["community_id"], cutoff)).rowcount
    return {"closed": len(closing), "appearancesProcessed": len(played_polls), "feedbackProcessed": len(due), "deleted": empty_closed + expired}


def process_due_polls_once():
    with db.connect() as connection:
        return process_due_polls(connection)

def create_poll(connection, user_id, data):
    require_object(data)
    question = text(data, "question", minimum=3, maximum=120, label="Question")
    category = choice(data, "category", POLL_CATEGORIES, required=False, default="Pickup", label="Category")
    options = ["Yes", "No"] if category == "Pickup" else text_list(data, "options", minimum=2, maximum=4, item_maximum=60)
    location = text(data, "location", required=False, minimum=0, maximum=160, default="", label="Pickup location") if category == "Pickup" else ""
    if data.get("closes_at"):
        try:
            closes_at_dt = parse_iso(text(data, "closes_at", maximum=64, label="Poll close date and time"))
        except (TypeError, ValueError):
            closes_at_dt = None
        if closes_at_dt is None or closes_at_dt <= utc_now():
            raise ApiError(400, "invalid_field", "Choose a poll closing time in the future.", {"closes_at": "date_time"})
    else:
        duration = integer(data, "duration_hours", required=False, default=48, minimum=1, maximum=168, label="Duration")
        closes_at_dt = utc_now() + timedelta(hours=duration)
    game_at_dt = None
    if category in {"Pickup", "Competition"}:
        if not data.get("community_id"):
            raise ApiError(400, "missing_field", "Pickup and competition polls must belong to a community.", {"community_id": "required"})
        try:
            game_at_dt = parse_iso(text(data, "game_at", maximum=64, label="Game date and time"))
        except (TypeError, ValueError):
            game_at_dt = None
        if game_at_dt is None or game_at_dt <= closes_at_dt:
            raise ApiError(400, "invalid_field", "The game must start after the poll closes.", {"game_at": "date_time"})
    community_id = data.get("community_id")
    if community_id:
        community_id = valid_id(community_id, "community_id")
        _community(connection, community_id)
        if not _is_platform_admin(connection, user_id):
            _ensure_member(connection, community_id, user_id)
    poll_id = new_id("poll")
    closes_at = iso(closes_at_dt)
    game_at = iso(game_at_dt) if game_at_dt else None
    feedback_due_at = iso(poll_feedback_due_at(game_at)) if game_at else None
    with transaction(connection):
        connection.execute(
            "INSERT INTO polls (id, community_id, question, category, author_id, closes_at, game_at, location, feedback_due_at, featured, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)",
            (poll_id, community_id, question, category, user_id, closes_at, game_at, location, feedback_due_at, iso()),
        )
        for index, label in enumerate(options):
            connection.execute(
                "INSERT INTO poll_options (id, poll_id, label, seed_votes, position) VALUES (?, ?, ?, 0, ?)",
                (new_id("option"), poll_id, label, index),
            )
    return poll_dict(connection, _poll(connection, poll_id), user_id)


def vote_poll(connection, user_id, poll_id, data):
    require_object(data)
    poll = _poll(connection, valid_id(poll_id, "poll_id"))
    if poll["community_id"] and not _is_platform_admin(connection, user_id):
        _ensure_member(connection, poll["community_id"], user_id)
    if parse_iso(poll["closes_at"]) <= utc_now():
        raise ApiError(409, "poll_closed", "That poll has already closed.")
    option_id = valid_id(data.get("option_id", ""), "option_id")
    option = connection.execute(
        "SELECT * FROM poll_options WHERE id = ? AND poll_id = ?",
        (option_id, poll["id"]),
    ).fetchone()
    if option is None:
        raise ApiError(400, "invalid_option", "That option does not belong to this poll.")
    player_id = None
    if poll["category"] == "Pickup":
        if option["label"].lower() not in {"yes", "no"}:
            raise ApiError(409, "invalid_pickup_options", "Pickup polls only allow Yes and No responses.")
        player_id = data.get("player_id")
        guest_count = integer(data, "guest_count", required=False, default=0, minimum=0, maximum=2, label="Additional guests")
        if option["label"].lower() == "yes":
            if not isinstance(player_id, str):
                raise ApiError(400, "player_required", "Choose your player from the community roster when you vote In.")
            player = connection.execute("""SELECT p.id,p.name,p.user_id FROM players p JOIN teams t ON t.id=p.team_id
                WHERE p.id=? AND t.community_id=? AND p.status<>'out'""", (player_id, poll["community_id"])).fetchone()
            if player is None:
                raise ApiError(400, "invalid_player", "Choose an available player from this community.")
            account_name = connection.execute("SELECT name FROM users WHERE id=?", (user_id,)).fetchone()["name"]
            if (player["user_id"] and player["user_id"] != user_id) or (not player["user_id"] and player["name"].strip().casefold() != account_name.strip().casefold()):
                raise ApiError(403, "player_not_self", "You can only register the player profile that matches your signed-in account name.")
            matching_profiles = connection.execute("""SELECT COUNT(*) AS n FROM players p JOIN teams t ON t.id=p.team_id
                WHERE t.community_id=? AND p.status<>'out' AND ((p.user_id IS NOT NULL AND p.user_id=?) OR (p.user_id IS NULL AND lower(trim(p.name))=lower(trim(?))))""", (poll["community_id"], user_id, account_name)).fetchone()["n"]
            if matching_profiles != 1:
                raise ApiError(409, "player_profile_ambiguous", "Your account name must match exactly one active player profile in this community.")
            duplicate = connection.execute("SELECT 1 FROM poll_votes WHERE poll_id=? AND player_id=? AND user_id<>?", (poll["id"], player_id, user_id)).fetchone()
            if duplicate:
                raise ApiError(409, "player_already_registered", "That player is already registered for this game.")
        elif player_id is not None or guest_count:
            raise ApiError(400, "invalid_player", "A No response cannot include a player or guests.")
    connection.execute(
        """
        INSERT INTO poll_votes (poll_id, user_id, option_id, player_id, guest_count, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(poll_id, user_id) DO UPDATE SET option_id = excluded.option_id, player_id=excluded.player_id, guest_count=excluded.guest_count, created_at = excluded.created_at
        """,
        (poll["id"], user_id, option_id, player_id, guest_count if poll["category"] == "Pickup" and option["label"].lower() == "yes" else 0, iso()),
    )
    return poll_dict(connection, _poll(connection, poll["id"]), user_id)


def _poll_roster(connection, community_id):
    rows = connection.execute("""SELECT p.*,COALESCE(SUM(r.value),0) AS member_rating_sum,COUNT(r.value) AS member_rating_count
        FROM players p JOIN teams t ON t.id=p.team_id LEFT JOIN player_ratings r ON r.player_id=p.id
        WHERE t.community_id=? AND p.status<>'out' GROUP BY p.id ORDER BY p.sort_order,p.number""", (community_id,)).fetchall()
    players = []
    for row in rows:
        count = int(row["rating_count"]) + int(row["member_rating_count"])
        rating = (float(row["rating_sum"]) + float(row["member_rating_sum"])) / count if count else 6.5
        players.append({"id": row["id"], "name": row["name"], "number": int(row["number"]), "position": row["pos"], "rating": round(rating, 1), "group": row["group_name"], "imageData": row["image_data"]})
    return players


def _pickup_poll_player_ids(connection, poll_id):
    return {row["player_id"] for row in connection.execute(
        """SELECT v.player_id FROM poll_votes v JOIN poll_options o ON o.id=v.option_id
        WHERE v.poll_id=? AND lower(o.label)='yes' AND v.player_id IS NOT NULL""", (poll_id,),
    ).fetchall()}


def update_poll_teams(connection, user_id, poll_id, data):
    require_object(data)
    poll = _poll(connection, valid_id(poll_id, "poll_id"))
    if poll["category"] not in {"Pickup", "Competition"} or not poll["community_id"]:
        raise ApiError(409, "not_pickup_poll", "Manual team balancing is only available for pickup and competition polls.")
    member_role = _community_role(connection, poll["community_id"], user_id)
    if not _is_platform_admin(connection, user_id) and member_role != "Admin" and poll["author_id"] != user_id:
        raise ApiError(403, "forbidden", "Only this poll's creator or a community admin can rearrange its teams.")
    if parse_iso(poll["closes_at"]) > utc_now():
        raise ApiError(409, "poll_open", "Wait until the poll closes before rearranging the balanced teams.")
    result = json.loads(poll["result_json"] or "{}")
    if not result:
        process_due_polls(connection)
        poll = _poll(connection, poll_id)
        result = json.loads(poll["result_json"] or "{}")
    if not result:
        raise ApiError(409, "teams_not_ready", "The automatic player teams are not ready yet.")
    team_a, team_b = data.get("team_a"), data.get("team_b")
    floater = data.get("floater")
    if not isinstance(team_a, list) or not isinstance(team_b, list) or (floater is not None and not isinstance(floater, str)):
        raise ApiError(400, "invalid_teams", "Provide player IDs for both teams and an optional floater.")
    all_ids = team_a + team_b + ([floater] if floater else [])
    eligible_ids = {player["id"] for player in _poll_roster(connection, poll["community_id"])}
    required_ids = set(eligible_ids)
    if poll["category"] == "Pickup":
        required_ids = {player["id"] for player in _pickup_poll_participants(connection, poll["community_id"], poll_id)}
        eligible_ids |= required_ids
    assigned_ids = set(all_ids)
    total_players = len(all_ids)
    valid_sizes = (len(team_a) == len(team_b) if floater or total_players % 2 == 0 else abs(len(team_a) - len(team_b)) == 1)
    valid_assignment = required_ids <= assigned_ids and assigned_ids <= eligible_ids
    if poll["category"] == "Competition":
        valid_assignment = assigned_ids == required_ids
    if len(all_ids) != len(assigned_ids) or not valid_assignment or not valid_sizes or (floater and total_players % 2 == 0):
        raise ApiError(400, "invalid_teams", "Every attending player and guest must be assigned exactly once. Teams must be balanced as evenly as possible; one floater is optional for an odd roster.")
    result.update({"teamA": team_a, "teamB": team_b, "floater": floater, "manual": True})
    connection.execute("UPDATE polls SET result_json=? WHERE id=?", (json.dumps(result), poll_id))
    return poll_dict(connection, _poll(connection, poll_id), user_id)


def get_poll_feedback(connection, user_id, poll_id):
    poll = _poll(connection, valid_id(poll_id, "poll_id"))
    if poll["category"] not in {"Pickup", "Competition"} or not poll["community_id"]:
        raise ApiError(409, "not_pickup_poll", "Post-game player feedback is only available for pickup and competition polls.")
    if not _is_platform_admin(connection, user_id):
        _ensure_member(connection, poll["community_id"], user_id)
        vote = connection.execute("""SELECT o.label,v.player_id,p.status AS player_status FROM poll_votes v JOIN poll_options o ON o.id=v.option_id
            LEFT JOIN players p ON p.id=v.player_id
            WHERE v.poll_id=? AND v.user_id=?""", (poll_id, user_id)).fetchone()
        if vote is None:
            raise ApiError(403, "poll_vote_required", "Only members who voted in this poll can submit post-game feedback.")
        if poll["category"] == "Pickup" and (vote["label"].lower() != "yes" or not vote["player_id"] or vote["player_status"] == "out"):
            raise ApiError(403, "pickup_attendance_required", "Only members who registered a player as Yes may submit game feedback.")
    if poll["feedback_due_at"] and parse_iso(poll["feedback_due_at"]) > utc_now():
        raise ApiError(409, "feedback_not_open", "Player feedback will open after the game.")
    request_rows = connection.execute("SELECT * FROM poll_player_ratings WHERE poll_id=? AND user_id=?", (poll_id, user_id)).fetchall()
    own = {row["player_id"]: row for row in request_rows}
    players = _poll_roster(connection, poll["community_id"])
    if poll["category"] == "Pickup":
        player_ids = _pickup_poll_player_ids(connection, poll_id)
        players = [player for player in players if player["id"] in player_ids]
    response = {"id": poll_id, "question": poll["question"], "gameAt": poll["game_at"], "players": [
        {**player, "rating": own[player["id"]]["value"] if player["id"] in own else None, "feedback": own[player["id"]]["feedback"] if player["id"] in own else ""}
        for player in players
    ]}
    if _is_platform_admin(connection, user_id) or _community_role(connection, poll["community_id"], user_id) == "Admin":
        response["results"] = [
            {"playerId": row["player_id"], "member": row["name"], "rating": row["value"], "feedback": row["feedback"]}
            for row in connection.execute("SELECT r.player_id,u.name,r.value,r.feedback FROM poll_player_ratings r JOIN users u ON u.id=r.user_id WHERE r.poll_id=? ORDER BY u.name", (poll_id,)).fetchall()
        ]
    return response


def submit_poll_feedback(connection, user_id, poll_id, data):
    require_object(data)
    review = get_poll_feedback(connection, user_id, poll_id)
    ratings = data.get("ratings")
    if not isinstance(ratings, list) or len(ratings) != len(review["players"]):
        raise ApiError(400, "invalid_ratings", "Rate every player before submitting your post-game feedback.")
    expected = {player["id"] for player in review["players"]}
    submitted = {}
    for entry in ratings:
        if not isinstance(entry, dict) or not isinstance(entry.get("player_id"), str) or entry["player_id"] not in expected or entry["player_id"] in submitted:
            raise ApiError(400, "invalid_ratings", "The feedback includes an invalid or duplicate player.")
        submitted[entry["player_id"]] = (integer(entry, "value", minimum=1, maximum=10, label="Rating"), text(entry, "feedback", required=False, maximum=500, default="", label="Feedback") or "")
    now = iso()
    for player_id, (value, feedback) in submitted.items():
        connection.execute("""INSERT INTO poll_player_ratings(poll_id,player_id,user_id,value,feedback,updated_at) VALUES(?,?,?,?,?,?)
            ON CONFLICT(poll_id,player_id,user_id) DO UPDATE SET value=excluded.value,feedback=excluded.feedback,updated_at=excluded.updated_at""", (poll_id, player_id, user_id, value, feedback, now))
    return {"submitted": True, "playerCount": len(submitted)}


# ---------- Communities ----------

def _mark(name):
    words = [word for word in str(name).split() if word]
    if len(words) >= 2:
        return (words[0][0] + words[1][0]).upper()
    return str(name).strip()[:2].upper()


def _image_data(value, label, *, max_bytes=170_000):
    if value in (None, ""):
        return None
    if not isinstance(value, str) or len(value) > max_bytes * 4 // 3 + 256:
        raise ApiError(400, "invalid_image", f"{label} must be a small PNG, JPEG, or WebP image.")
    match = re.fullmatch(r"data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/]+={0,2})", value)
    if not match:
        raise ApiError(400, "invalid_image", f"{label} must be a PNG, JPEG, or WebP image.")
    try:
        raw = base64.b64decode(match.group(2), validate=True)
    except (ValueError, binascii.Error):
        raise ApiError(400, "invalid_image", f"{label} is not a valid image.")
    signatures = {
        "png": raw.startswith(b"\x89PNG\r\n\x1a\n"),
        "jpeg": raw.startswith(b"\xff\xd8\xff"),
        "webp": len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP",
    }
    if len(raw) > max_bytes or not signatures[match.group(1)]:
        raise ApiError(400, "invalid_image", f"{label} is too large or does not match its image format.")
    return value


def create_community(connection, user_id, data):
    require_object(data)
    name = text(data, "name", minimum=2, maximum=48, label="Community name")
    sport = choice(data, "sport", SPORTS, label="Sport")
    kind = choice(data, "kind", {"Club", "Community"}, required=False, default="Community", label="Type")
    privacy = choice(data, "privacy", {"Public", "Private"}, required=False, default="Public", label="Privacy")
    description = text(data, "description", minimum=3, maximum=220, label="Description")
    logo_data = _image_data(data.get("logo_data"), "Community logo") if "logo_data" in data else None
    banner_data = _image_data(data.get("banner_data"), "Community banner") if "banner_data" in data else None
    starter_poll = boolean(data, "create_poll", default=False)
    community_id = new_id("community")
    count = connection.execute("SELECT COUNT(*) AS count FROM communities").fetchone()["count"]
    now = iso()
    with transaction(connection):
        connection.execute(
            """
            INSERT INTO communities
            (id, name, sport, kind, mark, member_count, privacy, accent, description, activity, created_by, created_at, logo_data, banner_data)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, 'Just created', ?, ?, ?, ?)
            """,
            (
                community_id,
                name,
                sport,
                kind,
                _mark(name),
                privacy,
                ACCENTS[count % len(ACCENTS)],
                description,
                user_id,
                now,
                logo_data,
                banner_data,
            ),
        )
        connection.execute(
            "INSERT INTO community_members (community_id, user_id, role, joined_at) VALUES (?, ?, 'Admin', ?)",
            (community_id, user_id, now),
        )
        if starter_poll:
            poll_id = new_id("poll")
            connection.execute(
                "INSERT INTO polls (id, community_id, question, category, author_id, closes_at, featured, created_at) VALUES (?, ?, ?, 'Club', ?, ?, 0, ?)",
                (
                    poll_id,
                    community_id,
                    f"First meet-up for {name} — who’s in?",
                    user_id,
                    iso(utc_now() + timedelta(days=3)),
                    now,
                ),
            )
            for index, label in enumerate(("I’m in", "Maybe next time", "Need more details first")):
                connection.execute(
                    "INSERT INTO poll_options (id, poll_id, label, seed_votes, position) VALUES (?, ?, ?, 0, ?)",
                    (new_id("option"), poll_id, label, index),
                )
    return community_dict(connection, _community(connection, community_id), user_id)


def update_community_branding(connection, user_id, community_id, data):
    require_object(data)
    community_id = valid_id(community_id, "community_id")
    row = _community(connection, community_id)
    _require_community_admin(connection, community_id, user_id)
    updates = {}
    for field, label in (("logo_data", "Community logo"), ("banner_data", "Community banner")):
        if field in data:
            updates[field] = _image_data(data[field], label)
    if not updates:
        raise ApiError(400, "no_changes", "Choose a community logo or banner to update.")
    assignments = ", ".join(f"{field}=?" for field in updates)
    connection.execute(f"UPDATE communities SET {assignments} WHERE id=?", (*updates.values(), row["id"]))
    return community_dict(connection, _community(connection, community_id), user_id)


def request_matchday_ratings(connection, user_id, community_id, fixture_id):
    community_id = valid_id(community_id, "community_id")
    fixture_id = valid_id(fixture_id, "fixture_id")
    _community(connection, community_id)
    _require_community_admin(connection, community_id, user_id)
    fixture = connection.execute("SELECT * FROM fixtures WHERE id=? AND community_id=?", (fixture_id, community_id)).fetchone()
    if fixture is None:
        raise ApiError(404, "not_found", "That matchday fixture was not found in this community.")
    kickoff = parse_iso(fixture["date"])
    if kickoff is None or kickoff > utc_now():
        raise ApiError(409, "match_not_finished", "Player ratings can be requested after the fixture has finished.")
    players = connection.execute("SELECT p.id FROM players p JOIN teams t ON t.id=p.team_id WHERE t.community_id=?", (community_id,)).fetchall()
    if not players:
        raise ApiError(409, "no_players", "Add players to this community before requesting matchday ratings.")
    now = iso()
    connection.execute(
        "INSERT OR IGNORE INTO matchday_rating_requests(id,community_id,fixture_id,requested_by,requested_at) VALUES(?,?,?,?,?)",
        (new_id("matchreview"), community_id, fixture_id, user_id, now),
    )
    request = connection.execute("SELECT id FROM matchday_rating_requests WHERE community_id=? AND fixture_id=?", (community_id, fixture_id)).fetchone()
    recipients = connection.execute(
        "SELECT u.email FROM users u JOIN community_members m ON m.user_id=u.id WHERE m.community_id=? AND u.email_verified=1 ORDER BY u.id",
        (community_id,),
    ).fetchall()
    if not recipients:
        raise ApiError(409, "no_verified_members", "No email-verified community members can receive the rating request yet.")
    review_url = f"{config.APP_BASE_URL}/#/community/{community_id}?rateFixture={fixture_id}"
    subject = f"Rate the players from {fixture['opponent']}"
    failures = 0
    for recipient in recipients:
        try:
            send_email(recipient["email"], subject,
                f"The matchday review for {fixture['opponent']} is open. Sign in to Touchline and rate each player, with optional feedback:\n\n{review_url}\n")
        except MailDeliveryError:
            failures += 1
    if failures:
        raise ApiError(503, "email_unavailable", "The review was created, but some email messages could not be delivered. Check SMTP settings and retry.")
    return {"id": request["id"], "fixtureId": fixture_id, "sentTo": len(recipients), "requestedAt": now}


def get_matchday_ratings(connection, user_id, community_id, fixture_id):
    community_id = valid_id(community_id, "community_id")
    fixture_id = valid_id(fixture_id, "fixture_id")
    _community(connection, community_id)
    _ensure_member(connection, community_id, user_id)
    request = connection.execute("SELECT * FROM matchday_rating_requests WHERE community_id=? AND fixture_id=?", (community_id, fixture_id)).fetchone()
    if request is None:
        raise ApiError(404, "not_found", "Matchday ratings have not been requested for this fixture.")
    rows = connection.execute(
        """SELECT p.id,p.name,p.number,p.pos,p.image_data,r.value,r.feedback
        FROM players p JOIN teams t ON t.id=p.team_id
        LEFT JOIN matchday_player_ratings r ON r.player_id=p.id AND r.request_id=? AND r.user_id=?
        WHERE t.community_id=? ORDER BY p.sort_order,p.number""",
        (request["id"], user_id, community_id),
    ).fetchall()
    fixture = connection.execute("SELECT opponent,date,venue,competition FROM fixtures WHERE id=?", (fixture_id,)).fetchone()
    response = {"id": request["id"], "fixtureId": fixture_id, "fixture": dict(fixture), "players": [
        {"id": row["id"], "name": row["name"], "number": row["number"], "position": row["pos"], "imageData": row["image_data"], "rating": row["value"], "feedback": row["feedback"]}
        for row in rows
    ]}
    if _is_platform_admin(connection, user_id) or _community_role(connection, community_id, user_id) == "Admin":
        responses = connection.execute(
            """SELECT r.player_id,r.value,r.feedback,u.name FROM matchday_player_ratings r
            JOIN users u ON u.id=r.user_id WHERE r.request_id=? ORDER BY u.name COLLATE NOCASE""",
            (request["id"],),
        ).fetchall()
        response["results"] = [{"playerId": row["player_id"], "rating": row["value"], "feedback": row["feedback"], "member": row["name"]} for row in responses]
    return response


def submit_matchday_ratings(connection, user_id, community_id, fixture_id, data):
    require_object(data)
    review = get_matchday_ratings(connection, user_id, community_id, fixture_id)
    submitted = data.get("ratings")
    if not isinstance(submitted, list) or len(submitted) != len(review["players"]):
        raise ApiError(400, "invalid_ratings", "Rate every player before submitting your matchday review.")
    expected = {player["id"] for player in review["players"]}
    values = {}
    for entry in submitted:
        if not isinstance(entry, dict) or not isinstance(entry.get("player_id"), str) or entry["player_id"] not in expected or entry["player_id"] in values:
            raise ApiError(400, "invalid_ratings", "The review includes an invalid or duplicate player.")
        values[entry["player_id"]] = (
            integer(entry, "value", minimum=1, maximum=10, label="Rating"),
            text(entry, "feedback", required=False, maximum=500, default="", label="Feedback") or "",
        )
    now = iso()
    for player_id, (value, feedback) in values.items():
        connection.execute(
            """INSERT INTO matchday_player_ratings(request_id,player_id,user_id,value,feedback,created_at)
            VALUES(?,?,?,?,?,?) ON CONFLICT(request_id,player_id,user_id) DO UPDATE SET
            value=excluded.value,feedback=excluded.feedback,created_at=excluded.created_at""",
            (review["id"], player_id, user_id, value, feedback, now),
        )
    return {"submitted": True, "playerCount": len(values)}


def create_team(connection, user_id, data):
    require_object(data)
    community_id = valid_id(data.get("community_id", ""), "community_id")
    _community(connection, community_id)
    _require_community_admin(connection, community_id, user_id)
    if connection.execute("SELECT 1 FROM teams WHERE community_id=?", (community_id,)).fetchone():
        raise ApiError(409, "team_exists", "A team already exists for this community.")
    name = text(data, "name", minimum=2, maximum=64, label="Club or team name")
    age_group = text(data, "age_group", minimum=2, maximum=32, label="Age group")
    league = text(data, "league", minimum=2, maximum=64, label="League")
    coach = text(data, "coach", minimum=2, maximum=64, label="Coach")
    formation = choice(data, "formation", FORMATIONS, required=False, default="4-3-3", label="Formation")
    team_id = new_id("team")
    now = iso()
    connection.execute(
        """INSERT INTO teams
        (id, community_id, name, age_group, league, mark, accent, coach, rank, record_w, record_d,
         record_l, form_json, formation, starting_xi_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'lime', ?, '—', 0, 0, 0, '[]', ?, '[]', ?)""",
        (team_id, community_id, name, age_group, league, _mark(name), coach, formation, now),
    )
    return team_dict(connection, connection.execute(
        "SELECT * FROM teams WHERE id = ?", (team_id,)
    ).fetchone(), user_id)


def join_community(connection, user_id, community_id):
    community = _community(connection, valid_id(community_id, "community_id"))
    existing = connection.execute(
        "SELECT 1 FROM community_members WHERE community_id = ? AND user_id = ?",
        (community["id"], user_id),
    ).fetchone()
    if existing:
        return community_dict(connection, community, user_id)
    # Platform admins can enter any community to administer it; ordinary users
    # must be approved by a community admin, even when it is public.
    if _is_platform_admin(connection, user_id):
        with transaction(connection):
            connection.execute(
                "INSERT INTO community_members (community_id, user_id, role, joined_at) VALUES (?, ?, 'Member', ?)",
                (community["id"], user_id, iso()),
            )
            connection.execute("UPDATE community_join_requests SET status='approved',decided_at=?,decided_by=? WHERE community_id=? AND user_id=? AND status='pending'", (iso(), user_id, community["id"], user_id))
            connection.execute(
                "UPDATE communities SET member_count = member_count + 1 WHERE id = ?",
                (community["id"],),
            )
        return community_dict(connection, _community(connection, community["id"]), user_id)
    return request_community_join(connection, user_id, community["id"])


def request_community_join(connection, user_id, community_id):
    community_id = valid_id(community_id, "community_id")
    community = _community(connection, community_id)
    if community["privacy"] != "Public":
        raise ApiError(403, "invite_required", "This private community requires an invitation.")
    if connection.execute("SELECT 1 FROM community_members WHERE community_id=? AND user_id=?", (community_id, user_id)).fetchone():
        return community_dict(connection, community, user_id)
    existing = connection.execute("SELECT status FROM community_join_requests WHERE community_id=? AND user_id=?", (community_id, user_id)).fetchone()
    if existing is None:
        connection.execute("INSERT INTO community_join_requests(community_id,user_id,status,requested_at) VALUES(?,?,'pending',?)", (community_id, user_id, iso()))
    elif existing["status"] == "denied":
        connection.execute("UPDATE community_join_requests SET status='pending',requested_at=?,decided_at=NULL,decided_by=NULL WHERE community_id=? AND user_id=?", (iso(), community_id, user_id))
    return community_dict(connection, community, user_id)


def list_community_join_requests(connection, actor_id, community_id):
    community_id = valid_id(community_id, "community_id")
    _community(connection, community_id)
    _require_community_admin(connection, community_id, actor_id)
    rows = connection.execute("""SELECT r.user_id,r.status,r.requested_at,u.name,u.email,u.avatar_tone
        FROM community_join_requests r JOIN users u ON u.id=r.user_id
        WHERE r.community_id=? AND r.status='pending' ORDER BY r.requested_at ASC""", (community_id,)).fetchall()
    return [{"userId": row["user_id"], "name": row["name"], "email": row["email"], "avatarTone": row["avatar_tone"], "status": row["status"], "requestedAt": row["requested_at"]} for row in rows]


def decide_community_join_request(connection, actor_id, community_id, applicant_id, data):
    require_object(data)
    community_id = valid_id(community_id, "community_id")
    applicant_id = valid_id(applicant_id, "applicant_id")
    _community(connection, community_id)
    _require_community_admin(connection, community_id, actor_id)
    decision = choice(data, "decision", {"approve", "deny"}, label="Decision")
    request = connection.execute("SELECT status FROM community_join_requests WHERE community_id=? AND user_id=?", (community_id, applicant_id)).fetchone()
    if not request or request["status"] != "pending":
        raise ApiError(404, "not_found", "Pending join request not found.")
    with transaction(connection):
        status = "approved" if decision == "approve" else "denied"
        connection.execute("UPDATE community_join_requests SET status=?,decided_at=?,decided_by=? WHERE community_id=? AND user_id=?", (status, iso(), actor_id, community_id, applicant_id))
        if decision == "approve":
            connection.execute("INSERT OR IGNORE INTO community_members(community_id,user_id,role,joined_at) VALUES(?,?,'Member',?)", (community_id, applicant_id, iso()))
            connection.execute("UPDATE communities SET member_count=(SELECT COUNT(*) FROM community_members WHERE community_id=?) WHERE id=?", (community_id, community_id))
    return {"communityId": community_id, "userId": applicant_id, "status": status}


def add_community_member(connection, actor_id, community_id, data):
    require_object(data)
    community_id = valid_id(community_id, "community_id")
    community = _community(connection, community_id)
    _require_community_admin(connection, community_id, actor_id)
    address = email(data).lower()
    user = connection.execute(
        "SELECT id,email_verified FROM users WHERE email=? COLLATE NOCASE", (address,)
    ).fetchone()
    if user is None or not user["email_verified"]:
        raise ApiError(404, "registered_user_not_found", "No verified account was found for that email address.")
    existing = connection.execute(
        "SELECT 1 FROM community_members WHERE community_id=? AND user_id=?", (community_id, user["id"])
    ).fetchone()
    if existing:
        raise ApiError(409, "already_member", "That user is already a member of this community.")
    with transaction(connection):
        connection.execute(
            "INSERT INTO community_members(community_id,user_id,role,joined_at) VALUES(?,?,'Member',?)",
            (community_id, user["id"], iso()),
        )
        connection.execute("UPDATE community_join_requests SET status='approved',decided_at=?,decided_by=? WHERE community_id=? AND user_id=? AND status='pending'", (iso(), actor_id, community_id, user["id"]))
        connection.execute("UPDATE communities SET member_count=member_count+1 WHERE id=?", (community_id,))
    return next(member for member in list_community_members(connection, actor_id, community_id) if member["id"] == user["id"])


def create_community_invite(connection, actor_id, community_id):
    community_id = valid_id(community_id, "community_id")
    community = _community(connection, community_id)
    _require_community_admin(connection, community_id, actor_id)
    token = new_token()
    expires_at = iso(utc_now() + timedelta(days=7))
    connection.execute(
        "INSERT INTO community_invites(token_hash,community_id,created_by,expires_at,created_at) VALUES(?,?,?,?,?)",
        (hash_token(token), community_id, actor_id, expires_at, iso()),
    )
    return {"token": token, "url": f"{config.APP_BASE_URL}/?community_invite={token}", "communityId": community_id, "communityName": community["name"], "expiresAt": expires_at}


def accept_community_invite(connection, user_id, data):
    require_object(data)
    token = text(data, "token", maximum=256, label="Invitation token")
    invite = connection.execute(
        "SELECT community_id,expires_at,created_by FROM community_invites WHERE token_hash=?", (hash_token(token),)
    ).fetchone()
    if invite is None or parse_iso(invite["expires_at"]) <= utc_now():
        if invite is not None:
            connection.execute("DELETE FROM community_invites WHERE token_hash=?", (hash_token(token),))
        raise ApiError(404, "invite_not_found", "This community invitation is invalid or has expired.")
    community_id = invite["community_id"]
    existing = connection.execute(
        "SELECT 1 FROM community_members WHERE community_id=? AND user_id=?", (community_id, user_id)
    ).fetchone()
    if not existing:
        with transaction(connection):
            connection.execute(
                "INSERT INTO community_members(community_id,user_id,role,joined_at) VALUES(?,?,'Member',?)",
                (community_id, user_id, iso()),
            )
            connection.execute("UPDATE community_join_requests SET status='approved',decided_at=?,decided_by=? WHERE community_id=? AND user_id=? AND status='pending'", (iso(), invite["created_by"], community_id, user_id))
            connection.execute("UPDATE communities SET member_count=member_count+1 WHERE id=?", (community_id,))
    return community_dict(connection, _community(connection, community_id), user_id)


def _community_deletion_timeout(connection):
    row = connection.execute(
        "SELECT value FROM meta WHERE key='community_deletion_timeout_days'"
    ).fetchone()
    try:
        return max(1, min(30, int(row["value"]))) if row else 7
    except (ValueError, TypeError):
        return 7


def _global_poll_retention_days(connection):
    row = connection.execute("SELECT value FROM meta WHERE key='poll_retention_days'").fetchone()
    try:
        return max(1, min(30, int(row["value"]))) if row else 7
    except (ValueError, TypeError):
        return 7


def get_community_poll_retention(connection, user_id, community_id):
    community_id = valid_id(community_id, "community_id")
    _community(connection, community_id)
    if not _is_platform_admin(connection, user_id) and _community_role(connection, community_id, user_id) != "Admin":
        raise ApiError(403, "forbidden", "Only this community's admins or the super admin can view its poll retention setting.")
    row = connection.execute("SELECT poll_retention_days FROM community_settings WHERE community_id=?", (community_id,)).fetchone()
    global_days = _global_poll_retention_days(connection)
    return {"days": int(row["poll_retention_days"]) if row else global_days, "globalDays": global_days, "custom": row is not None}


def set_community_poll_retention(connection, user_id, community_id, data):
    require_object(data)
    community_id = valid_id(community_id, "community_id")
    _community(connection, community_id)
    if not _is_platform_admin(connection, user_id) and _community_role(connection, community_id, user_id) != "Admin":
        raise ApiError(403, "forbidden", "Only this community's admins or the super admin can change its poll retention setting.")
    days = integer(data, "days", minimum=1, maximum=30, label="Poll retention")
    connection.execute(
        """INSERT INTO community_settings(community_id,poll_retention_days,updated_by,updated_at) VALUES(?,?,?,?)
        ON CONFLICT(community_id) DO UPDATE SET poll_retention_days=excluded.poll_retention_days,updated_by=excluded.updated_by,updated_at=excluded.updated_at""",
        (community_id, days, user_id, iso()),
    )
    return {"communityId": community_id, "days": days, "custom": True}


def set_global_poll_retention(connection, user_id, data):
    require_object(data)
    if not _is_platform_admin(connection, user_id):
        raise ApiError(403, "forbidden", "Only the super admin can change the default poll retention setting.")
    days = integer(data, "days", minimum=1, maximum=30, label="Poll retention")
    connection.execute(
        "INSERT INTO meta(key,value) VALUES('poll_retention_days',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(days),),
    )
    return {"days": days}


def set_global_app_theme(connection, user_id, data):
    require_object(data)
    if not _is_platform_admin(connection, user_id):
        raise ApiError(403, "forbidden", "Only the super admin can change the app theme.")
    theme = choice(data, "theme", {"light", "dark"}, label="App theme")
    connection.execute(
        "INSERT INTO meta(key,value) VALUES('app_theme',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (theme,),
    )
    return {"theme": theme}


def set_community_profile_theme(connection, user_id, community_id, data):
    require_object(data)
    community_id = valid_id(community_id, "community_id")
    _community(connection, community_id)
    if not _is_platform_admin(connection, user_id) and _community_role(connection, community_id, user_id) != "Admin":
        raise ApiError(403, "forbidden", "Only this community's admins can change its profile theme.")
    theme = choice(data, "theme", {"light", "dark"}, label="Community profile theme")
    connection.execute(
        """INSERT INTO community_settings(community_id,poll_retention_days,profile_theme,updated_by,updated_at)
        VALUES(?,?,?,?,?) ON CONFLICT(community_id) DO UPDATE SET
        profile_theme=excluded.profile_theme,updated_by=excluded.updated_by,updated_at=excluded.updated_at""",
        (community_id, _global_poll_retention_days(connection), theme, user_id, iso()),
    )
    return {"communityId": community_id, "profileTheme": theme}


def _community_deletion_dict(connection, request):
    community = connection.execute("SELECT name FROM communities WHERE id=?", (request["community_id"],)).fetchone()
    requester = connection.execute("SELECT name,email FROM users WHERE id=?", (request["requested_by"],)).fetchone()
    approvals = connection.execute(
        """SELECT u.id,u.name,u.email,a.approved_at FROM community_deletion_approvals a
        JOIN users u ON u.id=a.admin_user_id WHERE a.request_id=? ORDER BY u.name COLLATE NOCASE""",
        (request["id"],),
    ).fetchall()
    return {
        "id": request["id"],
        "communityId": request["community_id"],
        "communityName": community["name"] if community else "Deleted community",
        "requestedBy": {"name": requester["name"], "email": requester["email"]} if requester else None,
        "status": request["status"],
        "createdAt": request["created_at"],
        "superAdminDueAt": request["super_admin_due_at"],
        "adminApprovals": [dict(row) | {"approved": row["approved_at"] is not None} for row in approvals],
        "approvalCount": sum(1 for row in approvals if row["approved_at"] is not None),
        "requiredApprovalCount": len(approvals),
    }


def _delete_community_data(connection, community_id):
    team_ids = [row["id"] for row in connection.execute("SELECT id FROM teams WHERE community_id=?", (community_id,)).fetchall()]
    connection.execute("DELETE FROM posts WHERE community_id=?", (community_id,))
    if team_ids:
        connection.executemany("DELETE FROM teams WHERE id=?", [(team_id,) for team_id in team_ids])
    connection.execute("DELETE FROM communities WHERE id=?", (community_id,))


def request_community_deletion(connection, user_id, community_id):
    community_id = valid_id(community_id, "community_id")
    community = _community(connection, community_id)
    if _community_role(connection, community_id, user_id) != "Admin":
        raise ApiError(403, "forbidden", "A community admin must request this deletion.")
    pending = connection.execute(
        "SELECT 1 FROM community_deletion_requests WHERE community_id=? AND status IN ('pending_admins','pending_super_admin')",
        (community_id,),
    ).fetchone()
    if pending:
        raise ApiError(409, "deletion_already_requested", "A deletion request is already open for this community.")
    admins = connection.execute(
        "SELECT user_id FROM community_members WHERE community_id=? AND role='Admin' ORDER BY user_id",
        (community_id,),
    ).fetchall()
    request_id = new_id("delete-request")
    now = iso()
    with transaction(connection):
        connection.execute(
            "INSERT INTO community_deletion_requests(id,community_id,requested_by,status,created_at) VALUES(?,?,?,'pending_admins',?)",
            (request_id, community_id, user_id, now),
        )
        for admin in admins:
            connection.execute(
                "INSERT INTO community_deletion_approvals(request_id,admin_user_id,approved_at) VALUES(?,?,?)",
                (request_id, admin["user_id"], now if admin["user_id"] == user_id else None),
            )
        approved_count = 1
        if approved_count == len(admins):
            due_at = iso(utc_now() + timedelta(days=_community_deletion_timeout(connection)))
            connection.execute(
                "UPDATE community_deletion_requests SET status='pending_super_admin',super_admin_due_at=? WHERE id=?",
                (due_at, request_id),
            )
    row = connection.execute("SELECT * FROM community_deletion_requests WHERE id=?", (request_id,)).fetchone()
    return _community_deletion_dict(connection, row)


def get_community_deletion_request(connection, user_id, community_id):
    community_id = valid_id(community_id, "community_id")
    _community(connection, community_id)
    if _community_role(connection, community_id, user_id) != "Admin" and not _is_platform_admin(connection, user_id):
        raise ApiError(403, "forbidden", "Only community admins can view deletion requests.")
    row = connection.execute(
        "SELECT * FROM community_deletion_requests WHERE community_id=? ORDER BY created_at DESC LIMIT 1",
        (community_id,),
    ).fetchone()
    return _community_deletion_dict(connection, row) if row else None


def approve_community_deletion(connection, user_id, community_id, request_id):
    community_id = valid_id(community_id, "community_id")
    request_id = valid_id(request_id, "request_id")
    _community(connection, community_id)
    if _community_role(connection, community_id, user_id) != "Admin":
        raise ApiError(403, "forbidden", "Only this community’s admins can approve its deletion.")
    request = connection.execute(
        "SELECT * FROM community_deletion_requests WHERE id=? AND community_id=?",
        (request_id, community_id),
    ).fetchone()
    if request is None:
        raise ApiError(404, "not_found", "That deletion request does not exist.")
    if request["status"] != "pending_admins":
        raise ApiError(409, "deletion_not_pending_admins", "This request is no longer waiting for community admin approvals.")
    approval = connection.execute(
        "SELECT approved_at FROM community_deletion_approvals WHERE request_id=? AND admin_user_id=?",
        (request_id, user_id),
    ).fetchone()
    if approval is None:
        raise ApiError(403, "not_required_approver", "You were not a community admin when this request was opened.")
    with transaction(connection):
        connection.execute(
            "UPDATE community_deletion_approvals SET approved_at=COALESCE(approved_at,?) WHERE request_id=? AND admin_user_id=?",
            (iso(), request_id, user_id),
        )
        remaining = connection.execute(
            "SELECT COUNT(*) AS n FROM community_deletion_approvals WHERE request_id=? AND approved_at IS NULL",
            (request_id,),
        ).fetchone()["n"]
        if remaining == 0:
            due_at = iso(utc_now() + timedelta(days=_community_deletion_timeout(connection)))
            connection.execute(
                "UPDATE community_deletion_requests SET status='pending_super_admin',super_admin_due_at=? WHERE id=?",
                (due_at, request_id),
            )
    return _community_deletion_dict(connection, connection.execute(
        "SELECT * FROM community_deletion_requests WHERE id=?", (request_id,)
    ).fetchone())


def get_super_admin_deletion_panel(connection, user_id):
    if not _is_platform_admin(connection, user_id):
        raise ApiError(403, "forbidden", "Only the super admin can access these settings.")
    _expire_community_deletions(connection)
    requests = connection.execute(
        "SELECT * FROM community_deletion_requests WHERE status IN ('pending_admins','pending_super_admin') ORDER BY created_at ASC"
    ).fetchall()
    return {
        "timeoutDays": _community_deletion_timeout(connection),
        "pollRetentionDays": _global_poll_retention_days(connection),
        "appTheme": (connection.execute("SELECT value FROM meta WHERE key='app_theme'").fetchone() or {"value": "light"})["value"],
        "requests": [_community_deletion_dict(connection, row) for row in requests],
    }


def set_community_deletion_timeout(connection, user_id, data):
    require_object(data)
    if not _is_platform_admin(connection, user_id):
        raise ApiError(403, "forbidden", "Only the super admin can change this setting.")
    days = integer(data, "days", minimum=1, maximum=30, label="Approval window")
    connection.execute(
        "INSERT INTO meta(key,value) VALUES('community_deletion_timeout_days',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(days),),
    )
    return {"timeoutDays": days}


def decide_community_deletion(connection, user_id, request_id, data):
    require_object(data)
    if not _is_platform_admin(connection, user_id):
        raise ApiError(403, "forbidden", "Only the super admin can decide community deletions.")
    _expire_community_deletions(connection)
    decision = choice(data, "decision", {"approve", "deny"}, label="Decision")
    request = connection.execute(
        "SELECT * FROM community_deletion_requests WHERE id=?", (valid_id(request_id, "request_id"),)
    ).fetchone()
    if request is None:
        raise ApiError(404, "not_found", "That deletion request does not exist.")
    if request["status"] != "pending_super_admin":
        raise ApiError(409, "deletion_not_ready", "All community admins must approve before super-admin review.")
    if decision == "approve":
        with transaction(connection):
            _delete_community_data(connection, request["community_id"])
        return {"id": request_id, "status": "deleted"}
    connection.execute(
        "UPDATE community_deletion_requests SET status='denied',super_admin_due_at=NULL WHERE id=?",
        (request_id,),
    )
    return {"id": request_id, "status": "denied"}


def _expire_community_deletions(connection):
    request_ids = connection.execute(
        "SELECT id,community_id FROM community_deletion_requests WHERE status='pending_super_admin' AND super_admin_due_at<=?",
        (iso(),),
    ).fetchall()
    for request in request_ids:
        with transaction(connection):
            _delete_community_data(connection, request["community_id"])
    return len(request_ids)


def expire_community_deletions():
    with db.connect() as connection:
        return _expire_community_deletions(connection)


def list_community_messages(connection, user_id, community_id):
    community_id = valid_id(community_id, "community_id")
    _community(connection, community_id)
    _ensure_member(connection, community_id, user_id)
    rows = connection.execute("""SELECT m.rowid AS message_rowid,m.id,m.text,m.created_at,m.edited_at,u.id AS user_id,u.name,u.avatar_tone
        FROM community_messages m JOIN users u ON u.id=m.user_id WHERE m.community_id=?
        ORDER BY m.created_at DESC,m.rowid DESC LIMIT 100""", (community_id,)).fetchall()
    if rows:
        connection.execute(
            """INSERT INTO community_message_reads(community_id,user_id,last_read_rowid,updated_at)
            VALUES(?,?,?,?) ON CONFLICT(community_id,user_id) DO UPDATE SET
            last_read_rowid=MAX(last_read_rowid,excluded.last_read_rowid),updated_at=excluded.updated_at""",
            (community_id, user_id, rows[0]["message_rowid"], iso()),
        )
    return [{"id": r["id"], "text": r["text"], "createdAt": r["created_at"], "editedAt": r["edited_at"],
             "author": {"id": r["user_id"], "name": r["name"], "initials": initials(r["name"]), "avatarTone": r["avatar_tone"]}}
            for r in reversed(rows)]


def create_community_message(connection, user_id, community_id, data):
    require_object(data)
    community_id = valid_id(community_id, "community_id")
    _community(connection, community_id)
    _ensure_member(connection, community_id, user_id)
    wait = limiter.retry_after(f"community-message:{user_id}", 30, 60)
    if wait:
        raise ApiError(429, "rate_limited", "You are sending messages too quickly. Try again shortly.", {"retryAfter": wait})
    body = text(data, "text", minimum=1, maximum=1000, label="Message")
    mentions = data.get("mentions", [])
    if not isinstance(mentions, list) or len(mentions) > 50 or any(not isinstance(value, dict) for value in mentions):
        raise ApiError(400, "invalid_field", "Mentions must identify community members selected with an @ mention.")
    author = connection.execute("SELECT name FROM users WHERE id=?", (user_id,)).fetchone()
    valid_mentions = set()
    for mention in mentions:
        mentioned_id = mention.get("id")
        if not isinstance(mentioned_id, str):
            raise ApiError(400, "invalid_field", "Each @ mention must identify a community member.")
        member = connection.execute("SELECT 1 FROM community_members WHERE community_id=? AND user_id=?", (community_id, mentioned_id)).fetchone()
        if not member:
            raise ApiError(400, "invalid_field", "You can only tag members of this community.")
        target = connection.execute("SELECT name FROM users WHERE id=?", (mentioned_id,)).fetchone()
        if mention.get("name") != target["name"] or f"@{target['name']}" not in body:
            raise ApiError(400, "invalid_field", "Each selected member must be named in the chat message with @.")
        if mentioned_id != user_id:
            valid_mentions.add(mentioned_id)
    message_id = new_id("message")
    created_at = iso()
    connection.execute("INSERT INTO community_messages(id,community_id,user_id,text,created_at) VALUES(?,?,?,?,?)", (message_id, community_id, user_id, body, created_at))
    for mentioned_id in valid_mentions:
        _create_notification(
            connection, mentioned_id, icon="message", title="You were mentioned",
            body=f"{author['name']} tagged you in a community chat message.",
            route=f"#/community/{community_id}", created_at=created_at,
            community_id=community_id, kind="mention",
            source_key=f"mention:{message_id}:{mentioned_id}",
        )
    limiter.record(f"community-message:{user_id}", 60)
    return next(message for message in list_community_messages(connection, user_id, community_id) if message["id"] == message_id)


def update_community_message(connection, user_id, community_id, message_id, data):
    require_object(data)
    community_id = valid_id(community_id, "community_id")
    message_id = valid_id(message_id, "message_id")
    _community(connection, community_id)
    _ensure_member(connection, community_id, user_id)
    row = connection.execute("SELECT user_id FROM community_messages WHERE id=? AND community_id=?", (message_id, community_id)).fetchone()
    if not row:
        raise ApiError(404, "not_found", "Message not found.")
    if row["user_id"] != user_id:
        raise ApiError(403, "forbidden", "You can only edit your own messages.")
    body = text(data, "text", minimum=1, maximum=1000, label="Message")
    connection.execute("UPDATE community_messages SET text=?,edited_at=? WHERE id=? AND community_id=?", (body, iso(), message_id, community_id))
    return next(message for message in list_community_messages(connection, user_id, community_id) if message["id"] == message_id)


def delete_community_message(connection, user_id, community_id, message_id):
    community_id = valid_id(community_id, "community_id")
    message_id = valid_id(message_id, "message_id")
    _community(connection, community_id)
    _ensure_member(connection, community_id, user_id)
    row = connection.execute("SELECT user_id FROM community_messages WHERE id=? AND community_id=?", (message_id, community_id)).fetchone()
    if not row:
        raise ApiError(404, "not_found", "Message not found.")
    if row["user_id"] != user_id:
        raise ApiError(403, "forbidden", "You can only delete your own messages.")
    connection.execute("DELETE FROM community_messages WHERE id=? AND community_id=?", (message_id, community_id))
    return {"id": message_id, "deleted": True}


def list_community_members(connection, user_id, community_id):
    community_id = valid_id(community_id, "community_id")
    _community(connection, community_id)
    if not _is_platform_admin(connection, user_id):
        _ensure_member(connection, community_id, user_id)
    rows = connection.execute("""SELECT u.id,u.name,u.email,u.avatar_tone,m.role,m.joined_at
        FROM community_members m JOIN users u ON u.id=m.user_id WHERE m.community_id=?
        ORDER BY CASE m.role WHEN 'Admin' THEN 0 ELSE 1 END,u.name COLLATE NOCASE""", (community_id,)).fetchall()
    return [{"id": row["id"], "name": row["name"], "email": row["email"], "role": row["role"], "joinedAt": row["joined_at"], "avatarTone": row["avatar_tone"]} for row in rows]


def update_community_member(connection, user_id, community_id, member_id, data):
    require_object(data)
    community_id = valid_id(community_id, "community_id")
    member_id = valid_id(member_id, "user_id")
    _community(connection, community_id)
    _require_community_admin(connection, community_id, user_id)
    role = choice(data, "role", {"Admin", "Member"}, label="Community role")
    target = connection.execute("SELECT role FROM community_members WHERE community_id=? AND user_id=?", (community_id, member_id)).fetchone()
    if target is None:
        raise ApiError(404, "not_found", "That user is not a member of this community.")
    if target["role"] == "Admin" and role != "Admin":
        admins = connection.execute("SELECT COUNT(*) AS n FROM community_members WHERE community_id=? AND role='Admin'", (community_id,)).fetchone()["n"]
        if admins <= 1:
            raise ApiError(409, "last_admin", "A community must keep at least one admin.")
    connection.execute("UPDATE community_members SET role=? WHERE community_id=? AND user_id=?", (role, community_id, member_id))
    return next(member for member in list_community_members(connection, user_id, community_id) if member["id"] == member_id)


def remove_community_member(connection, user_id, community_id, member_id):
    community_id = valid_id(community_id, "community_id")
    member_id = valid_id(member_id, "user_id")
    _community(connection, community_id)
    _require_community_admin(connection, community_id, user_id)
    target = connection.execute(
        "SELECT role FROM community_members WHERE community_id=? AND user_id=?",
        (community_id, member_id),
    ).fetchone()
    if target is None:
        raise ApiError(404, "not_found", "That user is not a member of this community.")
    if target["role"] == "Admin":
        raise ApiError(409, "admin_must_be_demoted", "Demote this community admin before removing them.")
    with transaction(connection):
        connection.execute(
            "DELETE FROM community_members WHERE community_id=? AND user_id=?",
            (community_id, member_id),
        )
        connection.execute(
            "UPDATE communities SET member_count=(SELECT COUNT(*) FROM community_members WHERE community_id=?) WHERE id=?",
            (community_id, community_id),
        )
    return {"removed": True, "communityId": community_id, "userId": member_id}


# ---------- Team management ----------

STAT_FIELDS = {
    # api field -> (column, label, maximum)
    "goals": ("goals", "Goals", 999),
    "assists": ("assists", "Assists", 999),
    "apps": ("apps", "Appearances", 999),
    "starts": ("starts", "Starts", 999),
    "minutes": ("minutes", "Minutes played", 99999),
    "yellow_cards": ("yellow_cards", "Yellow cards", 99),
    "red_cards": ("red_cards", "Red cards", 99),
    "clean_sheets": ("clean_sheets", "Clean sheets", 999),
    "saves": ("saves", "Saves", 9999),
}
MINUTES_PER_APPEARANCE_LIMIT = 120


def _profile_updates(data, *, creating):
    """Validate the optional profile and season-stat fields from a request body.

    Returns {column: value} for fields that were sent. Unknown keys are ignored,
    so clients can never write columns such as rating_sum by naming them.
    """
    updates = {}
    if "date_of_birth" in data:
        updates["date_of_birth"] = iso_date(
            data, "date_of_birth", label="Date of birth", minimum_age=5, maximum_age=60
        )
    if "height_cm" in data:
        updates["height_cm"] = integer(
            data, "height_cm", required=False, minimum=100, maximum=230, label="Height"
        )
    if "bio" in data:
        value = data.get("bio")
        updates["bio"] = (
            "" if value is None else text(data, "bio", required=False, maximum=400, default="", label="Bio")
        )
    for field, (column, label, maximum) in STAT_FIELDS.items():
        if field in data:
            updates[column] = integer(data, field, minimum=0, maximum=maximum, label=label)
    return updates


def _insert_player_record(connection, team, player_data, user_id):
    extras = _profile_updates(player_data, creating=True)
    values = {"date_of_birth": None, "height_cm": None, "bio": "", **{column: 0 for column, _label, _max in STAT_FIELDS.values()}, **extras}
    _check_stat_consistency(values)
    player_id = new_id("player")
    order = connection.execute("SELECT COALESCE(MAX(sort_order),0)+1 AS next FROM players WHERE team_id=?", (team["id"],)).fetchone()["next"]
    try:
        connection.execute("""INSERT INTO players
            (id,team_id,name,number,pos,group_name,foot,status,sort_order,date_of_birth,height_cm,bio,
             goals,assists,apps,starts,minutes,yellow_cards,red_cards,clean_sheets,saves,image_data,user_id)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (player_id,team["id"],player_data["name"],player_data["number"],player_data["pos"],group_for_position(player_data["pos"]),
             player_data["foot"],player_data["status"],order,values["date_of_birth"],values["height_cm"],values["bio"],values["goals"],
             values["assists"],values["apps"],values["starts"],values["minutes"],values["yellow_cards"],values["red_cards"],
             values["clean_sheets"],values["saves"],player_data.get("image_data"),user_id))
    except sqlite3.IntegrityError:
        raise ApiError(409,"number_taken","That shirt number is already taken, or this account already has a player profile in the team.")
    if player_data.get("xi_slot") is not None:
        try:
            slot = int(player_data["xi_slot"])
        except (TypeError, ValueError):
            raise ApiError(400,"invalid_lineup","Choose a valid Starting XI position.")
        if not 0 <= slot < 11:
            raise ApiError(400,"invalid_lineup","Choose a valid Starting XI position.")
        lineup = _json_list(team["starting_xi_json"])
        lineup = (lineup + [None] * 11)[:11]
        if player_id in lineup:
            old_slot = lineup.index(player_id)
            lineup[old_slot], lineup[slot] = lineup[slot], lineup[old_slot]
        else:
            lineup[slot] = player_id
        connection.execute("UPDATE teams SET starting_xi_json=? WHERE id=?",(json.dumps(lineup),team["id"]))
    return player_id


def _check_stat_consistency(values):
    """Reject stat lines that cannot be true, using the merged final values."""
    apps = int(values["apps"])
    if int(values["starts"]) > apps:
        raise ApiError(400, "invalid_stats", "Starts cannot be higher than appearances.", {"starts": "range"})
    if int(values["clean_sheets"]) > apps:
        raise ApiError(400, "invalid_stats", "Clean sheets cannot be higher than appearances.", {"clean_sheets": "range"})
    if int(values["minutes"]) > apps * MINUTES_PER_APPEARANCE_LIMIT:
        raise ApiError(
            400,
            "invalid_stats",
            f"Minutes played cannot exceed {MINUTES_PER_APPEARANCE_LIMIT} per appearance.",
            {"minutes": "range"},
        )


def create_player(connection, user_id, data):
    require_object(data)
    team = _team_for_user(connection, user_id, valid_id(data["team_id"], "team_id") if data.get("team_id") else None, manage=True)
    name = text(data, "name", minimum=2, maximum=50, label="Name")
    email_value = email_field(data, "email")
    number = integer(data, "number", minimum=1, maximum=99, label="Shirt number")
    pos = choice(data, "pos", POSITIONS, label="Position")
    foot = choice(data, "foot", FEET, required=False, default="Right", label="Preferred foot")
    status = choice(data, "status", STATUSES, required=False, default="available", label="Availability")
    image_data = _image_data(data.get("image_data"), "Player photo") if "image_data" in data else None
    account = connection.execute("SELECT * FROM users WHERE email=? COLLATE NOCASE",(email_value,)).fetchone()
    player_data = {"name":name,"number":number,"pos":pos,"foot":foot,"status":status,"image_data":image_data,**data}
    if account and not account["email_verified"]:
        raise ApiError(409,"email_not_verified","This account exists but has not verified its email yet. Ask the player to verify it before adding them.")
    if not account:
        token = new_token()
        expires = iso(utc_now() + timedelta(days=7))
        connection.execute("DELETE FROM player_invites WHERE email=? COLLATE NOCASE AND team_id=?",(email_value,team["id"]))
        connection.execute("INSERT INTO player_invites(token_hash,email,team_id,invited_by,player_data_json,expires_at,created_at) VALUES(?,?,?,?,?,?,?)",
            (hash_token(token),email_value,team["id"],user_id,json.dumps(player_data),expires,iso()))
        try:
            send_email(email_value,"Join your Touchline community",
                f"{name} has been invited to join the squad. Create your account using this link; after verifying your email, your player profile will be added automatically:\n\n{config.APP_BASE_URL}/?player_invite={token}\n")
        except MailDeliveryError as error:
            connection.execute("DELETE FROM player_invites WHERE token_hash=?",(hash_token(token),))
            message = "Email delivery is not configured. Add SMTP settings and restart the server." if str(error)=="not_configured" else "The email provider rejected or could not deliver this message. Check SMTP settings and server logs."
            raise ApiError(503,"email_unavailable",message)
        return {"invitationPending":True,"email":email_value,"name":name,"expiresAt":expires}
    if team["community_id"]:
        connection.execute("INSERT OR IGNORE INTO community_members(community_id,user_id,role,joined_at) VALUES(?,?,'Member',?)",(team["community_id"],account["id"],iso()))
    player_id = _insert_player_record(connection,team,player_data,account["id"])
    return _player_dict(connection, _player(connection, player_id), user_id)


def update_player(connection, user_id, player_id, data):
    require_object(data)
    player = _player(connection, valid_id(player_id, "player_id"))
    team = connection.execute("SELECT * FROM teams WHERE id=?", (player["team_id"],)).fetchone()
    _require_community_admin(connection, team["community_id"], user_id)
    linked_existing_account = False
    if data.get("account_id"):
        if player["user_id"]:
            raise ApiError(409, "player_already_registered", "This player already has a registered account.")
        if str(data.get("email") or "").strip():
            raise ApiError(400, "choose_one_account_method", "Choose a registered community member or enter an email for a new signup.")
        account_id = valid_id(data["account_id"], "account_id")
        account = connection.execute(
            """SELECT u.* FROM users u JOIN community_members cm ON cm.user_id=u.id
            WHERE u.id=? AND cm.community_id=? AND u.email_verified=1""",
            (account_id, team["community_id"]),
        ).fetchone()
        if not account:
            raise ApiError(404, "community_member_not_found", "Choose a verified member of this community.")
        if connection.execute("SELECT 1 FROM players WHERE team_id=? AND user_id=?", (team["id"], account_id)).fetchone():
            raise ApiError(409, "player_profile_exists", "This member already has a player profile in the squad.")
        connection.execute("UPDATE players SET user_id=?,name=? WHERE id=?", (account_id, account["name"], player["id"]))
        player = _player(connection, player["id"])
        data = {key: value for key, value in data.items() if key not in ("account_id", "email", "name")}
        linked_existing_account = True
    if "email" in data and str(data.get("email") or "").strip():
        if player["user_id"]:
            raise ApiError(409, "player_already_registered", "This player already has a registered account; no email is needed.")
        email_value = email_field({"email": str(data["email"]).strip()}, "email")
        account = connection.execute("SELECT * FROM users WHERE email=? COLLATE NOCASE", (email_value,)).fetchone()
        if account:
            if not account["email_verified"]:
                raise ApiError(409, "email_not_verified", "This account exists but has not verified its email yet. Ask the player to verify it before linking.")
            if connection.execute("SELECT 1 FROM players WHERE team_id=? AND user_id=?", (team["id"], account["id"])).fetchone():
                raise ApiError(409, "player_profile_exists", "This account already has a player profile in the squad.")
            if team["community_id"]:
                connection.execute("INSERT OR IGNORE INTO community_members(community_id,user_id,role,joined_at) VALUES(?,?,'Member',?)", (team["community_id"], account["id"], iso()))
            connection.execute("UPDATE players SET user_id=?,name=? WHERE id=?", (account["id"], account["name"], player["id"]))
            player = _player(connection, player["id"])
            data = {key: value for key, value in data.items() if key not in ("email", "name")}
            linked_existing_account = True
        else:
            token = new_token()
            expires = iso(utc_now() + timedelta(days=7))
            player_data = {"existing_player_id": player["id"]}
            connection.execute("DELETE FROM player_invites WHERE email=? COLLATE NOCASE AND team_id=?", (email_value, team["id"]))
            token_hash = hash_token(token)
            connection.execute("INSERT INTO player_invites(token_hash,email,team_id,invited_by,player_data_json,expires_at,created_at) VALUES(?,?,?,?,?,?,?)", (token_hash,email_value,team["id"],user_id,json.dumps(player_data),expires,iso()))
            try:
                send_email(email_value, "Join your Touchline community", f"You have been invited to claim your {player['name']} player profile. Create your account using this link; after verifying your email, your account will be linked to the player profile and community automatically:\n\n{config.APP_BASE_URL}/?player_invite={token}\n")
            except MailDeliveryError as error:
                connection.execute("DELETE FROM player_invites WHERE token_hash=?", (token_hash,))
                message = "Email delivery is not configured. Add SMTP settings and restart the server." if str(error)=="not_configured" else "The email provider rejected or could not deliver this message. Check SMTP settings and server logs."
                raise ApiError(503, "email_unavailable", message)
            return {"invitationPending": True, "email": email_value, "name": player["name"], "expiresAt": expires}
    updates = {}
    if "name" in data:
        updates["name"] = text(data, "name", minimum=2, maximum=50, label="Name")
    if "number" in data:
        updates["number"] = integer(data, "number", minimum=1, maximum=99, label="Shirt number")
    if "pos" in data:
        pos = choice(data, "pos", POSITIONS, label="Position")
        updates["pos"] = pos
        updates["group_name"] = group_for_position(pos)
    if "foot" in data:
        updates["foot"] = choice(data, "foot", FEET, label="Preferred foot")
    if "status" in data:
        updates["status"] = choice(data, "status", STATUSES, label="Availability")
    if "image_data" in data:
        updates["image_data"] = _image_data(data["image_data"], "Player photo")
    profile = _profile_updates(data, creating=False)
    updates.update(profile)
    if not updates:
        if linked_existing_account:
            return _player_dict(connection, _player(connection, player["id"]), user_id)
        raise ApiError(400, "no_changes", "Provide at least one player field to update.")
    if any(column in profile for column, _label, _max in STAT_FIELDS.values()):
        merged = {column: player[column] for column, _label, _max in STAT_FIELDS.values()}
        merged.update({k: v for k, v in profile.items() if k in merged})
        _check_stat_consistency(merged)
    if "number" in updates:
        duplicate = connection.execute(
            "SELECT 1 FROM players WHERE team_id = ? AND number = ? AND id <> ?",
            (team["id"], updates["number"], player["id"]),
        ).fetchone()
        if duplicate:
            raise ApiError(409, "number_taken", "That shirt number is already taken.")
    assignments = ", ".join(f"{key} = ?" for key in updates)
    connection.execute(
        f"UPDATE players SET {assignments} WHERE id = ?",
        (*updates.values(), player["id"]),
    )
    return _player_dict(connection, _player(connection, player["id"]), user_id)


MIN_SQUAD_SIZE = 11


def delete_player(connection, user_id, player_id):
    """Remove a player and leave their Starting XI slot open for manual selection."""
    player = _player(connection, valid_id(player_id, "player_id"))
    team = connection.execute("SELECT * FROM teams WHERE id=?", (player["team_id"],)).fetchone()
    _require_community_admin(connection, team["community_id"], user_id)
    squad = connection.execute(
        "SELECT * FROM players WHERE team_id = ?", (team["id"],)
    ).fetchall()
    if len(squad) <= MIN_SQUAD_SIZE:
        raise ApiError(
            409,
            "squad_too_small",
            f"A squad needs at least {MIN_SQUAD_SIZE} players, so this player cannot be removed.",
        )
    starting = _json_list(team["starting_xi_json"])
    if player["id"] in starting:
        starting = (starting + [None] * 11)[:11]
        starting = [None if pid == player["id"] else pid for pid in starting]
        connection.execute(
            "UPDATE teams SET starting_xi_json = ? WHERE id = ?",
            (json.dumps(starting), team["id"]),
        )
    connection.execute("DELETE FROM players WHERE id = ?", (player["id"],))
    return {"deleted": True, "id": player["id"], "name": player["name"]}


def _json_list(raw):
    try:
        value = json.loads(raw or "[]")
    except ValueError:
        return []
    return value if isinstance(value, list) else []


def rate_player(connection, user_id, player_id, data):
    require_object(data)
    player = _player(connection, valid_id(player_id, "player_id"))
    team = connection.execute("SELECT * FROM teams WHERE id=?", (player["team_id"],)).fetchone()
    if team and team["community_id"]:
        _ensure_member(connection, team["community_id"], user_id)
    elif not _is_platform_admin(connection, user_id):
        raise ApiError(403, "forbidden", "You cannot rate this player.")
    value = number(data, "value", minimum=1, maximum=10, label="Rating")
    now = iso()
    connection.execute(
        """
        INSERT INTO player_ratings (player_id, user_id, value, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(player_id, user_id) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """,
        (player["id"], user_id, value, now, now),
    )
    return _player_dict(connection, _player(connection, player["id"]), user_id)


def update_team(connection, user_id, team_id, data):
    require_object(data)
    team = _team_for_user(connection, user_id, valid_id(team_id, "team_id"), manage=True)
    updates = {}
    if "formation" in data:
        formation = choice(data, "formation", FORMATIONS, label="Formation")
        updates["formation"] = formation
    if "starting_xi" in data:
        starting = data.get("starting_xi")
        if not isinstance(starting, list) or len(starting) != 11 or any(pid is not None and not isinstance(pid, str) for pid in starting):
            raise ApiError(400, "invalid_lineup", "A starting XI must contain 11 player or empty slots.")
        selected_ids = [pid for pid in starting if pid is not None]
        if len(set(selected_ids)) != len(selected_ids):
            raise ApiError(400, "invalid_lineup", "A player can only occupy one Starting XI slot.")
        valid_ids = {
            row["id"]
            for row in connection.execute(
                "SELECT id FROM players WHERE team_id = ?", (team["id"],)
            ).fetchall()
        }
        if any(player_id not in valid_ids for player_id in selected_ids):
            raise ApiError(400, "invalid_lineup", "Every starter must belong to this team.")
        updates["starting_xi_json"] = json.dumps(starting)
    if "publish" in data and boolean(data, "publish"):
        current_lineup = _json_list(updates.get("starting_xi_json", team["starting_xi_json"]))
        if len(current_lineup) != 11 or any(not player_id for player_id in current_lineup):
            raise ApiError(409, "incomplete_lineup", "Fill all 11 Starting XI spots before publishing.")
        updates["lineup_saved_at"] = iso()
    if not updates:
        raise ApiError(400, "no_changes", "Provide formation, starting_xi or publish.")
    assignments = ", ".join(f"{key} = ?" for key in updates)
    connection.execute(
        f"UPDATE teams SET {assignments} WHERE id = ?",
        (*updates.values(), team["id"]),
    )
    return team_dict(connection, connection.execute("SELECT * FROM teams WHERE id=?", (team["id"],)).fetchone(), user_id)


def pickup_teams(connection, user_id, include_doubtful=False, position_aware=True, seed=0):
    team = team_dict(connection, _team_for_user(connection, user_id), user_id)
    allowed = {"available"} | ({"doubtful"} if include_doubtful else set())
    pool = [player for player in team["players"] if player["status"] in allowed]
    return split_squad(pool, position_aware=position_aware, seed=seed)


# ---------- Plans ----------

def _default_plan_content(formation, objective):
    return {
        "inPossession": {
            "shape": f"A compact {formation} shape with the pivot connecting the first and last lines.",
            "patterns": [
                {
                    "title": "Build with purpose",
                    "text": "Play through the first line with a third-player combination, then find the free player between the lines.",
                },
                {
                    "title": "Attack the far post",
                    "text": "When the ball goes wide, the far winger attacks the back post and the striker holds the penalty spot.",
                },
            ],
            "roles": [
                {"role": "Pivot", "text": "Set the tempo and connect the first and last lines."},
                {"role": "Free eight", "text": "Arrive late in the box and lead the counter-press."},
                {"role": "Wide 1v1", "text": "Take the outside shoulder and deliver early."},
            ],
        },
        "outOfPossession": {
            "trigger": "A backward pass or a heavy first touch from their deep midfielder.",
            "block": f"A compact {formation} block, forcing the ball wide and keeping the central lane closed.",
            "restDefense": "The far-side full-back stays connected and the pivot protects the centre-backs.",
        },
        "setPieces": {
            "attack": {
                "title": "Near-post flick, far-post finish",
                "steps": [
                    "Deliver inswinging to the near post.",
                    "The first runner flicks toward the back post.",
                    "Two players attack the back-post zone.",
                ],
            },
            "defend": {
                "title": "Compact zonal marking",
                "steps": [
                    "Two players own the six-yard box.",
                    "One player guards the short corner.",
                    "First clearance goes wide, never central.",
                ],
            },
        },
        "_objective": objective,
    }


def create_plan(connection, user_id, data):
    require_object(data)
    title = text(data, "title", minimum=2, maximum=60, label="Plan name")
    opponent = text(data, "opponent", minimum=2, maximum=50, label="Opponent")
    date = text(data, "date", minimum=10, maximum=40, label="Match date")
    try:
        parsed_date = parse_iso(date)
    except (TypeError, ValueError):
        parsed_date = None
    if parsed_date is None:
        raise ApiError(400, "invalid_field", "Match date must be an ISO date.", {"date": "format"})
    venue = text(data, "venue", minimum=1, maximum=60, label="Venue")
    formation = choice(data, "formation", FORMATIONS, required=False, default="4-3-3", label="Formation")
    objective = text(data, "objective", minimum=3, maximum=260, label="Objective")
    team = None
    requested_team = valid_id(data["team_id"], "team_id") if data.get("team_id") else None
    try:
        team = _team_for_user(connection, user_id, team_id=requested_team, manage=True)
    except ApiError as error:
        if error.status != 404 or requested_team is not None or not _is_platform_admin(connection, user_id):
            raise
    board = data.get("board", [])
    if board:
        board = _validate_plan_board(connection, team, board)
    summary = text(
        data,
        "summary",
        required=False,
        default=f"A shared plan for {opponent}. The focus: {objective}",
        maximum=400,
        label="Summary",
    )
    content = _default_plan_content(formation, objective)
    content["board"] = board
    checklist = [
        {"id": new_id("check"), "text": "Confirm squad availability", "done": False},
        {"id": new_id("check"), "text": "Walk through the game model", "done": False},
        {"id": new_id("check"), "text": "Rehearse set-piece routines", "done": False},
        {"id": new_id("check"), "text": "Send team sheet and matchday info", "done": False},
    ]
    plan_id = new_id("plan")
    now = iso()
    connection.execute(
        """
        INSERT INTO plans
        (id, community_id, title, opponent, opponent_mark, date, venue, competition, formation, status,
         objective, summary, content_json, checklist_json, updated_at, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Club fixture · Matchday plan', ?, 'Draft', ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            plan_id,
            team["community_id"] if team else None,
            title,
            opponent,
            _mark(opponent),
            date,
            venue,
            formation,
            objective,
            summary,
            json.dumps(content),
            json.dumps(checklist),
            now,
            user_id,
            now,
        ),
    )
    return plan_dict(_plan(connection, plan_id))


def _validate_plan_board(connection, team, board):
    if not isinstance(board, list) or len(board) != 11 or any(pid is not None and not isinstance(pid, str) for pid in board) or len([pid for pid in board if pid is not None]) != len(set(pid for pid in board if pid is not None)):
        raise ApiError(400, "invalid_board", "The plan board must contain 11 positions and unique roster players.")
    if team is None:
        raise ApiError(409, "team_required", "Create a team with 11 players before editing the plan board.")
    valid = {row["id"] for row in connection.execute("SELECT id FROM players WHERE team_id=?", (team["id"],)).fetchall()}
    if any(pid not in valid for pid in board):
        raise ApiError(400, "invalid_board", "Every plan-board player must belong to your community team.")
    return board


def update_plan(connection, user_id, plan_id, data):
    require_object(data)
    plan = _plan(connection, valid_id(plan_id, "plan_id"))
    if plan["community_id"]:
        if not _is_platform_admin(connection, user_id):
            _require_community_admin(connection, plan["community_id"], user_id)
        team = connection.execute("SELECT * FROM teams WHERE community_id=? ORDER BY rowid LIMIT 1", (plan["community_id"],)).fetchone()
    elif _is_platform_admin(connection, user_id):
        team = connection.execute("SELECT * FROM teams ORDER BY rowid LIMIT 1").fetchone()
    else:
        raise ApiError(403, "forbidden", "A community admin must edit this game plan.")

    columns = {}
    limits = {"title": (2, 60), "opponent": (2, 50), "venue": (1, 60), "competition": (1, 80), "objective": (3, 260), "summary": (0, 400)}
    for key, (minimum, maximum) in limits.items():
        if key in data:
            columns[key] = text(data, key, minimum=minimum, maximum=maximum, label=key.replace("_", " ").title())
    if "date" in data:
        value = text(data, "date", minimum=10, maximum=40, label="Match date")
        try:
            if parse_iso(value) is None: raise ValueError
        except (TypeError, ValueError):
            raise ApiError(400, "invalid_field", "Match date must be an ISO date.", {"date": "format"})
        columns["date"] = value
    if "formation" in data:
        columns["formation"] = choice(data, "formation", FORMATIONS, label="Formation")
    if "status" in data:
        columns["status"] = choice(data, "status", {"Draft", "In review", "Ready", "Published"}, label="Status")

    try: content = json.loads(plan["content_json"] or "{}")
    except (TypeError, ValueError): content = {}
    content_fields = {
        "in_possession_shape": ("inPossession", "shape", 160),
        "out_trigger": ("outOfPossession", "trigger", 200),
        "out_block": ("outOfPossession", "block", 200),
        "out_rest_defense": ("outOfPossession", "restDefense", 200),
        "set_attack_title": ("setPieces", "attack.title", 100),
        "set_defend_title": ("setPieces", "defend.title", 100),
        "corner_taker": ("setPieces", "takers.corners", 80),
        "free_kick_taker": ("setPieces", "takers.freeKicks", 80),
        "penalty_taker": ("setPieces", "takers.penalties", 80),
    }
    for key, (section, field, maximum) in content_fields.items():
        if key in data:
            value = text(data, key, minimum=0, maximum=maximum, label=key.replace("_", " ").title())
            if "." in field:
                part, subfield = field.split(".")
                content.setdefault(section, {}).setdefault(part, {})[subfield] = value
            else:
                content.setdefault(section, {})[field] = value
    for key, section, field in (("patterns", "inPossession", "patterns"), ("roles", "inPossession", "roles"), ("attack_steps", "setPieces", "attack.steps"), ("defend_steps", "setPieces", "defend.steps")):
        if key not in data: continue
        raw = data[key]
        if not isinstance(raw, list) or len(raw) > 12 or any(not isinstance(item, dict) for item in raw):
            raise ApiError(400, "invalid_field", f"{key} must be a list with at most 12 entries.", {key: "type"})
        parsed = []
        for item in raw:
            if key in ("patterns", "roles"):
                left = text(item, "title" if key == "patterns" else "role", minimum=2, maximum=80, label=key)
                right = text(item, "text", minimum=2, maximum=240, label=key)
                parsed.append({("title" if key == "patterns" else "role"): left, "text": right})
            else:
                parsed.append(text({"value": item.get("text")}, "value", minimum=2, maximum=240, label=key))
        if "." in field:
            part, subfield = field.split(".")
            content.setdefault(section, {}).setdefault(part, {})[subfield] = parsed
        else:
            content.setdefault(section, {})[field] = parsed
    if "board" in data:
        content["board"] = _validate_plan_board(connection, team, data["board"])
    if "checklist" in data:
        values = data["checklist"]
        if not isinstance(values, list) or len(values) > 20:
            raise ApiError(400, "invalid_field", "A checklist can contain up to 20 items.", {"checklist": "range"})
        old_items = {item.get("text"): item for item in _json_list(plan["checklist_json"])}
        checklist = []
        for value in values:
            label = text({"text": value}, "text", minimum=2, maximum=100, label="Checklist item")
            previous = old_items.get(label)
            checklist.append({"id": previous["id"] if previous else new_id("check"), "text": label, "done": bool(previous and previous.get("done"))})
        columns["checklist_json"] = json.dumps(checklist)
    try: old_content = json.loads(plan["content_json"] or "{}")
    except (TypeError, ValueError): old_content = {}
    if not columns and content == old_content:
        raise ApiError(400, "no_changes", "Provide at least one game-plan field to update.")
    columns["content_json"] = json.dumps(content)
    columns["updated_at"] = iso()
    assignments = ", ".join(f"{key}=?" for key in columns)
    connection.execute(f"UPDATE plans SET {assignments} WHERE id=?", (*columns.values(), plan["id"]))
    return plan_dict(_plan(connection, plan["id"]))


def toggle_checklist(connection, user_id, plan_id, check_id, data):
    require_object(data)
    plan = _plan(connection, valid_id(plan_id, "plan_id"))
    if plan["community_id"] and not _is_platform_admin(connection, user_id):
        _ensure_member(connection, plan["community_id"], user_id)
    elif not _is_platform_admin(connection, user_id):
        raise ApiError(403, "forbidden", "You cannot update this game plan.")
    checklist = json.loads(plan["checklist_json"] or "[]")
    target = next((item for item in checklist if item.get("id") == check_id), None)
    if target is None:
        raise ApiError(404, "not_found", "That checklist item does not exist.")
    if "done" in data:
        target["done"] = boolean(data, "done")
    else:
        target["done"] = not bool(target.get("done"))
    connection.execute(
        "UPDATE plans SET checklist_json = ?, updated_at = ? WHERE id = ?",
        (json.dumps(checklist), iso(), plan["id"]),
    )
    return plan_dict(_plan(connection, plan["id"]))


# ---------- Notifications ----------

def mark_notifications(connection, user_id, data):
    require_object(data)
    ids = data.get("ids")
    if ids is None or data.get("all") is True:
        connection.execute(
            "UPDATE notifications SET unread = 0 WHERE user_id = ?", (user_id,)
        )
    else:
        if not isinstance(ids, list) or any(not isinstance(item, str) for item in ids):
            raise ApiError(400, "invalid_field", "ids must be a list of notification IDs.", {"ids": "type"})
        if ids:
            placeholders = ",".join("?" for _ in ids)
            connection.execute(
                f"UPDATE notifications SET unread = 0 WHERE user_id = ? AND id IN ({placeholders})",
                (user_id, *ids),
            )
    return list_notifications(connection, user_id)


# ---------- Matchday duties and calendar ----------

DUTY_CLAIMS_PER_DAY = 2
DUTY_MAX_UPCOMING = 200
DUTY_CREATE_LIMIT = 30
DUTY_CREATE_WINDOW = 3600
DUTY_PAST_GRACE = timedelta(hours=24)
CLAIM_GRACE = timedelta(hours=3)
DUTY_HORIZON = timedelta(days=366)
SOURCE_ORDER = {"match": 0, "event": 1, "duty": 2}


def _duty_row(connection, duty_id):
    row = connection.execute("SELECT * FROM duties WHERE id = ?", (duty_id,)).fetchone()
    if row is None:
        raise ApiError(404, "not_found", "That duty does not exist.")
    return row


def _duty_payload(connection, duty_id):
    return duty_dict(connection, _duty_row(connection, duty_id))


def _enforce_limit(key, limit, window):
    wait = limiter.retry_after(key, limit, window)
    if wait:
        raise ApiError(
            429,
            "rate_limited",
            "Too many duties added in a short time. Try again later.",
            {"retryAfter": wait},
        )


def _parse_time(value):
    try:
        parsed = parse_iso(value)
    except (TypeError, ValueError, OverflowError):
        parsed = None
    if parsed is None:
        raise ApiError(400, "invalid_field", "Start time must be an ISO date-time.", {"starts_at": "format"})
    return parsed


def _event_exists(connection, key, community_id):
    return connection.execute(
        """SELECT 1 FROM fixtures WHERE id = ? AND community_id=?
        UNION SELECT 1 FROM events WHERE id = ? AND community_id=?
        UNION SELECT 1 FROM polls p WHERE p.id=? AND p.community_id=? AND p.game_at>=?
          AND p.category IN ('Pickup','Competition')
          AND EXISTS (SELECT 1 FROM poll_votes v WHERE v.poll_id=p.id)""",
        (key, community_id, key, community_id, key, community_id, iso(utc_now())),
    ).fetchone() is not None


def _plain(value, label, key):
    """Reject control characters (NUL, escapes, bell) that break clients and logs."""
    if any(ord(char) < 32 and char not in "\n\t" for char in value) or "\x7f" in value:
        raise ApiError(400, "invalid_field", f"{label} contains characters that are not allowed.", {key: "characters"})
    return value


def create_duty(connection, user, data):
    require_object(data)
    user_id = user["id"]
    community_id = valid_id(data.get("community_id", ""), "community_id")
    _community(connection, community_id)
    if not _is_platform_admin(connection, user_id):
        _ensure_member(connection, community_id, user_id)
    items = data.get("items")
    if items is not None:
        if not isinstance(items, list) or not 1 <= len(items) <= 10:
            raise ApiError(400, "invalid_field", "Choose between 1 and 10 items for this duty.", {"items": "range"})
        if all(isinstance(item, str) for item in items):
            item_kinds = [choice({"kind": item}, "kind", set(DUTY_KINDS), label="Item") for item in items]
            if len(set(item_kinds)) != len(item_kinds):
                raise ApiError(400, "invalid_field", "Choose each item type once.", {"items": "duplicates"})
            return _create_single_duty(connection, user_id, community_id, data, item_kinds=item_kinds)
        created = []
        with transaction(connection):
            for item in items:
                if not isinstance(item, dict):
                    raise ApiError(400, "invalid_field", "Each duty must be an object.", {"items": "type"})
                item_data = dict(item)
                item_data["community_id"] = community_id
                created.append(_create_single_duty(connection, user_id, community_id, item_data))
        return {"duties": created}
    return _create_single_duty(connection, user_id, community_id, data)


def _create_single_duty(connection, user_id, community_id, data, item_kinds=None):
    kind = choice(data, "kind", set(DUTY_KINDS), required=not bool(item_kinds), default=item_kinds[0] if item_kinds else None, label="Item")
    item_kinds = item_kinds or [kind]
    title = _plain(text(
        data, "title", required=False, minimum=1, maximum=80,
        default=" + ".join(DUTY_KINDS[item] for item in item_kinds), label="Title",
    ), "Title", "title")
    starts = _parse_time(text(data, "starts_at", minimum=10, maximum=40, label="Start time"))
    now = utc_now()
    if starts < now - DUTY_PAST_GRACE:
        raise ApiError(400, "invalid_field", "That time has already passed.", {"starts_at": "range"})
    if starts > now + DUTY_HORIZON:
        raise ApiError(400, "invalid_field", "Duties can be planned up to a year ahead.", {"starts_at": "range"})
    note = _plain(text(data, "note", required=False, minimum=0, maximum=200, default="", label="Note"), "Note", "note")
    assigned_to = data.get("assigned_to")
    if assigned_to not in (None, ""):
        assigned_to = valid_id(assigned_to, "assigned_to")
        member = connection.execute("SELECT 1 FROM community_members WHERE community_id=? AND user_id=?", (community_id, assigned_to)).fetchone()
        if member is None:
            raise ApiError(400, "invalid_assignee", "The assigned person must be a member of this community.", {"assigned_to": "membership"})
        if assigned_to != user_id:
            _require_community_admin(connection, community_id, user_id)
    else:
        assigned_to = None
    event_key = None
    raw_event = data.get("event_key")
    if raw_event not in (None, ""):
        if not isinstance(raw_event, str):
            raise ApiError(400, "invalid_field", "event_key must be text.", {"event_key": "type"})
        event_key = valid_id(raw_event, "event_key")
        if not _event_exists(connection, event_key, community_id):
            raise ApiError(400, "unknown_event", "That match or event does not exist.", {"event_key": "unknown"})
    limit_key = f"duty-create:{user_id}"
    _enforce_limit(limit_key, DUTY_CREATE_LIMIT, DUTY_CREATE_WINDOW)
    upcoming = connection.execute(
        "SELECT COUNT(*) AS n FROM duties WHERE community_id=? AND starts_at >= ?", (community_id, iso(now - DUTY_PAST_GRACE))
    ).fetchone()["n"]
    if upcoming >= DUTY_MAX_UPCOMING:
        raise ApiError(409, "duty_limit", "The calendar already has the maximum number of upcoming duties.")
    team = connection.execute("SELECT id FROM teams WHERE community_id=? ORDER BY rowid LIMIT 1", (community_id,)).fetchone()
    if team is None:
        raise ApiError(409, "team_required", "Create a team for this community before adding matchday duties.")
    duty_id = new_id("duty")
    connection.execute(
        """
        INSERT INTO duties
        (id, community_id, team_id, event_key, assigned_to, items_json, kind, title, starts_at, note, claimed_by, claimed_at, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)
        """,
        (duty_id, community_id, team["id"], event_key, assigned_to, json.dumps([{"kind": item, "label": DUTY_KINDS[item]} for item in item_kinds]), kind, title, iso(starts), note, user_id, iso()),
    )
    limiter.record(limit_key, DUTY_CREATE_WINDOW)
    return _duty_payload(connection, duty_id)


def claim_duty(connection, user, duty_id):
    user_id = user["id"]
    row = _duty_row(connection, valid_id(duty_id, "duty_id"))
    _ensure_member(connection, row["community_id"], user_id)
    starts = parse_iso(row["starts_at"])
    if starts < utc_now() - CLAIM_GRACE:
        raise ApiError(409, "duty_passed", "This duty has already happened.")
    if row["claimed_by"] == user_id:
        return duty_dict(connection, row)
    if row["assigned_to"]:
        raise ApiError(409, "duty_assigned", "This duty is assigned to a community member already.")
    if row["claimed_by"]:
        raise ApiError(409, "already_claimed", "Someone has already claimed this duty.")
    day = starts.strftime("%Y-%m-%d")
    # The per-day cap is checked inside the same UPDATE as the claim, so two
    # concurrent requests can never both slip past the limit or the claim.
    result = connection.execute(
        """
        UPDATE duties SET claimed_by = ?, claimed_at = ?
        WHERE id = ? AND claimed_by IS NULL
          AND (SELECT COUNT(*) FROM duties AS other
               WHERE (other.claimed_by = ? OR other.assigned_to = ?) AND other.community_id=? AND substr(other.starts_at, 1, 10) = ?) < ?
        """,
        (user_id, iso(), row["id"], user_id, user_id, row["community_id"], day, DUTY_CLAIMS_PER_DAY),
    )
    if result.rowcount == 0:
        current = _duty_row(connection, row["id"])
        if current["claimed_by"]:
            raise ApiError(409, "already_claimed", "Someone has already claimed this duty.")
        raise ApiError(
            409,
            "claim_limit",
            f"You can bring at most {DUTY_CLAIMS_PER_DAY} duties on the same day.",
        )
    return _duty_payload(connection, row["id"])


def release_duty(connection, user, duty_id):
    row = _duty_row(connection, valid_id(duty_id, "duty_id"))
    if not _is_platform_admin(connection, user["id"]):
        _ensure_member(connection, row["community_id"], user["id"])
    if row["claimed_by"] is None:
        return duty_dict(connection, row)
    is_manager = _is_platform_admin(connection, user["id"]) or _community_role(connection, row["community_id"], user["id"]) == "Admin"
    if row["claimed_by"] != user["id"] and not is_manager:
        raise ApiError(403, "forbidden", "Only the person who took this duty, or a coach, can release it.")
    connection.execute(
        "UPDATE duties SET claimed_by = NULL, claimed_at = NULL WHERE id = ?", (row["id"],)
    )
    return _duty_payload(connection, row["id"])


def delete_duty(connection, user, duty_id):
    row = _duty_row(connection, valid_id(duty_id, "duty_id"))
    if not _is_platform_admin(connection, user["id"]):
        _ensure_member(connection, row["community_id"], user["id"])
    is_manager = _is_platform_admin(connection, user["id"]) or _community_role(connection, row["community_id"], user["id"]) == "Admin"
    if row["created_by"] != user["id"] and not is_manager:
        raise ApiError(403, "forbidden", "Only the person who added this duty, or a coach, can delete it.")
    connection.execute("DELETE FROM duties WHERE id = ?", (row["id"],))
    return {"deleted": True, "id": row["id"], "title": row["title"]}


def _safe_parse(value):
    try:
        return parse_iso(value)
    except (TypeError, ValueError, OverflowError):
        return None


def list_calendar(connection, user_id, community_id, start, end):
    """Matches, club events and duties in one list, for an inclusive UTC date range."""
    first = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
    last = datetime.fromisoformat(end).replace(tzinfo=timezone.utc) + timedelta(days=1)
    community_id = valid_id(community_id, "community_id")
    _community(connection, community_id)
    if not _is_platform_admin(connection, user_id):
        _ensure_member(connection, community_id, user_id)
    entries = []

    def add(when, source, entry):
        if when is not None and first <= when < last:
            entries.append((when, SOURCE_ORDER[source], entry))

    for row in connection.execute("SELECT * FROM fixtures WHERE community_id=?", (community_id,)).fetchall():
        prefix = "vs" if row["home_away"] == "Home" else "@"
        add(_safe_parse(row["date"]), "match", {
            "id": row["id"], "source": "match", "communityId": community_id, "date": row["date"],
            "title": f'{prefix} {row["opponent"]}',
            "detail": f'{row["venue"]} · {row["competition"]}',
            "accent": "lime", "eventType": None, "duty": None,
        })
    for row in connection.execute("SELECT * FROM events WHERE community_id=?", (community_id,)).fetchall():
        add(_safe_parse(row["date"]), "event", {
            "id": row["id"], "source": "event", "communityId": community_id, "date": row["date"],
            "title": row["title"], "detail": row["detail"],
            "accent": row["accent"], "eventType": row["type"], "duty": None,
        })
    for row in connection.execute("SELECT * FROM duties WHERE community_id=?", (community_id,)).fetchall():
        duty = duty_dict(connection, row)
        community = _community(connection, community_id)
        who = duty["assignedTo"]["name"] if duty["assignedTo"] else (duty["claimedBy"]["name"] if duty["claimedBy"] else "Unclaimed")
        add(_safe_parse(row["starts_at"]), "duty", {
            "id": row["id"], "source": "duty", "communityId": community_id, "communityName": community["name"], "date": row["starts_at"],
            "title": row["title"], "detail": f'{duty["kindLabel"]} · {who}',
            "accent": "sky" if duty["claimedBy"] or duty["assignedTo"] else "coral",
            "eventType": duty["kindLabel"], "duty": duty,
        })
    entries.sort(key=lambda item: (item[0], item[1]))
    return {
        "communityId": community_id,
        "from": start,
        "to": end,
        "entries": [entry for _when, _order, entry in entries],
    }


def create_calendar_event(connection, user_id, data):
    require_object(data)
    community_id = valid_id(data.get("community_id", ""), "community_id")
    _community(connection, community_id)
    _require_community_admin(connection, community_id, user_id)
    title = text(data, "title", minimum=2, maximum=100, label="Title")
    detail = text(data, "detail", required=False, maximum=240, default="", label="Details")
    event_type = choice(data, "type", {"Training", "Match", "Meeting", "Social", "Other"}, required=False, default="Other", label="Event type")
    starts = _parse_time(text(data, "date", minimum=10, maximum=40, label="Date"))
    accent = choice(data, "accent", {"lime", "sky", "coral", "violet"}, required=False, default="lime", label="Accent")
    event_id = new_id("event")
    connection.execute("INSERT INTO events(id,community_id,date,type,title,detail,accent,sort_order) VALUES(?,?,?,?,?,?,?,0)", (event_id, community_id, iso(starts), event_type, title, detail, accent))
    return {"id": event_id, "communityId": community_id, "date": iso(starts), "type": event_type, "title": title, "detail": detail, "accent": accent}
