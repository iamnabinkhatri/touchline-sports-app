import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const app = readFileSync(new URL("../js/app.js", import.meta.url), "utf8");

test("community membership refresh runs for signed-in users without requiring chat", () => {
  const polling = app.slice(app.indexOf("async function refreshMembershipAcrossDevices"), app.indexOf("if (!window.location.hash)"));
  assert.match(polling, /if\s*\(!state\s*\|\|\s*document\.hidden\s*\|\|\s*membershipRefreshInFlight\)\s*return/);
  assert.doesNotMatch(polling, /!ui\.messengerCommunityId\s*\|\|\s*document\.hidden/);
  assert.match(polling, /membershipChanged/);
  assert.match(polling, /renderApp\(\{\s*preserveScroll:\s*true\s*\}\)/);
  assert.match(polling, /window\.setInterval\(refreshMembershipAcrossDevices,\s*8000\)/);
});

test("community detail state is refreshed after membership status changes", () => {
  const polling = app.slice(app.indexOf("async function refreshMembershipAcrossDevices"), app.indexOf("if (!window.location.hash)"));
  assert.match(polling, /const openCommunity = next\.communities\.find\(\(community\) => community\.id === ui\.openCommunityId\)/);
  assert.match(polling, /openCommunityModal\(state, openCommunity\.id, ui, members\)/);
  assert.match(polling, /current\.joinRequestStatus !== previous\.joinRequestStatus/);
});
