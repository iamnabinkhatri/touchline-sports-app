import { icon } from "../icons.js";
import { planProgress, pollPercent, pollTotal } from "../store.js";
import {
  avatar,
  countLabel,
  crest,
  emptyState,
  openModal,
  safeImageData,
  voteIcon,
} from "../ui.js";
import {
  closingLabel,
  countdownParts,
  escapeHTML,
  finiteNumber,
  formatDate,
  formatTime,
  greeting,
  isOpen,
  pad,
  safeToken,
} from "../utils.js";

const TACTIC_DOTS = [
  { x: 50, y: 88, tone: "muted" },
  { x: 24, y: 72, tone: "muted" },
  { x: 42, y: 76, tone: "muted" },
  { x: 58, y: 76, tone: "muted" },
  { x: 76, y: 72, tone: "muted" },
  { x: 34, y: 50, tone: "away" },
  { x: 52, y: 56, tone: "away" },
  { x: 70, y: 48, tone: "away" },
  { x: 20, y: 28, tone: "lime" },
  { x: 40, y: 22, tone: "lime" },
  { x: 60, y: 18, tone: "lime" },
  { x: 82, y: 26, tone: "lime" },
];

export function renderHome(state, ui) {
  if (!state.teams?.length) {
    return `<div class="page page--home">
      <header class="page-head reveal"><div class="page-head__copy">
        <p class="eyebrow"><span class="eyebrow__line"></span>Clubhouse setup</p>
        <h1>Start with your club.</h1>
        <p class="page-subtitle">Your workspace is empty. Add your club or create a community, then fill in its details from the clubhouse.</p>
      </div></header>
      <section class="panel onboarding-panel reveal reveal--delay-1">
        <div><p class="eyebrow">First steps</p><h2>What would you like to add?</h2>
          <p>Create a club team to manage a roster, or start a community for your members. You can add the rest of your information from the existing screens.</p>
        </div>
        <div class="page-head__actions">
          <button class="btn btn--primary" type="button" data-action="new-team">${icon("team", 17)} Add a club team</button>
          <button class="btn btn--ghost" type="button" data-action="new-community">${icon("users", 17)} Add a community</button>
        </div>
      </section>
      ${renderHomeCommunityNews(state, ui)}
    </div>`;
  }
  const team = state.teams[0];
  const fixture = state.nextFixtures[0];
  if (!fixture) {
    return `<div class="page page--home"><header class="page-head"><div class="page-head__copy">
      <p class="eyebrow">${escapeHTML(team.name)} · Clubhouse</p><h1>Welcome, ${escapeHTML(state.user.name.split(" ")[0])}.</h1>
      <p class="page-subtitle">Your club is set up. Create a community for your members, then add posts and schedule details when ready.</p></div>
      <div class="page-head__actions">${state.communities?.length ? `<button class="btn btn--primary" type="button" data-action="new-post">${icon("plus", 17)} New post</button>` : ""}<button class="btn btn--ghost" type="button" data-action="new-community">${icon("users", 17)} Add community</button></div></header>
      <section class="panel onboarding-panel"><div><p class="eyebrow">Next step</p><h2>No fixtures have been added yet.</h2><p>Add players in Team Hub or create a game plan when you are ready.</p></div><div class="page-head__actions"><a class="btn btn--ghost" href="#/teams">Open Team Hub</a><button class="btn btn--primary" type="button" data-action="new-plan">Create a game plan</button></div></section>
      ${renderHomeCommunityNews(state, ui)}
    </div>`;
  }
  const fixtureHomeTeam = fixture.homeAway === "Away" ? fixture.opponent : team.name;
  const fixtureAwayTeam = fixture.homeAway === "Away" ? team.name : fixture.opponent;
  const activePlan = state.plans.find((plan) => plan.id === ui.selectedPlanId) ?? state.plans[0];
  if (!activePlan) return `<div class="page page--home"><header class="page-head"><div class="page-head__copy"><p class="eyebrow">${escapeHTML(team.name)} · Clubhouse</p><h1>Your first fixture is ready.</h1><p class="page-subtitle">Create a game plan to start filling in the matchday details.</p></div><div class="page-head__actions"><a class="btn btn--primary" href="#/plans">Open game plans</a></div></header>${renderHomeCommunityNews(state, ui)}</div>`;
  const activePolls = state.polls.filter((poll) => isOpen(poll.closesAt));
  const filteredPosts = filterPosts(state, ui.homeTab, ui.communityFilterId);
  const activeCommunity = ui.communityFilterId
    ? state.communities.find((community) => community.id === ui.communityFilterId)
    : null;
  const countdown = countdownParts(fixture.date);

  return `<div class="page page--home">
    <header class="page-head reveal">
      <div class="page-head__copy">
        <p class="eyebrow"><span class="eyebrow__line"></span>${formatDate(new Date(), { weekday: "long" })} · Clubhouse</p>
        <h1>${escapeHTML(greeting(state.user.name.split(" ")[0]))}</h1>
        <p class="page-subtitle">Matchday is close. Here’s what’s moving around the club.</p>
      </div>
      <div class="page-head__actions">
        <button class="btn btn--ghost" type="button" data-action="new-poll">${icon("poll", 17)} Start a poll</button>
        <button class="btn btn--primary" type="button" data-action="new-post">${icon("plus", 17)} New post</button>
      </div>
    </header>

    <article class="match-hero reveal reveal--delay-1" aria-labelledby="next-fixture-title">
      <div class="match-hero__grain"></div>
      <div class="match-hero__content">
        <div class="hero-kicker"><span class="live-dot"></span> Next fixture <span class="hero-kicker__divider"></span> ${escapeHTML(fixture.competition)}</div>
        <h2 id="next-fixture-title">${escapeHTML(fixtureHomeTeam)} <span class="hero-vs">vs</span> ${escapeHTML(fixtureAwayTeam)}</h2>
        <div class="hero-meta">
          <span>${icon("calendar", 15)}${escapeHTML(formatDate(fixture.date))}</span>
          <span>${icon("clock", 15)}${escapeHTML(formatTime(fixture.date))} kick-off</span>
          <span>${icon("location", 15)}${escapeHTML(fixture.venue)}</span>
        </div>
        <div class="hero-actions">
          <a class="btn btn--lime" href="#/plans" data-action="view-plan" data-plan="${escapeHTML(activePlan.id)}">${icon("clipboard", 17)} Open game plan</a>
          <a class="btn btn--ghost-light" href="#/teams">${icon("team", 17)} Team sheet</a>
        </div>
      </div>
      <div class="match-ticket" aria-label="Match countdown">
        <div class="match-ticket__top">
          <span>${escapeHTML(fixture.homeAway)} day</span>
          <strong>${pad(new Date(fixture.date).getDate())}</strong>
        </div>
        <div class="match-ticket__teams">
          <div class="ticket-team">
            ${crest(fixtureHomeTeam === team.name ? team.mark : fixture.opponentMark || "FC", "forest", "lg", fixtureHomeTeam)}
            <small>${escapeHTML(fixtureHomeTeam)}</small>
          </div>
          <span class="ticket-vs">VS</span>
          <div class="ticket-team">
            ${crest(fixtureAwayTeam === team.name ? team.mark : fixture.opponentMark || "FC", "coral", "lg", fixtureAwayTeam)}
            <small>${escapeHTML(fixtureAwayTeam)}</small>
          </div>
        </div>
        <div class="ticket-countdown">
          <div><strong>${countdown.days}</strong><span>days</span></div>
          <i>:</i>
          <div><strong>${pad(countdown.hours)}</strong><span>hrs</span></div>
          <i>:</i>
          <div><strong>${pad(countdown.minutes)}</strong><span>min</span></div>
        </div>
        <div class="match-ticket__foot">${icon("pin", 13)} ${escapeHTML(fixture.venue)} · ${escapeHTML(fixture.competition)}</div>
      </div>
      <span class="match-hero__number" aria-hidden="true">${pad(new Date(fixture.date).getDate())}</span>
    </article>

    <div class="home-grid">
      <section class="feed reveal reveal--delay-2" aria-labelledby="feed-title">
        <div class="feed-head">
          <div>
            <p class="eyebrow">Your feed</p>
            <h2 id="feed-title">From the clubhouse</h2>
          </div>
          <a class="text-link" href="#/communities">All communities ${icon("arrowRight", 15)}</a>
        </div>

        <div class="composer">
          ${avatar(state.user.name, { size: "md", tone: "forest" })}
          <button class="composer__prompt" type="button" data-action="new-post">
            Share something with the squad…
          </button>
          <div class="composer__tools">
            <button class="composer-tool" type="button" data-action="new-poll" title="Create a poll" aria-label="Create a poll">${icon("poll", 18)}</button>
            <button class="composer-tool" type="button" data-action="new-plan" title="Create a game plan" aria-label="Create a game plan">${icon("clipboard", 18)}</button>
          </div>
        </div>

        <div class="feed-tabs" role="tablist" aria-label="Filter clubhouse feed">
          ${[
            ["for-you", "For you"],
            ["matchday", "Matchday"],
            ["tactics", "Tactics"],
          ]
            .map(
              ([value, label]) => `<button class="feed-tab${ui.homeTab === value ? " is-active" : ""}" type="button" role="tab" aria-selected="${ui.homeTab === value}" data-action="home-tab" data-tab="${value}">${label}</button>`,
            )
            .join("")}
          <span class="feed-tabs__spacer"></span>
          ${activeCommunity ? `<button class="active-filter" type="button" data-action="clear-community-filter">${icon("users", 12)} ${escapeHTML(activeCommunity.name)} ${icon("close", 11)}</button>` : ""}
          <span class="feed-tabs__meta">${filteredPosts.length} updates</span>
        </div>

        <div class="post-list">
          ${
            filteredPosts.length
              ? filteredPosts.map((post) => renderPostNewsLink(state, post)).join("")
              : emptyState({
                  iconName: "message",
                  title: "Nothing here yet",
                  text: "No updates match this filter. Start the conversation with a new post.",
                  action: `<button class="btn btn--primary btn--sm" type="button" data-action="new-post">${icon("plus", 15)} New post</button>`,
                })
          }
        </div>
      </section>

      <aside class="rail reveal reveal--delay-3" aria-label="Club shortcuts">
        <section class="rail-card rail-card--fixture">
          <div class="rail-card__head">
            <span class="eyebrow">Next up</span>
            <a class="text-link text-link--small" href="#/plans">Plan ${icon("arrowRight", 13)}</a>
          </div>
          <div class="rail-fixture">
            <div class="rail-fixture__teams">
              ${crest(fixture.opponentMark || "FC", "coral", "sm", fixture.opponent)}
              <div>
                <strong>${escapeHTML(fixture.opponent)}</strong>
                <span>Away · ${escapeHTML(fixture.venue)}</span>
              </div>
            </div>
            <div class="rail-fixture__date">
              <strong>${formatDate(fixture.date)}</strong>
              <span>${formatTime(fixture.date)}</span>
            </div>
          </div>
          <div class="rail-progress">
            <div>
              <span>Game plan</span>
              <strong>${planProgress(activePlan)}% ready</strong>
            </div>
            <div class="progress-track"><span style="width:${planProgress(activePlan)}%"></span></div>
          </div>
          <a class="button-row" href="#/plans" data-action="view-plan" data-plan="${escapeHTML(activePlan.id)}">
            <span>${icon("clipboard", 17)} Review the plan</span>
            ${icon("chevronRight", 16)}
          </a>
        </section>

        <section class="rail-card">
          <div class="rail-card__head">
            <span class="eyebrow">Squad pulse</span>
            <a class="text-link text-link--small" href="#/polls">${activePolls.length} open ${icon("arrowRight", 13)}</a>
          </div>
          <div class="rail-polls">
            ${activePolls
              .slice(0, 2)
              .map((poll) => {
                const total = pollTotal(poll);
                const leader = [...poll.options].sort((a, b) => b.votes - a.votes)[0];
                return `<a class="rail-poll" href="#/polls" data-action="view-poll" data-poll="${escapeHTML(poll.id)}">
                  <span class="tag tag--${safeToken(poll.category.toLowerCase(), ["lineup", "tactics", "club"], "club")}">${escapeHTML(poll.category)}</span>
                  <strong>${escapeHTML(poll.question)}</strong>
                  <span class="rail-poll__meta">${countLabel(total)} votes · ${escapeHTML(closingLabel(poll.closesAt))}</span>
                  <span class="rail-poll__bar"><span style="width:${pollPercent(leader, poll)}%"></span></span>
                </a>`;
              })
              .join("")}
          </div>
        </section>

        <section class="rail-card">
          <div class="rail-card__head">
            <span class="eyebrow">Club leaders</span>
            <span class="mini-badge">${icon("trophy", 12)} Top 3</span>
          </div>
          <div class="leader-list">
            ${state.leaders
              .map(
                (leader, index) => `<div class="leader">
                  <span class="leader__rank">0${index + 1}</span>
                  ${avatar(leader.name, { size: "sm", tone: leader.tone })}
                  <div class="leader__copy">
                    <strong>${escapeHTML(leader.name)}</strong>
                    <span>${escapeHTML(leader.label)}</span>
                  </div>
                  <span class="leader__points">${finiteNumber(leader.points)}<small>pts</small></span>
                </div>`,
              )
              .join("")}
          </div>
          <div class="rail-card__foot">
            ${avatar(state.user.name, { size: "xs", tone: "forest", className: "avatar--you" })}
            <span>You’re <strong>#7</strong> this month</span>
            <span class="points-chip">620 pts</span>
          </div>
        </section>

        <section class="rail-card rail-card--schedule">
          <div class="rail-card__head">
            <span class="eyebrow">On the calendar</span>
            <a class="text-link text-link--small" href="#/teams">Team ${icon("arrowRight", 13)}</a>
          </div>
          <div class="schedule-list">
            ${state.schedule
              .map(
                (event) => `<div class="schedule-item">
                  <span class="schedule-item__date">
                    <strong>${formatDate(event.date, { weekday: "short", month: "short", day: "numeric" }).split(", ")[1]}</strong>
                    <small>${new Date(event.date).toLocaleDateString("en-US", { weekday: "short" })}</small>
                  </span>
                  <span class="schedule-item__dot schedule-item__dot--${safeToken(event.accent, ["lime", "sky", "coral"], "sky")}"></span>
                  <div class="schedule-item__copy">
                    <strong>${escapeHTML(event.title)}</strong>
                    <span>${escapeHTML(event.detail)}</span>
                  </div>
                </div>`,
              )
              .join("")}
          </div>
        </section>
      </aside>
    </div>
    ${renderHomeCommunityNews(state, ui)}
  </div>`;
}

function filterPosts(state, tab, communityId = null) {
  return state.posts.filter((post) => {
    if (communityId && post.communityId !== communityId) return false;
    if (!state.communities.some((community) => community.id === post.communityId && community.joined)) return false;
    if (tab === "matchday") return post.tags.includes("matchday");
    if (tab === "tactics") return post.tags.includes("tactics");
    return true;
  });
}

function renderHomeCommunityNews(state, ui = {}) {
  const communities = state.communities.filter((community) => community.joined);
  const selectedCommunity = ui.homeNewsCommunityId || "all";
  const sort = ui.homeNewsSort === "oldest" ? "oldest" : "newest";
  const direction = sort === "oldest" ? 1 : -1;
  const posts = state.posts
    .filter((post) => communities.some((community) => community.id === post.communityId))
    .filter((post) => selectedCommunity === "all" || post.communityId === selectedCommunity)
    .sort((a, b) => direction * ((Date.parse(a.createdAt || "") || 0) - (Date.parse(b.createdAt || "") || 0)))
    .slice(0, 8);
  const featured = posts[0];
  const featuredCommunity = communities.find((community) => community.id === featured?.communityId);
  const featuredTitle = featured ? String(featured.text ?? "").trim().split(/\n|(?<=[.!?])\s/)[0] || "Community update" : "";
  return `<section class="home-community-news"><div class="feed-head"><div><p class="eyebrow">From your communities</p><h2>Latest news</h2></div><a class="text-link" href="#/communities">All communities ${icon("arrowRight", 15)}</a></div>
    <div class="community-news-toolbar"><label><span>Community</span><select data-filter="home-news-community" data-community-selected="${escapeHTML(selectedCommunity)}"><option value="all"${selectedCommunity === "all" ? " selected" : ""}>All communities</option>${communities.map((community) => `<option value="${escapeHTML(community.id)}"${selectedCommunity === community.id ? " selected" : ""}>${escapeHTML(community.name)}</option>`).join("")}</select></label><label><span>Timeline</span><select data-filter="home-news-sort"><option value="newest"${sort === "newest" ? " selected" : ""}>Newest first · descending</option><option value="oldest"${sort === "oldest" ? " selected" : ""}>Oldest first · ascending</option></select></label><span class="community-news-count">${posts.length} ${posts.length === 1 ? "update" : "updates"}</span></div>
    <div class="community-news-list">${featured ? `<a class="home-news-feature" href="#/community/${encodeURIComponent(featured.communityId)}/posts/${encodeURIComponent(featured.id)}" data-action="open-post" data-community="${escapeHTML(featured.communityId)}" data-post="${escapeHTML(featured.id)}"><span class="home-news-feature__label">${sort === "newest" ? "Latest update" : "Earlier update"} · ${escapeHTML(featuredCommunity?.name ?? "Community")}</span><strong>${escapeHTML(featuredTitle)}</strong><span>${escapeHTML(featured.text)}</span><small>${escapeHTML(featured.author)} · ${escapeHTML(featured.timeLabel)}</small></a>${posts.slice(1).map((post) => renderPostNewsLink(state, post)).join("")}` : `<p class="community-glimpse-empty">No community updates match this filter yet. Create a post to get the conversation started.</p>`}</div></section>`;
}

export function renderPost(state, post, ui) {
  const community = state.communities.find((item) => item.id === post.communityId);
  const commentsOpen = ui.openComments.includes(post.id);
  const canDelete = post.authorId === state.user.id || community?.canManage || state.user.role === "Super Admin";
  return `<article class="post" data-post-card="${escapeHTML(post.id)}">
    <header class="post__head">
      ${avatar(post.author, { size: "md", tone: post.authorTone })}
      <div class="post__identity">
        <div class="post__name-row">
          <strong>${escapeHTML(post.author)}</strong>
          <span class="post__role">${escapeHTML(post.authorRole)}</span>
        </div>
        <div class="post__meta">
          <span>${escapeHTML(community?.name ?? "Clubhouse")}</span>
          <span class="dot-sep"></span>
          <span>${escapeHTML(post.timeLabel)}</span>
          ${community?.kind === "Club" ? `<span class="mini-badge mini-badge--club">${icon("team", 11)} Club</span>` : ""}
        </div>
      </div>
      <div class="post__head-actions">${canDelete ? `<button class="post-delete-button" type="button" data-action="delete-post" data-post="${escapeHTML(post.id)}" aria-label="Delete post">Delete</button>` : ""}<button class="icon-button icon-button--quiet" type="button" data-action="share-post" data-post="${escapeHTML(post.id)}" aria-label="Share post">${icon("share", 17)}</button></div>
    </header>
    <p class="post__text">${escapeHTML(post.text)}</p>
    ${post.media ? renderMedia(state, post, ui) : ""}
    <footer class="post__footer">
      <div class="post__actions">
        <button class="post-action${post.liked ? " is-liked" : ""}" type="button" data-action="like-post" data-post="${escapeHTML(post.id)}" aria-pressed="${post.liked}" aria-label="${post.liked ? "Unlike" : "Like"} post">
          ${icon("heart", 18, post.liked ? "icon--filled" : "")}<span>${finiteNumber(post.likes)}</span>
        </button>
        <button class="post-action${commentsOpen ? " is-active" : ""}" type="button" data-action="toggle-comments" data-post="${escapeHTML(post.id)}" aria-expanded="${commentsOpen}" aria-label="Show comments">
          ${icon("message", 17)}<span>${post.comments.length || "Comment"}</span>
        </button>
        <button class="post-action" type="button" data-action="share-post" data-post="${escapeHTML(post.id)}" aria-label="Share post">
          ${icon("share", 16)}<span>Share</span>
        </button>
      </div>
      <span class="post__community">${icon("users", 13)} ${countLabel(community?.memberCount ?? 0)} members</span>
    </footer>
    ${
      commentsOpen
        ? `<div class="comments">
            ${
              post.comments.length
                ? post.comments
                    .map(
                      (comment) => `<div class="comment">
                        ${avatar(comment.author, { size: "xs", tone: comment.tone })}
                        <div class="comment__body">
                          <div class="comment__top"><strong>${escapeHTML(comment.author)}</strong><span>${escapeHTML(comment.time)}</span></div>
                          <p>${escapeHTML(comment.text)}</p>
                        </div>
                      </div>`,
                    )
                    .join("")
                : `<p class="comments__empty">No comments yet. Be the first to weigh in.</p>`
            }
            <form class="comment-form" data-form="add-comment" data-post="${escapeHTML(post.id)}">
              ${avatar(state.user.name, { size: "xs", tone: "forest" })}
              <input name="comment" type="text" placeholder="Add a comment…" aria-label="Add a comment" autocomplete="off" required maxlength="220">
              <button class="icon-button icon-button--send" type="submit" aria-label="Post comment">${icon("send", 15)}</button>
            </form>
          </div>`
        : ""
    }
  </article>`;
}

function renderPostNewsLink(state, post) {
  const community = state.communities.find((item) => item.id === post.communityId);
  const title = String(post.text ?? "").trim().split(/\n|(?<=[.!?])\s/)[0] || "Community update";
  const excerpt = String(post.text ?? "").trim().replace(/\s+/g, " ");
  return `<a class="feed-news-link" href="#/community/${encodeURIComponent(post.communityId)}/posts/${encodeURIComponent(post.id)}" data-action="open-post" data-community="${escapeHTML(post.communityId)}" data-post="${escapeHTML(post.id)}">
    <span class="feed-news-link__icon">${icon("message", 18)}</span>
    <span class="feed-news-link__copy"><small>${escapeHTML(community?.name ?? "Community")} · ${escapeHTML(post.author)} · ${escapeHTML(post.timeLabel)}</small><strong>${escapeHTML(title)}</strong><span>${escapeHTML(excerpt)}</span></span>
    ${icon("arrowRight", 16)}
  </a>`;
}

function renderMedia(state, post, ui) {
  if (post.media.type === "image") {
    const imageData = safeImageData(post.media.data ?? post.media.imageData);
    if (!imageData) return "";
    const community = state.communities.find((item) => item.id === post.communityId);
    return `<figure class="post-banner"><img src="${escapeHTML(imageData)}" alt="${escapeHTML(community?.name ?? "Community")} post photo" loading="lazy"><figcaption>${escapeHTML(community?.name ?? "Community")} · Community photo</figcaption></figure>`;
  }
  if (post.media.type === "score") {
    return `<div class="score-media">
      <div class="score-media__label"><span>${escapeHTML(post.media.competition)}</span><span class="score-media__live">FT</span></div>
      <div class="score-media__board">
        <div class="score-team score-team--home">
          <span class="crest crest--forest crest--sm"><span>${escapeHTML(post.media.home)}</span></span>
          <strong>Brooklyn</strong>
        </div>
        <div class="score-digits"><strong>${finiteNumber(post.media.homeScore)}</strong><span>—</span><strong>${finiteNumber(post.media.awayScore)}</strong></div>
        <div class="score-team score-team--away">
          <span class="crest crest--coral crest--sm"><span>${escapeHTML(post.media.away)}</span></span>
          <strong>Queens</strong>
        </div>
      </div>
      <div class="score-media__scorers">${post.media.scorers.map((scorer) => `<span>${icon("ball", 12)}${escapeHTML(scorer)}</span>`).join("")}</div>
      <div class="score-media__note">${escapeHTML(post.media.note)}</div>
    </div>`;
  }

  if (post.media.type === "tactics") {
    return `<div class="tactics-media">
      <div class="mini-pitch">
        <span class="mini-pitch__half"></span>
        <span class="mini-pitch__circle"></span>
        <span class="mini-pitch__box mini-pitch__box--top"></span>
        <span class="mini-pitch__box mini-pitch__box--bottom"></span>
        ${TACTIC_DOTS.map(
          (dot) =>
            `<span class="tactics-dot tactics-dot--${dot.tone}" style="left:${dot.x}%;top:${dot.y}%"></span>`,
        ).join("")}
      </div>
      <div class="tactics-media__copy">
        <span class="tag tag--tactics">${icon("layers", 12)} Shape study</span>
        <h3>${escapeHTML(post.media.title)}</h3>
        <p>${escapeHTML(post.media.note)}</p>
        <span class="tactics-media__formation">${escapeHTML(post.media.formation)}</span>
      </div>
    </div>`;
  }

  if (post.media.type === "poll") {
    const poll = state.polls.find((item) => item.id === post.media.pollId);
    if (!poll) return "";
    const total = pollTotal(poll);
    const closed = !isOpen(poll.closesAt);
    return `<div class="feed-poll">
      <div class="feed-poll__head">
        <span class="tag tag--lineup">${icon("poll", 12)} ${escapeHTML(poll.category)} poll</span>
        <span>${countLabel(total)} votes · ${escapeHTML(closingLabel(poll.closesAt))}</span>
      </div>
      <h3>${escapeHTML(poll.question)}</h3>
      <div class="feed-poll__options">
        ${poll.options
          .map((option) => {
            const selected = poll.userVote === option.id;
            const pct = pollPercent(option, poll);
            return `<button class="feed-poll-option${selected ? " is-selected" : ""}" type="button" data-action="vote-poll" data-poll="${escapeHTML(poll.id)}" data-option="${escapeHTML(option.id)}" ${closed ? "disabled" : ""}>
              <span class="feed-poll-option__label">${voteIcon(selected)}${escapeHTML(option.label)}</span>
              <span class="feed-poll-option__pct">${pct}%</span>
              <span class="feed-poll-option__track"><span style="width:${pct}%"></span></span>
            </button>`;
          })
          .join("")}
      </div>
      <div class="feed-poll__foot">
        <span>${poll.userVote ? `${icon("check", 13)} Vote counted` : "Tap an option to have your say"}</span>
        <a class="text-link text-link--small" href="#/polls">Open polls ${icon("arrowRight", 13)}</a>
      </div>
    </div>`;
  }

  return "";
}

export function openNewPostModal(state, defaultCommunityId = null) {
  openModal({
    eyebrow: "Clubhouse",
    title: "Share an update",
    description: "A quick note, a matchday thought, or something the squad should see.",
    body: `<form class="form" data-form="new-post">
      <div class="form-row form-row--split">
        <label class="field">
          <span>Post to</span>
          <select name="community" required>
            ${state.communities
              .filter((community) => community.joined)
              .map(
                (community) =>
                  `<option value="${escapeHTML(community.id)}"${community.id === defaultCommunityId ? " selected" : ""}>${escapeHTML(community.name)}</option>`,
              )
              .join("")}
          </select>
        </label>
        <label class="field">
          <span>Tag</span>
          <select name="tag">
            <option value="club">Club update</option>
            <option value="matchday">Matchday</option>
            <option value="tactics">Tactics</option>
          </select>
        </label>
      </div>
      <label class="field">
        <span>Your update</span>
        <textarea name="text" rows="5" maxlength="500" placeholder="What’s on your mind?" required></textarea>
        <small>Keep it useful, keep it kind. 500 characters max.</small>
      </label>
      <label class="field post-photo-field">
        <span>Photo banner (optional)</span>
        <input name="image" type="file" accept="image/png,image/jpeg,image/webp" aria-describedby="post-photo-help">
        <small id="post-photo-help">Add one PNG, JPEG or WebP photo. It will appear as a wide banner on the post.</small>
      </label>
      <div class="form-actions">
        <button class="btn btn--ghost" type="button" data-action="close-modal">Cancel</button>
        <button class="btn btn--primary" type="submit">${icon("send", 16)} Post update</button>
      </div>
    </form>`,
  });
}
