const DEFAULT_OPTIONS = {
  faydaEndpoint: "https://time-series.mopd.gov.et/api/fayda/",
  sliderInterval: 2600,
  mesobData: {
    title: "Mesob",
    subtitle: "Public Service Delivery Snapshot",
    primaryValue: "136,156",
    primaryLabel: "Services Delivered",
    secondaryValue: "24",
    secondaryLabel: "Active Modules",
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

function formatNumber(value) {
  const numeric = Number(String(value ?? "").replaceAll(",", ""));
  if (!Number.isFinite(numeric)) {
    return value || "--";
  }

  return new Intl.NumberFormat().format(numeric);
}

function renderMetricSlides(metrics) {
  return `
    <div class="summary-slider" data-summary-slider>
      <div class="summary-slider-track">
        ${metrics
          .map(
            (metric, index) => `
              <article class="summary-slide${index === 0 ? " is-active" : ""}" data-summary-slide>
                <span class="summary-slide-label">${escapeHtml(metric.label)}</span>
                <strong>${escapeHtml(formatNumber(metric.value))}</strong>
              </article>
            `
          )
          .join("")}
      </div>
      <div class="summary-slider-dots">
        ${metrics
          .map(
            (_metric, index) => `
              <button
                type="button"
                class="summary-slider-dot${index === 0 ? " is-active" : ""}"
                data-summary-dot
                data-index="${index}"
                aria-label="Show metric ${index + 1}"
              ></button>
            `
          )
          .join("")}
      </div>
    </div>
  `;
}

function renderFaydaMetrics(data = {}) {
  const metrics = [
    { label: "eKYC", value: data.ekyc },
    { label: "Registrations", value: data.total_reg },
    { label: "Partners", value: data.partners },
  ];

  return renderMetricSlides(metrics);
}

function renderMesobMetrics(data = {}) {
  const metrics = [
    { label: data.primaryLabel || "Primary Metric", value: data.primaryValue },
    { label: data.secondaryLabel || "Secondary Metric", value: data.secondaryValue },
  ];

  return renderMetricSlides(metrics);
}

function mountSlider(panelBody, interval) {
  const slider = panelBody.querySelector("[data-summary-slider]");
  if (!slider) {
    return null;
  }

  const slides = Array.from(slider.querySelectorAll("[data-summary-slide]"));
  const dots = Array.from(slider.querySelectorAll("[data-summary-dot]"));
  if (slides.length <= 1) {
    return null;
  }

  let activeIndex = 0;
  let timer = null;
  let paused = false;

  const setActive = (index) => {
    activeIndex = index;
    slides.forEach((slide, slideIndex) => {
      slide.classList.toggle("is-active", slideIndex === index);
    });
    dots.forEach((dot, dotIndex) => {
      dot.classList.toggle("is-active", dotIndex === index);
    });
  };

  const next = () => {
    setActive((activeIndex + 1) % slides.length);
  };

  const start = () => {
    if (timer) {
      return;
    }
    timer = window.setInterval(() => {
      if (!paused) {
        next();
      }
    }, interval);
  };

  const stop = () => {
    if (!timer) {
      return;
    }
    window.clearInterval(timer);
    timer = null;
  };

  dots.forEach((dot, index) => {
    dot.addEventListener("click", () => {
      setActive(index);
    });
  });

  slider.addEventListener("mouseenter", () => {
    paused = true;
  });
  slider.addEventListener("mouseleave", () => {
    paused = false;
  });
  slider.addEventListener("touchstart", () => {
    paused = true;
  }, { passive: true });
  slider.addEventListener("touchend", () => {
    paused = false;
  }, { passive: true });

  start();

  return { stop };
}

function renderLoading(panelBody) {
  return `
    <div class="summary-slider">
      <div class="summary-slide summary-slide-loading"></div>
      <div class="summary-slider-dots">
        <span class="summary-slider-dot is-active"></span>
        <span class="summary-slider-dot"></span>
        <span class="summary-slider-dot"></span>
      </div>
    </div>
  `;
}

function renderError(panelBody, message) {
  panelBody.innerHTML = `<div class="summary-panel-state">${escapeHtml(message)}</div>`;
}

async function mountSummaryPanels(element, options = {}) {
  if (!element) {
    return null;
  }

  const settings = {
    ...DEFAULT_OPTIONS,
    ...options,
    faydaEndpoint: element.dataset.faydaEndpoint || options.faydaEndpoint || DEFAULT_OPTIONS.faydaEndpoint,
  };

  const faydaBody = element.querySelector("[data-summary-fayda-body]");
  const mesobBody = element.querySelector("[data-summary-mesob-body]");

  if (!faydaBody || !mesobBody) {
    return null;
  }

  const controllers = [];

  faydaBody.innerHTML = renderLoading();
  mesobBody.innerHTML = renderMesobMetrics(settings.mesobData);
  const mesobController = mountSlider(mesobBody, settings.sliderInterval);
  if (mesobController) {
    controllers.push(mesobController);
  }

  try {
    const response = await fetch(settings.faydaEndpoint, {
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    faydaBody.innerHTML = renderFaydaMetrics(payload?.data || {});
    const faydaController = mountSlider(faydaBody, settings.sliderInterval);
    if (faydaController) {
      controllers.push(faydaController);
    }
  } catch (_error) {
    renderError(faydaBody, "Unable to load Fayda summary right now.");
  }

  return {
    destroy() {
      controllers.forEach((controller) => controller.stop());
    },
  };
}

export const SummaryPanels = {
  init(elementOrSelector, options = {}) {
    const element =
      typeof elementOrSelector === "string"
        ? document.querySelector(elementOrSelector)
        : elementOrSelector;
    return mountSummaryPanels(element, options);
  },
  initAll(selector = "[data-summary-panels]", options = {}) {
    return Promise.all(
      Array.from(document.querySelectorAll(selector)).map((element) =>
        mountSummaryPanels(element, options)
      )
    );
  },
};

window.SummaryPanels = SummaryPanels;
