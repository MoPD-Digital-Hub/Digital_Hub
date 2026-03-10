import { DEFAULT_GESTURE_CONFIG, GESTURE_NAME, LOAD_STATE } from "./config.js";
import { HandTracker } from "./hand-tracker.js";
import { GestureRecognizer } from "./gesture-recognizer.js";
import { resolveTarget } from "./target-resolver.js";
import { ActionDispatcher } from "./action-dispatcher.js";
import { GestureFeedbackOverlay } from "./feedback-overlay.js";

export class GestureController {
  constructor(options = {}) {
    this.config = {
      ...DEFAULT_GESTURE_CONFIG,
      ...(options.config || {})
    };

    this.enabled = false;
    this.overlay = new GestureFeedbackOverlay({
      showFloatingToggle: options.ui?.showFloatingToggle,
      onToggle: (enabled) => {
        if (enabled) {
          this.enable();
        } else {
          this.disable();
        }
      }
    });

    this.overlay.mount();
    this.overlay.setEnabled(false);

    this.recognizer = new GestureRecognizer(this.config);
    this.dispatcher = new ActionDispatcher(this.config);

    this.tracker = new HandTracker({
      maxHands: this.config.maxHands,
      minPresenceConfidence: this.config.minHandPresenceScore,
      previewCanvas: this.overlay.previewCanvas,
      onStateChange: (state, error) => {
        this.overlay.setCameraState(state, error);
        if (state === LOAD_STATE.ERROR) {
          this.overlay.update({
            gesture: "Unavailable",
            target: error?.name === "NotAllowedError" ? "Camera permission denied" : "Camera failed"
          });
          this.disable();
        }
      },
      onResults: (frame) => this._onFrame(frame)
    });

    this.lastVisibleGesture = GESTURE_NAME.IDLE;
    this.lastGestureAt = 0;
  }

  async enable() {
    if (this.enabled) {
      return;
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      this.overlay.update({
        camera: "Unsupported",
        target: "No camera API",
        gesture: "Unavailable"
      });
      return;
    }

    this.enabled = true;
    this._emitState();
    this.overlay.setEnabled(true);
    this.overlay.update({
      hands: "0",
      gesture: GESTURE_NAME.IDLE,
      target: "Page",
      confidence: "0%"
    });

    try {
      await this.tracker.start();
    } catch (error) {
      this.overlay.setCameraState(LOAD_STATE.ERROR, error);
      this.overlay.update({
        target: error?.name === "NotAllowedError" ? "Camera permission denied" : "Camera unavailable",
        gesture: "Unavailable"
      });
      this.enabled = false;
      this._emitState();
      this.overlay.setEnabled(false);
    }
  }

  disable() {
    if (!this.enabled && this.tracker.state === LOAD_STATE.IDLE) {
      this.overlay.setEnabled(false);
      return;
    }

    this.enabled = false;
    this._emitState();
    this.tracker.stop();
    this.dispatcher.reset();
    this.overlay.setEnabled(false);
    this.overlay.update({
      camera: "Idle",
      hands: "0",
      gesture: GESTURE_NAME.IDLE,
      target: "Page",
      confidence: "0%"
    });
  }

  toggle() {
    if (this.enabled) {
      this.disable();
      return;
    }
    this.enable();
  }

  isEnabled() {
    return this.enabled;
  }

  _emitState() {
    window.dispatchEvent(new CustomEvent("gesture-control:state", {
      detail: { enabled: this.enabled }
    }));
  }

  _resolveGestureLabel(recognition, now) {
    if (recognition.gestureName !== GESTURE_NAME.IDLE) {
      this.lastVisibleGesture = recognition.gestureName;
      this.lastGestureAt = now;
      return recognition.gestureName;
    }

    if (now - this.lastGestureAt < this.config.gestureLabelHoldMs) {
      return this.lastVisibleGesture;
    }

    return GESTURE_NAME.IDLE;
  }

  _onFrame(frame) {
    if (!this.enabled) {
      return;
    }

    const recognition = this.recognizer.recognize(frame);
    const target = resolveTarget(recognition.pointer || this.config.pointerFallback);

    const now = performance.now();
    const gestureLabel = recognition.isPaused ? "Paused" : this._resolveGestureLabel(recognition, now);

    this.overlay.movePointer(recognition.pointer);
    this.overlay.update({
      hands: String(recognition.handsCount),
      gesture: gestureLabel,
      target: recognition.action?.type === "zoom" ? "Page" : target.label,
      confidence: `${Math.round(recognition.confidence * 100)}%`
    });

    if (!recognition.isPaused) {
      try {
        this.dispatcher.dispatch(target, recognition);
      } catch (error) {
        console.error("Gesture action failed:", error);
      }
    }
  }

  destroy() {
    this.disable();
    this.overlay.unmount();
  }
}

export function initGestureControl(options = {}) {
  return new GestureController(options);
}
