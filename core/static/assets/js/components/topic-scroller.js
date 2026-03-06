const TOPIC_MEDIA_BASE_URL = "https://time-series.mopd.gov.et/";

const DEFAULTS = {
  endpoint: "/api/mobile/topic-list/",
  mediaBaseUrl: TOPIC_MEDIA_BASE_URL,
  autoScroll: true,
  autoScrollStep: 360,
  autoScrollInterval: 2200,
  filterItem(item) {
    return Boolean(item);
  },
  sortItems(items) {
    return items.slice().sort(function (a, b) {
      return Number(a.rank || 0) - Number(b.rank || 0);
    });
  }
};

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function buildMediaUrl(path, baseUrl) {
  const raw = String(path || "").trim();
  if (!raw) {
    return "";
  }
  if (/^https?:\/\//i.test(raw)) {
    return raw;
  }
  return new URL(raw.replace(/^\//, ""), baseUrl || TOPIC_MEDIA_BASE_URL).toString();
}

function countLabel(count, label) {
  const value = Number(count || 0);
  return value + " " + label;
}

function createCard(item, options) {
  const title = item.title_ENG || item.title_AMH || "Untitled Topic";
  const bg = buildMediaUrl(item.background_image || item.image, options.mediaBaseUrl);
  const icon = buildMediaUrl(item.image_icons || item.image, options.mediaBaseUrl);
  const fallbackTone = Number(item.rank || 0) % 3;
  const toneClass = fallbackTone === 1 ? "tone-amber" : fallbackTone === 2 ? "tone-sky" : "tone-teal";

  return (
    '<article class="topic-card ' + toneClass + '" data-topic-id="' + escapeHtml(item.id) + '">' +
    (
      bg
        ? '<img class="topic-card-media" src="' + escapeHtml(bg) + '" alt="' + escapeHtml(title) + '">'
        : '<div class="topic-card-media topic-card-media-fallback"></div>'
    ) +
    '<div class="topic-card-body">' +
    '<div class="topic-card-top">' +
    '<span class="topic-card-icon">' +
    (icon ? '<img src="' + escapeHtml(icon) + '" alt="' + escapeHtml(title) + '">' : '<i class="ti ti-chart-bar"></i>') +
    "</span>" +
    '<span class="topic-card-pill"><i class="ti ti-hash"></i><span>' + escapeHtml(item.rank || "-") + "</span></span>" +
    "</div>" +
    '<div class="topic-card-kicker">Key Development Statistics</div>' +
    '<h3 class="topic-card-title">' + escapeHtml(title) + "</h3>" +
    '<div class="topic-card-meta">' +
    '<span class="topic-card-badge"><i class="ti ti-category"></i><span>' + escapeHtml(countLabel(item.count_category, "categories")) + "</span></span>" +
    '<span class="topic-card-badge"><i class="ti ti-chart-dots-2"></i><span>' + escapeHtml(countLabel(item.count_kpis, "indicators")) + "</span></span>" +
    "</div>" +
    "</div>" +
    "</article>"
  );
}

function renderLoading(track) {
  track.innerHTML = [
    '<div class="topic-card-skeleton"></div>',
    '<div class="topic-card-skeleton"></div>',
    '<div class="topic-card-skeleton"></div>'
  ].join("");
}

function renderError(track, message) {
  track.innerHTML = '<div class="topic-card-error">' + escapeHtml(message) + "</div>";
}

function renderEmpty(track) {
  track.innerHTML = '<div class="topic-card-empty">No topics available right now.</div>';
}

function updateNavState(viewport, prevBtn, nextBtn) {
  if (!viewport || !prevBtn || !nextBtn) {
    return;
  }
  const maxScroll = Math.max(0, viewport.scrollWidth - viewport.clientWidth);
  prevBtn.disabled = viewport.scrollLeft <= 4;
  nextBtn.disabled = viewport.scrollLeft >= maxScroll - 4;
}

function createAutoScroller(viewport, prevBtn, nextBtn, options) {
  let timer = null;

  function tick() {
    const maxScroll = Math.max(0, viewport.scrollWidth - viewport.clientWidth);
    if (maxScroll <= 0) {
      return;
    }
    const nextLeft = viewport.scrollLeft + options.autoScrollStep >= maxScroll - 4 ? 0 : viewport.scrollLeft + options.autoScrollStep;
    viewport.scrollTo({ left: nextLeft, behavior: "smooth" });
    updateNavState(viewport, prevBtn, nextBtn);
  }

  function resume() {
    if (timer || !options.autoScroll) {
      return;
    }
    timer = window.setInterval(tick, options.autoScrollInterval);
  }

  function pause() {
    if (!timer) {
      return;
    }
    window.clearInterval(timer);
    timer = null;
  }

  viewport.addEventListener("mouseenter", pause);
  viewport.addEventListener("mouseleave", resume);
  viewport.addEventListener("touchstart", pause, { passive: true });
  viewport.addEventListener("touchend", resume, { passive: true });

  return {
    start: resume,
    stop: pause
  };
}

function resolveOptions(mount, overrides) {
  const options = Object.assign({}, DEFAULTS, overrides || {});
  if (mount.dataset.endpoint && !(overrides && "endpoint" in overrides)) {
    options.endpoint = mount.dataset.endpoint;
  }
  if (mount.dataset.mediaBaseUrl && !(overrides && "mediaBaseUrl" in overrides)) {
    options.mediaBaseUrl = mount.dataset.mediaBaseUrl;
  }
  if (mount.dataset.autoScroll === "false" && !(overrides && "autoScroll" in overrides)) {
    options.autoScroll = false;
  }
  return options;
}

function bindNavigation(viewport, prevBtn, nextBtn) {
  prevBtn.addEventListener("click", function () {
    viewport.scrollBy({ left: -320, behavior: "smooth" });
  });

  nextBtn.addEventListener("click", function () {
    viewport.scrollBy({ left: 320, behavior: "smooth" });
  });

  viewport.addEventListener("scroll", function () {
    updateNavState(viewport, prevBtn, nextBtn);
  }, { passive: true });

  window.addEventListener("resize", function () {
    updateNavState(viewport, prevBtn, nextBtn);
  });
}

async function mountTopicScroller(mount, overrides) {
  const options = resolveOptions(mount, overrides);
  const viewport = mount.querySelector(".topic-strip-viewport");
  const track = mount.querySelector(".topic-strip-track");
  const prevBtn = mount.querySelector("[data-topic-prev]");
  const nextBtn = mount.querySelector("[data-topic-next]");

  if (!viewport || !track || !prevBtn || !nextBtn) {
    return null;
  }

  renderLoading(track);

  try {
    const response = await fetch(options.endpoint, {
      headers: { Accept: "application/json" },
      credentials: "same-origin"
    });
    const payload = await response.json();

    if (!response.ok || !payload || !Array.isArray(payload.data)) {
      renderError(track, "Unable to load topics.");
      return null;
    }

    const topics = options.sortItems(
      payload.data.filter(function (item) {
        return options.filterItem(item);
      })
    );

    if (!topics.length) {
      renderEmpty(track);
      return null;
    }

    track.innerHTML = topics.map(function (item) {
      return createCard(item, options);
    }).join("");
    bindNavigation(viewport, prevBtn, nextBtn);
    updateNavState(viewport, prevBtn, nextBtn);

    const autoScroller = createAutoScroller(viewport, prevBtn, nextBtn, options);
    autoScroller.start();

    mount.__topicScroller = {
      options,
      refresh() {
        return mountTopicScroller(mount, options);
      },
      start: autoScroller.start,
      stop: autoScroller.stop
    };

    return mount.__topicScroller;
  } catch (error) {
    renderError(track, "Unable to load topics.");
    return null;
  }
}

export const TopicScroller = {
  init(selectorOrElement, options) {
    const element = typeof selectorOrElement === "string"
      ? document.querySelector(selectorOrElement)
      : selectorOrElement;
    if (!element) {
      return null;
    }
    return mountTopicScroller(element, options);
  },
  initAll(selector, options) {
    const elements = Array.from(document.querySelectorAll(selector || "[data-topic-scroller]"));
    return Promise.all(elements.map(function (element) {
      return mountTopicScroller(element, options);
    }));
  }
};

window.TopicScroller = TopicScroller;
