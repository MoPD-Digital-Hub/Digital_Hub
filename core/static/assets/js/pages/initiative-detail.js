const mediaBaseUrl = "https://time-series.mopd.gov.et/";
const ETHIOPIA_REGIONS = [
  { label: "Afar", value: "afar", badge: "AF" },
  { label: "Addis Ababa", value: "addis ababa", badge: "AA" },
  { label: "Amhara", value: "amhara", badge: "AM" },
  { label: "Benishangul-Gumuz", value: "benishangul-gumuz", badge: "BG" },
  { label: "Central Ethiopia", value: "central ethiopia", badge: "CE" },
  { label: "Dire Dawa", value: "dire dawa", badge: "DD" },
  { label: "Gambella", value: "gambella", badge: "GA" },
  { label: "Harari", value: "harari", badge: "HR" },
  { label: "Oromia", value: "oromia", badge: "OR" },
  { label: "Sidama", value: "sidama", badge: "SI" },
  { label: "Somali", value: "somali", badge: "SO" },
  { label: "South Ethiopia", value: "south ethiopia", badge: "SE" },
  { label: "South West Ethiopia", value: "south west ethiopia", badge: "SW" },
  { label: "Tigray", value: "tigray", badge: "TI" },
];

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function buildMediaUrl(path) {
  if (!path) {
    return "";
  }

  try {
    return new URL(path, mediaBaseUrl).toString();
  } catch (_error) {
    return path;
  }
}

function fetchJson(url) {
  return fetch(url, {
    headers: { Accept: "application/json" },
    credentials: "same-origin",
  }).then((response) => {
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    return response.json();
  });
}

function formatDate(value) {
  if (!value) {
    return "Not available";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(date);
}

function formatMetricValue(value) {
  if (value === null || value === undefined || value === "") {
    return "--";
  }

  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return String(value);
  }

  return numeric % 1 === 0 ? numeric.toFixed(0) : numeric.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
}

function getIndicatorScope(indicator) {
  if (indicator?.is_regional === true || indicator?.is_reginal === true) {
    return "national";
  }
  return "federal";
}

function getCategoryScope(category) {
  if (category?.is_regional === true || category?.is_reginal === true) {
    return "national";
  }
  return "federal";
}

function getSeriesByLatest(indicator) {
  const latest = String(indicator?.latest_data || indicator?.frequency || "").toLowerCase();
  const map = {
    annual: indicator?.annual_data || [],
    yearly: indicator?.annual_data || [],
    quarter: indicator?.quarter_data || [],
    quarterly: indicator?.quarter_data || [],
    month: indicator?.month_data || [],
    monthly: indicator?.month_data || [],
    week: indicator?.week_data || [],
    weekly: indicator?.week_data || [],
    day: indicator?.day_data || [],
    daily: indicator?.day_data || [],
  };

  return {
    latest,
    points: Array.isArray(map[latest]) ? map[latest] : [],
  };
}

function getPointLabel(point, latest) {
  if (latest === "quarter" || latest === "quarterly") {
    return `${point.for_datapoint || ""} ${point.for_quarter || ""}`.trim();
  }
  if (latest === "month" || latest === "monthly") {
    return `${point.for_datapoint || ""} ${point.for_month || ""}`.trim() || point.for_month || "Period";
  }
  return String(point.for_datapoint || point.for_month || point.for_quarter || "Period");
}

function renderIndicatorValuePanel(indicator) {
  const { latest, points } = getSeriesByLatest(indicator);
  const usablePoints = points.filter((point) => point && point.performance !== null && point.performance !== undefined);

  if (!usablePoints.length) {
    return `
      <div class="initiative-indicator-value-card">
        <div class="initiative-indicator-empty">No historical values available.</div>
      </div>
    `;
  }

  const selected = usablePoints[usablePoints.length - 1];
  const history = usablePoints.slice(-6).reverse();
  const unit = indicator[`measurement_units_${latest}`] || indicator.measurement_units || "";

  return `
    <div class="initiative-indicator-value-card" data-initiative-value-card>
      <div class="initiative-indicator-selected">
        <span class="initiative-indicator-period" data-initiative-selected-period>${escapeHtml(getPointLabel(selected, latest))}</span>
        <div class="initiative-indicator-metric">
          <strong data-initiative-selected-value>${escapeHtml(formatMetricValue(selected.performance))}</strong>
          <span>${escapeHtml(unit || "-")}</span>
        </div>
      </div>
      <div class="initiative-indicator-history-label">Recent values</div>
      <div class="initiative-indicator-history">
        ${history
          .map(
            (point, index) => `
              <button
                type="button"
                class="initiative-indicator-history-item${index === 0 ? " is-active" : ""}"
                data-initiative-history-item
                data-period="${escapeHtml(getPointLabel(point, latest))}"
                data-value="${escapeHtml(formatMetricValue(point.performance))}"
              >
                <span>${escapeHtml(getPointLabel(point, latest))}</span>
                <strong>${escapeHtml(formatMetricValue(point.performance))}</strong>
              </button>
            `
          )
          .join("")}
      </div>
    </div>
  `;
}

function renderIndicatorCard(indicator) {
  const scope = getIndicatorScope(indicator);

  return `
    <article class="initiative-indicator-card" data-indicator-scope="${escapeHtml(scope)}">
      <div class="initiative-indicator-head">
        <div class="initiative-indicator-copy">
          <div class="initiative-indicator-topline">
            <span class="initiative-indicator-scope initiative-indicator-scope--${escapeHtml(scope)}">${escapeHtml(scope)}</span>
            <span class="initiative-indicator-frequency">${escapeHtml(indicator.frequency || indicator.latest_data || "No frequency")}</span>
          </div>
          <h4>${escapeHtml(indicator.title_ENG || indicator.title_AMH || "Indicator")}</h4>
          <p>${escapeHtml(indicator.description || "No description available.")}</p>
        </div>
        <a class="initiative-indicator-open" href="/dashboard/data/indicator/${escapeHtml(indicator.id)}/" aria-label="Open indicator detail">
          <i class="ti ti-chevron-right"></i>
        </a>
      </div>
      ${renderIndicatorValuePanel(indicator)}
    </article>
  `;
}

function renderIndicatorList(indicators) {
  if (!Array.isArray(indicators) || !indicators.length) {
    return '<div class="initiative-indicator-empty">No indicators are available in this scope.</div>';
  }

  return `
    <div class="initiative-indicator-grid">
      ${indicators.map((indicator) => renderIndicatorCard(indicator)).join("")}
    </div>
  `;
}

function renderRegionSelector(categoryId) {
  return `
    <div class="initiative-category-region">
      <div class="initiative-category-region-label">Region view</div>
      <div class="initiative-region-switch" data-initiative-region-switch data-category-id="${escapeHtml(categoryId)}">
        <button type="button" class="initiative-region-chip is-active" data-region-name="">
          <span class="initiative-region-flag">ALL</span>
          <span>All regions</span>
        </button>
        ${ETHIOPIA_REGIONS.map((region) => `
          <button type="button" class="initiative-region-chip" data-region-name="${escapeHtml(region.value)}">
            <span class="initiative-region-flag">${escapeHtml(region.badge)}</span>
            <span>${escapeHtml(region.label)}</span>
          </button>
        `).join("")}
      </div>
    </div>
  `;
}

function renderCategoryViewSwitch(categoryId) {
  return `
    <div class="initiative-category-view-switch" data-initiative-view-switch data-category-id="${escapeHtml(categoryId)}">
      <button type="button" class="initiative-category-view-chip is-active" data-category-view="normal">Normal</button>
      <button type="button" class="initiative-category-view-chip" data-category-view="region">Region</button>
    </div>
  `;
}

function renderCategorySection(category, index) {
  const indicators = Array.isArray(category?.indicators) ? category.indicators : [];
  const scope = getCategoryScope(category);

  return `
    <article class="initiative-category${index === 0 ? " is-open" : ""}" data-initiative-category data-category-scope="${escapeHtml(scope)}">
      <button
        type="button"
        class="initiative-category-trigger"
        data-initiative-category-trigger
        aria-expanded="${index === 0 ? "true" : "false"}"
      >
        <div class="initiative-category-copy">
          <h3>${escapeHtml(category.name_ENG || category.name_AMH || "Category")}</h3>
          <p>${escapeHtml(`${indicators.length} indicator${indicators.length === 1 ? "" : "s"}`)}</p>
        </div>
        <span class="initiative-category-icon"><i class="ti ti-chevron-down"></i></span>
      </button>
      <div class="initiative-category-panel" data-initiative-category-panel ${index === 0 ? "" : "hidden"}>
        ${scope === "national" ? renderCategoryViewSwitch(category.id) : ""}
        <div class="initiative-category-region-shell" data-initiative-region-shell hidden>
          ${scope === "national" ? renderRegionSelector(category.id) : ""}
        </div>
        <div data-initiative-category-content>
          ${renderIndicatorList(indicators)}
        </div>
      </div>
    </article>
  `;
}

function renderHero(data) {
  const title = data.title_ENG || data.title_AMH || "Initiative";
  const description = data.description || "No initiative narrative is available.";
  const backgroundImage = buildMediaUrl(data.background_image || data.image);
  const iconImage = buildMediaUrl(data.image_icons);
  const categories = Array.isArray(data.categories) ? data.categories : [];
  const allIndicators = categories.flatMap((category) =>
    Array.isArray(category?.indicators) ? category.indicators : []
  );
  const regionalCount = allIndicators.filter((indicator) => getIndicatorScope(indicator) === "regional").length;

  return `
    <section class="initiative-detail-hero">
      <div class="initiative-detail-media">
        ${
          backgroundImage
            ? `<img src="${escapeHtml(backgroundImage)}" alt="${escapeHtml(title)}" loading="lazy" decoding="async">`
            : `<div class="initiative-detail-fallback" aria-hidden="true"></div>`
        }
        <div class="initiative-detail-overlay"></div>
      </div>
      <div class="initiative-detail-shell">
        <div class="initiative-detail-mark">
          <a class="initiative-detail-back" href="/dashboard/projects/initiatives/">
            <i class="ti ti-arrow-left"></i>
            <span>All initiatives</span>
          </a>
          <span class="initiative-detail-kicker">National Initiative</span>
        </div>
        <div class="initiative-detail-copy">
          <div class="initiative-detail-icon">
            ${
              iconImage
                ? `<img src="${escapeHtml(iconImage)}" alt="${escapeHtml(title)} icon" loading="lazy" decoding="async">`
                : `<i class="ti ti-bulb"></i>`
            }
          </div>
          <h1>${escapeHtml(title)}</h1>
          <p>${escapeHtml(description)}</p>
        </div>
      </div>
    </section>
    <section class="initiative-detail-grid">
      <article class="initiative-detail-card">
        <span class="initiative-detail-label">Categories</span>
        <strong>${escapeHtml(categories.length)}</strong>
      </article>
      <article class="initiative-detail-card">
        <span class="initiative-detail-label">Indicators</span>
        <strong>${escapeHtml(allIndicators.length)}</strong>
      </article>
      <article class="initiative-detail-card">
        <span class="initiative-detail-label">Regional indicators</span>
        <strong>${escapeHtml(regionalCount)}</strong>
      </article>
      <article class="initiative-detail-card">
        <span class="initiative-detail-label">Updated</span>
        <strong>${escapeHtml(formatDate(data.updated))}</strong>
      </article>
    </section>
  `;
}

function renderBody(data, scope = "all") {
  const categories = (Array.isArray(data.categories) ? data.categories : []).filter((category) => {
    const indicators = Array.isArray(category?.indicators) ? category.indicators : [];
    if (!indicators.length) {
      return false;
    }
    if (scope === "all") {
      return true;
    }
    return getCategoryScope(category) === scope;
  });

  return `
    <section class="initiative-detail-toolbar">
      <div class="initiative-scope-switch" data-initiative-scope-switch>
        <button type="button" class="initiative-scope-chip${scope === "all" ? " is-active" : ""}" data-initiative-scope="all">All</button>
        <button type="button" class="initiative-scope-chip${scope === "national" ? " is-active" : ""}" data-initiative-scope="national">National</button>
        <button type="button" class="initiative-scope-chip${scope === "federal" ? " is-active" : ""}" data-initiative-scope="federal">Federal</button>
      </div>
    </section>
    <section class="initiative-category-list">
      ${
        categories.length
          ? categories.map((category, index) => renderCategorySection(category, index)).join("")
          : '<div class="initiative-detail-state">No categories or indicators match the selected scope.</div>'
      }
    </section>
  `;
}

function bindCategoryAccordions(container) {
  container.querySelectorAll("[data-initiative-category-trigger]").forEach((trigger) => {
    trigger.addEventListener("click", () => {
      const category = trigger.closest("[data-initiative-category]");
      const panel = category?.querySelector("[data-initiative-category-panel]");
      const expanded = trigger.getAttribute("aria-expanded") === "true";
      trigger.setAttribute("aria-expanded", expanded ? "false" : "true");
      category?.classList.toggle("is-open", !expanded);
      if (panel) {
        panel.hidden = expanded;
      }
    });
  });

  container.querySelectorAll("[data-initiative-view-switch]").forEach((switcher) => {
    switcher.querySelectorAll("[data-category-view]").forEach((button) => {
      button.addEventListener("click", () => {
        const categoryId = switcher.dataset.categoryId;
        const category = switcher.closest("[data-initiative-category]");
        const content = category?.querySelector("[data-initiative-category-content]");
        const regionShell = category?.querySelector("[data-initiative-region-shell]");
        if (!categoryId || !content || !regionShell) {
          return;
        }

        const selectedView = button.dataset.categoryView || "normal";
        switcher.querySelectorAll("[data-category-view]").forEach((entry) => {
          entry.classList.toggle("is-active", entry === button);
        });

        if (selectedView === "region") {
          regionShell.hidden = false;
          content.innerHTML = '<div class="initiative-indicator-empty">Select a region to view regional indicators.</div>';
          const regionButtons = Array.from(category.querySelectorAll("[data-region-name]"));
          regionButtons.forEach((entry) => entry.classList.toggle("is-active", entry.dataset.regionName === ""));
          return;
        }

        regionShell.hidden = true;
        const originalIndicators = Array.isArray(window.__initiativeCategoryIndicators?.[categoryId])
          ? window.__initiativeCategoryIndicators[categoryId]
          : [];
        content.innerHTML = renderIndicatorList(originalIndicators);
        bindIndicatorHistory(content);
      });
    });
  });

  container.querySelectorAll("[data-initiative-region-switch]").forEach((switcher) => {
    switcher.addEventListener("click", async (event) => {
      const button = event.target.closest("[data-region-name]");
      if (!button) {
        return;
      }

      const categoryId = switcher.dataset.categoryId;
      const category = switcher.closest("[data-initiative-category]");
      const content = category?.querySelector("[data-initiative-category-content]");
      if (!categoryId || !content) {
        return;
      }

      const regionShell = category?.querySelector("[data-initiative-region-shell]");
      if (regionShell?.hidden) {
        return;
      }

      const regionName = button.dataset.regionName || "";
      switcher.querySelectorAll("[data-region-name]").forEach((entry) => {
        entry.classList.toggle("is-active", entry === button);
      });

      if (!regionName) {
        const originalIndicators = Array.isArray(window.__initiativeCategoryIndicators?.[categoryId])
          ? window.__initiativeCategoryIndicators[categoryId]
          : [];
        content.innerHTML = renderIndicatorList(originalIndicators);
        bindIndicatorHistory(content);
        return;
      }

      content.innerHTML = '<div class="initiative-indicator-empty">Loading regional indicators...</div>';

      try {
        const payload = await fetchJson(
          `/api/mobile/filter-initiative-indicator-by-region/?category_id=${encodeURIComponent(categoryId)}&name=${encodeURIComponent(regionName)}`
        );
        const indicators = Array.isArray(payload?.data) ? payload.data : [];
        content.innerHTML = renderIndicatorList(indicators);
        bindIndicatorHistory(content);
      } catch (_error) {
        content.innerHTML = '<div class="initiative-indicator-empty">Unable to load indicators for this region.</div>';
      }
    });
  });
}

function bindIndicatorHistory(container) {
  container.querySelectorAll("[data-initiative-value-card]").forEach((card) => {
    const periodTarget = card.querySelector("[data-initiative-selected-period]");
    const valueTarget = card.querySelector("[data-initiative-selected-value]");
    const items = Array.from(card.querySelectorAll("[data-initiative-history-item]"));

    items.forEach((item) => {
      item.addEventListener("click", () => {
        items.forEach((entry) => entry.classList.remove("is-active"));
        item.classList.add("is-active");
        if (periodTarget) {
          periodTarget.textContent = item.dataset.period || "Period";
        }
        if (valueTarget) {
          valueTarget.textContent = item.dataset.value || "--";
        }
      });
    });
  });
}

async function loadInitiativeDetail() {
  const page = document.querySelector("[data-initiative-detail-page]");
  if (!page) {
    return;
  }

  const initiativeId = page.dataset.initiativeId;
  const loading = page.querySelector("[data-initiative-detail-loading]");
  const content = page.querySelector("[data-initiative-detail-content]");

  try {
    const payload = await fetchJson(`/api/mobile/topic-detail/${initiativeId}/`);
    const data = payload?.data || {};
    window.__initiativeCategoryIndicators = Object.fromEntries(
      (Array.isArray(data.categories) ? data.categories : []).map((category) => [
        String(category.id),
        Array.isArray(category?.indicators) ? category.indicators : [],
      ])
    );
    let activeScope = "all";

    const render = () => {
      content.innerHTML = `
        ${renderHero(data)}
        ${renderBody(data, activeScope)}
      `;

      content.querySelectorAll("[data-initiative-scope]").forEach((button) => {
        button.addEventListener("click", () => {
          activeScope = button.dataset.initiativeScope || "all";
          render();
        });
      });

      bindCategoryAccordions(content);
      bindIndicatorHistory(content);
    };

    render();
    content.hidden = false;
    loading.hidden = true;
  } catch (_error) {
    loading.textContent = "Unable to load this initiative right now.";
  }
}

document.addEventListener("DOMContentLoaded", loadInitiativeDetail);
