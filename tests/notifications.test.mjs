import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const app = readFileSync(new URL("../js/app.js", import.meta.url), "utf8");
const service = readFileSync(new URL("../backend/service.py", import.meta.url), "utf8");

test("notification UI groups post excerpts by community and preserves each post link", () => {
  assert.match(app, /groupNotifications\(state\.notifications\)/);
  assert.match(app, /notification-stack__items/);
  assert.match(app, /data-action="open-notification" data-note="\$\{escapeHTML\(notification\.id\)\}"/);
  assert.match(service, /route=f"#\/community\/\{community_id\}\/posts\/\{post_id\}"/);
});

test("opening a notification marks only that user's item read before following its deep link", () => {
  const open = app.slice(app.indexOf("async function openNotification"), app.indexOf("function applyRosterFilter"));
  assert.match(open, /await api\.post\("\/notifications\/read", \{ ids: \[noteId\] \}\)/);
  assert.match(open, /if \(route\.startsWith\("#\/"\)\)[\s\S]*?window\.location\.hash = route/);
  assert.match(service, /UPDATE notifications SET unread = 0 WHERE user_id = \?/);
});

test("poll close notifications fan out to community membership rows with idempotent keys", () => {
  const closeProcessing = service.slice(service.indexOf("def process_due_polls"), service.indexOf("def process_due_polls_once"));
  assert.match(closeProcessing, /SELECT user_id FROM community_members WHERE community_id=\?/);
  assert.match(closeProcessing, /source_key=f"poll-closed:\{poll\['id'\]\}:\{recipient\['user_id'\]\}"/);
});
