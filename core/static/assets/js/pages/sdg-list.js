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

const SDG_CACHE_TTL_MS = 60 * 60 * 1000;
const SDG_CACHE_PREFIX = "sdg-list-cache:";

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
    console.warn("Unable to read SDG list cache", error);
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
    console.warn("Unable to write SDG list cache", error);
  }

  return data;
}

function renderGoalItem(goal, detailBase, active = false) {
  const goalId = Number(goal?.id || 0);
  const color = getGoalColor(goalId);
  const label = `Goal ${goalId}`;
  return `
    <a class="sdg-goal-item${active ? " is-active" : ""}" href="${escapeHtml(`${detailBase}${goalId}/`)}" style="--goal-color:${escapeHtml(color)};">
      <span class="sdg-goal-item__icon">
        <img src="${escapeHtml(getGoalIconUrl(goalId))}" alt="${escapeHtml(label)} icon" loading="lazy" decoding="async">
      </span>
      <span class="sdg-goal-item__copy">
        <em>${escapeHtml(label)}</em>
        <strong>${escapeHtml(goal?.goal || "SDG goal")}</strong>
        <span>${escapeHtml(goal?.description || "Goal detail is not available.")}</span>
      </span>
    </a>
  `;
}

function renderGoalCard(goal, detailBase) {
  const goalId = Number(goal?.id || 0);
  const color = getGoalColor(goalId);
  const iconUrl = getGoalIconUrl(goalId);
  return `
    <a class="sdg-goal-card" href="${escapeHtml(`${detailBase}${goalId}/`)}" style="--goal-color:${escapeHtml(color)};">
      <span class="sdg-goal-card__media">
        <img src="${escapeHtml(iconUrl)}" alt="${escapeHtml(goal?.goal || `Goal ${goalId}`)} graphic" loading="lazy" decoding="async">
      </span>
      <div class="sdg-goal-card__footer">
        <span>Open</span>
        <i class="ti ti-arrow-up-right"></i>
      </div>
    </a>
  `;
}

function renderPage(payload, detailBase) {
  const goals = Array.isArray(payload?.goals) ? payload.goals : [];
  return `
    <section class="sdg-hero">
      <div class="sdg-hero__band" aria-hidden="true">
        ${goals.map((goal) => `<span style="--goal-color:${escapeHtml(getGoalColor(goal?.id))};"></span>`).join("")}
      </div>
      <div class="sdg-hero__layout">
        <div class="sdg-hero__copy">
          <span class="sdg-hero__eyebrow">
            <i class="ti ti-world"></i>
            SDG Framework
          </span>
          <h1>Sustainable Development Goals</h1>
          <p>
            Explore all 17 SDGs for ${escapeHtml(payload?.countryName || "Ethiopia")}, then open a goal to review its target structure,
            indicator evidence, and the latest data points carried on the national SDG platform.
          </p>
        </div>
        <aside class="sdg-hero__panel">
          <h2>Framework Snapshot</h2>
          <div class="sdg-hero__metrics">
            <article class="sdg-hero__metric">
              <span>Total goals</span>
              <strong>${goals.length}</strong>
            </article>
            <article class="sdg-hero__metric">
              <span>Detail views</span>
              <strong>17</strong>
            </article>
            <article class="sdg-hero__metric">
              <span>Country</span>
              <strong>${escapeHtml(payload?.countryName || "Ethiopia")}</strong>
            </article>
            <article class="sdg-hero__metric">
              <span>Source</span>
              <strong>MOPD SDG</strong>
            </article>
          </div>
        </aside>
      </div>
    </section>
    <section class="sdg-grid-panel">
      <div class="sdg-grid-panel__head">
        <h2>All Goals</h2>
        <p>Open any SDG goal to review its targets, indicators, and latest evidence in the goal workspace.</p>
      </div>
      <div class="sdg-card-grid">
        ${goals.map((goal) => renderGoalCard(goal, detailBase)).join("")}
      </div>
    </section>
  `;
}

async function loadSdgList() {
  const page = document.querySelector("[data-sdg-list-page]");
  if (!page) {
    return;
  }

  const endpoint = page.dataset.endpoint;
  const detailBase = page.dataset.detailBase || "/dashboard/frameworks/sdgs/";
  const state = page.querySelector("[data-sdg-list-state]");
  const content = page.querySelector("[data-sdg-list-content]");

  try {
    const payload = await fetchJson(endpoint);
    content.innerHTML = renderPage(payload, detailBase);
    content.hidden = false;
    if (state) {
      state.hidden = true;
    }
  } catch (error) {
    if (state) {
      state.textContent = "Unable to load the SDG catalog right now.";
    }
    console.error(error);
  }
}

document.addEventListener("DOMContentLoaded", loadSdgList);
