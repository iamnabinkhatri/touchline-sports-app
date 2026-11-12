import { icon } from "../icons.js";
import { teamAvailability } from "../store.js";
import { avatar, crest, openModal, ratingStars, statusPill } from "../ui.js";
import { escapeHTML, finiteNumber, formatDate, formatTime, pad, plural, safeToken } from "../utils.js";

export const FORMATIONS = {
  "4-3-3": [
    { role: "GK", x: 50, y: 91 },
    { role: "LB", x: 15, y: 74 },
    { role: "CB", x: 38, y: 78 },
    { role: "CB", x: 62, y: 78 },
    { role: "RB", x: 85, y: 74 },
    { role: "DM", x: 50, y: 60 },
    { role: "CM", x: 30, y: 47 },
    { role: "CM", x: 70, y: 47 },
    { role: "LW", x: 16, y: 24 },
    { role: "ST", x: 50, y: 18 },
    { role: "RW", x: 84, y: 24 },
  ],
  "4-2-3-1": [
    { role: "GK", x: 50, y: 91 },
    { role: "LB", x: 15, y: 74 },
    { role: "CB", x: 38, y: 78 },
    { role: "CB", x: 62, y: 78 },
    { role: "RB", x: 85, y: 74 },
    { role: "DM", x: 35, y: 61 },
    { role: "DM", x: 65, y: 61 },
    { role: "LM", x: 17, y: 40 },
    { role: "AM", x: 50, y: 43 },
    { role: "RM", x: 83, y: 40 },
    { role: "ST", x: 50, y: 18 },
  ],
  "3-5-2": [
    { role: "GK", x: 50, y: 91 },
    { role: "CB", x: 25, y: 78 },
    { role: "CB", x: 50, y: 81 },
    { role: "CB", x: 75, y: 78 },
    { role: "LWB", x: 9, y: 57 },
    { role: "CM", x: 32, y: 54 },
    { role: "DM", x: 50, y: 63 },
    { role: "CM", x: 68, y: 54 },
    { role: "RWB", x: 91, y: 57 },
    { role: "ST", x: 38, y: 20 },
    { role: "ST", x: 62, y: 20 },
  ],
};

const POSITION_GROUPS = [
  ["All", "all"],
  ["GK", "GK"],
  ["Defence", "DEF"],
  ["Midfield", "MID"],
  ["Forward", "FWD"],
];

const POSITIONS = ["GK", "RB", "CB", "LB", "LWB", "RWB", "DM", "CM", "AM", "LM", "RM", "RW", "LW", "ST"];

export function renderTeams(state, ui) {
  const team = state.teams.find((item) => item.id === ui.selectedTeamId) ?? state.teams[0];
  if (!team) return `<div class="page page--teams">
    <header class="page-head"><div class="page-head__copy"><p class="eyebrow">Team hub</p><h1>Add your club team.</h1>
    <p class="page-subtitle">Create the team first. Then add players, match details and plans from here.</p></div></header>
    <section class="panel onboarding-panel"><button class="btn btn--primary" type="button" data-action="new-team">${icon("team", 17)} Create club team</button></section>
  </div>`;
  const availability = teamAvailability(team);
  const playerRatio = Math.max(1, team.players.length);
  const avgRating = team.players.length ? (
    team.players.reduce((total, player) => total + player.rating, 0) / team.players.length
  ).toFixed(1) : "0.0";
  const fixture = state.nextFixtures[0];

  return `<div class="page page--teams">
    <header class="team-hero reveal">
      <span class="team-hero__watermark" aria-hidden="true">${escapeHTML(team.mark)}</span>
      <div class="team-hero__identity">
        ${crest(team.mark, "lime", "xl", team.name)}
        <div>
          <p class="eyebrow eyebrow--light"><span class="live-dot"></span>Team hub · ${escapeHTML(team.ageGroup)}</p>
          <h1>${escapeHTML(team.name)}</h1>
          <div class="team-hero__meta">
            <span>${icon("trophy", 14)}${escapeHTML(team.league)}</span>
            <span>${icon("user", 14)}Coach ${escapeHTML(team.coach)}</span>
          </div>
        </div>
      </div>
      <div class="team-hero__side">
        ${state.teams.length > 1 ? `<label class="field"><span>Community team</span><select id="team-select">${state.teams.map((item) => `<option value="${escapeHTML(item.id)}"${item.id === team.id ? " selected" : ""}>${escapeHTML(item.name)}</option>`).join("")}</select></label>` : ""}
        <div class="team-record">
          <span class="team-record__label">Season record</span>
          <strong>${finiteNumber(team.record.w)}<small>W</small> ${finiteNumber(team.record.d)}<small>D</small> ${finiteNumber(team.record.l)}<small>L</small></strong>
          <span class="form-results">${team.form
            .map((result) => `<span class="form-pill form-pill--${safeToken(result.toLowerCase(), ["w", "d", "l"], "d")}">${escapeHTML(result)}</span>`)
            .join("")}</span>
        </div>
        ${team.canManage ? `<button class="btn btn--lime" type="button" data-action="add-player">${icon("userPlus", 17)} Add player</button>` : ""}
      </div>
    </header>

    <div class="team-stats reveal reveal--delay-1">
      <article class="team-stat">
        <span class="team-stat__icon">${icon("users", 18)}</span>
        <div><strong>${team.players.length}</strong><span>Squad size</span></div>
        <small>${plural(availability.doubtful + availability.out, "player")} unavailable</small>
      </article>
      <article class="team-stat">
        <span class="team-stat__icon team-stat__icon--lime">${icon("check", 18)}</span>
        <div><strong>${availability.available}</strong><span>Available</span></div>
        <small>${Math.round((availability.available / playerRatio) * 100)}% ready for selection</small>
      </article>
      <article class="team-stat">
        <span class="team-stat__icon team-stat__icon--coral">${icon("sparkle", 18)}</span>
        <div><strong>${avgRating}</strong><span>Squad rating</span></div>
        <small>From the squad’s player ratings</small>
      </article>
      <article class="team-stat">
        <span class="team-stat__icon team-stat__icon--sky">${icon("trophy", 18)}</span>
        <div><strong>${escapeHTML(team.rank)}</strong><span>League position</span></div>
        <small>${finiteNumber(team.record.w) * 3 + finiteNumber(team.record.d)} points from 10 games</small>
      </article>
    </div>

    <div class="team-toolbar reveal reveal--delay-2">
      <div class="segmented segmented--wide" role="tablist" aria-label="Team view">
        <button class="segmented__item${ui.teamTab === "squad" ? " is-active" : ""}" type="button" role="tab" aria-selected="${ui.teamTab === "squad"}" data-action="team-tab" data-tab="squad">${icon("users", 15)} Squad list</button>
        <button class="segmented__item${ui.teamTab === "lineup" ? " is-active" : ""}" type="button" role="tab" aria-selected="${ui.teamTab === "lineup"}" data-action="team-tab" data-tab="lineup">${icon("dotsGrid", 15)} Starting XI</button>
      </div>
      <div class="team-toolbar__meta">
        <span class="save-state">${icon("check", 13)} ${team.lineupSavedAt ? "XI published" : "Saved to clubhouse"}</span>
        <a class="text-link text-link--small" href="#/pickup">${icon("shuffle", 13)} Pickup builder</a>
        <a class="text-link text-link--small" href="#/plans">Game plan ${icon("arrowRight", 14)}</a>
      </div>
    </div>

    ${
      ui.teamTab === "lineup"
        ? renderLineup(state, ui, team, availability)
        : renderSquad(state, ui, team, availability, fixture)
    }
  </div>`;
}

export function openNewTeamModal(state) {
  const available = state.communities.filter((community) => community.joined && (community.role === "Admin" || state.user.role === "Super Admin"));
  openModal({
    eyebrow: "New club team",
    title: "Add your club",
    description: "Start with the team details. You can add the roster, fixtures and plans afterward.",
    body: `<form class="form" data-form="new-team">
      <label class="field"><span>Community</span><select name="communityId" required>${available.map((community) => `<option value="${escapeHTML(community.id)}">${escapeHTML(community.name)}</option>`).join("")}</select></label>
      <label class="field"><span>Club or team name</span><input name="name" required minlength="2" maxlength="64" placeholder="e.g. Brooklyn Rangers"></label>
      <div class="form-row form-row--split">
        <label class="field"><span>Age group</span><input name="ageGroup" required minlength="2" maxlength="32" placeholder="e.g. U18"></label>
        <label class="field"><span>League</span><input name="league" required minlength="2" maxlength="64" placeholder="League name"></label>
      </div>
      <label class="field"><span>Head coach</span><input name="coach" required minlength="2" maxlength="64" placeholder="Coach name"></label>
      <label class="field"><span>Starting formation</span><select name="formation"><option>4-3-3</option><option>4-2-3-1</option><option>3-5-2</option></select></label>
      <div class="form-actions"><button class="btn btn--ghost" type="button" data-action="close-modal">Cancel</button><button class="btn btn--primary" type="submit">Create club team</button></div>
    </form>`,
  });
}

function renderSquad(state, ui, team, availability, fixture) {
  const statusCounts = availability;
  const playerRatio = Math.max(1, team.players.length);
  return `<div class="team-layout reveal reveal--delay-3">
    <section class="panel roster-panel" aria-labelledby="squad-list-title">
      <div class="panel__head">
        <div>
          <p class="eyebrow">Management</p>
          <h2 id="squad-list-title">Squad list</h2>
        </div>
        <span class="section-count" id="roster-count">${team.players.length} players</span>
      </div>
      <div class="roster-controls">
        <label class="search-field search-field--compact">
          ${icon("search", 16)}
          <input id="squad-search" type="search" value="${escapeHTML(ui.squadQuery)}" placeholder="Search the squad…" aria-label="Search the squad" autocomplete="off">
        </label>
        <div class="filter-row" role="group" aria-label="Filter by position">
          ${POSITION_GROUPS.map(
            ([label, value]) => `<button class="filter-chip filter-chip--small${ui.positionFilter === value ? " is-active" : ""}" type="button" data-action="filter-position" data-position="${value}">${label}</button>`,
          ).join("")}
        </div>
      </div>
      <div class="player-card-grid">
        ${team.players.map((player) => {
          const hidden = ui.positionFilter !== "all" && player.group !== ui.positionFilter;
          return `<button class="player-card" type="button" data-player-row data-name="${escapeHTML(player.name.toLowerCase())}" data-group="${escapeHTML(player.group)}" data-action="open-player" data-player="${escapeHTML(player.id)}" ${hidden ? "hidden" : ""}>
            <span class="player-card__photo">${avatar(player.name, { size: "xl", tone: playerTone(player.id), imageData: player.imageData, className: "player-card__avatar" })}<i>${pad(player.number)}</i></span>
            <span class="player-card__identity"><strong>${escapeHTML(player.name)}</strong><small>${escapeHTML(player.pos)} · ${escapeHTML(player.status)}</small></span>
            <span class="player-card__stats"><b>${player.rating.toFixed(1)} <small>RATING</small></b><span>${finiteNumber(player.goals)} goals · ${finiteNumber(player.assists)} assists</span></span>
          </button>`;
        }).join("")}
        <div id="roster-empty" class="table-empty" ${team.players.length ? "hidden" : ""}>${icon("search", 18)} ${team.players.length ? "No players match that search." : "No players yet."} ${!team.players.length && team.canManage ? `<button class="text-link" type="button" data-action="add-player">Add your first player</button>` : ""}</div>
      </div>
      <div class="panel__foot">
        <span>${icon("bolt", 14)} Status updates sync to the matchday plan instantly.</span>
        ${team.canManage ? `<button class="text-link text-link--small" type="button" data-action="add-player">${icon("plus", 14)} Add player</button>` : ""}
      </div>
    </section>

    <aside class="team-rail">
      <section class="panel availability-panel">
        <div class="panel__head panel__head--compact">
          <div>
            <p class="eyebrow">Readiness</p>
            <h2>Availability</h2>
          </div>
          <span class="status-pill status-pill--available"><span class="status-dot"></span>${Math.round((statusCounts.available / playerRatio) * 100)}%</span>
        </div>
        <div class="availability-strip" aria-hidden="true">
          <span class="availability-strip__available" style="width:${(statusCounts.available / playerRatio) * 100}%"></span>
          <span class="availability-strip__doubtful" style="width:${(statusCounts.doubtful / playerRatio) * 100}%"></span>
          <span class="availability-strip__out" style="width:${(statusCounts.out / playerRatio) * 100}%"></span>
        </div>
        <div class="availability-key">
          <div><span class="key-dot key-dot--available"></span><strong>${statusCounts.available}</strong><span>Available</span></div>
          <div><span class="key-dot key-dot--doubtful"></span><strong>${statusCounts.doubtful}</strong><span>Doubtful</span></div>
          <div><span class="key-dot key-dot--out"></span><strong>${statusCounts.out}</strong><span>Out</span></div>
        </div>
        <div class="availability-list">
          ${team.players
            .filter((player) => player.status !== "available")
            .map(
              (player) => `<button class="availability-row" type="button" data-action="open-player" data-player="${escapeHTML(player.id)}">
                ${avatar(player.name, { size: "xs", tone: playerTone(player.id) })}
                <span><strong>${escapeHTML(player.name)}</strong><small>${escapeHTML(player.pos)} · ${player.status === "out" ? "Rehab" : "Late fitness test"}</small></span>
                ${statusPill(player.status)}
              </button>`,
            )
            .join("")}
        </div>
      </section>

      <section class="panel next-match-panel">
        <div class="panel__head panel__head--compact">
          <div>
            <p class="eyebrow">Schedule</p>
            <h2>${fixture ? escapeHTML(fixture.opponent) : "No fixture added"}</h2>
          </div>
          ${icon("ball", 24, "panel__ghost-icon")}
        </div>
        ${fixture ? `<div class="next-match"><div class="next-match__teams">${crest(fixture.opponentMark || "FC", "coral", "sm", fixture.opponent)}<span>vs</span>${crest(team.mark, "forest", "sm", team.name)}</div><div class="next-match__date"><strong>${escapeHTML(formatDate(fixture.date))}</strong><span>${escapeHTML(formatTime(fixture.date))} · ${escapeHTML(fixture.venue)}</span></div></div><div class="next-match__meta"><span>${escapeHTML(fixture.competition)}</span></div>` : `<p class="page-subtitle">Add a fixture when your schedule is ready.</p>`}
      </section>

      <section class="panel staff-panel">
        <div class="panel__head panel__head--compact">
          <div>
            <p class="eyebrow">Football staff</p>
            <h2>Touchline crew</h2>
          </div>
        </div>
        <div class="staff-list"><div>${avatar(team.coach, { size: "sm", tone: "forest" })}<span><strong>${escapeHTML(team.coach)}</strong><small>Head coach</small></span><span class="staff-tag">Lead</span></div></div>
      </section>
    </aside>
  </div>`;
}

function renderLineup(state, ui, team, availability) {
  const slots = FORMATIONS[team.formation] ?? FORMATIONS["4-3-3"];
  const lineupPlayers = team.startingXI
    .map((id) => id ? team.players.find((player) => player.id === id) ?? null : null);
  const bench = team.players.filter((player) => !team.startingXI.includes(player.id));
  const selected = ui.lineupSelected;
  const selectedPlayer = selected
    ? team.players.find((player) => player.id === selected.id)
    : null;

  return `<div class="lineup-toolbar reveal reveal--delay-3">
    <div class="lineup-toolbar__copy">
      <p class="eyebrow">Matchday selection</p>
      <h2>Starting XI</h2>
      <p>${selectedPlayer ? `<strong>${escapeHTML(selectedPlayer.name)}</strong> selected — choose another player or an empty spot to swap.` : "Tap a player, then tap another player to swap positions. Your XI saves automatically."}</p>
    </div>
    <div class="lineup-toolbar__actions">
      <label class="formation-select">
        <span>Formation</span>
        <select id="formation-select" aria-label="Formation">
          ${Object.keys(FORMATIONS)
            .map(
              (formation) =>
                `<option value="${formation}"${team.formation === formation ? " selected" : ""}>${formation}</option>`,
            )
            .join("")}
        </select>
      </label>
      <button class="btn btn--ghost btn--sm" type="button" data-action="reset-lineup">${icon("reset", 15)} Auto-pick</button>
      ${team.canManage ? `<button class="btn btn--ghost btn--sm" type="button" data-action="clear-lineup">${icon("close", 15)} Clear XI</button>` : ""}
      <button class="btn btn--primary btn--sm" type="button" data-action="publish-lineup">${icon("flag", 15)} Publish XI</button>
    </div>
  </div>

  <div class="lineup-layout reveal reveal--delay-3">
    <section class="pitch-panel" aria-labelledby="pitch-title">
      <div class="pitch-panel__head">
        <div>
          <h2 id="pitch-title">${escapeHTML(team.formation)} <span>shape</span></h2>
          <p>${escapeHTML(team.name)} · ${escapeHTML(team.ageGroup)}</p>
        </div>
        <div class="pitch-legend">
          <span><i class="legend-dot legend-dot--natural"></i>Natural role</span>
          <span><i class="legend-dot legend-dot--out"></i>Out of role</span>
        </div>
      </div>
      <div class="pitch-wrap">
        <div class="pitch">
          <span class="pitch__stripe pitch__stripe--1"></span>
          <span class="pitch__stripe pitch__stripe--2"></span>
          <span class="pitch__stripe pitch__stripe--3"></span>
          <span class="pitch__stripe pitch__stripe--4"></span>
          <span class="pitch__halfway"></span>
          <span class="pitch__circle"></span>
          <span class="pitch__spot"></span>
          <span class="pitch__box pitch__box--top"></span>
          <span class="pitch__box pitch__box--bottom"></span>
          <span class="pitch__six pitch__six--top"></span>
          <span class="pitch__six pitch__six--bottom"></span>
          <span class="pitch__goal pitch__goal--top"></span>
          <span class="pitch__goal pitch__goal--bottom"></span>
          ${slots
            .map((slot, index) => {
              const player = lineupPlayers[index];
              if (!player) {
                return `<button class="pitch-player pitch-player--empty" type="button" style="left:${slot.x}%;top:${slot.y}%" data-action="${team.canManage ? "lineup-add-player" : "lineup-pick"}" data-source="pitch" data-player="" data-slot="${index}" data-lineup-drop-slot="${index}" aria-label="${team.canManage ? `Add a registered player to empty ${slot.role} spot` : `Empty ${slot.role} spot`}">
                  <span class="pitch-player__plus">${icon("plus", 16)}</span>
                  <span class="pitch-player__role">${slot.role}</span>
                </button>`;
              }
              const isSelected = selected?.id === player.id;
              const natural = player.group === roleGroup(slot.role);
              return `<button class="pitch-player${isSelected ? " is-selected" : ""}${natural ? "" : " is-out-of-role"}" type="button" draggable="true" data-lineup-drag-id="${escapeHTML(player.id)}" data-lineup-source="pitch" style="left:${slot.x}%;top:${slot.y}%" data-action="lineup-pick" data-source="pitch" data-player="${escapeHTML(player.id)}" data-slot="${index}" data-lineup-drop-slot="${index}" aria-pressed="${isSelected}" aria-label="${escapeHTML(player.name)}, ${slot.role}. Drag to another spot or bench player to swap.">
                <span class="pitch-player__shirt">${player.number}</span>
                <span class="pitch-player__name">${escapeHTML(shortName(player.name))}</span>
                <span class="pitch-player__role">${slot.role}</span>
                ${natural ? "" : `<span class="pitch-player__warn" title="Out of natural role"></span>`}
              </button>`;
            })
            .join("")}
        </div>
        <span class="pitch-side-label pitch-side-label--top">ATTACK</span>
        <span class="pitch-side-label pitch-side-label--bottom">DEFEND</span>
      </div>
    </section>

    <aside class="lineup-rail">
      <section class="panel bench-panel">
        <div class="panel__head panel__head--compact">
          <div>
            <p class="eyebrow">Rotation</p>
            <h2>Bench</h2>
          </div>
          <span class="section-count">${bench.length} players</span>
        </div>
        <p class="bench-note">${icon("bolt", 14)} Drag a player onto an empty XI slot, or tap a player and then tap a spot.</p>
        <div class="bench-list">
          ${bench
            .map((player) => {
              const isSelected = selected?.id === player.id;
              return `<button class="bench-player${isSelected ? " is-selected" : ""}${player.status === "out" ? " is-out" : ""}" type="button" draggable="true" data-lineup-drag-id="${escapeHTML(player.id)}" data-lineup-source="bench" data-lineup-drop-bench="${escapeHTML(player.id)}" data-action="lineup-pick" data-source="bench" data-player="${escapeHTML(player.id)}" aria-pressed="${isSelected}" aria-label="${escapeHTML(player.name)} on bench. Drag onto a starting XI spot or another bench player to swap.">
                <span class="shirt-number">${pad(player.number)}</span>
                ${avatar(player.name, { size: "sm", tone: playerTone(player.id) })}
                <span class="bench-player__copy">
                  <strong>${escapeHTML(player.name)}</strong>
                  <small>${escapeHTML(player.pos)} · ${player.rating.toFixed(1)} rating</small>
                </span>
                ${statusPill(player.status)}
              </button>`;
            })
            .join("")}
        </div>
      </section>

      <section class="panel lineup-summary">
        <div class="panel__head panel__head--compact">
          <div>
            <p class="eyebrow">Selection check</p>
            <h2>Matchday ready</h2>
          </div>
          <span class="status-pill status-pill--${availability.doubtful + availability.out > 2 ? "doubtful" : "available"}"><span class="status-dot"></span>${availability.available}/${team.players.length} fit</span>
        </div>
        <div class="lineup-summary__rows">
          <div><span>Formation</span><strong>${escapeHTML(team.formation)}</strong></div>
          <div><span>Players in natural roles</span><strong>${lineupPlayers.filter((player, index) => player && player.group === roleGroup(slots[index].role)).length}/11</strong></div>
          <div><span>Unavailable in XI</span><strong>${lineupPlayers.filter((player) => player && player.status !== "available").length}</strong></div>
          <div><span>Average XI rating</span><strong>${(lineupPlayers.reduce((total, player) => total + (player?.rating ?? 0), 0) / Math.max(1, lineupPlayers.filter(Boolean).length)).toFixed(1)}</strong></div>
        </div>
        <div class="lineup-tip">${icon("sparkle", 15)} <span>Tip: publish the XI to notify the squad and lock the team sheet.</span></div>
      </section>
    </aside>
  </div>`;
}

export function openPlayerModal(state, playerId) {
  const team = state.teams.find((candidate) => candidate.players.some((item) => item.id === playerId));
  const player = team?.players.find((item) => item.id === playerId);
  if (!player) return;
  const rating = Number(player.rating) || 0;
  const ratingCount = Number(player.ratingCount) || 0;
  const yourRating = Math.min(10, Math.max(1, Math.round(player.userRating ?? rating ?? 8)));
  openModal({
    eyebrow: `${player.pos} · #${player.number} · ${rating.toFixed(1)} squad rating`,
    title: player.name,
    description: `${team.name} ${team.ageGroup} · ${player.foot}-footed`,
    wide: true,
    body: `<div class="player-modal">
      <div class="player-modal__hero">
        ${avatar(player.name, { size: "xl", tone: playerTone(player.id), imageData: player.imageData })}
        <div>
          ${statusPill(player.status)}
          <h3>${escapeHTML(player.name)}</h3>
          <p>${escapeHTML(player.pos)} · ${finiteNumber(player.apps)} appearances this season</p>
        </div>
      </div>
      <div class="player-stat-grid">
        <div><strong>${rating.toFixed(1)}</strong><span>Squad rating</span></div>
        <div><strong>${ratingCount}</strong><span>Ratings</span></div>
        <div><strong>${finiteNumber(player.goals)}</strong><span>Goals</span></div>
        <div><strong>${finiteNumber(player.assists)}</strong><span>Assists</span></div>
      </div>

      <section class="player-rate">
        <div class="player-rate__head">
          <div class="player-rate__summary">
            <span class="eyebrow">Community rating</span>
            <div class="player-rate__score">
              <strong>${rating.toFixed(1)}</strong><span>/ 10</span>
              ${ratingStars(rating, "md")}
            </div>
            <p>${ratingCount ? `${ratingCount} squad ratings · this score powers the Pickup builder.` : "No ratings yet — be the first to set the benchmark."}</p>
          </div>
          <div class="player-rate__strength">
            <span>Player strength</span>
            <strong>${rating.toFixed(1)}</strong>
            <small>Used for balanced teams</small>
          </div>
        </div>
        <form class="rating-form" data-form="rate-player" data-player="${escapeHTML(player.id)}">
          <div class="rating-form__top">
            <span>Your rating</span>
            <strong><span class="rating-pick-value">${yourRating}</span><small>/ 10</small></strong>
          </div>
          <div class="rating-picker" role="group" aria-label="Rate ${escapeHTML(player.name)} from 1 to 10">
            ${Array.from({ length: 10 }, (_, index) => index + 1)
              .map(
                (value) => `<button class="rating-choice${value === yourRating ? " is-active" : ""}" type="button" data-action="pick-rating" data-value="${value}" aria-label="${value} out of 10" aria-pressed="${value === yourRating}">${value}</button>`,
              )
              .join("")}
          </div>
          <input type="hidden" name="rating" value="${yourRating}">
          <div class="rating-form__foot">
            <span>${player.userRating ? "Saving replaces your previous score." : "One rating per member. You can change it any time."}</span>
            <button class="btn btn--primary btn--sm" type="submit">${icon("star", 14)} ${player.userRating ? "Update rating" : "Save rating"}</button>
          </div>
        </form>
      </section>

      ${team.canManage ? `<form class="form" data-form="update-player" data-player="${escapeHTML(player.id)}">
        <label class="field"><span>Player photo</span><input name="image" type="file" accept="image/png,image/jpeg,image/webp"><small>Square or portrait image, compressed before saving.</small></label>
        ${player.imageData ? `<label class="check-row"><input name="removeImage" type="checkbox"><span>Remove the current player photo</span></label>` : ""}
        ${player.registered ? `<p class="form-note">Registered account: ${escapeHTML(player.accountEmail ?? "Account linked")}. No email is needed.</p>` : `<label class="field"><span>Registered community member (optional)</span><select name="account_id"><option value="">Choose a member to link</option>${(team.registeredMembers ?? []).map((member) => `<option value="${escapeHTML(member.id)}">${escapeHTML(member.name)}</option>`).join("")}</select><small>Pick an existing verified community member to link without email.</small></label><label class="field"><span>Player email for signup invitation</span><input name="email" type="email" autocomplete="email" placeholder="player@example.com"><small>If they are not registered or in the community, enter their email. We’ll send a signup link; after verification, their account joins this community and claims this player profile.</small></label>`}
        <div class="form-row form-row--split">
          <label class="field">
            <span>Name</span>
            <input name="name" type="text" value="${escapeHTML(player.name)}" required maxlength="50">
          </label>
          <label class="field">
            <span>Shirt number</span>
            <input name="number" type="number" value="${player.number}" min="1" max="99" required>
          </label>
        </div>
        <div class="form-row form-row--split">
          <label class="field">
            <span>Position</span>
            <select name="pos">
              ${POSITIONS.map((pos) => `<option value="${pos}"${player.pos === pos ? " selected" : ""}>${pos}</option>`).join("")}
            </select>
          </label>
          <label class="field">
            <span>Preferred foot</span>
            <select name="foot">
              ${["Right", "Left", "Both"].map((foot) => `<option value="${foot}"${player.foot === foot ? " selected" : ""}>${foot}</option>`).join("")}
            </select>
          </label>
        </div>
        <label class="field">
          <span>Availability</span>
          <select name="status">
            <option value="available"${player.status === "available" ? " selected" : ""}>Available for selection</option>
            <option value="doubtful"${player.status === "doubtful" ? " selected" : ""}>Doubtful — late fitness test</option>
            <option value="out"${player.status === "out" ? " selected" : ""}>Out — unavailable</option>
          </select>
        </label>
        <details class="form-extra">
          <summary>Profile details</summary>
          <div class="form-row form-row--split">
            <label class="field">
              <span>Date of birth</span>
              <input name="date_of_birth" type="date" value="${player.dateOfBirth ?? ""}" max="${new Date().toISOString().slice(0,10)}">
            </label>
            <label class="field">
              <span>Height (cm)</span>
              <input name="height_cm" type="number" placeholder="168" min="100" max="230" value="${player.heightCm ?? ""}"
            </label>
          </div>
          <label class="field">
            <span>Scouting note</span>
            <textarea name="bio" maxlength="400" rows="2">${escapeHTML(player.bio ?? "")}</textarea>
          </label>
          <p class="eyebrow">Season ${new Date().getFullYear()} stats</p>
          <div class="form-row form-row--split">
            ${[["clean_sheets","Clean sheets","cleanSheets"],["goals","Goals","goals"],["assists","Assists","assists"],["apps","Appearances","apps"],["starts","Starts","starts"],["minutes","Minutes played","minutes"],["yellow_cards","Yellow cards","yellowCards"],["red_cards","Red cards","redCards"]].map(([key,label,field]) => `<label class="field"><span>${label}</span><input name="${key}" type="number" min="0" value="${finiteNumber(player[field])}"></label>`).join("")}
          </div>
        </details>
        <div class="form-actions">
          <button class="btn btn--ghost" type="button" data-action="close-modal">Cancel</button>
          <button class="btn btn--primary" type="submit">${icon("check", 16)} Save player</button>
        </div>
      </form>` : ""}
    </div>`,
  });
}

export function openAddPlayerModal(teamId, xiSlot = null) {
  openModal({
    eyebrow: "Squad management",
    title: "Add a player",
    description: "New squad member? Add them here and set their availability for matchday.",
    body: `<form class="form" data-form="add-player"${xiSlot === null ? "" : ` data-xi-slot="${Number(xiSlot)}"`}><input type="hidden" name="teamId" value="${escapeHTML(teamId ?? "")}">
      <div class="form-row form-row--split">
        <label class="field">
          <span>Full name</span>
          <input name="name" type="text" placeholder="e.g. Avery Johnson" required maxlength="50" autocomplete="off">
        </label>
        <label class="field">
          <span>Shirt number</span>
          <input name="number" type="number" placeholder="19" min="1" max="99" required>
        </label>
      </div>
      <div class="form-row form-row--split">
        <label class="field">
          <span>Position</span>
          <select name="pos">
            ${POSITIONS.map((pos) => `<option value="${pos}">${pos}</option>`).join("")}
          </select>
        </label>
        <label class="field">
          <span>Preferred foot</span>
          <select name="foot">
            <option>Right</option>
            <option>Left</option>
            <option>Both</option>
          </select>
        </label>
      </div>
      <label class="field">
        <span>Player email</span>
        <input name="email" type="email" placeholder="player@example.com" required autocomplete="email">
        <small>Existing verified accounts are added now. New players receive an account registration link and join this community after signing up.</small>
      </label>
      <label class="field">
        <span>Availability</span>
        <select name="status">
          <option value="available">Available for selection</option>
          <option value="doubtful">Doubtful — late fitness test</option>
          <option value="out">Out — unavailable</option>
        </select>
      </label>
      <label class="field"><span>Player photo</span><input name="image" type="file" accept="image/png,image/jpeg,image/webp"><small>Square or portrait image, compressed before saving.</small></label>
      <details class="form-extra">
        <summary>Profile details and season stats</summary>
        <div class="form-row form-row--split">
          <label class="field">
            <span>Date of birth</span>
            <input name="date_of_birth" type="date" max="${new Date().toISOString().slice(0,10)}">
          </label>
          <label class="field">
            <span>Height (cm)</span>
            <input name="height_cm" type="number" placeholder="168" min="100" max="230">
          </label>
        </div>
        <label class="field">
          <span>Scouting note</span>
          <textarea name="bio" maxlength="400" rows="2" placeholder="e.g. Quick over ten yards, left-footed."></textarea>
        </label>
        <p class="eyebrow">Season ${new Date().getFullYear()} stats</p>
        <div class="form-row form-row--split">
          ${[["clean_sheets","Clean sheets"],["goals","Goals"],["assists","Assists"],["apps","Appearances"],["starts","Starts"],["minutes","Minutes played"],["yellow_cards","Yellow cards"],["red_cards","Red cards"]].map(([key,label]) => `<label class="field"><span>${label}</span><input name="${key}" type="number" min="0" value="0"></label>`).join("")}
        </div>
      </details>
      <div class="form-note">${icon("sparkle", 14)} New players start with a 6.5 rating and can be added to the XI right away.</div>
      <div class="form-actions">
        <button class="btn btn--ghost" type="button" data-action="close-modal">Cancel</button>
        <button class="btn btn--primary" type="submit">${icon("userPlus", 16)} Add to squad</button>
      </div>
    </form>`,
  });
}

export function autoLineup(team, formation) {
  const slots = FORMATIONS[formation] ?? FORMATIONS["4-3-3"];
  const pool = [...team.players].sort((a, b) => {
    const score = (player) => {
      if (player.status === "out") return -10;
      if (player.status === "doubtful") return -3;
      return player.rating;
    };
    return score(b) - score(a);
  });
  const picked = [];
  const fits = (player, role) => {
    if (player.pos === role) return true;
    return player.group === roleGroup(role);
  };
  for (const slot of slots) {
    let candidate = pool.find((player) => !picked.includes(player.id) && player.pos === slot.role);
    if (!candidate) {
      candidate = pool.find((player) => !picked.includes(player.id) && fits(player, slot.role));
    }
    if (!candidate) {
      candidate = pool.find((player) => !picked.includes(player.id));
    }
    if (candidate) picked.push(candidate.id);
  }
  return picked.slice(0, 11);
}

export function playerTone(id) {
  const tones = ["forest", "lime", "coral", "sky", "violet", "gold", "sage"];
  let total = 0;
  for (let index = 0; index < id.length; index += 1) {
    total += id.charCodeAt(index) * (index + 1);
  }
  return tones[total % tones.length];
}

function roleGroup(role) {
  if (role === "GK") return "GK";
  if (["RB", "CB", "LB", "LWB", "RWB"].includes(role)) return "DEF";
  if (["DM", "CM", "AM", "LM", "RM"].includes(role)) return "MID";
  return "FWD";
}

function shortName(name) {
  const parts = name.split(" ");
  if (parts.length < 2) return name;
  return `${parts[0][0]}. ${parts.slice(1).join(" ")}`;
}
