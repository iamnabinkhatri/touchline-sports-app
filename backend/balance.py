import itertools
import random

GROUPS = ("GK", "DEF", "MID", "FWD")
GROUP_ORDER = {"GK": 0, "DEF": 1, "MID": 2, "FWD": 3}
POSITION_WEIGHT = {"GK": 14, "DEF": 3, "MID": 2, "FWD": 3}


def _rating(player):
    value = float(player.get("rating") or 5)
    return max(1.0, min(10.0, value))


def _sort_roster(players):
    return sorted(
        players,
        key=lambda player: (
            GROUP_ORDER.get(player.get("group"), 5),
            -_rating(player),
            player.get("name", ""),
        ),
    )


def _counts(players):
    result = {group: 0 for group in GROUPS}
    for player in players:
        group = player.get("group")
        if group in result:
            result[group] += 1
    return result


def _summarize(players):
    players = list(players)
    total = sum(_rating(player) for player in players)
    captain = sorted(
        players,
        key=lambda player: (-_rating(player), -(player.get("apps") or 0), player.get("name", "")),
    )[0] if players else None
    return {
        "players": _sort_roster(players),
        "totalStrength": round(total, 1),
        "avgStrength": round(total / len(players), 1) if players else 0,
        "counts": _counts(players),
        "captainId": captain.get("id") if captain else None,
    }


def _choose_floater(pool):
    goalkeeper_count = sum(1 for player in pool if player.get("group") == "GK")
    candidates = [
        player for player in pool if goalkeeper_count > 2 or player.get("group") != "GK"
    ]
    chosen = sorted(
        candidates or pool,
        key=lambda player: (
            -(player.get("apps") or 0),
            _rating(player),
            player.get("name", ""),
        ),
    )
    return chosen[0] if chosen else None


def split_squad(players, position_aware=True, seed=0):
    pool = [player for player in players if player]
    if len(pool) < 2:
        return {
            "teamA": _summarize([]),
            "teamB": _summarize([]),
            "floater": pool[0] if pool else None,
            "gap": 0,
            "positionGap": 0,
            "balanceScore": 0,
            "poolSize": len(pool),
            "sessionLabel": "0v0",
        }

    working = sorted(pool, key=lambda player: player.get("id", ""))
    floater = None
    if len(working) % 2 == 1:
        floater = _choose_floater(working)
        working = [player for player in working if player.get("id") != floater.get("id")]

    total = sum(_rating(player) for player in working)
    total_counts = _counts(working)
    half = len(working) // 2
    randomizer = random.Random(seed or 1)
    tie_break = {player.get("id"): randomizer.random() for player in working}
    best = None

    # Fix the first player in team A to halve the symmetric combinations.
    for rest in itertools.combinations(range(1, len(working)), half - 1):
        indices = (0,) + rest
        selected_ids = {working[index].get("id") for index in indices}
        strength_a = sum(_rating(working[index]) for index in indices)
        strength_b = total - strength_a
        counts_a = _counts([working[index] for index in indices])
        counts_b = {group: total_counts[group] - counts_a[group] for group in GROUPS}
        strength_gap = abs(strength_a - strength_b)
        position_penalty = 0
        position_gap = 0
        if position_aware:
            for group in GROUPS:
                diff = abs(counts_a[group] - counts_b[group])
                position_gap += diff
                position_penalty += diff * POSITION_WEIGHT[group]
            if total_counts["GK"] >= 2 and (counts_a["GK"] == 0 or counts_b["GK"] == 0):
                position_penalty += 30
        tie_a = sum(tie_break.get(player_id, 0) for player_id in selected_ids)
        tie_b = sum(
            tie_break.get(player.get("id"), 0)
            for player in working
            if player.get("id") not in selected_ids
        )
        score = strength_gap * 20 + position_penalty + (tie_a - tie_b) * 0.0005
        if best is None or score < best["score"]:
            best = {
                "score": score,
                "ids": set(selected_ids),
                "strengthGap": strength_gap,
                "positionGap": position_gap,
            }

    if best is None:
        best = {"ids": set(), "strengthGap": 0, "positionGap": 0}

    team_a = [player for player in working if player.get("id") in best["ids"]]
    team_b = [player for player in working if player.get("id") not in best["ids"]]
    gap = round(best["strengthGap"], 1)
    position_gap = best["positionGap"]
    balance_score = max(0, min(100, round(100 - gap * 14 - position_gap * 3)))
    summary_a = _summarize(team_a)
    summary_b = _summarize(team_b)
    return {
        "teamA": summary_a,
        "teamB": summary_b,
        "floater": floater,
        "gap": gap,
        "positionGap": position_gap,
        "balanceScore": balance_score,
        "poolSize": len(pool),
        "sessionLabel": f"{len(summary_a['players'])}v{len(summary_b['players'])}",
    }
