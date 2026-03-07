const DEFAULT_OPTIONS = {
  endpoint: "/api/mobile/project-list/",
  mediaBaseUrl: "https://time-series.mopd.gov.et/",
  limit: 10,
  autoScroll: true,
  autoScrollStep: 320,
  autoScrollInterval: 2600,
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

function truncate(value, maxLength = 86) {
  const text = String(value ?? "").trim();
  if (!text) {
    return "";
  }

  return text.length > maxLength ? `${text.slice(0, maxLength).trim()}...` : text;
}

function createCard(item, mediaBaseUrl) {
  const title = item.title_ENG || item.title_AMH || "Project";
  const description = truncate(item.description || "Project insights and implementation highlights.");
  const image = buildMediaUrl(item.image, mediaBaseUrl);

  return `
    <article class="project-card">
      ${
        image
          ? `<img class="project-card-media" src="${escapeHtml(image)}" alt="${escapeHtml(title)}" loading="lazy" decoding="async" fetchpriority="low" sizes="(max-width: 767px) 230px, 240px">`
          : `<div class="project-card-fallback" aria-hidden="true"></div>`
      }
      <div class="project-card-overlay"></div>
      <div class="project-card-shell">
        <div class="project-card-mark">
          <span class="project-card-open">
            <i class="ti ti-arrow-up-right"></i>
          </span>
        </div>
        <div class="project-card-body">
          <h3>${escapeHtml(title)}</h3>
          <p>${escapeHtml(description)}</p>
        </div>
      </div>
    </article>
  `;
}

function renderLoading(track) {
  track.innerHTML = Array.from({ length: 4 }, () => '<div class="project-card project-card-skeleton"></div>').join("");
}

function renderEmpty(track) {
  track.innerHTML = '<div class="project-card-state">No projects available right now.</div>';
}

function renderError(track) {
  track.innerHTML = '<div class="project-card-state">Unable to load projects right now.</div>';
}

function updateNavState(viewport, previousButton, nextButton) {
  if (!viewport || !previousButton || !nextButton) {
    return;
  }

  const maxScrollLeft = Math.max(0, viewport.scrollWidth - viewport.clientWidth);
  previousButton.disabled = viewport.scrollLeft <= 4;
  nextButton.disabled = viewport.scrollLeft >= maxScrollLeft - 4;
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

  viewport.addEventListener(
    "scroll",
    () => {
      window.requestAnimationFrame(() => updateNavState(viewport, previousButton, nextButton));
    },
    { passive: true }
  );
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
  viewport.addEventListener(
    "touchstart",
    () => {
      paused = true;
    },
    { passive: true }
  );
  viewport.addEventListener(
    "touchend",
    () => {
      paused = false;
    },
    { passive: true }
  );

  return { start, stop };
}

async function mountProjectStrip(element, options = {}) {
  if (!element) {
    return null;
  }

  const settings = {
    ...DEFAULT_OPTIONS,
    ...options,
    endpoint: element.dataset.endpoint || options.endpoint || DEFAULT_OPTIONS.endpoint,
    mediaBaseUrl: element.dataset.mediaBaseUrl || options.mediaBaseUrl || DEFAULT_OPTIONS.mediaBaseUrl,
    autoScroll:
      element.dataset.autoScroll === "false"
        ? false
        : (options.autoScroll ?? DEFAULT_OPTIONS.autoScroll),
    limit: Number(element.dataset.limit || options.limit || DEFAULT_OPTIONS.limit),
  };

  const viewport = element.querySelector("[data-project-viewport]");
  const track = element.querySelector("[data-project-track]");
  const previousButton = element.querySelector("[data-project-prev]");
  const nextButton = element.querySelector("[data-project-next]");

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
    const items = (Array.isArray(payload?.data) ? payload.data : []).slice(0, settings.limit);

    if (!items.length) {
      renderEmpty(track);
      updateNavState(viewport, previousButton, nextButton);
      return null;
    }

    track.innerHTML = items.map((item) => createCard(item, settings.mediaBaseUrl)).join("");
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

export const ProjectStrip = {
  init(elementOrSelector, options = {}) {
    const element =
      typeof elementOrSelector === "string"
        ? document.querySelector(elementOrSelector)
        : elementOrSelector;
    return mountProjectStrip(element, options);
  },
  initAll(selector = "[data-project-strip]", options = {}) {
    return Promise.all(
      Array.from(document.querySelectorAll(selector)).map((element) =>
        mountProjectStrip(element, options)
      )
    );
  },
};

window.ProjectStrip = ProjectStrip;
