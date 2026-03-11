import { DataTopicBrowser } from "../components/data-topic-browser.js?v=20260311a";
import { HighFrequencyIndicators } from "../components/high-frequency-indicators.js";

DataTopicBrowser.init("[data-topic-browser]");
HighFrequencyIndicators.init("[data-high-frequency]");

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function truncate(value, maxLength = 150) {
  const text = String(value ?? "").trim();
  if (!text) {
    return "";
  }
  return text.length > maxLength ? `${text.slice(0, maxLength).trim()}...` : text;
}

function flattenIndicatorResults(payload) {
  const categories = Array.isArray(payload?.data) ? payload.data : [];
  const indicatorMap = new Map();

  categories.forEach((category) => {
    const categoryName = category?.name_ENG || category?.name_AMH || "Category";
    const indicators = Array.isArray(category?.indicators) ? category.indicators : [];

    indicators.forEach((indicator) => {
      if (!indicator?.id) {
        return;
      }

      const existing = indicatorMap.get(String(indicator.id));
      if (existing) {
        existing.categories.add(categoryName);
        return;
      }

      indicatorMap.set(String(indicator.id), {
        id: indicator.id,
        code: indicator.code || "",
        title: indicator.title_ENG || indicator.title_AMH || "Indicator",
        description: indicator.description || "",
        latestValue: indicator.latest_data || "",
        categories: new Set([categoryName]),
      });
    });
  });

  return Array.from(indicatorMap.values())
    .map((indicator) => ({
      ...indicator,
      categories: Array.from(indicator.categories),
    }))
    .sort((left, right) => left.title.localeCompare(right.title));
}

function createSearchResultMarkup(indicator) {
  const chips = indicator.categories
    .slice(0, 2)
    .map((category) => `<span class="data-page-search-chip">${escapeHtml(category)}</span>`)
    .join("");
  const latestChip = indicator.latestValue
    ? `<span class="data-page-search-chip">Latest: ${escapeHtml(indicator.latestValue)}</span>`
    : "";

  return `
    <button
      type="button"
      class="data-page-search-item"
      data-indicator-search-item
      data-indicator-id="${escapeHtml(indicator.id)}"
      aria-label="Open ${escapeHtml(indicator.title)}"
    >
      <div class="data-page-search-item-topline">
        <span class="data-page-search-item-code">${escapeHtml(indicator.code || "Indicator")}</span>
        <span class="data-page-search-item-arrow" aria-hidden="true"><i class="ti ti-arrow-up-right"></i></span>
      </div>
      <div class="data-page-search-item-title">${escapeHtml(indicator.title)}</div>
      <div class="data-page-search-item-meta">
        ${chips}
        ${latestChip}
      </div>
      ${
        indicator.description
          ? `<div class="data-page-search-item-meta">${escapeHtml(truncate(indicator.description, 120))}</div>`
          : ""
      }
    </button>
  `;
}

function mountIndicatorSearch(element) {
  if (!element) {
    return;
  }

  const input = element.querySelector("[data-indicator-search-input]");
  const results = element.querySelector("[data-indicator-search-results]");
  const clearButton = element.querySelector("[data-indicator-search-clear]");

  if (!input || !results || !clearButton) {
    return;
  }

  let debounceTimer = null;
  let activeController = null;

  const setResultsState = (markup, { hidden = false } = {}) => {
    results.innerHTML = markup;
    results.hidden = hidden;
  };

  const closeResults = () => {
    setResultsState("", { hidden: true });
  };

  const openResults = () => {
    results.hidden = false;
  };

  const setLoading = () => {
    setResultsState('<div class="data-page-search-state">Searching indicators...</div>');
  };

  const setNoResults = () => {
    setResultsState('<div class="data-page-search-state">No indicators matched that search.</div>');
  };

  const setError = () => {
    setResultsState('<div class="data-page-search-state">Unable to search indicators right now.</div>');
  };

  const updateClearButton = () => {
    clearButton.hidden = !input.value.trim();
  };

  const renderResults = (items) => {
    if (!items.length) {
      setNoResults();
      return;
    }

    setResultsState(`<div class="data-page-search-list">${items.map(createSearchResultMarkup).join("")}</div>`);
    openResults();
  };

  const runSearch = async (query) => {
    if (activeController) {
      activeController.abort();
    }

    activeController = new AbortController();
    setLoading();

    try {
      const response = await fetch(`/api/mobile/general_search/?q=${encodeURIComponent(query)}`, {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
        signal: activeController.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = await response.json();
      const items = flattenIndicatorResults(payload);
      renderResults(items);
    } catch (error) {
      if (error.name === "AbortError") {
        return;
      }
      setError();
    }
  };

  input.addEventListener("input", () => {
    updateClearButton();
    const query = input.value.trim();

    window.clearTimeout(debounceTimer);

    if (!query || query.length < 2) {
      closeResults();
      if (activeController) {
        activeController.abort();
      }
      return;
    }

    debounceTimer = window.setTimeout(() => {
      runSearch(query);
    }, 260);
  });

  input.addEventListener("focus", () => {
    if (results.innerHTML.trim()) {
      openResults();
    }
  });

  clearButton.addEventListener("click", () => {
    input.value = "";
    updateClearButton();
    closeResults();
    input.focus();
  });

  results.addEventListener("click", (event) => {
    const button = event.target.closest("[data-indicator-search-item]");
    if (!button) {
      return;
    }
    window.location.assign(`/dashboard/data/indicator/${encodeURIComponent(button.dataset.indicatorId)}/`);
  });

  document.addEventListener("click", (event) => {
    if (!element.contains(event.target)) {
      closeResults();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeResults();
    }
  });
}

mountIndicatorSearch(document.querySelector("[data-indicator-search]"));
