import { splitSquad } from "../balance.js";
import { icon } from "../icons.js";
import { avatar, emptyState, ratingStars } from "../ui.js";
import { escapeHTML, formatDate, formatTime, pad, safeToken } from "../utils.js";
import { playerTone } from "./teams.js";
import { pickupTeamNames, pickupTeamTone } from "../pickup-team-names.js";

export function getPickupPool(state, ui) {
  const team = state.teams[0];
  const pickupPoll = state.polls?.find((poll) => poll.category === "Pickup" && poll.communityId === team.communityId);
  if (pickupPoll) {
    const roster = new Map(team.players.map((player) => [player.id, player]));
    const participants = (pickupPoll.yesPlayers ?? []).map((participant) => roster.get(participant.id) ?? ({
      ...participant,
      pos: participant.pos ?? participant.position,
      number: 0,
      guest: true,
      status: "available",
      apps: 0,
    }));
    const included = new Set(participants.map((player) => player.id));
    for (const id of [...(pickupPoll.autoTeams?.teamA ?? []), ...(pickupPoll.autoTeams?.teamB ?? []), pickupPoll.autoTeams?.floater].filter(Boolean)) {
      const player = roster.get(id);
      if (player && !included.has(id)) {
        participants.push(player);
        included.add(id);
      }
    }
    return participants;
  }
  return team.players.filter(
    (player) =>
      player.status === "available" || (ui.pickupIncludeDoubtful && player.status === "doubtful"),
  );
}

export function getPickupResult(state, ui) {
  const pool = getPickupPool(state, ui);
  const split = splitSquad(pool, {
    positionAware: ui.pickupPositionAware,
    seed: ui.pickupVariant,
  });
  const poll = state.polls?.find((item) => item.category === "Pickup" && item.communityId === state.teams[0]?.communityId);
  const summarize = (players) => {
    const counts = players.reduce((value, player) => { value[player.group] = (value[player.group] ?? 0) + 1; return value; }, { GK: 0, DEF: 0, MID: 0, FWD: 0 });
    const totalStrength = Math.round(players.reduce((sum, player) => sum + Number(player.rating || 0), 0) * 10) / 10;
    return { players, totalStrength, avgStrength: players.length ? Math.round(totalStrength / players.length * 10) / 10 : 0, counts, captainId: players[0]?.id ?? null };
  };
  if (!poll?.autoTeams) {
    const manual = ui.pickupManualSplit;
    if (manual && [manual.teamA, manual.teamB].flat().length + (manual.floater ? 1 : 0) === pool.length) {
      const byId = new Map(pool.map((player) => [player.id, player]));
      const teamAPlayers = manual.teamA.map((id) => byId.get(id));
      const teamBPlayers = manual.teamB.map((id) => byId.get(id));
      const floater = manual.floater ? byId.get(manual.floater) : null;
      const valid = [...teamAPlayers, ...teamBPlayers, ...(floater ? [floater] : [])].every(Boolean)
        && new Set([...manual.teamA, ...manual.teamB, ...(manual.floater ? [manual.floater] : [])]).size === pool.length
        && (floater ? (pool.length % 2 === 1 && teamAPlayers.length === teamBPlayers.length) : (pool.length % 2 ? Math.abs(teamAPlayers.length - teamBPlayers.length) === 1 : teamAPlayers.length === teamBPlayers.length));
      if (valid) {
        const a = summarize(teamAPlayers), b = summarize(teamBPlayers);
        const gap = Math.abs(a.totalStrength - b.totalStrength);
        return { ...split, teamA: a, teamB: b, floater, gap, balanceScore: Math.max(0, 100 - Math.round(gap * 10)), teamNames: manual.teamNames ?? pickupTeamNames(ui.pickupVariant) };
      }
    }
    return { ...split, teamNames: pickupTeamNames(ui.pickupVariant) };
  }
  const byId = new Map(pool.map((player) => [player.id, player]));
  const teamAPlayers = poll.autoTeams.teamA.map((id) => byId.get(id)).filter(Boolean);
  const teamBPlayers = poll.autoTeams.teamB.map((id) => byId.get(id)).filter(Boolean);
  const floater = byId.get(poll.autoTeams.floater) ?? null;
  const a = summarize(teamAPlayers), b = summarize(teamBPlayers);
  const storedNames = poll.autoTeams.teamNames;
  const teamNames = Array.isArray(storedNames) ? storedNames : storedNames ? [storedNames.teamA, storedNames.teamB] : pickupTeamNames(poll.id);
  return { ...split, teamA: a, teamB: b, floater, gap: Math.abs(a.totalStrength - b.totalStrength), positionGap: Number(poll.autoTeams.positionGap ?? split.positionGap), balanceScore: Number(poll.autoTeams.balanceScore ?? Math.max(0, 100 - Math.round(Number(poll.autoTeams.gap ?? split.gap) * 10))), teamNames };
}

export function renderPickup(state, ui) {
  if (!state.teams?.length) return `<div class="page page--pickup"><header class="page-head"><div class="page-head__copy"><p class="eyebrow">Pickup builder</p><h1>Add your club team first.</h1><p class="page-subtitle">Once your team is set up, add players and use the pickup builder to balance sides.</p></div></header><section class="panel onboarding-panel"><a class="btn btn--primary" href="#/teams">Open Team Hub</a></section></div>`;
  const team = state.teams[0];
  const pickupPoll = state.polls?.find((poll) => poll.category === "Pickup" && poll.communityId === team.communityId);
  const pool = getPickupPool(state, ui);
  const result = getPickupResult(state, ui);
  const [teamAName, teamBName] = result.teamNames ?? pickupTeamNames(ui.pickupVariant);
  const teamATone = pickupTeamTone(teamAName), teamBTone = pickupTeamTone(teamBName);
  const doubtfulCount = team.players.filter((player) => player.status === "doubtful").length;
  const outCount = team.players.filter((player) => player.status === "out").length;
  const sessionLabel = `${result.teamA.players.length}v${result.teamB.players.length}`;
  const ratings = [...team.players].sort((a, b) => {
    const order = { GK: 0, DEF: 1, MID: 2, FWD: 3 };
    return (
      (order[a.group] ?? 5) - (order[b.group] ?? 5) ||
      b.rating - a.rating ||
      a.name.localeCompare(b.name)
    );
  });
  const squadAverage = (
    team.players.reduce((sum, player) => sum + Number(player.rating), 0) /
    Math.max(1, team.players.length)
  ).toFixed(1);

  return `<div class="page page--pickup">
    <header class="page-head reveal">
      <div class="page-head__copy">
        <p class="eyebrow"><span class="eyebrow__line"></span>Pickup &amp; internal games</p>
        <h1>Fair teams. Better games.</h1>
        <p class="page-subtitle">Rate the squad, then split every session by player strength and position so nobody gets a stacked side.</p>
      </div>
      <div class="page-head__actions">
        <button class="btn btn--ghost" type="button" data-action="copy-pickup-teams">${icon("share", 17)} Copy teams</button>
        ${pickupPoll?.autoTeams ? "" : `<button class="btn btn--ghost" type="button" data-action="edit-pickup-builder-teams">Arrange players</button><button class="btn btn--primary" type="button" data-action="shuffle-teams">${icon("shuffle", 17)} Shuffle split</button>`}
      </div>
    </header>

    <section class="pickup-hero reveal reveal--delay-1">
      <div class="pickup-hero__copy">
        <span class="pickup-kicker">${icon("scale", 14)} Session builder</span>
        <h2>${pool.length} players.<br><span class="pickup-headline-long">Two teams that match up.</span><span class="pickup-headline-short">Two even teams.</span></h2>
        <p>Every possible split is scored on total squad rating and positional spread. The closest match wins — no more stacked sides at Thursday pickup.</p>
        <div class="pickup-controls">
          <button class="pickup-toggle${ui.pickupIncludeDoubtful ? " is-on" : ""}" type="button" data-action="toggle-pickup-doubtful" aria-pressed="${ui.pickupIncludeDoubtful}" ${doubtfulCount ? "" : "disabled"}>
            <span class="pickup-switch"><i></i></span>
            <span><strong>Include doubtful</strong><small>${doubtfulCount} late fitness ${doubtfulCount === 1 ? "test" : "tests"}</small></span>
          </button>
          <button class="pickup-toggle${ui.pickupPositionAware ? " is-on" : ""}" type="button" data-action="toggle-pickup-position" aria-pressed="${ui.pickupPositionAware}">
            <span class="pickup-switch"><i></i></span>
            <span><strong>Position aware</strong><small>Keepers and roles balanced</small></span>
          </button>
          ${pickupPoll?.autoTeams ? `<button class="btn btn--lime pickup-shuffle" type="button" data-action="edit-pickup-poll-teams" data-poll="${escapeHTML(pickupPoll.id)}">${icon("shuffle", 16)} Rearrange poll teams</button>` : `<button class="btn btn--ghost pickup-shuffle" type="button" data-action="edit-pickup-builder-teams">Arrange players</button><button class="btn btn--lime pickup-shuffle" type="button" data-action="shuffle-teams">${icon("shuffle", 16)} Rebalance</button>`}
        </div>
      </div>
      <div class="pickup-hero__summary">
        <span class="eyebrow eyebrow--light">Session snapshot</span>
        <div class="pickup-summary-grid">
          <div><strong>${pool.length}</strong><span>players in</span></div>
          <div><strong>${sessionLabel}</strong><span>team split</span></div>
          <div><strong>${result.gap.toFixed(1)}</strong><span>strength gap</span></div>
          <div><strong>${result.balanceScore}<small>%</small></strong><span>balance score</span></div>
        </div>
        <div class="pickup-score">
          <span>Balance</span>
          <div class="pickup-score__track"><span style="width:${result.balanceScore}%"></span></div>
          <strong>${result.balanceScore}%</strong>
        </div>
        <div class="pickup-hero__foot">${icon("check", 13)} ${outCount} unavailable ${outCount === 1 ? "player is" : "players are"} always excluded</div>
      </div>
    </section>

    ${pickupPoll ? `<section class="panel pickup-poll-attendance"><div><p class="eyebrow">Pickup poll</p><h2>${escapeHTML(pickupPoll.question)}</h2><p>${pickupPoll.gameAt ? `Starts ${escapeHTML(formatDate(pickupPoll.gameAt))} at ${escapeHTML(formatTime(pickupPoll.gameAt))} · ` : ""}${pickupPoll.yesPlayers?.length ?? 0} attending · ${pickupPoll.noCount ?? 0} No · ${pickupPoll.guestCount ?? 0} guest${pickupPoll.guestCount === 1 ? "" : "s"}. These confirmed players are used above.</p></div><div class="pickup-poll-attendance__players">${pickupPoll.yesPlayers?.length ? pickupPoll.yesPlayers.map((player) => `<span>${player.guest ? "Guest" : `#${player.number}`} ${escapeHTML(player.name)}</span>`).join("") : `<small>No players have confirmed Yes yet.</small>`}</div>${pickupPoll.autoTeams && pickupPoll.canManageTeams ? `<button class="btn btn--light btn--sm" type="button" data-action="edit-pickup-poll-teams" data-poll="${escapeHTML(pickupPoll.id)}">Manually rearrange poll teams</button>` : pickupPoll.autoTeams ? `<span class="muted">Balanced teams are shown above.</span>` : `<a class="text-link" href="#/polls">Open the poll to confirm attendance</a>`}</section>` : ""}

    <div class="pickup-layout">
      <section class="pickup-board reveal reveal--delay-2" aria-labelledby="pickup-teams-title">
        <div class="pickup-board__head">
          <div>
            <p class="eyebrow">The split</p>
            <h2 id="pickup-teams-title">${escapeHTML(teamAName)} <span>vs</span> ${escapeHTML(teamBName)}</h2>
          </div>
          <div class="pickup-board__meta">
            <span class="pickup-chip">${icon("scale", 13)} ${result.gap.toFixed(1)} strength gap</span>
            <button class="text-link text-link--small" type="button" data-action="copy-pickup-teams">${icon("share", 13)} Copy</button>
          </div>
        </div>
        ${
          result.teamA.players.length
            ? `<div class="pickup-teams">
                ${renderTeamCard(result.teamA, teamAName, teamATone, "A", "Team one", pickupPoll?.autoTeams && pickupPoll.canManageTeams ? `teamA` : null, pickupPoll?.id)}
                ${renderTeamCard(result.teamB, teamBName, teamBTone, "B", "Team two", pickupPoll?.autoTeams && pickupPoll.canManageTeams ? `teamB` : null, pickupPoll?.id)}
              </div>
              <div class="pickup-balance">
                <div class="pickup-balance__copy">
                  <span class="eyebrow">Balance check</span>
                  <strong>${result.balanceScore}% balanced</strong>
                  <p>${result.gap <= 0.5 ? "The strength gap is within half a point." : "The closest possible rating match for this pool."} ${ui.pickupPositionAware ? (result.positionGap <= 2 ? "Positions are spread as evenly as the pool allows." : "Adjust the pool to improve the positional spread.") : "Position balancing is off for this split."}</p>
                </div>
                <div class="pickup-balance__rail">
                  <div class="pickup-balance__bars">
                    <span class="pickup-balance__bar pickup-balance__bar--${teamATone}" style="width:${share(result.teamA.totalStrength, result.teamB.totalStrength)}%"></span>
                    <span class="pickup-balance__bar pickup-balance__bar--${teamBTone}" style="width:${100 - share(result.teamA.totalStrength, result.teamB.totalStrength)}%"></span>
                  </div>
                  <div class="pickup-balance__labels"><span>${escapeHTML(teamAName)} ${result.teamA.totalStrength}</span><span>${escapeHTML(teamBName)} ${result.teamB.totalStrength}</span></div>
                </div>
              </div>
              ${
                result.floater
                  ? `<div class="pickup-floater">
                      <span class="pickup-floater__icon">${icon("shuffle", 16)}</span>
                      <div><span class="eyebrow">Floater</span><strong>${escapeHTML(result.floater.name)}</strong></div>
                      <p>Rotates between both teams to keep the session even.</p>
                    </div>`
                  : ""
              }`
            : emptyState({
                iconName: "users",
                title: "Not enough players to split",
                text: result.floater ? `${result.floater.name} is held as the floater. Add one more player to start both teams.` : "Mark more players available in the team hub, or include doubtful players to build two teams.",
              })}
      </section>

      <aside class="panel pickup-ratings reveal reveal--delay-2" aria-labelledby="pickup-ratings-title">
        <div class="panel__head panel__head--compact">
          <div>
            <p class="eyebrow">Squad ratings</p>
            <h2 id="pickup-ratings-title">Rate every player</h2>
          </div>
          <span class="section-count">${team.players.length} players</span>
        </div>
        <p class="pickup-ratings__intro">Give every player a 1–10 rating. Those scores are the strength used in every split.</p>
        <div class="pickup-ratings__average">
          <div><strong>${squadAverage}</strong><span>squad average</span></div>
          <div class="pickup-ratings__stars">${ratingStars(squadAverage, "md")}<span>Community rated</span></div>
        </div>
        <div class="pickup-rating-list">
          ${ratings
            .map(
              (player) => {
                const splitIds = new Set([...(pickupPoll?.autoTeams?.teamA ?? []), ...(pickupPoll?.autoTeams?.teamB ?? []), pickupPoll?.autoTeams?.floater].filter(Boolean));
                const isExtra = Boolean(pickupPoll?.autoTeams && !pickupPoll.yesPlayers?.some((attendee) => attendee.id === player.id) && splitIds.has(player.id));
                const canAdd = Boolean(pickupPoll?.autoTeams && pickupPoll.canManageTeams && !pickupPoll.yesPlayers?.some((attendee) => attendee.id === player.id) && !splitIds.has(player.id) && player.status !== "out");
                return `<button class="pickup-rating-row${canAdd ? " is-pickup-addable" : ""}" type="button" data-action="open-player" data-player="${escapeHTML(player.id)}" ${canAdd ? `draggable="true" data-pickup-squad-player="${escapeHTML(player.id)}" data-pickup-poll="${escapeHTML(pickupPoll.id)}"` : ""}>
                ${avatar(player.name, { size: "sm", tone: playerTone(player.id) })}
                <span class="pickup-rating-row__copy">
                  <strong>${escapeHTML(player.name)}${player.status !== "available" ? `<i class="pickup-status pickup-status--${safeToken(player.status, ["available", "doubtful", "out"], "unknown")}" title="${escapeHTML(player.status)}"></i>` : ""}</strong>
                  <small>#${pad(player.number)} · ${escapeHTML(player.pos)}</small>
                </span>
                <span class="pickup-rating-row__score">
                  <strong>${Number(player.rating).toFixed(1)}</strong>
                  <small>${player.ratingCount ? `${player.ratingCount} ratings` : "Not rated yet"}</small>
                </span>
                ${canAdd ? `<span class="pickup-add-cue">Drag to team</span>` : isExtra ? `<span class="pickup-add-cue is-added">In split</span>` : player.userRating ? `<span class="pickup-your-rating">You ${player.userRating}</span>` : `<span class="pickup-rate-action">Rate</span>`}
              </button>`;
              },
            )
            .join("")}
        </div>
        <div class="pickup-ratings__foot">${icon("sparkle", 13)} Your ratings save to this clubhouse instantly.</div>
      </aside>
    </div>

    <section class="pickup-method reveal reveal--delay-3" aria-label="How the team builder works">
      <div class="pickup-method__lead">
        <span class="eyebrow">How it works</span>
        <h2>Balanced by ratings, not guesswork.</h2>
      </div>
      <div class="pickup-method__steps">
        <div><span>01</span><strong>Rate the squad</strong><p>Every player gets a 1–10 strength score from the group.</p></div>
        <div><span>02</span><strong>Respect positions</strong><p>Keepers, defenders, midfielders and forwards are spread across both sides.</p></div>
        <div><span>03</span><strong>Find the closest split</strong><p>The builder checks every possible combination and picks the smallest strength gap.</p></div>
      </div>
    </section>
  </div>`;
}

function renderTeamCard(team, name, tone, mark, kicker, dropZone = null, pollId = null) {
  const total = team.totalStrength;
  const keeperCount = team.counts.GK;
  return `<article class="pickup-team pickup-team--${tone}${dropZone ? " pickup-team--drop-target" : ""}" ${dropZone ? `data-pickup-builder-zone="${dropZone}" data-pickup-poll="${escapeHTML(pollId)}"` : ""}>
    <header class="pickup-team__head">
      <span class="pickup-team__mark">${mark}</span>
      <div class="pickup-team__name">
        <span class="eyebrow">${kicker}</span>
        <h3>${name}</h3>
      </div>
      <div class="pickup-team__total"><strong>${total.toFixed(1)}</strong><span>strength</span></div>
    </header>
    <div class="pickup-team__meta">
      <span>${team.avgStrength.toFixed(1)} avg rating</span>
      <span>${team.counts.GK} GK · ${team.counts.DEF} DEF · ${team.counts.MID} MID · ${team.counts.FWD} FWD</span>
    </div>
    <div class="pickup-team__roster">
      ${dropZone ? `<div class="pickup-builder-drop-hint">Drop an available squad member here to add them</div>` : ""}
      ${team.players
        .map(
          (player) => `${player.guest ? `<div class="pickup-player pickup-player--guest">` : `<button class="pickup-player" type="button" data-action="open-player" data-player="${escapeHTML(player.id)}">`}
            <span class="pickup-player__number">${player.guest ? "G" : pad(player.number)}</span>
            ${avatar(player.name, { size: "sm", tone: playerTone(player.id) })}
            <span class="pickup-player__copy">
              <strong>${escapeHTML(player.name)}${player.guest ? `<span class="guest-badge">Guest</span>` : player.id === team.captainId ? `<span class="captain-badge" title="Captain">C</span>` : ""}</strong>
              <small>${escapeHTML(player.pos)} · ${Number(player.rating).toFixed(1)}</small>
            </span>
            ${player.status === "doubtful" ? `<span class="pickup-fit-tag">Late test</span>` : ""}
            ${player.guest ? "" : icon("chevronRight", 13)}
          ${player.guest ? `</div>` : `</button>`}`,
        )
        .join("")}
    </div>
    <footer class="pickup-team__foot">
      <span class="${keeperCount ? "" : "is-warning"}">${keeperCount ? icon("check", 13) : icon("flag", 13)}${keeperCount ? "Natural keeper" : "No natural keeper"}</span>
      <span>${team.players.length} players</span>
    </footer>
  </article>`;
}

function share(a, b) {
  const total = a + b;
  if (!total) return 50;
  return Math.round((a / total) * 100);
}
