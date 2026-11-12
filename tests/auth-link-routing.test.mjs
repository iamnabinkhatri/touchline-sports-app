import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;
const app = fs.readFileSync(path.join(ROOT, "js", "app.js"), "utf8");

test("adding the default home hash preserves email action query parameters", () => {
  assert.match(
    app,
    /history\.replaceState\(null,\s*"",\s*`\$\{window\.location\.pathname\}\$\{window\.location\.search\}#\/home`\)/,
  );
});
