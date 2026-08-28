# Gesture Control Module

## What it provides
- Real-time hand tracking from webcam (`hand-tracker.js`) using MediaPipe Hands Tasks.
- Gesture recognition (`gesture-recognizer.js`) for:
  - `Scroll up/down/left/right` with a strict pose: index + middle fingers up, ring + pinky folded, then directional swipe.
  - `Click` with a strict pose: index up, ring + pinky folded, then thumb-middle pinch.
  - `Zoom in/out` with strict two-hand pose: both hands open (all fingers extended), then move hands apart/together.
- DOM target resolution (`target-resolver.js`) for clickable, scrollable, and zoomable elements.
- Action dispatch (`action-dispatcher.js`) for page-level and component-level interactions.
- Floating feedback UI (`feedback-overlay.js`) with enable/disable toggle, camera/hand state, gesture, target, and confidence.

## Targeting behavior
1. Pointer location is mapped from primary hand index fingertip.
2. `document.elementFromPoint()` resolves hovered element.
3. Resolver derives the nearest:
   - clickable target
   - vertical scroll container
   - horizontal scroll container
   - zoomable container
4. Dispatch rules:
   - If a local scroll container exists, scroll it.
   - Otherwise, scroll the page.
   - Zoom applies to the full page window (`document.documentElement`) instead of a specific component.
   - Click triggers on nearest clickable ancestor.

## Threshold tuning
Edit [`config.js`](/home/kaleab/Projects/Digital_Hub/core/static/assets/js/gesture/config.js):
- `minHandPresenceScore`: minimum confidence before actions are allowed.
- `scrollDirectionDelta`, `scrollHoldFrames`, `scrollRepeatMs`, `scrollStepPx`: directional stability and scroll pacing.
- `clickPinchDistance`, `clickPinchReleaseDistance`, `clickCooldownMs`: click stability and repeat protection.
- `zoomDistanceDeadzone`, `zoomHoldFrames`, `zoomRepeatMs`, `zoomStepScale`, `zoomMinScale`, `zoomMaxScale`: zoom stability and bounds.
- `smoothFactor`, `pointerSmoothFactor`: landmark and cursor smoothing.

## Add a new gesture
1. Add a recognizer branch in `GestureRecognizer.recognize()`.
2. Emit a normalized action object: `{ type: "your-action", ...payload }`.
3. Implement handling in `ActionDispatcher.dispatch()`.
4. Update help text in `feedback-overlay.js`.
5. If needed, extend target rules in `target-resolver.js`.

## Integration example
The dashboard integration is in:
- [`dashboard-home.js`](/home/kaleab/Projects/Digital_Hub/core/static/assets/js/pages/dashboard-home.js)
- [`sample.html`](/home/kaleab/Projects/Digital_Hub/core/templates/dashboard/sample.html)

Use `initGestureControl()` from [`index.js`](/home/kaleab/Projects/Digital_Hub/core/static/assets/js/gesture/index.js).
