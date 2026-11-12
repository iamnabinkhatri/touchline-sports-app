import { test } from "node:test";
import assert from "node:assert/strict";
import {
  CLAIMS_PER_DAY,
  calendarEntries,
  claimState,
  claimsOnDay,
  kindMeta,
  localDayKey,
  monthGrid,
  monthKey,
  openDuties,
  shiftMonth,
} from "../js/calendar-model.js";

const ME = "me-1";
const OTHER = "other-2";
const HOUR = 3_600_000;

function duty(overrides = {}) {
  return {
    id: "duty-x",
    kind: "coffee",
    kindLabel: "Coffee",
    title: "Coffee",
    startsAt: new Date(Date.now() + 48 * HOUR).toISOString(),
    note: "",
    eventKey: null,
    claimedBy: null,
    claimedAt: null,
    createdById: OTHER,
    ...overrides,
  };
}

test("month grid is six Sunday-first weeks that contain every day once", () => {
  const cells = monthGrid("2026-11");
  assert.equal(cells.length, 42);
  assert.equal(new Date(`${cells[0].key}T12:00:00`).getDay(), 0, "first cell is a Sunday");
  const inMonth = cells.filter((cell) => cell.inMonth).map((cell) => cell.key);
  assert.equal(inMonth.length, 30, "November has 30 days");
  assert.equal(new Set(inMonth).size, 30);
  assert.equal(inMonth[0], "2026-11-01");
  assert.equal(inMonth[29], "2026-11-30");
});

test("month grid handles a month that starts on a Sunday", () => {
  const cells = monthGrid("2026-02");
  assert.equal(cells[0].key, "2026-02-01", "February 2026 starts on a Sunday");
  assert.equal(cells[0].inMonth, true);
  assert.equal(cells.filter((cell) => cell.inMonth).length, 28);
});

test("shifting months wraps across years in both directions", () => {
  assert.equal(shiftMonth("2026-12", 1), "2027-01");
  assert.equal(shiftMonth("2027-01", -1), "2026-12");
  assert.equal(shiftMonth("2026-11", 3), "2027-02");
  assert.equal(monthKey(new Date(2026, 0, 9)), "2026-01");
});

test("local day keys use the viewer's calendar day", () => {
  assert.equal(localDayKey(new Date(2026, 10, 7, 23, 30)), "2026-11-07");
  assert.equal(localDayKey(new Date(2026, 10, 8, 0, 5)), "2026-11-08");
});

test("claim state covers open, mine, taken, passed and the daily limit", () => {
  const now = Date.now();
  const open = duty();
  assert.equal(claimState(open, ME, [open], now), "open");
  assert.equal(claimState(duty({ claimedBy: { id: ME } }), ME, [], now), "mine");
  assert.equal(claimState(duty({ claimedBy: { id: OTHER } }), ME, [], now), "taken");
  const old = duty({ startsAt: new Date(now - 6 * HOUR).toISOString() });
  assert.equal(claimState(old, ME, [old], now), "passed");
  const day = new Date(now + 72 * HOUR).toISOString();
  const held = Array.from({ length: CLAIMS_PER_DAY }, (_, i) =>
    duty({ id: `held-${i}`, startsAt: day, claimedBy: { id: ME } }),
  );
  const candidate = duty({ id: "next", startsAt: day });
  assert.equal(claimState(candidate, ME, [...held, candidate], now), "limit");
  assert.equal(claimState(candidate, OTHER, [...held, candidate], now), "open");
});

test("the daily count only includes duties on the same day", () => {
  const monday = "2026-11-09T10:00:00.000Z";
  const tuesday = "2026-11-10T10:00:00.000Z";
  const duties = [
    duty({ startsAt: monday, claimedBy: { id: ME } }),
    duty({ startsAt: tuesday, claimedBy: { id: ME } }),
    duty({ startsAt: monday, claimedBy: { id: OTHER } }),
  ];
  assert.equal(claimsOnDay(duties, ME, monday), 1);
  assert.equal(claimsOnDay(duties, ME, tuesday), 1);
});

test("open duties exclude claimed and past ones and sort soonest first", () => {
  const now = Date.now();
  const late = duty({ id: "late", startsAt: new Date(now + 96 * HOUR).toISOString() });
  const soon = duty({ id: "soon", startsAt: new Date(now + 24 * HOUR).toISOString() });
  const claimed = duty({ id: "claimed", claimedBy: { id: OTHER } });
  const past = duty({ id: "past", startsAt: new Date(now - 10 * HOUR).toISOString() });
  const result = openDuties([late, claimed, past, soon], ME, now).map((d) => d.id);
  assert.deepEqual(result, ["soon", "late"]);
});

test("calendar entries merge matches, events and duties in time order", () => {
  const state = {
    nextFixtures: [{ id: "fx", opponent: "Riverside", homeAway: "Away", date: "2026-11-07T19:30:00.000Z", venue: "Kings Park", competition: "League" }],
    schedule: [{ id: "ev", type: "Training", title: "Walkthrough", detail: "Pier 40", accent: "sky", date: "2026-11-06T18:00:00.000Z" }],
    duties: [duty({ id: "d", title: "Coffee", startsAt: "2026-11-07T17:00:00.000Z", claimedBy: { id: OTHER, name: "Jordan Reyes" } })],
  };
  const entries = calendarEntries(state);
  assert.deepEqual(entries.map((e) => e.source), ["event", "duty", "match"]);
  const match = entries[2];
  assert.equal(match.title, "@ Riverside");
  assert.equal(match.accent, "lime");
  const claimedDuty = entries[1];
  assert.equal(claimedDuty.accent, "sky");
  assert.equal(claimedDuty.detail, "Coffee · Jordan Reyes");
});

test("unclaimed duties are coral so gaps stand out", () => {
  const entries = calendarEntries({ duties: [duty({ title: "Donuts", kind: "donuts", kindLabel: "Donuts" })] });
  assert.equal(entries[0].accent, "coral");
  assert.equal(entries[0].detail, "Donuts · Unclaimed");
});

test("unknown duty kinds fall back to a safe default", () => {
  assert.equal(kindMeta("coffee").icon, "coffee");
  assert.equal(kindMeta("nonsense").id, "other");
});
