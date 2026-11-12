import { icon } from "../icons.js";
import { planProgress } from "../store.js";
import {
  avatar,
  emptyState,
  openModal,
  progressRing,
} from "../ui.js";
import {
  escapeHTML,
  formatDate,
  formatTime,
  pad,
} from "../utils.js";
import { autoLineup, FORMATIONS, playerTone } from "./teams.js";

const PLAN_TABS = [
  ["overview", "Overview"],
  ["in-possession", "In possession"],
  ["out-of-possession", "Out of possession"],
  ["set-pieces", "Set pieces"],
];

export function renderPlans(state, ui) {
  const canCreate = Boolean(state.teams.some((team) => team.canManage) || state.user.role === "Super Admin");
  const selected =
    state.plans.find((plan) => plan.id === ui.selectedPlanId) ?? state.plans[0];
  if (!selected) {
    return `<div class="page">${emptyState({
      iconName: "clipboard",
      title: "No game plans yet",
      text: "Build your first matchday plan to get the squad on the same page.",
      action: canCreate ? `<button class="btn btn--primary" type="button" data-action="new-plan">${icon("plus", 16)} New plan</button>` : "",
    })}</div>`;
  }
  const progress = planProgress(selected);
  const completed = selected.checklist.filter((item) => item.done).length;
  const team = state.teams.find((item) => item.communityId === selected.communityId) ?? state.teams[0] ?? null;
  const canEdit = Boolean(team?.canManage || state.user.role === "Super Admin");

  return `<div class="page page--plans">
    <header class="page-head reveal">
      <div class="page-head__copy">
        <p class="eyebrow"><span class="eyebrow__line"></span>Game plans</p>
        <h1>Own the details.</h1>
        <p class="page-subtitle">A shared plan for every matchday: the idea, the triggers, the set pieces, and the jobs.</p>
      </div>
      <div class="page-head__actions">
        ${canCreate ? `<button class="btn btn--primary" type="button" data-action="new-plan">${icon("plus", 17)} New game plan</button>` : ""}
        ${canEdit ? `<button class="btn btn--ghost" type="button" data-action="edit-plan" data-plan="${escapeHTML(selected.id)}">${icon("edit", 16)} Edit plan</button>` : ""}
      </div>
    </header>

    <div class="plan-switcher reveal reveal--delay-1" role="group" aria-label="Game plan library">
      ${state.plans
        .map(
          (plan) => `<button class="plan-switch${plan.id === selected.id ? " is-active" : ""}" type="button" data-action="select-plan" data-plan="${escapeHTML(plan.id)}">
            <span class="plan-switch__top">
              <span class="plan-status plan-status--${statusSlug(plan.status)}">${escapeHTML(plan.status)}</span>
              <span>${escapeHTML(formatDate(plan.date))}</span>
            </span>
            <strong>${escapeHTML(plan.title)}</strong>
            <span class="plan-switch__meta">vs ${escapeHTML(plan.opponent)} · ${escapeHTML(plan.formation)}</span>
            <span class="plan-switch__bar"><span style="width:${planProgress(plan)}%"></span></span>
          </button>`,
        )
        .join("")}
      <button class="plan-switch plan-switch--new" type="button" data-action="new-plan">
        <span class="plan-switch__plus">${icon("plus", 22)}</span>
        <strong>New plan</strong>
        <span class="plan-switch__meta">Start from a blank page</span>
      </button>
    </div>

    <section class="plan-stage reveal reveal--delay-2" aria-labelledby="plan-title">
      <span class="plan-stage__watermark" aria-hidden="true">${escapeHTML(selected.formation)}</span>
      <div class="plan-stage__top">
        <div class="plan-stage__tags">
          <span class="plan-status plan-status--${statusSlug(selected.status)}">${icon("flag", 12)}${escapeHTML(selected.status)}</span>
          <span class="plan-stage__competition">${escapeHTML(selected.competition)}</span>
        </div>
        <span class="plan-stage__updated">${icon("clock", 13)} Updated ${formatDate(selected.updatedAt)}</span>
      </div>
      <div class="plan-stage__main">
        <div class="plan-stage__copy">
          <p class="eyebrow eyebrow--light">Matchday plan</p>
          <h2 id="plan-title"><span>vs</span> ${escapeHTML(selected.opponent)}</h2>
          <div class="plan-stage__meta">
            <span>${icon("calendar", 15)}${escapeHTML(formatDate(selected.date))}</span>
            <span>${icon("clock", 15)}${escapeHTML(formatTime(selected.date))}</span>
            <span>${icon("pin", 15)}${escapeHTML(selected.venue)}</span>
            <span>${icon("dotsGrid", 15)}${escapeHTML(selected.formation)}</span>
          </div>
          <p class="plan-stage__objective">${escapeHTML(selected.objective)}</p>
        </div>
        <div class="plan-stage__progress">
          ${progressRing(progress, "plan complete", 104)}
          <span>${completed} of ${selected.checklist.length} checklist items</span>
          <a href="#plan-checklist" class="stage-link">View checklist ${icon("arrowRight", 14)}</a>
        </div>
      </div>
      <div class="plan-stage__strip">
        <div><span>Venue</span><strong>${escapeHTML(selected.venue)}</strong></div>
        <div><span>Kick-off</span><strong>${escapeHTML(formatTime(selected.date))}</strong></div>
        <div><span>Shape</span><strong>${escapeHTML(selected.formation)}</strong></div>
        <div><span>Plan owner</span><strong>Club staff</strong></div>
        <div class="plan-stage__strip-action"><button class="text-link text-link--light" type="button" data-action="copy-plan" data-plan="${escapeHTML(selected.id)}">${icon("share", 14)} Copy match brief</button></div>
      </div>
    </section>

    ${renderPlanBoard(selected, team, ui, canEdit)}

    <div class="plan-layout">
      <section class="panel plan-detail reveal reveal--delay-3" aria-labelledby="plan-detail-title">
        <div class="plan-tabs" role="tablist" aria-label="Game plan sections">
          ${PLAN_TABS.map(
            ([value, label]) => `<button class="plan-tab${ui.planTab === value ? " is-active" : ""}" type="button" role="tab" aria-selected="${ui.planTab === value}" data-action="plan-tab" data-tab="${value}">${label}</button>`,
          ).join("")}
        </div>
        <div class="plan-detail__body">
          <div class="plan-detail__heading">
            <div>
              <p class="eyebrow">${escapeHTML(selected.formation)} · ${escapeHTML(tabEyebrow(ui.planTab))}</p>
              <h2 id="plan-detail-title">${escapeHTML(tabTitle(ui.planTab))}</h2>
            </div>
            <span class="plan-detail__badge">${icon("eye", 13)} Shared with squad</span>
          </div>
          ${renderPlanTab(selected, ui.planTab)}
        </div>
      </section>

      <aside class="plan-rail reveal reveal--delay-3">
        <section class="panel checklist-panel" id="plan-checklist">
          <div class="panel__head panel__head--compact">
            <div>
              <p class="eyebrow">Matchday</p>
              <h2>Checklist</h2>
            </div>
            <span class="checklist-count">${completed}/${selected.checklist.length}</span>
          </div>
          <div class="checklist-progress"><span style="width:${progress}%"></span></div>
          <div class="checklist">
            ${selected.checklist
              .map(
                (item) => `<button class="checklist-item${item.done ? " is-done" : ""}" type="button" data-action="toggle-check" data-plan="${escapeHTML(selected.id)}" data-check="${escapeHTML(item.id)}" role="checkbox" aria-checked="${item.done}">
                  <span class="checklist-box">${item.done ? icon("check", 12) : ""}</span>
                  <span>${escapeHTML(item.text)}</span>
                </button>`,
              )
              .join("")}
          </div>
          <div class="checklist-foot">${icon("sparkle", 14)} ${progress === 100 ? "Plan complete. Go win the game." : "Tick these off before the team sheet goes in."}</div>
        </section>

        <section class="panel plan-info-panel">
          <div class="panel__head panel__head--compact">
            <div>
              <p class="eyebrow">Reference</p>
              <h2>Match details</h2>
            </div>
          </div>
          <div class="info-list">
            <div><span>Opponent</span><strong>${escapeHTML(selected.opponent)}</strong></div>
            <div><span>Date</span><strong>${escapeHTML(formatDate(selected.date))}</strong></div>
            <div><span>Venue</span><strong>${escapeHTML(selected.venue)}</strong></div>
            <div><span>Formation</span><strong>${escapeHTML(selected.formation)}</strong></div>
          </div>
          <div class="plan-owner">
            <div><strong>Club plan</strong><span>Updated ${escapeHTML(formatDate(selected.updatedAt))}</span></div>
            ${icon("check", 14, "plan-owner__check")}
          </div>
        </section>

        <section class="panel set-piece-rail">
          <div class="panel__head panel__head--compact">
            <div>
              <p class="eyebrow">Dead balls</p>
              <h2>Set-piece takers</h2>
            </div>
          </div>
          <div class="taker-list"><div><span class="taker-type">Corners</span><strong>${escapeHTML(selected.setPieces.takers?.corners || "Not assigned")}</strong></div><div><span class="taker-type">Free kicks</span><strong>${escapeHTML(selected.setPieces.takers?.freeKicks || "Not assigned")}</strong></div><div><span class="taker-type">Penalties</span><strong>${escapeHTML(selected.setPieces.takers?.penalties || "Not assigned")}</strong></div></div>
        </section>
      </aside>
    </div>
  </div>`;
}

function renderPlanBoard(plan, team, ui, canEdit) {
  const starting = team?.startingXI?.length === 11 ? team.startingXI : team ? autoLineup(team, plan.formation) : [];
  const saved = plan.board?.length === 11 ? plan.board : starting;
  if (ui.planBoardPlanId !== plan.id) { ui.planBoardPlanId = plan.id; ui.planBoardDraft = [...saved]; }
  const board = ui.planBoardDraft?.length === 11 ? ui.planBoardDraft : saved;
  if (!team || team.players.length < 11 || board.length !== 11) {
    return `<section class="panel plan-board"><header><div><p class="eyebrow">Plan board</p><h2>Starting XI</h2></div></header><p class="plan-board__empty">Add at least 11 players in Team Hub to build a match plan board.</p></section>`;
  }
  const slots = FORMATIONS[plan.formation] ?? FORMATIONS["4-3-3"];
  const starters = new Set(board.filter(Boolean));
  const bench = team.players.filter((player) => !starters.has(player.id));
  return `<section class="panel plan-board" aria-label="Game plan starting eleven">
    <header class="plan-board__head"><div><p class="eyebrow">Matchday plan</p><h2>Starting XI · ${escapeHTML(plan.formation)}</h2><p>Drag to move a starter. Remove one to leave an open position, then choose a player from the squad list.</p></div>
      ${canEdit ? `<div class="page-head__actions"><button class="btn btn--ghost btn--sm" type="button" data-action="clear-plan-board" data-plan="${escapeHTML(plan.id)}">Reset XI</button><button class="btn btn--ghost btn--sm" type="button" data-action="auto-plan-board" data-plan="${escapeHTML(plan.id)}">${icon("reset", 14)} Auto-arrange</button><button class="btn btn--primary btn--sm" type="button" data-action="save-plan-board" data-plan="${escapeHTML(plan.id)}">${icon("check", 14)} Save board</button></div>` : ""}
    </header>
    <div class="plan-board__pitch"><span class="plan-board__halfway"></span><span class="plan-board__circle"></span>
      ${slots.map((slot, index) => { const player = team.players.find((item) => item.id === board[index]); const parts = player?.name.trim().split(/\s+/).filter(Boolean) ?? []; const initials = parts.length > 1 ? `${parts[0][0]}${parts[parts.length - 1][0]}`.toLocaleUpperCase() : (parts[0]?.[0]?.toLocaleUpperCase() ?? "+"); const cardPlacement = `${slot.y < 45 ? " plan-player-stats--below" : ""}${slot.x <= 25 ? " plan-player-stats--left" : slot.x >= 75 ? " plan-player-stats--right" : ""}`; const stats = player ? `<span class="plan-player-stats${cardPlacement}" role="tooltip"><span class="plan-player-card__top"><b>${escapeHTML(player.pos)}</b><strong>${Number(player.rating ?? 0).toFixed(1)}</strong></span><div class="plan-player-card__portrait">${avatar(player.name, { size: "xl", tone: playerTone(player.id), imageData: player.imageData })}</div><strong class="plan-player-card__name">${escapeHTML(player.name)}</strong><span class="plan-player-card__number">#${escapeHTML(player.number)} · ${escapeHTML(slot.role)}</span><div class="plan-player-card__rating"><i style="width:${Math.max(0,Math.min(100,Number(player.rating ?? 0)*10))}%"></i></div><div class="plan-player-card__stats"><b>${Number(player.goals ?? 0)}<small>Goals</small></b><b>${Number(player.assists ?? 0)}<small>Assists</small></b><b>${Number(player.apps ?? 0)}<small>Apps</small></b><b>${Number(player.starts ?? 0)}<small>Starts</small></b><b>${Number(player.minutes ?? 0)}<small>Minutes</small></b><b>${Number(player.cleanSheets ?? 0)}<small>Clean sheets</small></b></div><span class="plan-player-card__discipline">Yellow ${Number(player.yellowCards ?? 0)} · Red ${Number(player.redCards ?? 0)}</span></span>` : ""; return `<button class="plan-board__player${player ? "" : " is-empty"}" type="button" style="left:${slot.x}%;top:${slot.y}%" data-plan-board-slot="${index}" ${canEdit && player ? `draggable="true" data-plan-board-drag="${escapeHTML(player.id)}"` : ""} aria-label="${escapeHTML(slot.role)}: ${escapeHTML(player?.name ?? "Unfilled")}"><span>${escapeHTML(player?.number ?? "–")}</span><strong>${escapeHTML(initials)}</strong><small>${escapeHTML(slot.role)}</small>${stats}</button>`; }).join("")}
    </div>
    <aside class="plan-board__roster"><div><strong>Bench · ${bench.length}</strong><span>${ui.planBoardSelectedPlayer ? "Choose a position to add or swap this player" : "Select a bench player, then choose a position. Drag a starter here to clear their spot."}</span></div><div class="plan-board__roster-list${bench.length ? "" : " is-empty"}" data-plan-board-bench>${bench.length ? bench.map((player) => `<button class="plan-board__roster-player${ui.planBoardSelectedPlayer === player.id ? " is-selected" : ""}" type="button" data-plan-roster-player="${escapeHTML(player.id)}" ${canEdit ? `draggable="true" data-plan-board-drag="${escapeHTML(player.id)}"` : ""} aria-pressed="${ui.planBoardSelectedPlayer === player.id}"><b>#${escapeHTML(player.number)}</b><span>${escapeHTML(player.name)}<small>${escapeHTML(player.pos)} · ${Number(player.rating ?? 0).toFixed(1)} rating</small></span>${icon("arrowRight", 14)}</button>`).join("") : `<span class="plan-board__bench-empty">No players on the bench. Drag a starter here to open a position.</span>`}</div></aside>
  </section>`;
}

function renderPlanTab(plan, tab) {
  if (tab === "overview") {
    return `<div class="plan-overview">
      <div class="plan-objective-block">
        <span class="quote-mark">“</span>
        <div>
          <span class="eyebrow">The objective</span>
          <p>${escapeHTML(plan.objective)}</p>
        </div>
      </div>
      <div class="plan-story">
        <h3>The match story</h3>
        <p>${escapeHTML(plan.summary)}</p>
      </div>
      <div class="plan-overview-grid">
        <div class="shape-card">
          <div class="shape-card__head">
            <div><span class="eyebrow">Expected shape</span><h3>${escapeHTML(plan.formation)}</h3></div>
            <span class="shape-card__tag">Out of possession</span>
          </div>
          ${renderShapeBoard(plan.formation)}
        </div>
        <div class="non-negotiables">
          <span class="eyebrow">Three non-negotiables</span>
          <div class="principle">
            <span>01</span>
            <div><strong>Win the first line</strong><p>${escapeHTML(plan.inPossession.patterns[0]?.text ?? plan.inPossession.shape)}</p></div>
          </div>
          <div class="principle">
            <span>02</span>
            <div><strong>Press on the cue</strong><p>${escapeHTML(plan.outOfPossession.trigger)}</p></div>
          </div>
          <div class="principle">
            <span>03</span>
            <div><strong>Protect the middle</strong><p>${escapeHTML(plan.outOfPossession.restDefense)}</p></div>
          </div>
        </div>
      </div>
    </div>`;
  }

  if (tab === "in-possession") {
    return `<div class="plan-content">
      <div class="plan-callout plan-callout--lime">
        <span class="plan-callout__icon">${icon("layers", 20)}</span>
        <div><span class="eyebrow">Our shape</span><p>${escapeHTML(plan.inPossession.shape)}</p></div>
      </div>
      <h3 class="content-heading">Key patterns</h3>
      <div class="pattern-grid">
        ${plan.inPossession.patterns
          .map(
            (pattern, index) => `<article class="pattern-card">
              <span class="pattern-card__number">0${index + 1}</span>
              <h4>${escapeHTML(pattern.title)}</h4>
              <p>${escapeHTML(pattern.text)}</p>
            </article>`,
          )
          .join("")}
      </div>
      <h3 class="content-heading">Jobs in possession</h3>
      <div class="role-list">
        ${plan.inPossession.roles
          .map(
            (role) => `<div class="role-row">
              <span class="role-row__icon">${icon("target", 16)}</span>
              <strong>${escapeHTML(role.role)}</strong>
              <p>${escapeHTML(role.text)}</p>
            </div>`,
          )
          .join("")}
      </div>
    </div>`;
  }

  if (tab === "out-of-possession") {
    return `<div class="plan-content">
      <div class="defense-grid">
        <article class="defense-card defense-card--trigger">
          <span class="defense-card__icon">${icon("bolt", 20)}</span>
          <span class="eyebrow">Pressing trigger</span>
          <h3>When we jump</h3>
          <p>${escapeHTML(plan.outOfPossession.trigger)}</p>
        </article>
        <article class="defense-card defense-card--block">
          <span class="defense-card__icon">${icon("team", 20)}</span>
          <span class="eyebrow">Block shape</span>
          <h3>How we stay compact</h3>
          <p>${escapeHTML(plan.outOfPossession.block)}</p>
        </article>
        <article class="defense-card defense-card--rest">
          <span class="defense-card__icon">${icon("flag", 20)}</span>
          <span class="eyebrow">Rest defence</span>
          <h3>If it breaks down</h3>
          <p>${escapeHTML(plan.outOfPossession.restDefense)}</p>
        </article>
      </div>
      <div class="plan-callout plan-callout--dark">
        <span class="plan-callout__icon">${icon("sparkle", 20)}</span>
        <div><span class="eyebrow">Coach’s note</span><p>First reaction after losing the ball is always forward for five seconds. If we don’t win it back, we reset as a unit — no individual chases.</p></div>
      </div>
    </div>`;
  }

  const { attack, defend } = plan.setPieces;
  return `<div class="plan-content">
    <div class="set-piece-grid">
      <article class="set-piece-card">
        <div class="set-piece-card__head">
          <span class="set-piece-card__icon">${icon("arrowUpRight", 20)}</span>
          <div><span class="eyebrow">Attacking corner</span><h3>${escapeHTML(attack.title)}</h3></div>
          <span class="set-piece-card__badge">First phase</span>
        </div>
        <ol class="step-list">
          ${attack.steps.map((step) => `<li><span>${String(attack.steps.indexOf(step) + 1).padStart(2, "0")}</span><p>${escapeHTML(step)}</p></li>`).join("")}
        </ol>
      </article>
      <article class="set-piece-card">
        <div class="set-piece-card__head">
          <span class="set-piece-card__icon set-piece-card__icon--coral">${icon("team", 20)}</span>
          <div><span class="eyebrow">Defending dead balls</span><h3>${escapeHTML(defend.title)}</h3></div>
          <span class="set-piece-card__badge">Zonal + man</span>
        </div>
        <ol class="step-list">
          ${defend.steps.map((step) => `<li><span>${String(defend.steps.indexOf(step) + 1).padStart(2, "0")}</span><p>${escapeHTML(step)}</p></li>`).join("")}
        </ol>
      </article>
    </div>
    <div class="set-piece-note">
      <span>${icon("clipboard", 18)}</span>
      <div><strong>Rehearse it twice.</strong><p>Walk through both routines at Friday’s session, then again in the warm-up. Confidence comes from repetition.</p></div>
    </div>
  </div>`;
}

function renderShapeBoard(formation) {
  const slots = FORMATIONS[formation] ?? FORMATIONS["4-3-3"];
  return `<div class="shape-board">
    <div class="shape-pitch">
      <span class="shape-pitch__halfway"></span>
      <span class="shape-pitch__circle"></span>
      <span class="shape-pitch__box shape-pitch__box--top"></span>
      <span class="shape-pitch__box shape-pitch__box--bottom"></span>
      ${slots
        .map(
          (slot) => `<span class="shape-dot" style="left:${slot.x}%;top:${slot.y}%"><i></i><small>${slot.role}</small></span>`,
        )
        .join("")}
    </div>
    <div class="shape-board__legend">
      <span><i class="legend-dot legend-dot--lime"></i>On the ball</span>
      <span>${escapeHTML(formation)} base</span>
    </div>
  </div>`;
}

export function openNewPlanModal(state) {
  const fixture = state.nextFixtures[0];
  openModal({
    eyebrow: "New game plan",
    title: "Build the matchday plan",
    description: "Start with the opponent and the big idea. You can add details after.",
    body: `<form class="form" data-form="new-plan">
      <div class="form-row form-row--split">
        <label class="field">
          <span>Plan name</span>
          <input name="title" type="text" placeholder="e.g. Away at Riverside" required maxlength="60" autocomplete="off">
        </label>
        <label class="field">
          <span>Opponent</span>
          <input name="opponent" type="text" placeholder="e.g. Riverside United" required maxlength="50" autocomplete="off">
        </label>
      </div>
      <div class="form-row form-row--split">
        <label class="field">
          <span>Match date</span>
          <input name="date" type="date" value="${dateInput(fixture?.date || new Date())}" required>
        </label>
        <label class="field">
          <span>Formation</span>
          <select name="formation">
            ${Object.keys(FORMATIONS).map((formation) => `<option value="${formation}"${formation === "4-3-3" ? " selected" : ""}>${formation}</option>`).join("")}
          </select>
        </label>
      </div>
      <label class="field">
        <span>Venue</span>
        <input name="venue" type="text" value="${escapeHTML(fixture?.venue ?? "")}" maxlength="60" required>
      </label>
      <label class="field">
        <span>The objective</span>
        <textarea name="objective" rows="4" maxlength="260" placeholder="What has to be true for us to win this game?" required></textarea>
        <small>Keep it to one clear sentence the whole squad can remember.</small>
      </label>
      <div class="form-actions">
        <button class="btn btn--ghost" type="button" data-action="close-modal">Cancel</button>
        <button class="btn btn--primary" type="submit">${icon("clipboard", 16)} Create plan</button>
      </div>
    </form>`,
  });
}

export function openEditPlanModal(plan) {
  const lines = (items, firstKey, secondKey = "text") => (items ?? []).map((item) => `${item[firstKey]} | ${item[secondKey]}`).join("\n");
  const steps = (items) => (items ?? []).map((item) => typeof item === "string" ? item : item.text).join("\n");
  openModal({
    eyebrow: "Edit game plan",
    title: "Make this plan yours",
    description: "Edit match details and tactical notes. Use one item per line; patterns and roles use “Name | details”.",
    body: `<form class="form plan-edit-form" data-form="edit-plan" data-plan="${escapeHTML(plan.id)}">
      <div class="form-row form-row--split"><label class="field"><span>Plan name</span><input name="title" value="${escapeHTML(plan.title)}" required maxlength="60"></label><label class="field"><span>Opponent</span><input name="opponent" value="${escapeHTML(plan.opponent)}" required maxlength="50"></label></div>
      <div class="form-row form-row--split"><label class="field"><span>Match date and time</span><input name="date" type="datetime-local" value="${escapeHTML(dateTimeInput(plan.date))}" required></label><label class="field"><span>Formation</span><select name="formation">${Object.keys(FORMATIONS).map((formation) => `<option${formation === plan.formation ? " selected" : ""}>${formation}</option>`).join("")}</select></label></div>
      <label class="field"><span>Plan status</span><select name="status">${["Draft", "In review", "Ready", "Published"].map((status) => `<option${status === plan.status ? " selected" : ""}>${status}</option>`).join("")}</select></label>
      <div class="form-row form-row--split"><label class="field"><span>Venue</span><input name="venue" value="${escapeHTML(plan.venue)}" required maxlength="60"></label><label class="field"><span>Competition</span><input name="competition" value="${escapeHTML(plan.competition)}" required maxlength="80"></label></div>
      <label class="field"><span>Objective</span><textarea name="objective" required maxlength="260" rows="2">${escapeHTML(plan.objective)}</textarea></label>
      <label class="field"><span>Match story</span><textarea name="summary" maxlength="400" rows="3">${escapeHTML(plan.summary)}</textarea></label>
      <h3>In possession</h3>
      <label class="field"><span>Our shape</span><textarea name="in_possession_shape" required maxlength="160" rows="2">${escapeHTML(plan.inPossession.shape ?? "")}</textarea></label>
      <label class="field"><span>Patterns · one “Title | detail” per line</span><textarea name="patterns" rows="4">${escapeHTML(lines(plan.inPossession.patterns, "title"))}</textarea></label>
      <label class="field"><span>Player jobs · one “Role | detail” per line</span><textarea name="roles" rows="4">${escapeHTML(lines(plan.inPossession.roles, "role"))}</textarea></label>
      <h3>Out of possession</h3>
      <label class="field"><span>Pressing trigger</span><textarea name="out_trigger" maxlength="200" rows="2">${escapeHTML(plan.outOfPossession.trigger ?? "")}</textarea></label>
      <label class="field"><span>Defensive block</span><textarea name="out_block" maxlength="200" rows="2">${escapeHTML(plan.outOfPossession.block ?? "")}</textarea></label>
      <label class="field"><span>Rest defense</span><textarea name="out_rest_defense" maxlength="200" rows="2">${escapeHTML(plan.outOfPossession.restDefense ?? "")}</textarea></label>
      <h3>Set pieces</h3>
      <label class="field"><span>Attacking routine</span><input name="set_attack_title" value="${escapeHTML(plan.setPieces.attack.title ?? "")}" maxlength="100"></label>
      <label class="field"><span>Attack steps · one step per line</span><textarea name="attack_steps" rows="3">${escapeHTML(steps(plan.setPieces.attack.steps))}</textarea></label>
      <label class="field"><span>Defending routine</span><input name="set_defend_title" value="${escapeHTML(plan.setPieces.defend.title ?? "")}" maxlength="100"></label>
      <label class="field"><span>Defending steps · one step per line</span><textarea name="defend_steps" rows="3">${escapeHTML(steps(plan.setPieces.defend.steps))}</textarea></label>
      <div class="form-row form-row--split"><label class="field"><span>Corner taker</span><input name="corner_taker" value="${escapeHTML(plan.setPieces.takers?.corners ?? "")}" maxlength="80"></label><label class="field"><span>Free-kick taker</span><input name="free_kick_taker" value="${escapeHTML(plan.setPieces.takers?.freeKicks ?? "")}" maxlength="80"></label></div>
      <label class="field"><span>Penalty taker</span><input name="penalty_taker" value="${escapeHTML(plan.setPieces.takers?.penalties ?? "")}" maxlength="80"></label>
      <h3>Checklist</h3><label class="field"><span>Matchday tasks · one item per line</span><textarea name="checklist" rows="4">${escapeHTML((plan.checklist ?? []).map((item) => item.text).join("\n"))}</textarea></label>
      <div class="form-actions"><button class="btn btn--ghost" type="button" data-action="close-modal">Cancel</button><button class="btn btn--primary" type="submit">Save game plan</button></div>
    </form>`,
  });
}

function dateInput(value) {
  const date = new Date(value);
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function dateTimeInput(value) {
  const date = new Date(value);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function statusSlug(status) {
  const slug = String(status).toLowerCase().replaceAll(" ", "-");
  return ["ready", "in-review", "published", "in-progress", "draft", "complete"].includes(slug) ? slug : "draft";
}

function tabTitle(tab) {
  return {
    overview: "The game in one page",
    "in-possession": "How we break them down",
    "out-of-possession": "How we win it back",
    "set-pieces": "The details that decide games",
  }[tab];
}

function tabEyebrow(tab) {
  return {
    overview: "Plan overview",
    "in-possession": "On the ball",
    "out-of-possession": "Off the ball",
    "set-pieces": "Dead-ball moments",
  }[tab];
}
