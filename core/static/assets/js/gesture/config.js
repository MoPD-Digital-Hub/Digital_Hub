export const DEFAULT_GESTURE_CONFIG = {
  maxHands: 2,
  minHandPresenceScore: 0.45,
  smoothFactor: 0.46,
  pointerSmoothFactor: 0.48,
  fingerStateMargin: 0.018,
  clickPinchDistance: 0.05,
  clickPinchReleaseDistance: 0.075,
  clickCooldownMs: 380,
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
  zoomStepScale: 0.08,
  zoomMinScale: 0.7,
  zoomMaxScale: 2.2,
  targetOutlineMs: 260,
  gestureLabelHoldMs: 500,
  handLostPauseMs: 180,
  pointerFallback: { x: 0.5, y: 0.35 }
};

export const GESTURE_NAME = {
  IDLE: "Idle",
  SCROLL_UP: "Scroll Up",
  SCROLL_DOWN: "Scroll Down",
  SCROLL_LEFT: "Scroll Left",
  SCROLL_RIGHT: "Scroll Right",
  NAVIGATE_BACK: "Back",
  NAVIGATE_FORWARD: "Forward",
  CLICK: "Click",
  ZOOM_IN: "Zoom In",
  ZOOM_OUT: "Zoom Out"
};

export const LOAD_STATE = {
  IDLE: "idle",
  LOADING: "loading",
  READY: "ready",
  ERROR: "error"
};
