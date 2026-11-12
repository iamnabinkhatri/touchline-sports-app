import test from "node:test";
import assert from "node:assert/strict";

import {
  clamp,
  escapeHTML,
  initials,
  pad,
  timeUntil,
  avatarTone,
  countdownParts,
} from "../js/utils.js";

test("escapeHTML encodes all HTML control characters", () => {
  assert.equal(
    escapeHTML(`<script>alert("x") & 'y'</script>`),
    "&lt;script&gt;alert(&quot;x&quot;) &amp; &#039;y&#039;&lt;/script&gt;",
  );
});

test("escapeHTML leaves SQL-like strings as text", () => {
  const payload = `' OR 1=1 --`;
  assert.equal(escapeHTML(payload), "&#039; OR 1=1 --");
});

test("initials returns up to two uppercase initials", () => {
  assert.equal(initials("Maya Chen"), "MC");
  assert.equal(initials("  Priya   Nair  "), "PN");
  assert.equal(initials("Ava"), "A");
  assert.equal(initials(""), "");
});

test("clamp keeps values inside the range", () => {
  assert.equal(clamp(-4, 1, 10), 1);
  assert.equal(clamp(11, 1, 10), 10);
  assert.equal(clamp(7.5, 1, 10), 7.5);
});

test("pad always returns two digits", () => {
  assert.equal(pad(1), "01");
  assert.equal(pad(12), "12");
});

test("avatarTone is deterministic", () => {
  assert.equal(avatarTone("Maya Chen"), avatarTone("Maya Chen"));
  assert.ok(["lime", "coral", "sky", "gold", "violet", "sage"].includes(avatarTone("Alex")));
});

test("countdownParts returns non-negative values and timeUntil closes in the past", () => {
  const future = new Date(Date.now() + 90 * 60 * 1000);
  const parts = countdownParts(future);
  assert.ok(parts.hours >= 1);
  assert.ok(parts.minutes >= 0);
  assert.equal(timeUntil(new Date(Date.now() - 1_000)), "Closed");
});
