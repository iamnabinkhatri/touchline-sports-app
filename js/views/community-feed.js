import { icon } from "../icons.js";
import { pollPercent, pollTotal } from "../store.js";
import { avatar, communityMark, emptyState, safeImageData } from "../ui.js";
import { closingLabel, escapeHTML, formatDate, formatTime, isOpen, safeToken } from "../utils.js";
import { renderPost } from "./home.js";

export function renderCommunityFeed(state, ui, communityId, postId = null) {
  const community = state.communities.find((item) => item.id === communityId);
  if (!community) return emptyState({ iconName: "users", title: "Community not found", text: "This community may have been removed." });
  const posts = state.posts.filter((post) => post.communityId === communityId);
  const selectedPost = postId ? posts.find((post) => post.id === postId) : null;
  const polls = state.polls.filter((poll) => poll.communityId === communityId && isOpen(poll.closesAt)).slice(0, 2);
  const fixture = state.nextFixtures.find((item) => item.communityId === communityId);
  const schedule = state.schedule.filter((event) => event.communityId === communityId).slice(0, 3);
  const completedFixture = state.nextFixtures.filter((item) => item.communityId === communityId && new Date(item.date) < new Date()).sort((a, b) => new Date(b.date) - new Date(a.date))[0];

  return `<div class="page page--community-feed">
    <header class="page-head community-feed-head reveal">
      ${safeImageData(community.bannerData) ? `<img class="community-feed-head__banner" src="${escapeHTML(safeImageData(community.bannerData))}" alt="">` : ""}
      <div class="page-head__copy">
        <p class="eyebrow"><a href="#/communities">Communities</a> · ${escapeHTML(community.sport)} · ${escapeHTML(community.kind)}</p>
        ${communityMark(community, "sm")}
        <h1>${escapeHTML(community.name)}</h1>
        <p class="page-subtitle">${escapeHTML(community.description)}</p>
      </div>
      <div class="page-head__actions">
        ${community.canManage ? `<button class="btn btn--light" type="button" data-action="edit-community-branding" data-community="${escapeHTML(communityId)}">Branding</button>` : ""}
        ${community.canManage ? `<button class="btn btn--light" type="button" data-action="manage-community-members" data-community="${escapeHTML(communityId)}">${icon("users", 16)} Manage members</button>` : ""}
        ${community.joined ? `<button class="btn btn--primary" type="button" data-action="new-post" data-community="${escapeHTML(communityId)}">${icon("plus", 17)} New post</button>` : `<button class="btn btn--primary" type="button" data-action="join-community" data-community="${escapeHTML(communityId)}">${icon("plus", 17)} Join community</button>`}
      </div>
    </header>

    <div class="community-feed-layout">
      <section class="community-feed-main" aria-label="${escapeHTML(community.name)} feed">
        ${selectedPost ? `<a class="text-link community-feed-back" href="#/community/${encodeURIComponent(communityId)}" data-action="community-feed" data-community="${escapeHTML(communityId)}">${icon("arrowLeft", 15)} Back to ${escapeHTML(community.name)}</a>${renderPost(state, selectedPost, ui)}` : `<div class="feed-head"><div><p class="eyebrow">${posts.length} updates</p><h2>Community news</h2></div>${community.joined ? `<button class="text-link" type="button" data-action="new-post" data-community="${escapeHTML(communityId)}">Write an update ${icon("arrowRight", 14)}</button>` : ""}</div>
          <div class="community-news-list">${posts.length ? posts.map((post) => {
            const title = String(post.text ?? "").trim().split(/\n|(?<=[.!?])\s/)[0] || "Community update";
            return `<a class="feed-news-link" href="#/community/${encodeURIComponent(communityId)}/posts/${encodeURIComponent(post.id)}" data-action="open-post" data-community="${escapeHTML(communityId)}" data-post="${escapeHTML(post.id)}"><span class="feed-news-link__icon">${icon("message", 18)}</span><span class="feed-news-link__copy"><small>${escapeHTML(post.author)} · ${escapeHTML(post.timeLabel)}${post.tags?.length ? ` · ${escapeHTML(post.tags.join(" · "))}` : ""}</small><strong>${escapeHTML(title)}</strong><span>${escapeHTML(post.text)}</span></span>${icon("arrowRight", 16)}</a>`;
          }).join("") : emptyState({ iconName: "message", title: "No posts yet", text: community.joined ? "Start the community conversation with the first update." : "Join this community to take part in the conversation.", action: community.joined ? `<button class="btn btn--primary btn--sm" type="button" data-action="new-post" data-community="${escapeHTML(communityId)}">${icon("plus", 15)} New post</button>` : "" })}</div>`}
      </section>

      <aside class="community-feed-rail" aria-label="Community matchday and polls">
        <section class="rail-card community-glimpse-card">
          <div class="rail-card__head"><span class="eyebrow">Squad pulse</span>${community.joined ? `<button class="text-link text-link--small" type="button" data-action="new-poll" data-community="${escapeHTML(communityId)}">New poll ${icon("plus", 13)}</button>` : ""}</div>
          ${polls.length ? polls.map((poll) => { const total = pollTotal(poll); const leader = [...poll.options].sort((a, b) => b.votes - a.votes)[0]; return `<a class="community-glimpse-poll" href="#/polls" data-action="view-poll" data-poll="${escapeHTML(poll.id)}"><span class="tag tag--${safeToken(poll.category.toLowerCase(), ["lineup", "tactics", "club"], "club")}">${escapeHTML(poll.category)}</span><strong>${escapeHTML(poll.question)}</strong><small>${total} votes · ${escapeHTML(closingLabel(poll.closesAt))}</small><span class="rail-poll__bar"><span style="width:${pollPercent(leader, poll)}%"></span></span></a>`; }).join("") : `<p class="community-glimpse-empty">No open polls for this community yet.</p>`}
        </section>
        <section class="rail-card community-glimpse-card community-matchday-card">
          <div class="rail-card__head"><span class="eyebrow">Matchday</span>${community.joined ? `<button class="text-link text-link--small" type="button" data-action="community-calendar" data-community="${escapeHTML(communityId)}">Calendar ${icon("arrowRight", 13)}</button>` : ""}</div>
          ${fixture ? `<div class="community-matchday-fixture"><span class="mini-badge">${escapeHTML(fixture.competition)}</span><strong>${escapeHTML(community.name)} <i>vs</i> ${escapeHTML(fixture.opponent)}</strong><span>${escapeHTML(formatDate(fixture.date))} · ${escapeHTML(formatTime(fixture.date))}</span><small>${escapeHTML(fixture.venue)}</small>${completedFixture && community.canManage ? `<button class="btn btn--primary btn--sm" type="button" data-action="request-matchday-ratings" data-community="${escapeHTML(communityId)}" data-fixture="${escapeHTML(completedFixture.id)}">Email player rating request</button>${completedFixture.hasRatingRequest ? `<button class="btn btn--light btn--sm" type="button" data-action="view-matchday-ratings" data-community="${escapeHTML(communityId)}" data-fixture="${escapeHTML(completedFixture.id)}">View member feedback</button>` : ""}` : ""}</div>` : ""}
          ${schedule.map((event) => `<div class="community-matchday-event"><span>${escapeHTML(formatDate(event.date))}</span><strong>${escapeHTML(event.title)}</strong><small>${escapeHTML(event.detail)}</small></div>`).join("")}
          ${!fixture && !schedule.length ? `<p class="community-glimpse-empty">No matchday events scheduled yet.</p>` : ""}
        </section>
      </aside>
    </div>
  </div>`;
}
