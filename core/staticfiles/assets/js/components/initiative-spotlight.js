const DEFAULT_OPTIONS = {
  endpoint: "/api/mobile/initiatives/",
  mediaBaseUrl: "https://time-series.mopd.gov.et/",
  limit: 12,
  imageCards: 4,
  initialVisibleStacked: 4,
  shuffle: true,
  variant: "default",
  detailBase: "",
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

function createImageCard(item, mediaBaseUrl, detailBase) {
  const title = item.title_ENG || item.title_AMH || "Initiative";
  const description = truncate(item.description || "Initiative overview and strategic implementation context.");
  const backgroundImage = buildMediaUrl(item.background_image || item.image, mediaBaseUrl);
  const iconImage = buildMediaUrl(item.image_icons, mediaBaseUrl);
  const href = buildDetailHref(item, detailBase);
  const tagName = href ? "a" : "article";
  const hrefAttr = href ? ` href="${escapeHtml(href)}"` : "";

  return `
    <${tagName} class="initiative-card"${hrefAttr}>
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
    </${tagName}>
  `;
}

function createEditorialCard(item, mediaBaseUrl, tone = "compact") {
  const title = item.title_ENG || item.title_AMH || "Initiative";
  const description = truncate(
    item.description || "Initiative overview and strategic implementation context.",
    tone === "featured" ? 172 : 104
  );
  const backgroundImage = buildMediaUrl(item.background_image || item.image, mediaBaseUrl);
  const iconImage = buildMediaUrl(item.image_icons, mediaBaseUrl);
  const categoryCount = Number(item.count_category || 0);
  const kpiCount = Number(item.count_kpis || 0);

  return `
    <article class="initiative-editorial-card initiative-editorial-card--${escapeHtml(tone)}">
      <div class="initiative-editorial-media">
        ${
          backgroundImage
            ? `<img src="${escapeHtml(backgroundImage)}" alt="${escapeHtml(title)}" loading="lazy" decoding="async" fetchpriority="low" sizes="(max-width: 767px) 100vw, 420px">`
            : `<div class="initiative-editorial-fallback" aria-hidden="true"></div>`
        }
      </div>
      <div class="initiative-editorial-copy">
        <div class="initiative-editorial-meta">
          <span class="initiative-editorial-icon">
            ${
              iconImage
                ? `<img src="${escapeHtml(iconImage)}" alt="${escapeHtml(title)} icon" loading="lazy" decoding="async" fetchpriority="low" sizes="18px">`
                : `<i class="ti ti-bulb"></i>`
            }
          </span>
          <div class="initiative-editorial-stats">
            <span>${escapeHtml(`${categoryCount} categories`)}</span>
            <span>${escapeHtml(`${kpiCount} KPIs`)}</span>
          </div>
        </div>
        <div class="initiative-editorial-body">
          <h3>${escapeHtml(title)}</h3>
          <p>${escapeHtml(description)}</p>
        </div>
      </div>
    </article>
  `;
}

function createInteractiveStage(item, mediaBaseUrl) {
  const title = item.title_ENG || item.title_AMH || "Initiative";
  const description = item.description || "Initiative overview and strategic implementation context.";
  const backgroundImage = buildMediaUrl(item.background_image || item.image, mediaBaseUrl);
  const iconImage = buildMediaUrl(item.image_icons, mediaBaseUrl);
  const categoryCount = Number(item.count_category || 0);
  const kpiCount = Number(item.count_kpis || 0);

  return `
    <div class="initiative-interactive-stage">
      <div class="initiative-interactive-media">
        ${
          backgroundImage
            ? `<img src="${escapeHtml(backgroundImage)}" alt="${escapeHtml(title)}" loading="lazy" decoding="async" fetchpriority="low" sizes="(max-width: 991px) 100vw, 720px">`
            : `<div class="initiative-interactive-fallback" aria-hidden="true"></div>`
        }
        <div class="initiative-interactive-overlay"></div>
      </div>
      <div class="initiative-interactive-shell">
        <div class="initiative-interactive-head">
          <span class="initiative-interactive-icon">
            ${
              iconImage
                ? `<img src="${escapeHtml(iconImage)}" alt="${escapeHtml(title)} icon" loading="lazy" decoding="async" fetchpriority="low" sizes="20px">`
                : `<i class="ti ti-bulb"></i>`
            }
          </span>
          <div class="initiative-interactive-badges">
            <span>${escapeHtml(`${categoryCount} categories`)}</span>
            <span>${escapeHtml(`${kpiCount} KPIs`)}</span>
          </div>
        </div>
        <div class="initiative-interactive-copy">
          <h3>${escapeHtml(title)}</h3>
          <p>${escapeHtml(description)}</p>
        </div>
      </div>
    </div>
  `;
}

function createInteractiveListItem(item, mediaBaseUrl, index, active = false) {
  const title = item.title_ENG || item.title_AMH || "Initiative";
  const backgroundImage = buildMediaUrl(item.background_image || item.image, mediaBaseUrl);
  const iconImage = buildMediaUrl(item.image_icons, mediaBaseUrl);

  return `
    <button
      type="button"
      class="initiative-interactive-item${active ? " is-active" : ""}"
      data-initiative-pick="${escapeHtml(index)}"
    >
      <span class="initiative-interactive-item-thumb">
        ${
          backgroundImage
            ? `<img src="${escapeHtml(backgroundImage)}" alt="${escapeHtml(title)}" loading="lazy" decoding="async" fetchpriority="low" sizes="64px">`
            : `<span class="initiative-interactive-item-fallback"></span>`
        }
      </span>
      <span class="initiative-interactive-item-copy">
        <span class="initiative-interactive-item-title">${escapeHtml(title)}</span>
        <span class="initiative-interactive-item-meta">
          ${
            iconImage
              ? `<img src="${escapeHtml(iconImage)}" alt="" loading="lazy" decoding="async" fetchpriority="low" sizes="14px">`
              : `<i class="ti ti-bulb"></i>`
          }
          <span>${escapeHtml(`${Number(item.count_kpis || 0)} KPIs`)}</span>
        </span>
      </span>
    </button>
  `;
}

function buildDetailHref(item, detailBase) {
  if (!detailBase || !item?.id) {
    return "";
  }

  return `${String(detailBase).replace(/\/?$/, "/")}${item.id}/`;
}

function createCatalogCard(item, mediaBaseUrl, detailBase) {
  const title = item.title_ENG || item.title_AMH || "Initiative";
  const description = truncate(item.description || "Initiative overview and strategic implementation context.", 128);
  const backgroundImage = buildMediaUrl(item.background_image || item.image, mediaBaseUrl);
  const iconImage = buildMediaUrl(item.image_icons, mediaBaseUrl);
  const categoryCount = Number(item.count_category || 0);
  const kpiCount = Number(item.count_kpis || 0);
  const href = buildDetailHref(item, detailBase);
  const tagName = href ? "a" : "article";
  const hrefAttr = href ? ` href="${escapeHtml(href)}"` : "";

  return `
    <${tagName} class="initiative-catalog-card"${hrefAttr}>
      <div class="initiative-catalog-media">
        ${
          backgroundImage
            ? `<img src="${escapeHtml(backgroundImage)}" alt="${escapeHtml(title)}" loading="lazy" decoding="async" fetchpriority="low" sizes="(max-width: 767px) 100vw, (max-width: 1399px) 50vw, 25vw">`
            : `<div class="initiative-catalog-fallback" aria-hidden="true"></div>`
        }
      </div>
      <div class="initiative-catalog-body">
        <div class="initiative-catalog-head">
          <span class="initiative-catalog-icon">
            ${
              iconImage
                ? `<img src="${escapeHtml(iconImage)}" alt="${escapeHtml(title)} icon" loading="lazy" decoding="async" fetchpriority="low" sizes="18px">`
                : `<i class="ti ti-bulb"></i>`
            }
          </span>
          <div class="initiative-catalog-meta">
            <span>${escapeHtml(`${categoryCount} categories`)}</span>
            <span>${escapeHtml(`${kpiCount} KPIs`)}</span>
          </div>
        </div>
        <div class="initiative-catalog-copy">
          <h3>${escapeHtml(title)}</h3>
          <p>${escapeHtml(description)}</p>
        </div>
        <div class="initiative-catalog-foot">
          <span class="initiative-catalog-line"></span>
          <span class="initiative-catalog-open">
            <span>Open initiative</span>
            <i class="ti ti-arrow-up-right"></i>
          </span>
        </div>
      </div>
    </${tagName}>
  `;
}

function createStackItem(item, mediaBaseUrl, hidden = false, detailBase = "") {
  const title = item.title_ENG || item.title_AMH || "Initiative";
  const description = truncate(item.description || "Initiative overview and strategic implementation context.", 94);
  const backgroundImage = buildMediaUrl(item.background_image || item.image, mediaBaseUrl);
  const categoryCount = Number(item.count_category || 0);
  const kpiCount = Number(item.count_kpis || 0);
  const href = buildDetailHref(item, detailBase);
  const tagName = href ? "a" : "article";
  const hrefAttr = href ? ` href="${escapeHtml(href)}"` : "";

  return `
    <${tagName} class="initiative-list-item${hidden ? " is-hidden" : ""}"${hrefAttr}>
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
    </${tagName}>
  `;
}

function bindToggleState(toggleButton, list, hiddenCount) {
  if (!toggleButton) {
    return;
  }

  toggleButton.hidden = hiddenCount === 0;
  if (hiddenCount > 0) {
    toggleButton.setAttribute("aria-expanded", "false");
    toggleButton.querySelector("span").textContent = "Show more";
    bindToggle(toggleButton, list);
  }
}

function renderEditorialLayout(layout, settings, items, toggleButton) {
  const featuredItem = items[0];
  const compactItems = items.slice(1, 5);
  const stackedItems = items.slice(5);

  layout.innerHTML = `
    <div class="initiative-editorial">
      <div class="initiative-editorial-featured">
        ${featuredItem ? createEditorialCard(featuredItem, settings.mediaBaseUrl, "featured") : ""}
      </div>
      <div class="initiative-editorial-grid">
        ${compactItems.map((item) => createEditorialCard(item, settings.mediaBaseUrl, "compact")).join("")}
      </div>
      <div class="initiative-list-panel initiative-list-panel--editorial">
        <div class="initiative-list" data-initiative-list>
          ${stackedItems
            .map((item, index) =>
              createStackItem(item, settings.mediaBaseUrl, index >= settings.initialVisibleStacked, settings.detailBase)
            )
            .join("")}
        </div>
      </div>
    </div>
  `;

  bindToggleState(
    toggleButton,
    layout.querySelector("[data-initiative-list]"),
    Math.max(0, stackedItems.length - settings.initialVisibleStacked)
  );
}

function renderInteractiveLayout(layout, settings, items, toggleButton) {
  layout.innerHTML = `
    <div class="initiative-interactive">
      <div class="initiative-interactive-stage-wrap" data-initiative-stage></div>
      <div class="initiative-interactive-list" data-initiative-picker>
        ${items
          .map((item, index) => createInteractiveListItem(item, settings.mediaBaseUrl, index, index === 0))
          .join("")}
      </div>
    </div>
  `;

  const stage = layout.querySelector("[data-initiative-stage]");
  const picker = layout.querySelector("[data-initiative-picker]");
  if (!stage || !picker) {
    if (toggleButton) {
      toggleButton.hidden = true;
    }
    return;
  }

  const updateStage = (index) => {
    const activeIndex = Number(index) || 0;
    const selectedItem = items[activeIndex] || items[0];
    stage.innerHTML = createInteractiveStage(selectedItem, settings.mediaBaseUrl);
    picker.querySelectorAll("[data-initiative-pick]").forEach((button) => {
      button.classList.toggle("is-active", Number(button.dataset.initiativePick) === activeIndex);
    });
  };

  picker.addEventListener("click", (event) => {
    const button = event.target.closest("[data-initiative-pick]");
    if (!button) {
      return;
    }
    updateStage(button.dataset.initiativePick);
  });

  updateStage(0);

  if (toggleButton) {
    toggleButton.hidden = true;
  }
}

function renderCatalogLayout(layout, settings, items, toggleButton) {
  layout.innerHTML = `
    <div class="initiative-catalog-grid">
      ${items.map((item) => createCatalogCard(item, settings.mediaBaseUrl, settings.detailBase)).join("")}
    </div>
  `;

  if (toggleButton) {
    toggleButton.hidden = true;
  }
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
    shuffle:
      element.dataset.shuffle === "false"
        ? false
        : (options.shuffle ?? DEFAULT_OPTIONS.shuffle),
    variant: element.dataset.variant || options.variant || DEFAULT_OPTIONS.variant,
    detailBase: element.dataset.detailBase || options.detailBase || DEFAULT_OPTIONS.detailBase,
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
    const rawItems = (Array.isArray(payload?.data) ? payload.data : []).filter(
      (item) => item && item.is_initiative
    );
    const items = (settings.shuffle ? shuffle(rawItems) : rawItems).slice(0, settings.limit);

    if (!items.length) {
      renderEmpty(layout);
      if (toggleButton) {
        toggleButton.hidden = true;
      }
      return null;
    }

    if (settings.variant === "catalog") {
      renderCatalogLayout(layout, settings, items, toggleButton);
    } else if (settings.variant === "interactive") {
      renderInteractiveLayout(layout, settings, items, toggleButton);
    } else if (settings.variant === "editorial") {
      renderEditorialLayout(layout, settings, items, toggleButton);
    } else {
      const imageItems = items.slice(0, settings.imageCards);
      const stackedItems = items.slice(settings.imageCards);

      layout.innerHTML = `
        <div class="initiative-card-grid">
          ${imageItems.map((item) => createImageCard(item, settings.mediaBaseUrl, settings.detailBase)).join("")}
        </div>
        <div class="initiative-list-panel">
          <div class="initiative-list" data-initiative-list>
            ${stackedItems
              .map((item, index) =>
                createStackItem(item, settings.mediaBaseUrl, index >= settings.initialVisibleStacked, settings.detailBase)
              )
              .join("")}
          </div>
        </div>
      `;

      bindToggleState(
        toggleButton,
        layout.querySelector("[data-initiative-list]"),
        Math.max(0, stackedItems.length - settings.initialVisibleStacked)
      );
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
