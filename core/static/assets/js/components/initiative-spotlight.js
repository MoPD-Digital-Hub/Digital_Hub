const DEFAULT_OPTIONS = {
  endpoint: "/api/mobile/initiatives/",
  mediaBaseUrl: "https://time-series.mopd.gov.et/",
  limit: 12,
  imageCards: 4,
  initialVisibleStacked: 4,
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function shuffle(items) {
  const copy = [...items];
  for (let index = copy.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(Math.random() * (index + 1));
    [copy[index], copy[swapIndex]] = [copy[swapIndex], copy[index]];
  }
  return copy;
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

function truncate(value, maxLength = 108) {
  const text = String(value ?? "").trim();
  if (!text) {
    return "";
  }

  return text.length > maxLength ? `${text.slice(0, maxLength).trim()}...` : text;
}

function createImageCard(item, mediaBaseUrl) {
  const title = item.title_ENG || item.title_AMH || "Initiative";
  const description = truncate(item.description || "Initiative overview and strategic implementation context.");
  const backgroundImage = buildMediaUrl(item.background_image || item.image, mediaBaseUrl);
  const iconImage = buildMediaUrl(item.image_icons, mediaBaseUrl);

  return `
    <article class="initiative-card">
      ${
        backgroundImage
          ? `<img class="initiative-card-media" src="${escapeHtml(backgroundImage)}" alt="${escapeHtml(title)}" loading="lazy" decoding="async" fetchpriority="low" sizes="(max-width: 767px) 100vw, 320px">`
          : `<div class="initiative-card-fallback" aria-hidden="true"></div>`
      }
      <div class="initiative-card-overlay"></div>
      <div class="initiative-card-shell">
        <div class="initiative-card-mark">
          <span class="initiative-card-icon">
            ${
              iconImage
                ? `<img src="${escapeHtml(iconImage)}" alt="${escapeHtml(title)} icon" loading="lazy" decoding="async" fetchpriority="low" sizes="18px">`
                : `<i class="ti ti-bulb"></i>`
            }
          </span>
          <span class="initiative-card-open">
            <i class="ti ti-arrow-up-right"></i>
          </span>
        </div>
        <div class="initiative-card-copy">
          <h3>${escapeHtml(title)}</h3>
          <p>${escapeHtml(description)}</p>
        </div>
      </div>
    </article>
  `;
}

function createStackItem(item, mediaBaseUrl, hidden = false) {
  const title = item.title_ENG || item.title_AMH || "Initiative";
  const description = truncate(item.description || "Initiative overview and strategic implementation context.", 94);
  const backgroundImage = buildMediaUrl(item.background_image || item.image, mediaBaseUrl);
  const categoryCount = Number(item.count_category || 0);
  const kpiCount = Number(item.count_kpis || 0);

  return `
    <article class="initiative-list-item${hidden ? " is-hidden" : ""}">
      <div class="initiative-list-thumb">
        ${
          backgroundImage
            ? `<img src="${escapeHtml(backgroundImage)}" alt="${escapeHtml(title)}" loading="lazy" decoding="async" fetchpriority="low" sizes="72px">`
            : `<span class="initiative-list-thumb-fallback"></span>`
        }
      </div>
      <div class="initiative-list-copy">
        <h4>${escapeHtml(title)}</h4>
        <p>${escapeHtml(description)}</p>
        <div class="initiative-list-meta">
          <span>${escapeHtml(`${categoryCount} categories`)}</span>
          <span>${escapeHtml(`${kpiCount} KPIs`)}</span>
        </div>
      </div>
    </article>
  `;
}

function renderLoading(layout) {
  layout.innerHTML = `
    <div class="initiative-card-grid">
      ${Array.from({ length: 4 }, () => '<div class="initiative-card initiative-card-skeleton"></div>').join("")}
    </div>
    <div class="initiative-list-panel">
      ${Array.from({ length: 4 }, () => '<div class="initiative-list-item initiative-card-skeleton"></div>').join("")}
    </div>
  `;
}

function renderEmpty(layout) {
  layout.innerHTML = '<div class="initiative-card-state">No initiatives available right now.</div>';
}

function renderError(layout) {
  layout.innerHTML = '<div class="initiative-card-state">Unable to load initiatives right now.</div>';
}

function bindToggle(button, list) {
  if (!button || !list) {
    return;
  }

  button.onclick = () => {
    const expanded = list.classList.toggle("is-expanded");
    button.setAttribute("aria-expanded", expanded ? "true" : "false");
    button.querySelector("span").textContent = expanded ? "Show less" : "Show more";
  };
}

async function mountInitiativeSpotlight(element, options = {}) {
  if (!element) {
    return null;
  }

  const settings = {
    ...DEFAULT_OPTIONS,
    ...options,
    endpoint: element.dataset.endpoint || options.endpoint || DEFAULT_OPTIONS.endpoint,
    mediaBaseUrl: element.dataset.mediaBaseUrl || options.mediaBaseUrl || DEFAULT_OPTIONS.mediaBaseUrl,
    limit: Number(element.dataset.limit || options.limit || DEFAULT_OPTIONS.limit),
    imageCards: Number(element.dataset.imageCards || options.imageCards || DEFAULT_OPTIONS.imageCards),
    initialVisibleStacked: Number(
      element.dataset.initialVisibleStacked || options.initialVisibleStacked || DEFAULT_OPTIONS.initialVisibleStacked
    ),
  };

  const layout = element.querySelector("[data-initiative-layout]");
  const toggleButton = element.querySelector("[data-initiative-toggle]");
  if (!layout) {
    return null;
  }

  renderLoading(layout);

  try {
    const response = await fetch(settings.endpoint, {
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    const items = shuffle(
      (Array.isArray(payload?.data) ? payload.data : []).filter((item) => item && item.is_initiative)
    ).slice(0, settings.limit);

    if (!items.length) {
      renderEmpty(layout);
      if (toggleButton) {
        toggleButton.hidden = true;
      }
      return null;
    }

    const imageItems = items.slice(0, settings.imageCards);
    const stackedItems = items.slice(settings.imageCards);

    layout.innerHTML = `
      <div class="initiative-card-grid">
        ${imageItems.map((item) => createImageCard(item, settings.mediaBaseUrl)).join("")}
      </div>
      <div class="initiative-list-panel">
        <div class="initiative-list" data-initiative-list>
          ${stackedItems
            .map((item, index) =>
              createStackItem(item, settings.mediaBaseUrl, index >= settings.initialVisibleStacked)
            )
            .join("")}
        </div>
      </div>
    `;

    const hiddenCount = Math.max(0, stackedItems.length - settings.initialVisibleStacked);
    if (toggleButton) {
      toggleButton.hidden = hiddenCount === 0;
      if (hiddenCount > 0) {
        toggleButton.setAttribute("aria-expanded", "false");
        toggleButton.querySelector("span").textContent = "Show more";
        bindToggle(toggleButton, layout.querySelector("[data-initiative-list]"));
      }
    }
  } catch (_error) {
    renderError(layout);
    if (toggleButton) {
      toggleButton.hidden = true;
    }
  }

  return null;
}

export const InitiativeSpotlight = {
  init(elementOrSelector, options = {}) {
    const element =
      typeof elementOrSelector === "string"
        ? document.querySelector(elementOrSelector)
        : elementOrSelector;
    return mountInitiativeSpotlight(element, options);
  },
  initAll(selector = "[data-initiative-spotlight]", options = {}) {
    return Promise.all(
      Array.from(document.querySelectorAll(selector)).map((element) =>
        mountInitiativeSpotlight(element, options)
      )
    );
  },
};

window.InitiativeSpotlight = InitiativeSpotlight;
