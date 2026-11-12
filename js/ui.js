import { icon, sportGlyph } from "./icons.js";
import { avatarTone, clamp, escapeHTML, initials, safeToken } from "./utils.js";

const AVATAR_TONES = ["forest", "lime", "coral", "sky", "violet", "gold", "sage", "red"];
const CREST_ACCENTS = ["forest", "lime", "coral", "sky", "violet", "gold", "sage", "red"];
const PLAYER_STATUSES = ["available", "doubtful", "out"];

export function safeImageData(value) {
  return typeof value === "string" && value.length < 230_000 && /^data:image\/(?:png|jpeg|webp);base64,[A-Za-z0-9+/]+={0,2}$/.test(value) ? value : "";
}

export function avatar(name, options = {}) {
  const size = options.size ?? "md";
  const fallbackTone = avatarTone(name);
  const tone = safeToken(options.tone ?? fallbackTone, AVATAR_TONES, fallbackTone);
  const className = options.className ? ` ${options.className}` : "";
  const imageData = safeImageData(options.imageData);
  if (imageData) return `<span class="avatar avatar--${size} avatar--${tone}${className} avatar--photo"><img src="${escapeHTML(imageData)}" alt=""></span>`;
  return `<span class="avatar avatar--${size} avatar--${tone}${className}" aria-hidden="true">${escapeHTML(initials(name))}</span>`;
}

export function crest(mark, accent = "forest", size = "md", label = "") {
  const accessible = label
    ? `role="img" aria-label="${escapeHTML(label)}"`
    : 'aria-hidden="true"';
  const safeAccent = safeToken(accent, CREST_ACCENTS, "forest");
  const safeSize = safeToken(size, ["xxs", "xs", "sm", "md", "lg", "xl"], "md");
  return `<span class="crest crest--${safeAccent} crest--${safeSize}" ${accessible}><span>${escapeHTML(mark)}</span></span>`;
}

export function communityMark(community, size = "md") {
  const imageData = safeImageData(community.logoData);
  if (imageData) return `<span class="crest crest--${safeToken(community.accent, CREST_ACCENTS, "forest")} crest--${safeToken(size, ["xxs", "xs", "sm", "md", "lg", "xl"], "md")} community-mark--photo" role="img" aria-label="${escapeHTML(community.name)}"><img src="${escapeHTML(imageData)}" alt=""></span>`;
  return crest(community.mark, community.accent, size, community.name);
}

export function sportIcon(sport, size = 22) {
  return sportGlyph(sport, size);
}

export function statusPill(status) {
  const labels = {
    available: "Available",
    doubtful: "Doubtful",
    out: "Out",
    unknown: "Unknown",
  };
  const key = PLAYER_STATUSES.includes(String(status)) ? String(status) : "unknown";
  return `<span class="status-pill status-pill--${key}"><span class="status-dot"></span>${escapeHTML(labels[key])}</span>`;
}

export function privacyPill(privacy) {
  const isPrivate = privacy === "Private";
  return `<span class="meta-pill">${icon(isPrivate ? "lock" : "globe", 12)}${escapeHTML(privacy)}</span>`;
}

export function countLabel(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric < 0) return "0";
  if (numeric >= 1_000_000) return `${(numeric / 1_000_000).toFixed(1).replace(".0", "")}m`;
  if (numeric >= 1_000) return `${(numeric / 1_000).toFixed(1).replace(".0", "")}k`;
  return String(numeric);
}

export function avatarStack(people, extra = 0) {
  return `<span class="avatar-stack">
    ${people
      .map(
        (person) =>
          `<span class="avatar-stack__item">${avatar(person.name, {
            size: "xs",
            tone: person.tone,
          })}</span>`,
      )
      .join("")}
    ${extra > 0 ? `<span class="avatar-stack__more">+${extra}</span>` : ""}
  </span>`;
}

export function emptyState({ iconName = "sparkle", title, text, action = "" }) {
  return `<div class="empty-state">
    <span class="empty-state__icon">${icon(iconName, 24)}</span>
    <h3>${escapeHTML(title)}</h3>
    <p>${escapeHTML(text)}</p>
    ${action}
  </div>`;
}

export function sectionHeading(title, subtitle = "", action = "") {
  return `<div class="section-heading">
    <div>
      <h2>${escapeHTML(title)}</h2>
      ${subtitle ? `<p>${escapeHTML(subtitle)}</p>` : ""}
    </div>
    ${action}
  </div>`;
}

export function getModal() {
  return document.querySelector("#app-modal");
}

export function openModal({ eyebrow = "", title, description = "", body, wide = false }) {
  const dialog = getModal();
  if (!dialog) return;
  const alreadyOpen = dialog.open;
  dialog.className = `modal${wide ? " modal--wide" : ""}`;
  dialog.setAttribute("aria-label", title);
  dialog.innerHTML = `<div class="modal__card" role="document">
    <header class="modal__head">
      <div>
        ${eyebrow ? `<p class="eyebrow">${escapeHTML(eyebrow)}</p>` : ""}
        <h2>${escapeHTML(title)}</h2>
        ${description ? `<p class="modal__description">${escapeHTML(description)}</p>` : ""}
      </div>
      <button class="icon-button icon-button--dark modal__close" type="button" data-action="close-modal" aria-label="Close dialog">
        ${icon("close", 19)}
      </button>
    </header>
    <div class="modal__body">${body}</div>
  </div>`;
  if (!alreadyOpen) dialog.showModal();
  requestAnimationFrame(() => {
    const focusTarget = dialog.querySelector(
      "input:not([type=hidden]), textarea, select, button",
    );
    focusTarget?.focus({ preventScroll: true });
  });
}

export function closeModal() {
  const dialog = getModal();
  if (dialog?.open) dialog.close();
}

export function toast(message, tone = "default") {
  const root = document.querySelector("#toast-root");
  if (!root) return;
  const item = document.createElement("div");
  item.className = `toast toast--${tone}`;
  item.innerHTML = `<span class="toast__icon">${icon(
    tone === "error" ? "close" : "check",
    16,
  )}</span><span>${escapeHTML(message)}</span>`;
  root.appendChild(item);
  requestAnimationFrame(() => item.classList.add("is-visible"));
  window.setTimeout(() => {
    item.classList.remove("is-visible");
    window.setTimeout(() => item.remove(), 240);
  }, 3_000);
}

export function progressRing(percent, label = "complete", size = 86) {
  const safe = Math.max(0, Math.min(100, percent));
  return `<div class="progress-ring" style="--progress:${safe};--ring-size:${size}px" role="img" aria-label="${safe}% ${escapeHTML(label)}">
    <span class="progress-ring__value">${safe}<small>%</small></span>
  </div>`;
}

export function voteIcon(selected) {
  return `<span class="vote-radio${selected ? " is-selected" : ""}">${
    selected ? icon("check", 11) : ""
  }</span>`;
}

export function ratingStars(value, size = "sm") {
  const numeric = Number(value) || 0;
  const filled = Math.round(clamp(numeric, 0, 10) / 2);
  return `<span class="rating-stars rating-stars--${size}" role="img" aria-label="${numeric.toFixed(1)} out of 10">${Array.from(
    { length: 5 },
    (_, index) =>
      `<span class="${index < filled ? "is-filled" : ""}" aria-hidden="true">★</span>`,
  ).join("")}</span>`;
}
