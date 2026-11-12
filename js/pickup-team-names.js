const COLORS = ["Blue", "Red", "Green", "Yellow"];
const PAIRS = COLORS.flatMap((first) => COLORS.filter((second) => second !== first).map((second) => [`Yolo ${first}`, `Yolo ${second}`]));

export function pickupTeamNames(seed = 0) {
  const input = Number(seed);
  const value = Number.isFinite(input)
    ? Math.abs(Math.trunc(input))
    : [...String(seed)].reduce((sum, char) => (sum * 31 + char.charCodeAt(0)) >>> 0, 0);
  return PAIRS[(value * 7 + 13) % PAIRS.length];
}

export function pickupTeamTone(name = "") {
  const color = String(name).split(/\s+/).at(-1)?.toLowerCase();
  return COLORS.some((candidate) => candidate.toLowerCase() === color) ? color : "blue";
}
