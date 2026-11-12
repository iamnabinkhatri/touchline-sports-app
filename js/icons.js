const paths = {
  home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M9.5 21v-7h5v7"/>',
  users:
    '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  poll:
    '<path d="M4 20V10"/><path d="M10 20V4"/><path d="M16 20v-7"/><path d="M22 20H2"/><circle cx="4" cy="7" r="1.4"/><circle cx="10" cy="7" r="1.4"/><circle cx="16" cy="7" r="1.4"/>',
  team:
    '<path d="M12 21s8-3.7 8-9.4V5.3L12 2.5 4 5.3v6.3C4 17.3 12 21 12 21Z"/><path d="m8.7 11.8 2.1 2.1 4.6-4.6"/>',
  clipboard:
    '<rect x="8" y="2.5" width="8" height="4" rx="1.2"/><path d="M16 4.5h2a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-13a2 2 0 0 1 2-2h2"/><path d="M8 12h8M8 16h5"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
  bell:
    '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  minus: '<path d="M5 12h14"/>',
  arrowRight: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  arrowUpRight: '<path d="M7 17 17 7M8 7h9v9"/>',
  chevronDown: '<path d="m6 9 6 6 6-6"/>',
  chevronRight: '<path d="m9 18 6-6-6-6"/>',
  chevronLeft: '<path d="m15 18-6-6 6-6"/>',
  heart:
    '<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.6l-1-1a5.5 5.5 0 0 0-7.8 7.8l1 1L12 21l7.8-7.6 1-1a5.5 5.5 0 0 0 0-7.8Z"/>',
  message:
    '<path d="M21 14.5a4.5 4.5 0 0 1-4.5 4.5H8l-5 3V7a4.5 4.5 0 0 1 4.5-4.5h9A4.5 4.5 0 0 1 21 7Z"/>',
  share:
    '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="m8.6 13.5 6.8 4M15.4 6.5l-6.8 4"/>',
  more: '<circle cx="5" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="19" cy="12" r="1" fill="currentColor" stroke="none"/>',
  close: '<path d="M18 6 6 18M6 6l12 12"/>',
  check: '<path d="m20 6-11 11-5-5"/>',
  calendar:
    '<rect x="3" y="4.5" width="18" height="16.5" rx="2.5"/><path d="M16 2.5v4M8 2.5v4M3 10h18"/>',
  pin: '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.2 2"/>',
  key: '<circle cx="8" cy="15" r="4"/><path d="m10.8 12.2 8.7-8.7 2 2-2 2 1.5 1.5-2.2 2.2-1.5-1.5-3.7 3.7"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/>',
  trophy:
    '<path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0V4Z"/><path d="M7 6H4a3 3 0 0 0 3 5M17 6h3a3 3 0 0 1-3 5"/>',
  ball:
    '<circle cx="12" cy="12" r="9"/><path d="m12 7.4 3.7 2.7-1.4 4.3h-4.6L8.3 10 12 7.4Z"/><path d="m12 7.4.8-4.2M8.3 10l-4-1.3M15.7 10l4-1.3M9.7 14.4l-2.4 4M14.3 14.4l2.4 4"/>',
  sparkle:
    '<path d="m12 2.8 1.9 5.5 5.5 1.9-5.5 1.9-1.9 5.5-1.9-5.5-5.5-1.9 5.5-1.9 1.9-5.5Z"/><path d="m19 16 .8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8L19 16Z"/>',
  filter: '<path d="M4 6h16M7 12h10M10 18h4"/>',
  edit:
    '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  settings:
    '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06A1.7 1.7 0 0 0 15 19.38a1.7 1.7 0 0 0-1 1.55V21a2 2 0 1 1-4 0v-.09a1.7 1.7 0 0 0-1.1-1.55 1.7 1.7 0 0 0-1.88.35l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.55-1H3a2 2 0 1 1 0-4h.09A1.7 1.7 0 0 0 4.64 8.9a1.7 1.7 0 0 0-.35-1.88l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.55V3a2 2 0 1 1 4 0v.09a1.7 1.7 0 0 0 1 1.55 1.7 1.7 0 0 0 1.88-.35l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.7 1.7 0 0 0 19.4 9v.09a1.7 1.7 0 0 0 1.55 1H21a2 2 0 1 1 0 4h-.09a1.7 1.7 0 0 0-1.51 1Z"/>',
  user: '<circle cx="12" cy="7" r="4"/><path d="M4 21v-1a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v1"/>',
  userPlus:
    '<circle cx="9" cy="7" r="4"/><path d="M2 21v-2a5 5 0 0 1 5-5h4a5 5 0 0 1 5 5v2M19 8v6M16 11h6"/>',
  lock: '<rect x="4" y="10" width="16" height="11" rx="2.5"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
  globe:
    '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a15 15 0 0 1 0 18 15 15 0 0 1 0-18Z"/>',
  reset:
    '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>',
  send: '<path d="m22 2-7 20-4-9-9-4 20-7Z"/><path d="M22 2 11 13"/>',
  flag:
    '<path d="M5 22V3"/><path d="M5 4c4.5-2.7 9 2.7 14 0v9c-5 2.7-9.5-2.7-14 0"/>',
  target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.3" fill="currentColor" stroke="none"/>',
  layers:
    '<path d="m12 2.8 9 4.5-9 4.5-9-4.5 9-4.5Z"/><path d="m3 12.5 9 4.5 9-4.5"/><path d="m3 17 9 4.5 9-4.5"/>',
  location:
    '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/>',
  whistle:
    '<path d="M3 12h9l3-5 5 2-2 6H8a5 5 0 1 1-5-5Z"/><path d="M14 10h5M12 16l1 4"/>',
  bolt: '<path d="m13 2-9 12h7l-1 8 9-12h-7l1-8Z"/>',
  dotsGrid:
    '<circle cx="5" cy="5" r="1.2" fill="currentColor" stroke="none"/><circle cx="12" cy="5" r="1.2" fill="currentColor" stroke="none"/><circle cx="19" cy="5" r="1.2" fill="currentColor" stroke="none"/><circle cx="5" cy="12" r="1.2" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1.2" fill="currentColor" stroke="none"/><circle cx="19" cy="12" r="1.2" fill="currentColor" stroke="none"/><circle cx="5" cy="19" r="1.2" fill="currentColor" stroke="none"/><circle cx="12" cy="19" r="1.2" fill="currentColor" stroke="none"/><circle cx="19" cy="19" r="1.2" fill="currentColor" stroke="none"/>',
  arrowLeft: '<path d="M19 12H5M11 18l-6-6 6-6"/>',
  eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
  shuffle:
    '<path d="m18 14 4 4-4 4"/><path d="m18 2 4 4-4 4"/><path d="M2 18h1.97a4 4 0 0 0 3.3-1.7l5.46-8.6a4 4 0 0 1 3.3-1.7H22"/><path d="M2 6h1.97a4 4 0 0 1 3.3 1.7l.35.55"/><path d="M22 18h-6.67a4 4 0 0 1-3.3-1.7l-.35-.55"/>',
  star:
    '<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9L12 3Z"/>',
  scale:
    '<path d="M12 3v18M6 7h12M6 7l-3 6h6L6 7ZM18 7l-3 6h6l-3-6Z"/><path d="M8 21h8"/>',
  coffee:
    '<path d="M4 8h13v6a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5V8Z"/><path d="M17 10h1.5a2.5 2.5 0 0 1 0 5H17"/><path d="M8 2.5c-.6 1 .6 1.6 0 2.8M12 2.5c-.6 1 .6 1.6 0 2.8"/>',
  donut:
    '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="2.6"/><path d="M8 7.5l.8.6M15.5 8.2l-.6.8M16.2 15.4l-.8-.5M7.8 15.8l.6-.8"/>',
};

export function icon(name, size = 18, className = "") {
  const body = paths[name] ?? paths.sparkle;
  return `<svg class="icon ${className}" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
}

export function brandMark(size = 38) {
  return `<svg class="brand-mark" width="${size}" height="${size}" viewBox="0 0 42 42" fill="none" aria-hidden="true">
    <rect x="1" y="1" width="40" height="40" rx="13" fill="#D9FF4F"/>
    <path d="M10 7v28M32 7v28M10 21h22" stroke="#102A1E" stroke-width="1.8"/>
    <circle cx="21" cy="21" r="6.4" stroke="#102A1E" stroke-width="1.8"/>
    <path d="m21 17.8 2.9 2.1-1.1 3.4h-3.6L18.1 20l2.9-2.2Z" fill="#102A1E"/>
    <path d="M10 11.5h5.5v5H10v-5ZM26.5 25.5H32v5h-5.5v-5Z" fill="#102A1E"/>
  </svg>`;
}

export function sportGlyph(sport = "Soccer", size = 24) {
  if (sport === "Basketball") {
    return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3v18M5.6 5.6c3.5 2.5 3.5 10.3 0 12.8M18.4 5.6c-3.5 2.5-3.5 10.3 0 12.8"/></svg>`;
  }
  if (sport === "Running") {
    return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="15" cy="5" r="2"/><path d="m13 9-3 4 4 2 1 5M10 13l-4 2M13 8l4 3 3-1M8 21l2-4"/></svg>`;
  }
  if (sport === "Volleyball") {
    return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 3c2.7 4.5 2.8 9.7.3 14M4.7 7.5c4.7.5 9.2 3 11.9 7.5M7.2 20c1.4-4.7 5.2-8.5 10-9.8"/></svg>`;
  }
  if (sport === "Tennis") {
    return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M5 5.4c4 2.6 4 10.6 0 13.2M19 5.4c-4 2.6-4 10.6 0 13.2"/></svg>`;
  }
  if (sport === "Baseball") {
    return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M6.3 5.2c1.9 4.2 1.9 9.4 0 13.6M17.7 5.2c-1.9 4.2-1.9 9.4 0 13.6"/></svg>`;
  }
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="m12 7.4 3.7 2.7-1.4 4.3h-4.6L8.3 10 12 7.4Z"/><path d="m12 7.4.8-4.2M8.3 10l-4-1.3M15.7 10l4-1.3M9.7 14.4l-2.4 4M14.3 14.4l2.4 4"/></svg>`;
}
