import { LOAD_STATE } from "./config.js";

function createBadge(label, value, testId) {
  return `
    <div class="gesture-status-row" data-gesture-row="${testId}">
      <span class="gesture-status-label">${label}</span>
      <span class="gesture-status-value" data-gesture-value="${testId}">${value}</span>
    </div>
  `;
}

export class GestureFeedbackOverlay {
  constructor(options = {}) {
    this.options = options;
    this.showFloatingToggle = options.showFloatingToggle !== false;
    this.root = null;
    this.pointer = null;
    this.targetOutline = null;
    this.previewCanvas = null;
    this.statusMap = {};
  }

  mount() {
    if (this.root) {
      return;
    }

    const root = document.createElement("aside");
    root.className = "gesture-ui";
    root.innerHTML = `
      ${this.showFloatingToggle ? `
      <button type="button" class="gesture-toggle" data-gesture-toggle aria-pressed="false">
        <i class="ti ti-hand-stop"></i>
        <span>Enable Gesture Control</span>
      </button>` : ""}

      <section class="gesture-panel" data-gesture-panel hidden>
        <header class="gesture-panel-header">
          <h3>Gesture Control</h3>
          <span class="gesture-live-dot" data-gesture-live-dot></span>
        </header>
        <canvas class="gesture-preview" data-gesture-preview></canvas>
        <div class="gesture-status-list">
          ${createBadge("Camera", "Idle", "camera")}
          ${createBadge("Hands", "0", "hands")}
          ${createBadge("Gesture", "Idle", "gesture")}
          ${createBadge("Target", "Page", "target")}
          ${createBadge("Confidence", "0%", "confidence")}
        </div>
        <details class="gesture-help">
          <summary>Gestures and calibration</summary>
          <ul>
            <li>Scroll pose: index + middle up, ring + pinky folded, then move hand up/down/left/right</li>
            <li>Navigation pose: index finger up (other fingers folded), swipe left for back, right for next</li>
            <li>Click pose: pinch thumb + index while middle/ring/pinky stay folded</li>
            <li>Zoom pose: both hands open (all fingers up), move hands apart/together</li>
            <li>Keep your hand centered, with stable lighting and clear background</li>
          </ul>
        </details>
      </section>
    `;

    document.body.appendChild(root);
    this.root = root;

    this.pointer = document.createElement("div");
    this.pointer.className = "gesture-pointer";
    this.pointer.hidden = true;
    document.body.appendChild(this.pointer);

    this.targetOutline = document.createElement("div");
    this.targetOutline.className = "gesture-target-outline";
    this.targetOutline.hidden = true;
    document.body.appendChild(this.targetOutline);

    this.previewCanvas = root.querySelector("[data-gesture-preview]");
    const toggleButton = root.querySelector("[data-gesture-toggle]");
    if (toggleButton) {
      toggleButton.addEventListener("click", () => {
        const isEnabled = root.getAttribute("data-enabled") === "true";
        this.options.onToggle?.(!isEnabled);
      });
    }

    for (const entry of root.querySelectorAll("[data-gesture-value]")) {
      this.statusMap[entry.getAttribute("data-gesture-value")] = entry;
    }
  }

  unmount() {
    if (this.pointer) {
      this.pointer.remove();
      this.pointer = null;
    }
    if (this.targetOutline) {
      this.targetOutline.remove();
      this.targetOutline = null;
    }
    if (this.root) {
      this.root.remove();
      this.root = null;
    }
  }

  setEnabled(enabled) {
    if (!this.root) {
      return;
    }

    this.root.setAttribute("data-enabled", enabled ? "true" : "false");
    const toggle = this.root.querySelector("[data-gesture-toggle]");
    const panel = this.root.querySelector("[data-gesture-panel]");
    if (toggle) {
      toggle.setAttribute("aria-pressed", enabled ? "true" : "false");
      toggle.innerHTML = enabled
        ? '<i class="ti ti-hand-stop"></i><span>Disable Gesture Control</span>'
        : '<i class="ti ti-hand-stop"></i><span>Enable Gesture Control</span>';
    }
    panel.hidden = !enabled;
    this.pointer.hidden = !enabled;

    if (!enabled) {
      this.targetOutline.hidden = true;
    }
  }

  setCameraState(state, error) {
    const label = state === LOAD_STATE.READY
      ? "Active"
      : state === LOAD_STATE.LOADING
        ? "Loading"
        : state === LOAD_STATE.ERROR
          ? "Error"
          : "Idle";

    this.update({ camera: label });

    const dot = this.root?.querySelector("[data-gesture-live-dot]");
    if (dot) {
      dot.setAttribute("data-state", state);
      dot.title = error ? String(error.message || error) : label;
    }
  }

  update(fields = {}) {
    for (const [key, value] of Object.entries(fields)) {
      if (this.statusMap[key]) {
        this.statusMap[key].textContent = String(value);
      }
    }
  }

  movePointer(pointer) {
    if (!this.pointer || !pointer) {
      return;
    }
    const x = pointer.x * window.innerWidth;
    const y = pointer.y * window.innerHeight;
    this.pointer.style.transform = `translate(${x}px, ${y}px)`;
  }

  showTarget(element, holdMs = 250) {
    if (!this.targetOutline || !element || !(element instanceof HTMLElement)) {
      return;
    }

    const rect = element.getBoundingClientRect();
    if (rect.width < 2 || rect.height < 2) {
      this.targetOutline.hidden = true;
      return;
    }

    this.targetOutline.hidden = false;
    this.targetOutline.style.left = `${rect.left + window.scrollX}px`;
    this.targetOutline.style.top = `${rect.top + window.scrollY}px`;
    this.targetOutline.style.width = `${rect.width}px`;
    this.targetOutline.style.height = `${rect.height}px`;

    if (this._targetTimer) {
      clearTimeout(this._targetTimer);
    }

    this._targetTimer = setTimeout(() => {
      if (this.targetOutline) {
        this.targetOutline.hidden = true;
      }
    }, holdMs);
  }
}
