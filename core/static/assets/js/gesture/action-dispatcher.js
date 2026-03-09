import { clamp } from "./utils.js";

function scrollWindow(dx, dy) {
  window.scrollBy({
    left: dx,
    top: dy,
    behavior: "smooth"
  });
}

export class ActionDispatcher {
  constructor(config = {}) {
    this.config = config;
    this.pageScale = 1;
  }

  _applyScroll(target, action) {
    const dx = Number.isFinite(action.dx) ? action.dx : 0;
    const dy = Number.isFinite(action.dy) ? action.dy : 0;

    if (Math.abs(dx) > 0.5) {
      if (target.horizontalScrollable) {
        target.horizontalScrollable.scrollBy({ left: dx, behavior: "smooth" });
      } else {
        scrollWindow(dx, 0);
      }
    }

    if (Math.abs(dy) > 0.5) {
      if (target.verticalScrollable) {
        target.verticalScrollable.scrollBy({ top: dy, behavior: "smooth" });
      } else {
        scrollWindow(0, dy);
      }
    }
  }

  _applyClick(target) {
    const clickable = target.clickable || target.element;
    if (!clickable || typeof clickable.dispatchEvent !== "function") {
      return;
    }
    const clientX = Number.isFinite(target?.point?.x) ? target.point.x : 0;
    const clientY = Number.isFinite(target?.point?.y) ? target.point.y : 0;
    const eventInit = { bubbles: true, cancelable: true, clientX, clientY };

    clickable.dispatchEvent(new MouseEvent("mousedown", eventInit));
    clickable.dispatchEvent(new MouseEvent("mouseup", eventInit));
    if (typeof clickable.click === "function") {
      clickable.click();
    } else {
      clickable.dispatchEvent(new MouseEvent("click", eventInit));
    }
  }

  _applyZoom(_target, action) {
    const root = document.documentElement;
    if (!root || !Number.isFinite(action.deltaScale)) {
      return;
    }

    const nextScale = clamp(
      this.pageScale + action.deltaScale,
      this.config.zoomMinScale,
      this.config.zoomMaxScale
    );

    this.pageScale = nextScale;

    // Apply zoom at the document level so the whole window scales.
    root.style.zoom = nextScale.toFixed(3);
  }

  _applyNavigate(action) {
    if (!action || action.type !== "navigate") {
      return;
    }

    if (action.direction === "back") {
      if (window.history.length > 1) {
        window.history.back();
      }
      return;
    }

    if (action.direction === "forward") {
      window.history.forward();
    }
  }

  reset() {
    this.pageScale = 1;
    const root = document.documentElement;
    if (root) {
      root.style.zoom = "";
    }
  }

  dispatch(target, recognition) {
    if (!recognition || recognition.isPaused || !recognition.action) {
      return;
    }

    const action = recognition.action;
    if (action.type === "scroll") {
      this._applyScroll(target, action);
      return;
    }

    if (action.type === "click") {
      this._applyClick(target);
      return;
    }

    if (action.type === "zoom") {
      this._applyZoom(target, action);
      return;
    }

    if (action.type === "navigate") {
      this._applyNavigate(action);
    }
  }
}
