import { createDpmesPeriodFilter } from "../components/dpmes-period-filter.js";

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
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

function renderState(container, message) {
  container.innerHTML = `<div class="goal-detail-state">${escapeHtml(message)}</div>`;
}

function renderLoadingBlock() {
  return `
    <div class="goal-loading">
      <div class="goal-loading__line goal-loading__line--lg"></div>
      <div class="goal-loading__line goal-loading__line--md"></div>
      <div class="goal-loading__line goal-loading__line--sm"></div>
    </div>
  `;
}

function renderLoading(hero, body) {
  hero.innerHTML = `
    <section class="goal-hero goal-hero--loading">
      <div class="goal-hero__shell">${renderLoadingBlock()}</div>
    </section>
  `;
  body.innerHTML = `
    <div class="goal-layout">
      <section class="goal-panel">${renderLoadingBlock()}</section>
      <section class="goal-panel">${renderLoadingBlock()}${renderLoadingBlock()}</section>
    </div>
  `;
}

function renderCurrentPeriod(state) {
  const quarterMap = {
    "3month": "Q1",
    "6month": "Q2",
    "9month": "Q3",
    "12month": "Q4",
  };

  return state.dateType === "quarterly"
    ? `${escapeHtml(state.year)} - ${escapeHtml(quarterMap[state.quarter] || state.quarter)}`
    : `${escapeHtml(state.year)}`;
}

function formatNumber(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return "--";
  }
  return numeric % 1 === 0 ? String(numeric) : numeric.toFixed(2);
}

function formatPercent(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return "--";
  }
  return `${numeric.toFixed(2)}%`;
}

function normalizeDetail(payload) {
  return payload?.data && typeof payload.data === "object" ? payload.data : {};
}

function normalizeIndicatorDetail(payload) {
  return payload?.data && typeof payload.data === "object" ? payload.data : {};
}

function renderHero(detail, state) {
  const scoreCard = detail?.goal_score_card || {};
  const scoreColor = scoreCard.scorecard_color || "#5d9444";
  const score = formatPercent(scoreCard.avg_score);
  const scoreValue = Math.max(0, Math.min(Number(scoreCard.avg_score) || 0, 100));

  return `
    <section class="goal-hero" style="--goal-accent:${escapeHtml(scoreColor)}">
      <div class="goal-hero__shell">
        <div class="goal-hero__top">
          <a class="goal-hero__back" href="javascript:history.back()">
            <i class="ti ti-arrow-left"></i><span>Back to goals</span>
          </a>
        </div>
        <div class="goal-hero__body">
          <div class="goal-hero__main">
            <span class="goal-hero__kicker">Goal Dashboard</span>
            <h1>${escapeHtml(detail.goal_name_eng || detail.goal_name_amh || "Goal")}</h1>
            <p class="goal-hero__subtitle">Reporting period: ${escapeHtml(renderCurrentPeriod(state))}</p>
          </div>
          <div class="goal-hero__aside">
            <div class="goal-hero__scorecard">
              <span class="goal-hero__scorelabel">Goal Score</span>
              <strong class="goal-hero__scorevalue">${escapeHtml(score)}</strong>
              <div class="goal-hero__progress-track">
                <span class="goal-hero__progress-fill" style="width:${escapeHtml(scoreValue)}%; background:${escapeHtml(scoreColor)}"></span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  `;
}

function renderPerformanceCard(key, title, bucket, modifier, isActive) {
  const percentage = formatPercent(bucket?.percentage);
  return `
    <button type="button" class="goal-performance-card ${modifier}${isActive ? " is-active" : ""}" data-performance-bucket="${escapeHtml(key)}" aria-pressed="${isActive ? "true" : "false"}">
      <span class="goal-performance-card__label">${escapeHtml(title)}</span>
      <strong>${escapeHtml(percentage)}</strong>
      <div class="goal-performance-card__meta">
        <span>Target ${escapeHtml(formatNumber(bucket?.target))}</span>
        <span>Actual ${escapeHtml(formatNumber(bucket?.performance))}</span>
      </div>
    </button>
  `;
}

function getPerformanceBuckets(detail) {
  return {
    good: detail.good_performance || {},
    average: detail.average_performance || {},
    poor: detail.poor_performance || {},
    no_performance: detail.no_performance || {},
  };
}

function renderPerformanceSummary(detail, selectedBucket) {
  const buckets = getPerformanceBuckets(detail);
  const labelMap = {
    good: "Good",
    average: "Average",
    poor: "Poor",
    no_performance: "No Performance",
  };
  return `
    <section class="goal-panel">
      <div class="goal-sectionhead">
        <div>
          <h2>Performance Snapshot</h2>
          <p>Current delivery distribution for the selected reporting period.</p>
        </div>
        ${
          selectedBucket
            ? `<button type="button" class="goal-section-clear" data-clear-performance-filter>
          Clear ${escapeHtml(labelMap[selectedBucket] || "Filter")}
        </button>`
            : ""
        }
      </div>
      <div class="goal-performance-grid">
        ${renderPerformanceCard("good", "Good", buckets.good, "goal-performance-card--good", selectedBucket === "good")}
        ${renderPerformanceCard("average", "Average", buckets.average, "goal-performance-card--average", selectedBucket === "average")}
        ${renderPerformanceCard("poor", "Poor", buckets.poor, "goal-performance-card--poor", selectedBucket === "poor")}
        ${renderPerformanceCard("no_performance", "No Performance", buckets.no_performance, "goal-performance-card--neutral", selectedBucket === "no_performance")}
      </div>
    </section>
  `;
}

function getIndicatorSeries(indicator, state) {
  if (state.dateType === "quarterly") {
    return Array.isArray(indicator?.quarter_indicators) ? indicator.quarter_indicators : [];
  }
  return Array.isArray(indicator?.annual_indicators) ? indicator.annual_indicators : [];
}

function getLatestIndicatorRecord(indicator, state) {
  const series = getIndicatorSeries(indicator, state);
  return series.length ? series[0] : null;
}

function getIndicatorTarget(record, state) {
  if (!record) {
    return "--";
  }
  return state.dateType === "quarterly"
    ? formatNumber(record.quarter_target)
    : formatNumber(record.annual_target);
}

function getIndicatorPerformance(record, state) {
  if (!record) {
    return "--";
  }
  return state.dateType === "quarterly"
    ? formatNumber(record.quarter_performance)
    : formatNumber(record.annual_performance);
}

function hasIndicatorTarget(record, state) {
  if (!record) {
    return false;
  }
  const rawValue = state.dateType === "quarterly" ? record.quarter_target : record.annual_target;
  return rawValue !== null && rawValue !== undefined && rawValue !== "";
}

function getRenderableIndicators(kra, state) {
  const indicators = Array.isArray(kra?.indicators) ? kra.indicators : [];
  return indicators.filter((indicator) => hasIndicatorTarget(getLatestIndicatorRecord(indicator, state), state));
}

function getIndicatorScore(record) {
  if (!record) {
    return "--";
  }
  return formatPercent(record.score);
}

function getQuarterSortValue(quarterValue) {
  const map = { "3month": 1, "6month": 2, "9month": 3, "12month": 4 };
  return map[quarterValue] || 0;
}

function getIndicatorSeriesRecords(detail, seriesKey) {
  const source = seriesKey === "quarterly" ? detail?.quarter_indicators : detail?.annual_indicators;
  const records = Array.isArray(source) ? [...source] : [];
  records.sort((left, right) => {
    const leftYear = Number(left?.year) || 0;
    const rightYear = Number(right?.year) || 0;
    if (leftYear !== rightYear) {
      return leftYear - rightYear;
    }
    if (seriesKey === "quarterly") {
      return getQuarterSortValue(left?.quarter) - getQuarterSortValue(right?.quarter);
    }
    return 0;
  });
  return records;
}

function getIndicatorAvailableSeries(detail) {
  const tabs = [];
  if (Array.isArray(detail?.annual_indicators) && detail.annual_indicators.length) {
    tabs.push("yearly");
  }
  if (Array.isArray(detail?.quarter_indicators) && detail.quarter_indicators.length) {
    tabs.push("quarterly");
  }
  return tabs;
}

function getRecordLabel(record, seriesKey) {
  if (!record) {
    return "--";
  }
  if (seriesKey === "quarterly") {
    return `${record.year || "--"} ${record.quarter || ""}`.trim();
  }
  return String(record.year || "--");
}

function getSeriesTarget(record, seriesKey) {
  return seriesKey === "quarterly"
    ? formatNumber(record?.quarter_target)
    : formatNumber(record?.annual_target);
}

function getSeriesPerformance(record, seriesKey) {
  return seriesKey === "quarterly"
    ? formatNumber(record?.quarter_performance)
    : formatNumber(record?.annual_performance);
}

function getSeriesScore(record) {
  return formatNumber(record?.score);
}

function renderKpiDrawerLoading(container) {
  container.innerHTML = `
    <div class="goal-loading">
      <div class="goal-loading__line goal-loading__line--lg"></div>
      <div class="goal-loading__line goal-loading__line--md"></div>
      <div class="goal-loading__line goal-loading__line--sm"></div>
    </div>
  `;
}

function renderKpiDrawerState(container, message) {
  container.innerHTML = `<div class="goal-detail-state">${escapeHtml(message)}</div>`;
}

function getBucketRecordTarget(record, state) {
  return state.dateType === "quarterly"
    ? formatNumber(record?.quarter_target)
    : formatNumber(record?.annual_target);
}

function getBucketRecordPerformance(record, state) {
  return state.dateType === "quarterly"
    ? formatNumber(record?.quarter_performance)
    : formatNumber(record?.annual_performance);
}

function renderIndicatorCard(indicator, state) {
  const record = getLatestIndicatorRecord(indicator, state);
  const recordColor = record?.scorecard || "#5d9444";
  const score = getIndicatorScore(record);

  return `
    <button type="button" class="goal-indicator-card" style="--indicator-accent:${escapeHtml(recordColor)}" data-kpi-id="${escapeHtml(indicator.id)}">
      <div class="goal-indicator-card__accent"></div>
      <div class="goal-indicator-card__main">
        <div class="goal-indicator-card__marker" aria-hidden="true">
          <span class="goal-indicator-card__marker-dot"></span>
        </div>
        <div class="goal-indicator-card__identity">
          <span class="goal-indicator-card__label">Indicator</span>
          <h4>${escapeHtml(indicator.kpi_name_eng || indicator.kpi_name_amh || "Indicator")}</h4>
        </div>
        <div class="goal-indicator-card__stats">
          <div class="goal-indicator-card__score">${escapeHtml(score)}</div>
        </div>
      </div>
    </button>
  `;
}

function renderBucketIndicatorCard(record, state) {
  const recordColor = record?.scorecard || "#5d9444";
  const score = formatPercent(record?.score);
  const name = record?.indicator_name || "Indicator";
  const target = getBucketRecordTarget(record, state);
  const performance = getBucketRecordPerformance(record, state);
  const indicatorId = record?.indicator;

  return `
    <button type="button" class="goal-indicator-card" style="--indicator-accent:${escapeHtml(recordColor)}" data-kpi-id="${escapeHtml(indicatorId)}">
      <div class="goal-indicator-card__accent"></div>
      <div class="goal-indicator-card__main">
        <div class="goal-indicator-card__marker" aria-hidden="true">
          <span class="goal-indicator-card__marker-dot"></span>
        </div>
        <div class="goal-indicator-card__identity">
          <span class="goal-indicator-card__label">Indicator</span>
          <h4>${escapeHtml(name)}</h4>
        </div>
        <div class="goal-indicator-card__stats">
          <div class="goal-indicator-card__score">${escapeHtml(score)}</div>
        </div>
      </div>
      <div class="goal-indicator-card__detailrow">
        <span>Target ${escapeHtml(target)}</span>
        <span>Performance ${escapeHtml(performance)}</span>
      </div>
    </button>
  `;
}

function renderKraCard(kra, state, index) {
  const indicators = getRenderableIndicators(kra, state);
  const scoreCard = kra?.kra_score_card || {};
  const scoreColor = scoreCard.scorecard_color || "#5d9444";

  return `
    <details class="goal-kra-card" style="--kra-accent:${escapeHtml(scoreColor)}"${index === 0 ? " open" : ""}>
      <summary class="goal-kra-card__summary">
        <div class="goal-kra-card__head">
          <div>
            <span class="goal-kra-card__eyebrow">Key Result Area</span>
            <h3>${escapeHtml(kra.activity_name_eng || kra.activity_name_amh || "KRA")}</h3>
          </div>
          <div class="goal-kra-card__headside">
            <div class="goal-kra-card__score">${escapeHtml(formatPercent(scoreCard.avg_score))}</div>
            <span class="goal-kra-card__toggle"><i class="ti ti-chevron-down"></i></span>
          </div>
        </div>
        <div class="goal-kra-card__meta">
          <span>${escapeHtml(kra.activity_is_shared ? "Shared activity" : "Single activity")}</span>
          <span>${escapeHtml(indicators.length)} indicators</span>
        </div>
      </summary>
      <div class="goal-kra-card__content">
        <div class="goal-indicators-grid">
          ${
            indicators.length
              ? indicators.map((indicator) => renderIndicatorCard(indicator, state)).join("")
              : `<div class="goal-empty">No indicators are available for this key result area.</div>`
          }
        </div>
      </div>
    </details>
  `;
}

function renderKraSection(detail, state) {
  const kras = (Array.isArray(detail.kra_goal) ? detail.kra_goal : []).filter(
    (kra) => getRenderableIndicators(kra, state).length > 0
  );
  return `
    <section class="goal-panel">
      <div class="goal-sectionhead">
        <div>
          <h2>Key Result Areas</h2>
          <p>Browse each activity and inspect the indicators reported under it.</p>
        </div>
      </div>
      <div class="goal-kra-list">
        ${
          kras.length
            ? kras.map((kra, index) => renderKraCard(kra, state, index)).join("")
            : `<div class="goal-empty">No key result areas are available for the selected period.</div>`
        }
      </div>
    </section>
  `;
}

function renderBucketSection(detail, state, selectedBucket) {
  const bucketMap = getPerformanceBuckets(detail);
  const bucket = bucketMap[selectedBucket] || {};
  const records = Array.isArray(bucket.data) ? bucket.data : [];
  const labelMap = {
    good: "Good",
    average: "Average",
    poor: "Poor",
    no_performance: "No Performance",
  };

  return `
    <section class="goal-panel">
      <div class="goal-sectionhead">
        <div>
          <h2>${escapeHtml(labelMap[selectedBucket] || "Performance")} KPIs</h2>
          <p>Showing KPI records from the selected performance bucket. Click the active card again to return to key result areas.</p>
        </div>
      </div>
      <div class="goal-indicators-grid goal-indicators-grid--bucket">
        ${
          records.length
            ? records.map((record) => renderBucketIndicatorCard(record, state)).join("")
            : `<div class="goal-empty">No KPI records are available in this performance bucket.</div>`
        }
      </div>
    </section>
  `;
}

function renderKpiMetadata(detail) {
  const ministry = detail?.responsible_ministries || {};
  const characteristicMap = {
    inc: "Increasing",
    dec: "Decreasing",
    con: "Constant",
  };
  const rawItems = [
    ["Code", detail.kpi_code || "Not available"],
    ["Title", detail.kpi_name_eng || detail.kpi_name_amh || "Not available"],
    ["Owner", ministry.responsible_ministry_eng || ministry.responsible_ministry_amh || "Not available"],
    ["Ministry Code", ministry.code || ""],
    ["Characteristics", characteristicMap[detail.kpi_characteristics] || detail.kpi_characteristics || "Not available"],
    ["Measurement Unit", detail.kpi_measurement_units || ""],
    ["Weight", detail.kpi_weight || ""],
    ["Key Result Area", detail.keyResultArea || ""],
    ["Goal", detail.goal || ""],
    ["Description", detail.kpi_description || ""],
  ];
  const items = rawItems.filter(([, value]) => {
    if (value === null || value === undefined) return false;
    const normalized = String(value).trim();
    return normalized.length > 0;
  });

  return `
    <details class="goal-kpi-section goal-kpi-section--collapsible">
      <summary class="goal-kpi-section__head goal-kpi-section__head--summary">
        <h3>Indicator Details</h3>
        <div class="goal-kpi-section__headside">
          <span class="goal-kpi-section__tag">Metadata</span>
          <span class="goal-kpi-section__toggle"><i class="ti ti-chevron-down"></i></span>
        </div>
      </summary>
      <div class="goal-kpi-section__body">
        <div class="goal-kpi-meta-list">
        ${items
          .map(
            ([label, value]) => `
              <div class="goal-kpi-meta-item">
                <span>${escapeHtml(label)}</span>
                <strong>${escapeHtml(value)}</strong>
              </div>
            `
          )
          .join("")}
        </div>
      </div>
    </details>
  `;
}

function renderKpiAnalytics(detail, activeSeries) {
  const records = getIndicatorSeriesRecords(detail, activeSeries);
  const latestRecord = records[records.length - 1] || null;
  const averageScore = records.length
    ? (records.reduce((sum, record) => sum + (Number(record?.score) || 0), 0) / records.length).toFixed(2)
    : "--";

  return `
    <details class="goal-kpi-section goal-kpi-section--collapsible" open>
      <summary class="goal-kpi-section__head goal-kpi-section__head--summary">
        <h3>Performance Trends</h3>
        <div class="goal-kpi-section__headside">
          <span class="goal-kpi-section__tag">Analytics</span>
          <span class="goal-kpi-section__toggle"><i class="ti ti-chevron-down"></i></span>
        </div>
      </summary>
      <div class="goal-kpi-section__body">
      <div class="goal-kpi-tabs">
        ${getIndicatorAvailableSeries(detail)
          .map(
            (seriesKey) => `
              <button type="button" class="goal-kpi-tab${seriesKey === activeSeries ? " is-active" : ""}" data-kpi-series="${escapeHtml(seriesKey)}">
                ${escapeHtml(seriesKey === "yearly" ? "Yearly" : "Quarterly")}
              </button>
            `
          )
          .join("")}
      </div>
      <div class="goal-kpi-stats">
        <div class="goal-kpi-stat">
          <span>Records</span>
          <strong>${escapeHtml(String(records.length))}</strong>
        </div>
        <div class="goal-kpi-stat">
          <span>Latest Target</span>
          <strong>${escapeHtml(getSeriesTarget(latestRecord, activeSeries))}</strong>
        </div>
        <div class="goal-kpi-stat">
          <span>Latest Performance</span>
          <strong>${escapeHtml(getSeriesPerformance(latestRecord, activeSeries))}</strong>
        </div>
        <div class="goal-kpi-stat">
          <span>Avg Score</span>
          <strong>${escapeHtml(averageScore)}</strong>
        </div>
      </div>
      <div class="goal-kpi-chartpanel">
        <div class="goal-kpi-chart" data-goal-kpi-chart></div>
      </div>
      </div>
    </details>
    <details class="goal-kpi-section goal-kpi-section--collapsible">
      <summary class="goal-kpi-section__head goal-kpi-section__head--summary">
        <h3>Performance Records</h3>
        <div class="goal-kpi-section__headside">
          <span class="goal-kpi-section__tag">Table</span>
          <span class="goal-kpi-section__toggle"><i class="ti ti-chevron-down"></i></span>
        </div>
      </summary>
      <div class="goal-kpi-section__body">
      <div class="goal-kpi-tablewrap">
        <table class="goal-kpi-table">
          <thead>
            <tr>
              <th>${activeSeries === "yearly" ? "Year" : "Period"}</th>
              <th>Plan</th>
              <th>Performance</th>
              <th>Score</th>
            </tr>
          </thead>
          <tbody>
            ${
              records.length
                ? records
                    .map(
                      (record) => `
                        <tr>
                          <td>${escapeHtml(getRecordLabel(record, activeSeries))}</td>
                          <td>${escapeHtml(getSeriesTarget(record, activeSeries))}</td>
                          <td>${escapeHtml(getSeriesPerformance(record, activeSeries))}</td>
                          <td><span class="goal-kpi-table__score">${escapeHtml(getSeriesScore(record))}</span></td>
                        </tr>
                      `
                    )
                    .join("")
                : `<tr><td colspan="4">No records available for this series.</td></tr>`
            }
          </tbody>
        </table>
      </div>
      </div>
    </details>
  `;
}

function renderKpiDrawer(detail, activeSeries) {
  return `
    ${renderKpiMetadata(detail)}
    ${renderKpiAnalytics(detail, activeSeries)}
  `;
}

function renderKpiChart(container, detail, activeSeries) {
  if (!container || !window.ApexCharts) {
    return null;
  }

  const records = getIndicatorSeriesRecords(detail, activeSeries);
  const categories = records.map((record) => getRecordLabel(record, activeSeries));
  const targetData = records.map((record) => Number(activeSeries === "quarterly" ? record?.quarter_target : record?.annual_target) || 0);
  const performanceData = records.map((record) => Number(activeSeries === "quarterly" ? record?.quarter_performance : record?.annual_performance) || 0);
  const latestColoredRecord = [...records].reverse().find((record) => record?.scorecard);
  const scoreColor = latestColoredRecord?.scorecard || "#0f766e";

  const chart = new window.ApexCharts(container, {
    chart: {
      type: "line",
      height: 320,
      toolbar: { show: false },
      zoom: { enabled: false },
    },
    series: [
      { name: "Target", type: "column", data: targetData },
      { name: "Performance", type: "column", data: performanceData },
      { name: "Trendline", type: "line", data: performanceData },
    ],
    stroke: {
      width: [0, 0, 3],
      curve: "smooth",
      dashArray: [0, 0, 6],
    },
    colors: ["#2f855a", "#d89d2b", scoreColor],
    plotOptions: {
      bar: {
        columnWidth: "36%",
        borderRadius: 6,
      },
    },
    dataLabels: { enabled: false },
    xaxis: {
      categories,
      labels: { rotate: -20 },
    },
    yaxis: {
      labels: {
        formatter(value) {
          return Number(value).toFixed(0);
        },
      },
    },
    grid: {
      borderColor: "#e2e8f0",
      strokeDashArray: 4,
    },
    legend: {
      position: "top",
      horizontalAlign: "left",
    },
    tooltip: {
      shared: true,
    },
  });

  chart.render();
  return chart;
}

async function loadGoalDetail() {
  const root = document.querySelector("[data-goal-detail]");
  if (!root) {
    return;
  }

  const goalId = root.dataset.goalId;
  const hero = root.querySelector("[data-goal-hero]");
  const body = root.querySelector("[data-goal-body]");
  const currentPeriod = root.querySelector("[data-goal-current-period]");
  const query = new URLSearchParams(window.location.search);
  const drawerEl = document.querySelector("[data-goal-kpi-drawer]");
  const drawerTitle = drawerEl?.querySelector("[data-goal-kpi-title]");
  const drawerContent = drawerEl?.querySelector("[data-goal-kpi-content]");
  const drawer = drawerEl && window.bootstrap ? window.bootstrap.Offcanvas.getOrCreateInstance(drawerEl) : null;
  let selectedBucket = "";
  let currentDetail = null;
  let currentDrawerChart = null;
  let currentDrawerSeries = "yearly";

  const filter = await createDpmesPeriodFilter(root, {
    initialState: {
      year: query.get("year") || "2018",
      quarter: query.get("quarter") || "3month",
      dateType: query.get("quarter") ? "quarterly" : "yearly",
    },
    onChange: async (_state, _reason, api) => {
      const nextQuery = api.getQueryString();
      window.history.replaceState({}, "", `${window.location.pathname}?${nextQuery}`);
      currentPeriod.textContent = renderCurrentPeriod(api.getState());
      await renderDetail(api.getState());
    },
  });

  async function renderDetail(state) {
    try {
      renderLoading(hero, body);
      const params = new URLSearchParams({ year: state.year });
      if (state.dateType === "quarterly") {
        params.set("quarter", state.quarter);
      }

      const payload = await fetchJson(`/api/mobile/goal-detail/${goalId}/?${params.toString()}`);
      const detail = normalizeDetail(payload);
      currentDetail = detail;

      hero.innerHTML = renderHero(detail, state);
      body.innerHTML = `
        <div class="goal-layout">
          ${renderPerformanceSummary(detail, selectedBucket)}
          ${selectedBucket ? renderBucketSection(detail, state, selectedBucket) : renderKraSection(detail, state)}
        </div>
      `;

      body.querySelectorAll("[data-performance-bucket]").forEach((button) => {
        button.addEventListener("click", async () => {
          const nextBucket = button.dataset.performanceBucket || "";
          selectedBucket = selectedBucket === nextBucket ? "" : nextBucket;
          await renderDetail(state);
        });
      });

      const clearFilterButton = body.querySelector("[data-clear-performance-filter]");
      if (clearFilterButton) {
        clearFilterButton.addEventListener("click", async () => {
          selectedBucket = "";
          await renderDetail(state);
        });
      }

      body.querySelectorAll("[data-kpi-id]").forEach((button) => {
        button.addEventListener("click", async () => {
          const indicatorId = button.dataset.kpiId;
          await openKpiDrawer(indicatorId);
        });
      });
    } catch (_error) {
      renderState(hero, "Unable to load goal detail right now.");
      renderState(body, "The goal detail API did not return a usable payload.");
    }
  }

  async function openKpiDrawer(indicatorId) {
    if (!drawerEl || !drawerContent || !drawerTitle || !indicatorId) {
      return;
    }

    drawerTitle.textContent = "Indicator Detail";
    renderKpiDrawerLoading(drawerContent);
    drawer?.show();

    try {
      const payload = await fetchJson(`/api/mobile/dpmes-indicator-detail/${indicatorId}/`);
      const detail = normalizeIndicatorDetail(payload);
      const availableSeries = getIndicatorAvailableSeries(detail);
      currentDrawerSeries = availableSeries.includes("quarterly") ? "quarterly" : (availableSeries[0] || "yearly");
      drawerTitle.textContent = detail.kpi_name_eng || detail.kpi_name_amh || "Indicator Detail";
      renderDrawerContent(detail);
    } catch (_error) {
      renderKpiDrawerState(drawerContent, "Unable to load KPI detail right now.");
    }
  }

  function renderDrawerContent(detail) {
    if (!drawerContent) {
      return;
    }
    drawerContent.innerHTML = renderKpiDrawer(detail, currentDrawerSeries);

    if (currentDrawerChart) {
      currentDrawerChart.destroy();
      currentDrawerChart = null;
    }

    const chartEl = drawerContent.querySelector("[data-goal-kpi-chart]");
    currentDrawerChart = renderKpiChart(chartEl, detail, currentDrawerSeries);

    drawerContent.querySelectorAll("[data-kpi-series]").forEach((button) => {
      button.addEventListener("click", () => {
        const nextSeries = button.dataset.kpiSeries;
        if (!nextSeries || nextSeries === currentDrawerSeries) {
          return;
        }
        currentDrawerSeries = nextSeries;
        renderDrawerContent(detail);
      });
    });
  }

  drawerEl?.addEventListener("hidden.bs.offcanvas", () => {
    if (currentDrawerChart) {
      currentDrawerChart.destroy();
      currentDrawerChart = null;
    }
  });

  currentPeriod.textContent = renderCurrentPeriod(filter.getState());
  renderLoading(hero, body);
  await renderDetail(filter.getState());
}

loadGoalDetail();
