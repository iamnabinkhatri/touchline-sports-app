import { icon } from "../icons.js";
import {
  GROUP_NAMES,
  derivedStats,
  formatPerGame,
  neighbours,
  playerHighlights,
  positionName,
  positionSpot,
  statSections,
} from "../player-stats.js";
import { avatar, emptyState, ratingStars, statusPill } from "../ui.js";
import { escapeHTML, finiteNumber, plural } from "../utils.js";
import { FORMATIONS, playerTone } from "./teams.js";

const AVAILABILITY_COPY = {
  available: "Available for selection",
  doubtful: "Doubtful — late fitness test",
  out: "Out — unavailable",
};

export function renderPlayerProfile(state, ui, playerId) {
  const team = state.teams.find((candidate) => candidate.players.some((item) => item.id === playerId));
  const player = team?.players.find((item) => item.id === playerId);
  if (!player) {
    return `<div class="page page--player">
      ${emptyState({
        iconName: "user",
        title: "We can’t find that player",
        text: "They may have been removed from the squad.",
        action: `<a class="btn btn--primary" href="#/teams">${icon("arrowLeft", 16)} Back to the squad</a>`,
      })}
    </div>`;
  }

  const canManage = Boolean(team?.canManage);
  const players = team.players;
  const derived = derivedStats(player);
  const highlights = playerHighlights(players, player);
  const { previous, next } = neighbours(players, player.id);
  const isGoalkeeper = player.group === "GK";

  return `<div class="page page--player">
    <nav class="pp-nav reveal" aria-label="Player navigation">
      <a class="text-link" href="#/teams">${icon("arrowLeft", 16)} Squad list</a>
      ${
        previous && next
          ? `<div class="pp-pager">
              <a class="pp-pager__link" href="#/player/${escapeHTML(previous.id)}" aria-label="Previous player: ${escapeHTML(previous.name)}">${icon("chevronLeft", 16)}<span>${escapeHTML(previous.name)}</span></a>
              <a class="pp-pager__link" href="#/player/${escapeHTML(next.id)}" aria-label="Next player: ${escapeHTML(next.name)}"><span>${escapeHTML(next.name)}</span>${icon("chevronRight", 16)}</a>
            </div>`
          : ""
      }
    </nav>

    ${renderHero(player, team, highlights, canManage)}

    <section class="pp-figures reveal reveal--delay-1" aria-label="Season at a glance">
      ${renderFigures(player, derived, isGoalkeeper)}
    </section>

    <div class="pp-grid">
      <section class="pp-card pp-stats reveal reveal--delay-2" aria-labelledby="pp-stats-title">
        <header class="pp-card__head">
          <div>
            <p class="eyebrow">Season ${new Date().getFullYear()}</p>
            <h2 id="pp-stats-title">Stats</h2>
          </div>
          <span class="pp-legend"><i class="pp-legend__bar"></i>${escapeHTML(player.name.split(" ")[0])}<i class="pp-legend__tick"></i>Squad average</span>
        </header>
        ${statSections(player, players).map(renderSection).join("")}
      </section>

      <aside class="pp-side">
        ${renderRating(player)}
        ${renderAbout(player, canManage)}
        ${renderAvailability(player, team)}
        ${renderTeammates(player, players)}
      </aside>
    </div>
  </div>`;
}

function renderHero(player, team, highlights, canManage) {
  const [spotX, spotY] = positionSpot(player.pos);
  const facts = [];
  if (player.age !== null && player.age !== undefined) facts.push(["Age", String(finiteNumber(player.age))]);
  if (player.heightCm) facts.push(["Height", `${finiteNumber(player.heightCm)} cm`]);
  facts.push(["Preferred foot", escapeHTML(player.foot)]);
  facts.push(["Team", escapeHTML(team.ageGroup)]);

  return `<header class="pp-hero reveal reveal--delay-1">
    <span class="pp-hero__numeral" aria-hidden="true">${finiteNumber(player.number)}</span>
    <div class="pp-hero__identity">
      ${avatar(player.name, { size: "xl", tone: playerTone(player.id) })}
      <div class="pp-hero__copy">
        <div class="pp-hero__tags">
          ${statusPill(player.status)}
          ${highlights.map((badge) => `<span class="pp-badge">${icon("star", 12)}${escapeHTML(badge)}</span>`).join("")}
        </div>
        <h1>${escapeHTML(player.name)}</h1>
        <p class="pp-hero__role">${escapeHTML(positionName(player.pos))} <span>#${finiteNumber(player.number)}</span></p>
        <dl class="pp-facts">
          ${facts.map(([label, value]) => `<div><dt>${label}</dt><dd>${value}</dd></div>`).join("")}
        </dl>
        <div class="pp-hero__actions">
          ${
            canManage
              ? `<button class="btn btn--lime btn--sm" type="button" data-action="edit-player" data-player="${escapeHTML(player.id)}">${icon("edit", 15)} Edit player</button>
                 <button class="btn btn--ghost-light btn--sm" type="button" data-action="delete-player" data-player="${escapeHTML(player.id)}">Remove from squad</button>`
              : ""
          }
          <button class="btn btn--ghost-light btn--sm" type="button" data-action="jump-rating">${icon("star", 15)} Rate player</button>
        </div>
      </div>
    </div>
    <figure class="pp-pitch" role="img" aria-label="${escapeHTML(positionName(player.pos))}: plays ${spotY > 66 ? "in defence" : spotY > 38 ? "in midfield" : "in attack"}${spotX < 34 ? " on the left" : spotX > 66 ? " on the right" : " through the middle"}">
      <svg viewBox="0 0 100 140" aria-hidden="true" focusable="false">
        <rect class="pp-pitch__line" x="3" y="3" width="94" height="134" rx="3"/>
        <line class="pp-pitch__line" x1="3" y1="70" x2="97" y2="70"/>
        <circle class="pp-pitch__line" cx="50" cy="70" r="12"/>
        <rect class="pp-pitch__line" x="24" y="3" width="52" height="22"/>
        <rect class="pp-pitch__line" x="37" y="3" width="26" height="8"/>
        <rect class="pp-pitch__line" x="24" y="115" width="52" height="22"/>
        <rect class="pp-pitch__line" x="37" y="129" width="26" height="8"/>
        <circle class="pp-pitch__halo" cx="${spotX}" cy="${(spotY * 140) / 100}" r="9"/>
        <circle class="pp-pitch__dot" cx="${spotX}" cy="${(spotY * 140) / 100}" r="4.2"/>
      </svg>
      <figcaption><span>${escapeHTML(player.pos)}</span> ${escapeHTML(GROUP_NAMES[player.group] ?? "")}</figcaption>
    </figure>
  </header>`;
}

function renderFigures(player, derived, isGoalkeeper) {
  const figures = [
    ["Appearances", finiteNumber(player.apps), player.starts ? `${finiteNumber(player.starts)} starts` : ""],
    isGoalkeeper
      ? ["Clean sheets", finiteNumber(player.cleanSheets), derived.cleanSheetRate === null ? "" : `${derived.cleanSheetRate}% of games`]
      : ["Goals", finiteNumber(player.goals), derived.goalsPerGame === null ? "" : `${formatPerGame(derived.goalsPerGame)} per game`],
    isGoalkeeper
      ? ["Saves", finiteNumber(player.saves), derived.savesPerGame === null ? "" : `${formatPerGame(derived.savesPerGame, 1)} per game`]
      : ["Assists", finiteNumber(player.assists), derived.assistsPerGame === null ? "" : `${formatPerGame(derived.assistsPerGame)} per game`],
    ["Minutes", finiteNumber(player.minutes), derived.minutesPerGame === null ? "" : `${derived.minutesPerGame} per game`],
    [
      "Squad rating",
      Number(player.ratingCount) > 0 ? finiteNumber(player.rating).toFixed(1) : "–",
      Number(player.ratingCount) > 0 ? plural(finiteNumber(player.ratingCount), "rating") : "No ratings yet",
    ],
  ];
  return figures
    .map(
      ([label, value, hint]) => `<article class="pp-figure">
        <strong>${value}</strong>
        <span>${label}</span>
        <small>${escapeHTML(hint)}</small>
      </article>`,
    )
    .join("");
}

function renderSection(section) {
  return `<div class="pp-section">
    <h3>${escapeHTML(section.title)}</h3>
    ${section.rows.map(renderRow).join("")}
  </div>`;
}

function renderRow(row) {
  const label = `${row.label}: ${row.value}. Squad best ${row.squadBest}, squad average ${row.squadAverage.toFixed(1)}.`;
  return `<div class="pp-row">
    <div class="pp-row__top">
      <span>${escapeHTML(row.label)}</span>
      <strong>${finiteNumber(row.value)}</strong>
    </div>
    <div class="pp-bar" role="img" aria-label="${escapeHTML(label)}">
      <span class="pp-bar__fill${row.value === 0 ? " is-empty" : ""}" style="width:${finiteNumber(row.barPercent)}%"></span>
      <span class="pp-bar__avg" style="left:${finiteNumber(row.averagePercent)}%"></span>
    </div>
    <div class="pp-row__meta">
      <span>${escapeHTML(row.hint)}</span>
      <span>Squad best ${finiteNumber(row.squadBest)} · avg ${row.squadAverage.toFixed(1)}</span>
    </div>
  </div>`;
}

function renderRating(player) {
  const rating = Number(player.rating) || 0;
  const ratingCount = Number(player.ratingCount) || 0;
  const yourRating = Math.min(10, Math.max(1, Math.round(player.userRating ?? rating ?? 8)));
  return `<section class="pp-card pp-rating reveal reveal--delay-2" id="player-rating" aria-labelledby="pp-rating-title">
    <header class="pp-card__head">
      <div>
        <p class="eyebrow">Community rating</p>
        <h2 id="pp-rating-title">${ratingCount ? `${rating.toFixed(1)} <small>/ 10</small>` : "Not rated yet"}</h2>
      </div>
      ${ratingCount ? ratingStars(rating, "md") : ""}
    </header>
    <p class="pp-card__note">${ratingCount ? `${plural(ratingCount, "squad rating")}. This score powers the Pickup builder.` : "Be the first to set the benchmark."}</p>
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
  </section>`;
}

function renderAbout(player, canManage) {
  const bio = String(player.bio ?? "").trim();
  return `<section class="pp-card reveal reveal--delay-3" aria-labelledby="pp-about-title">
    <header class="pp-card__head"><div><p class="eyebrow">Scouting note</p><h2 id="pp-about-title">About</h2></div></header>
    ${
      bio
        ? `<p class="pp-bio">${escapeHTML(bio)}</p>`
        : `<p class="pp-card__note">No note yet.${canManage ? ` <button class="text-link text-link--small" type="button" data-action="edit-player" data-player="${escapeHTML(player.id)}">Add one</button>` : ""}</p>`
    }
  </section>`;
}

function renderAvailability(player, team) {
  const slots = FORMATIONS[team.formation] ?? FORMATIONS["4-3-3"];
  const slotIndex = team.startingXI.indexOf(player.id);
  const slot = slotIndex >= 0 ? slots[slotIndex] : null;
  return `<section class="pp-card reveal reveal--delay-3" aria-labelledby="pp-avail-title">
    <header class="pp-card__head"><div><p class="eyebrow">Matchday</p><h2 id="pp-avail-title">Selection</h2></div>${statusPill(player.status)}</header>
    <p class="pp-card__note">${escapeHTML(AVAILABILITY_COPY[player.status] ?? "Availability unknown")}.</p>
    <p class="pp-selection">${
      slot
        ? `${icon("flag", 15)} In the Starting XI at <strong>${escapeHTML(slot.role)}</strong> · ${escapeHTML(team.formation)}`
        : `${icon("users", 15)} On the bench for the next match`
    }</p>
  </section>`;
}

function renderTeammates(player, players) {
  const mates = players
    .filter((item) => item.group === player.group && item.id !== player.id)
    .sort((a, b) => a.number - b.number)
    .slice(0, 6);
  if (!mates.length) return "";
  return `<section class="pp-card reveal reveal--delay-3" aria-labelledby="pp-mates-title">
    <header class="pp-card__head"><div><p class="eyebrow">${escapeHTML(GROUP_NAMES[player.group] ?? "Squad")}s</p><h2 id="pp-mates-title">Same position group</h2></div></header>
    <ul class="pp-mates">
      ${mates
        .map(
          (mate) => `<li><a href="#/player/${escapeHTML(mate.id)}">
            ${avatar(mate.name, { size: "sm", tone: playerTone(mate.id) })}
            <span><strong>${escapeHTML(mate.name)}</strong><small>#${finiteNumber(mate.number)} · ${escapeHTML(mate.pos)}</small></span>
            ${icon("chevronRight", 14)}
          </a></li>`,
        )
        .join("")}
    </ul>
  </section>`;
}
