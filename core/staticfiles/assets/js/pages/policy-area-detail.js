import { createDpmesPeriodFilter } from "../components/dpmes-period-filter.js";

const mediaBaseUrl = "https://time-series.mopd.gov.et/";

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
    return new URL(path, mediaBaseUrl).toString();
  } catch (_error) {
    return path;
  }
}

function renderState(container, message) {
  container.innerHTML = `<div class="policy-area-detail-state">${escapeHtml(message)}</div>`;
}

function renderLoadingBlock() {
  return `
    <div class="policy-area-loading">
      <div class="policy-area-loading__line policy-area-loading__line--lg"></div>
      <div class="policy-area-loading__line policy-area-loading__line--md"></div>
      <div class="policy-area-loading__line policy-area-loading__line--sm"></div>
    </div>
  `;
}

function renderLoading(hero, body) {
  hero.innerHTML = `
    <section class="policy-area-detail-hero policy-area-detail-hero--loading">
      <div class="policy-area-detail-hero-shell">
        ${renderLoadingBlock()}
      </div>
    </section>
  `;
  body.innerHTML = `
    <div class="policy-area-detail-layout">
      <div class="policy-area-detail-main-column">
        <section class="policy-area-detail-panel">${renderLoadingBlock()}</section>
        <section class="policy-area-detail-panel">${renderLoadingBlock()}${renderLoadingBlock()}</section>
      </div>
    </div>
  `;
}

function normalizeOverviewItem(item) {
  return item && typeof item === "object" ? item : {};
}

function normalizeDetailItem(payload) {
  return payload?.data && typeof payload.data === "object" ? payload.data : {};
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

function renderHero(overview, detail, state) {
  const title =
    overview.policyAreaEng ||
    overview.policyAreaAmh ||
    detail.policyAreaEng ||
    detail.policyAreaAmh ||
    "Policy Area";
  const scoreCard = overview?.policy_area_score_card || detail?.policy_area_score_card || {};
  const scoreColor = scoreCard.scorecard_color || "#5d9444";
  const bgImage = buildMediaUrl(overview.bg_image || detail.bg_image || "");
  const scoreValue = Number(scoreCard.avg_score);
  const score = scoreCard.avg_score != null ? `${Number(scoreCard.avg_score).toFixed(2)}%` : "--";
  const progressWidth = Number.isFinite(scoreValue)
    ? Math.max(0, Math.min(scoreValue, 100))
    : 0;

  return `
    <section class="policy-area-detail-hero" style="--policy-area-bg:url('${escapeHtml(bgImage)}'); --policy-area-accent:${escapeHtml(scoreColor)}">
      <div class="policy-area-detail-hero-shell">
        <div class="policy-area-detail-top">
          <a class="policy-area-detail-back" href="/dashboard/statistics/policy-areas/?${escapeHtml(new URLSearchParams({
            year: state.year,
            ...(state.dateType === "quarterly" ? { quarter: state.quarter } : {}),
          }).toString())}">
            <i class="ti ti-arrow-left"></i><span>Back to policy areas</span>
          </a>
        </div>
        <div class="policy-area-detail-main">
          <span class="policy-area-detail-kicker">Policy Area Dashboard</span>
          <h1>${escapeHtml(title)}</h1>
          <div class="policy-area-detail-meta">
            <div class="policy-area-detail-progress">
              <div class="policy-area-detail-progress__top">
                <span>Area score</span>
                <strong>${escapeHtml(score)}</strong>
              </div>
              <div class="policy-area-detail-progress__track">
                <span class="policy-area-detail-progress__fill" style="width:${escapeHtml(progressWidth)}%; background:${escapeHtml(scoreColor)}"></span>
              </div>
            </div>
            <span>${escapeHtml(renderCurrentPeriod(state))}</span>
          </div>
        </div>
      </div>
    </section>
  `;
}

function renderGoalCard(goal, state) {
  const goalScore = goal?.goal_score_card?.avg_score;
  const scoreColor = goal?.goal_score_card?.scorecard_color || "#5d9444";
  const ministry = goal?.responsible_ministries || {};
  const image = buildMediaUrl(ministry.image || "");
  const params = new URLSearchParams({ year: state.year });
  if (state.dateType === "quarterly") {
    params.set("quarter", state.quarter);
  }

  return `
    <a class="policy-area-goal-card" href="/dashboard/statistics/goals/${escapeHtml(goal.id)}/?${escapeHtml(params.toString())}" style="--goal-accent:${escapeHtml(scoreColor)}">
      <div class="policy-area-goal-card__accent"></div>
      <div class="policy-area-goal-card__head">
        <div class="policy-area-goal-card__ministry">
          ${
            image
              ? `<img src="${escapeHtml(image)}" alt="${escapeHtml(ministry.responsible_ministry_eng || "Ministry")}" loading="lazy">`
              : `<span class="policy-area-goal-card__placeholder">${escapeHtml(ministry.code || "MO")}</span>`
          }
          <div>
            <span class="policy-area-goal-card__code">${escapeHtml(ministry.code || "Ministry")}</span>
            <p>${escapeHtml(ministry.responsible_ministry_eng || "Responsible ministry unavailable")}</p>
          </div>
        </div>
        <div class="policy-area-goal-card__score">${escapeHtml(goalScore != null ? `${Number(goalScore).toFixed(2)}%` : "--")}</div>
      </div>
      <div class="policy-area-goal-card__body">
        <div class="policy-area-goal-card__eyebrow">
          <span>${escapeHtml(goal.goal_is_shared ? "Shared goal" : "Single ministry goal")}</span>
        </div>
        <h3>${escapeHtml(goal.goal_name_eng || goal.goal_name_amh || "Goal")}</h3>
      </div>
      <div class="policy-area-goal-card__footer">
        <span>Goal dashboard</span>
        <strong>Open goal</strong>
      </div>
    </a>
  `;
}

function renderGoalsSection(detail, state) {
  const goals = Array.isArray(detail.policy_area_goal) ? detail.policy_area_goal : [];
  return `
    <section class="policy-area-detail-panel policy-area-detail-panel--full">
      <div class="policy-area-detail-sectionhead">
        <div>
          <h2>Goals</h2>
          <p>Each goal is clickable and opens its own goal detail view with the current filter state.</p>
        </div>
      </div>
      <div class="policy-area-goals-grid">
        ${
          goals.length
            ? goals.map((goal) => renderGoalCard(goal, state)).join("")
            : `<div class="policy-area-detail-list"><p>No goals are available for the selected period.</p></div>`
        }
      </div>
    </section>
  `;
}

async function loadPolicyAreaDetail() {
  const root = document.querySelector("[data-policy-area-detail]");
  if (!root) {
    return;
  }

  const policyAreaId = root.dataset.policyAreaId;
  const hero = root.querySelector("[data-policy-area-hero]");
  const body = root.querySelector("[data-policy-area-body]");
  const currentPeriod = root.querySelector("[data-policy-area-current-period]");
  const query = new URLSearchParams(window.location.search);

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

      const [overviewPayload, detailPayload] = await Promise.all([
        fetchJson(`/api/mobile/policy-areas/?${params.toString()}`),
        fetchJson(`/api/mobile/policy-area-detail/${policyAreaId}/?${params.toString()}`),
      ]);

      const overviewItems = Array.isArray(overviewPayload?.data) ? overviewPayload.data : [];
      const overview = normalizeOverviewItem(
        overviewItems.find((item) => Number(item.id) === Number(policyAreaId))
      );
      const detail = normalizeDetailItem(detailPayload);

      hero.innerHTML = renderHero(overview, detail, state);
      body.innerHTML = `
        <div class="policy-area-detail-layout">
          <div class="policy-area-detail-main-column">
            ${renderGoalsSection(detail, state)}
          </div>
        </div>
      `;
    } catch (_error) {
      renderState(hero, "Unable to load policy area detail right now.");
      renderState(body, "The policy area API did not return a usable payload.");
    }
  }

  currentPeriod.textContent = renderCurrentPeriod(filter.getState());
  renderLoading(hero, body);
  await renderDetail(filter.getState());
}

loadPolicyAreaDetail();
