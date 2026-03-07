import { TopicScroller } from "../components/topic-scroller.js";
import { MinistryScorecard } from "../components/ministry-scorecard.js";
import { SummaryPanels } from "../components/summary-panels.js";
import { HighFrequencyIndicators } from "../components/high-frequency-indicators.js";
import { ProjectStrip } from "../components/project-strip.js";
import { InitiativeSpotlight } from "../components/initiative-spotlight.js";
import { bootPageGestureControl } from "./gesture-bootstrap.js";

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

bootPageGestureControl();
