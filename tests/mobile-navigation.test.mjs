import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

test("mobile navigation stays fixed, visible and clear of device safe areas", () => {
  const html = read("index.html");
  const responsive = read("styles/responsive.css");
  assert.match(html, /name="viewport"[^>]*viewport-fit=cover/);
  assert.match(responsive, /\.mobile-nav\s*\{[^}]*position:\s*fixed[^}]*bottom:\s*0[^}]*safe-area-inset-bottom/s);
  assert.match(responsive, /\.app-main\s*\{[^}]*padding-bottom:\s*calc\([^;]*safe-area-inset-bottom/s);
  assert.match(responsive, /padding-top:\s*calc\([^;]*safe-area-inset-top/);
});

test("all seven mobile destinations use short labels that fit phone widths", () => {
  const app = read("js/app.js");
  const mobileNav = app.slice(app.indexOf("function renderMobileNav"), app.indexOf("function renderSearchResults"));
  for (const label of ["Home", "Clubs", "Polls", "Team", "Plans", "Pickup", "Calendar"]) {
    assert.ok(mobileNav.includes(`"${label}"`), `Missing mobile nav label: ${label}`);
  }
  assert.match(mobileNav, /Object\.entries\(ROUTES\)/);
});
