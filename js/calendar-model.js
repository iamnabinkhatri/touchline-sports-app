// Pure calendar logic shared by the calendar view and its tests. No DOM access.
// Day grouping uses the viewer's local calendar day. The duty rules mirror the
// server, which is the authority; the client only uses them to show buttons.

export const DUTY_KINDS = [
  { id: "coffee", label: "Coffee", icon: "coffee" },
  { id: "donuts", label: "Donuts", icon: "donut" },
  { id: "snacks", label: "Snacks", icon: "sparkle" },
  { id: "drinks", label: "Drinks", icon: "bolt" },
  { id: "other", label: "Something else", icon: "plus" },
];

export const CLAIMS_PER_DAY = 2;
const CLAIM_GRACE_MS = 3 * 3_600_000;
const SOURCE_ORDER = { match: 0, event: 1, duty: 2 };

const pad = (value) => String(value).padStart(2, "0");

export function localDayKey(value) {
  const date = value instanceof Date ? value : new Date(value);
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function monthKey(value = new Date()) {
  const date = value instanceof Date ? value : new Date(value);
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}`;
}

export function shiftMonth(key, delta) {
  const [year, month] = key.split("-").map(Number);
  return monthKey(new Date(year, month - 1 + delta, 1));
}

/** Six weeks, starting on the Sunday on or before the 1st. */
export function monthGrid(key) {
  const [year, month] = key.split("-").map(Number);
  const first = new Date(year, month - 1, 1);
  const start = new Date(year, month - 1, 1 - first.getDay());
  const cells = [];
  for (let index = 0; index < 42; index += 1) {
    const date = new Date(start.getFullYear(), start.getMonth(), start.getDate() + index);
    cells.push({ key: localDayKey(date), day: date.getDate(), inMonth: date.getMonth() === month - 1 });
  }
  return cells;
}

export function dutyEntry(duty) {
  const who = duty.claimedBy?.name ?? "Unclaimed";
  return {
    id: duty.id,
    source: "duty",
    date: duty.startsAt,
    title: duty.title,
    detail: `${duty.kindLabel} · ${who}`,
    accent: duty.claimedBy ? "sky" : "coral",
    eventType: duty.kindLabel,
    duty,
  };
}

/** Matches, club events and duties as one list, sorted by time. */
export function calendarEntries(state) {
  if (Array.isArray(state.calendarEntries)) return state.calendarEntries;
  const entries = [];
  for (const fixture of state.nextFixtures ?? []) {
    entries.push({
      id: fixture.id,
      source: "match",
      date: fixture.date,
      title: `${fixture.homeAway === "Home" ? "vs" : "@"} ${fixture.opponent}`,
      detail: `${fixture.venue} · ${fixture.competition}`,
      accent: "lime",
      eventType: null,
      duty: null,
    });
  }
  for (const event of state.schedule ?? []) {
    entries.push({
      id: event.id,
      source: "event",
      date: event.date,
      title: event.title,
      detail: event.detail,
      accent: event.accent,
      eventType: event.type,
      duty: null,
    });
  }
  for (const duty of state.duties ?? []) entries.push(dutyEntry(duty));
  return entries.sort(
    (a, b) => new Date(a.date) - new Date(b.date) || SOURCE_ORDER[a.source] - SOURCE_ORDER[b.source],
  );
}

export function entriesByDay(entries) {
  const map = new Map();
  for (const entry of entries) {
    const key = localDayKey(entry.date);
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(entry);
  }
  return map;
}

/** How many duties this person already holds on the UTC day of `startsAt`. */
export function claimsOnDay(duties, userId, startsAt) {
  const day = String(startsAt).slice(0, 10);
  return duties.filter((duty) => (duty.claimedBy?.id === userId || duty.assignedTo?.id === userId) && String(duty.startsAt).slice(0, 10) === day).length;
}

/** mine | taken | open | limit | passed — what this person can do with the duty. */
export function claimState(duty, userId, duties, now = Date.now()) {
  if (duty.assignedTo) return duty.assignedTo.id === userId ? "mine" : "taken";
  if (duty.claimedBy) return duty.claimedBy.id === userId ? "mine" : "taken";
  if (new Date(duty.startsAt).getTime() < now - CLAIM_GRACE_MS) return "passed";
  if (claimsOnDay(duties, userId, duty.startsAt) >= CLAIMS_PER_DAY) return "limit";
  return "open";
}

export function openDuties(duties, userId, now = Date.now()) {
  return duties
    .filter((duty) => claimState(duty, userId, duties, now) === "open")
    .sort((a, b) => new Date(a.startsAt) - new Date(b.startsAt));
}

export function kindMeta(kindId) {
  return DUTY_KINDS.find((kind) => kind.id === kindId) ?? DUTY_KINDS[DUTY_KINDS.length - 1];
}
