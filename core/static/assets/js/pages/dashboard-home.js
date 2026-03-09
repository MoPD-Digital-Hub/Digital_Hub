import { TopicScroller } from "../components/topic-scroller.js?v=20260307a";
import { MinistryScorecard } from "../components/ministry-scorecard.js";
import { SummaryPanels } from "../components/summary-panels.js";
import { HighFrequencyIndicators } from "../components/high-frequency-indicators.js";
import { ProjectStrip } from "../components/project-strip.js";
import { InitiativeSpotlight } from "../components/initiative-spotlight.js";
import { resolveDefaultTime } from "../components/default-time.js";

function mountWhenVisible(selector, mount) {
  const element = document.querySelector(selector);
  if (!element) {
    return;
  }

  let mounted = false;
  const runMount = () => {
    if (mounted) {
      return;
    }
    mounted = true;
    mount(element);
  };

  if (!("IntersectionObserver" in window)) {
    runMount();
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      const entry = entries[0];
      if (!entry?.isIntersecting) {
        return;
      }
      observer.disconnect();
      runMount();
    },
    {
      rootMargin: "320px 0px",
      threshold: 0.01,
    }
  );

  observer.observe(element);
}

TopicScroller.init(document.querySelector("[data-topic-scroller]"));
const ministryElement = document.querySelector("[data-ministry-scorecard]");

async function mountHomeMinistryScorecard() {
  if (!ministryElement) {
    return;
  }

  const defaultTime = await resolveDefaultTime({
    endpoint: ministryElement.dataset.defaultTimeEndpoint || "/api/mobile/default-time/",
    fallback: {
      year: "2018",
      quarter: "3month",
      dateType: "quarterly",
    },
  });
  const params = new URLSearchParams();
  params.set("year", defaultTime.year);

  if (defaultTime.dateType === "quarterly" && defaultTime.quarter) {
    params.set("quarter", defaultTime.quarter);
  }

  const endpointBase = ministryElement.dataset.endpointBase || "/api/mobile/ministries/";
  ministryElement.dataset.endpoint = `${endpointBase}?${params.toString()}`;

  MinistryScorecard.init(ministryElement);
}

mountHomeMinistryScorecard();

mountWhenVisible("[data-summary-panels]", (element) => SummaryPanels.init(element));
mountWhenVisible("[data-high-frequency]", (element) => HighFrequencyIndicators.init(element));
mountWhenVisible("[data-project-strip]", (element) => ProjectStrip.init(element));
mountWhenVisible("[data-initiative-spotlight]", (element) => InitiativeSpotlight.init(element));
