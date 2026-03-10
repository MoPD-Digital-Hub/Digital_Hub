const DEFAULT_OPTIONS = {
  endpoint: "/api/mobile/high-frequency/",
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
  const seriesMap = {
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

  return Array.isArray(seriesMap[latestData]) ? seriesMap[latestData] : [];
}

function getMonthOrder(value) {
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
  const raw = String(value || "").trim();
  return monthMap[raw] || Number(raw.replace(/[^0-9]/g, "") || 0);
}

function getPointSortValue(point, frequency) {
  const year = Number(point?.for_datapoint || 0);
  const quarterValue = Number(String(point?.for_quarter || "").replace(/[^0-9]/g, "") || 0);
  const monthValue = getMonthOrder(point?.for_month);
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

function getSortedSeries(indicator) {
  const frequency = String(indicator?.latest_data || "").toLowerCase();
  return [...getSeriesByLatestData(indicator)].sort(
    (left, right) => getPointSortValue(left, frequency) - getPointSortValue(right, frequency)
  );
}

function getLatestPoint(indicator) {
  return getSortedSeries(indicator).at(-1) || null;
}

function getPointLabel(point, frequency) {
  if (!point) {
    return "";
  }

  if (frequency === "quarter" || frequency === "quarterly") {
    return `${point.for_datapoint || ""} ${point.for_quarter || ""}`.trim();
  }
  if (frequency === "month" || frequency === "monthly") {
    return [point.for_datapoint, point.for_month].filter(Boolean).join(" ");
  }
  return String(point.for_datapoint || point.for_week || point.for_day || "");
}

function getMetricUnit(indicator) {
  const latestData = String(indicator?.latest_data || "").toLowerCase();
  return (
    indicator?.[`measurement_units_${latestData}`] ||
    indicator?.measurement_units ||
    indicator?.frequency ||
    "-"
  );
}

function getChildItems(indicator) {
  const children = Array.isArray(indicator?.children) ? indicator.children : [];
  return children
    .filter((child) => child && typeof child === "object")
    .map((child) => {
      const latestPoint = getLatestPoint(child);
      return {
        title: child?.title_ENG || child?.title_AMH || child?.code || "Child indicator",
        value: formatValue(latestPoint?.performance),
        unit: getMetricUnit(child),
      };
    });
}

function getRenderableSeries(indicator, limit = 8) {
  return getSortedSeries(indicator)
    .filter((point) => point?.performance !== null && point?.performance !== undefined && point?.performance !== "")
    .slice(-limit);
}

function getMiniLineChart(indicator) {
  const series = getRenderableSeries(indicator);
  if (series.length < 2) {
    return "";
  }

  const values = series
    .map((point) => Number(point?.performance))
    .filter((value) => Number.isFinite(value));

  if (values.length < 2) {
    return "";
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const width = 260;
  const height = 72;
  const baseline = height - 10;
  const gradientId = `hf-line-fill-${indicator?.id || Math.random().toString(36).slice(2, 8)}`;
  const coordinates = series
    .map((point, index) => {
      const numeric = Number(point?.performance || 0);
      const x = (index / Math.max(series.length - 1, 1)) * width;
      const y = baseline - ((numeric - min) / range) * (height - 20);
      return { x, y };
    })
    ;

  const linePath = buildSmoothPath(coordinates);
  const areaPath = `${linePath} L ${width},${baseline} L 0,${baseline} Z`;

  return `
    <div class="hf-dashboard-card__viz hf-dashboard-card__viz--line" aria-hidden="true">
      <svg class="hf-dashboard-card__chart" viewBox="0 0 ${width} ${height}" focusable="false">
        <defs>
          <linearGradient id="${gradientId}" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="rgba(15, 118, 110, 0.18)"></stop>
            <stop offset="100%" stop-color="rgba(15, 118, 110, 0)"></stop>
          </linearGradient>
        </defs>
        <line class="hf-dashboard-card__chart-grid" x1="0" y1="${baseline}" x2="${width}" y2="${baseline}"></line>
        <path class="hf-dashboard-card__chart-area" d="${areaPath}" fill="url(#${gradientId})"></path>
        <path class="hf-dashboard-card__chart-line" d="${linePath}"></path>
      </svg>
    </div>
  `;
}

function getMiniBarChart(indicator) {
  const series = getRenderableSeries(indicator, 7);
  if (!series.length) {
    return "";
  }

  const values = series
    .map((point) => Number(point?.performance))
    .filter((value) => Number.isFinite(value));
  const max = Math.max(...values, 1);
  const width = 220;
  const height = 68;
  const baseline = height - 8;
  const barWidth = 16;
  const gap = Math.max(10, Math.floor((width - barWidth * series.length) / Math.max(series.length - 1, 1)));

  const bars = series
    .map((point, index) => {
      const value = Number(point?.performance || 0);
      const barHeight = Math.max(10, ((value / max) * (height - 20)));
      const x = index * (barWidth + gap);
      const y = baseline - barHeight;
      return `<rect class="hf-dashboard-card__chart-bar" x="${x}" y="${y.toFixed(1)}" width="${barWidth}" height="${barHeight.toFixed(1)}" rx="4"></rect>`;
    })
    .join("");

  return `
    <div class="hf-dashboard-card__viz hf-dashboard-card__viz--bar" aria-hidden="true">
      <svg class="hf-dashboard-card__chart" viewBox="0 0 ${width} ${height}" focusable="false">
        <line class="hf-dashboard-card__chart-grid" x1="0" y1="${baseline}" x2="${width}" y2="${baseline}"></line>
        ${bars}
      </svg>
    </div>
  `;
}

function buildSmoothPath(points) {
  if (!Array.isArray(points) || !points.length) {
    return "";
  }

  if (points.length === 1) {
    return `M ${points[0].x.toFixed(1)},${points[0].y.toFixed(1)}`;
  }

  let path = `M ${points[0].x.toFixed(1)},${points[0].y.toFixed(1)}`;

  for (let index = 0; index < points.length - 1; index += 1) {
    const current = points[index];
    const next = points[index + 1];
    const controlX = ((current.x + next.x) / 2).toFixed(1);
    path += ` C ${controlX},${current.y.toFixed(1)} ${controlX},${next.y.toFixed(1)} ${next.x.toFixed(1)},${next.y.toFixed(1)}`;
  }

  return path;
}

function buildDetailHref(item, detailBase) {
  const indicatorId = item?.indicator?.id;
  if (!detailBase || !indicatorId) {
    return "";
  }
  return `${String(detailBase).replace(/\/?$/, "/")}${indicatorId}/`;
}

function createWidgetCard(item, detailBase) {
  const indicator = item?.indicator || {};
  const latestPoint = getLatestPoint(indicator);
  const frequency = String(indicator?.latest_data || indicator?.frequency || "annual").toLowerCase();
  const chartType = String(item?.chart_type || "number").toLowerCase();
  const title = indicator?.title_ENG || indicator?.title_AMH || "High Frequency Indicator";
  const href = buildDetailHref(item, detailBase);
  const tagName = href ? "a" : "article";
  const hrefAttr = href ? ` href="${escapeHtml(href)}"` : "";
  const latestLabel = latestPoint ? getPointLabel(latestPoint, frequency) : "No recent datapoint";
  const seriesCount = getRenderableSeries(indicator, 1000).filter(
    (point) => point?.performance !== null && point?.performance !== undefined && point?.performance !== ""
  ).length;
  const visualization =
    chartType === "line"
      ? getMiniLineChart(indicator)
      : chartType === "bar"
        ? getMiniBarChart(indicator)
        : "";
  const chartIcon =
    chartType === "line"
      ? "chart-line"
      : chartType === "bar"
        ? "chart-bar"
        : "hash";
  const badgeText = item?.include_children ? "Expanded" : "Live";
  const rowSizeClass = item?._rowSizeClass || "hf-dashboard-card--compact";
  const childItems = item?.include_children
    ? getChildItems(indicator)
    : [];
  const childCards = childItems
    .map(
      (child) => `
        <div class="hf-dashboard-card__child">
          <span class="hf-dashboard-card__child-title">${escapeHtml(child.title)}</span>
          <strong class="hf-dashboard-card__child-value">
            ${escapeHtml(child.value)}
            ${child.unit && child.unit !== "-" ? `<small>${escapeHtml(child.unit)}</small>` : ""}
          </strong>
        </div>
      `
    )
    .join("");
  const childrenMarkup = childItems.length
    ? `
      <div class="hf-dashboard-card__children ${childItems.length > 1 ? "hf-dashboard-card__children--animated" : ""}">
        <div class="hf-dashboard-card__children-track">
          ${childCards}
          ${childItems.length > 1 ? childCards : ""}
        </div>
      </div>
    `
    : "";

  return `
    <${tagName} class="hf-dashboard-card ${escapeHtml(rowSizeClass)} hf-dashboard-card--${escapeHtml(chartType)}"${hrefAttr}>
      <div class="hf-dashboard-card__head">
        <span class="hf-dashboard-card__chip">
          <i class="ti ti-${chartIcon}"></i>
          Indicator
        </span>
        <span class="hf-dashboard-card__rank">${escapeHtml(badgeText)}</span>
      </div>
      <div class="hf-dashboard-card__body">
        <div class="hf-dashboard-card__content">
          <div class="hf-dashboard-card__metric">
            <strong>${escapeHtml(formatValue(latestPoint?.performance))}</strong>
            <span>${escapeHtml(getMetricUnit(indicator))}</span>
          </div>
          <div>
            <h3 class="hf-dashboard-card__title">${escapeHtml(title)}</h3>
            <div class="hf-dashboard-card__meta">
              <span>${escapeHtml((indicator?.latest_data || indicator?.frequency || "annual").toUpperCase())}</span>
              <span>${escapeHtml(latestLabel)}</span>
              <span>${escapeHtml(`${seriesCount || 0} records`)}</span>
              ${item?.include_children ? "<span>Includes children</span>" : ""}
            </div>
          </div>
          ${childrenMarkup}
        </div>
        ${visualization}
      </div>
      <div class="hf-dashboard-card__footer">
        <span>${escapeHtml(indicator?.code || "No code")}</span>
        <span><i class="ti ti-arrow-up-right"></i> Open indicator</span>
      </div>
    </${tagName}>
  `;
}

function createRow(row, detailBase) {
  const columns = Array.isArray(row) ? row.length : 0;
  if (!columns) {
    return "";
  }

  const rowSizeClass =
    columns === 1
      ? "hf-dashboard-card--hero"
      : columns === 2
        ? "hf-dashboard-card--medium"
        : "hf-dashboard-card--compact";

  return `
    <section class="hf-dashboard-row" style="--hf-row-cols:${columns}">
      ${row
        .map((item) => createWidgetCard({ ...item, _rowSizeClass: rowSizeClass }, detailBase))
        .join("")}
    </section>
  `;
}

function renderLoading(body) {
  body.innerHTML = Array.from({ length: 3 }, () => {
    const cells = Array.from({ length: 3 }, () => '<div class="hf-dashboard-skeleton"></div>').join("");
    return `<section class="hf-dashboard-row" style="--hf-row-cols:3">${cells}</section>`;
  }).join("");
}

function renderState(body, message) {
  body.innerHTML = `<div class="hf-dashboard-state">${escapeHtml(message)}</div>`;
}

function initChildrenRails(root) {
  const rails = root.querySelectorAll(".hf-dashboard-card__children");

  rails.forEach((rail) => {
    if (rail.dataset.dragReady === "true") {
      return;
    }

    rail.dataset.dragReady = "true";

    let isPointerDown = false;
    let startX = 0;
    let startScrollLeft = 0;

    rail.addEventListener("pointerdown", (event) => {
      if (event.pointerType === "mouse" && event.button !== 0) {
        return;
      }

      isPointerDown = true;
      startX = event.clientX;
      startScrollLeft = rail.scrollLeft;
      rail.classList.add("is-dragging");
      rail.setPointerCapture?.(event.pointerId);
    });

    rail.addEventListener("pointermove", (event) => {
      if (!isPointerDown) {
        return;
      }

      const deltaX = event.clientX - startX;
      rail.scrollLeft = startScrollLeft - deltaX;
    });

    const stopDragging = (event) => {
      if (!isPointerDown) {
        return;
      }

      isPointerDown = false;
      rail.classList.remove("is-dragging");
      if (event?.pointerId !== undefined) {
        rail.releasePointerCapture?.(event.pointerId);
      }
    };

    rail.addEventListener("pointerup", stopDragging);
    rail.addEventListener("pointercancel", stopDragging);
    rail.addEventListener("pointerleave", stopDragging);
  });
}

async function mountHighFrequencyDashboard(element, options = {}) {
  if (!element) {
    return null;
  }

  const settings = {
    ...DEFAULT_OPTIONS,
    ...options,
    endpoint: element.dataset.endpoint || options.endpoint || DEFAULT_OPTIONS.endpoint,
    detailBase: element.dataset.detailBase || options.detailBase || DEFAULT_OPTIONS.detailBase,
  };

  const body = element.querySelector("[data-hf-dashboard-body]");
  if (!body) {
    return null;
  }

  renderLoading(body);

  try {
    const response = await fetch(settings.endpoint, {
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    const rows = Array.isArray(payload?.data)
      ? payload.data.filter((row) => Array.isArray(row) && row.length)
      : [];

    if (!rows.length) {
      renderState(body, "No high frequency widgets are configured right now.");
      return null;
    }

    body.innerHTML = rows.map((row) => createRow(row, settings.detailBase)).join("");
    initChildrenRails(body);
  } catch (_error) {
    renderState(body, "Unable to load the high frequency dashboard right now.");
  }

  return null;
}

export const HighFrequencyDashboard = {
  init(elementOrSelector, options = {}) {
    const element =
      typeof elementOrSelector === "string"
        ? document.querySelector(elementOrSelector)
        : elementOrSelector;
    return mountHighFrequencyDashboard(element, options);
  },
};

window.HighFrequencyDashboard = HighFrequencyDashboard;
