const DEFAULT_OPTIONS = {
  endpoint: "/api/mobile/trending/",
  limit: 8,
  detailBase: "/dashboard/data/indicator/",
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatValue(value) {
  if (value === null || value === undefined || value === "") {
    return "--";
  }

  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return String(value);
  }

  const formatted = numeric % 1 === 0 ? numeric.toFixed(0) : numeric.toFixed(2);
  return formatted.replace(/\.00$/, "");
}

function getSeriesByLatestData(indicator) {
  const latestData = String(indicator?.latest_data || "").toLowerCase();
  if (!latestData) {
    return [];
  }

  const seriesMap = {
    annual: indicator.annual_data || [],
    yearly: indicator.annual_data || [],
    quarter: indicator.quarter_data || [],
    quarterly: indicator.quarter_data || [],
    month: indicator.month_data || [],
    monthly: indicator.month_data || [],
    week: indicator.week_data || [],
    weekly: indicator.week_data || [],
    day: indicator.day_data || [],
    daily: indicator.day_data || [],
  };

  return seriesMap[latestData] || [];
}

function getPointSortValue(point, frequency) {
  const year = Number(point?.for_datapoint || 0);
  const quarterValue = Number(String(point?.for_quarter || "").replace(/[^0-9]/g, "") || 0);
  const monthMap = {
    "መስከረም": 1,
    "ጥቅምት": 2,
    "ኅዳር": 3,
    "ህዳር": 3,
    "ታኅሣሥ": 4,
    "ታህሳስ": 4,
    "ጥር": 5,
    "የካቲት": 6,
    "መጋቢት": 7,
    "ሚያዝያ": 8,
    "ግንቦት": 9,
    "ሰኔ": 10,
    "ሐምሌ": 11,
    "ሀምሌ": 11,
    "ነሐሴ": 12,
    "ነሀሴ": 12,
  };
  const rawMonth = String(point?.for_month || "").trim();
  const monthValue = monthMap[rawMonth] || Number(rawMonth.replace(/[^0-9]/g, "") || 0);
  const weekValue = Number(point?.for_week || 0);
  const dayValue = Number(point?.for_day || 0);

  if (frequency === "quarter" || frequency === "quarterly") {
    return year * 10 + quarterValue;
  }
  if (frequency === "month" || frequency === "monthly") {
    return year * 100 + monthValue;
  }
  if (frequency === "week" || frequency === "weekly") {
    return year * 100 + weekValue;
  }
  if (frequency === "day" || frequency === "daily") {
    return year * 1000 + dayValue;
  }
  return year;
}

function getLatestPoint(indicator) {
  const series = getSeriesByLatestData(indicator);
  if (!Array.isArray(series) || !series.length) {
    return null;
  }

  const frequency = String(indicator?.latest_data || "").toLowerCase();
  return [...series].sort((left, right) => getPointSortValue(left, frequency) - getPointSortValue(right, frequency)).at(-1) || null;
}

function shuffle(items) {
  const copy = [...items];
  for (let index = copy.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(Math.random() * (index + 1));
    [copy[index], copy[swapIndex]] = [copy[swapIndex], copy[index]];
  }
  return copy;
}

function buildDetailHref(item, detailBase) {
  const indicatorId = item?.indicator?.id;
  if (!detailBase || !indicatorId) {
    return "";
  }

  return `${String(detailBase).replace(/\/?$/, "/")}${indicatorId}/`;
}

function createCard(item, detailBase) {
  const indicator = item?.indicator || {};
  const latestPoint = getLatestPoint(indicator);
  const title = indicator.title_ENG || indicator.title_AMH || "Indicator";
  const unit =
    indicator[`measurement_units_${String(indicator.latest_data || "").toLowerCase()}`] ||
    indicator.measurement_units ||
    "-";
  const value = latestPoint ? latestPoint.performance : null;
  const href = buildDetailHref(item, detailBase);
  const tagName = href ? "a" : "article";
  const hrefAttr = href ? ` href="${escapeHtml(href)}"` : "";

  return `
    <${tagName} class="hf-card"${hrefAttr}>
      <div class="hf-card-head">
        <span class="hf-card-icon">
          <i class="ti ti-chart-donut-2"></i>
        </span>
        <span class="hf-card-trend" aria-hidden="true">
          <i class="ti ti-sparkles"></i>
        </span>
      </div>
      <div class="hf-card-metric">
        <strong>${escapeHtml(formatValue(value))}</strong>
        <span>${escapeHtml(unit || "-")}</span>
      </div>
      <p>${escapeHtml(title)}</p>
    </${tagName}>
  `;
}

function renderLoading(grid) {
  grid.innerHTML = Array.from({ length: 8 }, () => '<div class="hf-card hf-card-skeleton"></div>').join("");
}

function renderEmpty(grid) {
  grid.innerHTML = '<div class="hf-card-state">No high frequency indicators available right now.</div>';
}

function renderError(grid) {
  grid.innerHTML = '<div class="hf-card-state">Unable to load high frequency indicators right now.</div>';
}

async function mountHighFrequencyIndicators(element, options = {}) {
  if (!element) {
    return null;
  }

  const settings = {
    ...DEFAULT_OPTIONS,
    ...options,
    endpoint: element.dataset.endpoint || options.endpoint || DEFAULT_OPTIONS.endpoint,
    limit: Number(element.dataset.limit || options.limit || DEFAULT_OPTIONS.limit),
    detailBase: element.dataset.detailBase || options.detailBase || DEFAULT_OPTIONS.detailBase,
  };

  const grid = element.querySelector("[data-hf-grid]");
  if (!grid) {
    return null;
  }

  renderLoading(grid);

  try {
    const response = await fetch(settings.endpoint, {
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    const rows = Array.isArray(payload?.data) ? payload.data : [];
    const items = shuffle(
      rows.filter((item) => item?.indicator)
    )
      .slice(0, settings.limit);

    if (!items.length) {
      renderEmpty(grid);
      return null;
    }

    grid.innerHTML = items.map((item) => createCard(item, settings.detailBase)).join("");
  } catch (_error) {
    renderError(grid);
  }

  return null;
}

export const HighFrequencyIndicators = {
  init(elementOrSelector, options = {}) {
    const element =
      typeof elementOrSelector === "string"
        ? document.querySelector(elementOrSelector)
        : elementOrSelector;
    return mountHighFrequencyIndicators(element, options);
  },
  initAll(selector = "[data-high-frequency]", options = {}) {
    return Promise.all(
      Array.from(document.querySelectorAll(selector)).map((element) =>
        mountHighFrequencyIndicators(element, options)
      )
    );
  },
};

window.HighFrequencyIndicators = HighFrequencyIndicators;
