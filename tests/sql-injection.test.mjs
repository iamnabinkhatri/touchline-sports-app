import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

import { initialState } from "./fixtures/demo-state.js";
import { renderHome } from "../js/views/home.js";
import { renderPolls } from "../js/views/polls.js";
import { renderTeams } from "../js/views/teams.js";

const ROOT = new URL("..", import.meta.url).pathname;
const sqlPayload = `' OR 1=1; DROP TABLE players; --`;
const sqlPayload2 = `" UNION SELECT username, password FROM users --`;

function readFrontendSources() {
  const files = [];
  const walk = (directory) => {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      const resolved = path.join(directory, entry.name);
      if (entry.isDirectory()) walk(resolved);
      else if (entry.name.endsWith(".js")) files.push(resolved);
    }
  };
  walk(path.join(ROOT, "js"));
  return files.map((file) => ({ file, source: fs.readFileSync(file, "utf8") }));
}

test("the app has no SQL client, database driver, or SQL execution surface", () => {
  const packageJson = JSON.parse(fs.readFileSync(path.join(ROOT, "package.json"), "utf8"));
  const dependencyNames = Object.keys({
    ...(packageJson.dependencies ?? {}),
    ...(packageJson.devDependencies ?? {}),
  }).join(" ");
  assert.doesNotMatch(dependencyNames, /sqlite|mysql|postgres|\bpg\b|sequelize|knex/i);

  for (const { file, source } of readFrontendSources()) {
    assert.doesNotMatch(source, /\.query\s*\(/, `${file} contains a database query call`);
    assert.doesNotMatch(source, /new\s+(?:SQLite|Database)\s*\(/, `${file} opens a database`);
    assert.doesNotMatch(source, /\b(?:SELECT|INSERT INTO|UPDATE|DELETE FROM)\b[\s\S]{0,80}\b(?:FROM|WHERE|VALUES)\b/, `${file} contains SQL`);
  }
});

test("SQL injection payloads are rendered as inert text", () => {
  const state = JSON.parse(JSON.stringify(initialState));
  state.posts[0].text = sqlPayload;
  state.polls[0].question = sqlPayload2;
  state.polls[0].options[0].label = sqlPayload;
  state.teams[0].players[0].name = sqlPayload2;

  const ui = {
    homeTab: "for-you",
    communityFilterId: null,
    sportFilter: "All",
    pollTab: "active",
    pollFilter: "All",
    expandedPollCards: state.polls.map((poll) => poll.id),
    teamTab: "squad",
    positionFilter: "all",
    squadQuery: "",
    lineupSelected: null,
    planTab: "overview",
    selectedPlanId: "plan-riverside",
    openComments: [],
    pickupIncludeDoubtful: false,
    pickupPositionAware: true,
    pickupVariant: 0,
  };

  const output = [
    renderHome(state, ui),
    renderPolls(state, ui),
    renderTeams(state, ui),
  ].join("\n");

  assert.ok(output.includes("&#039; OR 1=1; DROP TABLE players; --"));
  assert.ok(output.includes("&quot; UNION SELECT username, password FROM users --"));
  assert.ok(!output.includes(sqlPayload));
  assert.ok(!output.includes(sqlPayload2));
});

test("the front end has one same-origin API client for server access", () => {
  const apiFile = path.join(ROOT, "js", "api.js");
  const apiSource = fs.readFileSync(apiFile, "utf8");
  assert.match(apiSource, /const API_BASE = globalThis\.window\?\.TOUCHLINE_API_BASE \|\| "\/api\/v1";/);
  assert.doesNotMatch(apiSource, /https?:\/\//, "API client should use relative same-origin URLs");
  for (const { file, source } of readFrontendSources()) {
    if (file !== apiFile) {
      assert.doesNotMatch(source, /\bfetch\s*\(/, `${file} bypasses the centralized API client`);
    }
  }
});
