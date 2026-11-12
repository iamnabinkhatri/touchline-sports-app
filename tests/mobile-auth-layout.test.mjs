import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const responsive = readFileSync(new URL("../styles/responsive.css", import.meta.url), "utf8");
const base = readFileSync(new URL("../styles/base.css", import.meta.url), "utf8");

test("small-screen auth layout fits device width and scrolls above the iOS keyboard", () => {
  const auth = responsive.slice(responsive.lastIndexOf(".auth-screen {"));
  assert.match(auth, /max-width:\s*100vw/);
  assert.match(auth, /min-height:\s*100dvh/);
  assert.match(auth, /overflow-y:\s*auto/);
  assert.match(auth, /safe-area-inset-top/);
  assert.match(auth, /safe-area-inset-bottom/);
});

test("mobile login inputs and submit button use the available screen width", () => {
  const auth = responsive.slice(responsive.lastIndexOf(".auth-screen {"));
  assert.match(auth, /\.auth-screen \.auth-form\s*\{[^}]*width:\s*100%/s);
  assert.match(auth, /\.auth-screen \.field input\s*\{[^}]*width:\s*100%[^}]*font-size:\s*16px/s);
  assert.match(auth, /\.auth-screen \.form-actions \.btn\s*\{[^}]*width:\s*100%/s);
  assert.match(auth, /\.auth-screen \.auth-links\s*\{[^}]*flex-wrap:\s*wrap/s);
});

test("auth content stays within the viewport even when iOS reports a wider layout viewport", () => {
  assert.match(base, /body\s*\{[^}]*overflow-x:\s*hidden/s);
  assert.match(base, /\.auth-screen\s*\{[^}]*width:\s*100%[^}]*max-width:\s*100vw[^}]*overflow-x:\s*clip/s);
  assert.match(base, /\.auth-screen > p\s*\{[^}]*overflow-wrap:\s*anywhere/s);
  assert.match(base, /\.auth-screen \.auth-links\s*\{[^}]*flex-wrap:\s*wrap/s);
});

test("shared mobile app shell cannot expand beyond the device width", () => {
  assert.match(responsive, /@media \(max-width:\s*760px\)\s*\{\s*html,\s*body,\s*#app,\s*\.app-shell,\s*\.app-main,\s*\.main\s*\{[^}]*max-width:\s*100%[^}]*min-width:\s*0/s);
  assert.match(responsive, /\.app-main,\s*\.main\s*\{[^}]*overflow-x:\s*clip/s);
});
