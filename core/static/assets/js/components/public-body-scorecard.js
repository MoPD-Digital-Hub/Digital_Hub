import { createDpmesPeriodFilter } from "./dpmes-period-filter.js";

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatScore(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? `${numeric.toFixed(2)}%` : "--";
}

function indicatorLabel(count) {
  const numeric = Number(count || 0);
  return `${numeric} indicator${numeric === 1 ? "" : "s"}`;
}

function formatPeriodLabel(filterState) {
  const quarterMap = {
    "3month": "Q1",
    "6month": "Q2",
    "9month": "Q3",
    "12month": "Q4",
  };

  if (filterState?.year && filterState?.dateType === "quarterly" && filterState?.quarter) {
    return `${filterState.year} ${quarterMap[filterState.quarter] || filterState.quarter}`;
  }

  if (filterState?.year) {
    return String(filterState.year);
  }

  return "Current period";
}

function buildImageUrl(value) {
  if (!value) {
    return "";
  }
  try {
    return new URL(value, window.location.origin).toString();
  } catch (_error) {
    return value;
  }
}

function renderSkeletons(track, options = {}) {
  const count = options.variant === "grid" ? 12 : 4;
  track.innerHTML = Array.from({ length: count }, () => `<div class="ministry-card-skeleton"></div>`).join("");
}

function renderEmpty(track, message) {
  track.innerHTML = `<div class="ministry-card-empty">${escapeHtml(message)}</div>`;
}

function renderError(track) {
  renderEmpty(track, "Unable to load public body scorecards right now.");
}

function normalizeItems(payload, options = {}) {
  const items = Array.isArray(payload?.data) ? payload.data : [];
  return items
    .filter((item) => item && item.ministry_is_visable && (options.showAll || item.show_mobile_dashboard))
    .sort((left, right) => Number(left.ministry_rank || 9999) - Number(right.ministry_rank || 9999));
}

function filterItemsBySearch(items, searchTerm) {
  const normalizedSearch = String(searchTerm || "").trim().toLowerCase();
  if (!normalizedSearch) {
    return items;
  }

  return items.filter((item) => {
    const title = item?.responsible_ministry_eng || item?.responsible_ministry_amh || "";
    const code = item?.code || "";
    return `${title} ${code}`.toLowerCase().includes(normalizedSearch);
  });
}

function createGridCard(item, filterState) {
  const accent = item.ministry_score_card?.scorecard_color || "#0f766e";
  const score = formatScore(item.ministry_score_card?.avg_score);
  const code = item.code || "N/A";
  const title = item.responsible_ministry_eng || item.responsible_ministry_amh || "Public Body";
  const logo = buildImageUrl(item.image);
  const indicators = indicatorLabel(item.count_indicator);
  const periodLabel = formatPeriodLabel(filterState);
  const params = new URLSearchParams({ year: filterState.year });
  if (filterState.dateType === "quarterly") {
    params.set("quarter", filterState.quarter);
  }

  return `
    <a class="ministry-card" href="/dashboard/statistics/public-bodies/${escapeHtml(item.id)}/?${escapeHtml(params.toString())}" style="--ministry-accent:${escapeHtml(accent)};">
      <div class="ministry-card-shell">
        <div class="ministry-card-mark">
          <span class="ministry-card-period">${escapeHtml(periodLabel)}</span>
        </div>
        <div class="ministry-card-body">
          <div class="ministry-card-logo">
            ${
              logo
                ? `<img src="${escapeHtml(logo)}" alt="${escapeHtml(code)} logo" loading="lazy" decoding="async" fetchpriority="low" sizes="40px">`
                : `<span>${escapeHtml(code.slice(0, 2))}</span>`
            }
          </div>
          <div class="ministry-card-heading">
            <h4>${escapeHtml(code)}</h4>
            <h5>${escapeHtml(title)}</h5>
          </div>
        </div>
        <div class="ministry-card-score">
          <div class="ministry-card-score-panel">
            <span>Score</span>
            <strong>${escapeHtml(score)}</strong>
          </div>
          <div class="ministry-card-side">
            <span class="ministry-card-indicators">${escapeHtml(indicators)}</span>
          </div>
        </div>
      </div>
    </a>
  `;
}

function renderCards(track, items, options = {}, filterState) {
  if (!items.length) {
    renderEmpty(track, "No public bodies match the current filters.");
    return;
  }

  track.innerHTML = items.map((item) => createGridCard(item, filterState)).join("");
}

function logFilterChange(reason, state, endpoint) {
  console.log("[public-body-filter]", {
    reason,
    dateType: state.dateType,
    year: state.year,
    quarter: state.dateType === "quarterly" ? state.quarter : null,
    search: state.searchTerm || "",
    endpoint,
  });
}

async function loadData(root, state) {
  const track = root.querySelector("[data-public-body-track]");
  if (!track) {
    return;
  }

  renderSkeletons(track, state.options);

  try {
    const response = await fetch(state.endpoint, {
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    const items = normalizeItems(payload, state.options);
    state.lastItems = items;
    renderCards(track, filterItemsBySearch(items, state.searchTerm), state.options, state.filterState);
  } catch (_error) {
    renderError(track);
  }
}

async function init(root) {
  if (!root) {
    return;
  }

  const endpoint = root.dataset.endpoint;
  const track = root.querySelector("[data-public-body-track]");
  if (!endpoint || !track) {
    return;
  }

  const scope = root.closest(".public-body-list-page") || root.parentElement || document;
  const searchInput = scope.querySelector("[data-public-body-search]");
  const options = {
    showAll: root.dataset.showAll === "true",
    variant: root.dataset.variant || "",
  };

  const initialParams = new URLSearchParams(window.location.search);
  const hasYearParam = initialParams.has("year");
  const hasQuarterParam = initialParams.has("quarter");
  const initialState = hasYearParam
    ? {
        year: initialParams.get("year") || "",
        quarter: hasQuarterParam ? initialParams.get("quarter") || "3month" : undefined,
        dateType: hasQuarterParam ? "quarterly" : "yearly",
      }
    : undefined;

  const state = {
    endpoint,
    options,
    searchTerm: "",
    lastItems: [],
    filterState: {
      year: root.dataset.defaultYear || "2017",
      quarter: root.dataset.defaultQuarter || "3month",
      dateType: "quarterly",
    },
  };

  const filter = await createDpmesPeriodFilter(scope, {
    dateTypeButtonsSelector: "[data-public-body-date-type-btn]",
    periodSelectSelector: "[data-public-body-period]",
    yearsEndpoint: root.dataset.yearsEndpoint || "/api/mobile/dpmes-year-lists/",
    defaultTimeEndpoint: root.dataset.defaultTimeEndpoint || "/api/mobile/default-time/",
    initialState,
    startYear: root.dataset.startYear || 2010,
    onChange: async (filterState, reason, api) => {
      state.filterState = filterState;
      state.endpoint = api.buildEndpoint(root.dataset.endpointBase || "/api/mobile/ministries/");
      logFilterChange(reason, { ...filterState, searchTerm: state.searchTerm }, state.endpoint);
      await loadData(root, state);
    },
  });

  state.filterState = filter.getState();
  state.endpoint = filter.buildEndpoint(root.dataset.endpointBase || "/api/mobile/ministries/");

  if (searchInput) {
    searchInput.addEventListener("input", () => {
      state.searchTerm = searchInput.value.trim();
      logFilterChange("search", { ...state.filterState, searchTerm: state.searchTerm }, state.endpoint);
      renderCards(track, filterItemsBySearch(state.lastItems || [], state.searchTerm), options, state.filterState);
    });
  }

  await loadData(root, state);
}

export const PublicBodyScorecard = {
  init,
  initAll(selector = "[data-public-body-scorecard]") {
    document.querySelectorAll(selector).forEach((root) => {
      this.init(root);
    });
  },
};

window.PublicBodyScorecard = PublicBodyScorecard;
