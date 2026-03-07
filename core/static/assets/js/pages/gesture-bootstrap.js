import { initGestureControl } from "../gesture/index.js";

const GESTURE_ENABLED_STORAGE_KEY = "digital-hub:gesture-control:enabled";

const DEFAULT_PAGE_GESTURE_CONFIG = {
  maxHands: 2,
  minHandPresenceScore: 0.45,
  clickCooldownMs: 700,
  smoothFactor: 0.38,
  pointerSmoothFactor: 0.36,
  directionBias: 1.2,
  scrollDirectionDelta: 0.015,
  scrollHoldFrames: 1,
  scrollRepeatMs: 55,
  scrollStepPx: 160,
  continuousOpenPalmUpEnabled: false,
  continuousOpenPalmUpY: 0.42,
  continuousOpenPalmDownY: 0.58,
  continuousOpenPalmFingerMargin: 0.03,
  continuousOpenPalmDirectionLockMs: 260,
  navigateDirectionDelta: 0.03,
  navigateHoldFrames: 2,
  navigateCooldownMs: 900,
  zoomDistanceDeadzone: 0.012,
  zoomHoldFrames: 2,
  zoomRepeatMs: 100,
  zoomStepScale: 0.08
};

function isGesturePersistedEnabled() {
  try {
    return localStorage.getItem(GESTURE_ENABLED_STORAGE_KEY) === "1";
  } catch (_error) {
    return false;
  }
}

function persistGestureEnabled(enabled) {
  try {
    localStorage.setItem(GESTURE_ENABLED_STORAGE_KEY, enabled ? "1" : "0");
  } catch (_error) {
    // Ignore storage errors (private mode / blocked storage).
  }
}

export function bootPageGestureControl(config = {}) {
  const existing = window.appGestureController;
  if (existing && typeof existing.destroy === "function") {
    existing.destroy();
  }

  const controller = initGestureControl({
    ui: {
      showFloatingToggle: false
    },
    config: {
      ...DEFAULT_PAGE_GESTURE_CONFIG,
      ...config
    }
  });

  // Keep old global for backward compatibility with existing scripts.
  window.dashboardGestureController = controller;
  window.appGestureController = controller;

  const originalEnable = controller.enable.bind(controller);
  const originalDisable = controller.disable.bind(controller);
  const originalToggle = controller.toggle.bind(controller);

  controller.enable = async (...args) => {
    const result = await originalEnable(...args);
    if (controller.isEnabled()) {
      persistGestureEnabled(true);
    }
    return result;
  };

  controller.disable = (...args) => {
    const result = originalDisable(...args);
    persistGestureEnabled(false);
    return result;
  };

  controller.toggle = (...args) => originalToggle(...args);

  if (isGesturePersistedEnabled()) {
    controller.enable();
  }

  return controller;
}
