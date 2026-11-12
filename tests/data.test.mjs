import test from "node:test";
import assert from "node:assert/strict";

import { enrichPlayer, initialState } from "./fixtures/demo-state.js";

const team = initialState.teams[0];
const POSITIONS = new Set([
  "GK",
  "RB",
  "CB",
  "LB",
  "LWB",
  "RWB",
  "DM",
  "CM",
  "AM",
  "LM",
  "RM",
  "RW",
  "LW",
  "ST",
]);

test("seed data is on the current schema version", () => {
  assert.equal(initialState.version, 2);
  assert.ok(Array.isArray(initialState.teams));
  assert.ok(initialState.teams.length > 0);
});

test("squad has unique ids and shirt numbers", () => {
  assert.equal(team.players.length, 18);
  assert.equal(new Set(team.players.map((player) => player.id)).size, team.players.length);
  assert.equal(
    new Set(team.players.map((player) => player.number)).size,
    team.players.length,
  );
});

test("every player has sane ratings and positions", () => {
  for (const player of team.players) {
    assert.ok(POSITIONS.has(player.pos), `${player.name} has an unknown position`);
    assert.ok(["GK", "DEF", "MID", "FWD"].includes(player.group));
    assert.ok(["available", "doubtful", "out"].includes(player.status));
    assert.ok(player.rating >= 1 && player.rating <= 10, `${player.name} rating out of range`);
    assert.ok(Number.isInteger(player.ratingCount) && player.ratingCount >= 0);
    assert.ok(player.userRating === null || (player.userRating >= 1 && player.userRating <= 10));
  }
});

test("starting XI references real players and has eleven slots", () => {
  const ids = new Set(team.players.map((player) => player.id));
  assert.equal(team.startingXI.length, 11);
  assert.equal(new Set(team.startingXI).size, 11);
  team.startingXI.forEach((id) => assert.ok(ids.has(id), `Unknown player ${id}`));
});

test("enrichPlayer is idempotent and preserves existing rating metadata", () => {
  const player = {
    ...team.players[0],
    ratingCount: 4,
    userRating: 9,
  };
  assert.deepEqual(enrichPlayer(player), player);
});

test("game plans contain the content needed by every tab", () => {
  for (const plan of initialState.plans) {
    assert.ok(plan.objective.length > 0);
    assert.ok(plan.inPossession.shape.length > 0);
    assert.ok(plan.inPossession.patterns.length > 0);
    assert.ok(plan.outOfPossession.trigger.length > 0);
    assert.ok(plan.setPieces.attack.steps.length > 0);
    assert.ok(plan.checklist.length > 0);
  }
});
