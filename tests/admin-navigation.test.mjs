import test from "node:test";
import assert from "node:assert/strict";
import { baseHrefForPath } from "../js/navigation.js";

test("fragment navigation from the private admin entry keeps its path", () => {
  const origin = "http://127.0.0.1:4173";
  const base = new URL(baseHrefForPath("/manage-private-key"), origin);
  assert.equal(new URL("#/calendar", base).pathname, "/manage-private-key");
  assert.equal(new URL("#/communities", base).pathname, "/manage-private-key");
});

test("public app navigation stays rooted at the public entry", () => {
  const origin = "http://127.0.0.1:4173";
  for (const pathname of ["/", "/index.html"]) {
    const base = new URL(baseHrefForPath(pathname), origin);
    assert.equal(new URL("#/calendar", base).pathname, "/");
  }
});

test("mobile navigation never enables a super-admin entry", async () => {
  const app = await import("node:fs/promises").then(({ readFile }) => readFile(new URL("../js/app.js", import.meta.url), "utf8"));
  assert.match(app, /function isAdminEntry\(\)\s*\{\s*if \(window\.TOUCHLINE_MOBILE\) return false;/);
  assert.doesNotMatch(app, /mobileAdmin=/);
  assert.match(app, /Super-admin access is available only in the web app/);
});
