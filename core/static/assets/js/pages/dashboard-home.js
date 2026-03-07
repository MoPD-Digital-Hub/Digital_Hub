import { TopicScroller } from "../components/topic-scroller.js?v=20260307a";
import { MinistryScorecard } from "../components/ministry-scorecard.js";
import { SummaryPanels } from "../components/summary-panels.js";
import { HighFrequencyIndicators } from "../components/high-frequency-indicators.js";
import { ProjectStrip } from "../components/project-strip.js";
import { InitiativeSpotlight } from "../components/initiative-spotlight.js";

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
MinistryScorecard.init(document.querySelector("[data-ministry-scorecard]"));

mountWhenVisible("[data-summary-panels]", (element) => SummaryPanels.init(element));
mountWhenVisible("[data-high-frequency]", (element) => HighFrequencyIndicators.init(element));
mountWhenVisible("[data-project-strip]", (element) => ProjectStrip.init(element));
mountWhenVisible("[data-initiative-spotlight]", (element) => InitiativeSpotlight.init(element));
