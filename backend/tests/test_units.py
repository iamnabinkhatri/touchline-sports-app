import json
import sqlite3
import tempfile
import unittest
import re
from unittest.mock import patch
from pathlib import Path
from datetime import timedelta

from backend import balance, config, db, security, service, validation
from backend.errors import ApiError


class SecurityUnitTests(unittest.TestCase):
    def setUp(self):
        self.original_iterations = config.PBKDF2_ITERATIONS
        config.PBKDF2_ITERATIONS = 1000

    def tearDown(self):
        config.PBKDF2_ITERATIONS = self.original_iterations

    def test_password_hashing_and_verification(self):
        encoded = security.hash_password("correct horse battery staple")
        self.assertTrue(encoded.startswith("pbkdf2_sha256$1000$"))
        self.assertNotIn("correct horse battery staple", encoded)
        self.assertTrue(security.verify_password("correct horse battery staple", encoded))
        self.assertFalse(security.verify_password("wrong", encoded))
        self.assertFalse(security.verify_password("anything", "disabled"))
        self.assertNotEqual(security.hash_password("same"), security.hash_password("same"))

    def test_tokens_are_random_and_hashed(self):
        first = security.new_token()
        second = security.new_token()
        self.assertNotEqual(first, second)
        self.assertNotEqual(security.hash_token(first), first)
        self.assertEqual(security.hash_token(first), security.hash_token(first))
        self.assertNotEqual(security.hash_token(first), security.hash_token(second))

    def test_dates_and_expiry(self):
        now = security.utc_now()
        parsed = security.parse_iso(security.iso(now))
        self.assertGreaterEqual((parsed - now).total_seconds(), 0)
        self.assertLess((parsed - now).total_seconds(), 2)
        expiry = security.parse_iso(security.session_expiry())
        self.assertGreater(expiry, now)

    def test_initials_and_slug(self):
        self.assertEqual(security.initials("Maya Chen"), "MC")
        self.assertEqual(security.slugify("  API FC!! "), "api-fc")


class ValidationUnitTests(unittest.TestCase):
    def test_required_text_and_bounds(self):
        self.assertEqual(validation.text({"name": "  Alex  "}, "name"), "Alex")
        with self.assertRaises(ApiError) as missing:
            validation.text({}, "name")
        self.assertEqual(missing.exception.status, 400)
        with self.assertRaises(ApiError):
            validation.text({"name": "x"}, "name", minimum=3)
        with self.assertRaises(ApiError):
            validation.text({"name": "x" * 10}, "name", maximum=5)

    def test_numbers_and_choices(self):
        self.assertEqual(validation.integer({"n": 5}, "n", minimum=1, maximum=10), 5)
        with self.assertRaises(ApiError):
            validation.integer({"n": 11}, "n", maximum=10)
        with self.assertRaises(ApiError):
            validation.number({"n": True}, "n")
        self.assertEqual(validation.choice({"x": "Club"}, "x", {"Club", "Lineup"}), "Club")
        with self.assertRaises(ApiError):
            validation.choice({"x": "Other"}, "x", {"Club"})

    def test_email_password_and_lists(self):
        self.assertEqual(validation.email({"email": "A@B.CO"}), "a@b.co")
        with self.assertRaises(ApiError):
            validation.email({"email": "not-an-email"})
        self.assertEqual(validation.password({"password": "12345678"}), "12345678")
        with self.assertRaises(ApiError):
            validation.password({"password": "short"})
        self.assertEqual(validation.text_list({"options": ["A", "B"]}, "options"), ["A", "B"])
        with self.assertRaises(ApiError):
            validation.text_list({"options": ["A"]}, "options", minimum=2)


class BalanceUnitTests(unittest.TestCase):
    def players(self, count):
        def group_for(index):
            if index < 2:
                return "GK"
            return ["DEF", "MID", "FWD"][(index - 2) % 3]

        return [
            {
                "id": f"p-{index}",
                "name": f"Player {index}",
                "group": group_for(index),
                "rating": 7.0 + (index % 5) / 10,
                "apps": index,
            }
            for index in range(count)
        ]

    def test_even_split_and_balance(self):
        result = balance.split_squad(self.players(14), position_aware=True, seed=1)
        self.assertEqual(len(result["teamA"]["players"]), 7)
        self.assertEqual(len(result["teamB"]["players"]), 7)
        self.assertLessEqual(result["gap"], 0.5)
        self.assertEqual(result["teamA"]["counts"]["GK"] + result["teamB"]["counts"]["GK"], 2)

    def test_odd_pool_and_determinism(self):
        first = balance.split_squad(self.players(13), position_aware=True, seed=4)
        second = balance.split_squad(self.players(13), position_aware=True, seed=4)
        self.assertIsNotNone(first["floater"])
        self.assertEqual([p["id"] for p in first["teamA"]["players"]], [p["id"] for p in second["teamA"]["players"]])
        combined = {p["id"] for p in first["teamA"]["players"]} | {p["id"] for p in first["teamB"]["players"]}
        self.assertNotIn(first["floater"]["id"], combined)

    def test_empty_pool(self):
        result = balance.split_squad([], position_aware=True, seed=1)
        self.assertEqual(result["sessionLabel"], "0v0")
        self.assertEqual(result["balanceScore"], 0)
        solo = balance.split_squad(self.players(1), position_aware=True, seed=1)
        self.assertEqual(solo["teamA"]["players"], [])
        self.assertEqual(solo["teamB"]["players"], [])
        self.assertEqual(solo["floater"]["id"], "p-0")


class DatabaseUnitTests(unittest.TestCase):
    def test_deleting_a_starter_keeps_an_empty_slot_for_manual_replacement(self):
        original = config.DB_PATH
        with tempfile.TemporaryDirectory() as directory:
            config.DB_PATH = Path(directory) / "empty-xi.db"
            try:
                db.init_db()
                now = security.iso(security.utc_now())
                with db.connect() as connection:
                    connection.execute("INSERT INTO users(id,name,email,password_hash,role,member_since,created_at) VALUES(?,?,?,?,?,?,?)",("owner","Owner","owner@example.test","disabled","member","2026",now))
                    connection.execute("INSERT INTO communities(id,name,sport,kind,mark,privacy,accent,description,activity,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",("club","Club","Soccer","Club","C","Private","forest","Test","New","owner",now))
                    connection.execute("INSERT INTO community_members(community_id,user_id,role,joined_at) VALUES(?,?,?,?)",("club","owner","Admin",now))
                    starters = [f"p{i}" for i in range(11)]
                    connection.execute("INSERT INTO teams(id,community_id,name,age_group,league,mark,accent,coach,rank,formation,starting_xi_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",("team","club","Team","Open","Local","T","forest","Coach","1","4-3-3",json.dumps(starters),now))
                    for index in range(12):
                        connection.execute("INSERT INTO players(id,team_id,name,number,pos,group_name,foot,status) VALUES(?,?,?,?,?,?,?,?)",(f"p{index}","team",f"Player {index}",index+1,"CM","MID","Right","available"))
                    service.delete_player(connection,"owner","p4")
                    saved = json.loads(connection.execute("SELECT starting_xi_json FROM teams WHERE id='team'").fetchone()[0])
                    self.assertEqual(len(saved),11)
                    self.assertIsNone(saved[4])
                    self.assertEqual(saved[:4]+saved[5:],starters[:4]+starters[5:])
                    cleared = service.update_team(connection,"owner","team",{"starting_xi":[None]*11})
                    self.assertEqual(cleared["startingXI"],[None]*11)
                    rebuilt = [None]*11
                    rebuilt[7] = "p11"
                    self.assertEqual(service.update_team(connection,"owner","team",{"starting_xi":rebuilt})["startingXI"],rebuilt)
                    with self.assertRaises(ApiError) as duplicate:
                        service.update_team(connection,"owner","team",{"starting_xi":["p0","p0"]+[None]*9})
                    self.assertEqual(duplicate.exception.code,"invalid_lineup")
            finally:
                config.DB_PATH = original

    def test_player_invite_registers_and_links_the_account_to_community(self):
        original = config.DB_PATH
        with tempfile.TemporaryDirectory() as directory:
            config.DB_PATH = Path(directory) / "player-invite.db"
            try:
                db.init_db()
                now = security.iso(security.utc_now())
                with db.connect() as connection:
                    connection.execute("INSERT INTO users(id,name,email,password_hash,role,club_role,member_since,created_at) VALUES(?,?,?,?,?,?,?,?)", ("club-admin","Club Admin","admin@example.test","disabled","member","Admin","2026",now))
                    connection.execute("INSERT INTO communities(id,name,sport,kind,mark,privacy,accent,description,activity,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", ("club","Club","Soccer","Club","C","Private","forest","Test","New","club-admin",now))
                    connection.execute("INSERT INTO community_members(community_id,user_id,role,joined_at) VALUES(?,?,?,?)",("club","club-admin","Admin",now))
                    connection.execute("INSERT INTO teams(id,community_id,name,age_group,league,mark,accent,coach,rank,formation,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",("team","club","Team","Open","Local","T","forest","Coach","1","4-3-3",now))
                    payload = {"team_id":"team","email":"new-player@example.test","name":"New Player","number":18,"pos":"CM"}
                    with patch("backend.service.send_email") as invite_email:
                        pending = service.create_player(connection,"club-admin",payload)
                    self.assertTrue(pending["invitationPending"])
                    token = re.search(r"player_invite=([A-Za-z0-9_-]+)",invite_email.call_args.args[2]).group(1)
                    with self.assertRaises(ApiError) as mismatched_email:
                        service.register(connection,{"name":"Someone Else","email":"attacker@example.test","password":"long-password-123","player_invite":token})
                    self.assertEqual(mismatched_email.exception.code,"invalid_player_invite")
                    self.assertFalse(connection.execute("SELECT 1 FROM users WHERE email='attacker@example.test'").fetchone())
                    with patch("backend.service.send_email") as verification_email:
                        registration = service.register(connection,{"name":"New Player","email":payload["email"],"password":"long-password-123","player_invite":token})
                    self.assertTrue(registration["playerAdded"])
                    verify = re.search(r"verify_token=([A-Za-z0-9_-]+)",verification_email.call_args.args[2]).group(1)
                    service.verify_email(connection,{"token":verify})
                    row = connection.execute("SELECT p.id,p.user_id,u.email FROM players p JOIN users u ON u.id=p.user_id WHERE u.email=?",(payload["email"],)).fetchone()
                    self.assertIsNotNone(row)
                    self.assertEqual(row["email"],payload["email"])
                    self.assertTrue(connection.execute("SELECT 1 FROM community_members WHERE community_id='club' AND user_id=?",(row["user_id"],)).fetchone())
                    self.assertEqual(connection.execute("SELECT COUNT(*) FROM player_invites").fetchone()[0],0)
            finally:
                config.DB_PATH = original

    def test_editing_unregistered_player_email_links_existing_profile_and_updates_name_at_signup(self):
        original = config.DB_PATH
        with tempfile.TemporaryDirectory() as directory:
            config.DB_PATH = Path(directory) / "existing-player-invite.db"
            try:
                db.init_db()
                now = security.iso(security.utc_now())
                with db.connect() as connection:
                    connection.execute("INSERT INTO users(id,name,email,password_hash,role,club_role,member_since,created_at) VALUES(?,?,?,?,?,?,?,?)", ("club-admin","Club Admin","admin@example.test","disabled","member","Admin","2026",now))
                    connection.execute("INSERT INTO communities(id,name,sport,kind,mark,privacy,accent,description,activity,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", ("club","Club","Soccer","Club","C","Private","forest","Test","New","club-admin",now))
                    connection.execute("INSERT INTO community_members(community_id,user_id,role,joined_at) VALUES(?,?,?,?)",("club","club-admin","Admin",now))
                    connection.execute("INSERT INTO teams(id,community_id,name,age_group,league,mark,accent,coach,rank,formation,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",("team","club","Team","Open","Local","T","forest","Coach","1","4-3-3",now))
                    team = connection.execute("SELECT * FROM teams WHERE id='team'").fetchone()
                    player_id = service._insert_player_record(connection, team, {"name":"Old Display Name","number":18,"pos":"CM","foot":"Right","status":"available"}, None)
                    with patch("backend.service.send_email") as invite_email:
                        pending = service.update_player(connection,"club-admin",player_id,{"email":"new-player@example.test"})
                    self.assertTrue(pending["invitationPending"])
                    token = re.search(r"player_invite=([A-Za-z0-9_-]+)",invite_email.call_args.args[2]).group(1)
                    with patch("backend.service.send_email") as verify_email:
                        registration = service.register(connection,{"name":"New Player","email":"new-player@example.test","password":"long-password-123","player_invite":token})
                    self.assertTrue(registration["playerAdded"])
                    verify = re.search(r"verify_token=([A-Za-z0-9_-]+)",verify_email.call_args.args[2]).group(1)
                    service.verify_email(connection,{"token":verify})
                    linked = connection.execute("SELECT p.id,p.name,p.user_id,u.email FROM players p JOIN users u ON u.id=p.user_id WHERE p.id=?",(player_id,)).fetchone()
                    self.assertEqual(linked["id"],player_id)
                    self.assertEqual(linked["name"],"New Player")
                    self.assertEqual(linked["email"],"new-player@example.test")
                    self.assertTrue(connection.execute("SELECT 1 FROM community_members WHERE community_id='club' AND user_id=?",(linked["user_id"],)).fetchone())
            finally:
                config.DB_PATH = original

    def test_editing_player_links_verified_community_member_without_email(self):
        original = config.DB_PATH
        with tempfile.TemporaryDirectory() as directory:
            config.DB_PATH = Path(directory) / "link-existing-member.db"
            try:
                db.init_db()
                now = security.iso(security.utc_now())
                with db.connect() as connection:
                    connection.execute("INSERT INTO users(id,name,email,password_hash,role,club_role,member_since,created_at,email_verified) VALUES(?,?,?,?,?,?,?,?,1)", ("club-admin","Club Admin","admin@example.test","disabled","member","Admin","2026",now))
                    connection.execute("INSERT INTO users(id,name,email,password_hash,role,club_role,member_since,created_at,email_verified) VALUES(?,?,?,?,?,?,?,?,1)", ("existing-user","Registered Player","registered@example.test","disabled","member","Member","2026",now))
                    connection.execute("INSERT INTO communities(id,name,sport,kind,mark,privacy,accent,description,activity,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", ("club","Club","Soccer","Club","C","Private","forest","Test","New","club-admin",now))
                    connection.executemany("INSERT INTO community_members(community_id,user_id,role,joined_at) VALUES(?,?,?,?)", [("club","club-admin","Admin",now),("club","existing-user","Member",now)])
                    connection.execute("INSERT INTO teams(id,community_id,name,age_group,league,mark,accent,coach,rank,formation,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",("team","club","Team","Open","Local","T","forest","Coach","1","4-3-3",now))
                    team = connection.execute("SELECT * FROM teams WHERE id='team'").fetchone()
                    player_id = service._insert_player_record(connection,team,{"name":"Player Placeholder","number":18,"pos":"CM","foot":"Right","status":"available"},None)
                    linked = service.update_player(connection,"club-admin",player_id,{"account_id":"existing-user"})
                    self.assertTrue(linked["registered"])
                    self.assertEqual(connection.execute("SELECT name FROM players WHERE id=?",(player_id,)).fetchone()["name"],"Registered Player")
            finally:
                config.DB_PATH = original

    def test_pickup_yes_increments_appearances_and_90_minutes_once(self):
        original = config.DB_PATH
        with tempfile.TemporaryDirectory() as directory:
            config.DB_PATH = Path(directory) / "match-stats.db"
            try:
                db.init_db()
                now_dt = security.utc_now()
                now = security.iso(now_dt)
                with db.connect() as connection:
                    for user_id,name in (("admin","Admin"),("player","Player 0")):
                        connection.execute("INSERT INTO users(id,name,email,password_hash,role,member_since,created_at) VALUES(?,?,?,?,?,?,?)",(user_id,name,f"{user_id}@example.test","disabled","member","2026",now))
                    connection.execute("INSERT INTO communities(id,name,sport,kind,mark,privacy,accent,description,activity,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",("club","Club","Soccer","Club","C","Public","forest","Test","New","admin",now))
                    connection.execute("INSERT INTO community_members(community_id,user_id,role,joined_at) VALUES(?,?,?,?)",("club","admin","Admin",now))
                    connection.execute("INSERT INTO community_members(community_id,user_id,role,joined_at) VALUES(?,?,?,?)",("club","player","Member",now))
                    connection.execute("INSERT INTO teams(id,community_id,name,age_group,league,mark,accent,coach,rank,formation,starting_xi_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",("team","club","Team","Open","Local","T","forest","Coach","1","4-3-3",'["p0"]',now))
                    connection.execute("INSERT INTO players(id,team_id,name,number,pos,group_name,foot,status,user_id) VALUES(?,?,?,?,?,?,?,?,?)",("p0","team","Player 0",9,"ST","FWD","Right","available","player"))
                    poll = service.create_poll(connection,"admin",{"community_id":"club","question":"Pickup","category":"Pickup","closes_at":security.iso(now_dt+timedelta(hours=1)),"game_at":security.iso(now_dt+timedelta(hours=2)),"location":"Park","options":[]})
                    yes_id = connection.execute("SELECT id FROM poll_options WHERE poll_id=? AND label='Yes'",(poll["id"],)).fetchone()["id"]
                    connection.execute("INSERT INTO poll_votes(poll_id,user_id,option_id,player_id,guest_count,created_at) VALUES(?,?,?,?,0,?)",(poll["id"],"player",yes_id,"p0",now))
                    past = security.iso(now_dt-timedelta(minutes=1))
                    connection.execute("UPDATE polls SET closes_at=?,game_at=? WHERE id=?",(past,past,poll["id"]))
                    service.process_due_polls(connection,now_dt)
                    service.process_due_polls(connection,now_dt)
                    stats = connection.execute("SELECT apps,starts,minutes FROM players WHERE id='p0'").fetchone()
                    self.assertEqual((stats["apps"],stats["starts"],stats["minutes"]),(1,0,90))
            finally:
                config.DB_PATH = original

    def test_duty_batch_assigns_members_and_rejects_member_assigning_others(self):
        original = config.DB_PATH
        with tempfile.TemporaryDirectory() as directory:
            config.DB_PATH = Path(directory) / "duty-assignment.db"
            try:
                db.init_db()
                now = security.utc_now()
                now_text = security.iso(now)
                with db.connect() as connection:
                    for user_id, role in (("admin", "admin"), ("member", "member"), ("other", "member")):
                        connection.execute("INSERT INTO users(id,name,email,password_hash,role,member_since,created_at) VALUES(?,?,?,?,?,?,?)", (user_id, user_id.title(), f"{user_id}@example.test", "disabled", role, now_text, now_text))
                    connection.execute("INSERT INTO communities(id,name,sport,kind,mark,privacy,accent,description,activity,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", ("club", "Club", "Soccer", "Community", "C", "Private", "forest", "Test", "New", "admin", now_text))
                    for user_id, role in (("admin", "Admin"), ("member", "Member"), ("other", "Member")):
                        connection.execute("INSERT INTO community_members(community_id,user_id,role,joined_at) VALUES(?,?,?,?)", ("club", user_id, role, now_text))
                    connection.execute("INSERT INTO teams(id,community_id,name,age_group,league,mark,accent,coach,rank,formation,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", ("team", "club", "Club team", "Open", "Local", "C", "forest", "Coach", "1", "4-3-3", now_text))
                    player_ids = []
                    for index in range(11):
                        player_id = f"player-{index}"
                        player_ids.append(player_id)
                        position = "GK" if index == 0 else "CB"
                        group = "GK" if index == 0 else "DEF"
                        connection.execute("INSERT INTO players(id,team_id,name,number,pos,group_name,foot,status) VALUES(?,?,?,?,?,?,?,?)", (player_id, "team", f"Player {index}", index + 1, position, group, "Right", "available"))
                    for poll_id in ("empty-poll", "voted-poll"):
                        connection.execute("INSERT INTO polls(id,community_id,question,category,author_id,closes_at,game_at,created_at) VALUES(?,?,?,?,?,?,?,?)", (poll_id, "club", poll_id, "Pickup", "admin", security.iso(now + timedelta(days=1)), security.iso(now + timedelta(days=2)), now_text))
                        connection.execute("INSERT INTO poll_options(id,poll_id,label,seed_votes) VALUES(?,?,?,10)", (f"option-{poll_id}", poll_id, "Yes"))
                    self.assertFalse(service._event_exists(connection, "empty-poll", "club"), "seeded vote totals are not actual poll votes")
                    connection.execute("INSERT INTO poll_votes(poll_id,user_id,option_id,created_at) VALUES(?,?,?,?)", ("voted-poll", "member", "option-voted-poll", now_text))
                    self.assertTrue(service._event_exists(connection, "voted-poll", "club"))
                    self.assertFalse(service._event_exists(connection, "voted-poll", "another-club"))
                    plan = service.create_plan(connection, "admin", {"title": "Match plan", "opponent": "Rivals", "date": security.iso(now + timedelta(days=2)), "venue": "Home", "objective": "Control the midfield", "board": player_ids})
                    self.assertEqual(plan["communityId"], "club")
                    updated = service.update_plan(connection, "admin", plan["id"], {"formation": "4-2-3-1", "status": "Ready", "board": player_ids[::-1], "in_possession_shape": "Build through the middle", "patterns": [{"title": "Switch play", "text": "Move it quickly wide."}], "roles": [{"role": "Pivot", "text": "Set the tempo."}], "out_trigger": "Press on a back pass.", "corner_taker": "Player 2", "checklist": ["Book the field", "Confirm players"]})
                    self.assertEqual(updated["board"], player_ids[::-1])
                    self.assertEqual(updated["formation"], "4-2-3-1")
                    self.assertEqual(updated["status"], "Ready")
                    self.assertEqual(updated["checklist"][0]["text"], "Book the field")
                    self.assertEqual(updated["setPieces"]["takers"]["corners"], "Player 2")
                    self.assertEqual(updated["inPossession"]["patterns"][0]["title"], "Switch play")
                    self.assertEqual(updated["outOfPossession"]["trigger"], "Press on a back pass.")
                    result = service.create_duty(connection, {"id": "admin"}, {"community_id": "club", "items": [
                        {"kind": "coffee", "starts_at": security.iso(now + timedelta(days=2)), "assigned_to": "member"},
                        {"kind": "drinks", "starts_at": security.iso(now + timedelta(days=2))},
                    ]})
                    self.assertEqual(len(result["duties"]), 2)
                    self.assertEqual(result["duties"][0]["assignedTo"]["id"], "member")
                    self.assertIsNone(result["duties"][1]["assignedTo"])
                    combo = service.create_duty(connection, {"id": "admin"}, {"community_id": "club", "kind": "coffee", "items": ["coffee", "donuts"], "starts_at": security.iso(now + timedelta(days=2))})
                    self.assertEqual(combo["kindLabel"], "Coffee + Donuts")
                    self.assertEqual([item["kind"] for item in combo["items"]], ["coffee", "donuts"])
                    with self.assertRaises(ApiError) as forbidden:
                        service.create_duty(connection, {"id": "member"}, {"community_id": "club", "kind": "coffee", "starts_at": security.iso(now + timedelta(days=2)), "assigned_to": "other"})
                    self.assertEqual(forbidden.exception.status, 403)
            finally:
                config.DB_PATH = original

    def test_seed_counts_and_sqlite_persistence(self):
        original = config.DB_PATH
        with tempfile.TemporaryDirectory() as directory:
            config.DB_PATH = Path(directory) / "unit.db"
            try:
                db.init_db()
                with db.connect() as connection:
                    expected = {
                        # A configured super-admin account may be provisioned; club content stays empty.
                        "users": int(bool(config.ADMIN_EMAIL and config.ADMIN_PASSWORD)),
                        "teams": 0,
                        "players": 0,
                        "communities": 0,
                        "posts": 0,
                        "polls": 0,
                    }
                    for table, count in expected.items():
                        actual = connection.execute(
                            f"SELECT COUNT(*) AS count FROM {table}"
                        ).fetchone()["count"]
                        self.assertEqual(actual, count)
                    connection.execute(
                        "INSERT INTO meta(key, value) VALUES ('unit-check', 'persisted')"
                    )
                with db.connect() as reopened:
                    row = reopened.execute(
                        "SELECT value FROM meta WHERE key = 'unit-check'"
                    ).fetchone()
                    self.assertEqual(row["value"], "persisted")
            finally:
                config.DB_PATH = original

    def test_due_poll_processing_deletes_old_polls_and_unvoted_closed_polls(self):
        original = config.DB_PATH
        with tempfile.TemporaryDirectory() as directory:
            config.DB_PATH = Path(directory) / "poll-retention.db"
            try:
                db.init_db()
                now = security.utc_now()
                with db.connect() as connection:
                    now_text = security.iso(now)
                    connection.execute("INSERT INTO users(id,name,email,password_hash,role,member_since,created_at) VALUES(?,?,?,?,?,?,?)", ("retention-admin", "Admin", "retention@example.test", "disabled", "member", now_text, now_text))
                    connection.execute("INSERT INTO users(id,name,email,password_hash,role,member_since,created_at) VALUES(?,?,?,?,?,?,?)", ("platform-admin", "Platform Admin", "platform-retention@example.test", "disabled", "admin", now_text, now_text))
                    connection.execute("INSERT INTO communities(id,name,sport,kind,mark,privacy,accent,description,activity,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", ("retention-community", "Retention Club", "Soccer", "Community", "RC", "Private", "forest", "Test", "New", "retention-admin", now_text))
                    connection.execute("INSERT INTO community_members(community_id,user_id,role,joined_at) VALUES(?,?,?,?)", ("retention-community", "retention-admin", "Admin", now_text))
                    self.assertEqual(service.set_global_poll_retention(connection, "platform-admin", {"days": 7})["days"], 7)
                    setting = service.set_community_poll_retention(connection, "retention-admin", "retention-community", {"days": 3})
                    self.assertEqual(setting["days"], 3)
                    self.assertTrue(service.get_community_poll_retention(connection, "retention-admin", "retention-community")["custom"])
                    poll_rows = (
                        ("old-poll", security.iso(now - timedelta(days=8)), security.iso(now + timedelta(days=1)), None),
                        ("recent-poll", security.iso(now - timedelta(days=6)), security.iso(now + timedelta(days=1)), None),
                        ("empty-closed-poll", security.iso(now - timedelta(days=1)), security.iso(now - timedelta(minutes=1))),
                        ("voted-closed-poll", security.iso(now - timedelta(days=1)), security.iso(now - timedelta(minutes=1))),
                    )
                    poll_rows = tuple((row[0], row[1], row[2], None) if len(row) == 3 else row for row in poll_rows)
                    poll_rows += (("community-old-poll", security.iso(now - timedelta(days=4)), security.iso(now + timedelta(days=1)), "retention-community"),)
                    for poll_id, created_at, closes_at, community_id in poll_rows:
                        connection.execute("INSERT INTO polls(id,community_id,question,category,author_id,closes_at,created_at) VALUES(?,?,?,?,?,?,?)", (poll_id, community_id, poll_id, "Club", "retention-admin", closes_at, created_at))
                        connection.execute("INSERT INTO poll_options(id,poll_id,label) VALUES(?,?,?)", (f"option-{poll_id}", poll_id, "Yes"))
                    connection.execute("INSERT INTO poll_votes(poll_id,user_id,option_id,created_at) VALUES(?,?,?,?)", ("voted-closed-poll", "retention-admin", "option-voted-closed-poll", now_text))
                    result = service.process_due_polls(connection, now=now)
                    self.assertEqual(result["deleted"], 3)
                    remaining = {row["id"] for row in connection.execute("SELECT id FROM polls")}
                    self.assertEqual(remaining, {"recent-poll", "voted-closed-poll"})
                    self.assertEqual(connection.execute("SELECT COUNT(*) FROM poll_options").fetchone()[0], 2)
                    self.assertEqual(connection.execute("SELECT COUNT(*) FROM poll_votes").fetchone()[0], 1)
            finally:
                config.DB_PATH = original

    def test_community_posts_store_one_valid_optional_banner_photo(self):
        original = config.DB_PATH
        with tempfile.TemporaryDirectory() as directory:
            config.DB_PATH = Path(directory) / "post-image.db"
            try:
                db.init_db()
                now = security.iso(security.utc_now())
                png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l7sAAAAASUVORK5CYII="
                with db.connect() as connection:
                    connection.execute("INSERT INTO users(id,name,email,password_hash,role,member_since,created_at) VALUES(?,?,?,?,?,?,?)", ("member","Member","member@example.test","disabled","member","2026",now))
                    connection.execute("INSERT INTO communities(id,name,sport,kind,mark,privacy,accent,description,activity,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", ("club","Club","Soccer","Club","C","Private","forest","Test","New","member",now))
                    connection.execute("INSERT INTO community_members(community_id,user_id,role,joined_at) VALUES(?,?,?,?)", ("club","member","Admin",now))
                    post = service.create_post(connection,"member",{"community_id":"club","text":"Matchday update","image_data":png})
                    self.assertEqual(post["media"],{"type":"image","data":png})
                    self.assertIsNone(service.create_post(connection,"member",{"community_id":"club","text":"Text only"})["media"])
                    with self.assertRaises(ApiError) as invalid:
                        service.create_post(connection,"member",{"community_id":"club","text":"Unsafe image","image_data":"javascript:alert(1)"})
                    self.assertEqual(invalid.exception.code,"invalid_image")
            finally:
                config.DB_PATH = original

    def test_foreign_keys_are_enforced(self):
        original = config.DB_PATH
        with tempfile.TemporaryDirectory() as directory:
            config.DB_PATH = Path(directory) / "fk.db"
            try:
                db.init_db()
                with db.connect() as connection:
                    with self.assertRaises(sqlite3.IntegrityError):
                        connection.execute(
                            "INSERT INTO community_members (community_id, user_id, role, joined_at) VALUES ('missing', 'alex-kim', 'Member', 'now')"
                        )
            finally:
                config.DB_PATH = original
