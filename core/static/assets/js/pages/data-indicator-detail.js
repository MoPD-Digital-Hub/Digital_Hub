const mediaBaseUrl = "https://time-series.mopd.gov.et/";
let indicatorChartInstance = null;
let indicatorChartWindowSize = null;
let indicatorChartContext = null;
let indicatorChartFocusIndex = null;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderState(container, message) {
  container.innerHTML = `<div class="data-indicator-state">${escapeHtml(message)}</div>`;
}

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

const ETHIOPIAN_MONTH_ORDER = {
  "መስከረም": 1,
  "ጥቅምት": 2,
  "ህዳር": 3,
  "ኅዳር": 3,
  "ታኅሣሥ": 4,
  "ታህሳስ": 4,
  "ጥር": 5,
  "የካቲት": 6,
  "መጋቢት": 7,
  "ሚያዝያ": 8,
  "ግንቦት": 9,
  "ሰኔ": 10,
  "ሐምሌ": 11,
  "ሃምሌ": 11,
  "ነሐሴ": 12,
  "ነሃሴ": 12,
  "ጳጉሜን": 13,
};

function getQuarterOrder(value) {
  const match = String(value || "").match(/q\s*([1-4])/i);
  return match ? Number(match[1]) : 0;
}

function getMonthOrder(value) {
  const text = String(value || "").trim();
  if (ETHIOPIAN_MONTH_ORDER[text]) {
    return ETHIOPIAN_MONTH_ORDER[text];
  }
  const numeric = Number(text);
  return Number.isFinite(numeric) && numeric > 0 ? numeric : 0;
}

function getSeriesConfig(indicator) {
  return [
    {
      key: "annual",
      label: "Annual",
      points: Array.isArray(indicator?.annual_data) ? indicator.annual_data : [],
      unit: indicator?.measurement_units || "",
    },
    {
      key: "quarter",
      label: "Quarter",
      points: Array.isArray(indicator?.quarter_data) ? indicator.quarter_data : [],
      unit: indicator?.measurement_units_quarter || indicator?.measurement_units || "",
    },
    {
      key: "month",
      label: "Month",
      points: Array.isArray(indicator?.month_data) ? indicator.month_data : [],
      unit: indicator?.measurement_units_month || indicator?.measurement_units || "",
    },
    {
      key: "week",
      label: "Week",
      points: Array.isArray(indicator?.week_data) ? indicator.week_data : [],
      unit: indicator?.measurement_units || "",
    },
    {
      key: "day",
      label: "Day",
      points: Array.isArray(indicator?.day_data) ? indicator.day_data : [],
      unit: indicator?.measurement_units || "",
    },
  ];
}

function getPointSortKey(point, seriesKey) {
  const year = Number(point?.for_datapoint || 0);

  if (seriesKey === "quarter") {
    return year * 10 + getQuarterOrder(point?.for_quarter);
  }

  if (seriesKey === "month") {
    return year * 100 + getMonthOrder(point?.for_month);
  }

  return year || 0;
}

function sortPoints(points, seriesKey) {
  return [...points].sort((left, right) => {
    const diff = getPointSortKey(left, seriesKey) - getPointSortKey(right, seriesKey);
    if (diff !== 0) {
      return diff;
    }
    return new Date(left?.created_at || 0).getTime() - new Date(right?.created_at || 0).getTime();
  });
}

function getSeriesLabel(point, seriesKey) {
  if (seriesKey === "quarter") {
    return `${point.for_quarter || ""} ${point.for_datapoint || ""}`.trim() || "Quarter";
  }
  if (seriesKey === "month") {
    return `${point.for_month || ""}${point.for_datapoint ? ` ${point.for_datapoint}` : ""}`.trim() || "Month";
  }
  return String(point?.for_datapoint || point?.for_month || point?.for_quarter || "Period");
}

function getVisiblePointWindow(activeSeries) {
  const points = Array.isArray(activeSeries?.points) ? activeSeries.points : [];
  if (!indicatorChartWindowSize || indicatorChartWindowSize >= points.length) {
    return { points, startIndex: 0 };
  }

  const focusIndex =
    Number.isInteger(indicatorChartFocusIndex) && indicatorChartFocusIndex >= 0
      ? Math.min(indicatorChartFocusIndex, points.length - 1)
      : points.length - 1;
  const halfWindow = Math.floor(indicatorChartWindowSize / 2);
  let startIndex = Math.max(0, focusIndex - halfWindow);
  if (startIndex + indicatorChartWindowSize > points.length) {
    startIndex = Math.max(0, points.length - indicatorChartWindowSize);
  }

  return {
    points: points.slice(startIndex, startIndex + indicatorChartWindowSize),
    startIndex,
  };
}

function getAvailableSeries(indicator) {
  return getSeriesConfig(indicator)
    .map((series) => ({
      ...series,
      points: sortPoints(
        series.points.filter((point) => point && point.performance !== null && point.performance !== undefined),
        series.key
      ),
    }))
    .filter((series) => series.points.length > 0);
}

function getDefaultSeries(indicator, series) {
  const latest = String(indicator?.latest_data || "").toLowerCase();
  return series.find((item) => item.key === latest) || series[0] || null;
}

function renderHero(indicator) {
  const title = indicator?.title_ENG || indicator?.title_AMH || "Indicator";
  const description = indicator?.description || "Inspect historical values, metadata, and data series for this indicator.";

  return `
    <div class="data-indicator-hero">
      <div class="data-indicator-hero-shell">
        <div class="data-indicator-hero-top">
          <a class="data-indicator-back" href="javascript:history.back()"><i class="ti ti-arrow-left"></i><span>Back</span></a>
          <span class="data-indicator-chip">${escapeHtml(indicator?.code || "Indicator")}</span>
        </div>
        <div class="data-indicator-hero-main">
          <div class="data-indicator-hero-title">
            <h1>${escapeHtml(title)}</h1>
            <p>${escapeHtml(description)}</p>
          </div>
          <div class="data-indicator-hero-meta">
            <span>${escapeHtml(indicator?.frequency || "No frequency")}</span>
            <span>${escapeHtml(indicator?.measurement_units || "No unit")}</span>
            <span>${escapeHtml(indicator?.source || "No source")}</span>
          </div>
        </div>
      </div>
    </div>
  `;
}

function renderStats(activeSeries) {
  const latestPoint = activeSeries.points[activeSeries.points.length - 1];
  const firstPoint = activeSeries.points[0];
  const pointCount = activeSeries.points.length;

  return `
    <div class="data-indicator-stats">
      <div class="data-indicator-stat">
        <span>Latest Value</span>
        <strong>${escapeHtml(formatMetricValue(latestPoint?.performance))}</strong>
      </div>
      <div class="data-indicator-stat">
        <span>Current Period</span>
        <strong>${escapeHtml(getSeriesLabel(latestPoint, activeSeries.key))}</strong>
      </div>
      <div class="data-indicator-stat">
        <span>Series Coverage</span>
        <strong>${escapeHtml(`${pointCount} points`)}</strong>
      </div>
    </div>
  `;
}

function renderSeriesTabs(series, activeKey) {
  return `
    <div class="data-indicator-series-tabs">
      ${series
        .map(
          (item) => `
            <button
              type="button"
              class="data-indicator-series-tab${item.key === activeKey ? " is-active" : ""}"
              data-series-tab
              data-series-key="${escapeHtml(item.key)}"
            >
              ${escapeHtml(item.label)}
            </button>
          `
        )
        .join("")}
    </div>
  `;
}

function getDefaultChartType(activeSeries) {
  return activeSeries?.key === "annual" ? "bar" : "line";
}

function renderChartTypeTabs(activeType) {
  const options = [
    { key: "line", label: "Line" },
    { key: "bar", label: "Bar" },
  ];

  return `
    <div class="data-indicator-chart-tabs">
      ${options
        .map(
          (option) => `
            <button
              type="button"
              class="data-indicator-chart-tab${option.key === activeType ? " is-active" : ""}"
              data-chart-type-tab
              data-chart-type="${escapeHtml(option.key)}"
            >
              ${escapeHtml(option.label)}
            </button>
          `
        )
        .join("")}
    </div>
  `;
}

function renderChartControls() {
  return `
    <div class="data-indicator-chart-controls">
      <button type="button" class="data-indicator-chart-control" data-chart-control="previous" aria-label="Previous zoom">
        <i class="ti ti-arrow-back-up"></i>
      </button>
      <button type="button" class="data-indicator-chart-control" data-chart-control="zoom-in" aria-label="Zoom in">
        <i class="ti ti-plus"></i>
      </button>
      <button type="button" class="data-indicator-chart-control" data-chart-control="zoom-out" aria-label="Zoom out">
        <i class="ti ti-minus"></i>
      </button>
      <button type="button" class="data-indicator-chart-control" data-chart-control="fullscreen" aria-label="Fullscreen">
        <i class="ti ti-maximize"></i>
      </button>
    </div>
  `;
}

function renderTable(activeSeries) {
  return `
    <div class="data-indicator-table-wrap">
      <table class="data-indicator-table">
        <thead>
          <tr>
            <th>Period</th>
            <th>Performance</th>
          </tr>
        </thead>
        <tbody>
          ${activeSeries.points
            .slice()
            .reverse()
            .map(
              (point) => `
                <tr>
                  <td>${escapeHtml(getSeriesLabel(point, activeSeries.key))}</td>
                  <td>${escapeHtml(formatMetricValue(point.performance))}</td>
                </tr>
              `
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderChildren(children) {
  if (!Array.isArray(children) || !children.length) {
    return `<div class="data-indicator-state">No sub indicators are attached to this indicator.</div>`;
  }

  return `
    <div class="data-indicator-children">
      ${children
        .map((child) => {
          const availableSeries = getAvailableSeries(child);
          const defaultSeries = getDefaultSeries(child, availableSeries);
          const latestPoint = defaultSeries?.points?.at(-1) || null;
          const latestUnit =
            defaultSeries?.unit ||
            child?.measurement_units ||
            child?.measurement_units_quarter ||
            child?.measurement_units_month ||
            "";
          const latestFrequency = defaultSeries?.label || child?.latest_data || child?.frequency || "No frequency";

          return `
            <article class="data-indicator-child">
              <a href="/dashboard/data/indicator/${escapeHtml(child.id)}/">${escapeHtml(child.title_ENG || child.title_AMH || "Indicator")}</a>
              <div class="data-indicator-child-value">
                <strong>${escapeHtml(formatMetricValue(latestPoint?.performance))}</strong>
                ${latestUnit ? `<small>${escapeHtml(latestUnit)}</small>` : ""}
              </div>
              <div class="data-indicator-child-meta">
                <span>${escapeHtml(child.code || "No code")}</span>
                <span>${escapeHtml(String(latestFrequency).toUpperCase())}</span>
                ${latestPoint ? `<span>${escapeHtml(getSeriesLabel(latestPoint, defaultSeries?.key || child?.latest_data || "annual"))}</span>` : ""}
              </div>
            </article>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderKeyFacts(indicator) {
  const facts = [
    ["Code", indicator?.code || "No code"],
    ["Frequency", indicator?.frequency || "No frequency"],
    ["Measurement Unit", indicator?.measurement_units || "No unit"],
    ["Source", indicator?.source || "No source"],
    ["Methodology", indicator?.methodology || "No methodology provided"],
    ["Responsible Entity", indicator?.responsible_entity || "Not specified"],
  ];

  return `
    <div class="data-indicator-keyfacts">
      ${facts
        .map(
          ([label, value]) => `
            <div class="data-indicator-keyfact">
              <span>${escapeHtml(label)}</span>
              <p>${escapeHtml(value)}</p>
            </div>
          `
        )
        .join("")}
    </div>
  `;
}

function renderBody(indicator, series, activeKey, chartType) {
  const activeSeries = series.find((item) => item.key === activeKey) || series[0];
  if (!activeSeries) {
    return `<div class="data-indicator-state">No usable data series were returned for this indicator.</div>`;
  }

  const activeChartType = chartType || getDefaultChartType(activeSeries);

  return `
    <div class="data-indicator-layout">
      <div class="data-indicator-main">
        <section class="data-indicator-panel">
          <div class="data-indicator-panel-head">
            <h2>Trend Overview</h2>
            ${renderSeriesTabs(series, activeSeries.key)}
          </div>
          <div class="data-indicator-chart-toolbar">
            ${renderChartControls()}
            ${renderChartTypeTabs(activeChartType)}
          </div>
          ${renderStats(activeSeries)}
          <div class="data-indicator-chart-wrap">
            <div class="data-indicator-chart" data-indicator-chart></div>
          </div>
        </section>
        <section class="data-indicator-panel">
          <div class="data-indicator-panel-head">
            <h3>Data Table</h3>
          </div>
          ${renderTable(activeSeries)}
        </section>
      </div>
      <aside class="data-indicator-side">
        <section class="data-indicator-panel">
          <div class="data-indicator-panel-head">
            <h3>Indicator Metadata</h3>
          </div>
          ${renderKeyFacts(indicator)}
        </section>
        <section class="data-indicator-panel">
          <div class="data-indicator-panel-head">
            <h3>Sub Indicators</h3>
          </div>
          ${renderChildren(indicator?.children || [])}
        </section>
      </aside>
    </div>
  `;
}

function mountChart(container, activeSeries, chartType) {
  if (!container || !window.ApexCharts || !activeSeries) {
    return;
  }

  if (indicatorChartInstance) {
    indicatorChartInstance.destroy();
    indicatorChartInstance = null;
  }

  const { points: visiblePoints, startIndex } = getVisiblePointWindow(activeSeries);
  const categories = visiblePoints.map((point) => getSeriesLabel(point, activeSeries.key));
  const values = visiblePoints.map((point) => Number(point.performance || 0));
  container.innerHTML = "";
  const pointCount = visiblePoints.length;
  const isBar = chartType === "bar";
  const isDark = document.body.getAttribute("data-pc-theme") === "dark";
  container.style.minWidth = "0";
  container.style.width = "100%";
  const seriesData = isBar
    ? values
    : visiblePoints.map((point) => ({
        x: getSeriesLabel(point, activeSeries.key),
        y: Number(point.performance || 0),
      }));

  const chart = new ApexCharts(container, {
    chart: {
      type: isBar ? "bar" : "line",
      width: "100%",
      height: 340,
      toolbar: {
        show: false,
        tools: {
          download: false,
          selection: true,
          zoom: true,
          zoomin: true,
          zoomout: true,
          pan: true,
          reset: true,
        },
      },
      zoom: {
        enabled: true,
        type: "x",
        autoScaleYaxis: true,
      },
      selection: {
        enabled: true,
      },
      events: {
        dataPointSelection(_event, _chartContext, config) {
          if (typeof config?.dataPointIndex === "number" && config.dataPointIndex >= 0) {
            indicatorChartFocusIndex = startIndex + config.dataPointIndex;
          }
        },
      },
      foreColor: isDark ? "#cbd5e1" : "#64748b",
    },
    series: [
      {
        name: activeSeries.label,
        data: seriesData,
      },
    ],
    colors: [isBar ? "#f59e0b" : "#5d9444"],
    stroke: {
      width: isBar ? 0 : 3,
      curve: isBar ? "straight" : "smooth",
      lineCap: "round",
    },
    plotOptions: isBar
      ? {
          bar: {
            columnWidth: pointCount > 20 ? "58%" : "66%",
            borderRadius: 4,
            borderRadiusApplication: "end",
          },
        }
      : {},
    fill: {
      type: isBar ? "solid" : "gradient",
      gradient: {
        shadeIntensity: 1,
        opacityFrom: isBar ? 1 : 0.24,
        opacityTo: isBar ? 1 : 0.03,
      },
    },
    markers: {
      size: isBar ? 0 : 3.5,
      strokeWidth: isBar ? 0 : 3,
      strokeColors: isDark ? "#0f172a" : "#ffffff",
      fillOpacity: 1,
      hover: {
        size: 6.5,
      },
    },
    dataLabels: { enabled: false },
    grid: {
      borderColor: isDark ? "#314252" : "#e2e8f0",
      strokeDashArray: 4,
    },
    xaxis: {
      categories: isBar ? categories : undefined,
      type: "category",
      tickPlacement: isBar ? "between" : "on",
      tickAmount: Math.min(pointCount, 12),
      labels: {
        rotate: -90,
        rotateAlways: pointCount > 8,
        trim: false,
        hideOverlappingLabels: true,
        style: {
          fontSize: isBar ? "11px" : "10px",
        },
      },
    },
    yaxis: {
      forceNiceScale: true,
      labels: {
        formatter(value) {
          return formatMetricValue(value);
        },
      },
    },
    tooltip: {
      y: {
        formatter(value) {
          return `${formatMetricValue(value)} ${activeSeries.unit || ""}`.trim();
        },
      },
    },
  });

  chart.render();
  indicatorChartInstance = chart;
  indicatorChartContext = { container, activeSeries, chartType };
}

function bindSeriesTabs(root, indicator, series, currentChartType) {
  const tabs = Array.from(root.querySelectorAll("[data-series-tab]"));
  const body = root.querySelector("[data-indicator-detail-body]");

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const nextKey = tab.dataset.seriesKey;
      const activeSeries = series.find((item) => item.key === nextKey) || series[0];
      const nextChartType = currentChartType || getDefaultChartType(activeSeries);
      body.innerHTML = renderBody(indicator, series, nextKey, nextChartType);
      bindIndicatorInteractions(root, indicator, series, nextKey, nextChartType);
    });
  });
}

function bindChartTypeTabs(root, indicator, series, currentSeriesKey) {
  const tabs = Array.from(root.querySelectorAll("[data-chart-type-tab]"));
  const body = root.querySelector("[data-indicator-detail-body]");

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const nextChartType = tab.dataset.chartType || "line";
      body.innerHTML = renderBody(indicator, series, currentSeriesKey, nextChartType);
      bindIndicatorInteractions(root, indicator, series, currentSeriesKey, nextChartType);
    });
  });
}

async function toggleChartFullscreen(root) {
  const panel = root.querySelector(".data-indicator-panel");
  if (!panel) {
    return;
  }

  if (document.fullscreenElement) {
    await document.exitFullscreen();
    return;
  }

  if (panel.requestFullscreen) {
    await panel.requestFullscreen();
  }
}

function bindChartControls(root) {
  const controls = Array.from(root.querySelectorAll("[data-chart-control]"));

  controls.forEach((control) => {
    control.addEventListener("click", async () => {
      if (!indicatorChartContext) {
        return;
      }

      const action = control.dataset.chartControl;
      const totalPoints = indicatorChartContext.activeSeries.points.length;
      if (action === "zoom-in") {
        const currentWindow = indicatorChartWindowSize || totalPoints;
        indicatorChartWindowSize = Math.max(6, Math.ceil(currentWindow * 0.7));
        if (!Number.isInteger(indicatorChartFocusIndex)) {
          indicatorChartFocusIndex = totalPoints - 1;
        }
        mountChart(
          indicatorChartContext.container,
          indicatorChartContext.activeSeries,
          indicatorChartContext.chartType
        );
        return;
      }
      if (action === "zoom-out") {
        if (!indicatorChartWindowSize) {
          return;
        }
        const nextWindow = Math.min(totalPoints, Math.ceil(indicatorChartWindowSize / 0.7));
        indicatorChartWindowSize = nextWindow >= totalPoints ? null : nextWindow;
        mountChart(
          indicatorChartContext.container,
          indicatorChartContext.activeSeries,
          indicatorChartContext.chartType
        );
        return;
      }
      if (action === "fullscreen") {
        await toggleChartFullscreen(root);
        return;
      }
      indicatorChartWindowSize = null;
      indicatorChartFocusIndex = null;
      mountChart(
        indicatorChartContext.container,
        indicatorChartContext.activeSeries,
        indicatorChartContext.chartType
      );
    });
  });
}

function bindIndicatorInteractions(root, indicator, series, currentSeriesKey, currentChartType) {
  const body = root.querySelector("[data-indicator-detail-body]");
  const activeSeries = series.find((item) => item.key === currentSeriesKey) || series[0];
  const activeChartType = currentChartType || getDefaultChartType(activeSeries);
  indicatorChartWindowSize = null;
  indicatorChartFocusIndex = null;
  bindSeriesTabs(root, indicator, series, activeChartType);
  bindChartTypeTabs(root, indicator, series, activeSeries.key);
  bindChartControls(root);
  mountChart(body.querySelector("[data-indicator-chart]"), activeSeries, activeChartType);
}

async function loadIndicatorDetail() {
  const root = document.querySelector("[data-indicator-detail]");
  if (!root) {
    return;
  }

  const indicatorId = root.dataset.indicatorId;
  const hero = root.querySelector("[data-indicator-detail-hero]");
  const body = root.querySelector("[data-indicator-detail-body]");

  try {
    const payload = await fetchJson(`/api/mobile/indicator-detail/${indicatorId}/`);
    const indicator = Array.isArray(payload?.data) ? payload.data[0] : payload?.data;

    if (!indicator || typeof indicator !== "object") {
      throw new Error("Invalid payload");
    }

    const series = getAvailableSeries(indicator);
    const activeSeries = getDefaultSeries(indicator, series);

    hero.innerHTML = renderHero(indicator);
    body.innerHTML = renderBody(indicator, series, activeSeries?.key, getDefaultChartType(activeSeries));
    bindIndicatorInteractions(root, indicator, series, activeSeries?.key, getDefaultChartType(activeSeries));
  } catch (_error) {
    renderState(hero, "Unable to load indicator detail right now.");
    renderState(body, "The indicator detail endpoint did not return a usable payload.");
  }
}

loadIndicatorDetail();
