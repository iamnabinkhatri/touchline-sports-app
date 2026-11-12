import test from "node:test";
import assert from "node:assert/strict";
import { filterCommunities, rankSearchResults, visibleDiscoverCommunities } from "../js/community-discovery.js";

test("sport filters include matching joined communities as well as discoverable ones", () => {
  const communities = [
    { id: "joined", sport: "Soccer", joined: true },
    { id: "open", sport: "Soccer", joined: false },
    { id: "other", sport: "Basketball", joined: false },
  ];
  assert.deepEqual(filterCommunities(communities, "Soccer").map((item) => item.id), ["joined", "open"]);
  assert.deepEqual(filterCommunities(communities, "All").map((item) => item.id), ["joined", "open", "other"]);
});

test("search recommendations rank exact, prefix and word matches above broad text matches", () => {
  const results = [
    { type: "community", title: "East Soccer Club", meta: "Soccer · 20 members" },
    { type: "community", title: "Soccer Club", meta: "Community · 8 members" },
    { type: "player", title: "Alex Soccer", meta: "#10 · ST" },
  ];
  assert.deepEqual(rankSearchResults(results, "soccer").map((item) => item.title), [
    "Soccer Club",
    "East Soccer Club",
    "Alex Soccer",
  ]);
});

test("blank search returns the highest ranked recommendations", () => {
  const results = [
    { title: "Local Team", recommendationScore: 4 },
    { title: "My Club", recommendationScore: 10 },
  ];
  assert.equal(rankSearchResults(results, "")[0].title, "My Club");
});

test("discover shows five communities at a time and reveals the rest on request", () => {
  const communities = Array.from({ length: 8 }, (_, index) => ({ id: `c${index}` }));
  const firstPage = visibleDiscoverCommunities(communities);
  assert.equal(firstPage.items.length, 5);
  assert.equal(firstPage.hasMore, true);
  assert.equal(firstPage.hiddenCount, 3);
  assert.equal(visibleDiscoverCommunities(communities, true).items.length, 8);
  assert.equal(visibleDiscoverCommunities(communities.slice(0, 5)).hasMore, false);
});
