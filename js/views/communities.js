import { icon } from "../icons.js";
import {
  avatar,
  avatarStack,
  communityMark,
  countLabel,
  openModal,
  privacyPill,
  sportIcon,
  safeImageData,
} from "../ui.js";
import { escapeHTML, safeToken } from "../utils.js";
import { filterCommunities, visibleDiscoverCommunities } from "../community-discovery.js";

const SPORTS = ["Soccer", "Basketball", "Running", "Volleyball", "Tennis", "Baseball"];
const ACCENTS = ["forest", "lime", "coral", "sky", "violet", "gold", "sage", "red"];

export function renderCommunities(state, ui) {
  const joined = state.communities.filter((community) => community.joined);
  const discover = filterCommunities(state.communities.filter((community) => community.joined || community.privacy === "Public"), ui.sportFilter);
  const discoverPage = visibleDiscoverCommunities(discover, ui.showAllDiscover === true, 5);
  const newToExplore = discover.filter((community) => !community.joined).length;
  const sports = [...new Set(state.communities.map((community) => community.sport))];

  return `<div class="page page--communities">
    <header class="page-head reveal">
      <div class="page-head__copy">
        <p class="eyebrow"><span class="eyebrow__line"></span>Communities</p>
        <h1>Find your people.</h1>
        <p class="page-subtitle">Clubhouses for every sport, squad and Sunday league team. Pull up a chair.</p>
      </div>
    </header>

    <section class="community-banner reveal reveal--delay-1" aria-labelledby="community-banner-title">
      <div class="community-banner__copy">
        <span class="tag tag--light">${icon("users", 12)} The clubhouse network</span>
        <h2 id="community-banner-title">Your team. Your rituals.<br><span>Your people.</span></h2>
        <p>Polls, team sheets and matchday plans belong with the people who care about them. Build a space that feels like your club.</p>
        <div class="community-banner__stats">
          <div><strong>${joined.length}</strong><span>your communities</span></div>
          <div><strong>${state.communities.reduce((total, community) => total + community.memberCount, 0).toLocaleString()}</strong><span>members nearby</span></div>
          <div><strong>${sports.length}</strong><span>sports covered</span></div>
        </div>
      </div>
      <div class="community-banner__art" aria-hidden="true">
        <div class="orbit orbit--one"></div>
        <div class="orbit orbit--two"></div>
        <div class="banner-ball">${icon("ball", 74)}</div>
        <span class="banner-chip banner-chip--one">${icon("poll", 13)} Your community</span>
        <span class="banner-chip banner-chip--two">${icon("team", 13)} Your club</span>
        <span class="banner-chip banner-chip--three">${icon("clipboard", 13)} Your space</span>
      </div>
    </section>

    <section class="community-section reveal reveal--delay-2" aria-labelledby="your-communities-title">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Your clubhouses</p>
          <h2 id="your-communities-title">Where you belong</h2>
        </div>
        <span class="section-count">${joined.length} joined</span>
      </div>
      <div class="community-grid">
        ${joined
          .map(
            (community, index) => `<article class="community-card community-card--${safeToken(community.accent, ACCENTS, "forest")}">
              <a class="community-card__visual" href="#/community/${encodeURIComponent(community.id)}" data-action="community-feed" data-community="${escapeHTML(community.id)}" aria-label="Open ${escapeHTML(community.name)} feed">
                <span class="community-card__mark">${communityMark(community, "md")}</span>
                ${safeImageData(community.bannerData) ? `<img class="community-card__banner" src="${escapeHTML(safeImageData(community.bannerData))}" alt="">` : ""}
                <span class="community-card__sport">${sportIcon(community.sport, 22)}</span>
                <span class="community-card__stamp">${String(index + 1).padStart(2, "0")}</span>
                <span class="community-card__lines" aria-hidden="true"></span>
              </a>
              <div class="community-card__body">
                <div class="community-card__title-row">
                  <div>
                    <h3>${escapeHTML(community.name)}</h3>
                    <p>${escapeHTML(community.sport)} · ${escapeHTML(community.kind)}</p>
                  </div>
                  ${community.role ? `<span class="role-badge">${escapeHTML(community.role)}</span>` : ""}
                </div>
                <p class="community-card__description">${escapeHTML(community.description)}</p>
                <div class="community-card__meta">
                  ${avatarStack(
                    state.leaders.slice(0, Math.min(3, community.memberCount)),
                    Math.max(0, community.memberCount - Math.min(3, community.memberCount)),
                  )}
                  <span>${countLabel(community.memberCount)} members</span>
                </div>
                <div class="community-card__footer">
                  <span>${icon("bolt", 13)} ${escapeHTML(community.activity)}</span>
                  <button class="text-link text-link--small" type="button" data-action="community-feed" data-community="${escapeHTML(community.id)}">Open ${icon("arrowRight", 14)}</button>
                  <button class="text-link text-link--small" type="button" data-action="open-community-chat" data-community="${escapeHTML(community.id)}">Chat${community.unreadCount ? ` <span class="chat-unread-badge">${community.unreadCount}</span>` : ""}</button>
                </div>
              </div>
            </article>`,
          )
          .join("")}
      </div>
    </section>

    <section class="community-section reveal reveal--delay-3" aria-labelledby="discover-title">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Discover</p>
          <h2 id="discover-title">More rooms, same love of the game</h2>
        </div>
        <span class="section-count">${discover.length} communities · ${newToExplore} to join</span>
      </div>
      <div class="filter-row filter-row--sports" role="group" aria-label="Filter communities by sport">
        ${["All", ...SPORTS]
          .map(
            (sport) => `<button class="filter-chip${ui.sportFilter === sport ? " is-active" : ""}" type="button" data-action="filter-sport" data-sport="${escapeHTML(sport)}">${sport === "All" ? icon("dotsGrid", 13) : sportIcon(sport, 13)}${escapeHTML(sport)}</button>`,
          )
          .join("")}
      </div>
      <div class="discover-list">
        ${
          discover.length
            ? discoverPage.items
                .map(
                  (community) => `<a class="discover-community-row" href="${community.joined ? `#/community/${encodeURIComponent(community.id)}` : "#/communities"}" data-action="${community.joined ? "community-feed" : "open-community"}" data-community="${escapeHTML(community.id)}">
                    <span class="discover-community-row__crest discover-icon--${safeToken(community.accent, ACCENTS, "forest")}">${escapeHTML(community.mark)}</span>
                    <span class="discover-community-row__copy"><strong>${escapeHTML(community.name)}</strong><small>${escapeHTML(community.sport)} · ${escapeHTML(community.kind)} · ${escapeHTML(community.privacy)}</small><span>${escapeHTML(community.description)}</span></span>
                    <span class="discover-community-row__members">${icon("users", 14)} ${countLabel(community.memberCount)}</span>
                    ${community.unreadCount ? `<span class="chat-unread-badge" aria-label="${community.unreadCount} unread messages">${community.unreadCount}</span>` : ""}
                    <span class="discover-community-row__action">${community.joined ? "Open" : community.joinRequestStatus === "pending" ? "Request pending" : community.privacy === "Public" ? "Explore" : "Invite only"} ${icon("arrowRight", 14)}</span>
                  </a>`,
                )
                .join("")
            : `<div class="empty-inline">${icon("search", 18)} No communities in ${escapeHTML(ui.sportFilter)} yet. Try another sport.</div>`
        }
      </div>
      ${discoverPage.hasMore ? `<button class="discover-show-more" type="button" data-action="toggle-discover-more">Show more <span>(${discoverPage.hiddenCount} more)</span></button>` : ui.showAllDiscover && discover.length > 5 ? `<button class="discover-show-more" type="button" data-action="toggle-discover-more">Show less</button>` : ""}
    </section>
  </div>`;
}

export function openCommunityModal(state, communityId, ui = {}, members = []) {
  const community = state.communities.find((item) => item.id === communityId);
  if (!community) return;
  ui.openCommunityId = communityId;
  const isJoined = community.joined;
  const joinPending = community.joinRequestStatus === "pending";
  openModal({
    title: community.name,
    eyebrow: `${community.sport} · ${community.kind}`,
    description: community.description,
    wide: true,
    body: `<div class="community-modal">
      <div class="community-modal__hero community-modal__hero--${safeToken(community.accent, ACCENTS, "forest")}">
        ${communityMark(community, "xl")}
        <div>
          <span class="community-modal__sport">${sportIcon(community.sport, 16)} ${escapeHTML(community.sport)} community</span>
          <h3>${escapeHTML(community.name)}</h3>
          <div class="community-modal__pills">
            ${privacyPill(community.privacy)}
            ${community.role ? `<span class="role-badge">${escapeHTML(community.role)}</span>` : ""}
            <span class="meta-pill">${icon("users", 12)} ${community.memberCount.toLocaleString()} members</span>
          </div>
        </div>
      </div>
      <div class="community-modal__stats">
        <div><strong>${countLabel(community.memberCount)}</strong><span>Members</span></div>
        <div><strong>${community.activity.includes("posts this week") ? community.activity.split(" ")[0] : "New"}</strong><span>Posts this week</span></div>
        <div><strong>${community.privacy}</strong><span>Access</span></div>
      </div>
      <div class="community-modal__section">
        <div class="section-heading section-heading--small">
          <h3>People in this clubhouse</h3>
          <span>${isJoined ? `${members.length} active members` : "Join to see everyone"}</span>
        </div>
        <div class="member-list">
          ${members
            .map(
              (member) => `<div class="member-row">
                ${avatar(member.name, { tone: member.avatarTone, size: "sm" })}
                <div><strong>${escapeHTML(member.name)}</strong><span>${escapeHTML(member.email)}</span></div>
                <span class="role-badge">${escapeHTML(member.role)}</span>
              </div>`,
            )
            .join("") || (!isJoined ? `<p class="community-members-hidden">Join this community to see its members.</p>` : `<p class="community-members-hidden">No members are listed yet.</p>`)}
        </div>
      </div>
      <div class="modal-actions">
        ${community.canManage ? `<button class="btn btn--light" type="button" data-action="manage-community-members" data-community="${escapeHTML(community.id)}">Manage members${community.pendingJoinRequestCount ? ` · ${community.pendingJoinRequestCount} request${community.pendingJoinRequestCount === 1 ? "" : "s"}` : ""}</button>` : ""}
        <button class="btn btn--ghost" type="button" data-action="close-modal">Close</button>
        ${
          isJoined
            ? `<button class="btn btn--primary" type="button" data-action="community-feed" data-community="${escapeHTML(community.id)}">${icon("arrowRight", 16)} Open feed</button>`
            : community.privacy !== "Public"
              ? `<span class="community-join-note">Private community · ask an admin for an invite</span>`
              : joinPending
                ? `<button class="btn btn--light" type="button" disabled>${icon("clock", 16)} Request pending</button>`
                : `<button class="btn btn--primary" type="button" data-action="join-community" data-community="${escapeHTML(community.id)}">${icon("plus", 16)} ${community.joinRequestStatus === "denied" ? "Request to join again" : "Request to join"}</button>`
        }
      </div>
    </div>`,
  });
}

export function openNewCommunityModal(state) {
  openModal({
    eyebrow: "New community",
    title: "Build your clubhouse",
    description: "Give your people a home for the season. You can fine-tune everything later.",
    body: `<form class="form" data-form="new-community">
      <label class="field">
        <span>Community name</span>
        <input name="name" type="text" placeholder="e.g. Fort Greene Football Club" required maxlength="48" autocomplete="off">
      </label>
      <div class="form-row form-row--split">
        <label class="field">
          <span>Space type</span>
          <select name="kind"><option value="Community">Community</option><option value="Club">Club</option></select>
        </label>
      </div>
      <div class="form-row form-row--split">
        <label class="field">
          <span>Sport</span>
          <select name="sport" required>
            ${SPORTS.map((sport) => `<option value="${sport}"${sport === "Soccer" ? " selected" : ""}>${sport}</option>`).join("")}
          </select>
        </label>
        <label class="field">
          <span>Privacy</span>
          <select name="privacy">
            <option value="Public">Public — anyone can find us</option>
            <option value="Private">Private — invite only</option>
          </select>
        </label>
      </div>
      <label class="field">
        <span>What’s it for?</span>
        <textarea name="description" rows="4" maxlength="220" placeholder="A short intro for new members…" required></textarea>
      </label>
      <div class="form-row form-row--split">
        <label class="field"><span>Community logo</span><input name="logo" type="file" accept="image/png,image/jpeg,image/webp"><small>Square image recommended.</small></label>
        <label class="field"><span>Banner image</span><input name="banner" type="file" accept="image/png,image/jpeg,image/webp"><small>Wide landscape image recommended.</small></label>
      </div>
      <label class="check-row">
        <input type="checkbox" name="createPoll">
        <span><strong>Add a starter poll</strong><small>Ask the group one question to get things moving.</small></span>
      </label>
      <div class="form-actions">
        <button class="btn btn--ghost" type="button" data-action="close-modal">Cancel</button>
        <button class="btn btn--primary" type="submit">${icon("plus", 16)} Create community</button>
      </div>
    </form>`,
  });
}

export function openCommunityBrandingModal(community) {
  openModal({
    eyebrow: "Community settings",
    title: "Community branding",
    description: "Add a logo and banner image for your clubhouse.",
    body: `<form class="form" data-form="community-branding" data-community="${escapeHTML(community.id)}">
      <label class="field"><span>Community logo</span><input name="logo" type="file" accept="image/png,image/jpeg,image/webp"><small>Square image recommended.</small></label>
      ${community.logoData ? `<label class="check-row"><input name="removeLogo" type="checkbox"><span>Remove current logo</span></label>` : ""}
      <label class="field"><span>Banner image</span><input name="banner" type="file" accept="image/png,image/jpeg,image/webp"><small>Wide landscape image recommended.</small></label>
      ${community.bannerData ? `<label class="check-row"><input name="removeBanner" type="checkbox"><span>Remove current banner</span></label>` : ""}
      <div class="form-actions"><button class="btn btn--ghost" type="button" data-action="close-modal">Cancel</button><button class="btn btn--primary" type="submit">Save branding</button></div>
    </form>`,
  });
}
