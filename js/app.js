import { initApp, setState, refreshState } from "./store.js";
import { ApiError, adminLogin, api, login, logout, register, setSessionToken } from "./api.js";
import { brandMark, icon } from "./icons.js";
import {
  avatar,
  closeModal,
  communityMark,
  countLabel,
  crest,
  getModal,
  openModal,
  toast,
} from "./ui.js";
import { escapeHTML, formatDate, formatTime, isOpen } from "./utils.js";
import { groupNotifications } from "./notification-groups.js";
import { renderHome, openNewPostModal } from "./views/home.js";
import { renderCommunityFeed } from "./views/community-feed.js";
import {
  renderCommunities,
  openCommunityModal,
  openNewCommunityModal,
  openCommunityBrandingModal,
} from "./views/communities.js";
import { renderPolls, openNewPollModal } from "./views/polls.js";
import { renderPickup, getPickupPool, getPickupResult } from "./views/pickup.js";
import {
  renderTeams,
  openAddPlayerModal,
  openPlayerModal,
  autoLineup,
  openNewTeamModal,
} from "./views/teams.js";
import { renderPlayerProfile } from "./views/player.js";
import { renderPlans, openEditPlanModal, openNewPlanModal } from "./views/plans.js";
import { renderCalendar, openNewDutyModal, openNewCalendarEventModal } from "./views/calendar.js";
import { DUTY_KINDS, localDayKey, monthKey, shiftMonth } from "./calendar-model.js";
import { baseHrefForPath } from "./navigation.js";
import { pickupTeamNames } from "./pickup-team-names.js";
import { rankSearchResults } from "./community-discovery.js";

let state = null;

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
  calendarMonth: null,
  calendarDay: null,
  calendarCommunityId: null,
  selectedTeamId: null,
  planTab: "overview",
  selectedPlanId: null,
  planBoardDraft: null,
  planBoardPlanId: null,
  planBoardSelectedPlayer: null,
  notificationsOpen: false,
  searchQuery: "",
  searchOpen: false,
  openComments: [],
  pickupIncludeDoubtful: false,
  pickupPositionAware: true,
  pickupVariant: Math.floor(Math.random() * 100000),
  pickupManualSplit: null,
  authMode: null,
  authMessage: "",
  authChallenge: null,
  googleAuthEnabled: false,
  resetToken: null,
  playerInviteToken: null,
  messengerCommunityId: null,
  messengerMessages: [],
  messengerDraft: "",
  messengerMembers: [],
  messengerTaggedMembers: [],
  expandedPollOptions: [],
  pollsShowMore: false,
  expandedPollCards: [],
  editingMessageId: null,
  messengerLoading: false,
  messengerMinimized: true,
  messengerForceScrollToBottom: false,
  messengerIsAtBottom: true,
  messengerScrollTop: 0,
};

function currentTeam() {
  return state?.teams?.find((team) => team.id === ui.selectedTeamId) ?? state?.teams?.[0] ?? null;
}

const ROUTES = {
  home: {
    label: "Clubhouse",
    title: "Home",
    render: renderHome,
  },
  communities: {
    label: "Communities",
    title: "Communities",
    render: renderCommunities,
  },
  community: {
    label: "Community feed",
    title: "Community feed",
    render: renderCommunityFeed,
  },
  polls: {
    label: "Soccer polls",
    title: "Polls",
    render: renderPolls,
  },
  teams: {
    label: "Team hub",
    title: "Team",
    render: renderTeams,
  },
  pickup: {
    label: "Pickup games",
    title: "Pickup",
    render: renderPickup,
  },
  plans: {
    label: "Game plans",
    title: "Game plans",
    render: renderPlans,
  },
  calendar: {
    label: "Calendar",
    title: "Calendar",
    render: renderCalendar,
  },
};

const PLAYER_ROUTE_RE = /^#\/player\/([a-z0-9][a-z0-9-]*)$/;

function currentPlayerRoute() {
  const m = window.location.hash.match(PLAYER_ROUTE_RE);
  return m ? m[1] : null;
}

const NAV_GROUPS = [
  {
    label: "Clubhouse",
    links: [
      { route: "home", icon: "home", label: "Home" },
      { route: "communities", icon: "users", label: "Communities" },
      { route: "polls", icon: "poll", label: "Soccer polls", count: "polls" },
    ],
  },
  {
    label: "Squad",
    links: [
      { route: "teams", icon: "team", label: "Team hub" },
      { route: "calendar", icon: "calendar", label: "Calendar" },
      { route: "pickup", icon: "shuffle", label: "Pickup builder" },
      { route: "plans", icon: "clipboard", label: "Game plans" },
    ],
  },
];

function currentRoute() {
  const key = window.location.hash.replace(/^#\/?/, "").split("?")[0] || "home";
  if (/^community\/[A-Za-z0-9_-]+(?:\/posts\/[A-Za-z0-9_-]+)?$/.test(key)) return "community";
  return ROUTES[key] ? key : "home";
}

function currentCommunityRoute() {
  const match = window.location.hash.match(/^#\/?community\/([A-Za-z0-9_-]+)(?:\/posts\/([A-Za-z0-9_-]+))?/);
  return match ? { communityId: match[1], postId: match[2] ?? null } : null;
}

function renderBootScreen() {
  return `<div class="boot-screen" role="status" aria-live="polite">
    <div class="boot-screen__mark">${brandMark(58)}</div>
    <p class="eyebrow">Touchline · Clubhouse server</p>
    <h1>Warming up the dressing room.</h1>
    <p>Loading your squad, polls and plans from the server.</p>
    <span class="boot-spinner" aria-label="Loading"></span>
  </div>`;
}

function renderBootError(error) {
  const message = error instanceof Error ? error.message : "The server could not be reached.";
  return `<div class="boot-screen boot-screen--error" role="alert">
    <div class="boot-screen__mark">${brandMark(58)}</div>
    <p class="eyebrow">Connection problem</p>
    <h1>We can’t reach the clubhouse.</h1>
    <p>${escapeHTML(message)}</p>
    <p class="boot-screen__hint">Start the Python server with <code>npm start</code>, then try again.</p>
    <button class="btn btn--primary" type="button" data-action="retry-boot">${icon("reset", 16)} Try again</button>
  </div>`;
}

async function boot() {
  const root = document.querySelector("#app");
  if (!root) return;
  const base = document.querySelector("base");
  if (base) base.href = new URL(baseHrefForPath(window.location.pathname), window.location.origin).href;
  const params = new URLSearchParams(window.location.search);
  try { ui.googleAuthEnabled = Boolean((await api.get("/auth/google/config")).enabled); }
  catch { ui.googleAuthEnabled = false; }
  if (params.has("code") && params.has("state")) {
    try {
      const result = await api.post("/auth/google/callback", { code: params.get("code"), state: params.get("state") });
      if (result.token) setSessionToken(result.token);
      if (result.twoFactorRequired) {
        ui.authChallenge = result.challengeToken;
        ui.authMode = "two-factor";
        ui.authMessage = "Complete your two-factor check to finish signing in.";
      } else if (result.created) {
        ui.authMessage = "Your account is ready. You signed in with Google.";
      }
      window.history.replaceState({}, "", `${window.location.pathname}${window.location.hash}`);
    } catch (error) {
      ui.authMessage = error.message || "Google sign-in could not be completed.";
      window.history.replaceState({}, "", `${window.location.pathname}${window.location.hash}`);
    }
  } else if (params.get("error") === "access_denied") {
    ui.authMessage = "Google sign-in was cancelled.";
    window.history.replaceState({}, "", `${window.location.pathname}${window.location.hash}`);
  } else if (params.has("error")) {
    ui.authMessage = "Google could not complete sign-in. Try again.";
    window.history.replaceState({}, "", `${window.location.pathname}${window.location.hash}`);
  }
  try {
    const theme = await api.get("/theme");
    document.documentElement.dataset.theme = theme.theme === "dark" ? "dark" : "light";
    document.documentElement.style.colorScheme = document.documentElement.dataset.theme;
  } catch { /* The signed-in bootstrap applies the saved theme when available. */ }
  if (params.has("player_invite")) {
    setSessionToken(null);
    ui.playerInviteToken = params.get("player_invite");
    ui.authMode = "register";
    window.history.replaceState({}, "", window.location.pathname);
  } else if (params.has("verify_token")) {
    try {
      await api.post("/auth/verify-email", { token: params.get("verify_token") });
      ui.authMessage = "Email verified. You can sign in now.";
      window.history.replaceState({}, "", window.location.pathname);
    } catch (error) { ui.authMessage = error.message; }
  } else if (params.has("reset_token")) {
    setSessionToken(null);
    ui.resetToken = params.get("reset_token"); ui.authMode = "reset";
  }
  root.innerHTML = renderBootScreen();
  document.title = "Connecting · Touchline";
  try {
    let inviteJoinedName = null;
    state = await initApp();
    if ((isAdminEntry() && state.user.role !== "Super Admin") || (!isAdminEntry() && state.user.role === "Super Admin")) {
      setSessionToken(null);
      throw new ApiError(window.TOUCHLINE_MOBILE ? "Super-admin access is available only in the web app." : "This private page is for the super administrator.", { status: 401, code: "admin_only" });
    }
    if (params.has("community_invite")) {
      const inviteToken = params.get("community_invite");
      const joinedCommunity = await api.post("/community-invites/accept", { token: inviteToken });
      inviteJoinedName = joinedCommunity.name;
      window.history.replaceState({}, "", `${window.location.pathname}${window.location.hash}`);
      state = await refreshState();
      setState(state);
      toast(`You joined ${joinedCommunity.name}.`, "success");
    }
    if (!state.plans.some((plan) => plan.id === ui.selectedPlanId)) {
      ui.selectedPlanId = state.plans[0]?.id ?? null;
    }
    if (!state.teams.some((team) => team.id === ui.selectedTeamId)) ui.selectedTeamId = state.teams[0]?.id ?? null;
    if ((window.location.hash || "#/home").startsWith("#/calendar")) await loadCalendar();
    renderApp({ scrollTop: true });
    const initialCommunityRoute = currentCommunityRoute();
    if (initialCommunityRoute) selectCommunityChat(initialCommunityRoute.communityId);
    const reviewParams = new URLSearchParams((window.location.hash.split("?")[1] || ""));
    const reviewFixture = reviewParams.get("rateFixture");
    if (initialCommunityRoute && reviewFixture) await openMatchdayReview(initialCommunityRoute.communityId, reviewFixture);
    const feedbackPoll = reviewParams.get("feedbackPoll");
    if (feedbackPoll) await openPollFeedback(feedbackPoll);
    if (inviteJoinedName) toast(`You joined ${inviteJoinedName}.`, "success");
  } catch (error) {
    if (error instanceof ApiError && (error.status === 401 || error.code === "sign_in_required")) {
      root.innerHTML = renderAuthScreen(error.code === "admin_only" ? "Use your private administrator URL to sign in as super admin." : "");
      document.title = isAdminEntry() ? "Administrator sign in · Touchline" : "Sign in · Touchline";
    } else {
      root.innerHTML = renderBootError(error);
      document.title = "Connection problem · Touchline";
    }
  }
}

function isAdminEntry() {
  if (window.TOUCHLINE_MOBILE) return false;
  return window.location.pathname !== "/" && window.location.pathname !== "/index.html";
}

function renderAuthScreen(message = "") {
  const admin = isAdminEntry();
  const mode = ui.authMode || (admin ? "login-admin" : "login");
  const isRegister = mode === "register";
  const isForgot = mode === "forgot";
  const isReset = mode === "reset";
  const isVerify = mode === "verify";
  const isChallenge = mode === "two-factor";
  const isNotice = ["check-email", "forgot-sent"].includes(mode);
  const heading = isRegister ? "Create your account" : isForgot ? "Reset your password" : isReset ? "Choose a new password" : isVerify ? "Check your email" : isChallenge ? "Two-factor sign in" : isNotice ? "Check your inbox" : admin ? "Super admin sign in" : "Welcome to the clubhouse";
  const content = isNotice ? `<p>${mode === "check-email" ? "We sent a verification link to your address. Verify it before signing in." : "If an account can receive a reset link, we have sent one."}</p><button class="text-link" type="button" data-action="auth-mode" data-mode="verify">Resend verification email</button>` : `<form class="form auth-form" data-form="${isChallenge ? "two-factor-login" : isRegister ? "player-register" : isForgot ? "forgot-password" : isReset ? "reset-password" : isVerify ? "resend-verification" : admin ? "admin-login" : "player-auth"}">
      ${isRegister ? `<label class="field"><span>Your name</span><input name="name" autocomplete="name" required minlength="2" maxlength="50"></label>${ui.playerInviteToken ? `<input type="hidden" name="playerInvite" value="${escapeHTML(ui.playerInviteToken)}"><p class="form-note">Use the email address this invite was sent to. Your account and player profile will join the community after registration; verify your email before signing in.</p>` : ""}` : ""}
      ${isChallenge ? `<label class="field"><span>Authenticator or recovery code</span><input name="code" autocomplete="one-time-code" inputmode="numeric" required maxlength="64"></label>` : isReset ? `<label class="field"><span>New password</span><input name="password" type="password" autocomplete="new-password" required minlength="10" maxlength="128"></label><label class="field"><span>Confirm password</span><input name="confirmPassword" type="password" required minlength="10" maxlength="128"></label>` : !isNotice && !isChallenge ? `<label class="field"><span>Email</span><input name="email" type="email" autocomplete="email" required maxlength="254"></label>${!isForgot && !isVerify ? `<label class="field"><span>Password</span><input name="password" type="password" autocomplete="${isRegister ? "new-password" : "current-password"}" required minlength="${isRegister ? 10 : 1}" maxlength="128"></label>` : ""}` : ""}
      <p class="auth-error" role="alert" hidden></p><div class="form-actions"><button class="btn btn--primary" type="submit">${isRegister ? "Create account" : isForgot ? "Send reset link" : isReset ? "Save password" : isVerify ? "Resend email" : isChallenge ? "Verify and sign in" : admin ? "Sign in as admin" : "Sign in"}</button></div>
    </form>`;
  return `<main class="boot-screen auth-screen">
    <div class="boot-screen__mark">${brandMark(58)}</div>
    <p class="eyebrow">Touchline · ${admin ? "Administrator access" : "Clubhouse access"}</p>
    <h1>${heading}</h1>
    <p>${admin ? "This private entry is for the club administrator." : "Use your email address to access your community."}</p>
    ${(message || ui.authMessage) ? `<p class="boot-screen__hint" role="status">${escapeHTML(message || ui.authMessage)}</p>` : ""}
    ${content}
    ${ui.googleAuthEnabled && !window.TOUCHLINE_MOBILE && !admin && !isNotice && !isChallenge && !isForgot && !isReset && !isVerify ? `<div class="auth-provider-divider"><span>or</span></div><button class="google-auth-button" type="button" data-action="google-signin"><span aria-hidden="true" class="google-auth-button__mark">G</span><span>Continue with Google</span></button>` : ""}
    ${!admin && !isNotice && !isChallenge && !isReset ? `<div class="auth-links">${mode === "login" ? `<button class="text-link" type="button" data-action="auth-mode" data-mode="forgot">Forgot password?</button><span>·</span><button class="text-link" type="button" data-action="auth-mode" data-mode="register">Create account</button><span>·</span><button class="text-link" type="button" data-action="auth-mode" data-mode="verify">Resend verification</button>` : `<button class="text-link" type="button" data-action="auth-mode" data-mode="login">Back to sign in</button>`}</div>` : ""}
    ${window.TOUCHLINE_MOBILE ? `<div class="auth-links"><a class="text-link" href="?mobileConfigure=1">Server connection</a></div>` : ""}
  </main>`;
}

function renderApp({ preserveScroll = false, scrollTop = false } = {}) {
  const root = document.querySelector("#app");
  if (!root) return;
  if (!state) {
    root.innerHTML = renderBootScreen();
    return;
  }
  const previousScroll = window.scrollY;
  const playerId = currentPlayerRoute();
  const routeKey = playerId ? "teams" : currentRoute();
  const route = ROUTES[routeKey];
  const communityRoute = currentCommunityRoute();
  const activeThemeCommunity = communityRoute && state.communities.find((item) => item.id === communityRoute.communityId);
  const activeTheme = activeThemeCommunity?.profileTheme ?? state.appTheme ?? "light";
  document.documentElement.dataset.theme = activeTheme === "dark" ? "dark" : "light";
  document.documentElement.style.colorScheme = document.documentElement.dataset.theme;
  const content = playerId
    ? renderPlayerProfile(state, ui, playerId)
    : communityRoute
      ? route.render(state, ui, communityRoute.communityId, communityRoute.postId)
      : route.render(state, ui);
  root.innerHTML = `<div class="app-shell">
    ${renderSidebar(routeKey)}
    <div class="app-main">
      ${renderTopbar(routeKey)}
      <main class="main" id="main-content">${content}</main>
      <footer class="site-footer">
        <span>${brandMark(22)} <strong>TOUCHLINE</strong> — the clubhouse for the beautiful game.</span>
        <span>${escapeHTML(state.teams?.[0]?.name || state.communities?.[0]?.name || "Your club")} · ${new Date().getFullYear()}</span>
      </footer>
    </div>
    ${renderMobileNav(routeKey)}
  </div>`;
  mountMessengerPanel();
  if (playerId) {
    const p = state?.teams?.[0]?.players?.find((item) => item.id === playerId);
    document.title = p ? `${p.name} · Touchline` : "Player · Touchline";
  } else {
    const community = communityRoute && state.communities.find((item) => item.id === communityRoute.communityId);
    document.title = `${community?.name ?? route.title} · Touchline`;
  }
  if (scrollTop) {
    window.scrollTo({ top: 0, behavior: "instant" });
  } else if (preserveScroll) {
    window.scrollTo({ top: previousScroll, behavior: "instant" });
  }
}

function renderSidebar(routeKey) {
  const activePolls = state.polls.filter((poll) => isOpen(poll.closesAt)).length;
  const joined = state.communities.filter((community) => community.joined).slice(0, 3);
  return `<aside class="sidebar" aria-label="Primary navigation">
    <a class="brand" href="#/home" aria-label="Touchline home">
      ${brandMark(38)}
      <span class="brand__word">TOUCH<span>LINE</span></span>
    </a>
    <div class="club-card">
      ${crest(state.teams?.[0]?.mark || "FC", state.teams?.[0]?.accent || "lime", "sm", state.teams?.[0]?.name || "Your club")}
      <div>
        <span>Your club</span>
        <strong>${escapeHTML(state.teams?.[0]?.name || state.communities?.[0]?.name || "Not set up")}</strong>
      </div>
      <span class="club-card__live"><i></i>Live</span>
    </div>
    <nav class="side-nav">
      ${NAV_GROUPS.map(
        (group) => `<div class="side-nav__group">
          <p class="side-label">${group.label}</p>
          ${group.links
            .map(
              (link) => `<a class="side-link${routeKey === link.route || (routeKey === "community" && link.route === "communities") ? " is-active" : ""}" href="#/${link.route}"${routeKey === link.route || (routeKey === "community" && link.route === "communities") ? ' aria-current="page"' : ""}>
                <span class="side-link__icon">${icon(link.icon, 18)}</span>
                <span>${link.label}</span>
                ${link.count === "polls" && activePolls ? `<span class="side-link__count">${activePolls}</span>` : ""}
              </a>`,
            )
            .join("")}
        </div>`,
      ).join("")}
    </nav>
    <div class="sidebar__clubs">
      <div class="side-label-row">
        <p class="side-label">Your clubhouses</p>
        <button class="side-mini-button" type="button" data-action="new-community" aria-label="Create a community">${icon("plus", 13)}</button>
      </div>
      ${joined
        .map(
          (community) => `<button class="side-club" type="button" data-action="community-feed" data-community="${escapeHTML(community.id)}">
            ${communityMark(community, "xxs")}
            <span>${escapeHTML(community.name)}</span>
            <i class="side-club__dot"></i>
          </button>`,
        )
        .join("")}
    </div>
    <div class="sidebar__tip">
      <span class="sidebar__tip-icon">${icon("sparkle", 17)}</span>
      <strong>Matchday, sorted.</strong>
      <p>Bring your squad in. Polls, plans and team sheets live in one place.</p>
      <button class="sidebar__tip-button" type="button" data-action="copy-invite">Copy invite link ${icon("arrowUpRight", 12)}</button>
    </div>
    <div class="sidebar__user">
      ${avatar(state.user.name, { size: "sm", tone: "lime" })}
      <div>
        <strong>${escapeHTML(state.user.name)}</strong>
        <span>${escapeHTML(state.user.role)}</span>
      </div>
      <button class="icon-button icon-button--sidebar" type="button" data-action="open-profile" aria-label="Open your profile">${icon("more", 17)}</button>
    </div>
  </aside>`;
}

function renderTopbar(routeKey) {
  const route = ROUTES[routeKey];
  const crumbLabel = routeKey === "home" ? "Home" : route.label;
  const unread = state.notifications.filter((notification) => notification.unread).length;
  return `<header class="topbar">
    <div class="topbar__left">
      <a class="mobile-brand" href="#/home" aria-label="Touchline home">${brandMark(30)}<span>TOUCHLINE</span></a>
      <div class="topbar__crumb">
        <span>Clubhouse</span>
        ${icon("chevronRight", 12)}
        <strong>${crumbLabel}</strong>
      </div>
    </div>
    <div class="topbar__right">
      <div class="global-search">
        <label class="global-search__field">
          ${icon("search", 17)}
          <input id="global-search" type="search" placeholder="Search the clubhouse…" aria-label="Search the clubhouse" value="${escapeHTML(ui.searchQuery)}" autocomplete="off">
          <kbd>⌘ K</kbd>
          <button class="global-search__clear" type="button" data-action="clear-search" aria-label="Clear search" ${ui.searchQuery ? "" : "hidden"}>${icon("close", 14)}</button>
        </label>
        <div class="search-results" id="search-results">${ui.searchOpen ? renderSearchResults(ui.searchQuery) : ""}</div>
      </div>
      <div class="notifications-wrap">
        <button class="topbar-icon${ui.notificationsOpen ? " is-active" : ""}" type="button" data-action="toggle-notifications" aria-label="Notifications${unread ? `, ${unread} unread` : ""}" aria-expanded="${ui.notificationsOpen}">
          ${icon("bell", 19)}
          ${unread ? `<span class="notification-dot">${unread}</span>` : ""}
        </button>
        ${ui.notificationsOpen ? renderNotifications() : ""}
      </div>
      <button class="topbar-avatar" type="button" data-action="open-profile" aria-label="Open profile">
        ${avatar(state.user.name, { size: "sm", tone: "forest" })}
        <span class="topbar-avatar__copy"><strong>${escapeHTML(state.user.name)}</strong><small>${escapeHTML(state.user.role)}</small></span>
        ${icon("chevronDown", 14)}
      </button>
    </div>
  </header>`;
}

function renderNotifications() {
  const { stacks, standalone } = groupNotifications(state.notifications);
  const renderItem = (notification) => `<button class="notification${notification.unread ? " is-unread" : ""}" type="button" data-action="open-notification" data-note="${escapeHTML(notification.id)}" aria-label="Open notification: ${escapeHTML(notification.title)}">
    <span class="notification__icon">${icon(notification.icon, 17)}</span>
    <span class="notification__copy"><strong>${escapeHTML(notification.title)}</strong><span>${escapeHTML(notification.body)}</span><small>${escapeHTML(notification.time)}</small></span>
    ${notification.unread ? '<i class="notification__unread"></i>' : ""}
  </button>`;
  const stackedPosts = stacks.map((stack) => {
    const communityName = state.communities.find((community) => community.id === stack.communityId)?.name || "Community";
    return `<section class="notification-stack${stack.unreadCount ? " has-unread" : ""}" aria-label="Posts from ${escapeHTML(communityName)}">
      <div class="notification-stack__head"><span class="notification-stack__mark">${icon("users", 13)}</span><span><strong>${escapeHTML(communityName)}</strong><small>${stack.notifications.length} post${stack.notifications.length === 1 ? "" : "s"}</small></span>${stack.unreadCount ? `<b>${stack.unreadCount}</b>` : ""}</div>
      <div class="notification-stack__items">${stack.notifications.map(renderItem).join("")}</div>
    </section>`;
  }).join("");
  return `<div class="popover notifications-popover" role="dialog" aria-label="Notifications">
    <div class="popover__head">
      <div><span class="eyebrow">Inbox</span><h3>Notifications</h3></div>
      <button class="text-link text-link--small" type="button" data-action="mark-notifications">Mark all read</button>
    </div>
    <div class="notification-list">
      ${stackedPosts}${standalone.map(renderItem).join("") || (!stacks.length ? `<p class="notification-list__empty">You’re all caught up. New community updates will appear here.</p>` : "")}
    </div>
    <div class="popover__foot">${icon("check", 13)} All caught up? You can mark everything as read.</div>
  </div>`;
}

function renderMobileNav(routeKey) {
  return `<nav class="mobile-nav" aria-label="Mobile navigation">
    ${Object.entries(ROUTES)
      .filter(([key]) => key !== "community")
      .map(
        ([key, route]) => {
          const active = routeKey === key || (key === "communities" && routeKey === "community");
          const label = {
            home: "Home",
            communities: "Clubs",
            polls: "Polls",
            teams: "Team",
            plans: "Plans",
            pickup: "Pickup",
            calendar: "Calendar",
          }[key];
          return `<a class="mobile-nav__item${active ? " is-active" : ""}" href="#/${key}"${active ? ' aria-current="page"' : ""}>
          <span>${icon(
            { home: "home", communities: "users", polls: "poll", teams: "team", plans: "clipboard", pickup: "shuffle", calendar: "calendar" }[key],
            19,
          )}</span>
          <small>${label}</small>
        </a>`;
        },
      )
      .join("")}
  </nav>`;
}

function renderSearchResults(query) {
  const q = query.trim().toLowerCase();
  const results = [];
  if (q) {
    state.communities.filter((community) => community.joined || community.privacy === "Public").forEach((community) => results.push({
        type: "community",
        id: community.id,
        title: community.name,
        meta: `${community.sport} · ${countLabel(community.memberCount)} members`,
        keywords: community.description,
        icon: communityMark(community, "xxs"),
      }));
    state.polls.forEach((poll) => results.push({
        type: "poll",
        id: poll.id,
        title: poll.question,
        meta: `${poll.category} poll · ${isOpen(poll.closesAt) ? "Open" : "Closed"}`,
        icon: `<span class="search-result__glyph">${icon("poll", 15)}</span>`,
      }));
    (currentTeam()?.players ?? []).forEach((player) => results.push({
        type: "player",
        id: player.id,
        title: player.name,
        meta: `#${player.number} · ${player.pos} · ${player.status}`,
        keywords: player.group,
        icon: avatar(player.name, { size: "xxs" }),
      }));
    state.plans.forEach((plan) => results.push({
        type: "plan",
        id: plan.id,
        title: plan.title,
        meta: `vs ${plan.opponent} · ${formatDate(plan.date)}`,
        keywords: plan.competition,
        icon: `<span class="search-result__glyph">${icon("clipboard", 15)}</span>`,
      }));
  } else {
    state.communities.filter((community) => community.joined || community.privacy === "Public")
      .sort((a, b) => Number(b.joined) - Number(a.joined) || b.memberCount - a.memberCount)
      .slice(0, 3)
      .forEach((community, index) => results.push({
        type: "community", id: community.id, title: community.name,
        meta: `${community.sport} · ${community.joined ? "Your community" : "Discover"}`,
        recommendationScore: 100 - index, icon: communityMark(community, "xxs"),
      }));
    state.polls.filter((poll) => isOpen(poll.closesAt)).slice(0, 2).forEach((poll, index) => results.push({
      type: "poll", id: poll.id, title: poll.question, meta: `${poll.category} poll · Open`,
      recommendationScore: 70 - index, icon: `<span class="search-result__glyph">${icon("poll", 15)}</span>`,
    }));
    (currentTeam()?.players ?? []).slice(0, 2).forEach((player, index) => results.push({
      type: "player", id: player.id, title: player.name,
      meta: `#${player.number} · ${player.pos} · ${player.status}`,
      recommendationScore: 50 - index, icon: avatar(player.name, { size: "xxs" }),
    }));
  }

  const ranked = rankSearchResults(results, q, 7);
  return `<div class="search-results__card">
    <div class="search-results__head"><span>${q ? "Best matches" : "Recommended for you"}</span><span>${q ? `${ranked.length} found` : "Suggestions"}</span></div>
    ${
      ranked.length
        ? ranked
            .map(
              (result) => `<button class="search-result" type="button" data-action="search-jump" data-type="${result.type}" data-id="${escapeHTML(result.id)}">
                ${result.icon}
                <span class="search-result__copy"><strong>${escapeHTML(result.title)}</strong><small>${escapeHTML(result.meta)}</small></span>
                <span class="search-result__type">${result.type}</span>
                ${icon("arrowUpRight", 13)}
              </button>`,
            )
            .join("")
        : `<div class="search-results__empty">${icon("search", 20)}<p>No results for “${escapeHTML(query)}”. Try a community, player, poll or game plan.</p></div>`
    }
  </div>`;
}

function navigate(route) {
  const next = `#/${route}`;
  if (window.location.hash === next) {
    renderApp({ scrollTop: true });
  } else {
    window.location.hash = next;
  }
}

function renderMessengerPanel() {
  const community = state?.communities?.find((item) => item.id === ui.messengerCommunityId);
  if (!community) return "";
  if (ui.messengerMinimized) return `<button class="community-messenger-launcher" type="button" data-action="restore-messenger-panel" data-community="${escapeHTML(community.id)}">${icon("message", 17)}<span>${escapeHTML(community.name)} chat</span>${community.unreadCount ? `<b class="chat-unread-badge">${community.unreadCount}</b>` : ""}</button>`;
  const messages = ui.messengerMessages.map((message) => {
    const own = message.author.id === state.user?.id;
    const timestamp = new Date(message.createdAt);
    const timeLabel = Number.isNaN(timestamp.valueOf()) ? "" : formatTime(timestamp);
    const author = own ? "You" : escapeHTML(message.author.name);
    return `<article class="community-messenger__message-row${own ? " is-own" : " is-other"}">${own ? "" : avatar(message.author.name, { size: "xs", tone: message.author.avatarTone })}<div class="community-messenger__message${own ? " is-own" : " is-other"}"><strong>${author}</strong>${ui.editingMessageId === message.id ? `<form class="community-messenger__edit-form" data-form="edit-community-message" data-community="${escapeHTML(community.id)}" data-message="${escapeHTML(message.id)}"><textarea name="text" rows="2" maxlength="1000" required aria-label="Edit message">${escapeHTML(message.text)}</textarea><div><button class="btn btn--primary" type="submit">Save</button><button class="btn btn--light" type="button" data-action="cancel-edit-community-message">Cancel</button></div></form>` : `<p>${escapeHTML(message.text)}</p>${message.editedAt ? `<small class="community-messenger__edited">Edited</small>` : ""}${own ? `<div class="community-messenger__message-actions"><button type="button" data-action="edit-community-message" data-message="${escapeHTML(message.id)}" aria-label="Edit your message">Edit</button><button type="button" data-action="delete-community-message" data-community="${escapeHTML(community.id)}" data-message="${escapeHTML(message.id)}" aria-label="Delete your message">Delete</button></div>` : ""}`}<small class="community-messenger__timestamp"><time datetime="${escapeHTML(message.createdAt)}" title="${escapeHTML(timestamp.toLocaleString())}">${timeLabel}</time></small></div></article>`;
  }).join("");
  return `<aside class="community-messenger" aria-label="${escapeHTML(community.name)} chat">
    <header class="community-messenger__head"><div class="community-messenger__heading"><span class="community-messenger__community-avatar">${escapeHTML(community.mark)}</span><span class="community-messenger__heading-copy"><strong>${escapeHTML(community.name)}</strong><small>${community.memberCount} members · Community chat</small></span>${community.unreadCount ? `<b class="chat-unread-badge">${community.unreadCount}</b>` : ""}</div><button class="icon-button community-messenger__minimize" type="button" data-action="minimize-messenger-panel" aria-label="Minimize chat">${icon("minus", 16)}</button></header>
    <div class="community-messenger__messages" aria-live="polite">${ui.messengerLoading ? `<p class="community-messenger__empty">Loading messages…</p>` : messages || `<div class="community-messenger__welcome"><span>${icon("message", 22)}</span><strong>Welcome to ${escapeHTML(community.name)}</strong><p>Start the conversation with your community.</p></div>`}</div>
    <form class="community-messenger__form" data-form="community-messenger-chat" data-community="${escapeHTML(community.id)}"><div class="community-messenger__composer"><textarea name="text" rows="1" maxlength="1000" placeholder="Message ${escapeHTML(community.name)}… Use @ to mention" aria-label="Write a message" required>${escapeHTML(ui.messengerDraft)}</textarea><div class="community-messenger__mention-suggestions" role="listbox" aria-label="Community members" hidden></div><small class="community-messenger__composer-hint">Enter to send · Shift + Enter for a new line</small></div><button class="community-messenger__send btn btn--primary" type="submit" aria-label="Send message">${icon("arrowRight", 17)}<span>Send</span></button></form>
  </aside>`;
}

function mountMessengerPanel() {
  const dialog = getModal();
  const existingMessages = document.querySelector(".community-messenger__messages");
  const wasAtBottom = ui.messengerForceScrollToBottom || (existingMessages
    ? existingMessages.scrollHeight - existingMessages.scrollTop - existingMessages.clientHeight <= 48
    : ui.messengerIsAtBottom);
  const previousMessageScroll = existingMessages?.scrollTop ?? ui.messengerScrollTop;
  const existingComposer = document.querySelector(".community-messenger__form textarea[name=text]");
  if (existingComposer) ui.messengerDraft = existingComposer.value;
  const keepFocus = existingComposer && document.activeElement === existingComposer;
  const selectionStart = existingComposer?.selectionStart ?? ui.messengerDraft.length;
  const selectionEnd = existingComposer?.selectionEnd ?? ui.messengerDraft.length;
  document.querySelectorAll(".community-messenger, .community-messenger-launcher").forEach((node) => node.remove());
  if (!ui.messengerCommunityId || !state?.communities?.some((item) => item.id === ui.messengerCommunityId)) return;
  const host = dialog?.open ? dialog : document.querySelector("#app");
  host?.insertAdjacentHTML("beforeend", renderMessengerPanel());
  const nextMessages = host?.querySelector(".community-messenger__messages");
  if (nextMessages) {
    nextMessages.scrollTop = wasAtBottom ? nextMessages.scrollHeight : previousMessageScroll;
    ui.messengerScrollTop = nextMessages.scrollTop;
    ui.messengerIsAtBottom = wasAtBottom;
  }
  ui.messengerForceScrollToBottom = false;
  const nextComposer = host?.querySelector(".community-messenger__form textarea[name=text]");
  if (nextComposer && !ui.messengerMinimized) {
    nextComposer.value = ui.messengerDraft;
    if (keepFocus) {
      nextComposer.focus({ preventScroll: true });
      nextComposer.setSelectionRange(selectionStart, selectionEnd);
    }
  }
}

function selectCommunityChat(communityId) {
  const community = state?.communities?.find((item) => item.id === communityId);
  if (!community?.joined) return;
  if (ui.messengerCommunityId !== communityId) {
    document.querySelectorAll(".community-messenger, .community-messenger-launcher").forEach((node) => node.remove());
    ui.messengerMessages = [];
    ui.messengerMembers = [];
    ui.messengerDraft = "";
    ui.messengerTaggedMembers = [];
    ui.messengerIsAtBottom = true;
    ui.messengerScrollTop = 0;
  }
  ui.messengerCommunityId = communityId;
  ui.messengerMinimized = true;
  ui.messengerLoading = false;
  mountMessengerPanel();
}

async function openMessengerPanel(communityId) {
  const community = state?.communities?.find((item) => item.id === communityId);
  if (!community?.joined) return;
  if (ui.messengerCommunityId !== communityId) {
    document.querySelectorAll(".community-messenger, .community-messenger-launcher").forEach((node) => node.remove());
    ui.messengerDraft = "";
    ui.messengerTaggedMembers = [];
    ui.messengerIsAtBottom = true;
    ui.messengerScrollTop = 0;
  }
  ui.messengerCommunityId = communityId;
  ui.messengerMinimized = false;
  ui.messengerForceScrollToBottom = true;
  ui.messengerMessages = [];
  ui.messengerLoading = true;
  mountMessengerPanel();
  try {
    ui.messengerMessages = await api.get(`/communities/${communityId}/messages`);
    ui.messengerMembers = await api.get(`/communities/${communityId}/members`);
    ui.messengerLoading = false;
    const current = state.communities.find((item) => item.id === communityId);
    if (current) current.unreadCount = 0;
    mountMessengerPanel();
  } catch (error) {
    ui.messengerCommunityId = null;
    ui.messengerLoading = false;
    mountMessengerPanel();
    handleApiError(error);
  }
}

async function showCommunityMembers(communityId) {
  try {
    const community = state.communities.find((item) => item.id === communityId);
    const [members, deletionRequest, joinRequests, pollRetention] = await Promise.all([
      api.get(`/communities/${communityId}/members`),
      api.get(`/communities/${communityId}/deletion-request`),
      community?.canManage ? api.get(`/communities/${communityId}/join-requests`) : Promise.resolve([]),
      community?.canManage ? api.get(`/communities/${communityId}/poll-retention-settings`) : Promise.resolve(null),
    ]);
    const adminCount = members.filter((member) => member.role === "Admin").length;
    const joinRequestPanel = joinRequests.length ? `<section class="community-join-requests"><div class="section-heading section-heading--small"><h3>Join requests</h3><span>${joinRequests.length} pending</span></div>${joinRequests.map((request) => `<article class="community-join-request"><div><strong>${escapeHTML(request.name)}</strong><span>${escapeHTML(request.email)} · Requested ${escapeHTML(new Date(request.requestedAt).toLocaleDateString())}</span></div><div><button class="btn btn--primary btn--sm" type="button" data-action="decide-community-join" data-community="${escapeHTML(communityId)}" data-user="${escapeHTML(request.userId)}" data-decision="approve">Approve</button><button class="btn btn--danger btn--sm" type="button" data-action="decide-community-join" data-community="${escapeHTML(communityId)}" data-user="${escapeHTML(request.userId)}" data-decision="deny">Decline</button></div></article>`).join("")}</section>` : `<p class="community-join-requests-empty">No pending join requests.</p>`;
    openModal({
      eyebrow: "Community access",
      title: `Members · ${community?.name ?? "Community"}`,
      description: "Review public community join requests, manage members, or share an invitation.",
      body: `${community?.canManage ? `<section class="community-theme-setting"><h3>Community appearance</h3><p>Choose a light or dark profile theme for this community.</p><form class="form" data-form="community-profile-theme" data-community="${escapeHTML(communityId)}"><label class="field"><span>Theme</span><select name="theme"><option value="light" ${community.profileTheme !== "dark" ? "selected" : ""}>Light</option><option value="dark" ${community.profileTheme === "dark" ? "selected" : ""}>Dark</option></select></label><div class="form-actions"><button class="btn btn--light btn--sm" type="submit">Save theme</button></div></form></section>` : ""}<div class="community-member-tools"><form class="form" data-form="add-community-member" data-community="${escapeHTML(communityId)}"><label class="field"><span>Registered user email</span><input name="email" type="email" required placeholder="player@example.com"></label><div class="form-actions"><button class="btn btn--primary" type="submit">Add member</button><button class="btn btn--light" type="button" data-action="share-community-invite" data-community="${escapeHTML(communityId)}">${icon("share", 15)} Copy invite link</button></div></form></div>${pollRetention ? `<section class="community-poll-retention"><h3>Poll cleanup</h3><p>Delete polls with their votes and results after this many days. Super-admin default: ${pollRetention.globalDays} days.</p><form class="form" data-form="community-poll-retention" data-community="${escapeHTML(communityId)}"><label class="field"><span>Keep polls (days)</span><input name="days" type="number" min="1" max="30" value="${pollRetention.days}" required></label><div class="form-actions"><button class="btn btn--light btn--sm" type="submit">Save retention</button></div></form></section>` : ""}${joinRequestPanel}<h3 class="community-members-title">Current members</h3><div class="member-list">${members.map((member) => `<div class="member-row"><div><strong>${escapeHTML(member.name)}</strong><span>${escapeHTML(member.email)}</span></div><span class="role-badge">${escapeHTML(member.role)}</span>${member.role === "Admin" ? adminCount > 1 ? `<button class="btn btn--ghost btn--sm" type="button" data-action="set-community-role" data-community="${escapeHTML(communityId)}" data-user="${escapeHTML(member.id)}" data-role="Member">Demote admin</button>` : `<span class="community-member-last-admin">Only admin</span>` : `<button class="btn btn--light btn--sm" type="button" data-action="set-community-role" data-community="${escapeHTML(communityId)}" data-user="${escapeHTML(member.id)}" data-role="Admin">Make admin</button>${member.id !== state.user.id ? `<button class="btn btn--danger btn--sm" type="button" data-action="remove-community-member" data-community="${escapeHTML(communityId)}" data-user="${escapeHTML(member.id)}" data-name="${escapeHTML(member.name)}">Remove member</button>` : ""}`}</div>`).join("")}</div>${renderCommunityDeletionControls(communityId, deletionRequest)}`,
    });
  } catch (error) { handleApiError(error); }
}

async function openCommunityDetail(communityId) {
  const community = state?.communities?.find((item) => item.id === communityId);
  if (!community) return;
  let members = [];
  if (community.joined || state.user?.role === "Super Admin") {
    try { members = await api.get(`/communities/${communityId}/members`); }
    catch (error) { handleApiError(error); }
  }
  openCommunityModal(state, communityId, ui, members);
  if (community.joined) selectCommunityChat(communityId);
}

async function openMatchdayReview(communityId, fixtureId) {
  try {
    const review = await api.get(`/communities/${communityId}/fixtures/${fixtureId}/ratings`);
    openModal({
      eyebrow: "Post-match review",
      title: `Rate the squad vs ${review.fixture.opponent}`,
      description: "Rate every player from 1 to 10. Leave feedback to help them improve.",
      body: `<form class="form matchday-review-form" data-form="matchday-review" data-community="${escapeHTML(communityId)}" data-fixture="${escapeHTML(fixtureId)}">
        <div class="matchday-review-grid">${review.players.map((player) => `<article class="matchday-review-player" data-player-id="${escapeHTML(player.id)}">
          ${avatar(player.name, { size: "md", imageData: player.imageData })}
          <div class="matchday-review-player__title"><strong>${escapeHTML(player.name)}</strong><small>#${escapeHTML(player.number)} · ${escapeHTML(player.position)}</small></div>
          <label class="field"><span>Performance rating</span><select data-rating required>${Array.from({ length: 10 }, (_, i) => i + 1).map((n) => `<option value="${n}"${Number(player.rating) === n ? " selected" : ""}>${n} / 10</option>`).join("")}</select></label>
          <label class="field"><span>Feedback (optional)</span><textarea data-feedback maxlength="500" rows="2" placeholder="What went well? What could improve?">${escapeHTML(player.feedback || "")}</textarea></label>
        </article>`).join("")}</div>
        <div class="form-actions"><button class="btn btn--ghost" type="button" data-action="close-modal">Cancel</button><button class="btn btn--primary" type="submit">Submit player ratings</button></div>
      </form>`,
    });
  } catch (error) { handleApiError(error); }
}

async function openMatchdayResults(communityId, fixtureId) {
  try {
    const results = await api.get(`/communities/${communityId}/fixtures/${fixtureId}/ratings`);
    if (!Array.isArray(results.results)) throw new Error("Only community admins can review the submitted feedback.");
    const content = results.players.map((player) => {
      const playerResponses = results.results.filter((item) => item.playerId === player.id);
      const average = playerResponses.length ? (playerResponses.reduce((sum, item) => sum + Number(item.rating), 0) / playerResponses.length).toFixed(1) : "—";
      return `<article class="matchday-result-player"><header>${avatar(player.name, { size: "sm", imageData: player.imageData })}<div><strong>${escapeHTML(player.name)}</strong><small>${playerResponses.length} ratings · average ${average}/10</small></div></header>${playerResponses.map((item) => `<p><strong>${escapeHTML(item.member)} · ${item.rating}/10</strong>${item.feedback ? `<span>${escapeHTML(item.feedback)}</span>` : `<span class="muted">No written feedback</span>`}</p>`).join("") || `<p class="muted">No ratings submitted yet.</p>`}</article>`;
    }).join("");
    openModal({ eyebrow: "Community admin", title: `Member feedback · ${results.fixture.opponent}`, description: "Player performance ratings and written feedback from community members.", body: `<div class="matchday-results">${content}</div><div class="modal-actions"><button class="btn btn--light" type="button" data-action="close-modal">Close</button></div>` });
  } catch (error) { handleApiError(error); }
}

async function openPollFeedback(pollId, resultsOnly = false) {
  try {
    const review = await api.get(`/polls/${encodeURIComponent(pollId)}/feedback`);
    if (resultsOnly) {
      if (!Array.isArray(review.results)) throw new Error("Only community admins can review submitted poll feedback.");
      const content = review.players.map((player) => {
        const responses = review.results.filter((item) => item.playerId === player.id);
        const average = responses.length ? (responses.reduce((sum, item) => sum + Number(item.rating), 0) / responses.length).toFixed(1) : "—";
        return `<article class="matchday-result-player"><header>${avatar(player.name, { size: "sm", imageData: player.imageData })}<div><strong>${escapeHTML(player.name)}</strong><small>${responses.length} ratings · average ${average}/10</small></div></header>${responses.map((item) => `<p><strong>${escapeHTML(item.member)} · ${item.rating}/10</strong><span>${escapeHTML(item.feedback || "No written feedback")}</span></p>`).join("") || `<p class="muted">No ratings submitted yet.</p>`}</article>`;
      }).join("");
      openModal({ eyebrow: "Community admin", title: "Poll player feedback", description: "Ratings and feedback submitted by poll voters.", body: `<div class="matchday-results">${content}</div><div class="modal-actions"><button class="btn btn--light" type="button" data-action="close-modal">Close</button></div>` });
      return;
    }
    openModal({ eyebrow: "Post-game feedback", title: "Rate the players", description: "Your ratings help the squad improve. Rate each player from 1 to 10.", body: `<form class="form matchday-review-form" data-form="poll-feedback" data-poll="${escapeHTML(pollId)}"><div class="matchday-review-grid">${review.players.map((player) => `<article class="matchday-review-player" data-player-id="${escapeHTML(player.id)}">${avatar(player.name, { size: "md", imageData: player.imageData })}<div class="matchday-review-player__title"><strong>${escapeHTML(player.name)}</strong><small>#${escapeHTML(player.number)} · ${escapeHTML(player.position)}</small></div><label class="field"><span>Performance rating</span><select data-rating required>${Array.from({ length: 10 }, (_, i) => i + 1).map((n) => `<option value="${n}"${Number(player.rating) === n ? " selected" : ""}>${n} / 10</option>`).join("")}</select></label><label class="field"><span>Feedback (optional)</span><textarea data-feedback maxlength="500" rows="2" placeholder="What went well? What could improve?">${escapeHTML(player.feedback || "")}</textarea></label></article>`).join("")}</div><div class="form-actions"><button class="btn btn--ghost" type="button" data-action="close-modal">Cancel</button><button class="btn btn--primary" type="submit">Submit player ratings</button></div></form>` });
  } catch (error) { handleApiError(error); }
}

function openPickupPollTeams(pollId) {
  const poll = state.polls.find((item) => item.id === pollId);
  if (!poll?.canManageTeams || !poll.autoTeams) return;
  const players = poll.yesPlayers ?? [];
  const result = poll.autoTeams;
  const storedNames = result.teamNames;
  const [teamAName, teamBName] = Array.isArray(storedNames) ? storedNames : storedNames ? [storedNames.teamA, storedNames.teamB] : pickupTeamNames(poll.id);
  const names = { teamA: teamAName, teamB: teamBName };
  const assignments = new Map(players.map((player) => [player.id, result.floater === player.id ? "floater" : result.teamA.includes(player.id) ? "teamA" : "teamB"]));
  openModal({ eyebrow: "Pickup builder", title: "Rearrange confirmed players", description: "Drag players between teams. For an odd roster, use the floater optionally; without one, teams can differ by one player.", body: `<form class="form pickup-poll-adjust" data-form="poll-team-rearrange" data-poll="${escapeHTML(poll.id)}">${renderPickupArrangeBoard(players, assignments, names, players.length % 2 === 1)}<div class="form-actions"><button class="btn btn--ghost" type="button" data-action="close-modal">Cancel</button><button class="btn btn--primary" type="submit">Save teams</button></div></form>` });
}

function renderPickupArrangeBoard(players, assignments, names, allowFloater) {
  const zone = (key, label) => `<section class="pickup-drop-zone" data-drop-zone="${key}"><h3>${escapeHTML(label)} <span data-zone-count></span></h3><div class="pickup-drop-zone__players">${players.filter((player) => assignments.get(player.id) === key).map((player) => `<article class="pickup-draggable-player" draggable="true" data-pickup-player="${escapeHTML(player.id)}"><span class="pickup-drag-grip" aria-hidden="true">⠿</span><span>${player.guest ? "Guest" : `#${player.number}`} ${escapeHTML(player.name)}</span></article>`).join("")}</div></section>`;
  return `<div class="pickup-drag-board">${zone("teamA", names.teamA)}${zone("teamB", names.teamB)}${allowFloater ? zone("floater", "Optional floater") : ""}</div><p class="pickup-drag-hint">Drag and drop any player to change their assignment.</p>`;
}

function openPickupBuilderTeams() {
  const players = getPickupPool(state, ui);
  if (!players.length) { toast("There are no available players to arrange.", "error"); return; }
  const result = getPickupResult(state, ui);
  const names = { teamA: result.teamNames?.[0] ?? "Yolo Blue", teamB: result.teamNames?.[1] ?? "Yolo Red" };
  const assignments = new Map(players.map((player) => [player.id, result.floater?.id === player.id ? "floater" : result.teamA.players.some((item) => item.id === player.id) ? "teamA" : "teamB"]));
  openModal({ eyebrow: "Pickup builder", title: "Arrange pickup teams", description: "Drag players between teams. For an odd roster, use the floater optionally; without one, teams can differ by one player.", body: `<form class="form pickup-poll-adjust" data-form="pickup-builder-rearrange">${renderPickupArrangeBoard(players, assignments, names, players.length % 2 === 1)}<div class="form-actions"><button class="btn btn--ghost" type="button" data-action="close-modal">Cancel</button><button class="btn btn--primary" type="submit">Save teams</button></div></form>` });
}

function renderCommunityDeletionControls(communityId, request) {
  if (!request || request.status === "denied") {
    return `<section class="community-deletion-controls"><strong>Delete community</strong><p>Deletion needs approval from every community admin and the super admin.</p>${request?.status === "denied" ? `<p class="community-deletion-status">The previous request was denied. You can submit a new request.</p>` : ""}<button class="btn btn--danger btn--sm community-deletion-request-button" type="button" data-action="request-community-deletion" data-community="${escapeHTML(communityId)}">Request deletion</button></section>`;
  }
  const myApproval = request.adminApprovals.find((approval) => approval.id === state.user.id);
  const waiting = request.status === "pending_admins";
  return `<section class="community-deletion-controls"><strong>Deletion approval · ${request.approvalCount}/${request.requiredApprovalCount} admins</strong><p>${waiting ? "Every admin must approve before the super admin reviews it." : "All community admins approved. Waiting for the super admin."}</p><div class="community-deletion-approvals">${request.adminApprovals.map((approval) => `<span class="${approval.approved ? "is-approved" : ""}">${escapeHTML(approval.name)} · ${approval.approved ? "Approved" : "Waiting"}</span>`).join("")}</div>${waiting && myApproval && !myApproval.approved ? `<button class="btn btn--danger" type="button" data-action="approve-community-deletion" data-community="${escapeHTML(communityId)}" data-request="${escapeHTML(request.id)}">Approve deletion request</button>` : ""}</section>`;
}

async function openSuperAdminDeletionSettings() {
  try {
    const panel = await api.get("/admin/community-deletions");
    openModal({
      eyebrow: "Super admin only",
      title: "Community deletion approvals",
      description: "Set how long newly approved requests wait for your decision. Requests with no decision are deleted automatically when this period ends.",
      body: `<div class="super-admin-deletion-panel"><form class="form" data-form="global-app-theme"><label class="field"><span>Application theme</span><select name="theme"><option value="light" ${panel.appTheme !== "dark" ? "selected" : ""}>Light</option><option value="dark" ${panel.appTheme === "dark" ? "selected" : ""}>Dark</option></select></label><small>Applies across the app unless a community profile has its own theme.</small><div class="form-actions"><button class="btn btn--primary" type="submit">Save app theme</button></div></form><form class="form" data-form="global-poll-retention"><label class="field"><span>Default poll retention (days)</span><input name="days" type="number" min="1" max="30" value="${Number(panel.pollRetentionDays ?? 7)}" required></label><small>Community admins can set a different retention period for their community.</small><div class="form-actions"><button class="btn btn--primary" type="submit">Save poll retention</button></div></form><form class="form" data-form="community-deletion-timeout"><label class="field"><span>Super-admin decision window (days)</span><input name="days" type="number" min="1" max="30" value="${Number(panel.timeoutDays)}" required></label><div class="form-actions"><button class="btn btn--primary" type="submit">Save setting</button></div></form><h3>Open requests</h3>${panel.requests.length ? panel.requests.map((request) => `<article class="super-admin-deletion-request"><div><strong>${escapeHTML(request.communityName)}</strong><span>${request.approvalCount}/${request.requiredApprovalCount} community admins approved</span>${request.status === "pending_super_admin" ? `<small>Decision due ${escapeHTML(new Date(request.superAdminDueAt).toLocaleString())}</small>` : `<small>Waiting for all community admins</small>`}</div>${request.status === "pending_super_admin" ? `<div class="form-actions"><button class="btn btn--danger" type="button" data-action="super-admin-deletion-decision" data-decision="approve" data-request="${escapeHTML(request.id)}" data-community-name="${escapeHTML(request.communityName)}">Approve and delete</button><button class="btn btn--light" type="button" data-action="super-admin-deletion-decision" data-decision="deny" data-request="${escapeHTML(request.id)}">Deny</button></div>` : ""}</article>`).join("") : `<p class="community-deletion-status">No open deletion requests.</p>`}</div>`,
    });
  } catch (error) { handleApiError(error); }
}

async function openApiKeyAccess(secret = null) {
  try {
    const access = await api.get("/me/api-key");
    const request = access.request;
    const body = secret
      ? `<div class="api-key-issued"><p class="role-badge">Copy this key now. It will not be shown again.</p><code>${escapeHTML(secret)}</code><button class="btn btn--primary" type="button" data-action="copy-api-key" data-api-key="${escapeHTML(secret)}">${icon("copy", 15)} Copy API key</button><p>Send it as the <code>X-API-Key</code> header over HTTPS. Keep it private.</p></div>`
      : access.activeKey
        ? `<div class="api-key-current"><p>Your approved key is active. The secret is shown only once when issued.</p><code>${escapeHTML(access.activeKey.prefix)}…</code><small>Created ${escapeHTML(new Date(access.activeKey.createdAt).toLocaleString())}</small><button class="btn btn--danger" type="button" data-action="revoke-api-key">Revoke API key</button></div>`
        : access.canClaim
          ? `<p class="profile-note">The super admin approved your request. Claim your key to display it once.</p><button class="btn btn--primary" type="button" data-action="claim-api-key">${icon("key", 15)} Create and show my key</button>`
          : request?.status === "pending"
            ? `<p class="community-deletion-status">Your request is waiting for super-admin approval.</p><p>${escapeHTML(request.reason)}</p>`
            : `<form class="form" data-form="api-key-request"><label class="field"><span>What will use the API?</span><textarea name="reason" maxlength="300" minlength="10" required placeholder="Describe the integration and what data it needs."></textarea></label><div class="form-actions"><button class="btn btn--primary" type="submit">Request API access</button></div></form>`;
    openModal({ eyebrow: "API access", title: "API key access", description: "API keys are issued after super-admin approval. Use the key only in a trusted server-side integration; do not put it in browser code or public repositories.", body: `<div class="api-key-access">${body}</div>` });
  } catch (error) { handleApiError(error); }
}

async function openSuperAdminApiKeyRequests() {
  try {
    const requests = await api.get("/admin/api-key-requests");
    openModal({
      eyebrow: "Super admin only",
      title: "API key requests",
      description: "Review each request before the account can claim a private API key.",
      body: `<div class="super-admin-api-key-requests">${requests.length ? requests.map((request) => `<article class="super-admin-deletion-request"><div><strong>${escapeHTML(request.name)} · ${escapeHTML(request.email)}</strong><span>${escapeHTML(request.reason)}</span><small>Requested ${escapeHTML(new Date(request.requestedAt).toLocaleString())}</small></div><div class="form-actions"><button class="btn btn--primary" type="button" data-action="api-key-request-decision" data-request="${escapeHTML(request.id)}" data-decision="approve">Approve</button><button class="btn btn--danger" type="button" data-action="api-key-request-decision" data-request="${escapeHTML(request.id)}" data-decision="deny">Decline</button></div></article>`).join("") : `<p class="community-deletion-status">No pending API key requests.</p>`}</div>`,
    });
  } catch (error) { handleApiError(error); }
}

function refresh({ preserveScroll = true } = {}) {
  renderApp({ preserveScroll });
}

async function handleAction(action, element) {
  switch (action) {
    case "google-signin": {
      const query = new URLSearchParams(window.location.search);
      const result = await api.post("/auth/google/start", {
        ...(ui.playerInviteToken ? { playerInvite: ui.playerInviteToken } : {}),
        ...(query.get("community_invite") ? { communityInvite: query.get("community_invite") } : {}),
      });
      window.location.assign(result.authorizationUrl);
      break;
    }
    case "auth-mode":
      ui.authMode = element.dataset.mode;
      ui.authMessage = "";
      document.querySelector("#app").innerHTML = renderAuthScreen();
      break;
    case "new-post":
      openNewPostModal(state, element.dataset.community || currentCommunityRoute()?.communityId || ui.communityFilterId);
      break;
    case "new-poll":
      openNewPollModal(element.dataset.community || currentCommunityRoute()?.communityId || null, state.communities.filter((community) => community.joined));
      break;
    case "new-community":
      openNewCommunityModal(state);
      break;
    case "edit-community-branding": {
      const community = state.communities.find((item) => item.id === element.dataset.community);
      if (community?.canManage) openCommunityBrandingModal(community);
      break;
    }
    case "request-matchday-ratings": {
      const result = await api.post(`/communities/${element.dataset.community}/fixtures/${element.dataset.fixture}/ratings/request`, {});
      toast(`Rating request emailed to ${result.sentTo} community members.`, "success");
      break;
    }
    case "view-matchday-ratings":
      await openMatchdayResults(element.dataset.community, element.dataset.fixture);
      break;
    case "go-communities":
      navigate("communities");
      break;
    case "new-team":
      openNewTeamModal(state);
      break;
    case "new-plan":
      openNewPlanModal(state);
      break;
    case "edit-plan": {
      const plan = state.plans.find((item) => item.id === element.dataset.plan);
      if (plan) openEditPlanModal(plan);
      break;
    }
    case "save-plan-board":
      await savePlanBoard();
      break;
    case "auto-plan-board":
      autoArrangePlanBoard();
      break;
    case "clear-plan-board":
      ui.planBoardDraft = Array(11).fill(null);
      ui.planBoardSelectedPlayer = null;
      refresh({ preserveScroll: true });
      break;
    case "close-modal":
      closeModal();
      break;
    case "home-tab":
      ui.homeTab = element.dataset.tab;
      ui.communityFilterId = null;
      refresh();
      break;
    case "like-post": {
      const postId = element.dataset.post;
      await apiCommit(() => api.post(`/posts/${postId}/like`));
      break;
    }
    case "delete-post": {
      const post = state.posts.find((item) => item.id === element.dataset.post);
      if (!post || !window.confirm("Delete this post and its comments? This cannot be undone.")) break;
      await api.delete(`/posts/${post.id}`);
      await syncFromServer();
      toast("Post deleted.", "success");
      break;
    }
    case "toggle-comments": {
      const id = element.dataset.post;
      if (ui.openComments.includes(id)) {
        ui.openComments = ui.openComments.filter((postId) => postId !== id);
      } else {
        ui.openComments.push(id);
      }
      refresh();
      break;
    }
    case "share-post": {
      const post = state.posts.find((item) => item.id === element.dataset.post);
      const community = state.communities.find((item) => item.id === post?.communityId);
      copyText(
        `${community?.name ?? "Touchline"} on Touchline: “${post?.text ?? ""}”`,
        "Post link copied — share it with the squad.",
      );
      break;
    }
    case "vote-poll":
      await votePoll(element.dataset.poll, element.dataset.option);
      break;
    case "filter-sport":
      ui.sportFilter = element.dataset.sport;
      ui.showAllDiscover = false;
      refresh();
      break;
    case "toggle-discover-more":
      ui.showAllDiscover = !ui.showAllDiscover;
      refresh({ preserveScroll: true });
      break;
    case "open-community":
      if (state.communities.find((item) => item.id === element.dataset.community)?.joined) {
        ui.communityFilterId = null;
        const next = `#/community/${encodeURIComponent(element.dataset.community)}`;
        if (window.location.hash === next) selectCommunityChat(element.dataset.community);
        else window.location.hash = next;
      } else await openCommunityDetail(element.dataset.community);
      break;
    case "manage-community-members":
      await showCommunityMembers(element.dataset.community);
      break;
    case "request-community-deletion": {
      const communityId = element.dataset.community;
      if (!window.confirm("Open a community deletion request? Every community admin and the super admin must approve it.")) break;
      await api.post(`/communities/${communityId}/deletion-requests`, {});
      await showCommunityMembers(communityId);
      toast("Deletion request opened. All community admins must approve it.", "success");
      break;
    }
    case "approve-community-deletion": {
      const communityId = element.dataset.community;
      await api.post(`/communities/${communityId}/deletion-requests/${element.dataset.request}/approve`, {});
      await showCommunityMembers(communityId);
      toast("Your approval was recorded.", "success");
      break;
    }
    case "open-super-admin-deletion-settings":
      await openSuperAdminDeletionSettings();
      break;
    case "open-api-key-access":
      await openApiKeyAccess();
      break;
    case "open-super-admin-api-key-requests":
      await openSuperAdminApiKeyRequests();
      break;
    case "api-key-request-decision": {
      const decision = element.dataset.decision;
      await api.post(`/admin/api-key-requests/${element.dataset.request}/decision`, { decision });
      await openSuperAdminApiKeyRequests();
      toast(decision === "approve" ? "API key request approved." : "API key request declined.", "success");
      break;
    }
    case "claim-api-key": {
      const issued = await api.post("/me/api-key-claim", {});
      await openApiKeyAccess(issued.apiKey);
      break;
    }
    case "revoke-api-key":
      if (!window.confirm("Revoke your active API key? Any integrations using it will stop working.")) break;
      await api.delete("/me/api-key");
      await openApiKeyAccess();
      toast("API key revoked.", "success");
      break;
    case "copy-api-key":
      await copyText(element.dataset.apiKey, "API key copied. Store it somewhere safe.");
      break;
    case "super-admin-deletion-decision": {
      const decision = element.dataset.decision;
      const name = element.dataset.communityName || "this community";
      if (decision === "approve" && !window.confirm(`Approve deletion of ${name}? This permanently removes its community, team, roster, messages, posts, and events.`)) break;
      await api.post(`/admin/community-deletions/${element.dataset.request}/decision`, { decision });
      await openSuperAdminDeletionSettings();
      toast(decision === "approve" ? `${name} was deleted.` : "Deletion request denied.", "success");
      break;
    }
    case "share-community-invite": {
      try {
        const invite = await api.post(`/communities/${element.dataset.community}/invites`, {});
        await copyText(invite.url, "Seven day invite link copied. Share it with your community.");
      } catch (error) { handleApiError(error); }
      break;
    }
    case "set-community-role": {
      const communityId = element.dataset.community;
      const userId = element.dataset.user;
      await api.patch(`/communities/${communityId}/members/${userId}`, { role: element.dataset.role });
      await syncFromServer();
      await showCommunityMembers(communityId);
      toast("Community role updated.", "success");
      break;
    }
    case "remove-community-member": {
      const communityId = element.dataset.community;
      const name = element.dataset.name || "this member";
      if (!window.confirm(`Remove ${name} from this community? They can rejoin later if invited.`)) break;
      await api.delete(`/communities/${communityId}/members/${element.dataset.user}`);
      await syncFromServer();
      await showCommunityMembers(communityId);
      toast(`${name} was removed from the community.`, "success");
      break;
    }
    case "open-community-chat": {
      await openMessengerPanel(element.dataset.community);
      break;
    }
    case "minimize-messenger-panel":
      ui.messengerMinimized = true;
      mountMessengerPanel();
      break;
    case "restore-messenger-panel":
      await openMessengerPanel(element.dataset.community);
      break;
    case "edit-community-message":
      ui.editingMessageId = element.dataset.message;
      mountMessengerPanel();
      document.querySelector(".community-messenger__edit-form textarea")?.focus();
      break;
    case "cancel-edit-community-message":
      ui.editingMessageId = null;
      mountMessengerPanel();
      break;
    case "insert-chat-mention": {
      const textarea = element.closest(".community-messenger__form")?.querySelector("textarea[name=text]");
      if (!textarea) break;
      const cursor = textarea.selectionStart;
      const before = textarea.value.slice(0, cursor);
      const match = /@[^\s@]*$/.exec(before);
      if (!match) break;
      const member = ui.messengerMembers.find((item) => item.id === element.dataset.user);
      if (!member) break;
      const start = cursor - match[0].length;
      const tagged = `@${member.name} `;
      textarea.value = before.slice(0, start) + tagged + textarea.value.slice(cursor);
      ui.messengerDraft = textarea.value;
      const nextCursor = start + tagged.length;
      textarea.setSelectionRange(nextCursor, nextCursor);
      if (!ui.messengerTaggedMembers.some((item) => item.id === member.id)) ui.messengerTaggedMembers.push({ id: member.id, name: member.name });
      element.closest(".community-messenger__mention-suggestions").hidden = true;
      textarea.focus();
      break;
    }
    case "delete-community-message": {
      const communityId = element.dataset.community;
      const messageId = element.dataset.message;
      if (!window.confirm("Delete this message? This cannot be undone.")) break;
      await api.delete(`/communities/${communityId}/messages/${messageId}`);
      ui.messengerMessages = await api.get(`/communities/${communityId}/messages`);
      mountMessengerPanel();
      break;
    }
    case "community-feed":
      ui.communityFilterId = null;
      closeModal();
      clearSearch();
      {
        const next = `#/community/${encodeURIComponent(element.dataset.community)}`;
        if (window.location.hash === next) selectCommunityChat(element.dataset.community);
        else window.location.hash = next;
      }
      break;
    case "community-calendar":
      ui.calendarCommunityId = element.dataset.community;
      window.location.hash = "#/calendar";
      break;
    case "open-post":
      ui.communityFilterId = null;
      {
        const next = `#/community/${encodeURIComponent(element.dataset.community)}/posts/${encodeURIComponent(element.dataset.post)}`;
        if (window.location.hash === next) selectCommunityChat(element.dataset.community);
        else window.location.hash = next;
      }
      break;
    case "clear-community-filter":
      ui.communityFilterId = null;
      refresh();
      break;
    case "join-community": {
      const community = state.communities.find((item) => item.id === element.dataset.community);
      if (!community || community.joined) break;
      const result = state.user.role === "Super Admin"
        ? await api.post(`/communities/${community.id}/join`, {})
        : await api.post(`/communities/${community.id}/join-requests`, {});
      await syncFromServer();
      closeModal();
      refresh();
      if (result.joined) {
        toast(`You joined ${community.name}.`, "success");
        if (currentCommunityRoute()?.communityId === community.id) selectCommunityChat(community.id);
      } else {
        toast(`Your request to join ${community.name} was sent to its admins.`, "success");
      }
      break;
    }
    case "decide-community-join": {
      const communityId = element.dataset.community;
      const userId = element.dataset.user;
      const decision = element.dataset.decision;
      const verb = decision === "approve" ? "Approve" : "Decline";
      if (!window.confirm(`${verb} this request to join the community?`)) break;
      await api.post(`/communities/${communityId}/join-requests/${userId}/decision`, { decision });
      await syncFromServer();
      await showCommunityMembers(communityId);
      toast(decision === "approve" ? "Member join request approved." : "Member join request declined.", "success");
      break;
    }
    case "poll-tab":
      ui.pollTab = element.dataset.tab;
      ui.pollsShowMore = false;
      refresh();
      break;
    case "filter-polls":
      ui.pollFilter = element.dataset.filter;
      ui.pollsShowMore = false;
      refresh();
      break;
    case "toggle-polls-show-more":
      ui.pollsShowMore = !ui.pollsShowMore;
      refresh();
      break;
    case "toggle-poll-card":
      ui.expandedPollCards = ui.expandedPollCards.includes(element.dataset.poll)
        ? ui.expandedPollCards.filter((id) => id !== element.dataset.poll)
        : [...ui.expandedPollCards, element.dataset.poll];
      refresh();
      break;
    case "toggle-poll-options":
      ui.expandedPollOptions = ui.expandedPollOptions.includes(element.dataset.poll)
        ? ui.expandedPollOptions.filter((id) => id !== element.dataset.poll)
        : [...ui.expandedPollOptions, element.dataset.poll];
      refresh();
      break;
    case "edit-pickup-poll-teams":
      openPickupPollTeams(element.dataset.poll);
      break;
    case "edit-pickup-builder-teams":
      openPickupBuilderTeams();
      break;
    case "rate-poll-players":
      await openPollFeedback(element.dataset.poll);
      break;
    case "view-poll-feedback":
      await openPollFeedback(element.dataset.poll, true);
      break;
    case "team-tab":
      ui.teamTab = element.dataset.tab;
      ui.lineupSelected = null;
      refresh();
      break;
    case "filter-position":
      ui.positionFilter = element.dataset.position;
      document.querySelectorAll('[data-action="filter-position"]').forEach((button) => {
        button.classList.toggle("is-active", button.dataset.position === ui.positionFilter);
      });
      applyRosterFilter();
      break;
    case "toggle-pickup-doubtful":
      ui.pickupIncludeDoubtful = !ui.pickupIncludeDoubtful;
      ui.pickupManualSplit = null;
      ui.pickupVariant += 1;
      refresh();
      break;
    case "toggle-pickup-position":
      ui.pickupPositionAware = !ui.pickupPositionAware;
      ui.pickupManualSplit = null;
      ui.pickupVariant += 1;
      refresh();
      break;
    case "shuffle-teams":
      ui.pickupManualSplit = null;
      ui.pickupVariant = (ui.pickupVariant + 1) % 100000;
      refresh();
      toast("Fresh balanced teams generated.", "success");
      break;
    case "copy-pickup-teams":
      copyPickupTeams();
      break;
    case "pick-rating": {
      const form = element.closest('form[data-form="rate-player"]');
      if (!form) break;
      const value = element.dataset.value;
      const input = form.querySelector('input[name="rating"]');
      if (input) input.value = value;
      form.querySelectorAll('[data-action="pick-rating"]').forEach((button) => {
        const isSelected = button.dataset.value === value;
        button.classList.toggle("is-active", isSelected);
        button.setAttribute("aria-pressed", String(isSelected));
      });
      const output = form.querySelector(".rating-pick-value");
      if (output) output.textContent = value;
      break;
    }
    case "open-player":
      openPlayerModal(state, element.dataset.player);
      break;
    case "add-player":
      openAddPlayerModal(currentTeam()?.id);
      break;
    case "lineup-add-player": {
      const team = currentTeam();
      const slot = Number(element.dataset.slot);
      if (!team) break;
      if (ui.lineupSelected) {
        await handleLineupPick("pitch", "", slot);
        break;
      }
      const benchPlayers = team.players.filter((player) => !team.startingXI.includes(player.id) && player.registered);
      const buttons = benchPlayers.map((player) => `<button class="btn btn--ghost lineup-player-option" type="button" data-action="lineup-select-player" data-player="${escapeHTML(player.id)}" data-slot="${slot}">#${player.number} · ${escapeHTML(player.name)} · ${escapeHTML(player.pos)}</button>`).join("");
      openModal({ eyebrow: "Starting XI", title: `Choose ${element.closest(".pitch-player")?.querySelector(".pitch-player__role")?.textContent || "a player"}`, description: "Choose a registered squad player, or add someone by email and send them a registration link.", body: `<div class="form">${buttons || `<p class="form-note">No registered bench players are available yet.</p>`}<button class="btn btn--lime" type="button" data-action="lineup-invite-player" data-slot="${slot}">${icon("userPlus",16)} Add player by email</button><button class="btn btn--ghost" type="button" data-action="close-modal">Cancel</button></div>` });
      break;
    }
    case "lineup-select-player": {
      const team = currentTeam();
      const playerId = element.dataset.player;
      const slot = Number(element.dataset.slot);
      if (!team || !Number.isInteger(slot) || slot < 0 || slot > 10) break;
      const next = [...team.startingXI];
      while (next.length < 11) next.push(null);
      const oldSlot = next.indexOf(playerId);
      if (oldSlot >= 0) [next[oldSlot], next[slot]] = [next[slot], next[oldSlot]];
      else next[slot] = playerId;
      const savedLineup = await apiCommit(() => api.patch(`/teams/${team.id}`, { starting_xi: next }), { successMessage: "Registered player added to the Starting XI.", preserveScroll: true });
      if (savedLineup) closeModal();
      break;
    }
    case "lineup-invite-player":
      closeModal();
      openAddPlayerModal(currentTeam()?.id, Number(element.dataset.slot));
      break;
    case "edit-player": {
      const pid = element.dataset.player;
      openPlayerModal(state, pid);
      break;
    }
    case "delete-player": {
      const pid = element.dataset.player;
      const pdata = currentTeam()?.players.find((item) => item.id === pid);
      if (!pdata) break;
      if (!window.confirm(`Remove ${pdata.name} from the squad? This cannot be undone.`)) break;
      await apiCommit(
        () => api.delete(`/players/${pid}`),
        { successMessage: `${pdata.name} removed from the squad.`, closeAfter: false },
      );
      navigate("teams");
      break;
    }
    case "calendar-prev":
    case "calendar-next":
      ui.calendarMonth = shiftMonth(ui.calendarMonth ?? monthKey(), action === "calendar-next" ? 1 : -1);
      await loadCalendar();
      refresh();
      break;
    case "calendar-today":
      ui.calendarMonth = monthKey();
      ui.calendarDay = localDayKey(new Date());
      await loadCalendar();
      refresh();
      break;
    case "calendar-day":
      ui.calendarDay = element.dataset.date;
      ui.calendarMonth = element.dataset.date.slice(0, 7);
      await loadCalendar();
      refresh();
      break;
    case "new-duty":
      {
        const communityId = ui.calendarCommunityId;
        const [members, communities] = await Promise.all([
          api.get(`/communities/${communityId}/members`), Promise.resolve(state.communities),
        ]);
        const community = communities.find((item) => item.id === communityId);
        openNewDutyModal({ ...state, dutyCommunityId: communityId, dutyMembers: members,
          dutyCanAssignOthers: state.user.role === "Super Admin" || Boolean(community?.canManage) }, element.dataset.date || ui.calendarDay);
      }
      break;
    case "add-duty-item": {
      const form = element.closest("form[data-form='new-duty']");
      const container = form?.querySelector("[data-duty-items]");
      if (!container || container.children.length >= 10) break;
      const first = container.firstElementChild.cloneNode(true);
      first.querySelector("[data-duty-kind]").value = "coffee";
      first.querySelector("[data-duty-item-title]").textContent = `Item ${container.children.length + 1}`;
      first.querySelectorAll("[data-action='select-duty-kind']").forEach((button) => {
        const selected = button.dataset.kind === "coffee";
        button.classList.toggle("is-selected", selected);
        button.setAttribute("aria-pressed", String(selected));
      });
      first.querySelector(".duty-kind-entry__head").insertAdjacentHTML("beforeend", `<button class="icon-button duty-kind-entry__remove" type="button" data-action="remove-duty-item" aria-label="Remove item">${icon("close", 14)}</button>`);
      container.append(first);
      break;
    }
    case "select-duty-kind": {
      const row = element.closest(".duty-kind-entry");
      const selected = element.dataset.kind;
      if (!row || !DUTY_KINDS.some((kind) => kind.id === selected)) break;
      row.querySelector("[data-duty-kind]").value = selected;
      row.querySelectorAll("[data-action='select-duty-kind']").forEach((button) => {
        const active = button.dataset.kind === selected;
        button.classList.toggle("is-selected", active);
        button.setAttribute("aria-pressed", String(active));
      });
      break;
    }
    case "remove-duty-item": {
      const container = element.closest("[data-duty-items]");
      if (container?.children.length > 1) {
        element.closest(".duty-kind-entry").remove();
        container.querySelectorAll("[data-duty-item-title]").forEach((title, index) => { title.textContent = `Item ${index + 1}`; });
      }
      break;
    }
    case "new-calendar-event":
      openNewCalendarEventModal(ui.calendarCommunityId, ui.calendarDay);
      break;
    case "claim-duty":
      await apiCommit(
        () => api.post(`/duties/${element.dataset.duty}/claim`),
        { successMessage: "Claimed. Thanks for bringing it." },
      );
      break;
    case "release-duty":
      await apiCommit(
        () => api.delete(`/duties/${element.dataset.duty}/claim`),
        { successMessage: "Handed back to the squad." },
      );
      break;
    case "delete-duty": {
      const title = element.dataset.title || "this duty";
      if (!window.confirm(`Delete "${title}" from the calendar?`)) break;
      await apiCommit(
        () => api.delete(`/duties/${element.dataset.duty}`),
        { successMessage: "Duty deleted." },
      );
      break;
    }
    case "jump-rating": {
      const ratingEl = document.getElementById("player-rating");
      if (ratingEl) ratingEl.scrollIntoView({ behavior: "smooth", block: "start" });
      break;
    }
    case "lineup-pick":
      await handleLineupPick(element.dataset.source, element.dataset.player, element.dataset.slot);
      break;
    case "reset-lineup":
      await resetLineup();
      break;
    case "clear-lineup": {
      const team = currentTeam();
      if (!team) break;
      ui.lineupSelected = null;
      await apiCommit(
        () => api.patch(`/teams/${team.id}`, { starting_xi: Array(11).fill(null) }),
        { successMessage: "Starting XI cleared. Drag players from the bench to fill it manually." },
      );
      break;
    }
    case "publish-lineup":
      await publishLineup();
      break;
    case "select-plan":
      ui.selectedPlanId = element.dataset.plan;
      ui.planTab = "overview";
      ui.planBoardPlanId = null;
      ui.planBoardDraft = null;
      refresh();
      break;
    case "plan-tab":
      ui.planTab = element.dataset.tab;
      refresh();
      break;
    case "toggle-check":
      await toggleCheck(element.dataset.plan, element.dataset.check);
      break;
    case "copy-plan": {
      const plan = state.plans.find((item) => item.id === element.dataset.plan);
      if (!plan) break;
      copyText(
        `${plan.title} — vs ${plan.opponent}\n${formatDate(plan.date)} · ${formatTime(plan.date)} · ${plan.venue}\nShape: ${plan.formation}\nObjective: ${plan.objective}\n\nIn possession: ${plan.inPossession.shape}\nOut of possession: ${plan.outOfPossession.block}\nSet pieces: ${plan.setPieces.attack.title}`,
        "Match brief copied to your clipboard.",
      );
      break;
    }
    case "view-plan":
      if (element.dataset.plan) ui.selectedPlanId = element.dataset.plan;
      navigate("plans");
      break;
    case "view-poll":
      ui.pollTab = isOpen(state.polls.find((poll) => poll.id === element.dataset.poll)?.closesAt)
        ? "active"
        : "closed";
      ui.pollFilter = "All";
      navigate("polls");
      break;
    case "toggle-notifications":
      ui.notificationsOpen = !ui.notificationsOpen;
      renderApp({ preserveScroll: true });
      break;
    case "mark-notifications":
      await markAllNotifications();
      break;
    case "open-notification":
      await openNotification(element.dataset.note);
      break;
    case "open-profile":
      openProfileModal();
      break;
    case "sign-out": {
      try { await logout(); } catch { /* Local credentials are cleared even if the server is unavailable. */ }
      state = null;
      setState(null);
      ui.authMode = null;
      ui.authMessage = "";
      ui.authChallenge = null;
      ui.resetToken = null;
      ui.messengerCommunityId = null;
      ui.messengerMessages = [];
      ui.messengerDraft = "";
      ui.messengerMinimized = true;
      ui.messengerIsAtBottom = true;
      ui.messengerScrollTop = 0;
      closeModal();
      await boot();
      toast("You’ve signed out.", "success");
      break;
    }
    case "password-change-open":
      openModal({ eyebrow: "Account security", title: "Change password", body: `<form class="form" data-form="password-change"><label class="field"><span>Current password</span><input name="current_password" type="password" required autocomplete="current-password"></label><label class="field"><span>New password</span><input name="new_password" type="password" required minlength="10" autocomplete="new-password"></label><p class="auth-error" role="alert" hidden></p><div class="form-actions"><button class="btn btn--primary" type="submit">Update password</button></div></form>` });
      break;
    case "two-factor-setup": {
      const setup = await api.post("/auth/2fa/setup", {});
      openModal({ eyebrow: "Account security", title: "Set up two-factor authentication", description: "Add this secret to your authenticator app, then enter its current six digit code.", body: `<div class="profile-note">Manual setup key: <code>${escapeHTML(setup.secret)}</code></div><p class="profile-note">${escapeHTML(setup.otpauthUri)}</p><form class="form" data-form="two-factor-enable"><label class="field"><span>Authenticator code</span><input name="code" inputmode="numeric" autocomplete="one-time-code" minlength="6" maxlength="6" required></label><p class="auth-error" role="alert" hidden></p><div class="form-actions"><button class="btn btn--primary" type="submit">Enable 2FA</button></div></form>` });
      break;
    }
    case "two-factor-disable":
      openModal({ eyebrow: "Account security", title: "Disable two-factor authentication", body: `<form class="form" data-form="two-factor-disable"><label class="field"><span>Password</span><input name="password" type="password" required autocomplete="current-password"></label><label class="field"><span>Authenticator code</span><input name="code" inputmode="numeric" autocomplete="one-time-code" minlength="6" maxlength="6" required></label><p class="auth-error" role="alert" hidden></p><div class="form-actions"><button class="btn btn--primary" type="submit">Disable 2FA</button></div></form>` });
      break;
    case "retry-boot":
      boot();
      break;
    case "copy-invite":
      copyText(
        "Join us on Touchline — the clubhouse for our football club. Polls, team sheets and game plans in one place.",
        "Invite message copied. Send it to the squad.",
      );
      break;
    case "clear-search":
      clearSearch(true);
      break;
    case "search-jump":
      jumpToSearchResult(element.dataset.type, element.dataset.id);
      break;
    default:
      break;
  }
}

async function syncFromServer() {
  const next = await refreshState();
  setState(next);
  state = next;
  if (!next.plans.some((plan) => plan.id === ui.selectedPlanId)) {
    ui.selectedPlanId = next.plans[0]?.id ?? null;
  }
  return next;
}

function handleApiError(error, form = null) {
  const message = error instanceof ApiError ? error.message : "Something went wrong.";
  if (form) {
    showFormError(form, message);
    return;
  }
  toast(message, "error");
  if (error instanceof ApiError && error.status === 401) {
    window.setTimeout(() => boot(), 600);
  }
}

async function apiCommit(call, { successMessage = null, closeAfter = false, preserveScroll = true } = {}) {
  try {
    const result = await call();
    await syncFromServer();
    if (currentRoute() === "calendar") await loadCalendar();
    if (closeAfter) closeModal();
    refresh({ preserveScroll });
    if (successMessage) toast(successMessage, "success");
    return result;
  } catch (error) {
    handleApiError(error);
    return null;
  }
}

async function votePoll(pollId, optionId) {
  const poll = state.polls.find((item) => item.id === pollId);
  if (!poll || !isOpen(poll.closesAt)) return;
  const option = poll.options.find((item) => item.id === optionId);
  if (poll.category === "Pickup" && option?.label.toLocaleLowerCase() === "yes") {
    const players = state.teams.find((team) => team.communityId === poll.communityId)?.players.filter((player) => player.status !== "out") ?? [];
    if (!players.length) { toast("This community needs an available player roster before members can confirm Yes.", "error"); return; }
    const ownProfiles = players.filter((player) => player.isMine || (!player.registered && player.name.trim().toLocaleLowerCase() === state.user.name.trim().toLocaleLowerCase()));
    if (ownProfiles.length !== 1) { toast(ownProfiles.length ? "More than one active player profile matches your account. Ask a community admin to correct the roster." : "To confirm Yes, your account name must match your player profile in this community. Ask an admin to update the name if needed.", "error"); return; }
    const ownPlayer = ownProfiles[0];
    openModal({ eyebrow: "Pickup attendance", title: "Are you playing?", description: "Yes registers only your own player profile. You can add up to two unregistered friends or family as guests.", body: `<form class="form" data-form="pickup-attendance-vote" data-poll="${escapeHTML(pollId)}" data-option="${escapeHTML(optionId)}"><input type="hidden" name="player_id" value="${escapeHTML(ownPlayer.id)}"><div class="form-note"><strong>Your player</strong><br>#${ownPlayer.number} ${escapeHTML(ownPlayer.name)} · ${escapeHTML(ownPlayer.pos)}</div><label class="field"><span>Additional guests</span><select name="guest_count"><option value="0">No additional guests</option><option value="1">+1 guest</option><option value="2">+2 guests</option></select><small>Guests are included in the team split but do not need an account.</small></label><div class="form-actions"><button class="btn btn--ghost" type="button" data-action="close-modal">Cancel</button><button class="btn btn--primary" type="submit">Confirm Yes</button></div></form>` });
    return;
  }
  if (poll.userVote === optionId) return;
  await apiCommit(
    () => api.post(`/polls/${pollId}/vote`, { option_id: optionId }),
    { successMessage: "Vote counted — thanks for weighing in." },
  );
}

async function handleLineupPick(source, playerId, slotIndex) {
  const team = currentTeam();
  if (!team) return;
  const selected = ui.lineupSelected;
  if (!playerId) {
    if (!selected || slotIndex === undefined) return;
    const targetIndex = Number(slotIndex);
    if (!Number.isInteger(targetIndex) || targetIndex < 0 || targetIndex > 10) return;
    const nextLineup = [...team.startingXI];
    while (nextLineup.length < 11) nextLineup.push(null);
    const selectedIndex = nextLineup.indexOf(selected.id);
    if (selectedIndex >= 0) nextLineup[selectedIndex] = null;
    nextLineup[targetIndex] = selected.id;
    ui.lineupSelected = null;
    await apiCommit(() => api.patch(`/teams/${team.id}`, { starting_xi: nextLineup }), { preserveScroll: true });
    return;
  }
  if (!selected) {
    ui.lineupSelected = { id: playerId, source, slot: slotIndex };
    refresh();
    return;
  }
  if (selected.id === playerId) {
    ui.lineupSelected = null;
    refresh();
    return;
  }
  if (selected.source === "bench" && source === "bench") {
    ui.lineupSelected = { id: playerId, source: "bench" };
    refresh();
    return;
  }

  const nextLineup = [...team.startingXI];
  const selectedIndex = nextLineup.indexOf(selected.id);
  if (source === "pitch") {
    const targetIndex =
      slotIndex !== undefined ? Number(slotIndex) : nextLineup.indexOf(playerId);
    if (selected.source === "pitch") {
      if (selectedIndex >= 0 && targetIndex >= 0) {
        [nextLineup[selectedIndex], nextLineup[targetIndex]] = [
          nextLineup[targetIndex],
          nextLineup[selectedIndex],
        ];
      }
    } else if (targetIndex >= 0) {
      nextLineup[targetIndex] = selected.id;
    }
  } else if (selected.source === "pitch" && selectedIndex >= 0) {
    nextLineup[selectedIndex] = playerId;
  }

  ui.lineupSelected = null;
  await apiCommit(
    () => api.patch(`/teams/${team.id}`, { starting_xi: nextLineup }),
    { preserveScroll: true },
  );
}

async function resetLineup() {
  const team = currentTeam();
  if (!team) return;
  const lineup = autoLineup(team, team.formation);
  await apiCommit(
    () => api.patch(`/teams/${team.id}`, { starting_xi: lineup }),
    { successMessage: "Auto-picked the strongest available XI." },
  );
}

function autoArrangePlanBoard() {
  const plan = state.plans.find((item) => item.id === ui.selectedPlanId);
  const team = state.teams.find((item) => item.communityId === plan?.communityId) ?? state.teams[0];
  if (!plan || !team || team.players.length < 11) { toast("Add at least 11 players before arranging the plan board.", "error"); return; }
  ui.planBoardPlanId = plan.id;
  ui.planBoardDraft = autoLineup(team, plan.formation);
  ui.planBoardSelectedPlayer = null;
  refresh({ preserveScroll: true });
  toast("Balanced lineup arranged. Save the board to keep it.", "success");
}

async function savePlanBoard() {
  const plan = state.plans.find((item) => item.id === ui.selectedPlanId);
  if (!plan || ui.planBoardDraft?.length !== 11) return;
  const saved = await apiCommit(() => api.patch(`/plans/${plan.id}`, { board: ui.planBoardDraft }), { successMessage: "Game plan board saved." });
  if (saved) { ui.planBoardDraft = null; ui.planBoardPlanId = null; ui.planBoardSelectedPlayer = null; refresh({ preserveScroll: true }); }
}

async function publishLineup() {
  const team = currentTeam();
  if (!team) return;
  if (team.startingXI.length !== 11 || team.startingXI.some((playerId) => !playerId)) {
    toast("Fill all 11 Starting XI spots before publishing.", "error");
    return;
  }
  await apiCommit(
    () => api.patch(`/teams/${team.id}`, { publish: true }),
    { successMessage: "Starting XI published to the squad." },
  );
}

async function toggleCheck(planId, checkId) {
  const plan = state.plans.find((item) => item.id === planId);
  const item = plan?.checklist.find((check) => check.id === checkId);
  if (!item) return;
  const result = await apiCommit(
    () => api.patch(`/plans/${planId}/checklist/${checkId}`, { done: !item.done }),
  );
  if (result?.checklist?.every((check) => check.done)) {
    toast("Plan complete. Go win the game.", "success");
  }
}

async function markAllNotifications() {
  await apiCommit(
    () => api.post("/notifications/read", { all: true }),
    { successMessage: "All notifications marked as read." },
  );
}

async function openNotification(noteId) {
  const notification = state.notifications.find((item) => item.id === noteId);
  if (!notification) return;
  try {
    await api.post("/notifications/read", { ids: [noteId] });
    await syncFromServer();
  } catch (error) {
    handleApiError(error);
    return;
  }
  ui.notificationsOpen = false;
  const route = String(notification.route || "#/home");
  if (route.startsWith("#/")) {
    if (window.location.hash === route) renderApp({ scrollTop: true });
    else window.location.hash = route;
  } else navigate(route.replace(/^\/+/, ""));
}

function applyRosterFilter() {
  const rows = [...document.querySelectorAll("[data-player-row]")];
  if (!rows.length) return;
  const query = ui.squadQuery.trim().toLowerCase();
  let visible = 0;
  rows.forEach((row) => {
    const matchesPosition =
      ui.positionFilter === "all" || row.dataset.group === ui.positionFilter;
    const matchesQuery = !query || row.dataset.name.includes(query);
    const show = matchesPosition && matchesQuery;
    row.hidden = !show;
    if (show) visible += 1;
  });
  const empty = document.querySelector("#roster-empty");
  if (empty) empty.hidden = visible > 0;
  const count = document.querySelector("#roster-count");
  if (count) {
    const total = currentTeam()?.players.length ?? 0;
    count.textContent =
      visible === total ? `${total} players` : `${visible} of ${total} players`;
  }
}

function clearSearch(focus = false) {
  ui.searchQuery = "";
  ui.searchOpen = false;
  const input = document.querySelector("#global-search");
  if (input) {
    input.value = "";
    if (focus) input.focus();
  }
  const results = document.querySelector("#search-results");
  if (results) results.innerHTML = "";
  const clear = document.querySelector(".global-search__clear");
  if (clear) clear.hidden = true;
}

function hideSearchResults() {
  const results = document.querySelector("#search-results");
  if (results) results.innerHTML = "";
}

function jumpToSearchResult(type, id) {
  clearSearch();
  if (type === "community") {
    const community = state.communities.find((item) => item.id === id);
    if (community?.joined) {
      const next = `#/community/${encodeURIComponent(id)}`;
      if (window.location.hash === next) selectCommunityChat(id);
      else window.location.hash = next;
    } else if (community?.privacy === "Public") {
      openCommunityDetail(id).catch((error) => handleApiError(error));
    }
    return;
  }
  if (type === "poll") {
    const poll = state.polls.find((item) => item.id === id);
    ui.pollTab = isOpen(poll?.closesAt) ? "active" : "closed";
    ui.pollFilter = "All";
    navigate("polls");
    return;
  }
  if (type === "player") {
    ui.teamTab = "squad";
    navigate("teams");
    window.setTimeout(() => openPlayerModal(state, id), 120);
    return;
  }
  if (type === "plan") {
    ui.selectedPlanId = id;
    ui.planTab = "overview";
    navigate("plans");
  }
}

async function copyText(text, message) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    document.execCommand("copy");
    area.remove();
  }
  toast(message, "success");
}

function openProfileModal() {
  const joined = state.communities.filter((community) => community.joined).length;
  openModal({
    eyebrow: "Member profile",
    title: state.user.name,
    description: `${state.user.role} · ${state.teams?.[0]?.name || state.communities?.[0]?.name || "Clubhouse"}`,
    body: `<div class="profile-modal">
      <div class="profile-hero">
        ${avatar(state.user.name, { size: "xl", tone: "forest" })}
        <div>
          <span class="tag tag--voted">${icon("check", 12)} ${escapeHTML(state.user.role)}</span>
          <h3>${escapeHTML(state.user.name)}</h3>
          <p>${escapeHTML(state.user.email)}</p>
        </div>
      </div>
      <div class="profile-stats">
        <div><strong>${joined}</strong><span>Clubhouses</span></div>
        <div><strong>${state.posts.filter((post) => post.author === state.user.name).length}</strong><span>Posts</span></div>
        <div><strong>${Number(state.user.points || 0)}</strong><span>Club points</span></div>
        <div><strong>${state.polls.filter((poll) => poll.userVote).length}</strong><span>Votes cast</span></div>
      </div>
      <div class="profile-note">${icon("sparkle", 16)} You’ve been part of the clubhouse since ${escapeHTML(state.user.memberSince)}. ${state.user.emailVerified ? "Email verified." : "Email not verified."}</div>
      ${!window.TOUCHLINE_MOBILE ? `<div class="modal-actions"><button class="btn btn--light" type="button" data-action="open-api-key-access">${icon("key", 15)} API access</button>${state.user.role === "Super Admin" ? `<button class="btn btn--light" type="button" data-action="open-super-admin-api-key-requests">${icon("shield", 15)} API key requests</button><button class="btn btn--light" type="button" data-action="open-super-admin-deletion-settings">${icon("team", 15)} Super admin settings</button>` : ""}</div>` : ""}
      <div class="modal-actions"><button class="btn btn--light" type="button" data-action="password-change-open">Change password</button>${state.user.twoFactorEnabled ? `<span class="role-badge">2FA enabled</span><button class="btn btn--light" type="button" data-action="two-factor-disable">Disable 2FA</button>` : `<button class="btn btn--light" type="button" data-action="two-factor-setup">Enable 2FA</button>`}</div>
      <div class="modal-actions"><button class="btn btn--ghost" type="button" data-action="close-modal">Close</button><button class="btn btn--light" type="button" data-action="sign-out">Sign out</button></div>
    </div>`,
  });
}

function showFormError(form, message) {
  let error = form.querySelector(".form-error");
  if (!error) {
    error = document.createElement("p");
    error.className = "form-error";
    error.setAttribute("role", "alert");
    const actions = form.querySelector(".form-actions");
    if (actions) actions.before(error);
    else form.appendChild(error);
  }
  error.textContent = message;
  error.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

async function imageDataFromInput(input, maxEncoded = 225_000) {
  const file = input?.files?.[0];
  if (!file) return null;
  if (!/^image\/(png|jpeg|webp)$/.test(file.type)) throw new Error("Choose a PNG, JPEG or WebP image.");
  if (file.size > 12 * 1024 * 1024) throw new Error("Choose an image smaller than 12 MB.");
  const bitmap = await createImageBitmap(file);
  const initialScale = Math.min(1, 1400 / Math.max(bitmap.width, bitmap.height));
  for (const reduction of [1, 0.78, 0.58, 0.4]) {
    const scale = initialScale * reduction;
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(bitmap.width * scale));
    canvas.height = Math.max(1, Math.round(bitmap.height * scale));
    canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    for (const quality of [0.82, 0.72, 0.6, 0.48, 0.36]) {
      const encoded = canvas.toDataURL("image/webp", quality);
      if (encoded.length < maxEncoded) { bitmap.close?.(); return encoded; }
    }
  }
  bitmap.close?.();
  throw new Error("This image is too large after compression. Choose a smaller image.");
}

async function handleFormSubmit(form) {
  if (form.dataset.busy === "1") return;
  const type = form.dataset.form;
  const formData = new FormData(form);
  const values = Object.fromEntries(formData.entries());
  const submitButtons = [...form.querySelectorAll('button[type="submit"]')];
  form.dataset.busy = "1";
  submitButtons.forEach((button) => {
    button.disabled = true;
  });

  try {
    if (type === "pickup-builder-rearrange") {
      const pool = getPickupPool(state, ui);
      const assignment = [...form.querySelectorAll("[data-pickup-player]")].map((card) => ({ id: card.dataset.pickupPlayer, side: card.closest("[data-drop-zone]")?.dataset.dropZone }));
      const ids = assignment.map((item) => item.id);
      const teamA = assignment.filter((item) => item.side === "teamA").map((item) => item.id);
      const teamB = assignment.filter((item) => item.side === "teamB").map((item) => item.id);
      const floaters = assignment.filter((item) => item.side === "floater").map((item) => item.id);
      const validSizes = floaters.length ? (pool.length % 2 === 1 && teamA.length === teamB.length) : (pool.length % 2 ? Math.abs(teamA.length - teamB.length) === 1 : teamA.length === teamB.length);
      if (ids.length !== pool.length || new Set(ids).size !== pool.length || pool.some((player) => !ids.includes(player.id)) || !validSizes || floaters.length > 1) {
        showFormError(form, "Assign every player once. For an odd roster, either balance teams with one optional floater or split players as evenly as possible without a floater.");
        return;
      }
      ui.pickupManualSplit = { teamA, teamB, floater: floaters[0] ?? null, teamNames: getPickupResult(state, ui).teamNames };
      closeModal();
      refresh();
      toast("Pickup teams saved with every player assigned.", "success");
      return;
    }
    if (type === "api-key-request") {
      await api.post("/me/api-key-requests", { reason: values.reason });
      await openApiKeyAccess();
      toast("API key request sent to the super admin.", "success");
      return;
    }
    if (type === "community-deletion-timeout") {
      const result = await api.patch("/admin/community-deletion-settings", { days: Number(values.days) });
      await openSuperAdminDeletionSettings();
      toast(`Decision window set to ${result.timeoutDays} days.`, "success");
      return;
    }
    if (type === "global-app-theme") {
      await api.patch("/admin/app-theme", { theme: values.theme });
      await syncFromServer();
      await openSuperAdminDeletionSettings();
      renderApp();
      toast("Application theme saved.", "success");
      return;
    }
    if (type === "community-profile-theme") {
      const communityId = form.dataset.community;
      await api.patch(`/communities/${encodeURIComponent(communityId)}/theme`, { theme: values.theme });
      await syncFromServer();
      await showCommunityMembers(communityId);
      renderApp();
      toast("Community theme saved.", "success");
      return;
    }
    if (type === "global-poll-retention") {
      const result = await api.patch("/admin/poll-retention-settings", { days: Number(values.days) });
      await openSuperAdminDeletionSettings();
      toast(`Default poll retention set to ${result.days} days.`, "success");
      return;
    }
    if (type === "community-poll-retention") {
      const communityId = form.dataset.community;
      const result = await api.patch(`/communities/${encodeURIComponent(communityId)}/poll-retention-settings`, { days: Number(values.days) });
      await showCommunityMembers(communityId);
      toast(`Community poll retention set to ${result.days} days.`, "success");
      return;
    }
    if (type === "player-auth") {
      const result = await login(values.email, values.password);
      if (result.twoFactorRequired) { ui.authChallenge = result.challengeToken; ui.authMode = "two-factor"; document.querySelector("#app").innerHTML = renderAuthScreen(); return; }
      await boot();
      return;
    }
    if (type === "add-community-member") {
      const communityId = form.dataset.community;
      await api.post(`/communities/${communityId}/members`, { email: values.email });
      await syncFromServer();
      await showCommunityMembers(communityId);
      toast("Member added to the community.", "success");
      return;
    }
    if (type === "community-messenger-chat") {
      const communityId = form.dataset.community;
      const mentions = ui.messengerTaggedMembers.filter((member) => values.text.includes(`@${member.name}`));
      await api.post(`/communities/${communityId}/messages`, { text: values.text, mentions });
      const composer = form.querySelector("textarea[name=text]");
      if (composer) composer.value = "";
      ui.messengerDraft = "";
      ui.messengerForceScrollToBottom = true;
      ui.messengerTaggedMembers = [];
      ui.messengerMessages = await api.get(`/communities/${communityId}/messages`);
      mountMessengerPanel();
      return;
    }
    if (type === "edit-community-message") {
      const communityId = form.dataset.community;
      await api.patch(`/communities/${communityId}/messages/${form.dataset.message}`, { text: values.text });
      ui.editingMessageId = null;
      ui.messengerMessages = await api.get(`/communities/${communityId}/messages`);
      mountMessengerPanel();
      return;
    }
    if (type === "player-register") {
      await register(values.name, values.email, values.password, ui.playerInviteToken);
      ui.playerInviteToken = null;
      ui.authMode = "check-email"; ui.authMessage = ""; document.querySelector("#app").innerHTML = renderAuthScreen(); return;
    }
    if (type === "admin-login") {
      const result = await adminLogin(values.email, values.password);
      if (result.twoFactorRequired) { ui.authChallenge = result.challengeToken; ui.authMode = "two-factor"; document.querySelector("#app").innerHTML = renderAuthScreen(); return; }
      await boot(); return;
    }
    if (type === "two-factor-login") {
      const result = await api.post("/auth/2fa/login", { challengeToken: ui.authChallenge, code: values.code });
      setSessionToken(result.token); ui.authMode = null; ui.authChallenge = null; await boot(); return;
    }
    if (type === "forgot-password") {
      await api.post("/auth/password/forgot", { email: values.email });
      ui.authMode = "forgot-sent"; document.querySelector("#app").innerHTML = renderAuthScreen(); return;
    }
    if (type === "resend-verification") {
      await api.post("/auth/verification/resend", { email: values.email });
      ui.authMode = "check-email"; ui.authMessage = "If the address needs verification, a new email has been sent."; document.querySelector("#app").innerHTML = renderAuthScreen(); return;
    }
    if (type === "reset-password") {
      if (values.password !== values.confirmPassword) throw new Error("The passwords do not match.");
      await api.post("/auth/password/reset", { token: ui.resetToken, password: values.password });
      ui.resetToken = null; ui.authMode = "login"; ui.authMessage = "Password changed. Sign in with your new password."; window.history.replaceState({}, "", window.location.pathname); document.querySelector("#app").innerHTML = renderAuthScreen(); return;
    }
    if (type === "password-change") {
      await api.post("/auth/password/change", { current_password: values.current_password, new_password: values.new_password });
      closeModal(); toast("Password updated.", "success"); return;
    }
    if (type === "two-factor-enable") {
      const result = await api.post("/auth/2fa/enable", { code: values.code });
      closeModal(); openModal({ eyebrow: "Save these codes", title: "Two-factor enabled", description: "Each recovery code works once. Save them somewhere private now.", body: `<div class="profile-note"><code>${result.recoveryCodes.map(escapeHTML).join("<br>")}</code></div><div class="modal-actions"><button class="btn btn--primary" type="button" data-action="close-modal">Done</button></div>` });
      await syncFromServer(); return;
    }
    if (type === "two-factor-disable") {
      await api.post("/auth/2fa/disable", { password: values.password, code: values.code });
      closeModal(); await syncFromServer(); openProfileModal(); toast("Two-factor authentication disabled.", "success"); return;
    }
    if (type === "new-post") {
      const body = String(values.text ?? "").trim();
      if (!body) return;
      const targetCommunity = String(values.community ?? "");
      const postPayload = {
        community_id: targetCommunity,
        text: body,
        tag: values.tag ?? "club",
      };
      const image = await imageDataFromInput(form.elements.image);
      if (image) postPayload.image_data = image;
      await api.post("/posts", postPayload);
      await syncFromServer();
      closeModal();
      ui.homeTab = "for-you";
      ui.communityFilterId = null;
      window.location.hash = currentCommunityRoute() ? `#/community/${encodeURIComponent(targetCommunity)}` : "#/home";
      toast("Posted to the clubhouse.", "success");
      return;
    }

    if (type === "add-comment") {
      const comment = String(values.comment ?? "").trim();
      const postId = form.dataset.post;
      if (!comment) return;
      await api.post(`/posts/${postId}/comments`, { text: comment });
      await syncFromServer();
      if (!ui.openComments.includes(postId)) ui.openComments.push(postId);
      refresh();
      toast("Comment added.", "success");
      return;
    }

    if (type === "new-community") {
      const name = String(values.name ?? "").trim();
      if (!name) return;
      const branding = {
        logo_data: await imageDataFromInput(form.elements.logo, 108_000),
        banner_data: await imageDataFromInput(form.elements.banner, 108_000),
      };
      await api.post("/communities", {
        name,
        sport: values.sport ?? "Soccer",
        kind: values.kind ?? "Community",
        privacy: values.privacy ?? "Public",
        description: String(values.description ?? "").trim(),
        create_poll: Boolean(values.createPoll),
        ...Object.fromEntries(Object.entries(branding).filter(([, image]) => image)),
      });
      await syncFromServer();
      closeModal();
      ui.sportFilter = "All";
      navigate("communities");
      toast(`${name} is live. Invite your people in.`, "success");
      return;
    }

    if (type === "community-branding") {
      const communityId = form.dataset.community;
      const body = {};
      const logo = await imageDataFromInput(form.elements.logo, 108_000);
      const banner = await imageDataFromInput(form.elements.banner, 108_000);
      if (logo) body.logo_data = logo;
      if (banner) body.banner_data = banner;
      if (form.elements.removeLogo?.checked) body.logo_data = "";
      if (form.elements.removeBanner?.checked) body.banner_data = "";
      if (!Object.keys(body).length) { showFormError(form, "Choose a logo or banner image first."); return; }
      await api.patch(`/communities/${communityId}`, body);
      await syncFromServer();
      closeModal();
      refresh({ preserveScroll: true });
      toast("Community branding updated.", "success");
      return;
    }

    if (type === "new-team") {
      const team = await api.post("/teams", {
        community_id: String(values.communityId ?? ""),
        name: String(values.name ?? "").trim(),
        age_group: String(values.ageGroup ?? "").trim(),
        league: String(values.league ?? "").trim(),
        coach: String(values.coach ?? "").trim(),
        formation: values.formation ?? "4-3-3",
      });
      ui.selectedTeamId = team.id;
      await syncFromServer();
      closeModal();
      navigate("teams");
      toast(`${team.name} is ready. Add your players when you’re ready.`, "success");
      return;
    }

    if (type === "new-poll") {
      const category = values.category ?? "Pickup";
      const options = category === "Pickup" ? ["Yes", "No"] : ["option1", "option2", "option3", "option4"]
        .map((key) => String(values[key] ?? "").trim())
        .filter(Boolean);
      if (!String(values.question ?? "").trim() || options.length < 2) return;
      const communityId = String(form.dataset.community || values.community_id || "");
      const closesAt = new Date(values.closesAt);
      if (Number.isNaN(closesAt.getTime())) throw new Error("Choose a valid poll closing date and time.");
      const gameAt = category === "Pickup"
        ? values.gameDate && values.gameTime ? new Date(`${values.gameDate}T${values.gameTime}`) : null
        : values.gameAt ? new Date(values.gameAt) : null;
      if (["Pickup", "Competition"].includes(category) && (!gameAt || Number.isNaN(gameAt.getTime()))) throw new Error(category === "Pickup" ? "Choose the pickup game date and start time." : "Choose the game date and kick-off time.");
      await api.post("/polls", {
        question: String(values.question).trim(),
        category,
        closes_at: closesAt.toISOString(),
        ...(gameAt ? { game_at: gameAt.toISOString() } : {}),
        ...(category === "Pickup" ? { location: String(values.location ?? "").trim() } : {}),
        options,
        ...(communityId ? { community_id: communityId } : {}),
      });
      await syncFromServer();
      closeModal();
      ui.pollTab = "active";
      ui.pollFilter = "All";
      if (communityId) window.location.hash = `#/community/${encodeURIComponent(communityId)}`;
      else navigate("polls");
      toast("Poll published to the squad.", "success");
      return;
    }

    if (type === "pickup-attendance-vote") {
      await api.post(`/polls/${encodeURIComponent(form.dataset.poll)}/vote`, { option_id: form.dataset.option, player_id: values.player_id, guest_count: Number(values.guest_count || 0) });
      await syncFromServer();
      closeModal();
      refresh();
      toast("Attendance confirmed.", "success");
      return;
    }

    if (type === "poll-team-rearrange") {
      const teamA = [], teamB = [];
      let floater = null;
      form.querySelectorAll("[data-pickup-player]").forEach((card) => {
        const side = card.closest("[data-drop-zone]")?.dataset.dropZone;
        if (side === "teamA") teamA.push(card.dataset.pickupPlayer);
        else if (side === "teamB") teamB.push(card.dataset.pickupPlayer);
        else if (side === "floater") floater = card.dataset.pickupPlayer;
      });
      await api.post(`/polls/${encodeURIComponent(form.dataset.poll)}/teams`, { team_a: teamA, team_b: teamB, floater });
      closeModal();
      await syncFromServer();
      toast("Teams updated.", "success");
      return;
    }

    if (type === "poll-feedback") {
      const ratings = [...form.querySelectorAll(".matchday-review-player")].map((player) => ({
        player_id: player.dataset.playerId,
        value: Number(player.querySelector("[data-rating]").value),
        feedback: player.querySelector("[data-feedback]").value.trim(),
      }));
      await api.post(`/polls/${encodeURIComponent(form.dataset.poll)}/feedback`, { ratings });
      closeModal();
      toast("Player feedback submitted. Thank you.", "success");
      return;
    }

    if (type === "add-player") {
      const body = {
        team_id: String(values.teamId ?? currentTeam()?.id ?? ""),
        email: String(values.email ?? "").trim(),
        name: String(values.name ?? "").trim(),
        number: Number(values.number),
        pos: values.pos ?? "CM",
        foot: values.foot ?? "Right",
        status: values.status ?? "available",
      };
      if (values.date_of_birth) body.date_of_birth = values.date_of_birth;
      if (values.height_cm) body.height_cm = Number(values.height_cm);
      if (values.bio?.trim()) body.bio = values.bio.trim();
      if (form.dataset.xiSlot !== undefined) body.xi_slot = Number(form.dataset.xiSlot);
      for (const field of ["goals","assists","apps","starts","minutes","yellow_cards","red_cards","clean_sheets"]) body[field] = Number(values[field] || 0);
      const image = await imageDataFromInput(form.elements.image);
      if (image) body.image_data = image;
      const created = await api.post("/players", body);
      if (created.invitationPending) {
        await syncFromServer();
        closeModal();
        toast(`Registration link sent to ${created.email}. They will join the community after signing up.`, "success");
        return;
      }
      await syncFromServer();
      if (body.xi_slot !== undefined) {
        const updatedTeam = state.teams.find((item) => item.id === body.team_id);
        if (updatedTeam?.startingXI.length === 11 && updatedTeam.players.length >= 11) {
          const next = [...updatedTeam.startingXI];
          const previousIndex = next.indexOf(created.id);
          if (previousIndex >= 0) [next[previousIndex], next[body.xi_slot]] = [next[body.xi_slot], next[previousIndex]];
          else next[body.xi_slot] = created.id;
          await api.patch(`/teams/${updatedTeam.id}`, { starting_xi: next });
          await syncFromServer();
        }
      }
      closeModal();
      window.location.hash = `#/player/${created.id}`;
      toast(`${created.name} added to the squad.`, "success");
      return;
    }

    if (type === "update-player") {
      const playerId = form.dataset.player;
      const patchBody = {
        name: String(values.name ?? "").trim(),
        number: Number(values.number),
        pos: values.pos,
        foot: values.foot,
        status: values.status,
        bio: values.bio ?? "",
      };
      if (String(values.email ?? "").trim()) patchBody.email = String(values.email).trim();
      if (String(values.account_id ?? "").trim()) patchBody.account_id = String(values.account_id).trim();
      for (const field of ["goals","assists","apps","starts","minutes","yellow_cards","red_cards","clean_sheets"]) patchBody[field] = Number(values[field] || 0);
      if (values.date_of_birth) patchBody.date_of_birth = values.date_of_birth;
      else patchBody.date_of_birth = null;
      if (values.height_cm) patchBody.height_cm = Number(values.height_cm);
      else patchBody.height_cm = null;
      const image = await imageDataFromInput(form.elements.image);
      if (image) patchBody.image_data = image;
      if (form.elements.removeImage?.checked) patchBody.image_data = "";
      const updated = await api.patch(`/players/${playerId}`, patchBody);
      await syncFromServer();
      closeModal();
      refresh({ preserveScroll: true });
      if (updated.invitationPending) {
        toast(`Signup link sent to ${updated.email}. After verifying their email, the player will be linked to this community.`, "success");
        return;
      }
      toast(`${updated.name} updated.`, "success");
      return;
    }

    if (type === "matchday-review") {
      const ratings = [...form.querySelectorAll(".matchday-review-player")].map((row) => ({
        player_id: row.dataset.playerId,
        value: Number(row.querySelector("[data-rating]").value),
        feedback: row.querySelector("[data-feedback]").value,
      }));
      const result = await api.post(`/communities/${form.dataset.community}/fixtures/${form.dataset.fixture}/ratings`, { ratings });
      toast(`Your ratings for ${result.playerCount} players were submitted.`, "success");
      closeModal();
      window.location.hash = `#/community/${encodeURIComponent(form.dataset.community)}`;
      return;
    }

    if (type === "rate-player") {
      const playerId = form.dataset.player;
      const value = Number(values.rating);
      if (!Number.isFinite(value) || value < 1 || value > 10) {
        showFormError(form, "Choose a rating between 1 and 10.");
        return;
      }
      const player = await api.post(`/players/${playerId}/ratings`, { value });
      await syncFromServer();
      closeModal();
      refresh({ preserveScroll: true });
      toast(`Your ${value}/10 rating for ${player.name} is in.`, "success");
      return;
    }

    if (type === "new-duty") {
      const field = (name) => form.querySelector(`[data-duty-field="${name}"]`)?.value ?? "";
      const items = [...form.querySelectorAll("[data-duty-kind]")].map((select) => select.value);
      const when = new Date(`${field("date")}T${field("time")}:00`);
      if (Number.isNaN(when.getTime())) { showFormError(form, "Choose a valid date and time."); return; }
      const duty = await api.post("/duties", { community_id: form.dataset.community, kind: items[0], items,
        title: field("title").trim() || undefined, starts_at: when.toISOString(), note: field("note").trim(),
        event_key: field("event_key") || null, assigned_to: field("assigned_to") || null });
      await syncFromServer();
      ui.calendarDay = localDayKey(when);
      ui.calendarMonth = monthKey(when);
      await loadCalendar();
      closeModal();
      refresh({ preserveScroll: false });
      toast(`${duty.title} added to the community calendar.`, "success");
      return;
    }
    if (type === "new-calendar-event") {
      const when = new Date(`${values.date}T12:00:00`);
      if (Number.isNaN(when.getTime())) { showFormError(form, "Choose a valid date."); return; }
      await api.post("/calendar/events", { community_id: values.communityId, title: String(values.title ?? "").trim(), type: values.type, date: when.toISOString(), detail: String(values.detail ?? "").trim() });
      await syncFromServer();
      ui.calendarDay = localDayKey(when);
      ui.calendarMonth = monthKey(when);
      await loadCalendar();
      closeModal();
      refresh({ preserveScroll: false });
      toast("Event added to this community calendar.", "success");
      return;
    }
    if (type === "new-plan") {
      const date = new Date(`${values.date}T14:30:00`);
      if (Number.isNaN(date.getTime())) {
        showFormError(form, "Choose a valid match date.");
        return;
      }
      const plan = await api.post("/plans", {
        title: String(values.title ?? "").trim(),
        opponent: String(values.opponent ?? "").trim(),
        date: date.toISOString(),
        venue: String(values.venue ?? "Home ground").trim(),
        formation: values.formation ?? "4-3-3",
        objective: String(values.objective ?? "").trim(),
        team_id: currentTeam()?.id,
        board: currentTeam()?.startingXI?.length === 11 && currentTeam().startingXI.every(Boolean) ? currentTeam().startingXI : currentTeam() ? autoLineup(currentTeam(), values.formation ?? "4-3-3") : [],
      });
      await syncFromServer();
      closeModal();
      ui.selectedPlanId = plan.id;
      ui.planTab = "overview";
      navigate("plans");
      toast("Game plan created. Time to fill in the details.", "success");
      return;
    }
    if (type === "edit-plan") {
      const parsePairs = (value, first, label) => {
        const lines = String(value ?? "").split("\n").map((line) => line.trim()).filter(Boolean);
        const output = [];
        for (const line of lines) {
          const separator = line.indexOf("|");
          if (separator < 1 || !line.slice(separator + 1).trim()) { throw new Error(`${label} lines must use “Name | details”.`); }
          output.push({ [first]: line.slice(0, separator).trim(), text: line.slice(separator + 1).trim() });
        }
        return output;
      };
      const list = (value) => String(value ?? "").split("\n").map((line) => line.trim()).filter(Boolean).map((text) => ({ text }));
      let patterns, roles;
      try { patterns = parsePairs(values.patterns, "title", "Pattern"); roles = parsePairs(values.roles, "role", "Role"); }
      catch (error) { showFormError(form, error.message); return; }
      const when = new Date(values.date);
      if (Number.isNaN(when.getTime())) { showFormError(form, "Choose a valid match date and time."); return; }
      await api.patch(`/plans/${form.dataset.plan}`, {
        title: values.title.trim(), opponent: values.opponent.trim(), date: when.toISOString(), venue: values.venue.trim(),
        competition: values.competition.trim(), formation: values.formation, status: values.status, objective: values.objective.trim(), summary: values.summary.trim(),
        in_possession_shape: values.in_possession_shape.trim(), patterns, roles,
        out_trigger: values.out_trigger.trim(), out_block: values.out_block.trim(), out_rest_defense: values.out_rest_defense.trim(),
        set_attack_title: values.set_attack_title.trim(), attack_steps: list(values.attack_steps),
        set_defend_title: values.set_defend_title.trim(), defend_steps: list(values.defend_steps),
        corner_taker: values.corner_taker.trim(), free_kick_taker: values.free_kick_taker.trim(), penalty_taker: values.penalty_taker.trim(),
        checklist: String(values.checklist ?? "").split("\n").map((line) => line.trim()).filter(Boolean),
      });
      await syncFromServer();
      closeModal();
      refresh({ preserveScroll: true });
      toast("Game plan updated.", "success");
      return;
    }
  } catch (error) {
    if (error instanceof ApiError) {
      showFormError(form, error.message);
    } else {
      showFormError(form, "The change could not be saved. Please try again.");
    }
  } finally {
    delete form.dataset.busy;
    submitButtons.forEach((button) => {
      button.disabled = false;
    });
  }
}

function copyPickupTeams() {
  const result = getPickupResult(state, ui);
  if (!result.teamA.players.length && !result.floater) {
    toast("There aren't enough available players to split yet.", "error");
    return;
  }
  const line = (player) => `${player.guest ? "Guest" : `#${String(player.number).padStart(2, "0")}`} ${player.name} (${player.pos}, ${Number(player.rating).toFixed(1)})`;
  const teamNames = result.teamNames ?? ["Yolo Blue", "Yolo Red"];
  const text = [
    `${teamNames[0]} vs ${teamNames[1]} — ${result.teamA.players.length}v${result.teamB.players.length}`,
    `Strength gap: ${result.gap.toFixed(1)} · Balance: ${result.balanceScore}%`,
    "",
    `${teamNames[0].toUpperCase()} — ${result.teamA.totalStrength.toFixed(1)} strength`,
    ...result.teamA.players.map(line),
    "",
    `${teamNames[1].toUpperCase()} — ${result.teamB.totalStrength.toFixed(1)} strength`,
    ...result.teamB.players.map(line),
    result.floater ? `\nFloater: ${result.floater.name}` : "",
  ].join("\n");
  copyText(text, "Teams copied. Drop them in the group chat.");
}



document.addEventListener("click", (event) => {
  const actionElement = event.target.closest("[data-action]");
  const rosterPlayer = event.target.closest("[data-plan-roster-player]");
  const boardSlot = event.target.closest("[data-plan-board-slot]");
  if (!actionElement && rosterPlayer) {
    ui.planBoardSelectedPlayer = rosterPlayer.dataset.planRosterPlayer;
    refresh({ preserveScroll: true });
    return;
  }
  if (!actionElement && boardSlot && ui.planBoardSelectedPlayer && ui.planBoardDraft) {
    const next = [...ui.planBoardDraft];
    const target = Number(boardSlot.dataset.planBoardSlot);
    const previous = next.indexOf(ui.planBoardSelectedPlayer);
    if (target >= 0 && target < next.length) {
      if (previous >= 0 && previous !== target) [next[previous], next[target]] = [next[target], next[previous]];
      else next[target] = ui.planBoardSelectedPlayer;
      ui.planBoardDraft = next;
      ui.planBoardSelectedPlayer = null;
      refresh({ preserveScroll: true });
    }
    return;
  }
  if (ui.ignoreNextDragClick && ["lineup-pick", "lineup-add-player"].includes(actionElement?.dataset.action)) { event.preventDefault(); ui.ignoreNextDragClick = false; return; }
  if (actionElement) {
    if (actionElement.tagName === "A") event.preventDefault();
    Promise.resolve(handleAction(actionElement.dataset.action, actionElement)).catch((error) => {
      handleApiError(error);
    });
  }

  if (!event.target.closest(".global-search")) {
    ui.searchOpen = false;
    hideSearchResults();
  }

  if (
    ui.notificationsOpen &&
    !event.target.closest(".notifications-wrap") &&
    !actionElement
  ) {
    ui.notificationsOpen = false;
    renderApp({ preserveScroll: true });
  }
});

let draggedPickupPlayer = null;
let draggedLineupPlayer = null;
let draggedPlanPlayer = null;
document.addEventListener("dragstart", (event) => {
  const lineup = event.target.closest("[data-lineup-drag-id]");
  if (lineup) {
    draggedLineupPlayer = lineup;
    event.dataTransfer?.setData("text/plain", `lineup:${lineup.dataset.lineupDragId}`);
    if (event.dataTransfer) event.dataTransfer.effectAllowed = "move";
    return;
  }
  const plan = event.target.closest("[data-plan-board-drag]");
  if (plan) {
    draggedPlanPlayer = plan;
    event.dataTransfer?.setData("text/plain", `plan:${plan.dataset.planBoardDrag}`);
    if (event.dataTransfer) event.dataTransfer.effectAllowed = "move";
    return;
  }
  const squadPickup = event.target.closest("[data-pickup-squad-player]");
  if (squadPickup) {
    draggedPickupPlayer = squadPickup;
    squadPickup.classList.add("is-dragging");
    event.dataTransfer?.setData("text/plain", `squad:${squadPickup.dataset.pickupSquadPlayer}`);
    if (event.dataTransfer) event.dataTransfer.effectAllowed = "copy";
    return;
  }
  const card = event.target.closest("[data-pickup-player]");
  if (!card) return;
  draggedPickupPlayer = card;
  card.classList.add("is-dragging");
  event.dataTransfer?.setData("text/plain", card.dataset.pickupPlayer);
  if (event.dataTransfer) event.dataTransfer.effectAllowed = "move";
});
document.addEventListener("dragend", () => {
  draggedPickupPlayer?.classList.remove("is-dragging");
  draggedPickupPlayer = null;
  draggedLineupPlayer = null;
  draggedPlanPlayer = null;
});
document.addEventListener("dragover", (event) => {
  if (event.target.closest("[data-lineup-drop-slot], [data-lineup-drop-bench], [data-plan-board-slot], [data-plan-board-bench]")) { event.preventDefault(); return; }
  const builderZone = event.target.closest("[data-pickup-builder-zone]");
  if (builderZone && draggedPickupPlayer?.hasAttribute("data-pickup-squad-player")) {
    event.preventDefault();
    builderZone.classList.add("is-drop-active");
    if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
    return;
  }
  const zone = event.target.closest("[data-drop-zone]");
  if (zone) event.preventDefault();
});
document.addEventListener("dragleave", (event) => {
  const zone = event.target.closest("[data-pickup-builder-zone]");
  if (zone && !zone.contains(event.relatedTarget)) zone.classList.remove("is-drop-active");
});
document.addEventListener("drop", (event) => {
  const lineupTarget = event.target.closest("[data-lineup-drop-slot], [data-lineup-drop-bench]");
  if (lineupTarget) {
    event.preventDefault();
    ui.ignoreNextDragClick = true;
    window.setTimeout(() => { ui.ignoreNextDragClick = false; }, 0);
    const transfer = event.dataTransfer?.getData("text/plain") ?? "";
    const playerId = transfer.startsWith("lineup:") ? transfer.slice(7) : draggedLineupPlayer?.dataset.lineupDragId;
    const team = currentTeam();
    if (playerId && team) {
      const next = [...team.startingXI];
      while (next.length < 11) next.push(null);
      const sourceIndex = next.indexOf(playerId);
      if (lineupTarget.hasAttribute("data-lineup-drop-slot")) {
        const targetIndex = Number(lineupTarget.dataset.lineupDropSlot);
        if (Number.isInteger(targetIndex) && targetIndex >= 0 && targetIndex < next.length && targetIndex !== sourceIndex) {
          if (sourceIndex >= 0) [next[sourceIndex], next[targetIndex]] = [next[targetIndex], next[sourceIndex]];
          else next[targetIndex] = playerId;
          ui.lineupSelected = null;
          apiCommit(() => api.patch(`/teams/${team.id}`, { starting_xi: next }), { preserveScroll: true });
        }
      } else if (sourceIndex >= 0) {
        next[sourceIndex] = lineupTarget.dataset.lineupDropBench;
        ui.lineupSelected = null;
        apiCommit(() => api.patch(`/teams/${team.id}`, { starting_xi: next }), { preserveScroll: true });
      }
    }
    return;
  }
  const planTarget = event.target.closest("[data-plan-board-slot]");
  const planBench = event.target.closest("[data-plan-board-bench]");
  const transfer = event.dataTransfer?.getData("text/plain") ?? "";
  const planPlayerId = transfer.startsWith("plan:") ? transfer.slice(5) : draggedPlanPlayer?.dataset.planBoardDrag;
  if (planBench && planPlayerId && ui.planBoardDraft) {
    const from = ui.planBoardDraft.indexOf(planPlayerId);
    if (from >= 0) {
      event.preventDefault();
      ui.planBoardDraft = [...ui.planBoardDraft];
      ui.planBoardDraft[from] = null;
      ui.planBoardSelectedPlayer = null;
      refresh({ preserveScroll: true });
    }
    return;
  }
  if (planTarget) {
    const playerId = planPlayerId;
    const plan = state.plans.find((item) => item.id === ui.planBoardPlanId);
    if (playerId && plan && ui.planBoardDraft) {
      event.preventDefault();
      const next = [...ui.planBoardDraft];
      const from = next.indexOf(playerId);
      const to = Number(planTarget.dataset.planBoardSlot);
      if (to >= 0 && to < next.length && from !== to) {
        if (from >= 0) [next[from], next[to]] = [next[to], next[from]];
        else next[to] = playerId;
        ui.planBoardDraft = next;
        refresh({ preserveScroll: true });
      }
    }
    return;
  }
  const builderZone = event.target.closest("[data-pickup-builder-zone]");
  if (builderZone) {
    const playerId = transfer.startsWith("squad:") ? transfer.slice(6) : "";
    const poll = state.polls.find((item) => item.id === builderZone.dataset.pickupPoll);
    const team = currentTeam();
    if (!playerId || !poll?.canManageTeams || !team || !team.players.some((player) => player.id === playerId && player.status !== "out")) return;
    event.preventDefault();
    builderZone.classList.remove("is-drop-active");
    ui.ignoreNextDragClick = true;
    window.setTimeout(() => { ui.ignoreNextDragClick = false; }, 0);
    const current = poll.autoTeams ?? {};
    const teamA = [...(current.teamA ?? [])];
    const teamB = [...(current.teamB ?? [])];
    const floater = current.floater ?? null;
    if ([...teamA, ...teamB, floater].includes(playerId)) return;
    const target = builderZone.dataset.pickupBuilderZone === "teamA" ? teamA : teamB;
    target.push(playerId);
    if (floater) {
      (target === teamA ? teamB : teamA).push(floater);
    }
    apiCommit(
      () => api.post(`/polls/${encodeURIComponent(poll.id)}/teams`, { team_a: teamA, team_b: teamB, floater: null }),
      { successMessage: `${team.players.find((player) => player.id === playerId)?.name ?? "Player"} added to ${builderZone.dataset.pickupBuilderZone === "teamA" ? "team one" : "team two"}.` },
    );
    return;
  }
  const zone = event.target.closest("[data-drop-zone]");
  if (!zone) return;
  event.preventDefault();
  const form = zone.closest("form");
  const playerId = event.dataTransfer?.getData("text/plain");
  const card = draggedPickupPlayer ?? [...(form?.querySelectorAll("[data-pickup-player]") ?? [])].find((item) => item.dataset.pickupPlayer === playerId);
  if (card && form?.contains(card)) {
    zone.querySelector(".pickup-drop-zone__players")?.append(card);
    form.querySelectorAll(".pickup-drop-zone").forEach((item) => {
      const count = item.querySelector("[data-zone-count]");
      if (count) count.textContent = `(${item.querySelectorAll("[data-pickup-player]").length})`;
    });
  }
});

document.addEventListener("scroll", (event) => {
  const messages = event.target.closest?.(".community-messenger__messages");
  if (!messages) return;
  ui.messengerScrollTop = messages.scrollTop;
  ui.messengerIsAtBottom = messages.scrollHeight - messages.scrollTop - messages.clientHeight <= 48;
}, true);

document.addEventListener("submit", (event) => {
  const form = event.target.closest("form[data-form]");
  if (!form) return;
  event.preventDefault();
  handleFormSubmit(form).catch((error) => {
    handleApiError(error, form);
  });
});

document.addEventListener("keydown", (event) => {
  const textarea = event.target.closest(".community-messenger__form textarea");
  if (!textarea || event.key !== "Enter" || event.shiftKey || event.isComposing) return;
  event.preventDefault();
  if (!textarea.value.trim()) return;
  handleFormSubmit(textarea.form).catch((error) => handleApiError(error, textarea.form));
});

document.addEventListener("input", (event) => {
  const chatTextarea = event.target.closest(".community-messenger__form textarea[name=text]");
  if (chatTextarea) {
    ui.messengerDraft = chatTextarea.value;
    ui.messengerTaggedMembers = ui.messengerTaggedMembers.filter((member) => chatTextarea.value.includes(`@${member.name}`));
    const list = chatTextarea.closest(".community-messenger__composer")?.querySelector(".community-messenger__mention-suggestions");
    const before = chatTextarea.value.slice(0, chatTextarea.selectionStart);
    const match = /@([^\s@]*)$/.exec(before);
    const startsAt = match ? before.length - match[0].length : -1;
    const validTrigger = match && (startsAt === 0 || /\s/.test(before[startsAt - 1]));
    const query = validTrigger ? match[1].toLocaleLowerCase() : "";
    const candidates = validTrigger ? ui.messengerMembers.filter((member) => member.id !== state.user?.id && member.name.toLocaleLowerCase().startsWith(query)).slice(0, 8) : [];
    if (list) {
      list.innerHTML = candidates.map((member) => `<button type="button" role="option" data-action="insert-chat-mention" data-user="${escapeHTML(member.id)}">${avatar(member.name, { size: "xxs", tone: member.avatarTone })}<span>${escapeHTML(member.name)}</span></button>`).join("");
      list.hidden = !candidates.length;
    }
  }
  if (event.target.id === "global-search") {
    ui.searchQuery = event.target.value;
    ui.searchOpen = true;
    const results = document.querySelector("#search-results");
    if (results) results.innerHTML = renderSearchResults(ui.searchQuery);
    const clear = document.querySelector(".global-search__clear");
    if (clear) clear.hidden = !ui.searchQuery;
  }
  if (event.target.id === "squad-search") {
    ui.squadQuery = event.target.value;
    applyRosterFilter();
  }
});

document.addEventListener("focusin", (event) => {
  if (event.target.id === "global-search") {
    ui.searchOpen = true;
    const results = document.querySelector("#search-results");
    if (results) results.innerHTML = renderSearchResults(ui.searchQuery);
  }
});

document.addEventListener("change", async (event) => {
  if (event.target.matches('[data-duty-field="event_key"]')) {
    const option = event.target.selectedOptions[0];
    if (option?.dataset.startAt) {
      const start = new Date(option.dataset.startAt);
      const local = new Date(start.getTime() - start.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
    const entry = event.target.closest("[data-duty-entry]");
      entry.querySelector('[data-duty-field="date"]').value = local.slice(0, 10);
      entry.querySelector('[data-duty-field="time"]').value = local.slice(11, 16);
    }
  }
  if (event.target.matches('select[name="category"]')) {
    const gameField = event.target.form?.querySelector(".poll-game-field");
    const pickupDateField = event.target.form?.querySelector(".poll-pickup-date-field");
    const customOptions = event.target.form?.querySelector(".poll-custom-options");
    const pickupLocation = event.target.form?.querySelector(".poll-pickup-location");
    const communityField = event.target.form?.querySelector(".poll-community-field");
    if (gameField) {
      const needsGameTime = event.target.value === "Competition";
      gameField.hidden = !needsGameTime;
      const gameInput = gameField.querySelector('input[name="gameAt"]');
      if (gameInput) gameInput.required = needsGameTime;
    }
    if (pickupDateField) {
      const needsPickupDate = event.target.value === "Pickup";
      pickupDateField.hidden = !needsPickupDate;
      pickupDateField.querySelectorAll("input").forEach((input) => { input.required = needsPickupDate; });
    }
    if (pickupLocation) pickupLocation.hidden = event.target.value !== "Pickup";
    if (customOptions) {
      const fixedPickupOptions = event.target.value === "Pickup";
      customOptions.hidden = fixedPickupOptions;
      customOptions.querySelectorAll("input").forEach((input) => { input.disabled = fixedPickupOptions; });
    }
    if (communityField) {
      const needsCommunity = ["Pickup", "Competition"].includes(event.target.value);
      communityField.hidden = !needsCommunity;
      const communityInput = communityField.querySelector('select[name="community_id"]');
      if (communityInput) communityInput.required = needsCommunity;
    }
  }
  if (event.target.dataset.filter === "home-news-community") {
    ui.homeNewsCommunityId = event.target.value;
    refresh({ preserveScroll: true });
  }
  if (event.target.dataset.filter === "home-news-sort") {
    ui.homeNewsSort = event.target.value;
    refresh({ preserveScroll: true });
  }
  if (event.target.id === "team-select") {
    ui.selectedTeamId = event.target.value;
    ui.lineupSelected = null;
    refresh({ preserveScroll: true });
  }
  if (event.target.id === "calendar-community") {
    ui.calendarCommunityId = event.target.value;
    await loadCalendar();
    refresh({ preserveScroll: true });
  }
  if (event.target.id === "formation-select") {
    const team = currentTeam();
    if (!team) return;
    const formation = event.target.value;
    const lineup = autoLineup(team, formation);
    ui.lineupSelected = null;
    const result = await apiCommit(
      () => api.patch(`/teams/${team.id}`, { formation, starting_xi: lineup }),
      { successMessage: `Switched to ${formation}. The XI reshuffled automatically.` },
    );
    if (!result) refresh();
  }
});

document.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    const input = document.querySelector("#global-search");
    input?.focus();
    input?.select();
  }
  if (event.key === "Escape") {
    ui.searchOpen = false;
    if (ui.notificationsOpen) {
      ui.notificationsOpen = false;
      renderApp({ preserveScroll: true });
    }
    hideSearchResults();
  }
  if (event.key === "Enter" && event.target.id === "global-search") {
    const first = document.querySelector(".search-result");
    if (first) {
      event.preventDefault();
      jumpToSearchResult(first.dataset.type, first.dataset.id);
    }
  }
});

window.addEventListener("hashchange", async () => {
  ui.searchQuery = "";
  ui.searchOpen = false;
  ui.notificationsOpen = false;
  ui.lineupSelected = null;
  if ((window.location.hash || "#/home") === "#/calendar") await loadCalendar();
  renderApp({ scrollTop: true });
  const communityRoute = currentCommunityRoute();
  if (communityRoute) selectCommunityChat(communityRoute.communityId);
});

async function loadCalendar() {
  const available = state.communities.filter((community) => community.joined || state.user.role === "Super Admin");
  if (!available.length) { ui.calendarCommunityId = null; state.calendarEntries = []; return; }
  if (!available.some((community) => community.id === ui.calendarCommunityId)) ui.calendarCommunityId = available[0].id;
  const grid = new Date(`${ui.calendarMonth ?? monthKey()}-01T12:00:00`);
  const from = localDayKey(new Date(grid.getFullYear(), grid.getMonth(), 1 - grid.getDay()));
  const to = localDayKey(new Date(grid.getFullYear(), grid.getMonth() + 1, 14));
  try {
    const result = await api.get(`/calendar?community_id=${encodeURIComponent(ui.calendarCommunityId)}&from=${from}&to=${to}`);
    state.calendarEntries = result.entries;
    state.duties = result.entries.filter((entry) => entry.source === "duty").map((entry) => entry.duty);
  } catch (error) { handleApiError(error); }
}

// Deep-link squad row click → go to player profile page
document.addEventListener("click", (event) => {
  const link = event.target.closest("[data-action='open-player']");
  if (!link) return;
  event.preventDefault();
  const pid = link.dataset.player;
  if (pid) window.location.hash = `#/player/${pid}`;
}, { capture: true });

const modal = getModal();
if (modal) {
  modal.addEventListener("click", (event) => {
    if (event.target === modal) closeModal();
  });
  modal.addEventListener("close", () => {
    modal.innerHTML = "";
    if (ui.messengerCommunityId) mountMessengerPanel();
  });
}

let membershipRefreshInFlight = false;

async function refreshMembershipAcrossDevices() {
  if (!state || document.hidden || membershipRefreshInFlight) return;
  membershipRefreshInFlight = true;
  try {
    const previousCommunities = state.communities ?? [];
    const next = await refreshState();
    const membershipChanged = previousCommunities.some((previous) => {
      const current = next.communities?.find((community) => community.id === previous.id);
      return current && (current.joined !== previous.joined || current.joinRequestStatus !== previous.joinRequestStatus || current.memberCount !== previous.memberCount);
    }) || (next.communities ?? []).some((current) => !previousCommunities.some((previous) => previous.id === current.id));
    setState(next);
    state = next;

    if (membershipChanged) {
      if (!next.plans.some((plan) => plan.id === ui.selectedPlanId)) ui.selectedPlanId = next.plans[0]?.id ?? null;
      renderApp({ preserveScroll: true });
      const modal = getModal();
      const openCommunity = next.communities.find((community) => community.id === ui.openCommunityId);
      if (modal?.open && openCommunity) {
        const members = openCommunity.joined || next.user?.role === "Super Admin"
          ? await api.get(`/communities/${openCommunity.id}/members`)
          : [];
        openCommunityModal(state, openCommunity.id, ui, members);
      }
    }

    if (ui.messengerCommunityId) {
      const communityId = ui.messengerCommunityId;
      if (!ui.messengerMinimized) ui.messengerMessages = await api.get(`/communities/${communityId}/messages`);
      if (!ui.messengerMinimized) {
        const current = state.communities.find((item) => item.id === communityId);
        if (current) current.unreadCount = 0;
      }
      mountMessengerPanel();
    }
  } catch { /* Polling is best effort; the next refresh or user action can retry. */ }
  finally { membershipRefreshInFlight = false; }
}

window.setInterval(refreshMembershipAcrossDevices, 8000);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) refreshMembershipAcrossDevices();
});
window.addEventListener("focus", refreshMembershipAcrossDevices);

if (!window.location.hash) {
  history.replaceState(null, "", `${window.location.pathname}${window.location.search}#/home`);
}
boot();
