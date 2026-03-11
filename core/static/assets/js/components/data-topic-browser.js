export const DEFAULT_OPTIONS = {
  endpoint: "/api/mobile/topic-list/",
  mediaBaseUrl: "https://time-series.mopd.gov.et/",
};

const TOPIC_DOWNLOAD_OPTIONS = [
  { key: "annual", label: "Annual" },
  { key: "quarter", label: "Quarter" },
  { key: "month", label: "Month" },
];

export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function buildMediaUrl(path, baseUrl) {
  if (!path) {
    return "";
  }
  try {
    return new URL(path, baseUrl).toString();
  } catch (_error) {
    return path;
  }
}

export function truncate(value, maxLength = 140) {
  const text = String(value ?? "").trim();
  if (!text) {
    return "";
  }
  return text.length > maxLength ? `${text.slice(0, maxLength).trim()}...` : text;
}

export function createTopicCard(topic, mediaBaseUrl) {
  const title = topic.title_ENG || topic.title_AMH || "Topic";
  const description = truncate(topic.description || "Explore indicators, categories, and topic-specific data assets.");
  const image = buildMediaUrl(topic.background_image || topic.image, mediaBaseUrl);
  const icon = buildMediaUrl(topic.image_icons, mediaBaseUrl);
  const href = `/dashboard/data/${topic.id}/`;
  const downloadMenu = TOPIC_DOWNLOAD_OPTIONS.map(
    (option) => `
      <button
        type="button"
        class="data-topic-card-download-option"
        data-topic-download-option
        data-download-type="${escapeHtml(option.key)}"
      >
        <span>${escapeHtml(option.label)}</span>
        <i class="ti ti-file-spreadsheet"></i>
      </button>
    `
  ).join("");

  return `
    <article class="data-topic-card" data-topic-id="${escapeHtml(topic.id)}" data-topic-title="${escapeHtml(title)}">
      ${
        image
          ? `<img class="data-topic-card-media" src="${escapeHtml(image)}" alt="${escapeHtml(title)}" loading="lazy" decoding="async" fetchpriority="low" sizes="(max-width: 767px) 100vw, 25vw">`
          : `<div class="data-topic-card-fallback" aria-hidden="true"></div>`
      }
      <div class="data-topic-card-overlay"></div>
      <a class="data-topic-card-link" href="${escapeHtml(href)}" aria-label="Open ${escapeHtml(title)} topic"></a>
      <div class="data-topic-card-shell">
        <div class="data-topic-card-topline">
          <span class="data-topic-card-badge">Data Topic</span>
          <div class="data-topic-card-actions">
            <div class="data-topic-card-download-shell">
              <button
                type="button"
                class="data-topic-card-download"
                data-topic-download-trigger
                aria-haspopup="true"
                aria-expanded="false"
                aria-label="Download topic data"
              >
                <i class="ti ti-file-spreadsheet"></i>
              </button>
              <div class="data-topic-card-download-menu" data-topic-download-menu hidden>
                <div class="data-topic-card-download-head">Download Excel</div>
                <div class="data-topic-card-download-list">
                  ${downloadMenu}
                </div>
              </div>
            </div>
            <span class="data-topic-card-open" aria-hidden="true"><i class="ti ti-arrow-up-right"></i></span>
          </div>
        </div>
        <div class="data-topic-card-body">
          <span class="data-topic-card-icon">
            ${
              icon
                ? `<img src="${escapeHtml(icon)}" alt="${escapeHtml(title)} icon" loading="lazy" decoding="async" fetchpriority="low" sizes="20px">`
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
    </article>
  `;
}

function renderLoading(grid) {
  grid.innerHTML = Array.from({ length: 8 }, () => '<div class="data-topic-card data-topic-card-skeleton"></div>').join("");
}

function renderState(grid, message) {
  grid.innerHTML = `<div class="data-topic-state">${escapeHtml(message)}</div>`;
}

function getTopicExportUrl(topicId, dataType) {
  const params = new URLSearchParams({
    data_type: dataType,
    file_type: "excel",
  });
  return `/api/mobile/export-topic-data/${encodeURIComponent(topicId)}/?${params.toString()}`;
}

function bindTopicDownloads(grid) {
  const downloadShells = Array.from(grid.querySelectorAll(".data-topic-card-download-shell"));
  if (!downloadShells.length) {
    return;
  }

  const closeAll = () => {
    downloadShells.forEach((shell) => {
      const trigger = shell.querySelector("[data-topic-download-trigger]");
      const menu = shell.querySelector("[data-topic-download-menu]");
      if (trigger) {
        trigger.setAttribute("aria-expanded", "false");
      }
      if (menu) {
        menu.hidden = true;
      }
    });
  };

  downloadShells.forEach((shell) => {
    const card = shell.closest("[data-topic-id]");
    const trigger = shell.querySelector("[data-topic-download-trigger]");
    const menu = shell.querySelector("[data-topic-download-menu]");

    if (!card || !trigger || !menu) {
      return;
    }

    trigger.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const isOpen = trigger.getAttribute("aria-expanded") === "true";
      closeAll();
      trigger.setAttribute("aria-expanded", isOpen ? "false" : "true");
      menu.hidden = isOpen;
    });

    menu.querySelectorAll("[data-topic-download-option]").forEach((option) => {
      option.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        const dataType = option.dataset.downloadType || "annual";
        closeAll();
        window.location.assign(getTopicExportUrl(card.dataset.topicId, dataType));
      });
    });
  });

  if (grid.dataset.topicDownloadsBound !== "true") {
    grid.dataset.topicDownloadsBound = "true";

    document.addEventListener("click", (event) => {
      if (!grid.contains(event.target)) {
        closeAll();
        return;
      }
      if (!event.target.closest(".data-topic-card-download-shell")) {
        closeAll();
      }
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeAll();
      }
    });
  }
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
    bindTopicDownloads(grid);
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
