import { fetchBootstrap, startSession } from "./api.js";

const LEGACY_STORAGE_KEY = "touchline:clubhouse:v1";

let state = null;

export async function initApp() {
  try {
    localStorage.removeItem(LEGACY_STORAGE_KEY);
  } catch {
    // Legacy local state can stay if storage is unavailable.
  }
  state = await startSession();
  return state;
}

export function getState() {
  return state;
}

export function setState(nextState) {
  state = nextState;
}

export async function refreshState() {
  state = await fetchBootstrap();
  return state;
}

export function getTeam() {
  return state?.teams?.[0] ?? null;
}

export function getCommunity(id) {
  return state?.communities?.find((community) => community.id === id) ?? null;
}

export function getPoll(id) {
  return state?.polls?.find((poll) => poll.id === id) ?? null;
}

export function getPlayer(id) {
  return getTeam()?.players?.find((player) => player.id === id) ?? null;
}

export function getPlan(id) {
  return state?.plans?.find((plan) => plan.id === id) ?? null;
}

export function pollTotal(poll) {
  if (!poll?.options) return 0;
  return poll.options.reduce((total, option) => total + Number(option.votes || 0), 0);
}

export function pollPercent(option, poll) {
  const total = pollTotal(poll);
  if (!total) return 0;
  return Math.round((Number(option.votes || 0) / total) * 100);
}

export function planProgress(plan) {
  if (!plan?.checklist?.length) return 0;
  return Math.round(
    (plan.checklist.filter((item) => item.done).length / plan.checklist.length) * 100,
  );
}

export function teamAvailability(team) {
  return (team?.players ?? []).reduce(
    (counts, player) => {
      counts[player.status] = (counts[player.status] ?? 0) + 1;
      return counts;
    },
    { available: 0, doubtful: 0, out: 0 },
  );
}
