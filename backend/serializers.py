import json
from datetime import date, datetime, timedelta, timezone

from .security import initials, iso, parse_iso, utc_now


def _json(value, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def relative_time(value):
    parsed = parse_iso(value)
    if parsed is None:
        return "Just now"
    seconds = max(0, int((utc_now() - parsed).total_seconds()))
    if seconds < 90:
        return "Just now"
    if seconds < 3600:
        return f"{max(1, seconds // 60)}m"
    if seconds < 86_400:
        return f"{seconds // 3600}h"
    if seconds < 172_800:
        return "Yesterday"
    return f"{seconds // 86_400}d"


def user_public(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "initials": initials(row["name"]),
        "role": "Super Admin" if row["role"] == "admin" else row["club_role"],
        "canManageTeam": row["role"] in ("admin", "coach"),
        "email": row["email"],
        "emailVerified": bool(row["email_verified"]),
        "twoFactorEnabled": bool(row["two_factor_enabled"]),
        "memberSince": row["member_since"],
        "points": row["club_points"],
    }


DUTY_KINDS = {
    "coffee": "Coffee",
    "donuts": "Donuts",
    "snacks": "Snacks",
    "drinks": "Drinks",
    "other": "Something else",
}


def duty_dict(connection, row):
    claimer = None
    assignee = None
    if row["assigned_to"]:
        user = connection.execute(
            "SELECT id, name, avatar_tone FROM users WHERE id = ?", (row["assigned_to"],)
        ).fetchone()
        if user is not None:
            assignee = {"id": user["id"], "name": user["name"], "initials": initials(user["name"]), "tone": user["avatar_tone"]}
    if row["claimed_by"]:
        user = connection.execute(
            "SELECT id, name, avatar_tone FROM users WHERE id = ?", (row["claimed_by"],)
        ).fetchone()
        if user is not None:
            claimer = {
                "id": user["id"],
                "name": user["name"],
                "initials": initials(user["name"]),
                "tone": user["avatar_tone"],
            }
    items = _json(row["items_json"], []) if "items_json" in row.keys() else []
    if not items:
        items = [{"kind": row["kind"], "label": DUTY_KINDS.get(row["kind"], "Something else")}]
    return {
        "id": row["id"],
        "kind": row["kind"],
        "kindLabel": " + ".join(item.get("label", DUTY_KINDS.get(item.get("kind"), "Something else")) for item in items),
        "items": items,
        "title": row["title"],
        "startsAt": row["starts_at"],
        "note": row["note"] or "",
        "eventKey": row["event_key"],
        "claimedBy": claimer,
        "assignedTo": assignee,
        "claimedAt": row["claimed_at"],
        "createdById": row["created_by"],
        "communityId": row["community_id"],
    }


def community_dict(connection, row, user_id):
    membership = connection.execute(
        "SELECT role FROM community_members WHERE community_id = ? AND user_id = ?",
        (row["id"], user_id),
    ).fetchone()
    unread = connection.execute(
        """SELECT COUNT(*) AS n FROM community_messages m
        WHERE m.community_id=? AND m.user_id<>? AND m.rowid>COALESCE((
            SELECT last_read_rowid FROM community_message_reads
            WHERE community_id=? AND user_id=?
        ),0)""",
        (row["id"], user_id, row["id"], user_id),
    ).fetchone()["n"]
    join_request = connection.execute(
        "SELECT status FROM community_join_requests WHERE community_id=? AND user_id=?",
        (row["id"], user_id),
    ).fetchone()
    can_manage = bool(membership and membership["role"] == "Admin") or connection.execute("SELECT role FROM users WHERE id=?", (user_id,)).fetchone()["role"] == "admin"
    pending_join_requests = connection.execute(
        "SELECT COUNT(*) AS n FROM community_join_requests WHERE community_id=? AND status='pending'",
        (row["id"],),
    ).fetchone()["n"] if can_manage else 0
    settings = connection.execute(
        "SELECT profile_theme FROM community_settings WHERE community_id=?", (row["id"],)
    ).fetchone()
    return {
        "id": row["id"],
        "name": row["name"],
        "sport": row["sport"],
        "kind": row["kind"],
        "mark": row["mark"],
        "memberCount": row["member_count"],
        "unreadCount": unread,
        "joined": membership is not None,
        "joinRequestStatus": join_request["status"] if join_request else None,
        "role": membership["role"] if membership else None,
        "canManage": can_manage,
        "pendingJoinRequestCount": pending_join_requests,
        "privacy": row["privacy"],
        "accent": row["accent"],
        "logoData": row["logo_data"],
        "bannerData": row["banner_data"],
        "description": row["description"],
        "activity": row["activity"],
        "profileTheme": settings["profile_theme"] if settings else "light",
    }


def comment_dict(connection, row):
    author = connection.execute(
        "SELECT name, avatar_tone FROM users WHERE id = ?", (row["author_id"],)
    ).fetchone()
    return {
        "id": row["id"],
        "author": author["name"] if author else "Unknown",
        "initials": initials(author["name"]) if author else "?",
        "tone": author["avatar_tone"] if author else "forest",
        "text": row["text"],
        "time": relative_time(row["created_at"]),
    }


def post_dict(connection, row, user_id):
    author = connection.execute(
        "SELECT name, avatar_tone, club_role FROM users WHERE id = ?", (row["author_id"],)
    ).fetchone()
    community = connection.execute(
        "SELECT name FROM communities WHERE id = ?", (row["community_id"],)
    ).fetchone()
    actual_likes = connection.execute(
        "SELECT COUNT(*) AS count FROM post_likes WHERE post_id = ?", (row["id"],)
    ).fetchone()["count"]
    liked = connection.execute(
        "SELECT 1 FROM post_likes WHERE post_id = ? AND user_id = ?",
        (row["id"], user_id),
    ).fetchone() is not None
    comments = connection.execute(
        "SELECT * FROM comments WHERE post_id = ? ORDER BY created_at ASC", (row["id"],)
    ).fetchall()
    return {
        "id": row["id"],
        "authorId": row["author_id"],
        "author": author["name"] if author else "Unknown",
        "authorInitials": initials(author["name"]) if author else "?",
        "authorRole": author["club_role"] if author else "Member",
        "authorTone": author["avatar_tone"] if author else "forest",
        "communityId": row["community_id"],
        "communityName": community["name"] if community else "Clubhouse",
        "timeLabel": relative_time(row["created_at"]),
        "createdAt": row["created_at"],
        "text": row["text"],
        "tags": _json(row["tags_json"], []),
        "liked": liked,
        "likes": int(row["seed_likes"]) + int(actual_likes),
        "media": _json(row["media_json"], None),
        "comments": [comment_dict(connection, comment) for comment in comments],
    }


def poll_dict(connection, row, user_id):
    author = connection.execute(
        "SELECT name, avatar_tone FROM users WHERE id = ?", (row["author_id"],)
    ).fetchone()
    options = connection.execute(
        "SELECT * FROM poll_options WHERE poll_id = ? ORDER BY position ASC", (row["id"],)
    ).fetchall()
    option_rows = []
    vote_count = connection.execute(
        "SELECT COUNT(*) AS count FROM poll_votes WHERE poll_id = ?", (row["id"],)
    ).fetchone()["count"]
    for option in options:
        actual = connection.execute(
            "SELECT COUNT(*) AS count FROM poll_votes WHERE poll_id = ? AND option_id = ?",
            (row["id"], option["id"]),
        ).fetchone()["count"]
        option_rows.append(
            {
                "id": option["id"],
                "label": option["label"],
                "votes": int(option["seed_votes"]) + int(actual),
            }
        )
    vote = connection.execute(
        "SELECT option_id FROM poll_votes WHERE poll_id = ? AND user_id = ?",
        (row["id"], user_id),
    ).fetchone()
    role = connection.execute("SELECT role FROM users WHERE id=?", (user_id,)).fetchone()["role"]
    community_admin = bool(row["community_id"] and connection.execute("SELECT 1 FROM community_members WHERE community_id=? AND user_id=? AND role='Admin'", (row["community_id"], user_id)).fetchone())
    is_poll_author = row["author_id"] == user_id
    feedback_count = connection.execute("SELECT COUNT(DISTINCT user_id) AS n FROM poll_player_ratings WHERE poll_id=?", (row["id"],)).fetchone()["n"]
    yes_players = []
    no_count = 0
    guest_count = 0
    if row["category"] == "Pickup":
        attendance = connection.execute("""SELECT p.id,p.name,p.number,p.pos,p.group_name,p.status,v.user_id,v.guest_count,
            CASE WHEN p.rating_count + COUNT(r.value) > 0 THEN ROUND((p.rating_sum + COALESCE(SUM(r.value),0))/(p.rating_count + COUNT(r.value)),1) ELSE 6.5 END AS rating
            FROM poll_votes v JOIN poll_options o ON o.id=v.option_id JOIN players p ON p.id=v.player_id
            LEFT JOIN player_ratings r ON r.player_id=p.id
            WHERE v.poll_id=? AND lower(o.label)='yes' AND p.status<>'out'
            GROUP BY p.id ORDER BY p.number""", (row["id"],)).fetchall()
        for player in attendance:
            guest_count += int(player["guest_count"])
            yes_players.append({"id": player["id"], "name": player["name"], "number": player["number"], "position": player["pos"], "pos": player["pos"], "group": player["group_name"], "rating": player["rating"], "status": player["status"], "guest": False})
            for index in range(1, int(player["guest_count"]) + 1):
                yes_players.append({"id": f"guest-{row['id']}-{player['user_id']}-{index}", "name": f"{player['name']} · Guest {index}", "number": 0, "position": player["pos"], "pos": player["pos"], "group": player["group_name"], "rating": player["rating"], "status": player["status"], "guest": True})
        no_count = int(connection.execute("""SELECT COUNT(*) AS n FROM poll_votes v JOIN poll_options o ON o.id=v.option_id
            WHERE v.poll_id=? AND lower(o.label)='no'""", (row["id"],)).fetchone()["n"])
    return {
        "id": row["id"],
        "communityId": row["community_id"],
        "question": row["question"],
        "category": row["category"],
        "author": author["name"] if author else "Member",
        "authorInitials": initials(author["name"]) if author else "?",
        "closesAt": row["closes_at"],
        "gameAt": row["game_at"],
        "location": row["location"] if "location" in row.keys() else "",
        "voteCount": int(vote_count),
        "feedbackDueAt": row["feedback_due_at"],
        "feedbackCount": int(feedback_count),
        "autoTeams": _json(row["result_json"], None),
        "canManageTeams": role == "admin" or community_admin or is_poll_author,
        "yesPlayers": yes_players,
        "noCount": no_count,
        "guestCount": guest_count,
        "options": option_rows,
        "userVote": vote["option_id"] if vote else None,
        "featured": bool(row["featured"]),
    }


def player_dict(row, aggregate, user_rating, user_id=None):
    seed_count = int(row["rating_count"])
    seed_sum = float(row["rating_sum"])
    actual_count = int(aggregate["count"]) if aggregate else 0
    actual_sum = float(aggregate["total"] or 0) if aggregate else 0.0
    count = seed_count + actual_count
    rating = round((seed_sum + actual_sum) / count, 1) if count else 6.5
    return {
        "id": row["id"],
        "name": row["name"],
        "number": int(row["number"]),
        "pos": row["pos"],
        "group": row["group_name"],
        "foot": row["foot"],
        "status": row["status"],
        "rating": rating,
        "ratingCount": count,
        "userRating": user_rating,
        "goals": int(row["goals"]),
        "assists": int(row["assists"]),
        "apps": int(row["apps"]),
        "dateOfBirth": row["date_of_birth"],
        "age": _age(row["date_of_birth"]),
        "heightCm": row["height_cm"],
        "bio": row["bio"] or "",
        "imageData": row["image_data"],
        "starts": int(row["starts"]),
        "minutes": int(row["minutes"]),
        "yellowCards": int(row["yellow_cards"]),
        "redCards": int(row["red_cards"]),
        "cleanSheets": int(row["clean_sheets"]),
        "saves": int(row["saves"]),
        "registered": bool(row["user_id"]),
        "isMine": bool(row["user_id"] and row["user_id"] == user_id),
    }


def _age(date_of_birth):
    if not date_of_birth:
        return None
    try:
        born = date.fromisoformat(date_of_birth)
    except ValueError:
        return None
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def team_dict(connection, row, user_id):
    player_rows = connection.execute(
        "SELECT * FROM players WHERE team_id = ? ORDER BY sort_order ASC, number ASC",
        (row["id"],),
    ).fetchall()
    aggregates = {
        item["player_id"]: item
        for item in connection.execute(
            """
            SELECT player_id, SUM(value) AS total, COUNT(*) AS count
            FROM player_ratings GROUP BY player_id
            """
        ).fetchall()
    }
    user_ratings = {
        item["player_id"]: item["value"]
        for item in connection.execute(
            "SELECT player_id, value FROM player_ratings WHERE user_id = ?", (user_id,)
        ).fetchall()
    }
    can_manage = bool(connection.execute("SELECT 1 FROM community_members WHERE community_id=? AND user_id=? AND role='Admin'", (row["community_id"], user_id)).fetchone()) or connection.execute("SELECT role FROM users WHERE id=?", (user_id,)).fetchone()["role"] == "admin"
    players = []
    for player in player_rows:
        rendered = player_dict(player, aggregates.get(player["id"]), user_ratings.get(player["id"]), user_id)
        if can_manage and player["user_id"]:
            account = connection.execute("SELECT email FROM users WHERE id=?", (player["user_id"],)).fetchone()
            rendered["accountEmail"] = account["email"] if account else None
        players.append(rendered)
    registered_members = []
    if can_manage and row["community_id"]:
        registered_members = [dict(member) for member in connection.execute(
            """SELECT u.id,u.name,u.email FROM community_members cm JOIN users u ON u.id=cm.user_id
            WHERE cm.community_id=? AND u.email_verified=1
            AND NOT EXISTS (SELECT 1 FROM players p WHERE p.team_id=? AND p.user_id=u.id)
            ORDER BY u.name COLLATE NOCASE""",
            (row["community_id"], row["id"]),
        ).fetchall()]
    return {
        "id": row["id"],
        "communityId": row["community_id"],
        "canManage": can_manage,
        "name": row["name"],
        "ageGroup": row["age_group"],
        "league": row["league"],
        "mark": row["mark"],
        "accent": row["accent"],
        "coach": row["coach"],
        "record": {
            "w": int(row["record_w"]),
            "d": int(row["record_d"]),
            "l": int(row["record_l"]),
        },
        "rank": row["rank"],
        "form": _json(row["form_json"], []),
        "formation": row["formation"],
        "lineupSavedAt": row["lineup_saved_at"],
        "startingXI": _json(row["starting_xi_json"], []),
        "players": players,
        "registeredMembers": registered_members,
    }


def plan_dict(row):
    content = _json(row["content_json"], {})
    return {
        "id": row["id"],
        "communityId": row["community_id"],
        "title": row["title"],
        "opponent": row["opponent"],
        "opponentMark": row["opponent_mark"],
        "date": row["date"],
        "venue": row["venue"],
        "competition": row["competition"],
        "formation": row["formation"],
        "status": row["status"],
        "objective": row["objective"],
        "summary": row["summary"],
        "inPossession": content.get("inPossession", {}),
        "outOfPossession": content.get("outOfPossession", {}),
        "setPieces": content.get("setPieces", {}),
        "board": content.get("board", []),
        "checklist": _json(row["checklist_json"], []),
        "updatedAt": row["updated_at"],
    }


def notification_dict(row):
    return {
        "id": row["id"],
        "icon": row["icon"],
        "title": row["title"],
        "body": row["body"],
        "time": relative_time(row["created_at"]),
        "unread": bool(row["unread"]),
        "route": row["route"],
        "communityId": row["community_id"],
        "postId": row["post_id"],
        "kind": row["kind"],
        "createdAt": row["created_at"],
    }


def bootstrap(connection, user_id):
    user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        return None
    communities = connection.execute(
        """SELECT * FROM communities WHERE privacy='Public'
        OR id IN (SELECT community_id FROM community_members WHERE user_id=?)
        OR (SELECT role FROM users WHERE id=?)='admin' ORDER BY rowid ASC""",
        (user_id, user_id),
    ).fetchall()
    posts = connection.execute(
        """SELECT * FROM posts WHERE community_id IN
        (SELECT community_id FROM community_members WHERE user_id=?)
        OR (SELECT role FROM users WHERE id=?)='admin' ORDER BY created_at DESC""",
        (user_id, user_id),
    ).fetchall()
    polls = connection.execute(
        """SELECT * FROM polls WHERE community_id IS NULL OR community_id IN
        (SELECT community_id FROM community_members WHERE user_id=?)
        OR (SELECT role FROM users WHERE id=?)='admin'
        ORDER BY created_at DESC, rowid ASC""",
        (user_id, user_id),
    ).fetchall()
    teams = connection.execute("SELECT t.* FROM teams t WHERE EXISTS (SELECT 1 FROM community_members m WHERE m.community_id=t.community_id AND m.user_id=?) OR (SELECT role FROM users WHERE id=?)='admin' ORDER BY t.rowid ASC", (user_id, user_id)).fetchall()
    plans = connection.execute("""SELECT * FROM plans WHERE ?='admin'
        OR community_id IN (SELECT community_id FROM community_members WHERE user_id=?) ORDER BY date ASC""",
        (user["role"], user_id)).fetchall()
    notifications = connection.execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY rowid ASC", (user_id,)
    ).fetchall()
    leaders = connection.execute(
        "SELECT * FROM users WHERE club_points > 0 ORDER BY club_points DESC LIMIT 3"
    ).fetchall()
    event_scope = "community_id IN (SELECT community_id FROM community_members WHERE user_id=?)" if user["role"] != "admin" else "1=1"
    scope_args = (user_id,) if user["role"] != "admin" else ()
    events = connection.execute(f"SELECT * FROM events WHERE {event_scope} ORDER BY sort_order ASC, date ASC", scope_args).fetchall()
    fixtures = connection.execute(f"SELECT * FROM fixtures WHERE {event_scope} ORDER BY sort_order ASC, date ASC", scope_args).fetchall()
    cutoff = iso(datetime.now(timezone.utc) - timedelta(days=1))
    duty_rows = connection.execute(
        "SELECT * FROM duties WHERE starts_at >= ? AND (community_id IN (SELECT community_id FROM community_members WHERE user_id=?) OR ?='admin') ORDER BY starts_at ASC LIMIT 300", (cutoff, user_id, user["role"])
    ).fetchall()
    user_payload = user_public(user)
    app_theme = connection.execute("SELECT value FROM meta WHERE key='app_theme'").fetchone()
    user_payload["canManageTeam"] = user["role"] == "admin" or bool(connection.execute("SELECT 1 FROM community_members WHERE user_id=? AND role='Admin' LIMIT 1", (user_id,)).fetchone())
    return {
        "version": 2,
        "serverTime": iso(),
        "user": user_payload,
        "appTheme": app_theme["value"] if app_theme else "light",
        "communities": [community_dict(connection, row, user_id) for row in communities],
        "posts": [post_dict(connection, row, user_id) for row in posts],
        "polls": [poll_dict(connection, row, user_id) for row in polls],
        "teams": [team_dict(connection, row, user_id) for row in teams],
        "plans": [plan_dict(row) for row in plans],
        "duties": [duty_dict(connection, row) for row in duty_rows],
        "notifications": [notification_dict(row) for row in notifications],
        "leaders": [
            {
                "name": leader["name"],
                "initials": initials(leader["name"]),
                "tone": leader["avatar_tone"],
                "points": int(leader["club_points"]),
                "label": leader["club_role"],
            }
            for leader in leaders
        ],
        "schedule": [
            {
                "id": event["id"],
                "communityId": event["community_id"],
                "date": event["date"],
                "type": event["type"],
                "title": event["title"],
                "detail": event["detail"],
                "accent": event["accent"],
            }
            for event in events
        ],
        "nextFixtures": [
            {
                "id": fixture["id"],
                "communityId": fixture["community_id"],
                "opponent": fixture["opponent"],
                "opponentMark": fixture["opponent_mark"],
                "homeAway": fixture["home_away"],
                "date": fixture["date"],
                "venue": fixture["venue"],
                "competition": fixture["competition"],
                "hasRatingRequest": connection.execute("SELECT 1 FROM matchday_rating_requests WHERE fixture_id=?", (fixture["id"],)).fetchone() is not None,
            }
            for fixture in fixtures
        ],
    }
