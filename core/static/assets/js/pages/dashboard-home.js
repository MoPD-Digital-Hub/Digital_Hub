import { TopicScroller } from "../components/topic-scroller.js";
import { MinistryScorecard } from "../components/ministry-scorecard.js";
import { SummaryPanels } from "../components/summary-panels.js";
import { HighFrequencyIndicators } from "../components/high-frequency-indicators.js";
import { ProjectStrip } from "../components/project-strip.js";
import { InitiativeSpotlight } from "../components/initiative-spotlight.js";
import { PolicyAreaScorecard } from "../components/policy-area-scorecard.js";

TopicScroller.initAll("[data-topic-scroller]");
MinistryScorecard.initAll("[data-ministry-scorecard]");
SummaryPanels.initAll("[data-summary-panels]");
HighFrequencyIndicators.initAll("[data-high-frequency]");
ProjectStrip.initAll("[data-project-strip]");
InitiativeSpotlight.initAll("[data-initiative-spotlight]");
PolicyAreaScorecard.initAll("[data-policy-area-scorecard]");
