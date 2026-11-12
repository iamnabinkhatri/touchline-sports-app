const GROUP_ORDER = { GK: 0, DEF: 1, MID: 2, FWD: 3 };
const GROUPS = ["GK", "DEF", "MID", "FWD"];
const POSITION_WEIGHT = { GK: 14, DEF: 3, MID: 2, FWD: 3 };
const POSITION_LABEL = {
  GK: "Goalkeeper",
  DEF: "Defence",
  MID: "Midfield",
  FWD: "Forward",
};

function playerRating(player) {
  const value = Number(player?.rating);
  return Number.isFinite(value) ? Math.max(1, Math.min(10, value)) : 5;
}

function sortRoster(players) {
  return [...players].sort((a, b) => {
    const groupDiff = (GROUP_ORDER[a.group] ?? 5) - (GROUP_ORDER[b.group] ?? 5);
    if (groupDiff !== 0) return groupDiff;
    const ratingDiff = playerRating(b) - playerRating(a);
    if (ratingDiff !== 0) return ratingDiff;
    return a.name.localeCompare(b.name);
  });
}

function groupCounts(players) {
  return players.reduce(
    (counts, player) => {
      if (counts[player.group] !== undefined) counts[player.group] += 1;
      return counts;
    },
    { GK: 0, DEF: 0, MID: 0, FWD: 0 },
  );
}

function summarizeTeam(players) {
  const total = players.reduce((sum, player) => sum + playerRating(player), 0);
  const captain = [...players].sort(
    (a, b) =>
      playerRating(b) - playerRating(a) ||
      (b.apps ?? 0) - (a.apps ?? 0) ||
      a.name.localeCompare(b.name),
  )[0];
  return {
    players: sortRoster(players),
    totalStrength: Math.round(total * 10) / 10,
    avgStrength: players.length ? Math.round((total / players.length) * 10) / 10 : 0,
    counts: groupCounts(players),
    captainId: captain?.id ?? null,
  };
}

function mulberry32(seed) {
  let state = seed >>> 0;
  return function random() {
    state |= 0;
    state = (state + 0x6d2b79f5) | 0;
    let value = Math.imul(state ^ (state >>> 15), 1 | state);
    value = (value + Math.imul(value ^ (value >>> 7), 61 | value)) ^ value;
    return ((value ^ (value >>> 14)) >>> 0) / 4_294_967_296;
  };
}

function chooseFloater(pool) {
  const goalkeeperCount = pool.filter((player) => player.group === "GK").length;
  const candidates = pool.filter(
    (player) => goalkeeperCount <= 2 || player.group !== "GK",
  );
  return [...(candidates.length ? candidates : pool)].sort(
    (a, b) =>
      (b.apps ?? 0) - (a.apps ?? 0) ||
      playerRating(a) - playerRating(b) ||
      a.name.localeCompare(b.name),
  )[0];
}

/**
 * Splits a squad into two teams. Each possible split is scored by the gap in
 * total player ratings and the positional spread of the two teams. The split
 * with the lowest combined score wins, with a seeded tie-break for reshuffles.
 */
export function splitSquad(players, { positionAware = true, seed = 0 } = {}) {
  const pool = players.filter(Boolean);
  if (pool.length < 2) {
    return {
      teamA: summarizeTeam([]),
      teamB: summarizeTeam([]),
      floater: pool[0] ?? null,
      gap: 0,
      positionGap: 0,
      balanceScore: 0,
      poolSize: pool.length,
    };
  }

  let working = [...pool].sort((a, b) => a.id.localeCompare(b.id));
  let floater = null;
  if (working.length % 2 === 1) {
    floater = chooseFloater(working);
    working = working.filter((player) => player.id !== floater.id);
  }

  const total = working.reduce((sum, player) => sum + playerRating(player), 0);
  const totalCounts = groupCounts(working);
  const half = Math.floor(working.length / 2);
  const random = mulberry32(seed || 1);
  const tieBreak = new Map(working.map((player) => [player.id, random()]));
  let best = null;

  function evaluate(indices) {
    let strengthA = 0;
    const countsA = { GK: 0, DEF: 0, MID: 0, FWD: 0 };
    for (const index of indices) {
      const player = working[index];
      strengthA += playerRating(player);
      if (countsA[player.group] !== undefined) countsA[player.group] += 1;
    }
    const strengthB = total - strengthA;
    const countsB = {
      GK: totalCounts.GK - countsA.GK,
      DEF: totalCounts.DEF - countsA.DEF,
      MID: totalCounts.MID - countsA.MID,
      FWD: totalCounts.FWD - countsA.FWD,
    };
    const strengthGap = Math.abs(strengthA - strengthB);
    let positionPenalty = 0;
    let positionGap = 0;

    if (positionAware) {
      for (const group of GROUPS) {
        const diff = Math.abs(countsA[group] - countsB[group]);
        positionGap += diff;
        positionPenalty += diff * POSITION_WEIGHT[group];
      }
      if (
        totalCounts.GK >= 2 &&
        (countsA.GK === 0 || countsB.GK === 0)
      ) {
        positionPenalty += 30;
      }
    }

    const tieA = indices.reduce((sum, index) => sum + tieBreak.get(working[index].id), 0);
    const tieB = working.reduce(
      (sum, player, index) =>
        indices.includes(index) ? sum : sum + tieBreak.get(player.id),
      0,
    );
    const score = strengthGap * 20 + positionPenalty + (tieA - tieB) * 0.0005;

    if (!best || score < best.score) {
      best = { indices: [...indices], score, strengthGap, positionGap };
    }
  }

  if (half === 0) {
    return {
      teamA: summarizeTeam([]),
      teamB: summarizeTeam([]),
      floater,
      gap: 0,
      positionGap: 0,
      balanceScore: 0,
      poolSize: pool.length,
    };
  }

  const selected = [0];
  function walk(start, remaining) {
    if (remaining === 0) {
      evaluate(selected);
      return;
    }
    for (let index = start; index <= working.length - remaining; index += 1) {
      selected.push(index);
      walk(index + 1, remaining - 1);
      selected.pop();
    }
  }
  walk(1, half - 1);

  const teamAIds = new Set(best.indices.map((index) => working[index].id));
  const teamAPlayers = working.filter((player) => teamAIds.has(player.id));
  const teamBPlayers = working.filter((player) => !teamAIds.has(player.id));
  const gap = Math.round(best.strengthGap * 10) / 10;
  const balanceScore = Math.max(
    0,
    Math.min(100, Math.round(100 - gap * 14 - best.positionGap * 3)),
  );

  return {
    teamA: summarizeTeam(teamAPlayers),
    teamB: summarizeTeam(teamBPlayers),
    floater,
    gap,
    positionGap: best.positionGap,
    balanceScore,
    poolSize: pool.length,
  };
}

export function positionLabel(group) {
  return POSITION_LABEL[group] ?? group;
}

export function groupOrder(group) {
  return GROUP_ORDER[group] ?? 5;
}
