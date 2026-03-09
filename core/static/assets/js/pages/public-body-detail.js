import { createDpmesPeriodFilter } from "../components/dpmes-period-filter.js";

const MEDIA_BASE_URL = "https://time-series.mopd.gov.et/";

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

function buildMediaUrl(path) {
  if (!path) {
    return "";
  }
  try {
    return new URL(path, MEDIA_BASE_URL).toString();
  } catch (_error) {
    return path;
  }
}

function renderLoadingBlock() {
  return `
    <div class="public-body-loading">
      <div class="public-body-loading__line public-body-loading__line--lg"></div>
      <div class="public-body-loading__line public-body-loading__line--md"></div>
      <div class="public-body-loading__line public-body-loading__line--sm"></div>
    </div>
  `;
}

function renderLoading(hero, body) {
  hero.innerHTML = `<section class="public-body-detail-hero public-body-detail-hero--loading"><div class="public-body-detail-hero-shell">${renderLoadingBlock()}</div></section>`;
  body.innerHTML = `<section class="public-body-detail-panel">${renderLoadingBlock()}${renderLoadingBlock()}</section>`;
}

function renderState(container, message) {
  container.innerHTML = `<div class="public-body-detail-state">${escapeHtml(message)}</div>`;
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

function normalizeIndicatorDetail(payload) {
  return payload?.data && typeof payload.data === "object" ? payload.data : {};
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
  const items = rawItems.filter(([, value]) => value !== null && value !== undefined && String(value).trim().length > 0);

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
          ${items.map(([label, value]) => `
            <div class="goal-kpi-meta-item">
              <span>${escapeHtml(label)}</span>
              <strong>${escapeHtml(value)}</strong>
            </div>
          `).join("")}
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
          ${getIndicatorAvailableSeries(detail).map((seriesKey) => `
            <button type="button" class="goal-kpi-tab${seriesKey === activeSeries ? " is-active" : ""}" data-kpi-series="${escapeHtml(seriesKey)}">
              ${escapeHtml(seriesKey === "yearly" ? "Yearly" : "Quarterly")}
            </button>
          `).join("")}
        </div>
        <div class="goal-kpi-stats">
          <div class="goal-kpi-stat"><span>Records</span><strong>${escapeHtml(String(records.length))}</strong></div>
          <div class="goal-kpi-stat"><span>Latest Target</span><strong>${escapeHtml(getSeriesTarget(latestRecord, activeSeries))}</strong></div>
          <div class="goal-kpi-stat"><span>Latest Performance</span><strong>${escapeHtml(getSeriesPerformance(latestRecord, activeSeries))}</strong></div>
          <div class="goal-kpi-stat"><span>Avg Score</span><strong>${escapeHtml(averageScore)}</strong></div>
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
                  ? records.map((record) => `
                    <tr>
                      <td>${escapeHtml(getRecordLabel(record, activeSeries))}</td>
                      <td>${escapeHtml(getSeriesTarget(record, activeSeries))}</td>
                      <td>${escapeHtml(getSeriesPerformance(record, activeSeries))}</td>
                      <td><span class="goal-kpi-table__score">${escapeHtml(getSeriesScore(record))}</span></td>
                    </tr>
                  `).join("")
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
  return `${renderKpiMetadata(detail)}${renderKpiAnalytics(detail, activeSeries)}`;
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
    stroke: { width: [0, 0, 3], curve: "smooth", dashArray: [0, 0, 6] },
    colors: ["#2f855a", "#d89d2b", scoreColor],
    plotOptions: { bar: { columnWidth: "36%", borderRadius: 6 } },
    dataLabels: { enabled: false },
    xaxis: { categories, labels: { rotate: -20 } },
    yaxis: { labels: { formatter(value) { return Number(value).toFixed(0); } } },
    grid: { borderColor: "#e2e8f0", strokeDashArray: 4 },
    legend: { position: "top", horizontalAlign: "left" },
    tooltip: { shared: true },
  });

  chart.render();
  return chart;
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

function getMinistryOverview(items, ministryId) {
  return Array.isArray(items)
    ? items.find((item) => Number(item.id) === Number(ministryId)) || {}
    : {};
}

function getAffiliatedLabel(item) {
  const title = item?.responsible_ministry_eng || item?.responsible_ministry_amh || "Organization";
  const code = item?.code ? ` (${item.code})` : "";
  return `${title}${code}`;
}

function renderAffiliatedOptions(select, items, selectedId) {
  if (!select) {
    return;
  }

  if (!Array.isArray(items) || !items.length) {
    select.innerHTML = '<option value="">No organizations available</option>';
    select.disabled = true;
    return;
  }

  select.disabled = false;
  select.innerHTML = [
    `<option value="all"${selectedId === "all" ? " selected" : ""}>All</option>`,
    ...items.map((item) => `
      <option value="${escapeHtml(item.id)}"${Number(item.id) === Number(selectedId) ? " selected" : ""}>
        ${escapeHtml(getAffiliatedLabel(item))}
      </option>
    `),
  ].join("");
}

function renderHero(overview, detailItems, state) {
  const title = overview.responsible_ministry_eng || overview.responsible_ministry_amh || "Public Body";
  const code = overview.code || "PB";
  const logo = buildMediaUrl(overview.image || "");
  const scoreCard = overview.ministry_score_card || {};
  const scoreColor = scoreCard.scorecard_color || "#0f766e";
  const scoreValue = Number(scoreCard.avg_score);
  const score = Number.isFinite(scoreValue) ? `${scoreValue.toFixed(2)}%` : "--";
  const progressWidth = Number.isFinite(scoreValue) ? Math.max(0, Math.min(scoreValue, 100)) : 0;
  const policyAreaCount = Array.isArray(detailItems) ? detailItems.length : 0;

  return `
    <section class="public-body-detail-hero" style="--public-body-accent:${escapeHtml(scoreColor)}">
      <div class="public-body-detail-hero-shell">
        <div class="public-body-detail-top">
          <a class="public-body-detail-back" href="/dashboard/statistics/public-bodies/?${escapeHtml(new URLSearchParams({
            year: state.year,
            ...(state.dateType === "quarterly" ? { quarter: state.quarter } : {}),
          }).toString())}">
            <i class="ti ti-arrow-left"></i><span>Back to public bodies</span>
          </a>
        </div>
        <div class="public-body-detail-head">
          <div class="public-body-detail-identity">
            <span class="public-body-detail-logo">
              ${
                logo
                  ? `<img src="${escapeHtml(logo)}" alt="${escapeHtml(title)} logo" loading="lazy" decoding="async">`
                  : `<span>${escapeHtml(code.slice(0, 2))}</span>`
              }
            </span>
            <div class="public-body-detail-copy">
              <span class="public-body-detail-kicker">Public Body Dashboard</span>
              <h1>${escapeHtml(title)}</h1>
              <div class="public-body-detail-meta">
                <span>${escapeHtml(code)}</span>
                <span>${escapeHtml(renderCurrentPeriod(state))}</span>
                <span>${escapeHtml(`${policyAreaCount} policy area${policyAreaCount === 1 ? "" : "s"}`)}</span>
              </div>
            </div>
          </div>
          <div class="public-body-detail-progress">
            <div class="public-body-detail-progress__top">
              <span>Overall score</span>
              <strong>${escapeHtml(score)}</strong>
            </div>
            <div class="public-body-detail-progress__track">
              <span class="public-body-detail-progress__fill" style="width:${escapeHtml(progressWidth)}%; background:${escapeHtml(scoreColor)}"></span>
            </div>
          </div>
        </div>
      </div>
    </section>
  `;
}

function getPerformanceBuckets(detail) {
  const resolveArray = (...keys) => {
    for (const key of keys) {
      if (Array.isArray(detail?.[key])) {
        return detail[key];
      }
    }
    return [];
  };

  return {
    on_track: resolveArray("good_performance", "high_performance", "on_track"),
    in_progress: resolveArray("average_performance", "in_progress"),
    weak_performance: resolveArray("low_performance", "weak_performance"),
    no_data: resolveArray("no_data"),
  };
}

function renderPerformanceCard(key, title, records, modifier, isActive) {
  return `
    <button type="button" class="public-body-performance-card ${modifier}${isActive ? " is-active" : ""}" data-performance-bucket="${escapeHtml(key)}" aria-pressed="${isActive ? "true" : "false"}">
      <span class="public-body-performance-card__label">${escapeHtml(title)}</span>
      <strong>${escapeHtml(String(records.length))}</strong>
    </button>
  `;
}

function renderPerformanceSummary(performanceDetail, selectedBucket) {
  const buckets = getPerformanceBuckets(performanceDetail);
  const labels = {
    on_track: "On Track",
    in_progress: "In Progress",
    weak_performance: "Weak Performance",
    no_data: "No Data",
  };

  return `
    <section class="public-body-detail-panel">
      <div class="public-body-section-head public-body-section-head--stack">
        <div>
          <h2>Indicator's Performances</h2>
          <p>Click a card to see details.</p>
        </div>
        ${
          selectedBucket
            ? `<button type="button" class="public-body-section-clear" data-clear-performance-filter>Clear Filter</button>`
            : ""
        }
      </div>
      <div class="public-body-performance-grid">
        ${renderPerformanceCard("on_track", "On Track", buckets.on_track, "public-body-performance-card--good", selectedBucket === "on_track")}
        ${renderPerformanceCard("in_progress", "In Progress", buckets.in_progress, "public-body-performance-card--average", selectedBucket === "in_progress")}
        ${renderPerformanceCard("weak_performance", "Weak Performance", buckets.weak_performance, "public-body-performance-card--poor", selectedBucket === "weak_performance")}
        ${renderPerformanceCard("no_data", "No Data", buckets.no_data, "public-body-performance-card--neutral", selectedBucket === "no_data")}
      </div>
    </section>
  `;
}

function renderPerformanceIndicatorCard(record) {
  const scoreColor = record?.scorecard || "#94a3b8";
  const name = record?.indicator_name || "Indicator";
  const score = formatPercent(record?.score);
  const indicatorId = record?.indicator;

  return `
    <button type="button" class="goal-indicator-card" style="--indicator-accent:${escapeHtml(scoreColor)}" data-kpi-id="${escapeHtml(indicatorId)}">
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
    </button>
  `;
}

function renderBucketSection(performanceDetail, selectedBucket) {
  const buckets = getPerformanceBuckets(performanceDetail);
  const records = buckets[selectedBucket] || [];
  const labels = {
    on_track: "On Track",
    in_progress: "In Progress",
    weak_performance: "Weak Performance",
    no_data: "No Data",
  };

  return `
    <section class="public-body-detail-panel">
      <div class="public-body-section-head public-body-section-head--stack">
        <div>
          <h2>${escapeHtml(labels[selectedBucket] || "Performance")} Indicators</h2>
          <p>Indicator list for the selected performance group.</p>
        </div>
      </div>
      <div class="public-body-indicators-grid">
        ${
          records.length
            ? records.map((record) => renderPerformanceIndicatorCard(record)).join("")
            : `<div class="public-body-empty-block">No indicators are available in this performance group.</div>`
        }
      </div>
    </section>
  `;
}

function renderGoalCard(goal, state, selectedOrganizationId) {
  const scoreCard = goal.ministry_strategic_goal_score_card || {};
  const score = Number(scoreCard.avg_score);
  const scoreText = Number.isFinite(score) ? `${score.toFixed(2)}%` : "--";
  const scoreColor = scoreCard.scorecard_color || "#0f766e";
  const progressWidth = Number.isFinite(score) ? Math.max(0, Math.min(score, 100)) : 0;
  const params = new URLSearchParams({ year: state.year });
  if (selectedOrganizationId && selectedOrganizationId !== "all") {
    params.set("ministry_id", selectedOrganizationId);
    params.set("org_id", selectedOrganizationId);
  } else if (goal?.responsible_ministries) {
    params.set("ministry_id", goal.responsible_ministries);
  }
  if (state.dateType === "quarterly") {
    params.set("quarter", state.quarter);
  }

  return `
    <a class="public-body-goal-card" href="/dashboard/statistics/goals/${escapeHtml(goal.id)}/?${escapeHtml(params.toString())}" style="--goal-accent:${escapeHtml(scoreColor)}">
      <div class="public-body-goal-card__top">
        <span class="public-body-goal-card__score">${escapeHtml(scoreText)}</span>
      </div>
      <h3>${escapeHtml(goal.goal_name_eng || goal.goal_name_amh || "Strategic Goal")}</h3>
      <div class="public-body-goal-card__meta">
        <span>Goal</span>
        <strong>${escapeHtml(goal.goal_weight_percentage != null ? `${Number(goal.goal_weight_percentage).toFixed(2)}% weight` : "Strategic goal")}</strong>
      </div>
      <div class="public-body-goal-card__progress">
        <span class="public-body-goal-card__progressbar" style="width:${escapeHtml(progressWidth)}%"></span>
      </div>
    </a>
  `;
}

function renderPolicyAreaSection(item, state, selectedOrganizationId) {
  const scoreCard = item.ministry_policy_area_score_card || {};
  const score = Number(scoreCard.avg_score);
  const scoreText = Number.isFinite(score) ? `${score.toFixed(2)}%` : "--";
  const scoreColor = scoreCard.scorecard_color || "#0f766e";
  const goals = Array.isArray(item.policy_area_goal) ? item.policy_area_goal.filter((goal) => goal && goal.goal_is_visable !== false) : [];
  const imageIcon = buildMediaUrl(item.image_icon || "");

  return `
    <section class="public-body-detail-panel">
      <div class="public-body-section-head">
        <div class="public-body-section-title">
          <span class="public-body-section-icon">
            ${
              imageIcon
                ? `<img src="${escapeHtml(imageIcon)}" alt="" loading="lazy" decoding="async">`
                : `<i class="ti ti-building-community"></i>`
            }
          </span>
          <div>
            <h2>${escapeHtml(item.policyAreaEng || item.policyAreaAmh || "Policy Area")}</h2>
            <p>${escapeHtml(`${goals.length} strategic goal${goals.length === 1 ? "" : "s"}`)}</p>
          </div>
        </div>
        <div class="public-body-section-score" style="--section-accent:${escapeHtml(scoreColor)}">
          <span>Area score</span>
          <strong>${escapeHtml(scoreText)}</strong>
        </div>
      </div>
      <div class="public-body-goals-grid">
        ${
          goals.length
            ? goals.map((goal) => renderGoalCard(goal, state, selectedOrganizationId)).join("")
            : `<div class="public-body-empty-block">No strategic goals are available for this policy area.</div>`
        }
      </div>
    </section>
  `;
}

async function loadPublicBodyDetail() {
  const root = document.querySelector("[data-public-body-detail]");
  if (!root) {
    return;
  }

  const ministryId = root.dataset.ministryId;
  const affiliatedSelect = root.querySelector("[data-public-body-affiliated-select]");
  const hero = root.querySelector("[data-public-body-hero]");
  const body = root.querySelector("[data-public-body-body]");
  const currentPeriod = root.querySelector("[data-public-body-current-period]");
  const query = new URLSearchParams(window.location.search);
  const drawerEl = document.querySelector("[data-goal-kpi-drawer]");
  const drawerBackdrop = document.querySelector("[data-goal-kpi-backdrop]");
  const drawerTitle = drawerEl?.querySelector("[data-goal-kpi-title]");
  const drawerContent = drawerEl?.querySelector("[data-goal-kpi-content]");
  const drawerClose = drawerEl?.querySelector("[data-goal-kpi-close]");
  let selectedBucket = "";
  let selectedOrganizationId = query.get("org_id") || "all";
  let affiliatedItems = [];
  let currentDrawerChart = null;
  let currentDrawerSeries = "yearly";

  if (drawerBackdrop && drawerBackdrop.parentElement !== document.body) {
    document.body.appendChild(drawerBackdrop);
  }
  if (drawerEl && drawerEl.parentElement !== document.body) {
    document.body.appendChild(drawerEl);
  }

  function closeKpiDrawer() {
    if (!drawerEl) {
      return;
    }
    drawerEl.classList.remove("is-open");
    drawerEl.setAttribute("aria-hidden", "true");
    if (drawerBackdrop) {
      drawerBackdrop.hidden = true;
    }
    document.documentElement.classList.remove("goal-kpi-lock");
    document.body.classList.remove("goal-kpi-lock");
    if (currentDrawerChart) {
      currentDrawerChart.destroy();
      currentDrawerChart = null;
    }
  }

  function openKpiDrawerShell() {
    if (!drawerEl) {
      return;
    }
    drawerEl.classList.add("is-open");
    drawerEl.setAttribute("aria-hidden", "false");
    if (drawerBackdrop) {
      drawerBackdrop.hidden = false;
    }
    document.documentElement.classList.add("goal-kpi-lock");
    document.body.classList.add("goal-kpi-lock");
  }

  const filter = await createDpmesPeriodFilter(root, {
    initialState: {
      year: query.get("year") || "2017",
      quarter: query.get("quarter") || "3month",
      dateType: query.get("quarter") ? "quarterly" : "yearly",
    },
    onChange: async (_state, _reason, api) => {
      const nextParams = new URLSearchParams(api.getQueryString());
      if (selectedOrganizationId && Number(selectedOrganizationId) !== Number(ministryId)) {
        nextParams.set("org_id", selectedOrganizationId);
      }
      if (selectedOrganizationId === String(ministryId)) {
        nextParams.set("solo", "true");
      } else {
        nextParams.delete("solo");
      }
      const nextQuery = nextParams.toString();
      window.history.replaceState({}, "", `${window.location.pathname}?${nextQuery}`);
      currentPeriod.textContent = renderCurrentPeriod(api.getState());
      await renderDetail(api.getState());
    },
  });

  async function loadAffiliatedOrganizations(state) {
    const params = new URLSearchParams({
      format: "json",
      ministry_id: ministryId,
      year: state.year,
      solo: "false",
    });
    if (state.dateType === "quarterly") {
      params.set("quarter", state.quarter);
    }

    const payload = await fetchJson(`/api/mobile/affiliated-ministries/?${params.toString()}`);
    affiliatedItems = Array.isArray(payload) ? payload : (Array.isArray(payload?.data) ? payload.data : []);

    if (
      selectedOrganizationId !== "all" &&
      !affiliatedItems.some((item) => Number(item.id) === Number(selectedOrganizationId))
    ) {
      selectedOrganizationId = "all";
    }

    renderAffiliatedOptions(affiliatedSelect, affiliatedItems, selectedOrganizationId);
  }

  async function fetchSelectedOrganizationOverview(state) {
    if (selectedOrganizationId === "all") {
      const localParent = affiliatedItems.find((item) => Number(item.id) === Number(ministryId));
      if (localParent) {
        return localParent;
      }

      const params = new URLSearchParams({
        format: "json",
        ministry_id: ministryId,
        year: state.year,
        solo: "false",
      });
      if (state.dateType === "quarterly") {
        params.set("quarter", state.quarter);
      }

      const payload = await fetchJson(`/api/mobile/affiliated-ministries/?${params.toString()}`);
      const rows = Array.isArray(payload) ? payload : (Array.isArray(payload?.data) ? payload.data : []);
      return rows.find((item) => Number(item.id) === Number(ministryId)) || rows[0] || {};
    }

    const params = new URLSearchParams({
      format: "json",
      ministry_id: selectedOrganizationId,
      year: state.year,
    });
    if (Number(selectedOrganizationId) === Number(ministryId)) {
      params.set("solo", "true");
    }
    if (state.dateType === "quarterly") {
      params.set("quarter", state.quarter);
    }

    const payload = await fetchJson(`/api/mobile/affiliated-ministries/?${params.toString()}`);
    const rows = Array.isArray(payload) ? payload : (Array.isArray(payload?.data) ? payload.data : []);
    return rows[0] || {};
  }

  async function renderDetail(state) {
    try {
      renderLoading(hero, body);
      await loadAffiliatedOrganizations(state);
      const targetOrganizationId = selectedOrganizationId === "all" ? ministryId : selectedOrganizationId;
      const params = new URLSearchParams({ year: state.year, format: "json" });
      if (state.dateType === "quarterly") {
        params.set("quarter", state.quarter);
      }
      const performanceParams = new URLSearchParams({
        year: state.year,
        ...(state.dateType === "quarterly" ? { quarter: state.quarter } : {}),
      });
      if (Number(targetOrganizationId) === Number(ministryId) && selectedOrganizationId !== "all") {
        performanceParams.set("solo", "true");
      }

      const [selectedOverview, detailPayload, performancePayload] = await Promise.all([
        fetchSelectedOrganizationOverview(state),
        fetchJson(`/api/mobile/ministry-detail/${targetOrganizationId}/?${params.toString()}`),
        fetchJson(`/api/mobile/ministry-performance/${targetOrganizationId}/?${performanceParams.toString()}`),
      ]);

      const detailItems = Array.isArray(detailPayload?.data) ? detailPayload.data : [];
      const performanceDetail = performancePayload && typeof performancePayload === "object" ? performancePayload : {};

      hero.innerHTML = renderHero(selectedOverview, detailItems, state);
      body.innerHTML = detailItems.length
        ? `<div class="public-body-detail-layout">
            ${renderPerformanceSummary(performanceDetail, selectedBucket)}
            ${selectedBucket ? renderBucketSection(performanceDetail, selectedBucket) : detailItems.map((item) => renderPolicyAreaSection(item, state, selectedOrganizationId)).join("")}
          </div>`
        : `<div class="public-body-detail-state">No ministry detail is available for the selected period.</div>`;

      body.querySelectorAll("[data-performance-bucket]").forEach((button) => {
        button.addEventListener("click", async () => {
          const nextBucket = button.dataset.performanceBucket || "";
          selectedBucket = selectedBucket === nextBucket ? "" : nextBucket;
          await renderDetail(state);
        });
      });

      const clearButton = body.querySelector("[data-clear-performance-filter]");
      if (clearButton) {
        clearButton.addEventListener("click", async () => {
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
      renderState(hero, "Unable to load public body detail right now.");
      renderState(body, "The ministry detail API did not return a usable payload.");
    }
  }

  async function openKpiDrawer(indicatorId) {
    if (!drawerEl || !drawerContent || !drawerTitle || !indicatorId) {
      return;
    }

    drawerTitle.textContent = "Indicator Detail";
    renderKpiDrawerLoading(drawerContent);
    openKpiDrawerShell();

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

  drawerClose?.addEventListener("click", closeKpiDrawer);
  drawerBackdrop?.addEventListener("click", closeKpiDrawer);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeKpiDrawer();
    }
  });

  currentPeriod.textContent = renderCurrentPeriod(filter.getState());
  affiliatedSelect?.addEventListener("change", async () => {
    selectedOrganizationId = affiliatedSelect.value || "all";
    selectedBucket = "";
    const nextParams = new URLSearchParams(window.location.search);
    if (selectedOrganizationId !== "all") {
      nextParams.set("org_id", selectedOrganizationId);
    } else {
      nextParams.delete("org_id");
    }
    if (selectedOrganizationId === String(ministryId)) {
      nextParams.set("solo", "true");
    } else {
      nextParams.delete("solo");
    }
    window.history.replaceState({}, "", `${window.location.pathname}?${nextParams.toString()}`);
    await renderDetail(filter.getState());
  });
  renderLoading(hero, body);
  await renderDetail(filter.getState());
}

loadPublicBodyDetail();
