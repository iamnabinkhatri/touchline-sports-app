import test from "node:test";
import assert from "node:assert/strict";

import { safeToken } from "../js/utils.js";

const TONES = ["forest", "lime", "coral", "sky", "violet", "gold", "sage", "red"];

test("returns an allowed token unchanged when lowercase", () => {
  assert.equal(safeToken("forest", TONES, "forest"), "forest");
  assert.equal(safeToken("coral", TONES, "forest"), "coral");
});

test("normalizes case before the allowlist check", () => {
  assert.equal(safeToken("LIME", TONES, "forest"), "lime");
});

test("rejects attribute-breaking and script-bearing values", () => {
  for (const payload of [
    `x" onmouseover="alert(1)`,
    "<script>alert(1)</script>",
    "javascript:alert(1)",
    "gold onload=alert(1)",
    "",
    null,
    undefined,
    42,
  ]) {
    assert.equal(safeToken(payload, TONES, "forest"), "forest");
  }
});

test("does not allow prototype keys", () => {
  assert.equal(safeToken("__proto__", TONES, "forest"), "forest");
  assert.equal(safeToken("constructor", TONES, "forest"), "forest");
});
