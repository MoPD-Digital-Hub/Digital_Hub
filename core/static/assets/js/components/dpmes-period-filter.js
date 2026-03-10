import { resolveDefaultTime } from "./default-time.js";
import { resolveDpmesYears } from "./dpmes-years.js";

const QUARTER_OPTIONS = [
  { value: "3month", label: "Q1" },
  { value: "6month", label: "Q2" },
  { value: "9month", label: "Q3" },
  { value: "12month", label: "Q4" },
];

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function getFallbackYears({ startYear = 2010, endYear = new Date().getFullYear() } = {}) {
  const years = [];
  for (let year = Number(endYear); year >= Number(startYear); year -= 1) {
    years.push({ value: String(year), label: String(year) });
  }
  return years;
}

function renderPeriodOptions(periodSelect, years, state) {
  if (!periodSelect) {
    return;
  }

  if (state.dateType === "yearly") {
    periodSelect.innerHTML = years
      .map(
        (year) =>
          `<option value="${escapeHtml(year.value)}"${
            String(year.value) === String(state.year) ? " selected" : ""
          }>${escapeHtml(year.label)}</option>`
      )
      .join("");
    return;
  }

  periodSelect.innerHTML = years
    .map((year) => {
      const options = QUARTER_OPTIONS.map((quarter) => {
        const optionValue = `${year.value}|${quarter.value}`;
        const isSelected = String(year.value) === String(state.year) && quarter.value === state.quarter;
        return `<option value="${escapeHtml(optionValue)}"${
          isSelected ? " selected" : ""
        }>${escapeHtml(year.label)}-${escapeHtml(quarter.label)}</option>`;
      }).join("");

      return `<optgroup label="${escapeHtml(year.label)}">${options}</optgroup>`;
    })
    .join("");
}

function buildQueryParams(state) {
  const params = new URLSearchParams();
  params.set("year", state.year);
  if (state.dateType === "quarterly") {
    params.set("quarter", state.quarter);
  }
  return params;
}

function syncUI(root, state, selectors) {
  const dateTypeButtons = root.querySelectorAll(selectors.dateTypeButtons);
  const periodSelect = root.querySelector(selectors.periodSelect);

  dateTypeButtons.forEach((button) => {
    const isActive = button.dataset.value === state.dateType;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-pressed", isActive ? "true" : "false");
  });

  renderPeriodOptions(periodSelect, state.years, state);
}

export async function createDpmesPeriodFilter(root, options = {}) {
  const selectors = {
    dateTypeButtons: options.dateTypeButtonsSelector || "[data-dpmes-date-type-btn]",
    periodSelect: options.periodSelectSelector || "[data-dpmes-period]",
  };

  const fallback = {
    year: options.initialState?.year || String(new Date().getFullYear()),
    quarter: options.initialState?.quarter || "3month",
    dateType: options.initialState?.dateType || "quarterly",
  };

  const years = await resolveDpmesYears({
    endpoint: options.yearsEndpoint || "/api/mobile/dpmes-year-lists/",
    fallback: getFallbackYears({
      startYear: options.startYear || 2010,
      endYear: options.endYear || new Date().getFullYear(),
    }),
  });

  const defaults = await resolveDefaultTime({
    endpoint: options.defaultTimeEndpoint || "/api/mobile/default-time/",
    fallback,
  });

  const state = {
    year: options.initialState?.year || defaults.year,
    quarter: options.initialState?.quarter || defaults.quarter,
    dateType: options.initialState?.dateType || defaults.dateType,
    years,
  };

  const api = {
    getState() {
      return { ...state };
    },
    getQueryParams() {
      return buildQueryParams(state);
    },
    getQueryString() {
      return buildQueryParams(state).toString();
    },
    buildEndpoint(baseEndpoint) {
      const query = buildQueryParams(state).toString();
      return `${baseEndpoint}?${query}`;
    },
  };

  const periodSelect = root.querySelector(selectors.periodSelect);
  const dateTypeButtons = root.querySelectorAll(selectors.dateTypeButtons);

  syncUI(root, state, selectors);

  dateTypeButtons.forEach((button) => {
    button.addEventListener("click", async () => {
      if (button.dataset.value === state.dateType) {
        return;
      }
      state.dateType = button.dataset.value;
      syncUI(root, state, selectors);
      if (state.dateType === "yearly") {
        state.year = periodSelect.value;
      } else {
        const [year, quarter] = String(periodSelect.value).split("|");
        state.year = year;
        state.quarter = quarter || "3month";
      }
      if (typeof options.onChange === "function") {
        await options.onChange(api.getState(), "date_type", api);
      }
    });
  });

  if (periodSelect) {
    periodSelect.addEventListener("change", async (event) => {
      if (state.dateType === "yearly") {
        state.year = event.target.value;
      } else {
        const [year, quarter] = String(event.target.value).split("|");
        state.year = year;
        state.quarter = quarter || state.quarter;
      }
      if (typeof options.onChange === "function") {
        await options.onChange(api.getState(), "period", api);
      }
    });
  }

  return api;
}
