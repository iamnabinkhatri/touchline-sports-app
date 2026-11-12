// Pure helpers behind the player profile page. No DOM access, so they can be
// unit-tested in Node and reused by other views.

export const POSITION_NAMES = {
  GK: "Goalkeeper",
  RB: "Right back",
  CB: "Centre back",
  LB: "Left back",
  LWB: "Left wing-back",
  RWB: "Right wing-back",
  DM: "Defensive midfielder",
  CM: "Central midfielder",
  AM: "Attacking midfielder",
  LM: "Left midfielder",
  RM: "Right midfielder",
  RW: "Right winger",
  LW: "Left winger",
  ST: "Striker",
};

export const GROUP_NAMES = {
  GK: "Goalkeeper",
  DEF: "Defender",
  MID: "Midfielder",
  FWD: "Forward",
};

// Where each position stands on a pitch drawn upright, attacking towards the
// top, as percentages of its width and height. Right side of the pitch is the
// player's right.
export const POSITION_SPOTS = {
  GK: [50, 91],
  RB: [84, 72],
  CB: [50, 76],
  LB: [16, 72],
  RWB: [88, 58],
  LWB: [12, 58],
  DM: [50, 60],
  CM: [50, 48],
  AM: [50, 34],
  RM: [86, 44],
  LM: [14, 44],
  RW: [82, 22],
  LW: [18, 22],
  ST: [50, 12],
};

export function positionName(pos) {
  return POSITION_NAMES[pos] ?? String(pos ?? "");
}

export function positionSpot(pos) {
  return POSITION_SPOTS[pos] ?? [50, 50];
}

function count(value) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? number : 0;
}

/** value / games, or null when there are no games to divide by. */
export function perGame(value, games) {
  const played = count(games);
  return played ? count(value) / played : null;
}

export function formatPerGame(value, digits = 2) {
  return value === null || value === undefined ? "–" : value.toFixed(digits);
}

export function percent(value, total) {
  const whole = count(total);
  return whole ? Math.round((count(value) / whole) * 100) : null;
}

/** Figures derived from a single player's totals. Null means "not enough games". */
export function derivedStats(player) {
  const apps = count(player.apps);
  const goals = count(player.goals);
  const assists = count(player.assists);
  return {
    goalInvolvements: goals + assists,
    goalsPerGame: perGame(goals, apps),
    assistsPerGame: perGame(assists, apps),
    involvementsPerGame: perGame(goals + assists, apps),
    minutesPerGame: apps ? Math.round(count(player.minutes) / apps) : null,
    startRate: percent(player.starts, apps),
    savesPerGame: perGame(player.saves, apps),
    cleanSheetRate: percent(player.cleanSheets, apps),
    cards: count(player.yellowCards) + count(player.redCards),
  };
}

const POOLS = {
  saves: (player) => player.group === "GK",
  cleanSheets: (player) => player.group === "GK" || player.group === "DEF",
};

const VALUE_OF = {
  goals: (player) => count(player.goals),
  assists: (player) => count(player.assists),
  goalInvolvements: (player) => count(player.goals) + count(player.assists),
  apps: (player) => count(player.apps),
  starts: (player) => count(player.starts),
  minutes: (player) => count(player.minutes),
  yellowCards: (player) => count(player.yellowCards),
  redCards: (player) => count(player.redCards),
  cleanSheets: (player) => count(player.cleanSheets),
  saves: (player) => count(player.saves),
  rating: (player) => (Number(player.ratingCount) > 0 ? Number(player.rating) || 0 : 0),
};

export function statValue(player, key) {
  return (VALUE_OF[key] ?? (() => 0))(player);
}

/**
 * How the squad is doing on one stat: the best value, the average and who holds
 * the best. Goalkeeping and clean-sheet stats are only compared within the
 * relevant position groups so an outfielder's zero saves does not drag it down.
 */
export function squadBenchmark(players, key) {
  const pool = players.filter(POOLS[key] ?? (() => true));
  if (!pool.length) return { max: 0, average: 0, leaders: [] };
  const values = pool.map((player) => statValue(player, key));
  const max = Math.max(...values);
  const total = values.reduce((sum, value) => sum + value, 0);
  return {
    max,
    average: total / pool.length,
    leaders: max > 0 ? pool.filter((player) => statValue(player, key) === max).map((player) => player.id) : [],
  };
}

/** Short badges for stats this player leads the squad in. At most `limit`. */
export function playerHighlights(players, player, limit = 3) {
  const badges = [];
  const leads = (key) => squadBenchmark(players, key).leaders.includes(player.id);
  if (leads("goals")) badges.push("Top scorer");
  if (leads("assists")) badges.push("Most assists");
  if (leads("cleanSheets") && player.group === "GK") badges.push("Most clean sheets");
  if (leads("rating")) badges.push("Highest rated");
  const games = Math.max(0, ...players.map((item) => count(item.apps)));
  if (games >= 5 && count(player.apps) === games && count(player.starts) === games) {
    badges.push("Ever-present");
  } else if (leads("minutes")) {
    badges.push("Most minutes");
  }
  return badges.slice(0, limit);
}

/** Previous and next players in shirt-number order, wrapping at the ends. */
export function neighbours(players, playerId) {
  const ordered = [...players].sort((a, b) => count(a.number) - count(b.number));
  const index = ordered.findIndex((player) => player.id === playerId);
  if (index === -1 || ordered.length < 2) return { previous: null, next: null };
  return {
    previous: ordered[(index - 1 + ordered.length) % ordered.length],
    next: ordered[(index + 1) % ordered.length],
  };
}

function row(players, player, key, label, hint = "") {
  const value = statValue(player, key);
  const { max, average } = squadBenchmark(players, key);
  const scale = Math.max(max, value, 1);
  return {
    key,
    label,
    value,
    hint,
    squadBest: max,
    squadAverage: average,
    barPercent: Math.round((value / scale) * 100),
    averagePercent: Math.round((average / scale) * 100),
  };
}

function gamesLabel(value, apps) {
  return apps ? `${value} in ${apps} ${apps === 1 ? "game" : "games"}` : "";
}

/**
 * The stat blocks for a profile, shaped by position: goalkeepers and defenders
 * get a defending block, everyone gets attacking, involvement and discipline.
 */
export function statSections(player, players) {
  const derived = derivedStats(player);
  const apps = count(player.apps);
  const perGameHint = (value) => (value === null ? "" : `${formatPerGame(value)} per game`);
  const sections = [];

  if (player.group === "GK" || player.group === "DEF") {
    const rows = [row(players, player, "cleanSheets", "Clean sheets", gamesLabel(count(player.cleanSheets), apps))];
    if (player.group === "GK") {
      rows.push(row(players, player, "saves", "Saves", derived.savesPerGame === null ? "" : `${formatPerGame(derived.savesPerGame, 1)} per game`));
    }
    sections.push({ id: "defending", title: player.group === "GK" ? "Goalkeeping" : "Defending", rows });
  }

  sections.push({
    id: "attacking",
    title: "Attacking",
    rows: [
      row(players, player, "goals", "Goals", perGameHint(derived.goalsPerGame)),
      row(players, player, "assists", "Assists", perGameHint(derived.assistsPerGame)),
      row(players, player, "goalInvolvements", "Goals + assists", perGameHint(derived.involvementsPerGame)),
    ],
  });

  sections.push({
    id: "involvement",
    title: "Involvement",
    rows: [
      row(players, player, "apps", "Appearances"),
      row(players, player, "starts", "Starts", derived.startRate === null ? "" : `${derived.startRate}% of games`),
      row(players, player, "minutes", "Minutes played", derived.minutesPerGame === null ? "" : `${derived.minutesPerGame} per game`),
    ],
  });

  sections.push({
    id: "discipline",
    title: "Discipline",
    rows: [
      row(players, player, "yellowCards", "Yellow cards"),
      row(players, player, "redCards", "Red cards"),
    ],
  });

  return sections;
}
