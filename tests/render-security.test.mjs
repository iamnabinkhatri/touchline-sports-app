import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { initialState } from "./fixtures/demo-state.js";
import { renderHome, renderPost } from "../js/views/home.js";
import { renderCommunityFeed } from "../js/views/community-feed.js";
import { renderCommunities } from "../js/views/communities.js";
import { renderPolls } from "../js/views/polls.js";
import { avatar, communityMark } from "../js/ui.js";

test("player and community image renderers reject untrusted URL schemes", () => {
  assert.doesNotMatch(avatar("Player", { imageData: "javascript:alert(1)" }), /<img\b/i);
  assert.doesNotMatch(communityMark({ name: "Club", mark: "CL", accent: "forest", logoData: "https://evil.example/logo.png" }), /<img\b/i);
});

test("community posts display an optional image as a safe banner", () => {
  const state = JSON.parse(JSON.stringify(initialState));
  const post = state.posts[0];
  post.media = { type: "image", data: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l7sAAAAASUVORK5CYII=" };
  const html = renderPost(state, post, ui);
  assert.match(html, /<figure class="post-banner"><img src="data:image\/png;base64,/);
  assert.match(html, /Community photo<\/figcaption>/);
  assert.doesNotMatch(html, /<script|onerror=/i);
  post.media.data = "javascript:alert(1)";
  assert.doesNotMatch(renderPost(state, post, ui), /<figure class="post-banner"/);
});
import { renderTeams } from "../js/views/teams.js";
import { renderPlans } from "../js/views/plans.js";
import { getPickupPool, getPickupResult, renderPickup } from "../js/views/pickup.js";

const tagPayload = `<img src=x onerror=alert(1)>`;
const attrPayload = `x" onmouseover="alert(1)`;
const scriptPayload = `<script>alert(1)</script>`;

const ui = {
  homeTab: "for-you",
  communityFilterId: null,
  sportFilter: "All",
  pollTab: "active",
  pollFilter: "All",
  teamTab: "squad",
  positionFilter: "all",
  squadQuery: "",
  lineupSelected: null,
  planTab: "overview",
  selectedPlanId: "plan-riverside",
  openComments: [],
  pickupIncludeDoubtful: false,
  pickupPositionAware: true,
  pickupVariant: 0,
};

function maliciousState() {
  const state = JSON.parse(JSON.stringify(initialState));
  state.user.name = tagPayload;
  state.user.email = attrPayload;
  state.leaders[0].name = tagPayload;
  state.leaders[0].tone = attrPayload;
  state.schedule[0].accent = attrPayload;

  const community = state.communities[0];
  community.name = tagPayload;
  community.description = scriptPayload;
  community.mark = tagPayload;
  community.accent = attrPayload;
  community.activity = scriptPayload;
  community.privacy = attrPayload;

  const post = state.posts[0];
  post.author = tagPayload;
  post.authorTone = attrPayload;
  post.text = `${tagPayload} ' OR 1=1 --`;
  post.likes = tagPayload;
  post.media.competition = tagPayload;
  post.media.homeScore = tagPayload;
  post.media.awayScore = tagPayload;
  post.media.scorers = [tagPayload];

  const poll = state.polls[0];
  poll.question = tagPayload;
  poll.author = tagPayload;
  poll.category = attrPayload;
  poll.options[0].label = tagPayload;

  const player = state.teams[0].players[0];
  player.name = tagPayload;
  player.status = attrPayload;
  player.pos = tagPayload;

  const plan = state.plans[0];
  plan.title = tagPayload;
  plan.opponent = tagPayload;
  plan.objective = tagPayload;
  plan.status = attrPayload;
  plan.venue = tagPayload;
  plan.competition = tagPayload;
  plan.checklist[0].text = scriptPayload;

  return state;
}

function assertSafeHTML(html, label) {
  assert.ok(html.length > 500, `${label} should render content`);
  assert.ok(!html.includes(tagPayload), `${label} contains an unescaped tag payload`);
  assert.ok(!html.includes(attrPayload), `${label} contains an unescaped attribute payload`);
  assert.ok(!html.includes(scriptPayload), `${label} contains an unescaped script payload`);
  assert.ok(!html.includes("<script"), `${label} emitted a script tag`);
  assert.ok(!/<img\b/i.test(html), `${label} emitted an image tag from data`);
  assert.ok(!/href\s*=\s*["']javascript:/i.test(html), `${label} emitted a javascript URL`);
}

test("home rendering escapes malicious state and class tokens", () => {
  assertSafeHTML(renderHome(maliciousState(), { ...ui, openComments: ["post-maya-recap"] }), "home");
});

test("community rendering escapes malicious state and class tokens", () => {
  assertSafeHTML(renderCommunities(maliciousState(), ui), "communities");
});

test("community discover renders links in a five-item list and removes the club banner", () => {
  const state = JSON.parse(JSON.stringify(initialState));
  state.communities = Array.from({ length: 8 }, (_, index) => ({
    ...state.communities[0], id: `community-${index}`, name: `Club ${index}`, joined: false,
    sport: "Soccer", privacy: "Public", memberCount: 1, unreadCount: 0,
  }));
  const html = renderCommunities(state, { ...ui, sportFilter: "Soccer" });
  assert.equal((html.match(/class="discover-community-row"/g) ?? []).length, 5);
  assert.match(html, /Show more/);
  assert.doesNotMatch(html, /community-cta|Can.t find your club/);
  assert.match(html, /href="#\/communities" data-action="open-community"/);
  const expanded = renderCommunities(state, { ...ui, sportFilter: "Soccer", showAllDiscover: true });
  assert.equal((expanded.match(/class="discover-community-row"/g) ?? []).length, 8);
  assert.match(expanded, /Show less/);
});

test("community discover shows public communities but keeps unjoined private communities out", () => {
  const state = JSON.parse(JSON.stringify(initialState));
  state.communities.push({ ...state.communities[0], id: "private-hidden", name: "Secret community", privacy: "Private", joined: false });
  const html = renderCommunities(state, { ...ui, sportFilter: "All" });
  assert.doesNotMatch(html, /Secret community|data-community="private-hidden"/);
  assert.match(html, /Request pending|Explore/);
});

test("community page shows linked news, a full post view, and stacked poll and matchday panels", () => {
  const state = JSON.parse(JSON.stringify(initialState));
  state.polls[0].communityId = "brooklyn";
  const post = state.posts.find((item) => item.communityId === "brooklyn");
  const list = renderCommunityFeed(state, ui, "brooklyn");
  assert.match(list, /class="community-news-list"/);
  assert.match(list, new RegExp(`data-post="${post.id}"`));
  assert.match(list, /Squad pulse/);
  assert.match(list, /Matchday/);
  assert.ok(list.indexOf("Squad pulse") < list.indexOf("Matchday"));
  const detail = renderCommunityFeed(state, ui, "brooklyn", post.id);
  assert.match(detail, new RegExp(`data-post-card="${post.id}"`));
  assert.doesNotMatch(detail, /class="community-news-list"/);
});

test("community page escapes community and post content", () => {
  assertSafeHTML(renderCommunityFeed(maliciousState(), ui, "brooklyn"), "community feed");
});

test("home community news is a link to its full community post", () => {
  const state = JSON.parse(JSON.stringify(initialState));
  const post = state.posts[0];
  const html = renderHome(state, ui);
  assert.match(html, new RegExp(`href="#/community/${post.communityId}/posts/${post.id}"`));
  assert.match(html, /class="feed-news-link"/);
});

test("home latest news filters by community and sorts by post creation time", () => {
  const state = JSON.parse(JSON.stringify(initialState));
  const communityId = state.communities.find((community) => community.joined).id;
  state.posts = [
    { ...state.posts[0], id: "home-news-old", communityId, createdAt: "2026-01-01T12:00:00Z", text: "Older update" },
    { ...state.posts[0], id: "home-news-new", communityId, createdAt: "2026-02-01T12:00:00Z", text: "Newer update" },
  ];
  const posts = state.posts;
  const html = renderHome(state, { ...ui, homeNewsCommunityId: "all", homeNewsSort: "oldest" });
  assert.match(html, /data-filter="home-news-community"/);
  assert.match(html, /data-filter="home-news-sort"/);
  assert.match(html, /class="home-news-feature"[^>]+data-post="home-news-old"/);
  const filtered = renderHome(state, { ...ui, homeNewsCommunityId: communityId, homeNewsSort: "newest" });
  assert.match(filtered, new RegExp(`data-community-selected="${communityId}"`));
  assert.match(filtered, /class="home-news-feature"[^>]+data-post="home-news-new"/);
});

test("poll rendering escapes malicious state and class tokens", () => {
  const state = maliciousState();
  assertSafeHTML(renderPolls(state, { ...ui, expandedPollCards: state.polls.map((poll) => poll.id) }), "polls");
});

test("featured poll hover keeps dark-card option text and background readable", () => {
  const styles = readFileSync(new URL("../styles/polls.css", import.meta.url), "utf8");
  const sharedHover = styles.indexOf(".poll-option:hover:not(:disabled)");
  const featuredHover = styles.indexOf(".poll-card--featured .poll-option:hover:not(:disabled)");
  assert.ok(featuredHover > sharedHover);
  assert.match(styles.slice(featuredHover, featuredHover + 250), /background:\s*rgba\(217,\s*255,\s*79,\s*0\.14\)/);
  assert.match(styles.slice(featuredHover, featuredHover + 250), /color:\s*var\(--paper\)/);
});

test("modal controls retain readable ink on light hover and focus surfaces", () => {
  const overlayStyles = readFileSync(new URL("../styles/overlays.css", import.meta.url), "utf8");
  const homeStyles = readFileSync(new URL("../styles/home.css", import.meta.url), "utf8");
  const baseStyles = readFileSync(new URL("../styles/base.css", import.meta.url), "utf8");
  assert.match(overlayStyles, /\.modal__body button:not\(\.btn--primary\)[\s\S]*?:hover:not\(:disabled\)[\s\S]*?color: var\(--ink\)/);
  assert.match(overlayStyles, /\.btn--danger-solid/);
  assert.match(homeStyles, /\.feed-poll-option:hover \{[^}]*background: var\(--white\);[^}]*color: var\(--ink\);/);
  assert.match(baseStyles, /\.icon-button--dark:hover[\s\S]*?background: var\(--forest-2\);[\s\S]*?color: var\(--lime\)/);
});

test("saving manually rearranged poll teams closes the dialog after the API accepts the update", () => {
  const app = readFileSync(new URL("../js/app.js", import.meta.url), "utf8");
  assert.match(app, /await api\.post\(`\/polls\/\$\{encodeURIComponent\(form\.dataset\.poll\)\}\/teams`, \{ team_a: teamA, team_b: teamB, floater \}\);\s*closeModal\(\);\s*await syncFromServer\(\);/);
});

test("poll cards start with two options and can expand the remaining options", () => {
  const state = JSON.parse(JSON.stringify(initialState));
  state.polls = [{ id: "many-options", communityId: state.communities[0].id, question: "Choose", category: "Pickup", author: "Coach", closesAt: new Date(Date.now() + 3600000).toISOString(), options: ["A", "B", "C", "D"].map((label, i) => ({ id: `option-${i}`, label, votes: 0 })), userVote: null }];
  const collapsed = renderPolls(state, { ...ui, pollTab: "active", pollFilter: "All", expandedPollCards: ["many-options"], expandedPollOptions: [] });
  assert.equal((collapsed.match(/class="poll-option(?:\s|\")/g) || []).length, 2);
  assert.match(collapsed, /More options · 2/);
  const expanded = renderPolls(state, { ...ui, pollTab: "active", pollFilter: "All", expandedPollCards: ["many-options"], expandedPollOptions: ["many-options"] });
  assert.equal((expanded.match(/class="poll-option(?:\s|\")/g) || []).length, 4);
});

test("poll cards show only the title until clicked open", () => {
  const state = JSON.parse(JSON.stringify(initialState));
  const html = renderPolls(state, { ...ui, pollTab: "active", pollFilter: "All", expandedPollCards: [] });
  const styles = readFileSync(new URL("../styles/polls.css", import.meta.url), "utf8");
  assert.match(html, /poll-card__title-toggle[^>]+aria-expanded="false"/);
  assert.match(html, /class="poll-card[^\"]*is-collapsed/);
  assert.match(styles, /\.poll-card\.is-collapsed > :not\(\.poll-card__title-toggle\) \{ display: none; \}/);
  const opened = renderPolls(state, { ...ui, pollTab: "active", pollFilter: "All", expandedPollCards: [state.polls[0].id] });
  assert.match(opened, /class="poll-card[^\"]*is-expanded/);
  assert.match(opened, /poll-card__title-toggle[^>]+aria-expanded="true"/);
  assert.match(opened, /data-action="vote-poll"/);
});

test("poll list shows at most four polls until Show more is selected", () => {
  const state = JSON.parse(JSON.stringify(initialState));
  const template = state.polls[0];
  state.polls = Array.from({ length: 7 }, (_, index) => ({ ...template, id: `visible-poll-${index}`, question: `Visible question ${index}`, options: template.options.map((option) => ({ ...option, id: `${option.id}-${index}` })) }));
  const collapsed = renderPolls(state, { ...ui, pollTab: "active", pollFilter: "All", pollsShowMore: false });
  assert.equal((collapsed.match(/<article class="poll-card/g) || []).length, 4);
  assert.match(collapsed, /Show more polls \(3\)/);
  const expanded = renderPolls(state, { ...ui, pollTab: "active", pollFilter: "All", pollsShowMore: true });
  assert.equal((expanded.match(/<article class="poll-card/g) || []).length, 7);
  assert.match(expanded, /Show fewer polls/);
});

test("team rendering escapes malicious state and class tokens", () => {
  assertSafeHTML(renderTeams(maliciousState(), ui), "teams");
});

test("Team Hub squad is capped at three cards per row and scrolls after three rows", () => {
  const css = readFileSync(new URL("../styles/teams.css", import.meta.url), "utf8");
  assert.match(css, /\.player-card-grid\s*\{[^}]*grid-template-columns:\s*repeat\(3,minmax\(0,1fr\)\);[^}]*grid-auto-rows:\s*280px;[^}]*max-height:\s*904px;[^}]*overflow-y:\s*auto/s);
  assert.match(css, /@media\s*\(max-width:\s*600px\)\s*\{\s*\.player-card-grid\s*\{[^}]*grid-template-columns:\s*repeat\(2,minmax\(0,1fr\)\)/s);
});

test("Team Hub schedule card stacks the matchup and lets venue text wrap", () => {
  const css = readFileSync(new URL("../styles/teams.css", import.meta.url), "utf8");
  assert.match(css, /\.next-match\s*\{[^}]*display:\s*grid;[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/s);
  assert.match(css, /\.next-match__date span\s*\{[^}]*overflow-wrap:\s*anywhere/s);
  assert.match(css, /\.next-match__teams\s*\{[^}]*justify-content:\s*center/s);
});

test("lineup rendering escapes malicious state and class tokens", () => {
  assertSafeHTML(renderTeams(maliciousState(), { ...ui, teamTab: "lineup" }), "lineup");
});

test("empty Starting XI plus slots open the registered player picker for admins", () => {
  const state = maliciousState();
  state.user.role = "Super Admin";
  state.teams[0].canManage = true;
  state.teams[0].startingXI = [];
  const html = renderTeams(state, { ...ui, teamTab: "lineup" });
  assert.match(html, /data-action="lineup-add-player"/);
  assert.match(html, /data-action="clear-lineup"/);
});

test("a null XI slot stays in place while later starters keep their positions", () => {
  const state = maliciousState();
  state.user.role = "Super Admin";
  state.teams[0].canManage = true;
  state.teams[0].startingXI = [...state.teams[0].startingXI];
  state.teams[0].startingXI[4] = null;
  const html = renderTeams(state, { ...ui, teamTab: "lineup" });
  assert.match(html, /pitch-player--empty[^>]*data-action="lineup-add-player"[^>]*data-slot="4"/);
  assert.ok(html.includes(`data-player="${state.teams[0].startingXI[5]}" data-slot="5"`));
});

test("plan rendering escapes malicious state and class tokens", () => {
  assertSafeHTML(renderPlans(maliciousState(), ui), "plans");
});

test("game plans show an editable 11-player board with auto-arrange and save controls", () => {
  const state = JSON.parse(JSON.stringify(initialState));
  state.user.role = "Super Admin";
  const selected = state.plans[0];
  const firstId = selected.board?.[0] ?? state.teams[0].startingXI[0];
  const first = state.teams[0].players.find((player) => player.id === firstId);
  first.name = "Kevin Ghale";
  const html = renderPlans(state, { ...ui, selectedPlanId: selected.id });
  assertSafeHTML(html, "game-plan-board");
  assert.equal((html.match(/data-plan-board-slot=/g) ?? []).length, 11);
  assert.match(html, /data-action="auto-plan-board"/);
  assert.match(html, /data-action="clear-plan-board"/);
  assert.match(html, /data-action="save-plan-board"/);
  assert.match(html, /data-plan-roster-player=/);
  assert.match(html, /role="tooltip"/);
  assert.match(html, /plan-player-stats--below/);
  assert.match(html, /data-action="edit-plan"/);
  const initials = first.name.trim().split(/\s+/).map((part) => part[0]).slice(0, 2).join("").toUpperCase();
  const tile = html.match(/<button class="plan-board__player"[\s\S]*?<\/button>/)?.[0] ?? "";
  assert.match(tile, new RegExp(`<strong>${initials}<\\/strong>`));
  assert.match(tile, new RegExp(`<span>${first.number}<\\/span>`));
});

test("game plan roster lists only bench players and updates after a bench player takes a position", () => {
  const state = JSON.parse(JSON.stringify(initialState));
  state.user.role = "Super Admin";
  const plan = state.plans[0];
  const team = state.teams.find((item) => item.communityId === plan.communityId) ?? state.teams[0];
  const board = plan.board?.length === 11 ? [...plan.board] : [...team.startingXI];
  const starters = new Set(board.filter(Boolean));
  const bench = team.players.filter((player) => !starters.has(player.id));
  const html = renderPlans(state, { ...ui, selectedPlanId: plan.id });
  assert.equal((html.match(/data-plan-roster-player=/g) ?? []).length, bench.length);
  for (const id of starters) assert.doesNotMatch(html, new RegExp(`data-plan-roster-player="${id}"`));
  if (!bench.length) return;
  const displaced = board[0];
  board[0] = bench[0].id;
  const updated = renderPlans(state, { ...ui, selectedPlanId: plan.id, planBoardPlanId: plan.id, planBoardDraft: board });
  assert.doesNotMatch(updated, new RegExp(`data-plan-roster-player="${bench[0].id}"`));
  assert.match(updated, new RegExp(`data-plan-roster-player="${displaced}"`));
});

test("game plan board preserves empty positions and pickup roster has a five-player scroll viewport", () => {
  const state = JSON.parse(JSON.stringify(initialState));
  state.user.role = "Super Admin";
  const draft = [...state.teams[0].startingXI];
  draft[3] = null;
  const html = renderPlans(state, { ...ui, selectedPlanId: state.plans[0].id, planBoardPlanId: state.plans[0].id, planBoardDraft: draft });
  assert.match(html, /class="plan-board__player is-empty"/);
  assert.match(html, /data-plan-board-slot="3"/);
  const css = readFileSync(new URL("../styles/pickup.css", import.meta.url), "utf8");
  assert.match(css, /\.pickup-rating-list\s*\{[^}]*max-height:\s*270px;[^}]*overflow-y:\s*auto/s);
  const planCss = readFileSync(new URL("../styles/plans.css", import.meta.url), "utf8");
  assert.match(planCss, /\.plan-board__player:hover \.plan-player-stats[^}]*transition-delay:\s*\.5s/s);
});

test("pickup rendering escapes malicious state and class tokens", () => {
  assertSafeHTML(renderPickup(maliciousState(), ui), "pickup");
});

test("pickup builder does not render a stray closing brace after the team split", () => {
  const html = renderPickup(JSON.parse(JSON.stringify(initialState)), ui);
  assert.doesNotMatch(html, /\}\s*<\/section>\s*<aside class="panel pickup-ratings/);
});

test("pickup builder uses only In poll players and keeps the saved poll team split", () => {
  const state = JSON.parse(JSON.stringify(initialState));
  const team = state.teams[0];
  const players = team.players.filter((player) => player.status !== "out").slice(0, 5);
  const split = { teamA: [players[0].id, players[1].id], teamB: [players[2].id, players[3].id], floater: players[4].id, gap: 0.5, positionGap: 1, balanceScore: 97, poolSize: 5, manual: true };
  state.polls = [{ id: "pickup-attendance", communityId: team.communityId, category: "Pickup", question: "Playing today?", yesPlayers: players.map((player) => ({ id: player.id, name: player.name, number: player.number, position: player.pos, pos: player.pos, group: player.group, rating: player.rating })), noCount: 2, guestCount: 0, autoTeams: split, canManageTeams: true }];
  const pool = getPickupPool(state, { pickupIncludeDoubtful: true });
  assert.deepEqual(new Set(pool.map((player) => player.id)), new Set(players.map((player) => player.id)));
  const result = getPickupResult(state, { pickupIncludeDoubtful: true, pickupPositionAware: true, pickupVariant: 0 });
  assert.deepEqual(result.teamA.players.map((player) => player.id), split.teamA);
  assert.deepEqual(result.teamB.players.map((player) => player.id), split.teamB);
  assert.equal(result.floater.id, split.floater);
});

test("pickup builder lets managers drag available non-poll squad members into a saved split", () => {
  const state = JSON.parse(JSON.stringify(initialState));
  const team = state.teams[0];
  state.user.role = "Super Admin";
  const participants = team.players.filter((player) => player.status !== "out").slice(0, 4);
  const extra = team.players.find((player) => player.status !== "out" && !participants.some((attendee) => attendee.id === player.id));
  const split = { teamA: [participants[0].id, participants[1].id], teamB: [participants[2].id, participants[3].id], floater: null, manual: true };
  state.polls = [{ id: "pickup-add-player", communityId: team.communityId, category: "Pickup", question: "Playing?", yesPlayers: participants.map((player) => ({ ...player })), autoTeams: split, canManageTeams: true }];
  const pool = getPickupPool(state, ui);
  assert.ok(!pool.some((player) => player.id === extra.id));
  const html = renderPickup(state, ui);
  assert.match(html, new RegExp(`data-pickup-squad-player="${extra.id}"`));
  assert.match(html, /data-pickup-builder-zone="teamA"/);
  assert.match(html, /data-pickup-builder-zone="teamB"/);
  state.polls[0].autoTeams.teamA.push(extra.id);
  assert.ok(getPickupPool(state, ui).some((player) => player.id === extra.id));
  assert.ok(getPickupResult(state, ui).teamA.players.some((player) => player.id === extra.id));
});

test("pickup builder manual split keeps every attendee on equal teams with one floater", () => {
  const state = JSON.parse(JSON.stringify(initialState));
  const team = state.teams[0];
  const players = team.players.filter((player) => player.status !== "out").slice(0, 5);
  state.polls = [{ id: "pickup-manual", communityId: team.communityId, category: "Pickup", question: "Playing?", yesPlayers: players.map((player) => ({ ...player, position: player.pos })), noCount: 0 }];
  const manual = { teamA: [players[0].id, players[1].id], teamB: [players[2].id, players[3].id], floater: players[4].id, teamNames: ["Yolo Green", "Yolo Yellow"] };
  const result = getPickupResult(state, { pickupIncludeDoubtful: true, pickupPositionAware: true, pickupVariant: 3, pickupManualSplit: manual });
  assert.equal(result.teamA.players.length, 2);
  assert.equal(result.teamB.players.length, 2);
  assert.equal(result.floater.id, players[4].id);
  assert.deepEqual(new Set([...result.teamA.players, ...result.teamB.players, result.floater].map((player) => player.id)), new Set(players.map((player) => player.id)));
  assert.deepEqual(result.teamNames, manual.teamNames);
  assert.match(renderPickup(state, { pickupIncludeDoubtful: true, pickupPositionAware: true, pickupVariant: 3 }), /edit-pickup-builder-teams/);
});

test("pickup builder allows an odd manual split without using a floater", () => {
  const state = JSON.parse(JSON.stringify(initialState));
  const team = state.teams[0];
  const players = team.players.filter((player) => player.status !== "out").slice(0, 5);
  state.polls = [{ id: "pickup-manual-no-floater", communityId: team.communityId, category: "Pickup", question: "Playing?", yesPlayers: players.map((player) => ({ ...player, position: player.pos })), noCount: 0 }];
  const manual = { teamA: players.slice(0, 3).map((player) => player.id), teamB: players.slice(3).map((player) => player.id), floater: null };
  const result = getPickupResult(state, { pickupIncludeDoubtful: true, pickupPositionAware: true, pickupVariant: 4, pickupManualSplit: manual });
  assert.equal(result.teamA.players.length, 3);
  assert.equal(result.teamB.players.length, 2);
  assert.equal(result.floater, null);
  assert.equal(new Set([...result.teamA.players, ...result.teamB.players].map((player) => player.id)).size, players.length);
});

test("Pickup poll has a dedicated start-time input and saves it into the game timestamp", () => {
  const pollView = readFileSync(new URL("../js/views/polls.js", import.meta.url), "utf8");
  const app = readFileSync(new URL("../js/app.js", import.meta.url), "utf8");
  assert.match(pollView, /name="gameTime" type="time"/);
  assert.match(pollView, /name="gameDate" type="date"/);
  assert.match(pollView, /value="Pickup" selected/);
  assert.match(pollView, /name="location" type="text"/);
  assert.match(app, /new Date\(`\$\{values\.gameDate\}T\$\{values\.gameTime\}`\)/);
  assert.match(app, /game_at: gameAt\.toISOString\(\)/);
  assert.match(app, /player\.name\.trim\(\)\.toLocaleLowerCase\(\) === state\.user\.name\.trim\(\)\.toLocaleLowerCase\(\)/);
});

test("SQL injection strings are rendered as text, not evaluated", () => {
  const state = maliciousState();
  const html = renderHome(state, ui);
  assert.ok(html.includes("&#039; OR 1=1 --"));
});

test("home renders safely for a team with no fixtures", () => {
  const state = JSON.parse(JSON.stringify(initialState));
  state.nextFixtures = [];
  const html = renderHome(state, ui);
  assert.ok(html.includes("No fixtures have been added yet."));
});

import { renderPlayerProfile } from "../js/views/player.js";

test("player profile renders with clean data", () => {
  const html = renderPlayerProfile(initialState, ui, initialState.teams[0].players[0].id);
  assert.ok(html.length > 400, "player profile should render content");
});

test("player profile escapes all malicious fields", () => {
  const state = maliciousState();
  const player = state.teams[0].players[0];
  player.bio = `${tagPayload} ' OR 1=1 --`;
  player.dateOfBirth = attrPayload;
  player.heightCm = tagPayload;
  player.foot = attrPayload;
  assertSafeHTML(renderPlayerProfile(state, ui, player.id), "player-profile");
});

test("player profile gracefully handles unknown player id", () => {
  const html = renderPlayerProfile(initialState, ui, "does-not-exist");
  assert.ok(html.includes("can’t find") || html.includes("can't find") || html.includes("not find"), "should show a not-found state");
  assert.ok(!html.includes("<script"), "not-found state must not emit scripts");
});

test("player profile renders stat bars and position pitch", () => {
  const player = initialState.teams[0].players.find((p) => p.pos === "GK");
  const html = renderPlayerProfile(initialState, ui, player.id);
  assert.ok(html.includes("pp-bar"), "should include stat bars");
  assert.ok(html.includes("pp-pitch"), "should include pitch map");
  assert.ok(html.includes("Saves"), "goalkeeper should see the saves row");
  assert.ok(html.includes("Goalkeeping"), "goalkeeper should see goalkeeping section");
});

test("player-stats module: derivedStats, squadBenchmark, playerHighlights", async () => {
  const { derivedStats, squadBenchmark, playerHighlights } = await import("../js/player-stats.js");
  const players = initialState.teams[0].players;
  const top = players.reduce((best, p) => p.goals > best.goals ? p : best, players[0]);
  const bench = squadBenchmark(players, "goals");
  assert.equal(bench.max, top.goals);
  assert.ok(bench.leaders.includes(top.id));
  assert.ok(bench.average < bench.max);
  const highlights = playerHighlights(players, top);
  assert.ok(highlights.includes("Top scorer"), "top scorer badge missing");
  const derived = derivedStats(players[0]);
  assert.ok("goalsPerGame" in derived && "cleanSheetRate" in derived);
});

import { renderCalendar, newDutyFormHTML } from "../js/views/calendar.js";

function calendarState() {
  const state = maliciousState();
  state.user.canManageTeam = false;
  state.duties = [
    {
      id: "duty-evil-1",
      kind: "coffee",
      kindLabel: "Coffee",
      title: tagPayload,
      startsAt: new Date(Date.now() + 26 * 3_600_000).toISOString(),
      note: `${scriptPayload} ${attrPayload}`,
      eventKey: attrPayload,
      claimedBy: { id: "someone-else", name: tagPayload, initials: "XX", tone: attrPayload },
      claimedAt: new Date().toISOString(),
      createdById: "someone-else",
    },
    {
      id: "duty-evil-2",
      kind: "donuts",
      kindLabel: "Donuts",
      title: `${tagPayload} ${attrPayload}`,
      startsAt: new Date(Date.now() + 50 * 3_600_000).toISOString(),
      note: scriptPayload,
      eventKey: null,
      claimedBy: null,
      claimedAt: null,
      createdById: state.user.id,
    },
  ];
  return state;
}

const calendarUi = () => ({
  calendarMonth: null,
  calendarDay: new Date(Date.now() + 26 * 3_600_000).toISOString().slice(0, 10),
  lineupSelected: null,
});

test("calendar renders hostile duty titles, notes and claimer names escaped", () => {
  const state = calendarState();
  const ui = calendarUi();
  const html = renderCalendar(state, ui);
  assertSafeHTML(html, "calendar");
  assert.ok(html.includes("cal-open"), "help-wanted section rendered");
});

test("calendar day panel escapes duty content for the selected day", () => {
  const state = calendarState();
  const ui = calendarUi();
  ui.calendarMonth = ui.calendarDay.slice(0, 7);
  const html = renderCalendar(state, ui);
  assert.ok(html.includes("&lt;img") || html.includes("&lt;script"), "payload is shown as text");
  assertSafeHTML(html, "calendar-day-panel");
});

test("calendar still renders with no duties and with an empty squad", () => {
  const state = maliciousState();
  state.duties = [];
  const html = renderCalendar(state, calendarUi());
  assert.ok(html.includes("Nothing on this day") || html.includes("cal-grid"));
  assertSafeHTML(html, "calendar-empty");
});

test("add-duty form escapes fixture names and ids", () => {
  const state = maliciousState();
  state.nextFixtures[0].opponent = tagPayload;
  state.nextFixtures[0].id = `fixture-${attrPayload}`;
  const html = newDutyFormHTML(state, state.nextFixtures[0].date.slice(0, 10));
  assertSafeHTML(html, "new-duty-form");
  assert.ok(!html.includes(tagPayload), "raw payload must not appear");
});

test("duty form supports batch entries, only voted upcoming community polls, and member assignment", () => {
  const state = calendarState();
  const communityId = state.communities[0].id;
  const future = new Date(Date.now() + 48 * 3_600_000).toISOString();
  state.user.id = "member-1";
  state.user.role = "Member";
  state.dutyCommunityId = communityId;
  state.dutyMembers = [{ id: "member-1", name: "Me" }, { id: "member-2", name: "Other" }];
  state.dutyCanAssignOthers = false;
  state.polls = [
    { id: "poll-voted", communityId, category: "Pickup", question: "Pickup match", gameAt: future, voteCount: 2 },
    { id: "poll-empty", communityId, category: "Competition", question: "Empty poll", gameAt: future, voteCount: 0 },
    { id: "poll-other", communityId: "different-community", category: "Pickup", question: "Other club", gameAt: future, voteCount: 4 },
  ];
  const html = newDutyFormHTML(state);
  assertSafeHTML(html, "duty-form-batch-assignment");
  assert.match(html, /data-action="add-duty-item"/);
  assert.equal((html.match(/data-duty-entry/g) ?? []).length, 1, "one form creates one duty record");
  assert.match(html, /data-duty-kind/);
  assert.equal((html.match(/data-action="select-duty-kind"/g) ?? []).length, 5, "each item has five compact visual choices");
  assert.doesNotMatch(html, /<select data-duty-kind/);
  assert.match(html, /data-start-at=/);
  assert.match(html, /poll-voted/);
  assert.doesNotMatch(html, /poll-empty|poll-other/);
  assert.match(html, /Assign to member/);
  assert.match(html, /disabled>Other/);
  const calendarCss = readFileSync(new URL("../styles/calendar.css", import.meta.url), "utf8");
  assert.match(calendarCss, /\.duty-entry\s*\{[^}]*flex-direction:\s*column;[^}]*gap:\s*14px;/s);
});
