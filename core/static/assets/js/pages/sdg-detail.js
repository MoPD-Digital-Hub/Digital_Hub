import { ETHIOPIA_ADMIN1_MAP } from "../data/ethiopia-admin1-map.js";

const SDG_CACHE_TTL_MS = 60 * 60 * 1000;
const SDG_CACHE_PREFIX = "sdg-detail-cache:";

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

function getIndicatorExportUrl(indicatorId) {
  return `https://sdg.mopd.gov.et/api/ethiopia/export/${encodeURIComponent(indicatorId)}?framework=sdg`;
}

function escapeTargetId(targetId) {
  return String(targetId || "").toLowerCase().replaceAll(".", "_");
}

async function fetchJson(url) {
  const cacheKey = `${SDG_CACHE_PREFIX}${url}`;
  try {
    const cached = window.localStorage.getItem(cacheKey);
    if (cached) {
      const parsed = JSON.parse(cached);
      if (
        parsed &&
        typeof parsed === "object" &&
        parsed.timestamp &&
        Date.now() - Number(parsed.timestamp) < SDG_CACHE_TTL_MS
      ) {
        return parsed.data;
      }
      window.localStorage.removeItem(cacheKey);
    }
  } catch (error) {
    console.warn("Unable to read SDG cache", error);
  }

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

  const data = await response.json();
  try {
    window.localStorage.setItem(
      cacheKey,
      JSON.stringify({
        timestamp: Date.now(),
        data,
      })
    );
  } catch (error) {
    console.warn("Unable to write SDG cache", error);
  }

  return data;
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

function formatMapValue(value, unit = "") {
  const cleanedUnit = normalizeText(unit) === "index" ? "" : unit;
  return formatValue(value, cleanedUnit);
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

function getIndicatorEntries(indicator) {
  const rows = [];
  const entries = Array.isArray(indicator?.data) ? indicator.data : [];

  entries.forEach((entry, entryIndex) => {
    const disaggregations = Array.isArray(entry?.disaggregations) ? entry.disaggregations : [];
    const filters = {};

    disaggregations.forEach((item) => {
      const type = String(item?.type || "").trim();
      const value = String(item?.value || "").trim();
      if (type && value) {
        filters[type] = value;
      }
    });

    const points = entry?.data && typeof entry.data === "object" ? entry.data : {};
    const seriesLabel =
      Object.entries(filters)
        .map(([, value]) => value)
        .join(" / ") ||
      entry?.label ||
      `Series ${entryIndex + 1}`;

    Object.entries(points).forEach(([yearKey, point]) => {
      const year = Number(point?.year ?? yearKey);
      const numeric = getNumericValue(point?.value);
      if (!Number.isFinite(year) || numeric === null) {
        return;
      }
      rows.push({
        year,
        value: numeric,
        unit: point?.unit || "",
        filters,
        seriesLabel,
      });
    });
  });

  return rows;
}

function getIndicatorTimeSeries(indicator) {
  const rows = getIndicatorEntries(indicator);
  const direct = rows.filter((row) => Object.keys(row.filters).length === 0);
  const source = direct.length ? direct : rows;
  const grouped = new Map();

  source.forEach((row) => {
    if (!grouped.has(row.year)) {
      grouped.set(row.year, { total: 0, count: 0, unit: row.unit || "" });
    }
    const bucket = grouped.get(row.year);
    bucket.total += row.value;
    bucket.count += 1;
    if (!bucket.unit && row.unit) {
      bucket.unit = row.unit;
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

function hasDirectIndicatorData(indicator) {
  return getIndicatorEntries(indicator).length > 0;
}

function resolveRenderableIndicator(indicator, indicators) {
  if (!indicator) {
    return null;
  }

  if (hasDirectIndicatorData(indicator)) {
    return indicator;
  }

  const children = (Array.isArray(indicators) ? indicators : []).filter(
    (candidate) => String(candidate?.parentIndicator || "") === String(indicator?.id || "")
  );

  const childWithData = children.find((candidate) => hasDirectIndicatorData(candidate));
  return childWithData || indicator;
}

function getIndicatorRows(indicator) {
  return getIndicatorEntries(indicator)
    .sort((left, right) => right.year - left.year)
    .map((row) => ({
      year: row.year,
      value: row.value,
      unit: row.unit || "",
      seriesLabel: row.seriesLabel,
      breakdown: Object.entries(row.filters)
        .map(([type, value]) => `${type}: ${value}`)
        .join(", "),
    }));
}

function getIndicatorTitle(indicator) {
  return `${indicator?.id || ""} ${indicator?.description || ""}`.trim();
}

function getIndicatorTree(indicators) {
  const items = Array.isArray(indicators) ? indicators : [];
  const byParent = new Map();
  const roots = [];

  items.forEach((indicator) => {
    const parentId = String(indicator?.parentIndicator || "");
    if (parentId) {
      if (!byParent.has(parentId)) {
        byParent.set(parentId, []);
      }
      byParent.get(parentId).push(indicator);
      return;
    }
    roots.push(indicator);
  });

  const ordered = [];
  roots.forEach((root) => {
    ordered.push({ indicator: root, level: 0 });
    (byParent.get(String(root?.id || "")) || []).forEach((child) => {
      ordered.push({ indicator: child, level: 1 });
    });
  });

  items
    .filter((indicator) => indicator?.parentIndicator && !roots.some((root) => String(root?.id || "") === String(indicator?.parentIndicator || "")))
    .forEach((indicator) => {
      ordered.push({ indicator, level: 1 });
    });

  return ordered;
}

function renderIndicatorPicker(indicators, activeIndicatorId) {
  const availableIndicators = getIndicatorsWithUsableData(indicators);
  const orderedIndicators = getIndicatorTree(availableIndicators.length ? availableIndicators : indicators);
  const activeEntry =
    orderedIndicators.find(({ indicator }) => String(indicator?.id || "") === String(activeIndicatorId)) ||
    orderedIndicators[0] ||
    null;
  const activeLabel = activeEntry ? getIndicatorTitle(activeEntry.indicator) : "Select indicator";

  return `
    <div class="sdg-indicator-picker" data-sdg-indicator-picker>
      <select id="sdg-indicator-select" class="sdg-data-select sdg-data-select--hero" data-sdg-indicator-select hidden>
        ${orderedIndicators
          .map(
            ({ indicator }) => `
              <option value="${escapeHtml(indicator?.id || "")}"${String(indicator?.id || "") === String(activeIndicatorId) ? " selected" : ""}>
                ${escapeHtml(getIndicatorTitle(indicator))}
              </option>
            `
          )
          .join("")}
      </select>
      <button type="button" class="sdg-indicator-picker__trigger" data-sdg-indicator-trigger aria-haspopup="listbox" aria-expanded="false">
        <span class="sdg-indicator-picker__trigger-label" data-sdg-indicator-label>${escapeHtml(activeLabel)}</span>
        <i class="ti ti-chevron-down"></i>
      </button>
      <div class="sdg-indicator-picker__panel" data-sdg-indicator-panel hidden>
        <div class="sdg-indicator-picker__search">
          <i class="ti ti-search"></i>
          <input type="search" placeholder="Search indicator" data-sdg-indicator-search>
        </div>
        <div class="sdg-indicator-picker__list" role="listbox" data-sdg-indicator-list>
          ${orderedIndicators
            .map(
              ({ indicator, level }) => `
                <button
                  type="button"
                  class="sdg-indicator-picker__option${String(indicator?.id || "") === String(activeIndicatorId) ? " is-active" : ""}${level > 0 ? " is-child" : ""}"
                  data-indicator-option="${escapeHtml(indicator?.id || "")}"
                  data-indicator-search-text="${escapeHtml(`${indicator?.id || ""} ${indicator?.description || ""}`.toLowerCase())}"
                  role="option"
                  aria-selected="${String(indicator?.id || "") === String(activeIndicatorId) ? "true" : "false"}"
                >
                  <span class="sdg-indicator-picker__option-main">
                    <span class="sdg-indicator-picker__option-title">${escapeHtml(getIndicatorTitle(indicator))}</span>
                  </span>
                  <span class="sdg-indicator-picker__option-code">${escapeHtml(indicator?.id || "")}</span>
                </button>
              `
            )
            .join("")}
        </div>
      </div>
    </div>
  `;
}

function normalizeDimensionType(type) {
  const raw = String(type || "").trim();
  const normalized = normalizeText(raw);
  if (normalized === "region") {
    return { key: "region", label: "Region" };
  }
  if (normalized === "geographical location") {
    return { key: "geography", label: "Geographical Location" };
  }
  if (normalized === "poverty type") {
    return { key: "poverty", label: "Poverty Type" };
  }
  return {
    key: normalized.replaceAll(" ", "-"),
    label: raw || titleCase(type),
  };
}

function getSeriesColor(index, label, goalColor) {
  return normalizeText(label) === "national"
    ? goalColor
    : SERIES_PALETTE[index % SERIES_PALETTE.length];
}

function buildIndicatorExplorerModel(indicator, goalColor, activeDimensionKey = "", selectedFilters = {}) {
  const rows = getIndicatorEntries(indicator);
  const dimensionMap = new Map();
  const dimensionOrder = [];

  rows.forEach((row) => {
    Object.entries(row.filters).forEach(([type, value]) => {
      const meta = normalizeDimensionType(type);
      if (!dimensionMap.has(meta.key)) {
        dimensionMap.set(meta.key, {
          key: meta.key,
          label: meta.label,
          rawType: type,
          values: new Set(),
        });
        dimensionOrder.push(meta.key);
      }
      dimensionMap.get(meta.key).values.add(value);
    });
  });

  const dimensions = dimensionOrder
    .map((key) => dimensionMap.get(key))
    .map((dimension) => ({
      ...dimension,
      values: Array.from(dimension.values),
    }));

  if (!dimensions.length) {
    const fallbackSeries = getIndicatorTimeSeries(indicator);
    return {
      dimensions: [],
      primaryKey: "series",
      primaryDimension: null,
      filters: {},
      series: [
        {
          key: "ethiopia",
          label: "Ethiopia",
          color: goalColor,
          points: fallbackSeries,
        },
      ],
    };
  }

  const primaryKey = dimensions.some((dimension) => dimension.key === activeDimensionKey)
    ? activeDimensionKey
    : dimensions[0].key;
  const primaryDimension = dimensions.find((dimension) => dimension.key === primaryKey) || dimensions[0];
  const filters = {};

  dimensions.forEach((dimension) => {
    if (dimension.key === primaryKey) {
      return;
    }
    const selectedValue = selectedFilters[dimension.key];
    filters[dimension.key] = dimension.values.includes(selectedValue) ? selectedValue : dimension.values[0];
  });

  const candidateRows = rows.filter((row) =>
    dimensions.every((dimension) => {
      if (dimension.key === primaryKey) {
        return true;
      }
      return row.filters[dimension.rawType] === filters[dimension.key];
    })
  );

  const seriesStore = new Map();
  candidateRows.forEach((row) => {
    const label = row.filters[primaryDimension.rawType] || "Ethiopia";
    const key = normalizeText(label).replaceAll(" ", "-") || "ethiopia";
    if (!seriesStore.has(key)) {
      seriesStore.set(key, {
        key,
        label,
        color: getSeriesColor(seriesStore.size, label, goalColor),
        points: [],
      });
    }
    seriesStore.get(key).points.push({
      year: row.year,
      value: row.value,
      unit: row.unit || "",
    });
  });

  const series = Array.from(seriesStore.values())
    .map((entry) => ({
      ...entry,
      points: entry.points.sort((left, right) => left.year - right.year),
    }))
    .sort((left, right) => {
      if (normalizeText(left.label) === "ethiopia") {
        return -1;
      }
      if (normalizeText(right.label) === "ethiopia") {
        return 1;
      }
      return left.label.localeCompare(right.label);
    });

  return {
    dimensions,
    primaryKey,
    primaryDimension,
    filters,
    series,
  };
}

function getIndicatorGeoSeriesFromSeries(seriesList, selectedYear = null) {
  const yearSet = new Set();
  const rows = seriesList
    .filter((series) => normalizeText(series.label) !== "ethiopia")
    .map((series) => {
      const region = resolveRegion(series.label);
      const points = [...series.points].sort((left, right) => left.year - right.year);
      points.forEach((point) => yearSet.add(point.year));
      const targetPoint =
        points.find((point) => Number(point.year) === Number(selectedYear)) ||
        points[points.length - 1];
      if (!region || !targetPoint) {
        return null;
      }
      return {
        key: region.key,
        label: region.label,
        value: targetPoint.value,
        unit: targetPoint.unit || "",
        year: targetPoint.year,
      };
    })
    .filter(Boolean);

  if (!rows.length) {
    return null;
  }

  const availableYears = Array.from(yearSet).sort((left, right) => left - right);
  const activeYear = availableYears.includes(Number(selectedYear))
    ? Number(selectedYear)
    : Math.max(...rows.map((row) => row.year));

  return {
    year: activeYear,
    availableYears,
    unit: rows[0]?.unit || "",
    rows: rows
      .filter((row) => Number(row.year) === Number(activeYear))
      .sort((left, right) => right.value - left.value),
  };
}

function getMapFeatureKey(label) {
  const normalized = normalizeText(label);
  if (normalized.includes("benishangul")) {
    return "benishangul gumz";
  }
  if (normalized.includes("gambella") || normalized.includes("gambela")) {
    return "gambela";
  }
  if (normalized.includes("snnpr") || normalized.includes("snnp")) {
    return "snnp";
  }
  return normalized;
}

function scoreIndicatorForExplorer(indicator, goalColor) {
  const model = buildIndicatorExplorerModel(indicator, goalColor);
  const splitCount = (model.series || []).length + model.dimensions.length;
  return {
    model,
    score:
      (indicator?.hasSplitData ? 100 : 0) +
      model.dimensions.length * 24 +
      splitCount +
      (indicator?.hasData ? 10 : 0),
  };
}

function getPreferredIndicator(indicators, goalColor) {
  const candidates = indicators.filter((indicator) => indicator?.hasData);
  const pool = candidates.length ? candidates : indicators;

  return [...pool]
    .map((indicator) => ({
      indicator: resolveRenderableIndicator(indicator, pool),
      ...scoreIndicatorForExplorer(resolveRenderableIndicator(indicator, pool), goalColor),
    }))
    .sort((left, right) => right.score - left.score)[0]?.indicator || null;
}

function getIndicatorsWithUsableData(indicators) {
  const allIndicators = Array.isArray(indicators) ? indicators : [];
  return allIndicators.filter((indicator) => {
    if (!indicator) {
      return false;
    }
    if (indicator?.hasData || indicator?.hasSplitData) {
      return true;
    }
    return allIndicators.some(
      (candidate) =>
        String(candidate?.parentIndicator || "") === String(indicator?.id || "") &&
        (candidate?.hasData || candidate?.hasSplitData)
    );
  });
}

function renderSummaryMetrics(payload) {
  const goalId = Number(payload?.goal?.id || 0);
  const indicators = Array.isArray(payload?.indicators) ? payload.indicators : [];
  const targets = Array.isArray(payload?.targets) ? payload.targets : [];
  const parentIndicators = indicators.filter((indicator) => !indicator?.parentIndicator);
  const applicableIndicators = parentIndicators.filter((indicator) => indicator?.applicable !== false);
  const applicableIndicatorsWithData = applicableIndicators.filter((indicator) => {
    if (indicator?.hasData) {
      return true;
    }

    return indicators.some(
      (candidate) =>
        String(candidate?.parentIndicator || "") === String(indicator?.id || "") &&
        candidate?.hasData
    );
  }).length;
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
  const allIndicators = Array.isArray(payload?.indicators) ? payload.indicators : [];

  return Array.from(targetMap.entries())
    .map(([targetId, target]) => {
      const indicators = groupedIndicators.get(targetId) || [];
      const parentIndicators = indicators.filter((indicator) => !indicator?.parentIndicator);
      const coveredIndicators = parentIndicators.filter((indicator) => {
        if (indicator?.hasData) {
          return true;
        }
        return allIndicators.some(
          (candidate) => String(candidate?.parentIndicator || "") === String(indicator?.id || "") && candidate?.hasData
        );
      }).length;
      const indicatorBoxes = parentIndicators
        .map(
          (indicator) => `
            <button
              type="button"
              class="sdg-target-card__kpi-box${indicator?.hasData || allIndicators.some((candidate) => String(candidate?.parentIndicator || "") === String(indicator?.id || "") && candidate?.hasData) ? " is-covered" : ""}"
              data-sdg-target-indicator="${escapeHtml(indicator?.id || "")}"
              aria-label="${escapeHtml(getIndicatorTitle(indicator) || indicator?.id || "Indicator")}"
            >
              <span class="sdg-target-card__kpi-tooltip">${escapeHtml(`INDICATOR ${indicator?.id || ""}`.trim() || "INDICATOR")}</span>
            </button>
          `
        )
        .join("");
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
              <div class="sdg-target-card__kpis">
                <div class="sdg-target-card__kpi-strip">
                  ${indicatorBoxes || '<span class="sdg-target-card__kpi-box"></span>'}
                </div>
                <p>${coveredIndicators}/${parentIndicators.length || 0} covered</p>
              </div>
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

function renderDataExplorer(payload, initialIndicatorId = "") {
  const indicators = Array.isArray(payload?.indicators) ? payload.indicators : [];
  const goalColor = getGoalColor(payload?.goal?.id || 0);
  const preferredIndicator = getPreferredIndicator(indicators, goalColor);
  const activeIndicator =
    indicators.find((indicator) => String(indicator?.id || "") === String(initialIndicatorId || "")) ||
    preferredIndicator;

  if (!activeIndicator) {
    return `
      <section class="sdg-data-workspace">
        <div class="sdg-target-empty">No indicator data is available for this goal yet.</div>
      </section>
    `;
  }

  const model = buildIndicatorExplorerModel(activeIndicator, goalColor);
  const dimensions = model.dimensions;
  const primaryDimension = model.primaryDimension;
  const defaultSeries = model.series || [];
  const showDimensionTabs = dimensions.length > 1;
  const showLegend = defaultSeries.length > 1;
  const isSingleSeries = !dimensions.length || model.primaryKey === "series";
  const canMap = dimensions.some((dimension) => dimension.key === "region");

  return `
    <section class="sdg-data-workspace" data-sdg-data-workspace>
      <section class="sdg-data-explorer">
        <div class="sdg-data-explorer__top">
          <div class="sdg-data-explorer__title">
            ${renderIndicatorPicker(indicators, activeIndicator?.id || "")}
            <div class="sdg-data-explorer__kicker">Explore data</div>
            <div class="sdg-data-explorer__country">${escapeHtml(payload?.countryName || "Ethiopia")}</div>
          </div>
        </div>
        <div class="sdg-data-toolbar sdg-data-toolbar--official">
          ${showDimensionTabs
            ? `
              <div class="sdg-data-dimensions" data-sdg-dimension-tabs>
                ${dimensions
                  .map(
                    (dimension) => `
                      <button type="button" class="${dimension.key === model.primaryKey ? "is-active" : ""}" data-dimension-tab="${escapeHtml(dimension.key)}">
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
            <button type="button"${canMap ? "" : " disabled"} data-chart-type="map" aria-label="Map view"><i class="ti ti-map-2"></i></button>
            <span class="sdg-data-chart-types__separator" aria-hidden="true"></span>
            <button type="button" data-chart-download="image" aria-label="Download image"><i class="ti ti-photo-down"></i></button>
            <a href="${escapeHtml(getIndicatorExportUrl(activeIndicator?.id || ""))}" data-chart-download-link="excel" aria-label="Download Excel"><i class="ti ti-file-spreadsheet"></i></a>
          </div>
        </div>
        <div class="sdg-data-layout sdg-data-layout--official">
          <section class="sdg-data-surface sdg-data-surface--chart">
            <div class="sdg-data-surface__head sdg-data-surface__head--compact">
              <p data-sdg-chart-subtitle>${escapeHtml(isSingleSeries ? (payload?.countryName || "Ethiopia") : ((primaryDimension?.label || "Series") + " • " + (payload?.countryName || "Ethiopia")))}</p>
            </div>
            <div class="sdg-data-y-label" data-sdg-y-label>Index</div>
            <div class="sdg-data-chart-wrap">
              <div class="sdg-data-chart" data-sdg-chart></div>
              <div class="sdg-data-map" data-sdg-map hidden></div>
            </div>
            <div class="sdg-data-legend" data-sdg-series-filters${showLegend ? "" : " hidden"}></div>
            <button type="button" class="sdg-data-clear" data-sdg-clear-series${showLegend ? "" : " hidden"}>Disable all</button>
            <div class="sdg-data-filter-groups" data-sdg-filter-groups></div>
            <div class="sdg-data-footnotes" data-sdg-meta-footer></div>
          </section>
        </div>
      </section>
    </section>
  `;
}

function renderDataExplorerPlaceholder() {
  return `
    <section class="sdg-data-workspace-placeholder" data-sdg-data-workspace-placeholder>
      <div class="sdg-page-state">Load the data tab to explore indicators, charts, and downloads.</div>
    </section>
  `;
}

function renderPage(payload, listBase, options = {}) {
  const dataOnly = Boolean(options?.dataOnly);
  const detailBase = options?.detailBase || `${listBase}${payload?.goal?.id || ""}/`;
  const dataBase = options?.dataBase || `${detailBase}data/`;
  const initialIndicatorId = options?.initialIndicatorId || "";
  const goal = payload?.goal || {};
  const goalId = Number(goal?.id || 0);
  const goalColor = getGoalColor(goalId);

  const tabsMarkup = dataOnly
    ? `
      <div class="sdg-detail-switcher__tabs" role="tablist" aria-label="Goal detail views">
        <a href="${escapeHtml(detailBase)}">Overview</a>
        <button type="button" class="is-active">Data</button>
      </div>
    `
    : `
      <div class="sdg-detail-switcher__tabs" role="tablist" aria-label="Goal detail views">
        <button type="button" class="is-active">Overview</button>
        <a href="${escapeHtml(dataBase)}">Data</a>
      </div>
    `;

  const panelMarkup = dataOnly
    ? `
      <div class="sdg-detail-view-panel is-active" data-sdg-view-panel="data">
        ${renderDataExplorer(payload, initialIndicatorId)}
      </div>
    `
    : `
      <div class="sdg-detail-view-panel is-active" data-sdg-view-panel="overview">
        <div class="sdg-detail-section-head">
          <h2>Targets</h2>
          <p>${escapeHtml(payload?.countryName || "Ethiopia")} currenty has data on these targets for Goal ${escapeHtml(goalId)}.</p>
        </div>
        <section class="sdg-target-grid">
          ${renderTargetCards(payload)}
        </section>
      </div>
    `;

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
          ${tabsMarkup}
          ${panelMarkup}
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
      value: indicator?.definition || indicator?.description || getIndicatorTitle(indicator) || "",
    },
    {
      title: "Method of computation",
      value: indicator?.methodOfComputation || indicator?.type || indicator?.tier || "",
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

function renderGroupedBarChart(container, dimension, visibleSeries, goalColor) {
  if (!visibleSeries.length) {
    container.innerHTML = `<div class="sdg-target-empty">No chartable data is available for this selection.</div>`;
    return;
  }

  const years = Array.from(
    new Set(visibleSeries.flatMap((series) => series.points.map((point) => point.year)))
  ).sort((left, right) => left - right);

  if (!years.length) {
    container.innerHTML = `<div class="sdg-target-empty">No chartable data is available for this selection.</div>`;
    return;
  }

  const nationalKeys = new Set(["national", "ethiopia"]);
  const rows = visibleSeries
    .map((series) => {
      const isPrimary = nationalKeys.has(normalizeText(series.label));
      const values = years.map((year) => {
        const point = series.points.find((item) => Number(item.year) === Number(year));
        if (!point || point.value === null || point.value === undefined) {
          return null;
        }
        return {
          value: Number(point.value),
          unit: point.unit || "",
        };
      });
      const available = values.filter(Boolean);
      if (!available.length) {
        return null;
      }
      const latest = available[available.length - 1];
      return {
        key: `${normalizeText(series.label)}-${series.label}`,
        label: series.label,
        isPrimary,
        color: goalColor,
        values,
        latest,
      };
    })
    .filter(Boolean)
    .sort((left, right) => {
      if (left.isPrimary) return -1;
      if (right.isPrimary) return 1;
      return right.latest.value - left.latest.value;
    });

  const maxValue = Math.max(
    ...rows.flatMap((row) => row.values.map((entry) => Number(entry?.value ?? 0))),
    0
  );

  const defaultActiveKey = rows.find((row) => row.isPrimary)?.key || rows[0]?.key || "";
  const chartHeight = 360;
  const plotHeight = 260;
  const axisWidth = 44;
  const topPad = 24;
  const yearGap = 24;
  const barWidth = 16;
  const barGap = 5;
  const barsWidth = rows.length * barWidth + Math.max(rows.length - 1, 0) * barGap;
  const groupWidth = Math.max(110, barsWidth);
  const chartWidth = axisWidth + years.length * groupWidth + Math.max(years.length - 1, 0) * yearGap + 18;
  const gridSteps = [0, 0.25, 0.5, 0.75, 1];
  const svgGroups = years
    .map((year, yearIndex) => {
      const groupX = axisWidth + yearIndex * (groupWidth + yearGap);
      const barsX = groupX + Math.max((groupWidth - barsWidth) / 2, 0);
      const yearY = topPad + plotHeight + 28;
      const bars = rows
        .map((row, rowIndex) => {
          const entry = row.values[yearIndex];
          const value = Number(entry?.value ?? 0);
          const height = entry && maxValue ? Math.max((value / maxValue) * plotHeight, 4) : 0;
          const x = barsX + rowIndex * (barWidth + barGap);
          const y = topPad + plotHeight - height;
          const labelY = Math.max(y - 8, 12);
          return `
            <g class="sdg-bar-svg__series${row.key === defaultActiveKey ? " is-active" : ""}" data-bar-series="${escapeHtml(row.key)}">
              <title>${escapeHtml(`${row.label}: ${entry ? formatValue(entry.value, entry.unit) : "No data"}`)}</title>
              <rect
                class="sdg-bar-svg__bar-track"
                x="${escapeHtml(x)}"
                y="${escapeHtml(topPad)}"
                width="${escapeHtml(barWidth)}"
                height="${escapeHtml(plotHeight)}"
                rx="0"
                ry="0"
              />
              <rect
                class="sdg-bar-svg__bar${entry ? "" : " is-empty"}"
                x="${escapeHtml(x)}"
                y="${escapeHtml(y)}"
                width="${escapeHtml(barWidth)}"
                height="${escapeHtml(height)}"
                rx="0"
                ry="0"
              />
              ${entry ? `<text class="sdg-bar-svg__value" x="${escapeHtml(x + barWidth / 2)}" y="${escapeHtml(labelY)}" text-anchor="middle">${escapeHtml(formatMapValue(entry.value, entry.unit))}</text>` : ""}
            </g>
          `;
        })
        .join("");
      return `
        <g class="sdg-bar-svg__year-group">
          ${bars}
          <text class="sdg-bar-svg__year" x="${escapeHtml(groupX + groupWidth / 2)}" y="${escapeHtml(yearY)}" text-anchor="middle">${escapeHtml(year)}</text>
        </g>
      `;
    })
    .join("");

  container.innerHTML = `
    <section class="sdg-bar-board">
      <div class="sdg-bar-board__header">
        <div>
          <span class="sdg-bar-board__eyebrow">Bar view</span>
          <h3>${escapeHtml(dimension?.label || "Series")} grouped by year</h3>
        </div>
        <p>All years are shown in one grouped vertical chart.</p>
      </div>
      <div class="sdg-bar-board__toggles">
        ${rows
          .map(
            (row) => `
              <button type="button" class="sdg-bar-board__toggle${row.key === defaultActiveKey ? " is-active" : ""}" data-bar-legend="${escapeHtml(row.key)}">
                <span class="sdg-bar-board__toggle-dot"></span>
                <span>${escapeHtml(row.label)}</span>
              </button>
            `
          )
          .join("")}
      </div>
      <div class="sdg-bar-stage">
        <div class="sdg-bar-svg-wrap">
          <svg class="sdg-bar-svg" viewBox="0 0 ${escapeHtml(chartWidth)} ${escapeHtml(chartHeight)}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="${escapeHtml(dimension?.label || "Series")} grouped by year">
            ${gridSteps
              .map((ratio) => {
                const y = topPad + plotHeight - ratio * plotHeight;
                const value = maxValue * ratio;
                return `
                  <g class="sdg-bar-svg__grid-row">
                    <line class="sdg-bar-svg__grid-line" x1="${escapeHtml(axisWidth)}" x2="${escapeHtml(chartWidth - 8)}" y1="${escapeHtml(y)}" y2="${escapeHtml(y)}" />
                    <text class="sdg-bar-svg__grid-label" x="${escapeHtml(axisWidth - 10)}" y="${escapeHtml(y + 4)}" text-anchor="end">${escapeHtml(formatMapValue(value))}</text>
                  </g>
                `;
              })
              .join("")}
            ${svgGroups}
          </svg>
        </div>
      </div>
    </section>
  `;

  let selectedKey = defaultActiveKey;
  const syncActive = (key) => {
    container.querySelectorAll("[data-bar-series]").forEach((item) => {
      item.classList.toggle("is-active", item.getAttribute("data-bar-series") === key);
    });
    container.querySelectorAll("[data-bar-legend]").forEach((item) => {
      item.classList.toggle("is-active", item.getAttribute("data-bar-legend") === key);
    });
  };

  container.querySelectorAll("[data-bar-series]").forEach((item) => {
    const key = item.getAttribute("data-bar-series");
    if (!key) return;
    item.addEventListener("mouseenter", () => syncActive(key));
    item.addEventListener("mouseleave", () => syncActive(selectedKey));
  });

  container.querySelectorAll("[data-bar-legend]").forEach((item) => {
    const key = item.getAttribute("data-bar-legend");
    if (!key) return;
    item.addEventListener("mouseenter", () => syncActive(key));
    item.addEventListener("mouseleave", () => syncActive(selectedKey));
    item.addEventListener("click", () => {
      selectedKey = key;
      syncActive(selectedKey);
    });
  });
}

function cloneSvgWithInlineStyles(svgElement) {
  const clone = svgElement.cloneNode(true);
  const sourceNodes = [svgElement, ...svgElement.querySelectorAll("*")];
  const cloneNodes = [clone, ...clone.querySelectorAll("*")];
  const styleProps = [
    "fill",
    "stroke",
    "stroke-width",
    "stroke-dasharray",
    "stroke-linecap",
    "stroke-linejoin",
    "opacity",
    "filter",
    "font-family",
    "font-size",
    "font-weight",
    "letter-spacing",
    "color",
  ];

  sourceNodes.forEach((node, index) => {
    const cloneNode = cloneNodes[index];
    if (!cloneNode) return;
    const computed = window.getComputedStyle(node);
    const inlineStyle = styleProps
      .map((prop) => `${prop}:${computed.getPropertyValue(prop)};`)
      .join("");
    cloneNode.setAttribute("style", `${cloneNode.getAttribute("style") || ""};${inlineStyle}`);
  });

  const viewBox = svgElement.viewBox?.baseVal;
  const width = Number(svgElement.getAttribute("width")) || viewBox?.width || svgElement.clientWidth || 1200;
  const height = Number(svgElement.getAttribute("height")) || viewBox?.height || svgElement.clientHeight || 360;
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  clone.setAttribute("xmlns:xlink", "http://www.w3.org/1999/xlink");
  clone.setAttribute("width", width);
  clone.setAttribute("height", height);
  if (!clone.getAttribute("viewBox") && viewBox) {
    clone.setAttribute("viewBox", `${viewBox.x} ${viewBox.y} ${viewBox.width} ${viewBox.height}`);
  }
  return { clone, width, height };
}

function downloadSvgMarkupAsPng(source, width, height, filename) {
  const blob = new Blob([source], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const image = new Image();

  image.onload = () => {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) {
      URL.revokeObjectURL(url);
      return;
    }
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, width, height);
    context.drawImage(image, 0, 0, width, height);
    const pngUrl = canvas.toDataURL("image/png");
    const link = document.createElement("a");
    link.href = pngUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  image.onerror = () => {
    URL.revokeObjectURL(url);
  };

  image.src = url;
}

function downloadSvgElement(svgElement, filename) {
  if (!svgElement) {
    return;
  }
  const { clone, width, height } = cloneSvgWithInlineStyles(svgElement);
  const serializer = new XMLSerializer();
  const source = serializer.serializeToString(clone);
  downloadSvgMarkupAsPng(source, width, height, filename);
}

function exportMapExplorerAsPng(mapContainer, filename) {
  const explorer = mapContainer?.querySelector(".sdg-region-explorer");
  const mapSvg = mapContainer?.querySelector(".sdg-region-explorer__svg");
  if (!explorer || !mapSvg) {
    return;
  }

  const serializer = new XMLSerializer();
  const { clone } = cloneSvgWithInlineStyles(mapSvg);
  const mapMarkup = serializer.serializeToString(clone);
  const rows = Array.from(explorer.querySelectorAll(".sdg-region-explorer__row")).map((row) => {
    const label = row.querySelector(".sdg-region-explorer__label")?.textContent?.trim() || "";
    const value = row.querySelector("strong")?.textContent?.trim() || "";
    const bar = row.querySelector(".sdg-region-explorer__bar i");
    const width = bar ? Number.parseFloat(bar.style.width || "0") : 0;
    const background = bar?.style.background || "#d1d5db";
    const isEmpty = row.classList.contains("is-empty");
    return { label, value, width, background, isEmpty };
  });
  const selectedYear = explorer.querySelector("[data-sdg-map-year]")?.value || "";
  const svgWidth = 1400;
  const svgHeight = 860;
  const mapBox = { x: 40, y: 80, width: 700, height: 560 };
  const rankX = 860;
  const rankTop = 110;
  const rowHeight = 42;
  const maxBarWidth = 360;
  const title = selectedYear ? `Year ${selectedYear}` : "Regional values";

  const exportSvg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="${svgWidth}" height="${svgHeight}" viewBox="0 0 ${svgWidth} ${svgHeight}">
      <rect width="${svgWidth}" height="${svgHeight}" fill="#ffffff"/>
      <text x="${rankX}" y="58" fill="#111827" font-family="Arial, sans-serif" font-size="28" font-weight="800">${escapeHtml(title)}</text>
      <g transform="translate(${mapBox.x}, ${mapBox.y})">
        <rect width="${mapBox.width}" height="${mapBox.height}" fill="#ffffff"/>
        <svg x="0" y="0" width="${mapBox.width}" height="${mapBox.height}" viewBox="${clone.getAttribute("viewBox") || "0 0 100 100"}" preserveAspectRatio="xMidYMid meet">
          ${clone.innerHTML}
        </svg>
      </g>
      <g transform="translate(${rankX}, ${rankTop})">
        ${rows
          .map((row, index) => {
            const y = index * rowHeight;
            const fill = row.isEmpty ? "#e5e7eb" : row.background;
            const barWidth = row.isEmpty ? 0 : (maxBarWidth * row.width) / 100;
            return `
              <text x="0" y="${y + 24}" fill="#374151" font-family="Arial, sans-serif" font-size="17" font-weight="700">${escapeHtml(row.label)}</text>
              <rect x="170" y="${y + 8}" width="${maxBarWidth}" height="18" fill="#f3f4f6"/>
              <rect x="170" y="${y + 8}" width="${barWidth}" height="18" fill="${escapeHtml(fill)}"/>
              <text x="${170 + maxBarWidth + 18}" y="${y + 24}" fill="#111827" font-family="Arial, sans-serif" font-size="17" font-weight="800">${escapeHtml(row.value)}</text>
            `;
          })
          .join("")}
      </g>
    </svg>
  `;

  downloadSvgMarkupAsPng(exportSvg, svgWidth, svgHeight, filename);
}

function renderLineChart(container, dimension, visibleSeries, goalColor) {
  if (!visibleSeries.length) {
    container.innerHTML = `<div class="sdg-target-empty">No chartable data is available for this selection.</div>`;
    return;
  }

  const nationalKeys = new Set(["national", "ethiopia"]);
  const rows = visibleSeries
    .map((series) => {
      const points = [...series.points]
        .map((point) => ({ year: Number(point.year), value: Number(point.value), unit: point.unit || "" }))
        .filter((point) => Number.isFinite(point.value))
        .sort((left, right) => left.year - right.year);
      if (!points.length) {
        return null;
      }
      const isPrimary = nationalKeys.has(normalizeText(series.label));
      const latest = points[points.length - 1];
      return {
        key: `${normalizeText(series.label)}-${series.label}`,
        label: series.label,
        isPrimary,
        points,
        latest,
      };
    })
    .filter(Boolean)
    .sort((left, right) => {
      if (left.isPrimary) return -1;
      if (right.isPrimary) return 1;
      return right.latest.value - left.latest.value;
    });

  if (!rows.length) {
    container.innerHTML = `<div class="sdg-target-empty">No chartable data is available for this selection.</div>`;
    return;
  }

  const years = Array.from(new Set(rows.flatMap((row) => row.points.map((point) => point.year)))).sort((a, b) => a - b);
  const values = rows.flatMap((row) => row.points.map((point) => point.value));
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const range = maxValue - minValue || 1;
  const defaultActiveKey = rows.find((row) => row.isPrimary)?.key || rows[0]?.key || "";
  const chartHeight = 360;
  const plotHeight = 250;
  const axisWidth = 44;
  const topPad = 24;
  const lineWidth = Math.max(1120, years.length * 96);
  const plotWidth = lineWidth - axisWidth - 18;
  const gridSteps = [0, 0.25, 0.5, 0.75, 1];
  const yearIndex = new Map(years.map((year, index) => [year, index]));
  const xForYear = (year) => {
    const index = yearIndex.get(year) ?? 0;
    if (years.length === 1) {
      return axisWidth + plotWidth / 2;
    }
    return axisWidth + (plotWidth * index) / (years.length - 1);
  };
  const yForValue = (value) => topPad + plotHeight - ((value - minValue) / range) * plotHeight;
  const linePaths = rows
    .map((row) => {
      const path = row.points
        .map((point, index) => `${index === 0 ? "M" : "L"} ${xForYear(point.year)} ${yForValue(point.value)}`)
        .join(" ");
      const dots = row.points
        .map((point) => `
          <circle class="sdg-line-svg__dot" cx="${escapeHtml(xForYear(point.year))}" cy="${escapeHtml(yForValue(point.value))}" r="4"></circle>
        `)
        .join("");
      return `
        <g class="sdg-line-svg__series${row.key === defaultActiveKey ? " is-active" : ""}" data-line-series="${escapeHtml(row.key)}">
          <path class="sdg-line-svg__path" d="${escapeHtml(path)}"></path>
          ${dots}
        </g>
      `;
    })
    .join("");

  container.innerHTML = `
    <section class="sdg-line-board">
      <div class="sdg-line-board__header">
        <div>
          <span class="sdg-line-board__eyebrow">Line view</span>
          <h3>${escapeHtml(dimension?.label || "Series")} trend chart</h3>
        </div>
        <p>All visible series are shown together in one line chart.</p>
      </div>
      <div class="sdg-line-board__toggles">
        ${rows
          .map(
            (row) => `
              <button type="button" class="sdg-line-board__toggle${row.key === defaultActiveKey ? " is-active" : ""}" data-line-legend="${escapeHtml(row.key)}">
                <span class="sdg-line-board__toggle-dot"></span>
                <span>${escapeHtml(row.label)}</span>
              </button>
            `
          )
          .join("")}
      </div>
      <div class="sdg-line-stage">
        <div class="sdg-line-svg-wrap">
          <svg class="sdg-line-svg" viewBox="0 0 ${escapeHtml(lineWidth)} ${escapeHtml(chartHeight)}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="${escapeHtml(dimension?.label || "Series")} trend chart">
            ${gridSteps
              .map((ratio) => {
                const y = topPad + plotHeight - ratio * plotHeight;
                const value = minValue + range * ratio;
                return `
                  <g class="sdg-line-svg__grid-row">
                    <line class="sdg-line-svg__grid-line" x1="${escapeHtml(axisWidth)}" x2="${escapeHtml(lineWidth - 8)}" y1="${escapeHtml(y)}" y2="${escapeHtml(y)}" />
                    <text class="sdg-line-svg__grid-label" x="${escapeHtml(axisWidth - 10)}" y="${escapeHtml(y + 4)}" text-anchor="end">${escapeHtml(formatMapValue(value))}</text>
                  </g>
                `;
              })
              .join("")}
            ${years
              .map((year) => `
                <text class="sdg-line-svg__year" x="${escapeHtml(xForYear(year))}" y="${escapeHtml(topPad + plotHeight + 28)}" text-anchor="middle">${escapeHtml(year)}</text>
              `)
              .join("")}
            ${linePaths}
          </svg>
        </div>
      </div>
    </section>
  `;

  let selectedKey = defaultActiveKey;
  const syncActive = (key) => {
    container.querySelectorAll("[data-line-series]").forEach((item) => {
      item.classList.toggle("is-active", item.getAttribute("data-line-series") === key);
    });
    container.querySelectorAll("[data-line-legend]").forEach((item) => {
      item.classList.toggle("is-active", item.getAttribute("data-line-legend") === key);
    });
  };

  container.querySelectorAll("[data-line-series]").forEach((item) => {
    const key = item.getAttribute("data-line-series");
    if (!key) return;
    item.addEventListener("mouseenter", () => syncActive(key));
    item.addEventListener("mouseleave", () => syncActive(selectedKey));
  });

  container.querySelectorAll("[data-line-legend]").forEach((item) => {
    const key = item.getAttribute("data-line-legend");
    if (!key) return;
    item.addEventListener("mouseenter", () => syncActive(key));
    item.addEventListener("mouseleave", () => syncActive(selectedKey));
    item.addEventListener("click", () => {
      selectedKey = key;
      syncActive(selectedKey);
    });
  });
}

function mountIndicatorChart(container, dimension, chartType, goalColor, visibleKeys) {
  if (!container) {
    return;
  }

  const dimensionSeries = Array.isArray(dimension?.series) ? dimension.series : [];
  const visibleSeries = dimensionSeries.filter((series) => visibleKeys.has(series.key));

  if (chartType === "bar") {
    container.innerHTML = "";
    renderGroupedBarChart(container, dimension, visibleSeries, goalColor);
    return;
  }

  if (!visibleSeries.length) {
    container.innerHTML = `<div class="sdg-target-empty">No chartable data is available for this selection.</div>`;
    return;
  }
  container.innerHTML = "";
  renderLineChart(container, dimension, visibleSeries, goalColor);
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
  const minValue = Math.min(...geoSeries.rows.map((row) => row.value), 0);
  const rowsByKey = new Map(
    geoSeries.rows.map((row) => [getMapFeatureKey(row.label), row])
  );
  const completeRows = ETHIOPIA_ADMIN1_MAP.features
    .map((feature) => {
      const row = rowsByKey.get(feature.key);
      return {
        key: feature.key,
        label: feature.name,
        value: row?.value ?? null,
        unit: row?.unit || geoSeries.unit || "",
        hasData: Boolean(row),
      };
    })
    .sort((left, right) => {
      if (left.hasData && right.hasData) {
        return right.value - left.value;
      }
      if (left.hasData) {
        return -1;
      }
      if (right.hasData) {
        return 1;
      }
      return left.label.localeCompare(right.label);
    });
  const [minX, minY, width, height] = ETHIOPIA_ADMIN1_MAP.viewBox;
  const colorForValue = (value) => {
    if (!max || value === null || value === undefined) {
      return "color-mix(in srgb, var(--dh-border) 22%, var(--dh-surface-soft))";
    }
    const ratio = max === minValue ? 1 : (value - minValue) / (max - minValue);
    return rgba(goalColor, 0.16 + ratio * 0.84);
  };

  container.innerHTML = `
    <section class="sdg-region-explorer">
      <div class="sdg-region-explorer__body">
        <figure class="sdg-region-explorer__figure">
          <div class="sdg-region-explorer__canvas">
            <svg class="sdg-region-explorer__svg" viewBox="${escapeHtml(`${minX} ${minY} ${width} ${height}`)}" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
              ${ETHIOPIA_ADMIN1_MAP.features
                .map((feature) => {
                  const row = rowsByKey.get(feature.key);
                  const fill = row
                    ? colorForValue(row.value)
                    : "color-mix(in srgb, var(--dh-border) 18%, var(--dh-surface-soft))";
                  const stroke = row
                    ? rgba(goalColor, 0.28)
                    : "color-mix(in srgb, var(--dh-border) 74%, transparent)";
                  const label = row
                    ? `${feature.name}: ${formatMapValue(row.value, row.unit)}`
                    : `${feature.name}: no data`;
                  return `
                    <path
                      class="sdg-region-explorer__region${row ? " has-data" : ""}"
                      data-region-key="${escapeHtml(feature.key)}"
                      d="${escapeHtml(feature.path)}"
                      fill="${escapeHtml(fill)}"
                      stroke="${escapeHtml(stroke)}"
                    >
                      <title>${escapeHtml(label)}</title>
                    </path>
                  `;
                })
                .join("")}
            </svg>
          </div>
        </figure>
        <aside class="sdg-region-explorer__aside">
          <div class="sdg-region-explorer__aside-head">
            <div class="sdg-region-explorer__year">
              <select data-sdg-map-year>
                ${geoSeries.availableYears
                  .map(
                    (year) => `
                      <option value="${escapeHtml(year)}"${Number(year) === Number(geoSeries.year) ? " selected" : ""}>${escapeHtml(year)}</option>
                    `
                  )
                  .join("")}
              </select>
            </div>
          </div>
          <div class="sdg-region-explorer__ranking">
            ${completeRows
              .map((row) => {
                const widthPct = row.hasData && max ? (row.value / max) * 100 : 0;
                return `
                  <div class="sdg-region-explorer__row${row.hasData ? "" : " is-empty"}" data-region-row="${escapeHtml(row.key)}">
                    <span class="sdg-region-explorer__label">${escapeHtml(row.label)}</span>
                    <div class="sdg-region-explorer__bar">
                      <i style="width:${escapeHtml(widthPct.toFixed(2))}%; background:${escapeHtml(colorForValue(row.value))};"></i>
                    </div>
                    <strong>${escapeHtml(row.hasData ? formatMapValue(row.value, row.unit) : "No data")}</strong>
                  </div>
                `;
              })
              .join("")}
          </div>
        </aside>
      </div>
    </section>
  `;

  const explorer = container.querySelector(".sdg-region-explorer");
  const regionPaths = Array.from(container.querySelectorAll("[data-region-key]"));
  const regionRows = Array.from(container.querySelectorAll("[data-region-row]"));
  const syncHover = (key, active) => {
    explorer?.classList.toggle("has-region-hover", active);
    container
      .querySelector(`[data-region-key="${CSS.escape(key)}"]`)
      ?.classList.toggle("is-hovered", active);
    container
      .querySelector(`[data-region-row="${CSS.escape(key)}"]`)
      ?.classList.toggle("is-hovered", active);
  };

  regionPaths.forEach((path) => {
    const key = path.getAttribute("data-region-key");
    if (!key) {
      return;
    }
    path.addEventListener("mouseenter", () => syncHover(key, true));
    path.addEventListener("mouseleave", () => syncHover(key, false));
  });

  regionRows.forEach((row) => {
    const key = row.getAttribute("data-region-row");
    if (!key) {
      return;
    }
    row.addEventListener("mouseenter", () => syncHover(key, true));
    row.addEventListener("mouseleave", () => syncHover(key, false));
  });
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

function initializeTargetIndicatorLinks(root, options = {}) {
  const dataPageUrl = options?.dataPageUrl || "";
  root.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-sdg-target-indicator]");
    if (!trigger) {
      return;
    }

    const indicatorId = trigger.getAttribute("data-sdg-target-indicator");
    if (!indicatorId) {
      return;
    }

    if (dataPageUrl) {
      window.location.href = `${dataPageUrl}?indicator=${encodeURIComponent(indicatorId)}`;
      return;
    }

    const dataTab = root.querySelector('[data-sdg-view-tab="data"]');
    if (typeof options?.ensureDataWorkspace === "function") {
      options.ensureDataWorkspace();
    }
    const select = root.querySelector("[data-sdg-indicator-select]");
    if (!dataTab || !select) {
      return;
    }

    if (String(select.value) !== String(indicatorId)) {
      select.value = indicatorId;
      select.dispatchEvent(new Event("change", { bubbles: true }));
    }

    dataTab.click();
  });
}

function initializeIndicatorPicker(workspace) {
  const picker = workspace.querySelector("[data-sdg-indicator-picker]");
  const select = workspace.querySelector("[data-sdg-indicator-select]");
  if (!picker || !select) {
    return;
  }

  const trigger = picker.querySelector("[data-sdg-indicator-trigger]");
  const panel = picker.querySelector("[data-sdg-indicator-panel]");
  const searchInput = picker.querySelector("[data-sdg-indicator-search]");
  const label = picker.querySelector("[data-sdg-indicator-label]");
  const options = Array.from(picker.querySelectorAll("[data-indicator-option]"));

  function syncLabel() {
    const selectedOption = select.options[select.selectedIndex];
    if (label) {
      label.textContent = selectedOption?.textContent?.trim() || "Select indicator";
    }
    options.forEach((option) => {
      const active = String(option.getAttribute("data-indicator-option") || "") === String(select.value || "");
      option.classList.toggle("is-active", active);
      option.setAttribute("aria-selected", active ? "true" : "false");
    });
  }

  function closePanel() {
    if (!panel || !trigger) {
      return;
    }
    panel.hidden = true;
    trigger.setAttribute("aria-expanded", "false");
  }

  function openPanel() {
    if (!panel || !trigger) {
      return;
    }
    panel.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
    if (searchInput) {
      searchInput.value = "";
      options.forEach((option) => {
        option.hidden = false;
      });
      window.requestAnimationFrame(() => searchInput.focus());
    }
  }

  trigger?.addEventListener("click", () => {
    if (panel?.hidden) {
      openPanel();
      return;
    }
    closePanel();
  });

  searchInput?.addEventListener("input", () => {
    const query = String(searchInput.value || "").trim().toLowerCase();
    options.forEach((option) => {
      const haystack = String(option.getAttribute("data-indicator-search-text") || "");
      option.hidden = query ? !haystack.includes(query) : false;
    });
  });

  options.forEach((option) => {
    option.addEventListener("click", () => {
      const indicatorId = option.getAttribute("data-indicator-option");
      if (!indicatorId) {
        return;
      }
      if (String(select.value) !== String(indicatorId)) {
        select.value = indicatorId;
        select.dispatchEvent(new Event("change", { bubbles: true }));
      } else {
        syncLabel();
      }
      closePanel();
    });
  });

  document.addEventListener("click", (event) => {
    if (!picker.contains(event.target)) {
      closePanel();
    }
  });

  select.addEventListener("change", syncLabel);
  syncLabel();
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
  const subtitleEl = workspace.querySelector("[data-sdg-chart-subtitle]");
  const metaFooterEl = workspace.querySelector("[data-sdg-meta-footer]");
  const chartTypeButtons = Array.from(workspace.querySelectorAll("[data-chart-type]"));
  const imageDownloadButton = workspace.querySelector("[data-chart-download='image']");
  const excelDownloadLink = workspace.querySelector("[data-chart-download-link='excel']");
  const dimensionTabsEl = workspace.querySelector("[data-sdg-dimension-tabs]");
  const legendEl = workspace.querySelector("[data-sdg-series-filters]");
  const clearEl = workspace.querySelector("[data-sdg-clear-series]");
  const yLabelEl = workspace.querySelector("[data-sdg-y-label]");
  const filterGroupsEl = workspace.querySelector("[data-sdg-filter-groups]");
  const goalColor = getGoalColor(payload?.goal?.id || 0);
  initializeIndicatorPicker(workspace);
  let activeIndicatorId = select?.value || getPreferredIndicator(indicators, goalColor)?.id || indicators[0]?.id || "";
  let activeChartType = "line";
  let activeDimensionKey = "";
  let activeFilters = {};
  let visibleSeriesKeys = new Set();
  let activeMapYear = null;
  let resetSeries = true;
  let lastRender = null;

  function syncChartTypeButtons(canMap) {
    chartTypeButtons.forEach((button) => {
      const isMap = button.dataset.chartType === "map";
      button.disabled = isMap && !canMap;
      button.classList.toggle("is-active", button.dataset.chartType === activeChartType);
    });
  }

  function render() {
    const selectedIndicator = indicators.find((item) => String(item?.id) === String(activeIndicatorId)) || indicators[0];
    const indicator = resolveRenderableIndicator(selectedIndicator, indicators);
    if (!indicator) {
      return;
    }
    if (excelDownloadLink) {
      excelDownloadLink.href = getIndicatorExportUrl(indicator.id || selectedIndicator?.id || "");
      excelDownloadLink.setAttribute("download", "");
    }

    let model = buildIndicatorExplorerModel(indicator, goalColor, activeDimensionKey, activeFilters);
    const hasRegionDimension = model.dimensions.some((item) => item.key === "region");
    if (activeChartType === "map" && hasRegionDimension && model.primaryKey !== "region") {
      model = buildIndicatorExplorerModel(indicator, goalColor, "region", activeFilters);
    }

    const dimensions = model.dimensions;
    activeDimensionKey = model.primaryKey;
    const dimension = model.primaryDimension;
    const availableSeries = model.series || [];
    activeFilters = { ...model.filters };

    if (dimensionTabsEl) {
      if (dimensions.length > 1) {
        dimensionTabsEl.hidden = false;
        dimensionTabsEl.innerHTML = dimensions
          .map(
            (item) => `
              <button type="button" class="${item.key === activeDimensionKey ? "is-active" : ""}" data-dimension-tab="${escapeHtml(item.key)}">
                ${escapeHtml(item.label)}
              </button>
            `
          )
          .join("");
      } else {
        dimensionTabsEl.hidden = true;
        dimensionTabsEl.innerHTML = "";
      }
    }

    if (resetSeries || !availableSeries.some((series) => visibleSeriesKeys.has(series.key))) {
      visibleSeriesKeys = new Set(availableSeries.map((series) => series.key));
      resetSeries = false;
    }

    const mapDimension = activeDimensionKey === "region"
      ? getIndicatorGeoSeriesFromSeries(
          availableSeries.filter((series) => visibleSeriesKeys.has(series.key)),
          activeMapYear
        )
      : null;

    if (activeChartType === "map" && (!mapDimension || !mapDimension.rows.length)) {
      activeChartType = "line";
    }

    syncChartTypeButtons(hasRegionDimension);
    workspace.classList.toggle("is-map-active", activeChartType === "map");
    if (select && String(select.value) !== String(selectedIndicator?.id || "")) {
      select.value = selectedIndicator?.id || "";
    }
    subtitleEl.textContent =
      activeDimensionKey === "series"
        ? `${payload?.countryName || "Ethiopia"}`
        : `${dimension?.label || "Series"} • ${payload?.countryName || "Ethiopia"}`;
    yLabelEl.textContent = getIndicatorEntries(indicator)[0]?.unit || indicator?.type || "Index";
    const currentDimension = {
      label: dimension?.label || "Series",
      series: availableSeries,
    };
    const showLegend = availableSeries.length > 1;
    legendEl.hidden = !showLegend;
    clearEl.hidden = !showLegend;
    legendEl.innerHTML = showLegend ? renderSeriesFilters(currentDimension, visibleSeriesKeys) : "";
    metaFooterEl.innerHTML = renderIndicatorMetaFooter(indicator);
    filterGroupsEl.innerHTML = dimensions
      .filter((item) => item.key !== activeDimensionKey)
      .filter((item) => item.values.length > 1)
      .map(
        (item) => `
          <div class="sdg-data-filter-group">
            <div class="sdg-data-filter-group__title">${escapeHtml(item.label)}</div>
            <div class="sdg-data-filter-group__options">
              ${item.values
                .map(
                  (value) => `
                    <button
                      type="button"
                      class="sdg-data-filter-option${activeFilters[item.key] === value ? " is-active" : ""}"
                      data-filter-type="${escapeHtml(item.key)}"
                      data-filter-value="${escapeHtml(value)}"
                    >
                      ${escapeHtml(value)}
                    </button>
                  `
                )
                .join("")}
            </div>
          </div>
        `
      )
      .join("");

    dimensionTabsEl?.querySelectorAll("[data-dimension-tab]").forEach((button) => {
      button.onclick = () => {
        const nextKey = button.dataset.dimensionTab || model.primaryKey;
        if (nextKey === activeDimensionKey) {
          return;
        }
        activeDimensionKey = nextKey;
        resetSeries = true;
        render();
      };
    });

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

    filterGroupsEl.querySelectorAll("[data-filter-type]").forEach((button) => {
      button.addEventListener("click", () => {
        const type = button.dataset.filterType;
        const value = button.dataset.filterValue;
        if (!type || !value) {
          return;
        }
        activeFilters[type] = value;
        resetSeries = true;
        const refreshedModel = buildIndicatorExplorerModel(indicator, goalColor, activeDimensionKey, activeFilters);
        const refreshedSeries = refreshedModel.series || [];
        visibleSeriesKeys = new Set(refreshedSeries.map((series) => series.key));
        render();
      });
    });

    if (activeChartType === "map") {
      chartEl.hidden = true;
      mapEl.hidden = false;
      renderGeoMap(mapEl, mapDimension, goalColor);
      const yearSelect = mapEl.querySelector("[data-sdg-map-year]");
      if (yearSelect) {
        yearSelect.addEventListener("change", () => {
          activeMapYear = Number(yearSelect.value || "") || null;
          render();
        });
      }
      lastRender = render;
      return;
    }

    mapEl.hidden = true;
    chartEl.hidden = false;
    mountIndicatorChart(chartEl, currentDimension, activeChartType, goalColor, visibleSeriesKeys);
    lastRender = render;
  }

  select?.addEventListener("change", () => {
    activeIndicatorId = select.value;
    activeDimensionKey = "";
    activeFilters = {};
    activeMapYear = null;
    resetSeries = true;
    render();
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

  imageDownloadButton?.addEventListener("click", () => {
    const selectedIndicator = indicators.find((item) => String(item?.id) === String(activeIndicatorId)) || indicators[0];
    const indicator = resolveRenderableIndicator(selectedIndicator, indicators) || selectedIndicator;
    const fileBase = String(indicator?.id || "sdg-indicator").replace(/[^\w.-]+/g, "-");
    if (activeChartType === "map") {
      exportMapExplorerAsPng(mapEl, `${fileBase}-${activeChartType}.png`);
      return;
    }
    const chartSvg = chartEl.querySelector("svg");
    if (!chartSvg) {
      return;
    }
    downloadSvgElement(chartSvg, `${fileBase}-${activeChartType}.png`);
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
  const detailBase = page.dataset.detailBase || "";
  const dataBase = page.dataset.dataBase || "";
  const pageMode = page.dataset.pageMode || "overview";
  const state = page.querySelector("[data-sdg-detail-state]");
  const content = page.querySelector("[data-sdg-detail-content]");
  const initialIndicatorId = new URLSearchParams(window.location.search).get("indicator") || "";

  try {
    const payload = await fetchJson(endpoint);
    content.innerHTML = renderPage(payload, listBase, {
      dataOnly: pageMode === "data",
      detailBase,
      dataBase,
      initialIndicatorId,
    });
    content.hidden = false;
    initializeTargetIndicatorLinks(content, { dataPageUrl: dataBase });
    if (pageMode === "data") {
      initializeDataWorkspace(content, payload);
    }
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
