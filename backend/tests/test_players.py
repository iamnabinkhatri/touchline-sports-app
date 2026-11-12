import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from backend import config, db
from backend import service
from backend.tests.base import ApiTestCase

PLAYERS = "/api/v1/players"


def years_ago(years, month=1, day=1):
    return date(date.today().year - years, month, day).isoformat()


class PlayerProfileApiTests(ApiTestCase):
    def player(self, **overrides):
        body = {"email": self.unique_player_email(), "name": "Test Player", "number": 77, "pos": "CM"}
        body.update(overrides)
        return body

    def team(self):
        return self.data(self.authed("GET", "/api/v1/team"))

    def member_token(self):
        session = self.data(self.request("POST", "/api/v1/auth/register", {
            "name": "Plain Member", "email": "member@example.com", "password": "password-123",
        }))
        return session["token"]

    # ---------- reading ----------

    def test_seeded_players_have_profile_and_stats(self):
        for player in self.team()["players"]:
            for key in ("dateOfBirth", "age", "heightCm", "bio", "starts", "minutes",
                        "yellowCards", "redCards", "cleanSheets", "saves"):
                self.assertIn(key, player)
            self.assertIsNotNone(player["age"], player["name"])
            self.assertLessEqual(player["starts"], player["apps"], player["name"])

    def test_get_single_player_returns_profile(self):
        goalkeeper = next(p for p in self.team()["players"] if p["pos"] == "GK")
        one = self.data(self.authed("GET", f"{PLAYERS}/{goalkeeper['id']}"))
        self.assertEqual(one["id"], goalkeeper["id"])
        self.assertGreater(one["saves"], 0)

    # ---------- creating ----------

    def test_new_player_requires_an_email_address(self):
        self.error(self.authed("POST", PLAYERS, {"name":"No Email", "number":77, "pos":"CM"}), 400, "missing_field")

    def test_unregistered_player_receives_registration_link_and_joins_after_signup(self):
        import re
        email = "invited-player@example.test"
        with mock.patch("backend.service.send_email") as send:
            invitation = self.data(self.authed("POST", PLAYERS, self.player(email=email)))
        self.assertTrue(invitation["invitationPending"])
        token = re.search(r"player_invite=([A-Za-z0-9_-]+)", send.call_args.args[2]).group(1)
        with mock.patch("backend.service.send_email") as verification_mail:
            registration = self.data(self.request("POST", "/api/v1/auth/register", {
                "name": "Invited Player", "email": email, "password": "player-password-123", "player_invite": token,
            }))
        self.assertTrue(registration["playerAdded"])
        verify_token = re.search(r"verify_token=([A-Za-z0-9_-]+)", verification_mail.call_args.args[2]).group(1)
        self.data(self.request("POST", "/api/v1/auth/verify-email", {"token": verify_token}))
        with db.connect() as connection:
            row = connection.execute("SELECT p.user_id,p.team_id FROM players p JOIN users u ON u.id=p.user_id WHERE u.email=?", (email,)).fetchone()
            self.assertIsNotNone(row)
            team = connection.execute("SELECT community_id FROM teams WHERE id=?", (row["team_id"],)).fetchone()
            self.assertTrue(connection.execute("SELECT 1 FROM community_members WHERE community_id=? AND user_id=?", (team["community_id"], row["user_id"])).fetchone())

    def test_yes_pickup_vote_increments_appearance_once_after_game(self):
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        close = now + timedelta(hours=2)
        game = now + timedelta(hours=3)
        team = self.team()
        poll = self.data(self.authed("POST", "/api/v1/polls", {
            "community_id": team["communityId"], "question": "Tuesday pickup", "category": "Pickup",
            "closes_at": close.isoformat(), "game_at": game.isoformat(), "location": "Riverside Park", "options": [],
        }))
        player = next(item for item in team["players"] if item["id"] in team["startingXI"])
        with db.connect() as connection:
            option = connection.execute("SELECT id FROM poll_options WHERE poll_id=? AND label='Yes'", (poll["id"],)).fetchone()
            connection.execute("INSERT OR IGNORE INTO community_members(community_id,user_id,role,joined_at) VALUES(?,?,'Member',?)", (team["communityId"], self.user["id"], service.iso()))
            connection.execute("INSERT INTO poll_votes(poll_id,user_id,option_id,player_id,guest_count,created_at) VALUES(?,?,?,?,0,?)", (poll["id"], self.user["id"], option["id"], player["id"], service.iso()))
            past = service.iso(now - timedelta(minutes=1))
            connection.execute("UPDATE polls SET closes_at=?,game_at=? WHERE id=?", (past,past,poll["id"]))
            original = connection.execute("SELECT apps,starts,minutes FROM players WHERE id=?", (player["id"],)).fetchone()
            service.process_due_polls(connection, now)
            service.process_due_polls(connection, now)
            updated = connection.execute("SELECT apps,starts,minutes FROM players WHERE id=?", (player["id"],)).fetchone()
            self.assertEqual(updated["apps"], original["apps"] + 1)
            self.assertEqual(updated["starts"], original["starts"] + 1)
            self.assertEqual(updated["minutes"], original["minutes"] + 90)

    def test_create_with_profile_and_stats(self):
        created = self.data(self.authed("POST", PLAYERS, self.player(
            date_of_birth=years_ago(15, 3, 9), height_cm=168, bio="  Quick on the break.  ",
            apps=5, starts=4, minutes=300, goals=2, assists=1, yellow_cards=1, red_cards=0,
            clean_sheets=0, saves=0,
        )))
        self.assertIn(created["age"], (14, 15))
        self.assertEqual(created["heightCm"], 168)
        self.assertEqual(created["bio"], "Quick on the break.")
        self.assertEqual((created["apps"], created["starts"], created["minutes"]), (5, 4, 300))
        self.assertEqual((created["goals"], created["assists"], created["yellowCards"]), (2, 1, 1))

    def test_create_without_profile_defaults_to_empty(self):
        created = self.data(self.authed("POST", PLAYERS, self.player()))
        self.assertIsNone(created["dateOfBirth"])
        self.assertIsNone(created["age"])
        self.assertIsNone(created["heightCm"])
        self.assertEqual(created["bio"], "")
        self.assertEqual(created["minutes"], 0)

    def test_create_rejects_invalid_profile_values(self):
        cases = {
            "future date of birth": {"date_of_birth": "2999-01-01"},
            "not a calendar date": {"date_of_birth": "2011-02-31"},
            "wrong format": {"date_of_birth": "03/09/2011"},
            "too young": {"date_of_birth": years_ago(2)},
            "too old": {"date_of_birth": years_ago(90)},
            "height too small": {"height_cm": 50},
            "height too large": {"height_cm": 400},
            "height wrong type": {"height_cm": "tall"},
            "bio too long": {"bio": "x" * 401},
            "negative goals": {"goals": -1},
            "huge minutes": {"apps": 999, "minutes": 100000},
            "stat as text": {"apps": "ten"},
            "starts above apps": {"apps": 3, "starts": 4},
            "clean sheets above apps": {"apps": 2, "clean_sheets": 3},
            "minutes above 120 per game": {"apps": 2, "minutes": 241},
        }
        for label, extra in cases.items():
            with self.subTest(label):
                self.error(self.authed("POST", PLAYERS, self.player(**extra)), 400)
        # none of the rejected requests created a player
        self.assertEqual(len(self.team()["players"]), 18)

    # ---------- updating ----------

    def test_update_stats_and_profile(self):
        target = self.team()["players"][3]
        updated = self.data(self.authed("PATCH", f"{PLAYERS}/{target['id']}", {
            "apps": 12, "starts": 11, "minutes": 800, "goals": 6, "assists": 4,
            "yellow_cards": 2, "red_cards": 1, "clean_sheets": 5, "saves": 3,
            "height_cm": 175, "bio": "Captain material.", "date_of_birth": years_ago(16, 6, 1),
        }))
        self.assertEqual((updated["apps"], updated["starts"], updated["minutes"]), (12, 11, 800))
        self.assertEqual((updated["goals"], updated["assists"]), (6, 4))
        self.assertEqual((updated["yellowCards"], updated["redCards"]), (2, 1))
        self.assertEqual(updated["heightCm"], 175)
        self.assertEqual(updated["bio"], "Captain material.")

    def test_update_checks_consistency_against_stored_values(self):
        target = next(p for p in self.team()["players"] if p["starts"] >= 5)
        # lowering appearances below the stored starts must be rejected
        self.error(self.authed("PATCH", f"{PLAYERS}/{target['id']}", {"apps": target["starts"] - 1}), 400, "invalid_stats")
        # raising starts above stored appearances must be rejected
        self.error(self.authed("PATCH", f"{PLAYERS}/{target['id']}", {"starts": target["apps"] + 1}), 400, "invalid_stats")
        unchanged = self.data(self.authed("GET", f"{PLAYERS}/{target['id']}"))
        self.assertEqual((unchanged["apps"], unchanged["starts"]), (target["apps"], target["starts"]))

    def test_profile_fields_can_be_cleared(self):
        target = self.team()["players"][0]
        cleared = self.data(self.authed("PATCH", f"{PLAYERS}/{target['id']}", {
            "date_of_birth": None, "height_cm": None, "bio": "",
        }))
        self.assertIsNone(cleared["dateOfBirth"])
        self.assertIsNone(cleared["heightCm"])
        self.assertEqual(cleared["bio"], "")

    def test_mass_assignment_is_ignored(self):
        target = self.team()["players"][0]
        before = self.data(self.authed("GET", f"{PLAYERS}/{target['id']}"))
        updated = self.data(self.authed("PATCH", f"{PLAYERS}/{target['id']}", {
            "bio": "ok", "rating_sum": 9999, "rating_count": 1, "id": "hacked", "team_id": "other",
            "group_name": "GK", "sort_order": -5, "rating": 10, "userRating": 10,
        }))
        self.assertEqual(updated["id"], target["id"])
        self.assertEqual(updated["rating"], before["rating"])
        self.assertEqual(updated["ratingCount"], before["ratingCount"])
        self.assertEqual(updated["group"], before["group"])

    def test_stored_markup_round_trips_as_inert_text(self):
        payload = "<img src=x onerror=alert(1)><script>alert(2)</script>"
        created = self.data(self.authed("POST", PLAYERS, self.player(name="Zed <b>Bold</b>", bio=payload)))
        fetched = self.data(self.authed("GET", f"{PLAYERS}/{created['id']}"))
        self.assertEqual(fetched["bio"], payload)  # stored verbatim; the UI escapes on render
        self.assertEqual(fetched["name"], "Zed <b>Bold</b>")

    # ---------- permissions ----------

    def test_members_cannot_write_players(self):
        member = self.member_token()
        target = self.team()["players"][0]
        self.error(self.request("POST", PLAYERS, self.player(), token=member), 403, "forbidden")
        self.error(self.request("PATCH", f"{PLAYERS}/{target['id']}", {"goals": 99}, token=member), 403, "forbidden")
        self.error(self.request("DELETE", f"{PLAYERS}/{target['id']}", token=member), 403, "forbidden")
        self.assertEqual(self.data(self.authed("GET", f"{PLAYERS}/{target['id']}"))["goals"], target["goals"])

    def test_members_can_read_and_rate(self):
        member = self.member_token()
        target = self.team()["players"][0]
        self.data(self.request("GET", f"{PLAYERS}/{target['id']}", token=member))
        rated = self.data(self.request("POST", f"{PLAYERS}/{target['id']}/ratings", {"value": 9}, token=member))
        self.assertEqual(rated["userRating"], 9)

    def test_player_endpoints_require_authentication(self):
        target = self.team()["players"][0]
        for method, path, body in (
            ("GET", f"{PLAYERS}/{target['id']}", None),
            ("POST", PLAYERS, self.player()),
            ("PATCH", f"{PLAYERS}/{target['id']}", {"goals": 1}),
            ("DELETE", f"{PLAYERS}/{target['id']}", None),
        ):
            with self.subTest(method=method):
                self.error(self.request(method, path, body), 401, "unauthorized")

    # ---------- deleting ----------

    def test_delete_player_removes_them_and_their_ratings(self):
        created = self.data(self.authed("POST", PLAYERS, self.player()))
        self.data(self.authed("POST", f"{PLAYERS}/{created['id']}/ratings", {"value": 7}))
        result = self.data(self.authed("DELETE", f"{PLAYERS}/{created['id']}"))
        self.assertTrue(result["deleted"])
        self.error(self.authed("GET", f"{PLAYERS}/{created['id']}"), 404, "not_found")
        self.assertEqual(len(self.team()["players"]), 18)
        with db.connect() as connection:
            left = connection.execute(
                "SELECT COUNT(*) AS n FROM player_ratings WHERE player_id = ?", (created["id"],)
            ).fetchone()["n"]
        self.assertEqual(left, 0)

    def test_deleting_a_starter_leaves_the_same_xi_slot_empty(self):
        team = self.team()
        starter = team["startingXI"][4]
        self.data(self.authed("DELETE", f"{PLAYERS}/{starter}"))
        after = self.team()
        self.assertEqual(len(after["startingXI"]), 11)
        self.assertIsNone(after["startingXI"][4])
        self.assertEqual(after["startingXI"][:4] + after["startingXI"][5:], team["startingXI"][:4] + team["startingXI"][5:])
        known = {p["id"] for p in after["players"]}
        self.assertTrue({pid for pid in after["startingXI"] if pid} <= known)
        self.data(self.authed("PATCH", f"/api/v1/teams/{after['id']}", {"starting_xi": after["startingXI"]}))

    def test_lineup_can_be_cleared_and_rebuilt_manually(self):
        team = self.team()
        empty = [None] * 11
        cleared = self.data(self.authed("PATCH", f"/api/v1/teams/{team['id']}", {"starting_xi": empty}))
        self.assertEqual(cleared["startingXI"], empty)
        rebuilt = list(empty)
        rebuilt[4] = team["players"][0]["id"]
        updated = self.data(self.authed("PATCH", f"/api/v1/teams/{team['id']}", {"starting_xi": rebuilt}))
        self.assertEqual(updated["startingXI"], rebuilt)

    def test_squad_cannot_shrink_below_eleven(self):
        players = self.team()["players"]
        bench = [p for p in players if p["id"] not in self.team()["startingXI"]]
        for player in bench:  # 18 -> 11
            self.data(self.authed("DELETE", f"{PLAYERS}/{player['id']}"))
        remaining = self.team()
        self.assertEqual(len(remaining["players"]), 11)
        self.error(self.authed("DELETE", f"{PLAYERS}/{remaining['players'][0]['id']}"), 409, "squad_too_small")
        self.assertEqual(len(self.team()["players"]), 11)

    def test_delete_unknown_or_malformed_ids(self):
        self.error(self.authed("DELETE", f"{PLAYERS}/does-not-exist"), 404, "not_found")
        self.error(self.authed("DELETE", f"{PLAYERS}/UPPER_case"), 400, "invalid_id")
        self.error(self.authed("DELETE", f"{PLAYERS}/x"), 400, "invalid_id")

    def test_sql_injection_in_player_id_and_fields(self):
        # an injection-style id never matches the route, so no query is ever built
        self.error(self.authed("GET", f"{PLAYERS}/1%27%20OR%20%271%27=%271"), 404, "not_found")
        created = self.data(self.authed("POST", PLAYERS, self.player(
            name="Robert'); DROP TABLE players;--", bio="' OR 1=1 --")))
        self.assertEqual(created["name"], "Robert'); DROP TABLE players;--")
        self.assertEqual(len(self.team()["players"]), 19)


class PlayerMigrationTests(unittest.TestCase):
    """An older database must be upgraded in place without losing data."""

    OLD_PLAYERS_TABLE = """
        CREATE TABLE players (
            id TEXT PRIMARY KEY,
            team_id TEXT NOT NULL,
            name TEXT NOT NULL,
            number INTEGER NOT NULL,
            pos TEXT NOT NULL,
            group_name TEXT NOT NULL,
            foot TEXT NOT NULL,
            status TEXT NOT NULL,
            rating_sum REAL NOT NULL DEFAULT 0,
            rating_count INTEGER NOT NULL DEFAULT 0,
            goals INTEGER NOT NULL DEFAULT 0,
            assists INTEGER NOT NULL DEFAULT 0,
            apps INTEGER NOT NULL DEFAULT 0,
            sort_order INTEGER NOT NULL DEFAULT 0,
            UNIQUE (team_id, number)
        );
    """

    def make_old_database(self, path):
        connection = sqlite3.connect(path)
        connection.executescript(self.OLD_PLAYERS_TABLE)
        connection.execute(
            "INSERT INTO players VALUES ('maya', 't1', 'Maya Chen', 8, 'CM', 'MID', 'Right', "
            "'available', 80, 10, 4, 6, 10, 7)"
        )
        connection.execute(
            "INSERT INTO players VALUES ('custom-kid', 't1', 'Added By Club', 30, 'ST', 'FWD', 'Left', "
            "'available', 0, 0, 1, 0, 2, 20)"
        )
        # Supply the surrounding tables from the live schema so this exercises
        # a legacy players table inside an otherwise real app database.
        connection.executescript(db._SCHEMA_PATH.read_text())
        connection.commit()
        connection.close()

    def migrate(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "old.db"
        self.make_old_database(path)
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        self.addCleanup(connection.close)
        return connection, db.migrate_schema(connection)

    def test_columns_are_added_and_existing_rows_survive(self):
        connection, added = self.migrate()
        self.assertEqual(set(added), set(db._PLAYER_COLUMNS))
        row = connection.execute("SELECT * FROM players WHERE id = 'custom-kid'").fetchone()
        self.assertEqual((row["name"], row["goals"], row["apps"]), ("Added By Club", 1, 2))
        self.assertEqual((row["starts"], row["minutes"], row["bio"]), (0, 0, ""))
        self.assertIsNone(row["date_of_birth"])

    def test_existing_player_stats_survive_with_new_profile_defaults(self):
        connection, _ = self.migrate()
        demo = connection.execute("SELECT * FROM players WHERE id = 'maya'").fetchone()
        self.assertIsNone(demo["date_of_birth"])
        self.assertEqual(demo["minutes"], 0)
        self.assertEqual((demo["goals"], demo["assists"]), (4, 6))  # untouched
        custom = connection.execute("SELECT * FROM players WHERE id = 'custom-kid'").fetchone()
        self.assertIsNone(custom["date_of_birth"])
        self.assertEqual(custom["minutes"], 0)

    def test_migration_is_idempotent(self):
        connection, _ = self.migrate()
        connection.execute("UPDATE players SET minutes = 123 WHERE id = 'maya'")
        self.assertEqual(db.migrate_schema(connection), [])
        self.assertEqual(
            connection.execute("SELECT minutes FROM players WHERE id = 'maya'").fetchone()["minutes"], 123
        )

    def test_migration_creates_account_link_and_appearance_support(self):
        connection, _ = self.migrate()
        self.assertIn("user_id", {row["name"] for row in connection.execute("PRAGMA table_info(players)")})
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM player_match_appearances").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
