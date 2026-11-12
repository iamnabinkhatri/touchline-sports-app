import { icon } from "../icons.js";
import { pollPercent, pollTotal } from "../store.js";
import { avatar, countLabel, emptyState, openModal, voteIcon } from "../ui.js";
import { closingLabel, escapeHTML, formatDate, formatTime, isOpen, plural, safeToken } from "../utils.js";
import { pickupTeamNames, pickupTeamTone } from "../pickup-team-names.js";

const CATEGORIES = ["All", "Pickup", "Competition", "Lineup", "Tactics", "Club"];

export function renderPolls(state, ui) {
  const active = state.polls.filter((poll) => isOpen(poll.closesAt));
  const closed = state.polls.filter((poll) => !isOpen(poll.closesAt));
  const current = ui.pollTab === "closed" ? closed : active;
  const filtered = current.filter(
    (poll) => ui.pollFilter === "All" || poll.category === ui.pollFilter,
  );
  const visiblePolls = ui.pollsShowMore ? filtered : filtered.slice(0, 4);
  const hiddenPollCount = Math.max(0, filtered.length - visiblePolls.length);
  const totalVotes = active.reduce((total, poll) => total + pollTotal(poll), 0);
  const avgTurnout = active.length
    ? Math.round(totalVotes / (active.length * 128) * 100)
    : 0;

  return `<div class="page page--polls">
    <header class="page-head reveal">
      <div class="page-head__copy">
        <p class="eyebrow"><span class="eyebrow__line"></span>Soccer polls</p>
        <h1>The squad has a say.</h1>
        <p class="page-subtitle">Quick calls, big debates. Every vote helps the coach and the club make a better decision.</p>
      </div>
      <div class="page-head__actions">
        <button class="btn btn--primary" type="button" data-action="new-poll">${icon("plus", 17)} New poll</button>
      </div>
    </header>

    <section class="poll-summary reveal reveal--delay-1" aria-label="Poll activity">
      <div class="poll-summary__main">
        <span class="poll-summary__icon">${icon("poll", 24)}</span>
        <div>
          <span class="eyebrow">This week</span>
          <h2>${plural(active.length, "open poll")}, ${plural(totalVotes, "vote")} cast.</h2>
        </div>
      </div>
      <div class="poll-summary__stats">
        <div><strong>${avgTurnout}%</strong><span>avg. turnout per poll</span></div>
        <div class="poll-summary__avatars">
          ${state.leaders
            .map((leader) => avatar(leader.name, { size: "sm", tone: leader.tone }))
            .join("")}
          <span class="poll-summary__more">+125</span>
        </div>
      </div>
      <div class="poll-summary__note">${icon("sparkle", 15)} Polls close 24 hours before kick-off unless the coach says otherwise.</div>
    </section>

    <div class="poll-toolbar reveal reveal--delay-2">
      <div class="segmented" role="tablist" aria-label="Poll status">
        <button class="segmented__item${ui.pollTab === "active" ? " is-active" : ""}" type="button" role="tab" aria-selected="${ui.pollTab === "active"}" data-action="poll-tab" data-tab="active">Open <span>${active.length}</span></button>
        <button class="segmented__item${ui.pollTab === "closed" ? " is-active" : ""}" type="button" role="tab" aria-selected="${ui.pollTab === "closed"}" data-action="poll-tab" data-tab="closed">Closed <span>${closed.length}</span></button>
      </div>
      <div class="filter-row" role="group" aria-label="Filter polls by category">
        ${CATEGORIES.map(
          (category) => `<button class="filter-chip filter-chip--small${ui.pollFilter === category ? " is-active" : ""}" type="button" data-action="filter-polls" data-filter="${escapeHTML(category)}">${escapeHTML(category)}</button>`,
        ).join("")}
      </div>
    </div>

    <div class="poll-grid reveal reveal--delay-3">
      ${
        visiblePolls.length
          ? visiblePolls
              .map((poll, index) => renderPollCard(poll, index === 0 && ui.pollFilter === "All" && ui.pollTab === "active", state, ui))
              .join("")
          : emptyState({
              iconName: "poll",
              title: ui.pollTab === "closed" ? "No closed polls here" : "No open polls in this lane",
              text:
                ui.pollTab === "closed"
                  ? "Once a poll closes, its final results will show up here."
                  : "Try another category, or start a new poll for the squad.",
              action: `<button class="btn btn--primary btn--sm" type="button" data-action="new-poll">${icon("plus", 15)} New poll</button>`,
            })
      }
    </div>
    ${filtered.length > 4 ? `<div class="poll-show-more"><button class="btn btn--light" type="button" data-action="toggle-polls-show-more">${ui.pollsShowMore ? "Show fewer polls" : `Show more polls (${filtered.length - 4})`}</button></div>` : ""}

    <section class="poll-how reveal">
      <div class="poll-how__lead">
        <span class="eyebrow">How it works</span>
        <h2>One question. One vote. No group-chat chaos.</h2>
      </div>
      <div class="poll-how__steps">
        <div><span>01</span><strong>Ask the group</strong><p>Coaches and members can start a poll in seconds.</p></div>
        <div><span>02</span><strong>Vote once</strong><p>Every member gets one say. You can change it until it closes.</p></div>
        <div><span>03</span><strong>Make the call</strong><p>Results land with the coaching staff before matchday.</p></div>
      </div>
    </section>
  </div>`;
}

function renderPollCard(poll, featured = false, state = {}, ui = {}) {
  const total = pollTotal(poll);
  const closed = !isOpen(poll.closesAt);
  const leader = [...poll.options].sort((a, b) => b.votes - a.votes)[0];
  const category = safeToken(poll.category.toLowerCase(), ["pickup", "competition", "lineup", "tactics", "club"], "club");
  const expanded = ui.expandedPollOptions?.includes(poll.id);
  const cardExpanded = ui.expandedPollCards?.includes(poll.id) ?? false;
  const visibleOptions = expanded ? poll.options : poll.options.slice(0, 2);
  const roster = state.teams?.find((team) => team.communityId === poll.communityId)?.players ?? [];
  const playerById = new Map([...roster, ...(poll.yesPlayers ?? [])].map((player) => [player.id, player]));
  const eligibleRoster = poll.category === "Pickup" ? (poll.yesPlayers ?? []) : roster.filter((player) => player.status !== "out");
  const teamResult = poll.autoTeams?.teamA ? poll.autoTeams : null;
  const [teamAName, teamBName] = teamResult?.teamNames ? [teamResult.teamNames.teamA, teamResult.teamNames.teamB] : pickupTeamNames(poll.id);
  const renderTeam = (label, teamName, playerIds) => `<div class="pickup-poll-team pickup-poll-team--${pickupTeamTone(teamName)}"><strong>${escapeHTML(label)}</strong>${playerIds.map((id) => { const player = playerById.get(id); return player ? `<span>${player.guest ? "Guest" : `#${player.number}`} ${escapeHTML(player.name)} <small>${escapeHTML(player.pos)} · ${Number(player.rating).toFixed(1)}</small></span>` : ""; }).join("") || `<small>No players</small>`}</div>`;
  return `<article class="poll-card${featured ? " poll-card--featured" : ""}${closed ? " poll-card--closed" : ""}${cardExpanded ? " is-expanded" : " is-collapsed"}">
    <button class="poll-card__title-toggle" type="button" data-action="toggle-poll-card" data-poll="${escapeHTML(poll.id)}" aria-expanded="${cardExpanded}">
      <span>${escapeHTML(poll.question)}</span><span class="poll-card__title-chevron${cardExpanded ? " is-up" : ""}" aria-hidden="true">${icon("chevronDown", 20)}</span>
    </button>
    <div class="poll-card__top">
      <div class="poll-card__tags">
        <span class="tag tag--${category}">${icon(
          category === "pickup" ? "shuffle" : category === "competition" ? "trophy" : category === "lineup" ? "team" : category === "tactics" ? "layers" : "users",
          12,
        )}${escapeHTML(poll.category)}</span>
        ${featured && poll.featured ? `<span class="tag tag--spotlight">${icon("sparkle", 12)} Poll of the week</span>` : ""}
        ${poll.userVote ? `<span class="tag tag--voted">${icon("check", 12)} You voted</span>` : ""}
      </div>
      <span class="poll-card__time">${icon("clock", 13)} ${escapeHTML(closed ? "Closed" : closingLabel(poll.closesAt))} · ${escapeHTML(new Date(poll.closesAt).toLocaleString())}</span>
    </div>

    <h2>${escapeHTML(poll.question)}</h2>
    <div class="poll-card__meta">
      ${avatar(poll.author, { size: "xs", tone: "forest" })}
      <span>Asked by <strong>${escapeHTML(poll.author)}</strong></span>
      <span class="dot-sep"></span>
      <span>${countLabel(total)} ${total === 1 ? "vote" : "votes"}</span>
    </div>
    ${featured ? `<p class="poll-card__context">The gaffer makes the final call after Friday’s session, but every vote is read. Have your say before the team sheet goes in.</p>` : ""}

    <div class="poll-options">
      ${visibleOptions
        .map((option) => {
          const percent = pollPercent(option, poll);
          const selected = poll.userVote === option.id;
          const isLeader = leader?.id === option.id && total > 0;
          return `<button class="poll-option${selected ? " is-selected" : ""}${isLeader ? " is-leading" : ""}" type="button" data-action="vote-poll" data-poll="${escapeHTML(poll.id)}" data-option="${escapeHTML(option.id)}" ${closed ? "disabled" : ""} aria-label="Vote for ${escapeHTML(option.label)}, ${percent} percent">
            <span class="poll-option__top">
              <span class="poll-option__label">${voteIcon(selected)}${escapeHTML(option.label)}</span>
              <span class="poll-option__result">${percent}<small>%</small></span>
            </span>
            <span class="poll-option__track"><span style="width:${percent}%"></span></span>
          </button>`;
        })
        .join("")}
      ${poll.options.length > 2 ? `<button class="poll-options-more" type="button" data-action="toggle-poll-options" data-poll="${escapeHTML(poll.id)}">${expanded ? "Show fewer options" : `More options · ${poll.options.length - 2}`}</button>` : ""}
    </div>

    ${poll.gameAt ? `<p class="poll-game-time">${icon("calendar", 13)} ${poll.category === "Pickup" ? "Pickup starts" : "Game day"} · ${escapeHTML(formatDate(poll.gameAt))} at ${escapeHTML(formatTime(poll.gameAt))}${poll.category === "Pickup" && poll.location ? ` · ${escapeHTML(poll.location)}` : ""}</p>` : ""}
    ${poll.category === "Pickup" ? `<section class="poll-attendance"><strong>${poll.yesPlayers?.length ?? 0} attending</strong>${poll.yesPlayers?.length ? `<div>${poll.yesPlayers.map((player) => `<span>${player.guest ? "Guest" : `#${player.number}`} ${escapeHTML(player.name)} · ${escapeHTML(player.position)}</span>`).join("")}</div>` : ""}<small>${poll.yesPlayers?.length ? "Yes players and their guests are used in the pickup split." : "No players have confirmed yet."}${poll.guestCount ? ` Includes ${poll.guestCount} guest${poll.guestCount === 1 ? "" : "s"}.` : ""}${poll.noCount ? ` ${poll.noCount} voted No.` : ""}</small></section>` : ""}
    ${closed && teamResult ? `<section class="pickup-poll-result"><div class="pickup-poll-result__head"><strong>Balanced teams</strong><span>${teamResult.manual ? "Manually adjusted" : "Auto balanced"} · strength gap ${Number(teamResult.gap || 0).toFixed(1)}</span></div><div class="pickup-poll-result__teams">${renderTeam(teamAName.toUpperCase(), teamAName, teamResult.teamA)}${renderTeam(teamBName.toUpperCase(), teamBName, teamResult.teamB)}</div>${teamResult.floater && playerById.has(teamResult.floater) ? `<p class="pickup-poll-floater">Floater · ${escapeHTML(playerById.get(teamResult.floater).name)}</p>` : ""}${poll.canManageTeams ? `<button class="btn btn--light btn--sm" type="button" data-action="edit-pickup-poll-teams" data-poll="${escapeHTML(poll.id)}">Manually rearrange players</button>` : ""}</section>` : ""}

    <div class="poll-card__foot">
      <span class="poll-card__status">${
        closed
          ? `${icon("trophy", 14)} ${escapeHTML(leader?.label ?? "")} won with ${pollPercent(leader, poll)}%`
          : poll.userVote
            ? `${icon("check", 14)} Your vote is in — tap another option to change it`
            : `${icon("sparkle", 14)} Tap an option to cast your vote`
      }</span>
      ${!closed ? `<span class="poll-card__turnout"><span class="pulse-dot"></span>${Math.round((total / 128) * 100)}% turnout</span>` : ""}
      ${closed && poll.feedbackDueAt && new Date(poll.feedbackDueAt) <= new Date() && poll.userVote ? `<button type="button" class="text-link" data-action="rate-poll-players" data-poll="${escapeHTML(poll.id)}">Rate players</button>` : ""}
      ${closed && poll.feedbackCount && poll.canManageTeams ? `<button type="button" class="text-link" data-action="view-poll-feedback" data-poll="${escapeHTML(poll.id)}">Feedback · ${poll.feedbackCount}</button>` : ""}
    </div>
  </article>`;
}

export function openNewPollModal(communityId = null, communities = []) {
  openModal({
    eyebrow: "New poll",
    title: "Ask the squad",
    description: "Keep it clear, keep it useful. You can add up to four options.",
    body: `<form class="form" data-form="new-poll" data-community="${escapeHTML(communityId ?? "")}">
      ${communityId ? `<input type="hidden" name="community_id" value="${escapeHTML(communityId)}"><p class="form-note">This poll will only be visible in this community.</p>` : ""}
      ${!communityId && communities.length ? `<label class="field poll-community-field"><span>Community</span><select name="community_id" required><option value="">Choose a community</option>${communities.map((community) => `<option value="${escapeHTML(community.id)}">${escapeHTML(community.name)}</option>`).join("")}</select></label>` : ""}
      <label class="field">
        <span>Your question</span>
        <input name="question" type="text" placeholder="e.g. Who starts at left-back on Saturday?" required maxlength="120" autocomplete="off">
      </label>
      <div class="form-row form-row--split">
        <label class="field">
          <span>Poll type</span>
          <select name="category">
            <option value="Pickup" selected>Pickup</option>
            <option value="Competition">Competition</option>
            <option value="Lineup">Lineup</option>
            <option value="Tactics">Tactics</option>
            <option value="Club">Club</option>
          </select>
        </label>
        <label class="field"><span>Poll closes at</span><input name="closesAt" type="datetime-local" required></label>
      </div>
      <div class="form-row form-row--split poll-pickup-date-field"><label class="field"><span>Pickup game date</span><input name="gameDate" type="date" required></label><label class="field"><span>Pickup start time</span><input name="gameTime" type="time" required><small>Ratings email: 10 AM for 5–8 AM kick-offs; 10 PM otherwise, in the configured timezone.</small></label></div>
      <label class="field poll-pickup-location"><span>Pickup location</span><input name="location" type="text" maxlength="160" placeholder="e.g. Riverside Park, Field 2"><small>Add where the game is happening so everyone knows where to meet.</small></label>
      <label class="field poll-game-field" hidden><span>Competition game date and kick-off time</span><input name="gameAt" type="datetime-local"><small>Voters receive post-game rating email at 10 AM for 5–8 AM games; otherwise at 10 PM in the configured app timezone.</small></label>
      <fieldset class="field option-fieldset poll-custom-options" hidden>
        <legend>Options</legend>
        <label class="option-input"><span>1</span><input name="option1" type="text" placeholder="First option" required disabled maxlength="60" autocomplete="off"></label>
        <label class="option-input"><span>2</span><input name="option2" type="text" placeholder="Second option" required disabled maxlength="60" autocomplete="off"></label>
        <label class="option-input"><span>3</span><input name="option3" type="text" placeholder="Add another (optional)" disabled maxlength="60" autocomplete="off"></label>
        <label class="option-input"><span>4</span><input name="option4" type="text" placeholder="Add another (optional)" disabled maxlength="60" autocomplete="off"></label>
      </fieldset>
      <div class="form-note">${icon("globe", 14)} Visible to your community members. One vote per member.</div>
      <div class="form-actions">
        <button class="btn btn--ghost" type="button" data-action="close-modal">Cancel</button>
        <button class="btn btn--primary" type="submit">${icon("poll", 16)} Publish poll</button>
      </div>
    </form>`,
  });
}
