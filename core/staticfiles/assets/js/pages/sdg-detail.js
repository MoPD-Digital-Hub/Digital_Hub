const GOAL_COLORS = {
  1: "#e5243b",
  2: "#dda63a",
  3: "#4c9f38",
  4: "#c5192d",
  5: "#ff3a21",
  6: "#26bde2",
  7: "#fcc30b",
  8: "#a21942",
  9: "#fd6925",
  10: "#dd1367",
  11: "#fd9d24",
  12: "#bf8b2e",
  13: "#3f7e44",
  14: "#0a97d9",
  15: "#56c02b",
  16: "#00689d",
  17: "#19486a",
};

const ETHIOPIA_REGIONS = [
  { key: "tigray", label: "Tigray", x: 52, y: 10, aliases: ["tigray"] },
  { key: "afar", label: "Afar", x: 72, y: 21, aliases: ["afar"] },
  { key: "amhara", label: "Amhara", x: 46, y: 24, aliases: ["amhara"] },
  { key: "benishangul", label: "Benishangul-Gumuz", x: 26, y: 35, aliases: ["benishangul", "gumuz", "benishangul gumuz"] },
  { key: "addis", label: "Addis Ababa", x: 45, y: 42, aliases: ["addis ababa"] },
  { key: "oromia", label: "Oromia", x: 49, y: 49, aliases: ["oromia"] },
  { key: "diredawa", label: "Dire Dawa", x: 66, y: 36, aliases: ["dire dawa"] },
  { key: "harari", label: "Harari", x: 63, y: 40, aliases: ["harari"] },
  { key: "somali", label: "Somali", x: 78, y: 51, aliases: ["somali"] },
  { key: "gambela", label: "Gambela", x: 18, y: 52, aliases: ["gambela"] },
  { key: "snnpr", label: "SNNPR", x: 36, y: 66, aliases: ["snnpr", "southern nations", "southern nations nationalities and peoples"] },
  { key: "sidama", label: "Sidama", x: 47, y: 63, aliases: ["sidama"] },
  { key: "south", label: "South Ethiopia", x: 43, y: 74, aliases: ["south ethiopia"] },
  { key: "southwest", label: "South West Ethiopia", x: 24, y: 70, aliases: ["south west ethiopia", "southwest ethiopia"] },
  { key: "central", label: "Central Ethiopia", x: 36, y: 58, aliases: ["central ethiopia"] },
];

let currentSdgChart = null;
const SERIES_PALETTE = [
  "#2f855a",
  "#0f4c75",
  "#ca8a04",
  "#b45309",
  "#6b7280",
  "#9f1239",
  "#0f766e",
  "#be123c",
  "#7c3aed",
  "#1d4ed8",
];

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function getGoalColor(goalId) {
  return GOAL_COLORS[Number(goalId)] || "var(--dh-accent)";
}

function getGoalIconUrl(goalId) {
  return `https://sdg.mopd.gov.et/icons/frameworks/sdg-icons/${encodeURIComponent(goalId)}.svg`;
}

function getTargetIconUrl(goalId, targetId) {
  return `https://sdg.mopd.gov.et/icons/frameworks/sdg-icons/targets/goal_${encodeURIComponent(goalId)}_target_${escapeTargetId(targetId)}.svg`;
}

function escapeTargetId(targetId) {
  return String(targetId || "").replaceAll(".", "_");
}

async function fetchJson(url) {
  const response = await fetch(url, {
    headers: {
      Accept: "application/json",
      "X-Requested-With": "XMLHttpRequest",
    },
    credentials: "same-origin",
  });

  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }

  return response.json();
}

function normalizeText(value) {
  return String(value ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function titleCase(value) {
  return String(value || "")
    .split(" ")
    .filter(Boolean)
    .map((chunk) => chunk.charAt(0).toUpperCase() + chunk.slice(1))
    .join(" ");
}

function getNumericValue(value) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === "string") {
    const cleaned = value.replaceAll(",", "").replace(/[^\d.-]/g, "");
    const parsed = Number(cleaned);
    return Number.isFinite(parsed) ? parsed : null;
  }

  return null;
}

function formatValue(value, unit = "") {
  const numeric = getNumericValue(value);
  if (numeric === null) {
    return value || "N/A";
  }

  const formatted = new Intl.NumberFormat("en-US", {
    maximumFractionDigits: numeric % 1 === 0 ? 0 : 2,
  }).format(numeric);

  return unit ? `${formatted} ${unit}` : formatted;
}

function hexToRgb(value) {
  const clean = String(value || "").replace("#", "");
  const normalized = clean.length === 3
    ? clean.split("").map((chunk) => `${chunk}${chunk}`).join("")
    : clean;

  if (normalized.length !== 6) {
    return { r: 93, g: 148, b: 68 };
  }

  return {
    r: Number.parseInt(normalized.slice(0, 2), 16),
    g: Number.parseInt(normalized.slice(2, 4), 16),
    b: Number.parseInt(normalized.slice(4, 6), 16),
  };
}

function rgba(value, alpha) {
  const { r, g, b } = hexToRgb(value);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function flattenDataPoints(indicator) {
  const rows = [];
  const series = Array.isArray(indicator?.data) ? indicator.data : [];

  series.forEach((entry, seriesIndex) => {
    const points = entry?.data && typeof entry.data === "object" ? entry.data : {};
    const seriesLabel =
      entry?.label ||
      entry?.name ||
      entry?.series ||
      entry?.title ||
      (series.length > 1 ? `Series ${seriesIndex + 1}` : "National series");

    Object.entries(points).forEach(([yearKey, point]) => {
      const year = Number(point?.year ?? yearKey);
      if (!Number.isFinite(year)) {
        return;
      }
      rows.push({
        year,
        unit: point?.unit || "",
        value: point?.value ?? "",
        disaggregations: Array.isArray(point?.disaggregations) ? point.disaggregations : [],
        seriesIndex,
        seriesLabel,
      });
    });
  });

  rows.sort((left, right) => right.year - left.year);
  return rows;
}

function getLatestIndicatorPoint(indicator) {
  const points = flattenDataPoints(indicator);
  return points[0] || null;
}

function groupIndicatorsByTarget(indicators) {
  const grouped = new Map();

  indicators.forEach((indicator) => {
    const targetId = indicator?.target || "other";
    if (!grouped.has(targetId)) {
      grouped.set(targetId, []);
    }
    grouped.get(targetId).push(indicator);
  });

  return grouped;
}

function resolveRegion(label) {
  const normalized = normalizeText(label);
  return ETHIOPIA_REGIONS.find((region) =>
    region.aliases.some((alias) => normalized.includes(normalizeText(alias)))
  ) || null;
}

function extractDisaggregationRows(point) {
  const rows = [];
  const entries = Array.isArray(point?.disaggregations) ? point.disaggregations : [];

  entries.forEach((item) => {
    if (item && typeof item === "object" && !Array.isArray(item)) {
      const label =
        item.label ||
        item.name ||
        item.title ||
        item.category ||
        item.dimension ||
        item.region ||
        item.area ||
        item.admin ||
        item.location;
      const numeric =
        getNumericValue(item.value) ??
        getNumericValue(item.performance) ??
        getNumericValue(item.score) ??
        getNumericValue(item.amount) ??
        getNumericValue(item.count);

      if (label && numeric !== null) {
        rows.push({
          label,
          value: numeric,
          unit: item.unit || point?.unit || "",
        });
      }
    }
  });

  return rows;
}

function getIndicatorTimeSeries(indicator) {
  const points = flattenDataPoints(indicator);
  const direct = points.filter((point) => !point.disaggregations.length && getNumericValue(point.value) !== null);
  const source = direct.length ? direct : points.filter((point) => getNumericValue(point.value) !== null);
  const grouped = new Map();

  source.forEach((point) => {
    const numeric = getNumericValue(point.value);
    if (numeric === null) {
      return;
    }

    if (!grouped.has(point.year)) {
      grouped.set(point.year, {
        total: 0,
        count: 0,
        unit: point.unit || "",
      });
    }

    const bucket = grouped.get(point.year);
    bucket.total += numeric;
    bucket.count += 1;
    if (!bucket.unit && point.unit) {
      bucket.unit = point.unit;
    }
  });

  return Array.from(grouped.entries())
    .map(([year, bucket]) => ({
      year: Number(year),
      value: bucket.count ? bucket.total / bucket.count : 0,
      unit: bucket.unit || "",
    }))
    .sort((left, right) => left.year - right.year);
}

function getIndicatorGeoSeries(indicator) {
  const points = flattenDataPoints(indicator);
  const rows = [];

  points.forEach((point) => {
    extractDisaggregationRows(point).forEach((entry) => {
      const region = resolveRegion(entry.label);
      if (!region) {
        return;
      }
      rows.push({
        year: point.year,
        key: region.key,
        label: region.label,
        x: region.x,
        y: region.y,
        value: entry.value,
        unit: entry.unit || point.unit || "",
      });
    });
  });

  if (!rows.length) {
    return null;
  }

  const latestYear = Math.max(...rows.map((row) => row.year));
  const latestRows = rows.filter((row) => row.year === latestYear);

  if (latestRows.length < 3) {
    return null;
  }

  const grouped = new Map();
  latestRows.forEach((row) => {
    if (!grouped.has(row.key)) {
      grouped.set(row.key, {
        ...row,
        total: 0,
        count: 0,
      });
    }

    const bucket = grouped.get(row.key);
    bucket.total += row.value;
    bucket.count += 1;
  });

  return {
    year: latestYear,
    unit: latestRows[0]?.unit || "",
    rows: Array.from(grouped.values())
      .map((row) => ({
        key: row.key,
        label: row.label,
        x: row.x,
        y: row.y,
        value: row.count ? row.total / row.count : 0,
        unit: row.unit || "",
      }))
      .sort((left, right) => right.value - left.value),
  };
}

function getIndicatorRows(indicator) {
  return flattenDataPoints(indicator).map((point) => ({
    year: point.year,
    value: point.value,
    unit: point.unit || "",
    seriesLabel: point.seriesLabel,
    breakdown: extractDisaggregationRows(point).map((entry) => entry.label).slice(0, 3).join(", "),
  }));
}

function getIndicatorTitle(indicator) {
  return `${indicator?.id || ""} ${indicator?.description || ""}`.trim();
}

function classifyGeography(label) {
  const normalized = normalizeText(label);
  if (normalized.includes("urban")) {
    return { key: "urban", label: "Urban" };
  }
  if (normalized.includes("rural")) {
    return { key: "rural", label: "Rural" };
  }
  if (normalized.includes("all area") || normalized.includes("all areas")) {
    return { key: "all-area", label: "All Area" };
  }
  return null;
}

function classifyPovertyType(label) {
  const normalized = normalizeText(label);
  if (normalized.includes("absolute poverty")) {
    return { key: "absolute-poverty", label: "Absolute poverty" };
  }
  if (normalized.includes("food poverty")) {
    return { key: "food-poverty", label: "Food Poverty" };
  }
  if (normalized.includes("poverty")) {
    return { key: normalized.replaceAll(" ", "-"), label: titleCase(normalized) };
  }
  return null;
}

function addSeriesPoint(store, key, label, point, color) {
  if (!store.has(key)) {
    store.set(key, {
      key,
      label,
      color,
      points: [],
    });
  }

  store.get(key).points.push({
    year: point.year,
    value: point.value,
    unit: point.unit || "",
  });
}

function sortSeries(series) {
  const normalizedNational = normalizeText("national");
  return [...series]
    .map((item) => ({
      ...item,
      points: [...item.points].sort((left, right) => left.year - right.year),
    }))
    .sort((left, right) => {
      if (normalizeText(left.label) === normalizedNational) {
        return -1;
      }
      if (normalizeText(right.label) === normalizedNational) {
        return 1;
      }
      return left.label.localeCompare(right.label);
    });
}

function buildIndicatorDimensions(indicator, goalColor) {
  const regionSeries = new Map();
  const geographySeries = new Map();
  const povertySeries = new Map();
  const points = flattenDataPoints(indicator);
  let paletteIndex = 0;

  points.forEach((point) => {
    const directValue = getNumericValue(point.value);
    if (directValue !== null) {
      addSeriesPoint(
        regionSeries,
        "national",
        "NATIONAL",
        { year: point.year, value: directValue, unit: point.unit || "" },
        goalColor
      );
    }

    extractDisaggregationRows(point).forEach((entry) => {
      const region = resolveRegion(entry.label);
      if (region) {
        addSeriesPoint(
          regionSeries,
          region.key,
          region.label,
          { year: point.year, value: entry.value, unit: entry.unit || point.unit || "" },
          SERIES_PALETTE[paletteIndex++ % SERIES_PALETTE.length]
        );
      }

      const geography = classifyGeography(entry.label);
      if (geography) {
        addSeriesPoint(
          geographySeries,
          geography.key,
          geography.label.toUpperCase(),
          { year: point.year, value: entry.value, unit: entry.unit || point.unit || "" },
          SERIES_PALETTE[paletteIndex++ % SERIES_PALETTE.length]
        );
      }

      const poverty = classifyPovertyType(entry.label);
      if (poverty) {
        addSeriesPoint(
          povertySeries,
          poverty.key,
          poverty.label,
          { year: point.year, value: entry.value, unit: entry.unit || point.unit || "" },
          SERIES_PALETTE[paletteIndex++ % SERIES_PALETTE.length]
        );
      }
    });
  });

  const dimensions = [
    {
      key: "region",
      label: "Region",
      series: sortSeries(Array.from(regionSeries.values())),
    },
    {
      key: "geography",
      label: "Geographical Location",
      series: sortSeries(Array.from(geographySeries.values())),
    },
    {
      key: "poverty",
      label: "Poverty Type",
      series: sortSeries(Array.from(povertySeries.values())),
    },
  ].filter((dimension) => {
    if (!dimension.series.length) {
      return false;
    }

    if (dimension.key === "region") {
      return dimension.series.some((series) => series.key !== "national");
    }

    return dimension.series.length > 0;
  });

  if (!dimensions.length) {
    const fallbackSeries = getIndicatorTimeSeries(indicator);
    if (fallbackSeries.length) {
      dimensions.push({
        key: "series",
        label: "Series",
        series: [
          {
            key: "national",
            label: "NATIONAL",
            color: goalColor,
            points: fallbackSeries,
          },
        ],
      });
    }
  }

  return dimensions;
}

function scoreIndicatorForExplorer(indicator, goalColor) {
  const dimensions = buildIndicatorDimensions(indicator, goalColor);
  const splitCount = dimensions.reduce((total, dimension) => total + dimension.series.length, 0);
  return {
    dimensions,
    score:
      (indicator?.hasSplitData ? 100 : 0) +
      dimensions.length * 20 +
      splitCount +
      (indicator?.hasData ? 10 : 0),
  };
}

function getPreferredIndicator(indicators, goalColor) {
  const candidates = indicators.filter((indicator) => indicator?.hasData);
  const pool = candidates.length ? candidates : indicators;

  return [...pool]
    .map((indicator) => ({
      indicator,
      ...scoreIndicatorForExplorer(indicator, goalColor),
    }))
    .sort((left, right) => right.score - left.score)[0]?.indicator || null;
}

function renderSummaryMetrics(payload) {
  const goalId = Number(payload?.goal?.id || 0);
  const indicators = Array.isArray(payload?.indicators) ? payload.indicators : [];
  const targets = Array.isArray(payload?.targets) ? payload.targets : [];
  const applicableIndicators = indicators.filter((indicator) => indicator?.applicable !== false);
  const applicableIndicatorsWithData = applicableIndicators.filter((indicator) => indicator?.hasData).length;
  const groupedIndicators = groupIndicatorsByTarget(indicators);
  const targetsWithData = targets.filter((target) =>
    (groupedIndicators.get(String(target?.id)) || []).some((indicator) => indicator?.hasData)
  ).length;
  const coverage = applicableIndicators.length
    ? ((applicableIndicatorsWithData / applicableIndicators.length) * 100).toFixed(1)
    : "0.0";

  return `
    <section class="sdg-detail-summary">
      <div class="sdg-detail-summary__head">
        <h2>Goal Snapshot</h2>
        <p>Summary for SDG ${escapeHtml(goalId)} and its current evidence coverage.</p>
      </div>
      <div class="sdg-detail-summary__metrics">
        <article class="sdg-detail-summary__metric">
          <strong>${targetsWithData}/${targets.length}</strong>
          <span>targets with data available for at least one indicator</span>
        </article>
        <article class="sdg-detail-summary__metric">
          <strong>${applicableIndicatorsWithData}/${applicableIndicators.length}</strong>
          <span>applicable indicators with data available for ${escapeHtml(payload?.countryName || "Ethiopia")}</span>
        </article>
        <article class="sdg-detail-summary__metric">
          <strong>${coverage}%</strong>
          <span>indicator coverage for Goal ${escapeHtml(goalId)} in ${escapeHtml(payload?.countryName || "Ethiopia")}</span>
        </article>
      </div>
    </section>
  `;
}

function renderTargetCards(payload) {
  const goalId = Number(payload?.goal?.id || 0);
  const goalColor = getGoalColor(goalId);
  const targetMap = new Map(
    (Array.isArray(payload?.targets) ? payload.targets : []).map((target) => [String(target?.id), target])
  );
  const groupedIndicators = groupIndicatorsByTarget(Array.isArray(payload?.indicators) ? payload.indicators : []);

  return Array.from(targetMap.entries())
    .map(([targetId, target]) => {
      const indicators = groupedIndicators.get(targetId) || [];
      return `
        <section class="sdg-target-card" style="--goal-color:${escapeHtml(goalColor)};">
          <div class="sdg-target-card__panel">
            <span class="sdg-target-card__icon">
              <img src="${escapeHtml(getTargetIconUrl(goalId, targetId))}" alt="${escapeHtml(targetId)} icon" loading="lazy" decoding="async">
            </span>
          </div>
          <div class="sdg-target-card__body">
            <div class="sdg-target-card__copy">
              <span class="sdg-target-card__eyebrow">Target ${escapeHtml(targetId)}</span>
              <h3>${escapeHtml(target?.description || "Target description is not available.")}</h3>
              <p>${indicators.length} indicator${indicators.length === 1 ? "" : "s"} mapped to this target</p>
            </div>
            <span class="sdg-target-card__count">
              <i class="ti ti-arrow-up-right"></i>
            </span>
          </div>
        </section>
      `;
    })
    .join("");
}

function renderGoalMiniNav(goals, activeGoalId, listBase) {
  return `
    <div class="sdg-goal-mini-nav">
      ${goals
        .map((goal) => {
          const goalId = Number(goal?.id || 0);
          const active = goalId === Number(activeGoalId);
          return `
            <a
              class="sdg-goal-mini-nav__item${active ? " is-active" : ""}"
              href="${escapeHtml(`${listBase}${goalId}/`)}"
              style="--goal-color:${escapeHtml(getGoalColor(goalId))};"
              aria-label="${escapeHtml(goal?.goal || `Goal ${goalId}`)}"
              title="${escapeHtml(goal?.goal || `Goal ${goalId}`)}"
            >
              <img
                src="${escapeHtml(getGoalIconUrl(goalId))}"
                alt="${escapeHtml(goal?.goal || `Goal ${goalId}`)} icon"
                loading="lazy"
                decoding="async"
              >
              <span class="sdg-goal-mini-nav__label">${escapeHtml(goal?.goal || `Goal ${goalId}`)}</span>
            </a>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderDataExplorer(payload) {
  const indicators = Array.isArray(payload?.indicators) ? payload.indicators : [];
  const goalColor = getGoalColor(payload?.goal?.id || 0);
  const activeIndicator = getPreferredIndicator(indicators, goalColor);

  if (!activeIndicator) {
    return `
      <section class="sdg-data-workspace">
        <div class="sdg-target-empty">No indicator data is available for this goal yet.</div>
      </section>
    `;
  }

  const dimensions = buildIndicatorDimensions(activeIndicator, goalColor);
  const defaultDimension = dimensions[0] || null;

  const showDimensionTabs = dimensions.length > 1;
  const showLegend = (defaultDimension?.series?.length || 0) > 1;

  return `
    <section class="sdg-data-workspace" data-sdg-data-workspace>
      <section class="sdg-data-explorer">
        <div class="sdg-data-explorer__top">
          <div class="sdg-data-explorer__title">
            <select id="sdg-indicator-select" class="sdg-data-select sdg-data-select--hero" data-sdg-indicator-select>
              ${indicators
                .map(
                  (indicator) => `
                    <option value="${escapeHtml(indicator?.id || "")}"${indicator?.id === activeIndicator?.id ? " selected" : ""}>
                      ${escapeHtml(getIndicatorTitle(indicator))}
                    </option>
                  `
                )
                .join("")}
            </select>
          </div>
          <div class="sdg-data-explorer__goalmark">
            <img src="${escapeHtml(getGoalIconUrl(payload?.goal?.id || 0))}" alt="${escapeHtml(payload?.goal?.goal || "SDG")} icon" loading="lazy" decoding="async">
          </div>
        </div>
        <div class="sdg-data-toolbar sdg-data-toolbar--official">
          ${showDimensionTabs
            ? `
              <div class="sdg-data-dimensions" data-sdg-dimension-tabs>
                ${dimensions
                  .map(
                    (dimension, index) => `
                      <button type="button" class="${index === 0 ? "is-active" : ""}" data-dimension-tab="${escapeHtml(dimension.key)}">
                        ${escapeHtml(dimension.label)}
                      </button>
                    `
                  )
                  .join("")}
              </div>
            `
            : `<div class="sdg-data-dimensions" data-sdg-dimension-tabs hidden></div>`}
          <div class="sdg-data-chart-types sdg-data-chart-types--icon" data-sdg-chart-types>
            <button type="button" class="is-active" data-chart-type="line" aria-label="Line chart"><i class="ti ti-chart-line"></i></button>
            <button type="button" data-chart-type="bar" aria-label="Bar chart"><i class="ti ti-chart-bar"></i></button>
            <button type="button"${defaultDimension?.key === "region" ? "" : " disabled"} data-chart-type="map" aria-label="Map view"><i class="ti ti-map-2"></i></button>
          </div>
        </div>
        <div class="sdg-data-layout sdg-data-layout--official">
          <section class="sdg-data-surface sdg-data-surface--chart">
            <div class="sdg-data-surface__head sdg-data-surface__head--compact">
              <div>
                <h3 data-sdg-chart-title>${escapeHtml(getIndicatorTitle(activeIndicator))}</h3>
                <p data-sdg-chart-subtitle>${escapeHtml(defaultDimension?.label || "Region")} view for ${escapeHtml(payload?.countryName || "Ethiopia")}.</p>
              </div>
            </div>
            <div class="sdg-data-y-label" data-sdg-y-label>Index</div>
            <div class="sdg-data-chart-wrap">
              <div class="sdg-data-chart" data-sdg-chart></div>
              <div class="sdg-data-map" data-sdg-map hidden></div>
            </div>
            <div class="sdg-data-legend" data-sdg-series-filters${showLegend ? "" : " hidden"}></div>
            <button type="button" class="sdg-data-clear" data-sdg-clear-series${showLegend ? "" : " hidden"}>Disable all</button>
            <div class="sdg-data-footnotes" data-sdg-meta-footer></div>
          </section>
        </div>
      </section>
    </section>
  `;
}

function renderPage(payload, listBase) {
  const goal = payload?.goal || {};
  const goalId = Number(goal?.id || 0);
  const goalColor = getGoalColor(goalId);

  return `
    <div class="sdg-detail-shell" style="--goal-color:${escapeHtml(goalColor)};">
      <section class="sdg-detail-main">
        <div class="sdg-detail-main__head">
          <div class="sdg-detail-main__head-copy">
            <h2>Sustainable Development Goal</h2>
            <p>Targets and indicators for SDG ${escapeHtml(goalId)} in ${escapeHtml(payload?.countryName || "Ethiopia")}.</p>
          </div>
          ${renderGoalMiniNav(payload?.goals || [], goalId, listBase)}
        </div>
        <section class="sdg-detail-hero" style="--goal-color:${escapeHtml(goalColor)};">
          <div class="sdg-detail-hero__layout">
            <span class="sdg-detail-hero__icon">
              <img src="${escapeHtml(getGoalIconUrl(goalId))}" alt="${escapeHtml(goal?.goal || `Goal ${goalId}`)} icon" loading="eager" decoding="async">
            </span>
            <div class="sdg-detail-hero__copy">
              <span class="sdg-detail-hero__eyebrow">Goal ${escapeHtml(goalId)}</span>
              <h1>${escapeHtml(goal?.goal || `Goal ${goalId}`)}</h1>
              <p>${escapeHtml(goal?.description || "Goal description is not available.")}</p>
            </div>
            <a class="sdg-detail-hero__back" href="${escapeHtml(listBase)}">
              <i class="ti ti-arrow-left"></i>
              <span>All goals</span>
            </a>
          </div>
        </section>
        ${renderSummaryMetrics(payload)}
        <section class="sdg-detail-switcher">
          <div class="sdg-detail-switcher__tabs" role="tablist" aria-label="Goal detail views">
            <button type="button" class="is-active" data-sdg-view-tab="overview">Overview</button>
            <button type="button" data-sdg-view-tab="data">Data</button>
          </div>
          <div class="sdg-detail-view-panel is-active" data-sdg-view-panel="overview">
            <div class="sdg-detail-section-head">
              <h2>Targets</h2>
              <p>${escapeHtml(payload?.countryName || "Ethiopia")} currenty has data on these targets for Goal ${escapeHtml(goalId)}.</p>
            </div>
            <section class="sdg-target-grid">
              ${renderTargetCards(payload)}
            </section>
          </div>
          <div class="sdg-detail-view-panel" data-sdg-view-panel="data" hidden>
            ${renderDataExplorer(payload)}
          </div>
        </section>
      </section>
    </div>
  `;
}

function renderIndicatorMetaFooter(indicator) {
  const sources = Array.isArray(indicator?.sources) ? indicator.sources : [];
  const providers = Array.isArray(indicator?.providers) ? indicator.providers : [];
  const cards = [
    {
      title: "Definition",
      value: indicator?.description || getIndicatorTitle(indicator) || "",
    },
    {
      title: "Method of computation",
      value: indicator?.type || indicator?.tier || "",
    },
    {
      title: "Source",
      value: sources.join(", ") || providers.join(", ") || "",
    },
  ].filter((card) => String(card.value || "").trim());

  if (!cards.length) {
    return "";
  }

  return `
    <div class="sdg-data-meta-grid">
      ${cards
        .map(
          (card) => `
            <article class="sdg-data-meta-card">
              <h4>${escapeHtml(card.title)}</h4>
              <p>${escapeHtml(card.value)}</p>
            </article>
          `
        )
        .join("")}
    </div>
  `;
}

function renderIndicatorTable(indicator) {
  const rows = getIndicatorRows(indicator).slice(0, 24);

  if (!rows.length) {
    return `<div class="sdg-target-empty">No records are available for this indicator.</div>`;
  }

  return `
    <table class="sdg-data-table">
      <thead>
        <tr>
          <th>Year</th>
          <th>Series</th>
          <th>Value</th>
          <th>Breakdown</th>
        </tr>
      </thead>
      <tbody>
        ${rows
          .map(
            (row) => `
              <tr>
                <td>${escapeHtml(row.year)}</td>
                <td>${escapeHtml(row.seriesLabel)}</td>
                <td>${escapeHtml(formatValue(row.value, row.unit))}</td>
                <td>${escapeHtml(row.breakdown || "National")}</td>
              </tr>
            `
          )
          .join("")}
      </tbody>
    </table>
  `;
}

function renderSeriesFilters(dimension, visibleKeys) {
  if (!dimension?.series || dimension.series.length <= 1) {
    return "";
  }

  return `
    <div class="sdg-data-legend__head">${escapeHtml(dimension.label)}</div>
    <div class="sdg-data-legend__items">
      ${dimension.series
        .map(
          (series) => `
            <button
              type="button"
              class="sdg-data-legend__item${visibleKeys.has(series.key) ? " is-active" : ""}"
              data-series-toggle="${escapeHtml(series.key)}"
            >
              <span class="sdg-data-legend__swatch" style="--series-color:${escapeHtml(series.color)};"></span>
              <span>${escapeHtml(series.label)}</span>
            </button>
          `
        )
        .join("")}
    </div>
  `;
}

function renderChartFallback(container, dimension, visibleSeries) {
  if (!visibleSeries.length) {
    container.innerHTML = `<div class="sdg-target-empty">No chartable data is available for this selection.</div>`;
    return;
  }

  const years = Array.from(new Set(visibleSeries.flatMap((item) => item.points.map((point) => point.year)))).sort((a, b) => a - b);
  const latestYear = years[years.length - 1];
  const rows = visibleSeries
    .map((series) => ({
      label: series.label,
      color: series.color,
      point: [...series.points].reverse().find((point) => point.year === latestYear) || series.points[series.points.length - 1],
    }))
    .filter((row) => row.point);
  const maxValue = Math.max(...rows.map((row) => row.point.value), 0);
  container.innerHTML = `
    <div class="sdg-data-fallback">
      ${rows
        .map((row) => {
          const width = maxValue ? `${(row.point.value / maxValue) * 100}%` : "0%";
          return `
            <div class="sdg-data-fallback__row">
              <span>${escapeHtml(row.label)}</span>
              <div class="sdg-data-fallback__bar">
                <i style="width:${escapeHtml(width)}; background:${escapeHtml(row.color)};"></i>
              </div>
              <strong>${escapeHtml(formatValue(row.point.value, row.point.unit))}</strong>
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}

function mountIndicatorChart(container, dimension, chartType, goalColor, visibleKeys) {
  if (!container) {
    return;
  }

  if (currentSdgChart) {
    currentSdgChart.destroy();
    currentSdgChart = null;
  }

  const visibleSeries = dimension.series.filter((series) => visibleKeys.has(series.key));

  if (!window.ApexCharts) {
    renderChartFallback(container, dimension, visibleSeries);
    return;
  }

  if (!visibleSeries.length) {
    container.innerHTML = `<div class="sdg-target-empty">No chartable data is available for this selection.</div>`;
    return;
  }

  const styles = getComputedStyle(document.documentElement);
  const textMuted = styles.getPropertyValue("--dh-text-muted").trim() || "#64748b";
  const border = styles.getPropertyValue("--dh-border").trim() || "#e2e8f0";
  const surface = styles.getPropertyValue("--dh-surface-bg").trim() || "#ffffff";

  container.innerHTML = "";
  const categories = Array.from(
    new Set(visibleSeries.flatMap((series) => series.points.map((point) => point.year)))
  ).sort((left, right) => left - right);
  const isBar = chartType === "bar";
  const seriesConfig = isBar
    ? visibleSeries.map((series) => {
        const latestPoint = [...series.points].sort((left, right) => right.year - left.year)[0];
        return {
          name: series.label,
          data: [latestPoint ? Number(latestPoint.value || 0) : 0],
        };
      })
    : visibleSeries.map((series) => {
        const pointMap = new Map(series.points.map((point) => [point.year, Number(point.value || 0)]));
        return {
          name: series.label,
          data: categories.map((year) => (pointMap.has(year) ? pointMap.get(year) : null)),
        };
      });

  currentSdgChart = new window.ApexCharts(container, {
    chart: {
      type: isBar ? "bar" : "line",
      height: 420,
      toolbar: { show: false },
      zoom: { enabled: false },
      foreColor: textMuted,
    },
    series: seriesConfig,
    colors: visibleSeries.map((series) => series.color || goalColor),
    stroke: {
      curve: "smooth",
      width: isBar ? 0 : visibleSeries.map((series) => (normalizeText(series.label) === "national" ? 4 : 2.2)),
    },
    plotOptions: isBar
      ? {
          bar: {
            horizontal: true,
            barHeight: "56%",
            borderRadius: 6,
          },
        }
      : {},
    dataLabels: { enabled: false },
    xaxis: {
      categories: isBar ? [categories[categories.length - 1] || "Latest"] : categories,
      labels: { rotate: -20 },
      axisBorder: { color: border },
      axisTicks: { color: border },
    },
    yaxis: {
      labels: {
        formatter(value) {
          return Number(value).toFixed(0);
        },
      },
    },
    grid: {
      borderColor: border,
      strokeDashArray: 4,
    },
    tooltip: {
      y: {
        formatter(value) {
          const unit = visibleSeries[0]?.points?.[0]?.unit || "";
          return formatValue(value, unit);
        },
      },
    },
    markers: {
      size: isBar ? 0 : visibleSeries.map((series) => (normalizeText(series.label) === "national" ? 5 : 3.5)),
      hover: { size: 6 },
      strokeColors: surface,
      strokeWidth: 2,
    },
    legend: { show: false },
  });

  currentSdgChart.render();
}

function renderGeoMap(container, geoSeries, goalColor) {
  if (!container) {
    return;
  }

  if (!geoSeries || !geoSeries.rows.length) {
    container.innerHTML = `<div class="sdg-target-empty">Regional Ethiopia data is not available for this indicator.</div>`;
    return;
  }

  const max = Math.max(...geoSeries.rows.map((row) => row.value), 0);

  container.innerHTML = `
    <div class="sdg-data-map__shell">
      <div class="sdg-data-map__canvas">
        <div class="sdg-data-map__shape"></div>
        ${geoSeries.rows
          .map((row) => {
            const strength = max ? 0.25 + (row.value / max) * 0.75 : 0.25;
            return `
              <div
                class="sdg-data-map__region"
                style="
                  --x:${escapeHtml(row.x)}%;
                  --y:${escapeHtml(row.y)}%;
                  --region-fill:${escapeHtml(rgba(goalColor, strength))};
                  --region-ring:${escapeHtml(rgba(goalColor, Math.min(strength + 0.12, 1)))};
                "
              >
                <span>${escapeHtml(row.label)}</span>
                <strong>${escapeHtml(formatValue(row.value, row.unit))}</strong>
              </div>
            `;
          })
          .join("")}
      </div>
      <div class="sdg-data-map__legend">
        <strong>Ethiopia regional view</strong>
        <span>Latest available geographic split from ${escapeHtml(geoSeries.year)}</span>
      </div>
    </div>
  `;
}

function initializeViewTabs(root, onChange) {
  const tabs = Array.from(root.querySelectorAll("[data-sdg-view-tab]"));
  const panels = Array.from(root.querySelectorAll("[data-sdg-view-panel]"));

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const view = tab.dataset.sdgViewTab;
      tabs.forEach((item) => item.classList.toggle("is-active", item === tab));
      panels.forEach((panel) => {
        const active = panel.dataset.sdgViewPanel === view;
        panel.hidden = !active;
        panel.classList.toggle("is-active", active);
      });
      if (typeof onChange === "function") {
        onChange(view);
      }
    });
  });
}

function initializeDataWorkspace(root, payload) {
  const workspace = root.querySelector("[data-sdg-data-workspace]");
  if (!workspace) {
    return;
  }

  const indicators = Array.isArray(payload?.indicators) ? payload.indicators : [];
  const select = workspace.querySelector("[data-sdg-indicator-select]");
  const chartEl = workspace.querySelector("[data-sdg-chart]");
  const mapEl = workspace.querySelector("[data-sdg-map]");
  const titleEl = workspace.querySelector("[data-sdg-chart-title]");
  const subtitleEl = workspace.querySelector("[data-sdg-chart-subtitle]");
  const metaFooterEl = workspace.querySelector("[data-sdg-meta-footer]");
  const chartTypeButtons = Array.from(workspace.querySelectorAll("[data-chart-type]"));
  const dimensionButtons = Array.from(workspace.querySelectorAll("[data-dimension-tab]"));
  const legendEl = workspace.querySelector("[data-sdg-series-filters]");
  const clearEl = workspace.querySelector("[data-sdg-clear-series]");
  const yLabelEl = workspace.querySelector("[data-sdg-y-label]");
  const goalColor = getGoalColor(payload?.goal?.id || 0);
  let activeIndicatorId = select?.value || getPreferredIndicator(indicators, goalColor)?.id || indicators[0]?.id || "";
  let activeChartType = "line";
  let activeDimensionKey = "region";
  let visibleSeriesKeys = new Set();
  let resetSeries = true;
  let lastRender = null;

  function syncChartTypeButtons(canMap) {
    chartTypeButtons.forEach((button) => {
      const isMap = button.dataset.chartType === "map";
      button.disabled = isMap && !canMap;
      button.classList.toggle("is-active", button.dataset.chartType === activeChartType);
    });
  }

  function syncDimensionButtons() {
    dimensionButtons.forEach((button) => {
      button.classList.toggle("is-active", button.dataset.dimensionTab === activeDimensionKey);
    });
  }

  function render() {
    const indicator = indicators.find((item) => String(item?.id) === String(activeIndicatorId)) || indicators[0];
    if (!indicator) {
      return;
    }

    const dimensions = buildIndicatorDimensions(indicator, goalColor);
    let dimension = dimensions.find((item) => item.key === activeDimensionKey) || dimensions[0];
    if (!dimension) {
      return;
    }
    activeDimensionKey = dimension.key;
    syncDimensionButtons();

    if (resetSeries || !dimension.series.some((series) => visibleSeriesKeys.has(series.key))) {
      visibleSeriesKeys = new Set(dimension.series.map((series) => series.key));
      resetSeries = false;
    }

    const mapDimension = dimension.key === "region"
      ? {
          year: getIndicatorGeoSeries(indicator)?.year,
          unit: getIndicatorGeoSeries(indicator)?.unit,
          rows: dimension.series
            .filter((series) => series.key !== "national" && visibleSeriesKeys.has(series.key))
            .map((series) => {
              const region = resolveRegion(series.label);
              const latest = [...series.points].sort((left, right) => right.year - left.year)[0];
              if (!region || !latest) {
                return null;
              }
              return {
                key: region.key,
                label: region.label,
                x: region.x,
                y: region.y,
                value: latest.value,
                unit: latest.unit || "",
              };
            })
            .filter(Boolean),
        }
      : null;

    if (activeChartType === "map" && (!mapDimension || !mapDimension.rows.length)) {
      activeChartType = "line";
    }

    syncChartTypeButtons(Boolean(mapDimension && mapDimension.rows.length));
    titleEl.textContent = getIndicatorTitle(indicator);
    subtitleEl.textContent =
      dimension.key === "series"
        ? `Target ${indicator?.target || "N/A"} • ${payload?.countryName || "Ethiopia"}`
        : `${dimension.label} • Target ${indicator?.target || "N/A"} • ${payload?.countryName || "Ethiopia"}`;
    yLabelEl.textContent = indicator?.type || "Index";
    const showLegend = dimension.series.length > 1;
    legendEl.hidden = !showLegend;
    clearEl.hidden = !showLegend;
    legendEl.innerHTML = showLegend ? renderSeriesFilters(dimension, visibleSeriesKeys) : "";
    metaFooterEl.innerHTML = renderIndicatorMetaFooter(indicator);

    legendEl.querySelectorAll("[data-series-toggle]").forEach((button) => {
      button.addEventListener("click", () => {
        const key = button.dataset.seriesToggle;
        if (!key) {
          return;
        }
        if (visibleSeriesKeys.has(key)) {
          visibleSeriesKeys.delete(key);
        } else {
          visibleSeriesKeys.add(key);
        }
        if (!visibleSeriesKeys.size) {
          visibleSeriesKeys = new Set([key]);
        }
        render();
      });
    });

    if (activeChartType === "map") {
      chartEl.hidden = true;
      mapEl.hidden = false;
      if (currentSdgChart) {
        currentSdgChart.destroy();
        currentSdgChart = null;
      }
      renderGeoMap(mapEl, mapDimension, goalColor);
      lastRender = render;
      return;
    }

    mapEl.hidden = true;
    chartEl.hidden = false;
    mountIndicatorChart(chartEl, dimension, activeChartType, goalColor, visibleSeriesKeys);
    lastRender = render;
  }

  select?.addEventListener("change", () => {
    activeIndicatorId = select.value;
    resetSeries = true;
    render();
  });

  dimensionButtons.forEach((button) => {
    button.addEventListener("click", () => {
      activeDimensionKey = button.dataset.dimensionTab || "region";
      resetSeries = true;
      render();
    });
  });

  chartTypeButtons.forEach((button) => {
    button.addEventListener("click", () => {
      if (button.disabled) {
        return;
      }
      activeChartType = button.dataset.chartType || "line";
      render();
    });
  });

  clearEl?.addEventListener("click", () => {
    visibleSeriesKeys = new Set();
    resetSeries = false;
    render();
  });

  render();
  return () => {
    window.requestAnimationFrame(() => {
      if (typeof lastRender === "function") {
        lastRender();
      }
    });
  };
}

async function loadSdgDetail() {
  const page = document.querySelector("[data-sdg-detail-page]");
  if (!page) {
    return;
  }

  const endpoint = page.dataset.endpoint;
  const listBase = page.dataset.listBase || "/dashboard/frameworks/sdgs/";
  const state = page.querySelector("[data-sdg-detail-state]");
  const content = page.querySelector("[data-sdg-detail-content]");

  try {
    const payload = await fetchJson(endpoint);
    content.innerHTML = renderPage(payload, listBase);
    content.hidden = false;
    const refreshDataWorkspace = initializeDataWorkspace(content, payload);
    initializeViewTabs(content, (view) => {
      if (view === "data" && typeof refreshDataWorkspace === "function") {
        refreshDataWorkspace();
      }
    });
    if (state) {
      state.hidden = true;
    }
  } catch (error) {
    if (state) {
      state.textContent = "Unable to load SDG detail right now.";
    }
    console.error(error);
  }
}

document.addEventListener("DOMContentLoaded", loadSdgDetail);
