const DEFAULT_OPTIONS = {
  endpoint: "/api/mobile/ministries/?year=2017&quarter=3month",
  autoScroll: true,
  autoScrollStep: 320,
  autoScrollInterval: 2600,
  limit: 10,
  detailBase: "",
  filterItem(item) {
    return Boolean(item && item.show_mobile_dashboard && item.ministry_is_visable);
  },
  sortItems(items) {
    return [...items].sort((left, right) => {
      const leftRank = Number(left.ministry_rank || 9999);
      const rightRank = Number(right.ministry_rank || 9999);
      return leftRank - rightRank;
    });
  },
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatScore(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return "--";
  }

  return `${numeric.toFixed(2)}%`;
}

function indicatorLabel(count) {
  const numeric = Number(count || 0);
  return `${numeric} indicator${numeric === 1 ? "" : "s"}`;
}

function formatPeriodLabel(endpoint) {
  try {
    const endpointUrl = new URL(endpoint, window.location.origin);
    const year = endpointUrl.searchParams.get("year");
    const quarter = endpointUrl.searchParams.get("quarter");
    const quarterMap = {
      "3month": "Q1",
      "6month": "Q2",
      "9month": "Q3",
      "12month": "Q4",
    };

    if (year && quarter) {
      return `${year} ${quarterMap[quarter] || quarter}`;
    }

    if (year) {
      return String(year);
    }
  } catch (_error) {
    // Ignore malformed endpoints.
  }

  return "Current period";
}

function buildImageUrl(value) {
  if (!value) {
    return "";
  }

  try {
    return new URL(value, window.location.origin).toString();
  } catch (_error) {
    return value;
  }
}

function buildDetailHref(item, endpoint, detailBase) {
  if (!detailBase || !item?.id) {
    return "";
  }

  const params = new URLSearchParams();

  try {
    const endpointUrl = new URL(endpoint, window.location.origin);
    const year = endpointUrl.searchParams.get("year");
    const quarter = endpointUrl.searchParams.get("quarter");

    if (year) {
      params.set("year", year);
    }

    if (quarter) {
      params.set("quarter", quarter);
    }
  } catch (_error) {
    // Ignore malformed endpoints and fall back to the base detail path.
  }

  const base = `${String(detailBase).replace(/\/?$/, "/")}${item.id}/`;
  const query = params.toString();
  return query ? `${base}?${query}` : base;
}

function createCard(item, endpoint, detailBase) {
  const accent = item.ministry_score_card?.scorecard_color || "#0f766e";
  const score = formatScore(item.ministry_score_card?.avg_score);
  const code = item.code || "N/A";
  const title = item.responsible_ministry_eng || item.responsible_ministry_amh || "Ministry";
  const logo = buildImageUrl(item.image);
  const href = buildDetailHref(item, endpoint, detailBase);
  const periodLabel = formatPeriodLabel(endpoint);
  const tagName = href ? "a" : "article";
  const hrefAttr = href ? ` href="${escapeHtml(href)}"` : "";

  return `
    <${tagName} class="ministry-card" style="--ministry-accent: ${escapeHtml(accent)};"${hrefAttr}>
      <div class="ministry-card-shell">
        <div class="ministry-card-mark">
          <span class="ministry-card-period">${escapeHtml(periodLabel)}</span>
        </div>
        <div class="ministry-card-body">
          <div class="ministry-card-logo">
            ${
              logo
                ? `<img src="${escapeHtml(logo)}" alt="${escapeHtml(code)} logo" loading="lazy" decoding="async" fetchpriority="low" sizes="40px">`
                : `<span>${escapeHtml(code.slice(0, 2))}</span>`
            }
          </div>
          <div class="ministry-card-heading">
            <h4>${escapeHtml(code)}</h4>
            <h5>${escapeHtml(title)}</h5>
          </div>
        </div>
        <div class="ministry-card-score">
          <div class="ministry-card-score-panel">
            <span>Score</span>
            <strong>${escapeHtml(score)}</strong>
          </div>
          <div class="ministry-card-side">
            <span class="ministry-card-indicators">${escapeHtml(indicatorLabel(item.count_indicator))}</span>
          </div>
        </div>
      </div>
    </${tagName}>
  `;
}

function renderLoading(track) {
  track.innerHTML = Array.from({ length: 4 }, () => '<div class="ministry-card-skeleton"></div>').join("");
}

function renderEmpty(track) {
  track.innerHTML = '<div class="ministry-card-empty">No ministry scorecards available for this period.</div>';
}

function renderError(track) {
  track.innerHTML = '<div class="ministry-card-error">Unable to load ministry scorecards right now.</div>';
}

function updateNavState(viewport, previousButton, nextButton) {
  if (!viewport || !previousButton || !nextButton) {
    return;
  }

  const maxScrollLeft = Math.max(0, viewport.scrollWidth - viewport.clientWidth);
  previousButton.disabled = viewport.scrollLeft <= 4;
  nextButton.disabled = viewport.scrollLeft >= maxScrollLeft - 4;
}

function createAutoScroller(viewport, options) {
  if (!viewport || !options.autoScroll) {
    return { start() {}, stop() {} };
  }

  let timer = null;
  let paused = false;

  const tick = () => {
    if (paused) {
      return;
    }

    const maxScrollLeft = Math.max(0, viewport.scrollWidth - viewport.clientWidth);
    if (maxScrollLeft <= 0) {
      return;
    }

    const nextPosition = viewport.scrollLeft + options.autoScrollStep;
    viewport.scrollTo({
      left: nextPosition >= maxScrollLeft ? 0 : nextPosition,
      behavior: "smooth",
    });
  };

  const start = () => {
    if (timer) {
      return;
    }
    timer = window.setInterval(tick, options.autoScrollInterval);
  };

  const stop = () => {
    if (!timer) {
      return;
    }
    window.clearInterval(timer);
    timer = null;
  };

  viewport.addEventListener("mouseenter", () => {
    paused = true;
  });
  viewport.addEventListener("mouseleave", () => {
    paused = false;
  });
  viewport.addEventListener("touchstart", () => {
    paused = true;
  }, { passive: true });
  viewport.addEventListener("touchend", () => {
    paused = false;
  }, { passive: true });

  return { start, stop };
}

function bindNavigation(viewport, previousButton, nextButton, options) {
  if (!viewport) {
    return;
  }

  previousButton?.addEventListener("click", () => {
    viewport.scrollBy({ left: -options.autoScrollStep, behavior: "smooth" });
  });

  nextButton?.addEventListener("click", () => {
    viewport.scrollBy({ left: options.autoScrollStep, behavior: "smooth" });
  });

  viewport.addEventListener("scroll", () => {
    window.requestAnimationFrame(() => updateNavState(viewport, previousButton, nextButton));
  }, { passive: true });
}

function resolveOptions(options) {
  return { ...DEFAULT_OPTIONS, ...(options || {}) };
}

async function mountMinistryScorecard(element, options = {}) {
  if (!element) {
    return null;
  }

  const settings = resolveOptions({
    endpoint: element.dataset.endpoint || DEFAULT_OPTIONS.endpoint,
    autoScroll:
      element.dataset.autoScroll === "false"
        ? false
        : options.autoScroll,
    limit: Number(element.dataset.limit || options.limit || DEFAULT_OPTIONS.limit),
    detailBase: element.dataset.detailBase || options.detailBase || DEFAULT_OPTIONS.detailBase,
    ...options,
  });

  const viewport = element.querySelector(".ministry-strip-viewport");
  const track = element.querySelector(".ministry-strip-track");
  const previousButton = element.querySelector("[data-ministry-prev]");
  const nextButton = element.querySelector("[data-ministry-next]");

  if (!viewport || !track) {
    return null;
  }

  renderLoading(track);
  bindNavigation(viewport, previousButton, nextButton, settings);

  try {
    const response = await fetch(settings.endpoint, {
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    const rows = Array.isArray(payload?.data) ? payload.data : [];
    const filtered = rows.filter((item) => settings.filterItem(item));
    const sorted = settings.sortItems(filtered).slice(0, settings.limit);

    if (!sorted.length) {
      renderEmpty(track);
      updateNavState(viewport, previousButton, nextButton);
      return null;
    }

    track.innerHTML = sorted.map((item) => createCard(item, settings.endpoint, settings.detailBase)).join("");
    updateNavState(viewport, previousButton, nextButton);

    const autoScroller = createAutoScroller(viewport, settings);
    autoScroller.start();

    return {
      destroy() {
        autoScroller.stop();
      },
    };
  } catch (_error) {
    renderError(track);
    updateNavState(viewport, previousButton, nextButton);
    return null;
  }
}

export const MinistryScorecard = {
  init(elementOrSelector, options = {}) {
    const element =
      typeof elementOrSelector === "string"
        ? document.querySelector(elementOrSelector)
        : elementOrSelector;
    return mountMinistryScorecard(element, options);
  },
  initAll(selector = "[data-ministry-scorecard]", options = {}) {
    return Promise.all(
      Array.from(document.querySelectorAll(selector)).map((element) =>
        mountMinistryScorecard(element, options)
      )
    );
  },
};

window.MinistryScorecard = MinistryScorecard;
