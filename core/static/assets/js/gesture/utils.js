export function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

export function lerp(from, to, t) {
  return from + (to - from) * clamp(t, 0, 1);
}

export function smoothPoint(prev, next, factor) {
  if (!prev) {
    return next;
  }
  return {
    x: lerp(prev.x, next.x, factor),
    y: lerp(prev.y, next.y, factor),
    z: lerp(prev.z || 0, next.z || 0, factor)
  };
}

export function distance(a, b) {
  if (!a || !b) {
    return Infinity;
  }
  const dx = a.x - b.x;
  const dy = a.y - b.y;
  const dz = (a.z || 0) - (b.z || 0);
  return Math.sqrt(dx * dx + dy * dy + dz * dz);
}

export function nowMs() {
  return performance.now();
}

export function isVisible(el) {
  if (!el) {
    return false;
  }
  const style = getComputedStyle(el);
  if (style.visibility === "hidden" || style.display === "none") {
    return false;
  }
  const rect = el.getBoundingClientRect();
  return rect.width > 0 && rect.height > 0;
}

export function getElementLabel(el) {
  if (!el || !(el instanceof Element)) {
    return "Page";
  }
  const role = el.getAttribute("role");
  if (el.dataset.gestureLabel) {
    return el.dataset.gestureLabel;
  }
  if (el.getAttribute("aria-label")) {
    return el.getAttribute("aria-label");
  }
  if (el.tagName === "BUTTON") {
    return (el.textContent || "Button").trim() || "Button";
  }
  if (el.tagName === "A") {
    return (el.textContent || "Link").trim() || "Link";
  }
  if (role) {
    return role;
  }
  return el.className?.split?.(" ")?.find(Boolean) || el.tagName.toLowerCase();
}
