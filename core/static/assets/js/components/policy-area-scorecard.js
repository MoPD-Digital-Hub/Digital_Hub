import { createDpmesPeriodFilter } from "./dpmes-period-filter.js";

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderSkeletons(track, options = {}) {
  const skeletonCount = options.variant === "grid" ? 12 : 4;
  const cardClass = options.variant === "grid" ? " policy-area-card-grid" : "";
  track.innerHTML = Array.from({ length: skeletonCount })
    .map(
      () => `
        <article class="policy-area-card policy-area-card-skeleton${cardClass}">
          ${
            options.variant === "grid"
              ? `<div class="policy-area-card-media">
                  <div class="policy-area-card-media-skeleton"></div>
                </div>`
              : ""
          }
          <div class="policy-area-card-shell">
            <div class="policy-area-card-top">
              <span class="policy-area-rank policy-area-skeleton-chip"></span>
              <span class="policy-area-score policy-area-skeleton-pill"></span>
            </div>
            <div class="policy-area-card-body">
              <div class="policy-area-skeleton-title"></div>
              <div class="policy-area-skeleton-title policy-area-skeleton-title--short"></div>
              ${
                options.variant === "grid"
                  ? `
                    <div class="policy-area-skeleton-meta"></div>
                    <div class="policy-area-progress">
                      <span class="policy-area-progress-bar policy-area-progress-bar--skeleton"></span>
                    </div>
                    <div class="policy-area-card-footer">
                      <span class="policy-area-skeleton-meta policy-area-skeleton-meta--inline"></span>
                      <span class="policy-area-skeleton-meta policy-area-skeleton-meta--value"></span>
                    </div>
                  `
                  : ""
              }
            </div>
          </div>
        </article>
      `
    )
    .join("");
}

function getFilterScope(root) {
  return root.closest(".policy-area-list-page") || root.parentElement || document;
}

function logFilterChange(reason, state, endpoint) {
  console.log("[policy-area-filter]", {
    reason,
    dateType: state.dateType,
    year: state.year,
    quarter: state.dateType === "quarterly" ? state.quarter : null,
    search: state.searchTerm || "",
    endpoint,
  });
}

function normalizeItems(payload, options = {}) {
  const items = Array.isArray(payload?.data) ? payload.data : [];
  return items
    .filter((item) => item && (options.showAll || item.show_mobile_dashboard))
    .sort((left, right) => Number(left.rank || 999) - Number(right.rank || 999));
}

function filterItemsBySearch(items, searchTerm) {
  const normalizedSearch = String(searchTerm || "").trim().toLowerCase();
  if (!normalizedSearch) {
    return items;
  }

  return items.filter((item) => {
    const title = item?.policyAreaEng || item?.policyAreaAmh || "";
    const code = item?.policyAreaCode || item?.code || "";
    return `${title} ${code}`.toLowerCase().includes(normalizedSearch);
  });
}

function renderCards(track, items, options = {}, filterState) {
  if (!items.length) {
    track.innerHTML = `<div class="policy-area-empty">No policy areas match the current filters.</div>`;
    return;
  }

  const params = new URLSearchParams();
  params.set("year", filterState.year);
  if (filterState.dateType === "quarterly") {
    params.set("quarter", filterState.quarter);
  }
  const queryString = params.toString();

  track.innerHTML = items
    .map((item) => {
      const score = item?.policy_area_score_card?.avg_score;
      const scoreColor = item?.policy_area_score_card?.scorecard_color || "#5d9444";
      const icon = item?.image_icon || "";
      const cardClass = options.variant === "grid" ? " policy-area-card-grid" : "";
      const title = item?.policyAreaEng || item?.policyAreaAmh || "Policy Area";
      const image = item?.bg_image || "";
      const numericScore = Number(score);
      const hasScore = Number.isFinite(numericScore);
      const scoreText = hasScore ? `${numericScore.toFixed(2)}%` : "--";
      const progressValue = hasScore ? Math.max(0, Math.min(numericScore, 100)) : 0;
      const inlineStyle =
        options.variant === "grid"
          ? `--policy-area-accent:${escapeHtml(scoreColor)}`
          : `--policy-area-accent:${escapeHtml(scoreColor)}; --policy-area-bg:url('${escapeHtml(image)}')`;
      return `
        <a
          class="policy-area-card${cardClass}"
          href="/dashboard/statistics/policy-areas/${escapeHtml(item.id)}/?${escapeHtml(queryString)}"
          style="${inlineStyle}"
        >
          ${
            options.variant === "grid"
              ? `<div class="policy-area-card-media">
                  ${
                    image
                      ? `<img src="${escapeHtml(image)}" alt="${escapeHtml(title)}" loading="lazy" decoding="async" fetchpriority="low" sizes="(max-width: 767px) 100vw, 180px">`
                      : `<div class="policy-area-card-media-fallback"></div>`
                  }
                </div>`
              : ""
          }
          <div class="policy-area-card-shell">
            <div class="policy-area-card-overlay"></div>
            <div class="policy-area-card-top">
              <span class="policy-area-rank" aria-hidden="true">
                ${
                  icon
                    ? `<img src="${escapeHtml(icon)}" alt="" loading="lazy" decoding="async" fetchpriority="low" sizes="15px">`
                    : `<i class="ti ti-chart-pie-2"></i>`
                }
              </span>
              <span class="policy-area-card-meta">Policy Area</span>
            </div>
            <div class="policy-area-card-body">
              <div class="policy-area-card-copy">
                <h3>${escapeHtml(title)}</h3>
                <p class="policy-area-card-kicker">Performance overview</p>
              </div>
              <div class="policy-area-card-scoreblock">
                <small>Average score</small>
                <span class="policy-area-score">${escapeHtml(scoreText)}</span>
              </div>
              ${
                options.variant === "grid"
                  ? `
                    <div class="policy-area-progress" aria-hidden="true">
                      <span class="policy-area-progress-bar" style="width:${escapeHtml(progressValue)}%; background:${escapeHtml(scoreColor)}"></span>
                    </div>
                    <div class="policy-area-card-footer">
                      <span>Open scorecard</span>
                      <strong>${escapeHtml(progressValue.toFixed(0))}% complete</strong>
                    </div>
                  `
                  : ""
              }
            </div>
          </div>
        </a>
      `;
    })
    .join("");
}

function bindNavigation(root) {
  const viewport = root.querySelector("[data-policy-area-viewport]");
  const prev = root.querySelector("[data-policy-area-prev]");
  const next = root.querySelector("[data-policy-area-next]");

  if (!viewport || !prev || !next) {
    return;
  }

  prev.addEventListener("click", () => {
    viewport.scrollBy({ left: -320, behavior: "smooth" });
  });

  next.addEventListener("click", () => {
    viewport.scrollBy({ left: 320, behavior: "smooth" });
  });
}

async function loadData(root, state) {
  const track = root.querySelector("[data-policy-area-track]");
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
    track.innerHTML = `<div class="policy-area-empty">Unable to load policy area scorecards right now.</div>`;
  }
}

async function init(root) {
  const endpoint = root.dataset.endpoint;
  const track = root.querySelector("[data-policy-area-track]");
  if (!endpoint || !track) {
    return;
  }

  const scope = getFilterScope(root);
  const searchInput = scope.querySelector("[data-policy-area-search]");
  const options = {
    showAll: root.dataset.showAll === "true",
    variant: root.dataset.variant || "",
  };

  const state = {
    endpoint,
    options,
    searchTerm: "",
    lastItems: [],
    filterState: {
      year: root.dataset.defaultYear || "2018",
      quarter: root.dataset.defaultQuarter || "3month",
      dateType: "quarterly",
    },
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

  const filter = await createDpmesPeriodFilter(scope, {
    dateTypeButtonsSelector: "[data-policy-area-date-type-btn]",
    periodSelectSelector: "[data-policy-area-period]",
    yearsEndpoint: root.dataset.yearsEndpoint || "/api/mobile/dpmes-year-lists/",
    defaultTimeEndpoint: root.dataset.defaultTimeEndpoint || "/api/mobile/default-time/",
    initialState,
    startYear: root.dataset.startYear || 2010,
    onChange: async (filterState, reason, api) => {
      state.filterState = filterState;
      state.endpoint = api.buildEndpoint(root.dataset.endpointBase || "/api/mobile/policy-areas/");
      logFilterChange(reason, { ...filterState, searchTerm: state.searchTerm }, state.endpoint);
      await loadData(root, state);
    },
  });

  state.filterState = filter.getState();
  state.endpoint = filter.buildEndpoint(root.dataset.endpointBase || "/api/mobile/policy-areas/");

  if (searchInput) {
    searchInput.addEventListener("input", () => {
      state.searchTerm = searchInput.value.trim();
      logFilterChange("search", { ...state.filterState, searchTerm: state.searchTerm }, state.endpoint);
      renderCards(track, filterItemsBySearch(state.lastItems || [], state.searchTerm), options, state.filterState);
    });
  }

  bindNavigation(root);
  await loadData(root, state);
}

export const PolicyAreaScorecard = {
  init,
  initAll(selector = "[data-policy-area-scorecard]") {
    document.querySelectorAll(selector).forEach((root) => {
      this.init(root);
    });
  },
};
