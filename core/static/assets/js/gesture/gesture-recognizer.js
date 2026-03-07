import { DEFAULT_GESTURE_CONFIG, GESTURE_NAME } from "./config.js";
import { clamp, distance, smoothPoint, nowMs } from "./utils.js";

const WRIST = 0;
const THUMB_TIP = 4;
const INDEX_TIP = 8;
const INDEX_PIP = 6;
const MIDDLE_TIP = 12;
const MIDDLE_PIP = 10;
const RING_TIP = 16;
const RING_PIP = 14;
const PINKY_TIP = 20;
const PINKY_PIP = 18;

const SCROLL_DIRECTIONS = ["up", "down", "left", "right"];
const NAVIGATE_DIRECTIONS = ["left", "right"];
const ZOOM_DIRECTIONS = ["in", "out"];

function smoothLandmarks(previous, next, factor) {
  if (!previous || previous.length !== next.length) {
    return next;
  }
  return next.map((point, i) => smoothPoint(previous[i], point, factor));
}

function handCenter(landmarks) {
  let x = 0;
  let y = 0;
  for (let i = 0; i < landmarks.length; i += 1) {
    x += landmarks[i].x;
    y += landmarks[i].y;
  }
  return { x: x / landmarks.length, y: y / landmarks.length, z: 0 };
}

function makeCounter(keys) {
  const state = {};
  for (const key of keys) {
    state[key] = 0;
  }
  return state;
}

export class GestureRecognizer {
  constructor(config = {}) {
    this.config = { ...DEFAULT_GESTURE_CONFIG, ...config };
    this.previousHands = [];
    this.previousWrist = null;
    this.previousNavigateWrist = null;
    this.previousTwoHandDistance = null;
    this.pointer = { ...this.config.pointerFallback };

    this.pinched = false;
    this.lastClickAt = 0;
    this.lastScrollAt = 0;
    this.lastContinuousDirection = null;
    this.lastContinuousDirectionAt = 0;
    this.lastNavigateAt = 0;
    this.lastZoomAt = 0;
    this.lastHandSeenAt = 0;

    this.scrollCounters = makeCounter(SCROLL_DIRECTIONS);
    this.navigateCounters = makeCounter(NAVIGATE_DIRECTIONS);
    this.zoomCounters = makeCounter(ZOOM_DIRECTIONS);
  }

  _normalizeHands(rawHands) {
    const validHands = rawHands
      .filter((hand) => hand && Array.isArray(hand.landmarks) && hand.score >= this.config.minHandPresenceScore)
      .slice(0, this.config.maxHands);

    return validHands.map((hand, idx) => {
      const previous = this.previousHands[idx];
      const landmarks = smoothLandmarks(previous?.landmarks, hand.landmarks, this.config.smoothFactor);
      return {
        ...hand,
        landmarks,
        center: handCenter(landmarks)
      };
    });
  }

  _fingerExtended(landmarks, tip, pip) {
    return landmarks[tip].y < landmarks[pip].y - this.config.fingerStateMargin;
  }

  _fingerFolded(landmarks, tip, pip) {
    return landmarks[tip].y > landmarks[pip].y + this.config.fingerStateMargin;
  }

  _fingerOpen(landmarks, tip, pip) {
    // Orientation-agnostic finger openness: tip must be farther from wrist than PIP.
    const wrist = landmarks[WRIST];
    const tipDistance = distance(landmarks[tip], wrist);
    const pipDistance = distance(landmarks[pip], wrist);
    return tipDistance > pipDistance + this.config.fingerStateMargin * 1.2;
  }

  _isScrollPose(landmarks) {
    // Scroll uses a dedicated two-finger pose for more stable directional control.
    return (
      this._fingerExtended(landmarks, INDEX_TIP, INDEX_PIP) &&
      this._fingerExtended(landmarks, MIDDLE_TIP, MIDDLE_PIP) &&
      this._fingerFolded(landmarks, RING_TIP, RING_PIP) &&
      this._fingerFolded(landmarks, PINKY_TIP, PINKY_PIP)
    );
  }

  _isOpenPalmPose(landmarks) {
    return (
      this._fingerOpen(landmarks, INDEX_TIP, INDEX_PIP) &&
      this._fingerOpen(landmarks, MIDDLE_TIP, MIDDLE_PIP) &&
      this._fingerOpen(landmarks, RING_TIP, RING_PIP) &&
      this._fingerOpen(landmarks, PINKY_TIP, PINKY_PIP)
    );
  }

  _isNavigatePose(landmarks) {
    // Straight hand for browser navigation: index finger up, others folded.
    return (
      this._fingerExtended(landmarks, INDEX_TIP, INDEX_PIP) &&
      this._fingerFolded(landmarks, MIDDLE_TIP, MIDDLE_PIP) &&
      this._fingerFolded(landmarks, RING_TIP, RING_PIP) &&
      this._fingerFolded(landmarks, PINKY_TIP, PINKY_PIP)
    );
  }

  _isClickPose(landmarks) {
    // Specific click pose: thumb-index pinch while middle/ring/pinky are folded.
    return (
      this._fingerFolded(landmarks, MIDDLE_TIP, MIDDLE_PIP) &&
      this._fingerFolded(landmarks, RING_TIP, RING_PIP) &&
      this._fingerFolded(landmarks, PINKY_TIP, PINKY_PIP)
    );
  }

  _resolveContinuousOpenPalmDirection(landmarks) {
    if (!this._isOpenPalmPose(landmarks)) {
      return null;
    }

    const wristY = landmarks[WRIST].y;
    const avgTipY = (
      landmarks[INDEX_TIP].y +
      landmarks[MIDDLE_TIP].y +
      landmarks[RING_TIP].y +
      landmarks[PINKY_TIP].y
    ) / 4;
    const margin = this.config.continuousOpenPalmFingerMargin ?? 0.03;

    // Open palm held up (fingers above wrist) => keep scrolling down to bottom.
    if (
      this.config.continuousOpenPalmUpEnabled !== false &&
      wristY <= (this.config.continuousOpenPalmUpY ?? 0.42) &&
      avgTipY < wristY - margin
    ) {
      return "down";
    }

    // Open palm reversed/inverted (fingers below wrist) => keep scrolling up to top.
    if (
      wristY >= (this.config.continuousOpenPalmDownY ?? 0.58) &&
      avgTipY > wristY + margin
    ) {
      return "up";
    }

    return null;
  }

  _buildPointer(primaryHand) {
    if (!primaryHand) {
      return this.pointer;
    }
    const index = primaryHand.landmarks[INDEX_TIP];
    const rawPointer = {
      x: clamp(1 - index.x, 0, 1),
      y: clamp(index.y, 0, 1)
    };
    this.pointer = {
      x: clamp(this.pointer.x + (rawPointer.x - this.pointer.x) * this.config.pointerSmoothFactor, 0, 1),
      y: clamp(this.pointer.y + (rawPointer.y - this.pointer.y) * this.config.pointerSmoothFactor, 0, 1)
    };
    return this.pointer;
  }

  _incCounter(counterMap, key) {
    for (const counterKey of Object.keys(counterMap)) {
      counterMap[counterKey] = counterKey === key ? counterMap[counterKey] + 1 : 0;
    }
  }

  _resetCounters(counterMap) {
    for (const key of Object.keys(counterMap)) {
      counterMap[key] = 0;
    }
  }

  _resolveScrollDirection(deltaX, deltaY) {
    const absX = Math.abs(deltaX);
    const absY = Math.abs(deltaY);

    if (absX < this.config.scrollDirectionDelta && absY < this.config.scrollDirectionDelta) {
      return null;
    }

    if (absX > absY * this.config.directionBias) {
      return deltaX > 0 ? "right" : "left";
    }

    if (absY > absX * this.config.directionBias) {
      return deltaY > 0 ? "down" : "up";
    }

    return null;
  }

  _clickAction(primaryHand, timestamp) {
    if (!primaryHand) {
      this.pinched = false;
      return null;
    }

    const landmarks = primaryHand.landmarks;
    const pinchDistance = distance(landmarks[THUMB_TIP], landmarks[INDEX_TIP]);
    const relaxedClickDistance = this.config.clickPinchDistance * 1.25;
    const releaseDistance = this.config.clickPinchReleaseDistance * 1.1;

    if (!this.pinched && pinchDistance < relaxedClickDistance) {
      this.pinched = true;
      if (timestamp - this.lastClickAt > this.config.clickCooldownMs) {
        this.lastClickAt = timestamp;
        return { type: "click" };
      }
    } else if (this.pinched && pinchDistance > releaseDistance) {
      this.pinched = false;
    }

    return null;
  }

  _scrollAction(primaryHand, timestamp, handsCount = 0) {
    if (!primaryHand || handsCount !== 1) {
      this.previousWrist = null;
      this._resetCounters(this.scrollCounters);
      return null;
    }

    const landmarks = primaryHand.landmarks;
    const wrist = landmarks[WRIST];

    if (!this._isScrollPose(landmarks)) {
      this.previousWrist = wrist;
      this._resetCounters(this.scrollCounters);
      return null;
    }

    // Continuous scrolling based on static open-palm hold orientation.
    const continuousDirection = this._resolveContinuousOpenPalmDirection(landmarks);
    const lockMs = this.config.continuousOpenPalmDirectionLockMs ?? 260;
    const canReuseLockedDirection = (
      this._isOpenPalmPose(landmarks) &&
      this.lastContinuousDirection &&
      (timestamp - this.lastContinuousDirectionAt) < lockMs
    );
    const stableContinuousDirection = continuousDirection || (canReuseLockedDirection ? this.lastContinuousDirection : null);

    if (stableContinuousDirection) {
      this.lastContinuousDirection = stableContinuousDirection;
      this.lastContinuousDirectionAt = timestamp;
      if (timestamp - this.lastScrollAt < this.config.scrollRepeatMs) {
        return null;
      }
      this.lastScrollAt = timestamp;
      const step = this.config.scrollStepPx;
      if (stableContinuousDirection === "down") {
        return { type: "scroll", dx: 0, dy: step, gestureName: GESTURE_NAME.SCROLL_DOWN };
      }
      return { type: "scroll", dx: 0, dy: -step, gestureName: GESTURE_NAME.SCROLL_UP };
    }

    if (this._isOpenPalmPose(landmarks)) {
      this.lastContinuousDirection = null;
      this._resetCounters(this.scrollCounters);
      // Keep open-palm behavior stable and avoid jittery fallback swipe actions.
      return null;
    }

    if (!this.previousWrist) {
      this.previousWrist = wrist;
      return null;
    }

    const deltaX = wrist.x - this.previousWrist.x;
    const deltaY = wrist.y - this.previousWrist.y;
    this.previousWrist = wrist;

    const direction = this._resolveScrollDirection(deltaX, deltaY);
    if (!direction) {
      this._resetCounters(this.scrollCounters);
      return null;
    }

    this._incCounter(this.scrollCounters, direction);
    if (this.scrollCounters[direction] < this.config.scrollHoldFrames) {
      return null;
    }

    if (timestamp - this.lastScrollAt < this.config.scrollRepeatMs) {
      return null;
    }
    this.lastScrollAt = timestamp;

    const step = this.config.scrollStepPx;
    if (direction === "up") {
      // User requested inverted vertical movement: moving hand up scrolls page down.
      return { type: "scroll", dx: 0, dy: step, gestureName: GESTURE_NAME.SCROLL_UP };
    }
    if (direction === "down") {
      // User requested inverted vertical movement: moving hand down scrolls page up.
      return { type: "scroll", dx: 0, dy: -step, gestureName: GESTURE_NAME.SCROLL_DOWN };
    }
    if (direction === "left") {
      return { type: "scroll", dx: -step, dy: 0, gestureName: GESTURE_NAME.SCROLL_LEFT };
    }
    return { type: "scroll", dx: step, dy: 0, gestureName: GESTURE_NAME.SCROLL_RIGHT };
  }

  _navigateAction(primaryHand, timestamp, handsCount = 0) {
    if (!primaryHand || handsCount !== 1) {
      this.previousNavigateWrist = null;
      this._resetCounters(this.navigateCounters);
      return null;
    }

    const landmarks = primaryHand.landmarks;
    const wrist = landmarks[WRIST];

    if (!this._isNavigatePose(landmarks)) {
      this.previousNavigateWrist = wrist;
      this._resetCounters(this.navigateCounters);
      return null;
    }

    if (!this.previousNavigateWrist) {
      this.previousNavigateWrist = wrist;
      return null;
    }

    const deltaX = wrist.x - this.previousNavigateWrist.x;
    const deltaY = wrist.y - this.previousNavigateWrist.y;
    this.previousNavigateWrist = wrist;

    const absX = Math.abs(deltaX);
    const absY = Math.abs(deltaY);
    if (absX < this.config.navigateDirectionDelta || absX < absY * 1.2) {
      this._resetCounters(this.navigateCounters);
      return null;
    }

    const direction = deltaX > 0 ? "right" : "left";
    this._incCounter(this.navigateCounters, direction);
    if (this.navigateCounters[direction] < this.config.navigateHoldFrames) {
      return null;
    }

    if (timestamp - this.lastNavigateAt < this.config.navigateCooldownMs) {
      return null;
    }
    this.lastNavigateAt = timestamp;

    return direction === "left"
      ? { type: "navigate", direction: "back", gestureName: GESTURE_NAME.NAVIGATE_BACK }
      : { type: "navigate", direction: "forward", gestureName: GESTURE_NAME.NAVIGATE_FORWARD };
  }

  _zoomAction(hands, timestamp) {
    if (hands.length < 2) {
      this.previousTwoHandDistance = null;
      this._resetCounters(this.zoomCounters);
      return null;
    }

    const [a, b] = hands;
    if (!this._isOpenPalmPose(a.landmarks) || !this._isOpenPalmPose(b.landmarks)) {
      this.previousTwoHandDistance = distance(a.center, b.center);
      this._resetCounters(this.zoomCounters);
      return null;
    }

    const currentDistance = distance(a.center, b.center);
    if (!this.previousTwoHandDistance) {
      this.previousTwoHandDistance = currentDistance;
      return null;
    }

    const delta = currentDistance - this.previousTwoHandDistance;
    this.previousTwoHandDistance = currentDistance;

    if (Math.abs(delta) < this.config.zoomDistanceDeadzone) {
      this._resetCounters(this.zoomCounters);
      return null;
    }

    const direction = delta > 0 ? "in" : "out";
    this._incCounter(this.zoomCounters, direction);

    if (this.zoomCounters[direction] < this.config.zoomHoldFrames) {
      return null;
    }

    if (timestamp - this.lastZoomAt < this.config.zoomRepeatMs) {
      return null;
    }
    this.lastZoomAt = timestamp;

    return {
      type: "zoom",
      deltaScale: direction === "in" ? this.config.zoomStepScale : -this.config.zoomStepScale,
      gestureName: direction === "in" ? GESTURE_NAME.ZOOM_IN : GESTURE_NAME.ZOOM_OUT
    };
  }

  recognize(frame) {
    const timestamp = frame.timestamp || nowMs();
    const hands = this._normalizeHands(frame.hands || []);
    this.previousHands = hands;

    if (!hands.length) {
      const pause = timestamp - this.lastHandSeenAt >= this.config.handLostPauseMs;
      return {
        pointer: this.pointer,
        handsCount: 0,
        confidence: 0,
        gestureName: GESTURE_NAME.IDLE,
        action: null,
        isPaused: pause
      };
    }

    this.lastHandSeenAt = timestamp;

    const primaryHand = hands[0];
    const pointer = this._buildPointer(primaryHand);
    const confidence = clamp(
      hands.reduce((max, hand) => Math.max(max, hand.score), 0),
      0,
      1
    );

    const clickAction = this._clickAction(primaryHand, timestamp);
    if (clickAction) {
      return {
        pointer,
        handsCount: hands.length,
        confidence,
        gestureName: GESTURE_NAME.CLICK,
        action: clickAction,
        isPaused: false
      };
    }

    const zoomAction = this._zoomAction(hands, timestamp);
    if (zoomAction) {
      return {
        pointer,
        handsCount: hands.length,
        confidence,
        gestureName: zoomAction.gestureName,
        action: zoomAction,
        isPaused: false
      };
    }

    const navigateAction = this._navigateAction(primaryHand, timestamp, hands.length);
    if (navigateAction) {
      return {
        pointer,
        handsCount: hands.length,
        confidence,
        gestureName: navigateAction.gestureName,
        action: navigateAction,
        isPaused: false
      };
    }

    const scrollAction = this._scrollAction(primaryHand, timestamp, hands.length);
    if (scrollAction) {
      return {
        pointer,
        handsCount: hands.length,
        confidence,
        gestureName: scrollAction.gestureName,
        action: scrollAction,
        isPaused: false
      };
    }

    return {
      pointer,
      handsCount: hands.length,
      confidence,
      gestureName: GESTURE_NAME.IDLE,
      action: null,
      isPaused: false
    };
  }
}
