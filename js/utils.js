const DAY_MS = 86_400_000;

export function escapeHTML(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export function initials(name = "") {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

export function uid(prefix = "id") {
  if (globalThis.crypto?.randomUUID) {
    return `${prefix}-${crypto.randomUUID().slice(0, 8)}`;
  }
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
}

export function addDays(date, days) {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

export function atTime(date, hours = 14, minutes = 30) {
  const next = new Date(date);
  next.setHours(hours, minutes, 0, 0);
  return next;
}

export function nextWeekday(day, hours = 14, minutes = 30) {
  const now = new Date();
  const result = new Date(now);
  let delta = (day - now.getDay() + 7) % 7;
  result.setDate(now.getDate() + delta);
  result.setHours(hours, minutes, 0, 0);
  if (result <= now) {
    result.setDate(result.getDate() + 7);
  }
  return result;
}

export function daysFromNow(days, hours = 18, minutes = 0) {
  return atTime(addDays(new Date(), days), hours, minutes);
}

export function formatDate(value, options = {}) {
  const date = value instanceof Date ? value : new Date(value);
  return new Intl.DateTimeFormat("en-US", {
    weekday: options.weekday ?? "short",
    month: options.month ?? "short",
    day: options.day ?? "numeric",
    ...(options.year ? { year: "numeric" } : {}),
  }).format(date);
}

export function formatTime(value) {
  const date = value instanceof Date ? value : new Date(value);
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

export function formatDateTime(value) {
  return `${formatDate(value)} · ${formatTime(value)}`;
}

export function longDate(value, options = {}) {
  const date = value instanceof Date ? value : new Date(value);
  return new Intl.DateTimeFormat("en-US", {
    weekday: options.weekday ?? "long",
    month: options.month ?? "long",
    day: options.day ?? "numeric",
    ...(options.year ? { year: "numeric" } : {}),
  }).format(date);
}

export function timeUntil(value) {
  const target = value instanceof Date ? value : new Date(value);
  const diff = target.getTime() - Date.now();
  if (diff <= 0) return "Closed";
  const days = Math.floor(diff / DAY_MS);
  const hours = Math.floor((diff % DAY_MS) / 3_600_000);
  const minutes = Math.max(1, Math.floor((diff % 3_600_000) / 60_000));
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

export function closingLabel(value) {
  const target = value instanceof Date ? value : new Date(value);
  const diff = target.getTime() - Date.now();
  if (diff <= 0) return "Closed";
  if (diff < DAY_MS) return `${timeUntil(target)} left`;
  return `Ends ${formatDate(target)}`;
}

export function isOpen(value) {
  return new Date(value).getTime() > Date.now();
}

export function countdownParts(value) {
  const diff = Math.max(0, new Date(value).getTime() - Date.now());
  return {
    days: Math.floor(diff / DAY_MS),
    hours: Math.floor((diff % DAY_MS) / 3_600_000),
    minutes: Math.floor((diff % 3_600_000) / 60_000),
  };
}

export function greeting(name) {
  const hour = new Date().getHours();
  if (hour < 5) return `Late one, ${name}.`;
  if (hour < 12) return `Good morning, ${name}.`;
  if (hour < 18) return `Good afternoon, ${name}.`;
  return `Good evening, ${name}.`;
}

export function pad(value) {
  return String(value).padStart(2, "0");
}

export function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

export function sum(values) {
  return values.reduce((total, value) => total + value, 0);
}

export function plural(value, singular, pluralWord = `${singular}s`) {
  return `${value} ${value === 1 ? singular : pluralWord}`;
}

export function hashString(value = "") {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash << 5) - hash + value.charCodeAt(index);
    hash |= 0;
  }
  return Math.abs(hash);
}

export function avatarTone(name) {
  const tones = ["lime", "coral", "sky", "gold", "violet", "sage"];
  return tones[hashString(name) % tones.length];
}

/**
 * Normalizes a CSS class token against an explicit allowlist. State can come
 * back from localStorage, so never interpolate arbitrary values into a class
 * attribute without passing them through this helper.
 */
export function safeToken(value, allowedTokens = [], fallback = "") {
  const normalized = String(value ?? "")
    .trim()
    .toLowerCase();
  return allowedTokens.includes(normalized) ? normalized : fallback;
}

export function finiteNumber(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}
