import os
import sqlite3
import threading
from pathlib import Path

from . import config
from .security import (
    hash_password,
    iso,
    new_id,
    utc_now,
)

_INIT_LOCK = threading.Lock()
_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


class TouchlineConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()

_storage_hardened = False


def _harden_storage():
    """Keep the database owner-only: other local users must not read hashes or sessions.

    The umask applies to every file this process creates, so the database and its
    WAL/SHM side files are born 0600. The data folder is restricted to 0700.
    """
    global _storage_hardened
    if _storage_hardened:
        return
    os.umask(0o077)
    try:
        os.chmod(config.DB_PATH.parent, 0o700)
    except OSError:
        pass
    _storage_hardened = True


def connect():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _harden_storage()
    connection = sqlite3.connect(
        str(config.DB_PATH),
        timeout=15,
        isolation_level=None,
        check_same_thread=False,
        factory=TouchlineConnection,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 15000")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


# Columns added to `players` after schema version 2. Existing databases are
# upgraded in place with ALTER TABLE so saved data is never dropped.
_PLAYER_COLUMNS = {
    "date_of_birth": "TEXT",
    "height_cm": "INTEGER",
    "bio": "TEXT NOT NULL DEFAULT ''",
    "starts": "INTEGER NOT NULL DEFAULT 0",
    "minutes": "INTEGER NOT NULL DEFAULT 0",
    "yellow_cards": "INTEGER NOT NULL DEFAULT 0",
    "red_cards": "INTEGER NOT NULL DEFAULT 0",
    "clean_sheets": "INTEGER NOT NULL DEFAULT 0",
    "saves": "INTEGER NOT NULL DEFAULT 0",
    "image_data": "TEXT",
    "user_id": "TEXT REFERENCES users(id) ON DELETE SET NULL",
}
_COMMUNITY_COLUMNS = {"logo_data": "TEXT", "banner_data": "TEXT"}
_USER_COLUMNS = {
    "email_verified": "INTEGER NOT NULL DEFAULT 1",
    "two_factor_enabled": "INTEGER NOT NULL DEFAULT 0",
    "two_factor_secret": "TEXT",
    "two_factor_pending_secret": "TEXT",
    "two_factor_last_step": "INTEGER NOT NULL DEFAULT -1",
}
_TEAM_COLUMNS = {
    "community_id": "TEXT REFERENCES communities(id) ON DELETE SET NULL",
}
_POLL_COLUMNS = {
    "community_id": "TEXT REFERENCES communities(id) ON DELETE CASCADE",
    "game_at": "TEXT",
    "location": "TEXT NOT NULL DEFAULT ''",
    "feedback_due_at": "TEXT",
    "feedback_completed_at": "TEXT",
    "result_json": "TEXT",
}
_POLL_VOTE_COLUMNS = {
    "player_id": "TEXT REFERENCES players(id) ON DELETE SET NULL",
    "guest_count": "INTEGER NOT NULL DEFAULT 0 CHECK(guest_count BETWEEN 0 AND 2)",
}
_NOTIFICATION_COLUMNS = {
    "community_id": "TEXT REFERENCES communities(id) ON DELETE CASCADE",
    "post_id": "TEXT REFERENCES posts(id) ON DELETE CASCADE",
    "kind": "TEXT NOT NULL DEFAULT ''",
    "source_key": "TEXT",
}
_COMMUNITY_DATA_COLUMNS = {
    "plans": {"community_id": "TEXT REFERENCES communities(id) ON DELETE CASCADE"},
    "events": {"community_id": "TEXT REFERENCES communities(id) ON DELETE CASCADE"},
    "fixtures": {"community_id": "TEXT REFERENCES communities(id) ON DELETE CASCADE"},
    "duties": {
        "community_id": "TEXT REFERENCES communities(id) ON DELETE CASCADE",
        "assigned_to": "TEXT REFERENCES users(id) ON DELETE SET NULL",
        "items_json": "TEXT NOT NULL DEFAULT '[]'",
    },
}
def migrate_schema(connection):
    """Upgrade an older database in place. Safe to run on every start."""
    existing = {row["name"] for row in connection.execute("PRAGMA table_info(players)")}
    added = [name for name in _PLAYER_COLUMNS if name not in existing]
    for name in added:
        connection.execute(f"ALTER TABLE players ADD COLUMN {name} {_PLAYER_COLUMNS[name]}")
    connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS players_user_team_idx ON players(team_id,user_id) WHERE user_id IS NOT NULL")
    has_users = bool(connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'").fetchone())
    if has_users:
        users = {row["name"] for row in connection.execute("PRAGMA table_info(users)")}
        added_users = [name for name in _USER_COLUMNS if name not in users]
        for name in added_users:
            connection.execute(f"ALTER TABLE users ADD COLUMN {name} {_USER_COLUMNS[name]}")
    communities = {row["name"] for row in connection.execute("PRAGMA table_info(communities)")}
    for name, definition in _COMMUNITY_COLUMNS.items():
        if name not in communities:
            connection.execute(f"ALTER TABLE communities ADD COLUMN {name} {definition}")
    community_settings = {row["name"] for row in connection.execute("PRAGMA table_info(community_settings)")}
    if "profile_theme" not in community_settings:
        connection.execute("ALTER TABLE community_settings ADD COLUMN profile_theme TEXT NOT NULL DEFAULT 'light'")
    teams = {row["name"] for row in connection.execute("PRAGMA table_info(teams)")}
    added_teams = [name for name in _TEAM_COLUMNS if name not in teams]
    for name in added_teams:
        connection.execute(f"ALTER TABLE teams ADD COLUMN {name} {_TEAM_COLUMNS[name]}")
    polls = {row["name"] for row in connection.execute("PRAGMA table_info(polls)")}
    added_polls = [name for name in _POLL_COLUMNS if name not in polls]
    for name in added_polls:
        connection.execute(f"ALTER TABLE polls ADD COLUMN {name} {_POLL_COLUMNS[name]}")
    poll_votes = {row["name"] for row in connection.execute("PRAGMA table_info(poll_votes)")}
    for name, definition in _POLL_VOTE_COLUMNS.items():
        if name not in poll_votes:
            connection.execute(f"ALTER TABLE poll_votes ADD COLUMN {name} {definition}")
    notifications = {row["name"] for row in connection.execute("PRAGMA table_info(notifications)")}
    added_notifications = []
    for name, definition in _NOTIFICATION_COLUMNS.items():
        if name not in notifications:
            connection.execute(f"ALTER TABLE notifications ADD COLUMN {name} {definition}")
            added_notifications.append(name)
    connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS notifications_source_key_idx ON notifications(source_key) WHERE source_key IS NOT NULL")
    connection.execute("""UPDATE poll_options SET label=CASE lower(trim(label)) WHEN 'in' THEN 'Yes' WHEN 'available' THEN 'Yes' WHEN 'out' THEN 'No' WHEN 'unavailable' THEN 'No' ELSE label END
        WHERE poll_id IN (SELECT id FROM polls WHERE category='Pickup') AND lower(trim(label)) IN ('in','available','out','unavailable')""")
    connection.execute("""UPDATE poll_options SET label=CASE lower(trim(label)) WHEN 'yes' THEN 'Yes' WHEN 'no' THEN 'No' ELSE label END
        WHERE poll_id IN (SELECT id FROM polls WHERE category='Pickup') AND lower(trim(label)) IN ('yes','no')""")
    connection.execute("""DELETE FROM poll_options WHERE poll_id IN (SELECT id FROM polls WHERE category='Pickup')
        AND lower(trim(label)) NOT IN ('yes','no')""")
    for label, position in (("Yes", 0), ("No", 1)):
        connection.execute("""INSERT INTO poll_options(id,poll_id,label,seed_votes,position)
            SELECT lower(hex(randomblob(16))),p.id,?,0,? FROM polls p WHERE p.category='Pickup'
            AND NOT EXISTS(SELECT 1 FROM poll_options o WHERE o.poll_id=p.id AND lower(trim(o.label))=lower(?))""", (label, position, label))
    connection.execute("""UPDATE poll_votes SET player_id=(SELECT p.id FROM players p JOIN teams t ON t.id=p.team_id JOIN users u ON lower(trim(u.name))=lower(trim(p.name))
        WHERE u.id=poll_votes.user_id AND t.community_id=(SELECT community_id FROM polls WHERE id=poll_votes.poll_id) AND p.status<>'out' LIMIT 1)
        WHERE player_id IS NULL AND poll_id IN (SELECT id FROM polls WHERE category='Pickup')
        AND option_id IN (SELECT o.id FROM poll_options o WHERE lower(o.label)='yes')""")
    messages = {row["name"] for row in connection.execute("PRAGMA table_info(community_messages)")}
    if "edited_at" not in messages:
        connection.execute("ALTER TABLE community_messages ADD COLUMN edited_at TEXT")
    added_community_data = False
    for table, columns in _COMMUNITY_DATA_COLUMNS.items():
        existing = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
        for name, definition in columns.items():
            if name not in existing:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
                added_community_data = True
    # Attach a legacy single club team to the earliest community with an admin.
    if added_teams:
        connection.execute("""UPDATE teams SET community_id=(
            SELECT c.id FROM communities c JOIN community_members m ON m.community_id=c.id
            WHERE m.role='Admin' ORDER BY c.rowid LIMIT 1
        ) WHERE community_id IS NULL""")
    connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS teams_community_unique_idx ON teams(community_id) WHERE community_id IS NOT NULL")
    connection.execute("CREATE INDEX IF NOT EXISTS polls_community_created_idx ON polls(community_id, created_at DESC)")
    connection.execute("CREATE INDEX IF NOT EXISTS events_community_date_idx ON events(community_id, date)")
    connection.execute("CREATE INDEX IF NOT EXISTS fixtures_community_date_idx ON fixtures(community_id, date)")
    connection.execute("CREATE INDEX IF NOT EXISTS duties_community_starts_idx ON duties(community_id, starts_at)")
    if added_community_data:
        connection.execute("UPDATE duties SET community_id=(SELECT community_id FROM teams WHERE teams.id=duties.team_id) WHERE community_id IS NULL AND EXISTS (SELECT 1 FROM teams WHERE teams.id=duties.team_id)")
    connection.execute("""UPDATE plans SET community_id=(SELECT m.community_id FROM community_members m
        WHERE m.user_id=plans.created_by ORDER BY CASE m.role WHEN 'Admin' THEN 0 ELSE 1 END,m.joined_at LIMIT 1)
        WHERE community_id IS NULL AND EXISTS (SELECT 1 FROM community_members m WHERE m.user_id=plans.created_by)""")
    if added or added_users or added_teams or added_notifications:
        return added or added_users or added_teams or added_notifications
    return ["community_data"] if added_community_data else []



def init_db(force=False):
    with _INIT_LOCK:
        if force:
            return reset_database_locked()
        config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with connect() as connection:
            connection.executescript(_SCHEMA_PATH.read_text())
            migrate_schema(connection)
            connection.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', '17')"
            )
            connection.execute(
                "INSERT OR IGNORE INTO meta(key, value) VALUES ('community_deletion_timeout_days', '7')"
            )
            connection.execute(
                "INSERT OR IGNORE INTO meta(key, value) VALUES ('poll_retention_days', '7')"
            )
            connection.execute(
                "INSERT OR IGNORE INTO meta(key, value) VALUES ('app_theme', 'light')"
            )
            provision_superadmin(connection)
        return True


def provision_superadmin(connection):
    """Create or promote the explicitly configured super-admin account."""
    if not config.ADMIN_EMAIL or not config.ADMIN_PASSWORD:
        return
    existing = connection.execute(
        "SELECT id, role FROM users WHERE email = ? COLLATE NOCASE", (config.ADMIN_EMAIL,)
    ).fetchone()
    if existing:
        if existing["role"] != "admin":
            # An account registered before admin setup may use this address.
            # The operator's explicit environment config authorizes promotion.
            connection.execute(
                """UPDATE users SET name=?,password_hash=?,role='admin',club_role='Super Admin',email_verified=1
                   WHERE id=?""",
                (config.ADMIN_NAME, hash_password(config.ADMIN_PASSWORD), existing["id"]),
            )
            connection.execute("DELETE FROM sessions WHERE user_id=?", (existing["id"],))
            connection.execute("DELETE FROM auth_tokens WHERE user_id=?", (existing["id"],))
        else:
            connection.execute("UPDATE users SET club_role='Super Admin' WHERE id=?", (existing["id"],))
        return
    now = iso()
    _insert_user(connection, {
        "id": new_id("admin"),
        "name": config.ADMIN_NAME,
        "email": config.ADMIN_EMAIL,
        "password_hash": hash_password(config.ADMIN_PASSWORD),
        "role": "admin",
        "club_role": "Super Admin",
        "avatar_tone": "forest",
        "member_since": str(utc_now().year),
        "club_points": 0,
        "created_at": now,
    })


def reset_database_locked():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as connection:
        connection.executescript(
            """
            DROP TABLE IF EXISTS player_ratings;
            DROP TABLE IF EXISTS player_match_appearances;
            DROP TABLE IF EXISTS player_invites;
            DROP TABLE IF EXISTS poll_player_ratings;
            DROP TABLE IF EXISTS poll_feedback_deliveries;
            DROP TABLE IF EXISTS matchday_player_ratings;
            DROP TABLE IF EXISTS matchday_rating_requests;
            DROP TABLE IF EXISTS community_messages;
            DROP TABLE IF EXISTS community_message_reads;
            DROP TABLE IF EXISTS recovery_codes;
            DROP TABLE IF EXISTS auth_tokens;
            DROP TABLE IF EXISTS poll_votes;
            DROP TABLE IF EXISTS poll_options;
            DROP TABLE IF EXISTS polls;
            DROP TABLE IF EXISTS comments;
            DROP TABLE IF EXISTS post_likes;
            DROP TABLE IF EXISTS notifications;
            DROP TABLE IF EXISTS posts;
            DROP TABLE IF EXISTS community_join_requests;
            DROP TABLE IF EXISTS api_keys;
            DROP TABLE IF EXISTS api_key_requests;
            DROP TABLE IF EXISTS community_members;
            DROP TABLE IF EXISTS community_settings;
            DROP TABLE IF EXISTS community_invites;
            DROP TABLE IF EXISTS community_deletion_approvals;
            DROP TABLE IF EXISTS community_deletion_requests;
            DROP TABLE IF EXISTS communities;
            DROP TABLE IF EXISTS duties;
            DROP TABLE IF EXISTS players;
            DROP TABLE IF EXISTS teams;
            DROP TABLE IF EXISTS plans;
            DROP TABLE IF EXISTS events;
            DROP TABLE IF EXISTS fixtures;
            DROP TABLE IF EXISTS sessions;
            DROP TABLE IF EXISTS users;
            DROP TABLE IF EXISTS meta;
            """
        )
        connection.executescript(_SCHEMA_PATH.read_text())
        connection.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', '17')"
        )
        connection.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES ('community_deletion_timeout_days', '7')"
        )
        connection.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES ('poll_retention_days', '7')"
        )
        connection.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES ('app_theme', 'light')"
        )
        provision_superadmin(connection)
    return True


def reset_database():
    with _INIT_LOCK:
        return reset_database_locked()


def _insert_user(connection, user):
    connection.execute(
        """
        INSERT OR REPLACE INTO users
        (id, name, email, password_hash, role, club_role, avatar_tone, member_since, club_points, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user["id"],
            user["name"],
            user["email"],
            user["password_hash"],
            user["role"],
            user["club_role"],
            user["avatar_tone"],
            user["member_since"],
            user["club_points"],
            user["created_at"],
        ),
    )


