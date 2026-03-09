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



mountWhenVisible("[data-summary-panels]", (element) => SummaryPanels.init(element));
mountWhenVisible("[data-high-frequency]", (element) => HighFrequencyIndicators.init(element));
mountWhenVisible("[data-project-strip]", (element) => ProjectStrip.init(element));
mountWhenVisible("[data-initiative-spotlight]", (element) => InitiativeSpotlight.init(element));
TopicScroller.initAll("[data-topic-scroller]");
MinistryScorecard.initAll("[data-ministry-scorecard]");
SummaryPanels.initAll("[data-summary-panels]");
HighFrequencyIndicators.initAll("[data-high-frequency]");
ProjectStrip.initAll("[data-project-strip]");
InitiativeSpotlight.initAll("[data-initiative-spotlight]");

// Mark major dashboard sections as zoomable surfaces for two-hand zoom gestures.
document.querySelectorAll(
  ".summary-panels, .hf-section, .project-strip, .initiative-section, [data-gesture-zoomable]"
).forEach((element) => {
  if (!element.hasAttribute("data-gesture-zoomable")) {
    element.setAttribute("data-gesture-zoomable", "true");
  }
});
