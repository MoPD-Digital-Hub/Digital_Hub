const DEFAULT_OPTIONS = {
  endpoint: "/api/mobile/topic-list/",
  mediaBaseUrl: "https://time-series.mopd.gov.et/",
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function buildMediaUrl(path, baseUrl) {
  if (!path) {
    return "";
  }
  try {
    return new URL(path, baseUrl).toString();
  } catch (_error) {
    return path;
  }
}

function truncate(value, maxLength = 140) {
  const text = String(value ?? "").trim();
  if (!text) {
    return "";
  }
  return text.length > maxLength ? `${text.slice(0, maxLength).trim()}...` : text;
}

function createTopicCard(topic, mediaBaseUrl) {
  const title = topic.title_ENG || topic.title_AMH || "Topic";
  const description = truncate(topic.description || "Explore indicators, categories, and topic-specific data assets.");
  const image = buildMediaUrl(topic.background_image || topic.image, mediaBaseUrl);
  const icon = buildMediaUrl(topic.image_icons, mediaBaseUrl);
  const href = `/dashboard/data/${topic.id}/`;

  return `
    <a class="data-topic-card" href="${escapeHtml(href)}">
      ${
        image
          ? `<img class="data-topic-card-media" src="${escapeHtml(image)}" alt="${escapeHtml(title)}" loading="lazy">`
          : `<div class="data-topic-card-fallback" aria-hidden="true"></div>`
      }
      <div class="data-topic-card-overlay"></div>
      <div class="data-topic-card-shell">
        <div class="data-topic-card-topline">
          <span class="data-topic-card-badge">Data Topic</span>
          <span class="data-topic-card-open"><i class="ti ti-arrow-up-right"></i></span>
        </div>
        <div class="data-topic-card-body">
          <span class="data-topic-card-icon">
            ${
              icon
                ? `<img src="${escapeHtml(icon)}" alt="${escapeHtml(title)} icon" loading="lazy">`
                : `<i class="ti ti-database"></i>`
            }
          </span>
          <div class="data-topic-card-copy">
            <h3>${escapeHtml(title)}</h3>
            <p>${escapeHtml(description)}</p>
          </div>
          <div class="data-topic-card-meta">
            <span>${escapeHtml(`${Number(topic.count_category || 0)} categories`)}</span>
            <span>${escapeHtml(`${Number(topic.count_kpis || 0)} KPIs`)}</span>
          </div>
        </div>
      </div>
    </a>
  `;
}

function renderLoading(grid) {
  grid.innerHTML = Array.from({ length: 8 }, () => '<div class="data-topic-card data-topic-card-skeleton"></div>').join("");
}

function renderState(grid, message) {
  grid.innerHTML = `<div class="data-topic-state">${escapeHtml(message)}</div>`;
}

async function mountDataTopicBrowser(element, options = {}) {
  if (!element) {
    return null;
  }

  const settings = {
    ...DEFAULT_OPTIONS,
    ...options,
    endpoint: element.dataset.endpoint || options.endpoint || DEFAULT_OPTIONS.endpoint,
    mediaBaseUrl: element.dataset.mediaBaseUrl || options.mediaBaseUrl || DEFAULT_OPTIONS.mediaBaseUrl,
  };

  const grid = element.querySelector("[data-topic-browser-grid]");
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
    const topics = Array.isArray(payload?.data) ? payload.data : [];

    if (!topics.length) {
      renderState(grid, "No data topics are available right now.");
      return null;
    }

    grid.innerHTML = topics
      .sort((left, right) => Number(left.rank || 999) - Number(right.rank || 999))
      .map((topic) => createTopicCard(topic, settings.mediaBaseUrl))
      .join("");
  } catch (_error) {
    renderState(grid, "Unable to load data topics right now.");
  }

  return null;
}

export const DataTopicBrowser = {
  init(elementOrSelector, options = {}) {
    const element =
      typeof elementOrSelector === "string"
        ? document.querySelector(elementOrSelector)
        : elementOrSelector;
    return mountDataTopicBrowser(element, options);
  },
};

window.DataTopicBrowser = DataTopicBrowser;
