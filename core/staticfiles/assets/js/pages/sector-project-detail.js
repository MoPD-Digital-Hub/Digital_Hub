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

function parseJsonArray(value) {
  if (!value) {
    return [];
  }

  if (Array.isArray(value)) {
    return value.filter(Boolean);
  }

  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed.filter(Boolean) : [];
  } catch (_error) {
    return [];
  }
}

function toNumber(value) {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }

  if (typeof value !== "string") {
    return null;
  }

  const normalized = value.replaceAll(",", "").trim();
  if (!normalized) {
    return null;
  }

  const numeric = Number(normalized);
  return Number.isFinite(numeric) ? numeric : null;
}

function clampPercent(value) {
  const numeric = toNumber(value);
  if (numeric === null) {
    return null;
  }

  return Math.max(0, Math.min(100, numeric));
}

function getScoreTone(value) {
  const percent = clampPercent(value);
  if (percent === null) {
    return "#e2e8f0";
  }
  if (percent >= 85) {
    return "#16a34a";
  }
  if (percent >= 65) {
    return "#d97706";
  }
  return "#dc2626";
}

function getPrimaryRecord(project) {
  const rows = Array.isArray(project?.data) ? project.data : [];
  return rows.find((row) =>
    Object.values(row || {}).some((value) => String(value ?? "").trim() && String(value ?? "").trim() !== "[]")
  ) || null;
}

function summarizeInvestment(projects) {
  let withInvestment = 0;

  projects.forEach((project) => {
    const primary = getPrimaryRecord(project);
    if (primary?.["Amount of investment"]) {
      withInvestment += 1;
    }
  });

  return withInvestment;
}

function collectGalleryImages(projects, mediaBaseUrl) {
  const images = [];

  projects.forEach((project) => {
    const primary = getPrimaryRecord(project);
    const pictureList = parseJsonArray(primary?.Pictures);
    pictureList.forEach((item) => {
      const url = buildMediaUrl(item, mediaBaseUrl);
      if (url && !images.includes(url)) {
        images.push(url);
      }
    });
  });

  return images.slice(0, 8);
}

function createProjectNavigator(projects, currentProjectId, detailBase) {
  if (!Array.isArray(projects) || !projects.length) {
    return "";
  }

  const base = detailBase || "/dashboard/projects/sector/";
  const filtered = projects.filter((item) => item?.is_initiative !== true);
  const currentIndex = filtered.findIndex((item) => Number(item?.id) === Number(currentProjectId));
  const previous = currentIndex > 0 ? filtered[currentIndex - 1] : null;
  const next = currentIndex >= 0 && currentIndex < filtered.length - 1 ? filtered[currentIndex + 1] : null;
  return `
    <div class="sector-project-hero__navigator">
      <div class="sector-project-hero__navigator-head">
        <span>Project Navigation</span>
        <div class="sector-project-hero__navigator-controls">
          ${
            previous
              ? `<a class="sector-project-hero__nav-btn" href="${escapeHtml(`${String(base).replace(/\/?$/, "/")}${previous.id}/`)}" aria-label="Previous project"><i class="ti ti-arrow-left"></i></a>`
              : `<span class="sector-project-hero__nav-btn is-disabled" aria-hidden="true"><i class="ti ti-arrow-left"></i></span>`
          }
          ${
            next
              ? `<a class="sector-project-hero__nav-btn" href="${escapeHtml(`${String(base).replace(/\/?$/, "/")}${next.id}/`)}" aria-label="Next project"><i class="ti ti-arrow-right"></i></a>`
              : `<span class="sector-project-hero__nav-btn is-disabled" aria-hidden="true"><i class="ti ti-arrow-right"></i></span>`
          }
        </div>
      </div>
      <div class="sector-project-hero__navigator-list">
        ${filtered
          .map((item) => {
            const title = item?.title_ENG || item?.title_AMH || `Project ${item?.id ?? ""}`;
            const active = Number(item?.id) === Number(currentProjectId);
            const target = `${String(base).replace(/\/?$/, "/")}${item.id}/`;
            return `<a class="sector-project-hero__nav-pill${active ? " is-active" : ""}" href="${escapeHtml(target)}">${escapeHtml(title)}</a>`;
          })
          .join("")}
      </div>
    </div>
  `;
}

function createHero(project, mediaBaseUrl, stats, navigation = {}) {
  const title = project?.title_ENG || project?.title_AMH || "Sector Project";
  const description = project?.description || "Project details are not available.";
  const image = buildMediaUrl(project?.image, mediaBaseUrl);
  const icon = buildMediaUrl(project?.image_icons, mediaBaseUrl);

  return `
    <section class="sector-project-hero">
      ${
        image
          ? `<img class="sector-project-hero__media" src="${escapeHtml(image)}" alt="${escapeHtml(title)}" loading="eager" decoding="async">`
          : `<div class="sector-project-hero__fallback" aria-hidden="true"></div>`
      }
      <div class="sector-project-hero__overlay"></div>
      <div class="sector-project-hero__content">
        <div class="sector-project-hero__top">
          ${createProjectNavigator(navigation.projects, navigation.currentProjectId, navigation.detailBase)}
          <span class="sector-project-hero__chip">
            <i class="ti ti-layout-grid"></i>
            ${stats.subProjectCount} sub-project${stats.subProjectCount === 1 ? "" : "s"}
          </span>
        </div>
        <div class="sector-project-hero__body">
          ${icon ? `<span class="sector-project-hero__icon"><img src="${escapeHtml(icon)}" alt="${escapeHtml(title)} icon" loading="eager" decoding="async"></span>` : ""}
          <h1 class="sector-project-hero__title">${escapeHtml(title)}</h1>
          <p class="sector-project-hero__description">${escapeHtml(description)}</p>
        </div>
      </div>
    </section>
  `;
}

function createStats(stats) {
  return `
    <section class="sector-project-stats">
      <article class="sector-project-stat">
        <span class="sector-project-stat__label">Sub-projects</span>
        <p class="sector-project-stat__value">${stats.subProjectCount}</p>
      </article>
      <article class="sector-project-stat">
        <span class="sector-project-stat__label">With investment data</span>
        <p class="sector-project-stat__value">${stats.investmentCount}</p>
      </article>
      <article class="sector-project-stat">
        <span class="sector-project-stat__label">Regional split</span>
        <p class="sector-project-stat__value">${stats.regionalCount}</p>
      </article>
      <article class="sector-project-stat">
        <span class="sector-project-stat__label">Gallery images</span>
        <p class="sector-project-stat__value">${stats.galleryCount}</p>
      </article>
    </section>
  `;
}

function createScorePanel(label, percent, tone) {
  if (percent === null) {
    return "";
  }

  return `
    <div class="sub-project-score-panel" style="--sub-project-score-tone:${escapeHtml(tone)};">
      <div class="sub-project-score-panel__value">${percent.toFixed(2)}%</div>
      <div class="sub-project-score-panel__meta">
        <strong>${escapeHtml(label)}</strong>
        <span>Current completion ratio</span>
      </div>
    </div>
  `;
}

function createPerformanceBlock(title, plan, performance, percent, tone) {
  const hasPlan = plan !== null && String(plan ?? "").trim() !== "";
  const hasPerformance = performance !== null && String(performance ?? "").trim() !== "";

  if (!hasPlan && !hasPerformance && percent === null) {
    return "";
  }

  return `
    <section class="sub-project-performance">
      <div class="sub-project-performance__head">
        <div>
          <h4>${escapeHtml(title)}</h4>
          <p>Up-to-date delivery snapshot</p>
        </div>
        ${percent !== null ? `<span class="sub-project-performance__badge" style="color:${escapeHtml(tone)};">${percent.toFixed(2)}%</span>` : ""}
      </div>
      <div class="sub-project-performance__compare">
        <div class="sub-project-performance__metric sub-project-performance__metric--plan">
          <span>Plan</span>
          <strong>${escapeHtml(plan || "Not available")}</strong>
        </div>
        <div class="sub-project-performance__arrow" aria-hidden="true">
          <i class="ti ti-arrow-right"></i>
        </div>
        <div class="sub-project-performance__metric sub-project-performance__metric--performance">
          <span>Performance</span>
          <strong>${escapeHtml(performance || "Not available")}</strong>
        </div>
      </div>
      ${createScorePanel(`${title}`, percent, tone)}
    </section>
  `;
}

function createFact(label, value) {
  if (!value || String(value).trim().toLowerCase() === "none") {
    return "";
  }

  return `
    <div class="sub-project-card__fact">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </div>
  `;
}

function createSubProjectCard(project, mediaBaseUrl) {
  const primary = getPrimaryRecord(project);
  const title = project?.title_ENG || project?.title_AMH || primary?.Name || "Sub-project";
  const description = primary?.Description || project?.description || "No detailed description is available for this sub-project.";
  const pictureList = parseJsonArray(primary?.Pictures);
  const image = buildMediaUrl(pictureList[0] || project?.image, mediaBaseUrl);
  const udpp = clampPercent(primary?.["UDPP-Percentage"]);
  const udfp = clampPercent(primary?.["UDFP-Percentage"]);
  const badgeValue = udpp ?? udfp;
  const udppPlan = primary?.["UDPP-Plan"];
  const udppPerformance = primary?.["UDPP-Performance"];
  const udfpPlan = primary?.["UDFP-Plan"];
  const udfpPerformance = primary?.["UDFP-Performance"];
  const meta = [
    primary?.["Potential"] ? `${primary["Potential"]}` : "",
    primary?.["Number of beneficiaries"] ? `${primary["Number of beneficiaries"]} beneficiaries` : "",
    project?.is_regional ? "Regional" : "Federal",
  ].filter(Boolean);
  const location = primary?.Location || "Location not available";
  const investment = primary?.["Amount of investment"] || "Investment not available";

  return `
    <article class="sub-project-card" data-sub-project-card>
      <div class="sub-project-card__media">
        ${image ? `<img src="${escapeHtml(image)}" alt="${escapeHtml(title)}" loading="lazy" decoding="async">` : ""}
        <div class="sub-project-card__overlay"></div>
        <div class="sub-project-card__hero">
          <div class="sub-project-card__eyebrow">
            <span class="sub-project-card__kind">${project?.is_regional ? "Regional Project" : "Sector Project"}</span>
            ${badgeValue !== null ? `
              <span class="sub-project-card__score" style="--sub-project-score:${escapeHtml(badgeValue.toFixed(1))}; --sub-project-score-angle:${escapeHtml((badgeValue * 3.6).toFixed(2))}deg; --sub-project-score-color:${escapeHtml(getScoreTone(badgeValue))};">
                <strong>${badgeValue.toFixed(1)}%</strong>
              </span>
            ` : ""}
          </div>
          <h3 class="sub-project-card__title">${escapeHtml(title)}</h3>
        </div>
      </div>
      <div class="sub-project-card__body">
        <div class="sub-project-card__summary">
          <div class="sub-project-card__summary-item">
            <span>Location</span>
            <strong>${escapeHtml(location)}</strong>
          </div>
          <div class="sub-project-card__summary-item">
            <span>Investment</span>
            <strong>${escapeHtml(investment)}</strong>
          </div>
        </div>

        <p class="sub-project-card__description">${escapeHtml(description)}</p>

        <div class="sub-project-card__actions">
          <button type="button" class="sub-project-card__toggle" data-sub-project-toggle aria-expanded="false">
            <span>Show more</span>
            <i class="ti ti-chevron-down"></i>
          </button>
        </div>

        <div class="sub-project-card__details" data-sub-project-details hidden>
          <div class="sub-project-card__facts">
            ${createFact("Location", primary?.Location)}
            ${createFact("Investment", primary?.["Amount of investment"])}
            ${createFact("Start date", primary?.["Start date"])}
            ${createFact("End date", primary?.["End date"])}
          </div>

          <div class="sub-project-card__progress">
            ${createPerformanceBlock("Physical performance", udppPlan, udppPerformance, udpp, "#0f766e")}
            ${createPerformanceBlock("Financial performance", udfpPlan, udfpPerformance, udfp, "#d97706")}
          </div>

          ${meta.length ? `<div class="sub-project-card__meta">${meta.map((item) => `<span class="sub-project-chip">${escapeHtml(item)}</span>`).join("")}</div>` : ""}
        </div>
      </div>
    </article>
  `;
}

function createGallery(images) {
  if (!images.length) {
    return "";
  }

  return `
    <section class="sector-project-section">
      <div class="sector-project-section__head">
        <div>
          <h2>Project Gallery</h2>
          <p>Transition through representative visuals pulled from the sub-project media records.</p>
        </div>
      </div>
      <div class="sector-project-gallery" data-project-gallery data-gallery-count="${images.length}">
        <div class="sector-project-gallery__stage">
          ${images
            .map(
              (image, index) => `
                <figure class="sector-project-gallery__slide${index === 0 ? " is-active" : ""}" data-gallery-slide>
                  <img src="${escapeHtml(image)}" alt="Project image ${index + 1}" loading="${index === 0 ? "eager" : "lazy"}" decoding="async">
                </figure>
              `
            )
            .join("")}
          <div class="sector-project-gallery__controls">
            <button type="button" class="sector-project-gallery__nav" data-gallery-prev aria-label="Previous image">
              <i class="ti ti-arrow-left"></i>
            </button>
            <div class="sector-project-gallery__counter" data-gallery-counter>1 / ${images.length}</div>
            <button type="button" class="sector-project-gallery__nav" data-gallery-next aria-label="Next image">
              <i class="ti ti-arrow-right"></i>
            </button>
          </div>
        </div>
        <div class="sector-project-gallery__thumbs">
          ${images
            .map(
              (image, index) => `
                <button type="button" class="sector-project-gallery__thumb${index === 0 ? " is-active" : ""}" data-gallery-thumb data-index="${index}" aria-label="Show image ${index + 1}">
                  <img src="${escapeHtml(image)}" alt="" loading="lazy" decoding="async">
                </button>
              `
            )
            .join("")}
        </div>
      </div>
    </section>
  `;
}

function initGallery(container) {
  const gallery = container.querySelector("[data-project-gallery]");
  if (!gallery) {
    return;
  }

  const slides = Array.from(gallery.querySelectorAll("[data-gallery-slide]"));
  const thumbs = Array.from(gallery.querySelectorAll("[data-gallery-thumb]"));
  const prev = gallery.querySelector("[data-gallery-prev]");
  const next = gallery.querySelector("[data-gallery-next]");
  const counter = gallery.querySelector("[data-gallery-counter]");

  if (!slides.length) {
    return;
  }

  let activeIndex = 0;
  let timer = null;

  const render = (index) => {
    activeIndex = (index + slides.length) % slides.length;
    slides.forEach((slide, slideIndex) => {
      slide.classList.toggle("is-active", slideIndex === activeIndex);
    });
    thumbs.forEach((thumb, thumbIndex) => {
      thumb.classList.toggle("is-active", thumbIndex === activeIndex);
    });
    if (counter) {
      counter.textContent = `${activeIndex + 1} / ${slides.length}`;
    }
  };

  const start = () => {
    if (slides.length < 2 || timer) {
      return;
    }
    timer = window.setInterval(() => render(activeIndex + 1), 3600);
  };

  const stop = () => {
    if (!timer) {
      return;
    }
    window.clearInterval(timer);
    timer = null;
  };

  prev?.addEventListener("click", () => {
    stop();
    render(activeIndex - 1);
    start();
  });

  next?.addEventListener("click", () => {
    stop();
    render(activeIndex + 1);
    start();
  });

  thumbs.forEach((thumb) => {
    thumb.addEventListener("click", () => {
      stop();
      render(Number(thumb.dataset.index || 0));
      start();
    });
  });

  gallery.addEventListener("mouseenter", stop);
  gallery.addEventListener("mouseleave", start);

  render(0);
  start();
}

function createSubProjects(projects, mediaBaseUrl) {
  return `
    <section class="sector-project-section" data-sub-project-section>
      <div class="sector-project-section__head">
        <div>
          <h2>Sub-project Delivery</h2>
          <p>Review the project set page by page and expand only the records you want in detail.</p>
        </div>
      </div>
      <div class="sector-project-grid" data-sub-project-grid></div>
      <div class="sector-project-pagination" data-sub-project-pagination></div>
      <template data-sub-project-template>${projects.map((project) => createSubProjectCard(project, mediaBaseUrl)).join("")}</template>
    </section>
  `;
}

function initSubProjectCards(scope) {
  scope.querySelectorAll("[data-sub-project-card]").forEach((card) => {
    const toggle = card.querySelector("[data-sub-project-toggle]");
    const details = card.querySelector("[data-sub-project-details]");
    const label = toggle?.querySelector("span");

    if (!toggle || !details || !label) {
      return;
    }

    toggle.addEventListener("click", () => {
      const expanded = toggle.getAttribute("aria-expanded") === "true";
      toggle.setAttribute("aria-expanded", expanded ? "false" : "true");
      details.hidden = expanded;
      label.textContent = expanded ? "Show more" : "Collapse";
      card.classList.toggle("is-expanded", !expanded);
    });
  });
}

function initSubProjectSection(container) {
  const section = container.querySelector("[data-sub-project-section]");
  const grid = section?.querySelector("[data-sub-project-grid]");
  const pager = section?.querySelector("[data-sub-project-pagination]");
  const template = section?.querySelector("[data-sub-project-template]");

  if (!section || !grid || !pager || !template) {
    return;
  }

  const holder = document.createElement("div");
  holder.innerHTML = template.innerHTML.trim();
  const cards = Array.from(holder.children);
  const pageSize = 4;
  const pageCount = Math.max(1, Math.ceil(cards.length / pageSize));
  let currentPage = 1;

  const renderPager = () => {
    if (pageCount <= 1) {
      pager.innerHTML = "";
      return;
    }

    pager.innerHTML = `
      <button type="button" class="sector-project-pagination__btn" data-page-prev ${currentPage === 1 ? "disabled" : ""}>
        <i class="ti ti-arrow-left"></i>
      </button>
      <div class="sector-project-pagination__pages">
        ${Array.from({ length: pageCount }, (_, index) => {
          const page = index + 1;
          return `<button type="button" class="sector-project-pagination__page${page === currentPage ? " is-active" : ""}" data-page="${page}">${page}</button>`;
        }).join("")}
      </div>
      <button type="button" class="sector-project-pagination__btn" data-page-next ${currentPage === pageCount ? "disabled" : ""}>
        <i class="ti ti-arrow-right"></i>
      </button>
    `;

    pager.querySelector("[data-page-prev]")?.addEventListener("click", () => renderPage(currentPage - 1));
    pager.querySelector("[data-page-next]")?.addEventListener("click", () => renderPage(currentPage + 1));
    pager.querySelectorAll("[data-page]").forEach((button) => {
      button.addEventListener("click", () => renderPage(Number(button.dataset.page)));
    });
  };

  const renderPage = (page) => {
    currentPage = Math.max(1, Math.min(pageCount, page));
    const start = (currentPage - 1) * pageSize;
    const items = cards.slice(start, start + pageSize);
    grid.innerHTML = "";
    items.forEach((card) => grid.appendChild(card.cloneNode(true)));
    initSubProjectCards(grid);
    renderPager();
    section.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  renderPage(1);
}

function renderDetail(container, project, mediaBaseUrl, navigation) {
  const projects = Array.isArray(project?.sub_projects?.projects) ? project.sub_projects.projects : [];
  const galleryImages = collectGalleryImages(projects, mediaBaseUrl);
  const stats = {
    subProjectCount: projects.length,
    investmentCount: summarizeInvestment(projects),
    regionalCount: projects.filter((item) => item?.is_regional).length,
    galleryCount: galleryImages.length,
  };

  container.innerHTML = [
    createHero(project, mediaBaseUrl, stats, navigation),
    createStats(stats),
    createSubProjects(projects, mediaBaseUrl),
    createGallery(galleryImages),
  ].join("");

  initSubProjectSection(container);
  initGallery(container);
}

async function initProjectDetail() {
  const container = document.querySelector("[data-project-detail]");
  if (!container) {
    return;
  }

  const state = container.querySelector("[data-project-detail-state]");
  const endpoint = container.dataset.endpoint;
  const listEndpoint = container.dataset.listEndpoint;
  const detailBase = container.dataset.detailBase || "/dashboard/projects/sector/";
  const currentProjectId = Number(container.dataset.projectId || 0);
  const mediaBaseUrl = container.dataset.mediaBaseUrl || "https://time-series.mopd.gov.et/";

  if (!endpoint || !state) {
    return;
  }

  try {
    const [detailResponse, listResponse] = await Promise.all([
      fetch(endpoint, {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      }),
      fetch(listEndpoint, {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      }),
    ]);

    if (!detailResponse.ok) {
      throw new Error(`HTTP ${detailResponse.status}`);
    }

    const detailPayload = await detailResponse.json();
    const listPayload = listResponse.ok ? await listResponse.json() : { data: [] };
    const project = detailPayload?.data;
    const navigation = {
      projects: Array.isArray(listPayload?.data) ? listPayload.data : [],
      currentProjectId,
      detailBase,
    };

    if (!project) {
      state.textContent = "Project detail is not available right now.";
      return;
    }

    renderDetail(container, project, mediaBaseUrl, navigation);
  } catch (_error) {
    state.textContent = "Unable to load the selected project right now.";
  }
}

document.addEventListener("DOMContentLoaded", initProjectDetail);
