const mediaBaseUrl = "https://time-series.mopd.gov.et/";

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

function renderState(container, message) {
  container.innerHTML = `<div class="data-topic-detail-state">${escapeHtml(message)}</div>`;
}

function hasChildKpis(kpi) {
  return Array.isArray(kpi?.children) && kpi.children.length > 0;
}

function renderSubIndicatorSection(kpi, level) {
  if (!hasChildKpis(kpi)) {
    return "";
  }

  const count = kpi.children.length;
  return `
    <div class="data-topic-kpi-children-shell">
      <button
        type="button"
        class="data-topic-kpi-children-trigger"
        data-kpi-children-trigger
        aria-expanded="false"
      >
        <span class="data-topic-kpi-children-label">Sub indicators</span>
        <span class="data-topic-kpi-children-count">${escapeHtml(`${count} item${count === 1 ? "" : "s"}`)}</span>
        <span class="data-topic-kpi-children-icon">
          <i class="ti ti-chevron-down"></i>
        </span>
      </button>
      <div class="data-topic-kpi-children-panel" data-kpi-children-panel hidden>
        ${renderKpiList(kpi.children, level + 1)}
      </div>
    </div>
  `;
}

function renderKpiCard(kpi, level = 0) {
  return `
    <article
      class="data-topic-kpi data-topic-kpi-level-${Math.min(level, 3)}"
      data-kpi-card
      data-kpi-url="/dashboard/data/indicator/${escapeHtml(kpi.id)}/"
      tabindex="0"
      role="link"
      aria-label="Open ${escapeHtml(kpi.title_ENG || kpi.title_AMH || "KPI")} indicator detail"
    >
      <div class="data-topic-kpi-head">
        <div class="data-topic-kpi-copy">
          <h4>${escapeHtml(kpi.title_ENG || kpi.title_AMH || "KPI")}</h4>
          <div class="data-topic-kpi-meta">
            <span>${escapeHtml(kpi.frequency || "No frequency")}</span>
            <span>${escapeHtml(kpi.measurement_units || "-")}</span>
            <span>${escapeHtml(kpi.code || "No code")}</span>
          </div>
        </div>
        <a class="data-topic-kpi-open" href="/dashboard/data/indicator/${escapeHtml(kpi.id)}/" aria-label="Open indicator detail">
          <i class="ti ti-chevron-right"></i>
        </a>
      </div>
      ${renderKpiValuePanel(kpi)}
      ${renderSubIndicatorSection(kpi, level)}
    </article>
  `;
}

function renderKpiList(kpis, level = 0) {
  if (!Array.isArray(kpis) || !kpis.length) {
    return '<div class="data-topic-kpi-empty">No KPIs available for this category yet.</div>';
  }

  return `
    <div class="data-topic-kpis data-topic-kpis-level-${Math.min(level, 3)}">
      ${kpis.map((kpi) => renderKpiCard(kpi, level)).join("")}
    </div>
  `;
}

function getKpiSeries(kpi) {
  const latestData = String(kpi?.latest_data || kpi?.frequency || "").toLowerCase();
  const seriesMap = {
    annual: kpi.annual_data || [],
    yearly: kpi.annual_data || [],
    quarter: kpi.quarter_data || [],
    quarterly: kpi.quarter_data || [],
    month: kpi.month_data || [],
    monthly: kpi.month_data || [],
    week: kpi.week_data || [],
    weekly: kpi.week_data || [],
    day: kpi.day_data || [],
    daily: kpi.day_data || [],
  };

  return {
    latestData,
    points: Array.isArray(seriesMap[latestData]) ? seriesMap[latestData] : [],
  };
}

function getPointLabel(point, latestData) {
  if (latestData === "quarter" || latestData === "quarterly") {
    return `${point.for_datapoint || ""} ${point.for_quarter || ""}`.trim();
  }
  if (latestData === "month" || latestData === "monthly") {
    return `${point.for_datapoint || ""} ${point.for_month || ""}`.trim() || point.for_month || "Period";
  }
  return String(point.for_datapoint || point.for_month || point.for_quarter || "Period");
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

function renderKpiValuePanel(kpi) {
  const { latestData, points } = getKpiSeries(kpi);
  const usablePoints = points.filter((point) => point && point.performance !== null && point.performance !== undefined);

  if (!usablePoints.length) {
    return `
      <div class="data-topic-kpi-value-card">
        <div class="data-topic-kpi-value-empty">No historical values available.</div>
      </div>
    `;
  }

  const selected = usablePoints[usablePoints.length - 1];
  const visibleHistory = usablePoints.slice(-6).reverse();
  const unit =
    kpi[`measurement_units_${latestData}`] ||
    kpi.measurement_units ||
    "";

  return `
    <div class="data-topic-kpi-value-card" data-kpi-value-card>
      <div class="data-topic-kpi-selected">
        <span class="data-topic-kpi-period" data-kpi-selected-period>${escapeHtml(getPointLabel(selected, latestData))}</span>
        <div class="data-topic-kpi-metric">
          <strong data-kpi-selected-value>${escapeHtml(formatMetricValue(selected.performance))}</strong>
          <span class="data-topic-kpi-unit">${escapeHtml(unit || "-")}</span>
        </div>
      </div>
      <div class="data-topic-kpi-history-label">Historical Trend</div>
      <div class="data-topic-kpi-history">
        ${visibleHistory
          .map(
            (point, index) => `
              <button
                type="button"
                class="data-topic-kpi-history-item${index === 0 ? " is-active" : ""}"
                data-kpi-history-item
                data-period="${escapeHtml(getPointLabel(point, latestData))}"
                data-value="${escapeHtml(formatMetricValue(point.performance))}"
              >
                <span>${escapeHtml(getPointLabel(point, latestData))}</span>
                <strong>${escapeHtml(formatMetricValue(point.performance))}</strong>
              </button>
            `
          )
          .join("")}
      </div>
    </div>
  `;
}

function renderCategoryAccordion(categories) {
  if (!Array.isArray(categories) || !categories.length) {
    return '<div class="data-topic-detail-empty">No categories are available for this topic yet.</div>';
  }

  return `
    <div class="data-topic-categories">
      ${categories
        .map(
          (category) => `
            <article class="data-topic-category" data-category-item data-category-id="${escapeHtml(category.id)}">
              <button type="button" class="data-topic-category-trigger" data-category-trigger aria-expanded="false">
                <span class="data-topic-category-icon">
                  <i class="ti ti-layout-grid"></i>
                </span>
                <div class="data-topic-category-copy">
                  <h3>${escapeHtml(category.name_ENG || category.name_AMH || "Category")}</h3>
                  <p>${escapeHtml(category.code || "No code")}</p>
                </div>
                <span class="data-topic-category-count">View KPIs</span>
                <span class="data-topic-category-toggle">
                  <i class="ti ti-chevron-down"></i>
                </span>
              </button>
              <div class="data-topic-category-panel" data-category-panel hidden>
                <div class="data-topic-category-loading" hidden>Loading KPIs...</div>
                <div data-category-content></div>
              </div>
            </article>
          `
        )
        .join("")}
    </div>
  `;
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

function bindCategoryAccordions(container) {
  const items = Array.from(container.querySelectorAll("[data-category-item]"));

  items.forEach((item) => {
    const categoryId = item.dataset.categoryId;
    const trigger = item.querySelector("[data-category-trigger]");
    const panel = item.querySelector("[data-category-panel]");
    const loading = item.querySelector(".data-topic-category-loading");
    const content = item.querySelector("[data-category-content]");
    let loaded = false;

    trigger.addEventListener("click", async () => {
      const expanded = trigger.getAttribute("aria-expanded") === "true";
      trigger.setAttribute("aria-expanded", expanded ? "false" : "true");
      item.classList.toggle("is-open", !expanded);
      panel.hidden = expanded;

      if (expanded || loaded) {
        return;
      }

      loading.hidden = false;
      try {
        const payload = await fetchJson(`/api/mobile/kpis/${categoryId}/`);
        const kpis = Array.isArray(payload?.data) ? payload.data : [];
        content.innerHTML = renderKpiList(kpis);
        bindKpiHistory(content);
        bindKpiChildren(content);
        bindKpiCards(content);
        loaded = true;
      } catch (_error) {
        content.innerHTML = '<div class="data-topic-kpi-empty">Unable to load KPIs for this category right now.</div>';
      } finally {
        loading.hidden = true;
      }
    });
  });
}

function bindKpiHistory(container) {
  const cards = Array.from(container.querySelectorAll("[data-kpi-value-card]"));

  cards.forEach((card) => {
    const periodTarget = card.querySelector("[data-kpi-selected-period]");
    const valueTarget = card.querySelector("[data-kpi-selected-value]");
    const items = Array.from(card.querySelectorAll("[data-kpi-history-item]"));

    items.forEach((item) => {
      item.addEventListener("click", () => {
        items.forEach((entry) => entry.classList.remove("is-active"));
        item.classList.add("is-active");
        periodTarget.textContent = item.dataset.period || "Period";
        valueTarget.textContent = item.dataset.value || "--";
      });
    });
  });
}

function bindKpiChildren(container) {
  const triggers = Array.from(container.querySelectorAll("[data-kpi-children-trigger]"));

  triggers.forEach((trigger) => {
    trigger.addEventListener("click", () => {
      const expanded = trigger.getAttribute("aria-expanded") === "true";
      const shell = trigger.closest(".data-topic-kpi-children-shell");
      const panel = shell?.querySelector("[data-kpi-children-panel]");

      trigger.setAttribute("aria-expanded", expanded ? "false" : "true");
      shell?.classList.toggle("is-open", !expanded);
      if (panel) {
        panel.hidden = expanded;
      }
    });
  });
}

function bindKpiCards(container) {
  const cards = Array.from(container.querySelectorAll("[data-kpi-card]"));

  cards.forEach((card) => {
    const openUrl = card.dataset.kpiUrl;
    if (!openUrl) {
      return;
    }

    card.addEventListener("click", (event) => {
      if (event.target.closest("a, button, [data-kpi-children-trigger], [data-kpi-history-item]")) {
        return;
      }
      window.location.href = openUrl;
    });

    card.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") {
        return;
      }
      if (event.target.closest("a, button")) {
        return;
      }
      event.preventDefault();
      window.location.href = openUrl;
    });
  });
}

async function loadTopicDetail() {
  const root = document.querySelector("[data-topic-detail]");
  if (!root) {
    return;
  }

  const topicId = root.dataset.topicId;
  const hero = root.querySelector("[data-topic-detail-hero]");
  const body = root.querySelector("[data-topic-detail-body]");

  try {
    const [topicListPayload, categoriesPayload] = await Promise.all([
      fetchJson("/api/mobile/topic-list/"),
      fetchJson(`/api/mobile/categories/${topicId}/`),
    ]);

    const topics = Array.isArray(topicListPayload?.data) ? topicListPayload.data : [];
    const topic = topics.find((item) => Number(item.id) === Number(topicId)) || {};
    const categories = Array.isArray(categoriesPayload?.data) ? categoriesPayload.data : [];
    const title = topic.title_ENG || topic.title_AMH || `Topic ${topicId}`;
    const description = topic.description || "Explore topic categories and open each category to inspect KPI details.";
    const image = buildMediaUrl(topic.background_image || topic.image);
    const icon = buildMediaUrl(topic.image_icons);

    hero.innerHTML = `
      <div class="data-topic-hero-card">
        ${
          image
            ? `<img class="data-topic-hero-media" src="${escapeHtml(image)}" alt="${escapeHtml(title)}" loading="lazy">`
            : `<div class="data-topic-hero-fallback" aria-hidden="true"></div>`
        }
        <div class="data-topic-hero-overlay"></div>
        <div class="data-topic-hero-shell">
          <div class="data-topic-hero-topline">
            <span class="data-topic-hero-badge">Topic Detail</span>
            <a class="data-topic-back" href="/dashboard/data/"><i class="ti ti-arrow-left"></i><span>Back to topics</span></a>
          </div>
          <div class="data-topic-hero-copy">
            <span class="data-topic-hero-icon">
              ${icon ? `<img src="${escapeHtml(icon)}" alt="${escapeHtml(title)} icon" loading="lazy">` : `<i class="ti ti-database"></i>`}
            </span>
            <h1>${escapeHtml(title)}</h1>
            <p>${escapeHtml(description)}</p>
            <div class="data-topic-hero-meta">
              <span>${escapeHtml(`${Number(topic.count_category || categories.length || 0)} categories`)}</span>
              <span>${escapeHtml(`${Number(topic.count_kpis || 0)} KPIs`)}</span>
            </div>
          </div>
        </div>
      </div>
    `;

    body.innerHTML = `
      <section class="data-topic-detail-section">
        <div class="data-topic-detail-head">
          <h2>Categories</h2>
          <p>Open a category to load and inspect its KPI list.</p>
        </div>
        ${renderCategoryAccordion(categories)}
      </section>
    `;

    bindCategoryAccordions(body);
  } catch (_error) {
    renderState(hero, "Unable to load topic detail right now.");
    renderState(body, "The categories endpoint did not return a usable payload.");
  }
}

loadTopicDetail();
