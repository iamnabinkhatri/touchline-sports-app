import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;
const html = fs.readFileSync(path.join(ROOT, "index.html"), "utf8");
const server = fs.readFileSync(path.join(ROOT, "backend", "server.py"), "utf8");
const jsFiles = [];
const walk = (directory) => {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const resolved = path.join(directory, entry.name);
    if (entry.isDirectory()) walk(resolved);
    else if (entry.name.endsWith(".js")) jsFiles.push(resolved);
  }
};
walk(path.join(ROOT, "js"));

test("index.html contains no inline scripts, so script-src 'self' can stay strict", () => {
  const scripts = [...html.matchAll(/<script\b([^>]*)>/gi)].map((match) => match[1]);
  assert.ok(scripts.length > 0);
  for (const attributes of scripts) {
    assert.match(attributes, /\bsrc\s*=\s*["']/i);
  }
  assert.ok(!/\son[a-z]+\s*=/i.test(html), "inline event handler in index.html");
});

test("server sends a script-src 'self' policy without unsafe-script allowances", () => {
  assert.match(server, /script-src 'self'/);
  assert.doesNotMatch(server, /script-src[^"']*unsafe-inline/);
  assert.match(server, /frame-ancestors 'none'/);
  assert.match(server, /object-src 'none'/);
  assert.match(server, /base-uri 'self'/, "the same-origin base href in index.html must be permitted");
});

test("runtime code avoids eval and string-to-code execution", () => {
  for (const file of jsFiles) {
    const source = fs.readFileSync(file, "utf8");
    assert.doesNotMatch(source, /\beval\s*\(/, `${file} uses eval`);
    assert.doesNotMatch(source, /\bnew\s+Function\s*\(/, `${file} uses new Function`);
    assert.doesNotMatch(source, /document\.write\s*\(/, `${file} uses document.write`);
  }
});
