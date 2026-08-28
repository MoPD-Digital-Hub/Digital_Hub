import { isVisible, getElementLabel } from "./utils.js";

const CLICKABLE_SELECTOR = [
  "button",
  "a[href]",
  "[role='button']",
  "[role='link']",
  "input:not([type='hidden'])",
  "select",
  "textarea",
  "summary",
  "[data-gesture-clickable]",
  "[tabindex]:not([tabindex='-1'])"
].join(",");

const ZOOMABLE_SELECTOR = [
  "[data-gesture-zoomable]",
  "canvas",
  "svg",
  "img",
  ".apexcharts-canvas",
  ".mapboxgl-map",
  ".leaflet-container"
].join(",");

function canInteract(el) {
  if (!el || !(el instanceof HTMLElement)) {
    return false;
  }
  const style = getComputedStyle(el);
  return style.pointerEvents !== "none" && style.visibility !== "hidden" && style.display !== "none";
}

function isScrollable(el, axis) {
  if (!el || !(el instanceof HTMLElement)) {
    return false;
  }
  const style = getComputedStyle(el);
  const overflow = axis === "x" ? style.overflowX : style.overflowY;
  const size = axis === "x"
    ? { scroll: el.scrollWidth, client: el.clientWidth }
    : { scroll: el.scrollHeight, client: el.clientHeight };
  return size.scroll > size.client + 2 && /(auto|scroll|overlay)/.test(overflow);
}

function findAncestor(start, matcher) {
  let node = start;
  while (node && node !== document.documentElement) {
    if (matcher(node)) {
      return node;
    }
    node = node.parentElement;
  }
  return null;
}

export function resolveTarget(pointer) {
  const x = Math.round(pointer.x * window.innerWidth);
  const y = Math.round(pointer.y * window.innerHeight);
  const element = document.elementFromPoint(x, y) || document.body;

  const clickable = findAncestor(element, (node) => {
    return node.matches && node.matches(CLICKABLE_SELECTOR) && canInteract(node) && isVisible(node);
  });

  const vScrollable = findAncestor(element, (node) => isScrollable(node, "y") && canInteract(node));
  const hScrollable = findAncestor(element, (node) => isScrollable(node, "x") && canInteract(node));
  const zoomable = findAncestor(element, (node) => {
    return node.matches && node.matches(ZOOMABLE_SELECTOR) && canInteract(node) && isVisible(node);
  });

  return {
    point: { x, y },
    element,
    label: getElementLabel(clickable || zoomable || hScrollable || vScrollable || element),
    clickable,
    verticalScrollable: vScrollable,
    horizontalScrollable: hScrollable,
    zoomable
  };
}
