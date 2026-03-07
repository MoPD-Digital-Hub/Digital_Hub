import { LOAD_STATE } from "./config.js";

const MEDIAPIPE_CDN = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.18/+esm";
const MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task";

export class HandTracker {
  constructor(options = {}) {
    this.options = options;
    this.video = null;
    this.stream = null;
    this.handLandmarker = null;
    this.vision = null;
    this.state = LOAD_STATE.IDLE;
    this.animationFrameId = null;
    this.onStateChange = options.onStateChange || (() => {});
    this.onResults = options.onResults || (() => {});
    this.previewCanvas = options.previewCanvas || null;
    this.previewCtx = this.previewCanvas ? this.previewCanvas.getContext("2d") : null;
    this._lastTimestamp = -1;
  }

  async _loadModel() {
    if (this.handLandmarker) {
      return;
    }
    this.state = LOAD_STATE.LOADING;
    this.onStateChange(this.state);

    try {
      const mp = await import(MEDIAPIPE_CDN);
      const { FilesetResolver, HandLandmarker } = mp;
      this.vision = await FilesetResolver.forVisionTasks(
        "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.18/wasm"
      );
      this.handLandmarker = await HandLandmarker.createFromOptions(this.vision, {
        baseOptions: {
          modelAssetPath: MODEL_URL,
          delegate: "GPU"
        },
        runningMode: "VIDEO",
        numHands: this.options.maxHands || 2,
        minHandDetectionConfidence: this.options.minDetectionConfidence || 0.6,
        minHandPresenceConfidence: this.options.minPresenceConfidence || 0.55,
        minTrackingConfidence: this.options.minTrackingConfidence || 0.55
      });
      this.state = LOAD_STATE.READY;
      this.onStateChange(this.state);
    } catch (error) {
      this.state = LOAD_STATE.ERROR;
      this.onStateChange(this.state, error);
      throw error;
    }
  }

  async _ensureVideo() {
    if (this.video) {
      return;
    }
    const video = document.createElement("video");
    video.setAttribute("playsinline", "");
    video.setAttribute("muted", "");
    video.muted = true;
    video.autoplay = true;
    video.style.position = "fixed";
    video.style.right = "-9999px";
    video.style.bottom = "-9999px";
    video.style.width = "1px";
    video.style.height = "1px";
    video.style.opacity = "0";
    video.style.pointerEvents = "none";
    video.setAttribute("aria-hidden", "true");
    document.body.appendChild(video);
    this.video = video;
  }

  async start() {
    await this._loadModel();
    await this._ensureVideo();

    this.stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: "user",
        width: { ideal: 960 },
        height: { ideal: 540 }
      },
      audio: false
    });

    this.video.srcObject = this.stream;
    await this.video.play();
    this._lastTimestamp = -1;
    this._loop();
  }

  _drawPreview(results) {
    if (!this.previewCtx || !this.previewCanvas || !this.video) {
      return;
    }

    const canvas = this.previewCanvas;
    const ctx = this.previewCtx;
    canvas.width = canvas.clientWidth || 260;
    canvas.height = canvas.clientHeight || 146;

    ctx.save();
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(this.video, 0, 0, canvas.width, canvas.height);

    const landmarks = results.landmarks || [];
    for (const hand of landmarks) {
      for (const point of hand) {
        const x = point.x * canvas.width;
        const y = point.y * canvas.height;
        ctx.beginPath();
        ctx.arc(x, y, 2.1, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(65, 206, 255, 0.95)";
        ctx.fill();
      }
    }

    ctx.restore();
  }

  _normalizeResults(results) {
    const hands = [];
    const landmarks = results.landmarks || [];
    const handednesses = results.handednesses || [];

    for (let i = 0; i < landmarks.length; i += 1) {
      const handednessInfo = handednesses[i] && handednesses[i][0] ? handednesses[i][0] : null;
      hands.push({
        landmarks: landmarks[i],
        handedness: handednessInfo?.categoryName || "Unknown",
        score: handednessInfo?.score || 0
      });
    }

    return hands;
  }

  _loop = () => {
    if (!this.video || !this.handLandmarker) {
      return;
    }

    const now = performance.now();
    if (this.video.currentTime !== this._lastTimestamp) {
      this._lastTimestamp = this.video.currentTime;
      const results = this.handLandmarker.detectForVideo(this.video, now);
      const hands = this._normalizeResults(results);
      this._drawPreview(results);
      this.onResults({
        timestamp: now,
        hands,
        videoSize: {
          width: this.video.videoWidth,
          height: this.video.videoHeight
        }
      });
    }

    this.animationFrameId = window.requestAnimationFrame(this._loop);
  };

  stop() {
    if (this.animationFrameId) {
      window.cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }

    if (this.stream) {
      for (const track of this.stream.getTracks()) {
        track.stop();
      }
      this.stream = null;
    }

    if (this.video) {
      this.video.pause();
      this.video.srcObject = null;
      this.video.remove();
      this.video = null;
    }

    if (this.previewCtx && this.previewCanvas) {
      this.previewCtx.clearRect(0, 0, this.previewCanvas.width, this.previewCanvas.height);
    }

    this.state = LOAD_STATE.IDLE;
    this.onStateChange(this.state);
  }
}
