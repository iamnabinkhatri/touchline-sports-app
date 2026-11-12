import { icon } from "../icons.js";
import {
  CLAIMS_PER_DAY,
  calendarEntries,
  claimState,
  entriesByDay,
  kindMeta,
  localDayKey,
  monthGrid,
  monthKey,
  openDuties,
  DUTY_KINDS,
} from "../calendar-model.js";
import { avatar, emptyState, openModal } from "../ui.js";
import { escapeHTML } from "../utils.js";

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function clock(value) {
  return new Date(value).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}

function longDay(key) {
  return new Date(`${key}T12:00:00`).toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

function monthTitle(key) {
  const [year, month] = key.split("-").map(Number);
  return new Date(year, month - 1, 1).toLocaleDateString("en-US", { month: "long", year: "numeric" });
}

function chipKind(entry) {
  if (entry.source !== "duty") return entry.source;
  return entry.duty.claimedBy ? "duty" : "open";
}

function renderCell(cell, items, todayKey, selectedKey) {
  const shown = items.slice(0, 3);
  const extra = items.length - shown.length;
  const classes = ["cal-day"];
  if (!cell.inMonth) classes.push("is-out");
  if (cell.key === todayKey) classes.push("is-today");
  if (cell.key === selectedKey) classes.push("is-selected");
  const summary = items.length ? `, ${items.length} ${items.length === 1 ? "item" : "items"}` : "";
  return `<button class="${classes.join(" ")}" type="button" data-action="calendar-day" data-date="${cell.key}" aria-pressed="${cell.key === selectedKey}" aria-label="${escapeHTML(longDay(cell.key))}${summary}">
    <span class="cal-day__num">${cell.day}</span>
    <span class="cal-day__chips">
      ${shown
        .map((entry) => `<span class="cal-chip cal-chip--${chipKind(entry)}"><i aria-hidden="true"></i>${escapeHTML(entry.source === "duty" ? entry.duty.kindLabel : entry.source === "match" ? entry.title : entry.eventType ?? entry.title)}</span>`)
        .join("")}
      ${extra > 0 ? `<span class="cal-more">+${extra} more</span>` : ""}
    </span>
  </button>`;
}

function claimControl(duty, userId, duties, now) {
  if (duty.assignedTo) return duty.assignedTo.id === userId
    ? `<span class="cal-open-badge">Assigned to you</span>`
    : `<span class="cal-note">Assigned to ${escapeHTML(duty.assignedTo.name)}</span>`;
  const state = claimState(duty, userId, duties, now);
  if (state === "open") {
    return `<button class="btn btn--primary btn--sm" type="button" data-action="claim-duty" data-duty="${escapeHTML(duty.id)}">${icon("check", 14)} I’ll bring it</button>`;
  }
  if (state === "mine") {
    return `<button class="btn btn--ghost btn--sm" type="button" data-action="release-duty" data-duty="${escapeHTML(duty.id)}">Give it back</button>`;
  }
  if (state === "limit") {
    return `<span class="cal-note">You already have ${CLAIMS_PER_DAY} duties that day</span>`;
  }
  if (state === "passed") return `<span class="cal-note">Already happened</span>`;
  return "";
}

function renderDutyItem(entry, state, duties, now) {
  const duty = entry.duty;
  const userId = state.user.id;
  const meta = kindMeta(duty.kind);
  const canDelete = duty.createdById === userId || Boolean(state.user.canManageTeam);
  const claimer = duty.assignedTo
    ? `${avatar(duty.assignedTo.name, { size: "xs", tone: duty.assignedTo.tone })}<span>Assigned to ${escapeHTML(duty.assignedTo.name)}</span>`
    : duty.claimedBy
    ? `${avatar(duty.claimedBy.name, { size: "xs", tone: duty.claimedBy.tone })}<span>${escapeHTML(duty.claimedBy.name)}</span>`
    : `<span class="cal-open-badge">Needs cover</span>`;
  return `<li class="cal-item cal-item--duty${duty.claimedBy ? "" : " is-open"}">
    <span class="cal-item__icon" aria-hidden="true">${icon(meta.icon, 16)}</span>
    <div class="cal-item__body">
      <div class="cal-item__top"><time>${escapeHTML(clock(entry.date))}</time><span class="cal-kind">${escapeHTML(duty.kindLabel)}</span></div>
      ${entry.communityName ? `<span class="cal-kind">${escapeHTML(entry.communityName)}</span>` : ""}
      <strong>${escapeHTML(duty.title)}</strong>
      ${duty.note ? `<p class="cal-item__note">${escapeHTML(duty.note)}</p>` : ""}
      <div class="cal-item__who">${claimer}</div>
    </div>
    <div class="cal-item__actions">
      ${claimControl(duty, userId, duties, now)}
      ${canDelete ? `<button class="icon-button cal-delete" type="button" data-action="delete-duty" data-duty="${escapeHTML(duty.id)}" data-title="${escapeHTML(duty.title)}" aria-label="Delete ${escapeHTML(duty.title)}">${icon("close", 15)}</button>` : ""}
    </div>
  </li>`;
}

function renderPlainItem(entry) {
  const label = entry.source === "match" ? "Match" : entry.eventType ?? "Club";
  return `<li class="cal-item cal-item--${entry.source}">
    <span class="cal-item__icon" aria-hidden="true">${icon(entry.source === "match" ? "whistle" : "calendar", 16)}</span>
    <div class="cal-item__body">
      <div class="cal-item__top"><time>${escapeHTML(clock(entry.date))}</time><span class="cal-kind">${escapeHTML(label)}</span></div>
      <strong>${escapeHTML(entry.title)}</strong>
      <p class="cal-item__note">${escapeHTML(entry.detail)}</p>
    </div>
  </li>`;
}

function renderDayPanel(state, selectedKey, items, duties, now, hasTeam) {
  const canAdd = hasTeam ? `<button class="btn btn--ghost btn--sm" type="button" data-action="new-duty" data-date="${selectedKey}">${icon("plus", 14)} Add a duty this day</button>` : "";
  return `<header class="cal-panel__head">
      <div><p class="eyebrow">${escapeHTML(new Date(`${selectedKey}T12:00:00`).toLocaleDateString("en-US", { weekday: "long" }))}</p>
      <h2>${escapeHTML(longDay(selectedKey))}</h2></div>
      ${canAdd}
    </header>
    ${
      items.length
        ? `<ul class="cal-list">${items
            .map((entry) => (entry.source === "duty" ? renderDutyItem(entry, state, duties, now) : renderPlainItem(entry)))
            .join("")}</ul>`
        : emptyState({
            iconName: "calendar",
            title: "Nothing on this day",
            text: "Pick another day, or add a duty for this one.",
          })
    }`;
}

export function renderCalendar(state, ui) {
  const now = Date.now();
  const todayKey = localDayKey(new Date());
  ui.calendarMonth ??= monthKey(new Date());
  ui.calendarDay ??= todayKey;
  const duties = state.duties ?? [];
  const entries = calendarEntries(state);
  const byDay = entriesByDay(entries);
  const grid = monthGrid(ui.calendarMonth);
  const selectedKey = ui.calendarDay;
  const monthEntries = entries.filter((entry) => localDayKey(entry.date).startsWith(ui.calendarMonth));
  const monthDuties = monthEntries.filter((entry) => entry.source === "duty");
  const needsCover = openDuties(duties, state.user.id, now);
  const matches = monthEntries.filter((entry) => entry.source === "match").length;
  const dayItems = byDay.get(selectedKey) ?? [];
  const availableCommunities = state.communities.filter((community) => community.joined || state.user.role === "Super Admin");
  const selectedCommunity = availableCommunities.find((community) => community.id === ui.calendarCommunityId);
  const hasTeam = state.teams.some((team) => team.communityId === ui.calendarCommunityId);
  if (!availableCommunities.length) return `<div class="page page--calendar"><header class="page-head"><div><p class="eyebrow">Community calendar</p><h1>Create a community first.</h1><p class="page-head__lede">Calendars belong to communities. Create one or join a community to see its events.</p></div><div class="page-head__actions"><button class="btn btn--primary" type="button" data-action="go-communities">${icon("users", 17)} View communities</button></div></header></div>`;

  return `<div class="page page--calendar">
    <header class="page-head reveal">
      <div>
        <p class="eyebrow">Squad calendar</p>
        <h1>Matchday &amp; duties</h1>
        <p class="page-head__lede">Who is bringing coffee, donuts or drinks, and what is on the calendar. Everyone in the club can see it.</p>
      </div>
      <div class="page-head__actions">
        <label class="field calendar-community-select"><span>Community calendar</span><select id="calendar-community">${availableCommunities.map((community) => `<option value="${escapeHTML(community.id)}"${community.id === ui.calendarCommunityId ? " selected" : ""}>${escapeHTML(community.name)}</option>`).join("")}</select>${icon("chevronDown", 15)}</label>
        ${selectedCommunity?.canManage || state.user.role === "Super Admin" ? `<button class="btn btn--ghost" type="button" data-action="new-calendar-event">${icon("plus", 16)} Add event</button>` : ""}
        ${hasTeam ? `<button class="btn btn--primary" type="button" data-action="new-duty" data-date="${selectedKey}">${icon("plus", 17)} Add a duty</button>` : ""}
      </div>
    </header>

    <div class="cal-summary reveal reveal--delay-1" aria-label="This month at a glance">
      <div><strong>${matches}</strong><span>${matches === 1 ? "match" : "matches"}</span></div>
      <div><strong>${monthDuties.filter((entry) => entry.duty.claimedBy || entry.duty.assignedTo).length}</strong><span>${monthDuties.filter((entry) => entry.duty.claimedBy || entry.duty.assignedTo).length === 1 ? "duty covered" : "duties covered"}</span></div>
      <div class="is-alert"><strong>${monthDuties.filter((entry) => !entry.duty.claimedBy && !entry.duty.assignedTo).length}</strong><span>still need${monthDuties.filter((entry) => !entry.duty.claimedBy && !entry.duty.assignedTo).length === 1 ? "s" : ""} cover</span></div>
    </div>

    <div class="cal-layout">
      <section class="cal-card reveal reveal--delay-2" aria-label="Calendar">
        <div class="cal-head">
          <button class="icon-button" type="button" data-action="calendar-prev" aria-label="Previous month">${icon("chevronLeft", 17)}</button>
          <h2 aria-live="polite">${escapeHTML(monthTitle(ui.calendarMonth))}</h2>
          <div class="cal-head__right">
            <button class="btn btn--ghost btn--sm" type="button" data-action="calendar-today">Today</button>
            <button class="icon-button" type="button" data-action="calendar-next" aria-label="Next month">${icon("chevronRight", 17)}</button>
          </div>
        </div>
        <div class="cal-legend" aria-hidden="true">
          <span><i class="cal-chip--match"></i>Match</span>
          <span><i class="cal-chip--event"></i>Training &amp; events</span>
          <span><i class="cal-chip--duty"></i>Covered</span>
          <span><i class="cal-chip--open"></i>Needs cover</span>
        </div>
        <div class="cal-weekdays" aria-hidden="true">${WEEKDAYS.map((day) => `<span>${day}</span>`).join("")}</div>
        <div class="cal-grid">
          ${grid.map((cell) => renderCell(cell, byDay.get(cell.key) ?? [], todayKey, selectedKey)).join("")}
        </div>
      </section>

      <aside class="cal-panel reveal reveal--delay-3" aria-live="polite">
        ${renderDayPanel(state, selectedKey, dayItems, duties, now, hasTeam)}
      </aside>
    </div>

    <section class="cal-open reveal reveal--delay-3" aria-labelledby="cal-open-title">
      <header class="cal-open__head">
        <div><p class="eyebrow">Help wanted</p><h2 id="cal-open-title">Still needs cover</h2></div>
        <span class="cal-count">${needsCover.length} open</span>
      </header>
      ${
        needsCover.length
          ? `<ul class="cal-open__list">${needsCover
              .slice(0, 6)
              .map(
                (duty) => `<li>
                  <span class="cal-item__icon" aria-hidden="true">${icon(kindMeta(duty.kind).icon, 16)}</span>
                  <div><strong>${escapeHTML(duty.title)}</strong><small>${escapeHTML(new Date(duty.startsAt).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" }))} · ${escapeHTML(clock(duty.startsAt))}</small></div>
                  ${claimControl(duty, state.user.id, duties, now)}
                </li>`,
              )
              .join("")}</ul>`
          : `<p class="cal-open__empty">Every upcoming duty is covered. Nice work, squad.</p>`
      }
    </section>
  </div>`;
}

export function newDutyFormHTML(state, dateKey = null) {
  const communityId = state.dutyCommunityId;
  const matches = (state.polls ?? []).filter((poll) => poll.communityId === communityId
    && ["Pickup", "Competition"].includes(poll.category) && poll.gameAt
    && new Date(poll.gameAt) > new Date() && Number(poll.voteCount) > 0);
  const date = dateKey || localDayKey(new Date());
  const members = state.dutyMembers ?? [];
  const canAssignOthers = Boolean(state.dutyCanAssignOthers);
  const match = matches.find((poll) => localDayKey(poll.gameAt) === date) ?? null;
  const time = match ? new Date(match.gameAt).toTimeString().slice(0, 5) : "09:00";
  return `<form class="form" data-form="new-duty" data-community="${escapeHTML(communityId ?? "")}">
      <fieldset class="duty-entry" data-duty-entry><legend>Matchday duty</legend>
      <div class="duty-items-heading"><div><span class="eyebrow">What to bring</span><p>Choose one or more items for this duty.</p></div></div>
      <div class="duty-kind-list" data-duty-items><section class="duty-kind-entry"><div class="duty-kind-entry__head"><strong data-duty-item-title>Item 1</strong></div><input type="hidden" data-duty-kind aria-label="Duty item" value="coffee"><div class="duty-kind-options" role="group" aria-label="Choose an item">${DUTY_KINDS.map((kind) => `<button class="duty-kind-choice${kind.id === "coffee" ? " is-selected" : ""}" type="button" data-action="select-duty-kind" data-kind="${kind.id}" aria-pressed="${kind.id === "coffee"}">${icon(kind.icon, 16)}<span>${escapeHTML(kind.label)}</span></button>`).join("")}</div></section></div>
      <button class="btn btn--ghost btn--sm" type="button" data-action="add-duty-item">${icon("plus", 14)} Add another item</button>
      <label class="field"><span>For</span><select data-duty-field="event_key"><option value="">General, no specific match</option>${matches.map((poll) => `<option value="${escapeHTML(poll.id)}" data-start-at="${escapeHTML(poll.gameAt)}"${match?.id === poll.id ? " selected" : ""}>${escapeHTML(`${poll.question} · ${new Date(poll.gameAt).toLocaleString()} · ${poll.voteCount} vote${poll.voteCount === 1 ? "" : "s"}`)}</option>`).join("")}</select></label>
      ${members.length ? `<label class="field"><span>Assign to member</span><select data-duty-field="assigned_to"><option value="">Open for a volunteer</option>${members.map((member) => `<option value="${escapeHTML(member.id)}" ${!canAssignOthers && member.id !== state.user.id ? "disabled" : ""}>${escapeHTML(member.name)}${member.id === state.user.id ? " (you)" : ""}</option>`).join("")}</select></label>` : ""}
      <label class="field"><span>Title (optional)</span><input data-duty-field="title" maxlength="80" placeholder="e.g. Matchday refreshments"></label>
      <div class="form-row form-row--split"><label class="field"><span>Date</span><input data-duty-field="date" type="date" value="${escapeHTML(match ? localDayKey(match.gameAt) : date)}" required></label><label class="field"><span>Time</span><input data-duty-field="time" type="time" value="${escapeHTML(time)}" required></label></div>
      <label class="field"><span>Note (optional)</span><textarea data-duty-field="note" maxlength="200" rows="2" placeholder="Oat milk, a dozen, something nut-free"></textarea></label>
      </fieldset>
      <div class="form-note">${icon("sparkle", 14)} Each person can take at most ${CLAIMS_PER_DAY} duties on the same day.</div>
      <div class="form-actions">
        <button class="btn btn--ghost" type="button" data-action="close-modal">Cancel</button>
        <button class="btn btn--primary" type="submit">${icon("plus", 16)} Add to calendar</button>
      </div>
    </form>`;
}

export function openNewDutyModal(state, dateKey = null) {
  openModal({
    eyebrow: "Matchday duties",
    title: "Add a duty",
    description: "Create one matchday duty with as many items as needed. Assign it to a member or leave it open for a volunteer.",
    body: newDutyFormHTML(state, dateKey),
  });
}

export function openNewCalendarEventModal(communityId, dateKey = null) {
  const date = dateKey || localDayKey(new Date());
  openModal({
    eyebrow: "Community calendar",
    title: "Add an event",
    description: "This event is visible to members of this community only.",
    body: `<form class="form" data-form="new-calendar-event"><input type="hidden" name="communityId" value="${escapeHTML(communityId)}"><label class="field"><span>Event title</span><input name="title" required minlength="2" maxlength="100"></label><div class="form-row form-row--split"><label class="field"><span>Type</span><select name="type"><option>Training</option><option>Match</option><option>Meeting</option><option>Social</option><option>Other</option></select></label><label class="field"><span>Date</span><input name="date" type="date" value="${escapeHTML(date)}" required></label></div><label class="field"><span>Details</span><textarea name="detail" maxlength="240" rows="2"></textarea></label><div class="form-actions"><button class="btn btn--ghost" type="button" data-action="close-modal">Cancel</button><button class="btn btn--primary" type="submit">Add event</button></div></form>`,
  });
}
