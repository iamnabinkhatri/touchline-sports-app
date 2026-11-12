import test from "node:test";
import assert from "node:assert/strict";

import { initialState } from "./fixtures/demo-state.js";
import { splitSquad } from "../js/balance.js";
import { pickupTeamNames, pickupTeamTone } from "../js/pickup-team-names.js";

const allPlayers = initialState.teams[0].players;
const available = allPlayers.filter((player) => player.status === "available");

function ratingOf(players) {
  return players.reduce((total, player) => total + player.rating, 0);
}

function ids(players) {
  return players.map((player) => player.id);
}

test("splits the available squad into two equal teams", () => {
  const result = splitSquad(available, { positionAware: true, seed: 1 });
  assert.equal(result.teamA.players.length, 7);
  assert.equal(result.teamB.players.length, 7);
  assert.equal(result.poolSize, 14);
  assert.equal(new Set([...ids(result.teamA.players), ...ids(result.teamB.players)]).size, 14);
});

test("keeps the strength gap tight", () => {
  const result = splitSquad(available, { positionAware: true, seed: 1 });
  assert.ok(result.gap <= 0.5, `expected a tight gap, got ${result.gap}`);
  assert.ok(result.balanceScore >= 85, `expected a strong balance score, got ${result.balanceScore}`);
  assert.ok(Math.abs(ratingOf(result.teamA.players) - ratingOf(result.teamB.players)) <= 0.5);
});

test("splits goalkeepers and keeps the positional spread as even as the pool allows", () => {
  const result = splitSquad(available, { positionAware: true, seed: 1 });
  assert.equal(result.teamA.counts.GK, 1);
  assert.equal(result.teamB.counts.GK, 1);
  assert.ok(result.positionGap <= 2, `position gap ${result.positionGap}`);
});

test("includes every player exactly once when doubtful players are included", () => {
  const pool = allPlayers.filter((player) => player.status !== "out");
  const result = splitSquad(pool, { positionAware: true, seed: 7 });
  const combined = [...ids(result.teamA.players), ...ids(result.teamB.players)];
  assert.equal(result.teamA.players.length, 8);
  assert.equal(result.teamB.players.length, 8);
  assert.equal(new Set(combined).size, 16);
});

test("is deterministic for a given seed", () => {
  const first = splitSquad(available, { positionAware: true, seed: 3 });
  const second = splitSquad(available, { positionAware: true, seed: 3 });
  assert.deepEqual(ids(first.teamA.players), ids(second.teamA.players));
  assert.deepEqual(ids(first.teamB.players), ids(second.teamB.players));
  assert.equal(first.balanceScore, second.balanceScore);
});

test("handles an odd pool with one floater and no duplicate players", () => {
  const result = splitSquad(available.slice(0, 13), { positionAware: true, seed: 3 });
  assert.ok(result.floater);
  assert.equal(result.teamA.players.length, 6);
  assert.equal(result.teamB.players.length, 6);
  const combined = [...ids(result.teamA.players), ...ids(result.teamB.players)];
  assert.equal(combined.includes(result.floater.id), false);
  assert.equal(new Set(combined).size, 12);
});

test("handles a tiny pool and an empty pool without throwing", () => {
  const tiny = splitSquad(available.slice(0, 2), { seed: 2 });
  assert.equal(tiny.teamA.players.length, 1);
  assert.equal(tiny.teamB.players.length, 1);
  const empty = splitSquad([], { seed: 2 });
  assert.equal(empty.teamA.players.length, 0);
  assert.equal(empty.teamB.players.length, 0);
  assert.equal(empty.balanceScore, 0);
  const solo = splitSquad(available.slice(0, 1), { seed: 2 });
  assert.equal(solo.teamA.players.length, 0);
  assert.equal(solo.teamB.players.length, 0);
  assert.equal(solo.floater.id, available[0].id);
});

test("pickup team names use two distinct Yolo colors and cycle through ordered pairings", () => {
  const pairs = Array.from({ length: 12 }, (_, seed) => pickupTeamNames(seed));
  assert.equal(new Set(pairs.map((pair) => pair.join(" vs "))).size, 12);
  for (const [a, b] of pairs) {
    assert.notEqual(a, b);
    assert.match(a, /^Yolo (Blue|Red|Green|Yellow)$/);
    assert.match(b, /^Yolo (Blue|Red|Green|Yellow)$/);
    assert.notEqual(pickupTeamTone(a), pickupTeamTone(b));
  }
});

test("position-aware mode never scores worse than position-blind mode on positions", () => {
  const aware = splitSquad(available, { positionAware: true, seed: 4 });
  const blind = splitSquad(available, { positionAware: false, seed: 4 });
  assert.ok(aware.positionGap <= 2);
  assert.ok(aware.gap <= 0.5);
  assert.ok(blind.gap <= 0.5);
});
