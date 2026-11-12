import test from "node:test";
import assert from "node:assert/strict";

import { planProgress, pollPercent, pollTotal, teamAvailability } from "../js/store.js";

test("pollTotal and pollPercent derive from option vote counts", () => {
  const poll = { options: [{ votes: 30 }, { votes: 10 }] };
  assert.equal(pollTotal(poll), 40);
  assert.equal(pollPercent(poll.options[0], poll), 75);
  assert.equal(pollTotal({}), 0);
});

test("planProgress counts completed checklist items", () => {
  assert.equal(planProgress({ checklist: [{ done: true }, { done: false }, { done: true }, { done: false }] }), 50);
  assert.equal(planProgress({ checklist: [] }), 0);
  assert.equal(planProgress({}), 0);
});

test("teamAvailability groups players by status", () => {
  const team = {
    players: [
      { status: "available" },
      { status: "available" },
      { status: "doubtful" },
      { status: "out" },
    ],
  };
  assert.deepEqual(teamAvailability(team), { available: 2, doubtful: 1, out: 1 });
  assert.deepEqual(teamAvailability({}), { available: 0, doubtful: 0, out: 0 });
});
