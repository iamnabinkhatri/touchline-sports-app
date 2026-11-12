export function filterCommunities(communities, sport = "All") {
  const normalizedSport = String(sport || "All").trim().toLowerCase();
  return (communities ?? []).filter((community) =>
    normalizedSport === "all" || String(community.sport || "").trim().toLowerCase() === normalizedSport,
  );
}

export function visibleDiscoverCommunities(communities, showAll = false, pageSize = 5) {
  const items = communities ?? [];
  return {
    items: showAll ? items : items.slice(0, pageSize),
    hasMore: !showAll && items.length > pageSize,
    hiddenCount: showAll ? 0 : Math.max(0, items.length - pageSize),
  };
}

export function rankSearchResults(results, query = "", limit = 8) {
  const normalized = String(query || "").trim().toLowerCase();
  return (results ?? [])
    .map((result, index) => {
      const title = String(result.title || "").toLowerCase();
      const words = title.split(/\s+/);
      const searchable = [result.title, result.meta, result.keywords].filter(Boolean).join(" ").toLowerCase();
      let score = 0;
      if (!normalized) score = Number(result.recommendationScore ?? 0);
      else if (title === normalized) score = 100;
      else if (title.startsWith(normalized)) score = 80;
      else if (words.some((word) => word.startsWith(normalized))) score = 70;
      else if (title.includes(normalized)) score = 55;
      else if (searchable.includes(normalized)) score = 25;
      return { ...result, score, originalIndex: index };
    })
    .filter((result) => result.score > 0)
    .sort((left, right) => right.score - left.score || left.originalIndex - right.originalIndex)
    .slice(0, limit);
}
