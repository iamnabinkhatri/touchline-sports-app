import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const responsive = readFileSync(new URL("../styles/responsive.css", import.meta.url), "utf8");
const communities = readFileSync(new URL("../styles/communities.css", import.meta.url), "utf8");
const app = readFileSync(new URL("../js/app.js", import.meta.url), "utf8");
const service = readFileSync(new URL("../backend/service.py", import.meta.url), "utf8");

test("mobile messenger keeps the composer above navigation and safe-area insets", () => {
  assert.match(responsive, /\.community-messenger\s*\{[^}]*bottom:\s*calc\(env\(safe-area-inset-bottom[^}]*max-height:[^}]*100dvh/s);
  assert.match(responsive, /\.community-messenger__form\s*\{[^}]*flex:\s*none/s);
  assert.match(responsive, /\.community-messenger__messages\s*\{[^}]*min-height:\s*0/s);
});

test("minimized messenger launcher stays above the fixed mobile navigation and safe area", () => {
  assert.match(responsive, /\.community-messenger-launcher\s*\{[^}]*bottom:\s*calc\(env\(safe-area-inset-bottom[^}]*z-index:\s*70/s);
  assert.match(responsive, /\.mobile-nav\s*\{[^}]*z-index:\s*50/s);
});

test("messenger distinguishes own messages and provides member tagging", () => {
  assert.match(app, /own \? " is-own" : " is-other"/);
  assert.match(communities, /\.community-messenger__message\.is-own\s*\{[^}]*align-self:\s*flex-end/s);
  assert.match(app, /Use @ to mention/);
  assert.match(app, /insert-chat-mention/);
  assert.doesNotMatch(app, /name="mentions"/);
  assert.match(service, /You were mentioned/);
});

test("chat message actions reveal on hover and remain available to keyboard and touch users", () => {
  assert.match(communities, /community-messenger__message-actions[^}]*opacity:\s*0/s);
  assert.match(communities, /:hover[^}]*community-messenger__message-actions/s);
  assert.match(communities, /@media[^}]*community-messenger__message-actions[^}]*opacity:\s*1/s);
  assert.match(service, /row\["user_id"\] != user_id/);
});

test("chat starts minimized and entering a community keeps it minimized", () => {
  assert.match(app, /messengerMinimized:\s*true/);
  assert.match(app, /function selectCommunityChat\(communityId\)[\s\S]*?ui\.messengerMinimized = true/);
  assert.match(app, /if \(communityRoute\) selectCommunityChat\(communityRoute\.communityId\)/);
  assert.doesNotMatch(app, /if \(initialCommunityRoute\) await openMessengerPanel/);
});

test("message refresh preserves the composer draft and cursor while polling", () => {
  assert.match(app, /ui\.messengerDraft = existingComposer\.value/);
  assert.match(app, /nextComposer\.value = ui\.messengerDraft/);
  assert.match(app, /nextComposer\.setSelectionRange\(selectionStart, selectionEnd\)/);
  assert.match(app, /ui\.messengerDraft = chatTextarea\.value/);
  assert.match(app, /ui\.messengerForceScrollToBottom \|\| \(existingMessages[\s\S]*?nextMessages\.scrollTop = wasAtBottom \? nextMessages\.scrollHeight/);
  assert.match(app, /ui\.messengerIsAtBottom = messages\.scrollHeight - messages\.scrollTop - messages\.clientHeight <= 48/);
});

test("messenger uses a polished responsive conversation and composer layout", () => {
  assert.match(communities, /\.community-messenger__message\.is-own\s*\{[^}]*border-radius/s);
  assert.match(communities, /\.community-messenger__timestamp/);
  assert.match(communities, /\.community-messenger__form textarea\s*\{[^}]*font-size:\s*16px/s);
  assert.match(communities, /\.community-messenger__message p\s*\{[^}]*white-space:\s*pre-wrap/s);
});

test("mobile profile menu hides API access and API-key administration entries", () => {
  assert.match(app, /\$\{!window\.TOUCHLINE_MOBILE \? `<div class="modal-actions"><button[^`]*open-api-key-access/);
});
