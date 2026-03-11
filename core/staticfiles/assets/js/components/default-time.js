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

export async function fetchDefaultTime(endpoint = "/api/mobile/default-time/") {
  const payload = await fetchJson(endpoint);
  const data = payload?.data && typeof payload.data === "object" ? payload.data : {};
  return {
    year: data?.year != null ? String(data.year) : "",
    quarter: data?.quarter || "3month",
    dateType: data?.is_quarter ? "quarterly" : "yearly",
  };
}

export async function resolveDefaultTime({
  endpoint = "/api/mobile/default-time/",
  fallback = {},
} = {}) {
  try {
    const resolved = await fetchDefaultTime(endpoint);
    if (!resolved.year) {
      throw new Error("Missing default year");
    }
    return {
      year: resolved.year,
      quarter: resolved.quarter || fallback.quarter || "3month",
      dateType: resolved.dateType || fallback.dateType || "quarterly",
    };
  } catch (_error) {
    return {
      year: fallback.year || String(new Date().getFullYear()),
      quarter: fallback.quarter || "3month",
      dateType: fallback.dateType || "quarterly",
    };
  }
}
