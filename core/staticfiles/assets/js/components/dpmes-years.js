async function fetchJson(url) {
  const response = await fetch(url, {
    headers: { Accept: "application/json" },
    credentials: "same-origin",
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  return response.json();
}

export async function fetchDpmesYears(endpoint = "/api/mobile/dpmes-year-lists/") {
  const payload = await fetchJson(endpoint);
  const items = Array.isArray(payload?.years) ? payload.years : [];

  return items
    .filter((item) => item && item.visible)
    .map((item) => ({
      id: item.id,
      value: String(item.year_amh ?? item.year_eng ?? ""),
      label: String(item.year_amh ?? item.year_eng ?? ""),
      order: item.year_eng ?? item.year_amh ?? "",
      quarterView: Boolean(item.quarter_view),
      isCurrent: Boolean(item.is_current_year),
    }))
    .filter((item) => item.value);
}

export async function resolveDpmesYears({
  endpoint = "/api/mobile/dpmes-year-lists/",
  fallback = [],
} = {}) {
  try {
    const years = await fetchDpmesYears(endpoint);
    return years.length ? years : fallback;
  } catch (_error) {
    return fallback;
  }
}
