(function () {
  const chatInput = document.getElementById("chatInput");
  const sendBtn = document.getElementById("sendBtn");
  const chatOutput = document.getElementById("chatOutput");
  const micBtn = document.getElementById("micBtn");
  const speechLangEnBtn = document.getElementById("speechLangEn");
  const speechLangAmBtn = document.getElementById("speechLangAm");
  const liveTranscript = document.getElementById("liveTranscript");
  const liveTranscriptLabel = document.getElementById("liveTranscriptLabel");
  const liveTranscriptText = document.getElementById("liveTranscriptText");
  const chatSearch = document.getElementById("chatSearch");
  const chatTitle = document.getElementById("chatTitle");
  const newInstanceBtn = document.getElementById("newInstanceBtn");
  const renameInstanceBtn = document.getElementById("renameInstanceBtn");
  const deleteInstanceBtn = document.getElementById("deleteInstanceBtn");
  const chatShell = document.getElementById("aiChatShell");
  const sidebarCollapseBtn = document.getElementById("sidebarCollapseBtn");
  const sidebarExpandBtn = document.getElementById("sidebarExpandBtn");

  if (!chatInput || !sendBtn || !chatOutput || !micBtn || !chatTitle) {
    return;
  }

  let instances = Array.from(document.querySelectorAll(".ai-instance"));
  const tags = Array.from(document.querySelectorAll(".ai-tag"));
  const quickTags = Array.from(document.querySelectorAll(".ai-quick-tag"));

  let selectedTag = "all";
  let currentRoom = chatOutput.dataset.room || "";
  let socket = null;
  let streamMessageElement = null;
  let streamHtmlBuffer = "";
  let pendingStreamRender = false;
  let loadingElement = null;
  let chartCounter = 0;
  const sidebarStorageKey = "admas-ai-sidebar-collapsed";
  const speechLanguageStorageKey = "admas-ai-speech-language";
  const aiAvatarSrc = "/static/assets/images/token-branded_ais.png";
  // Reuse generated speech per response text so repeated playback stays instant.
  const ttsAudioCache = new Map();
  const ttsRequestCache = new Map();
  const ttsWarmRequestCache = new Map();
  const translationCache = new Map();
  const translationSocketRequests = new Map();
  let activeTtsAudio = null;
  let activeTtsButton = null;
  let activeTtsObjectUrl = null;
  let activeTtsStreamSocket = null;
  let activeTtsAudioContext = null;
  let activeTtsNextTime = 0;
  const STREAMING_TTS_ENABLED = false;
  let currentSpeechLanguage = "en-US";
  let isVoiceRecording = false;
  let voiceTranscriptFinal = "";
  let voiceTranscriptInterim = "";
  let autoScrollPinned = true;
  let lastTouchY = 0;

  function buildAIMessageMarkup(contentHtml) {
    return (
      '<span class="msg-avatar" aria-hidden="true"><img class="msg-avatar-image" src="' + aiAvatarSrc + '" alt=""></span>' +
      '<div class="msg-bubble">' +
      '<div class="ai-msg-head">' +
      '<span class="ai-msg-brand"><i class="ti ti-sparkles"></i><span>Admas AI</span></span>' +
      '<div class="ai-msg-actions">' +
      '<button type="button" class="ai-translate-btn" title="Show Amharic translation" aria-label="Show Amharic translation">' +
      '<i class="ti ti-language-hiragana" aria-hidden="true"></i><span>Amharic</span>' +
      "</button>" +
      '<button type="button" class="ai-tts-btn" title="Listen to this response" aria-label="Listen to this response">' +
      '<i class="ti ti-player-play-filled" aria-hidden="true"></i><span>Listen</span>' +
      "</button>" +
      "</div>" +
      "</div>" +
      '<div class="ai-msg-content">' + contentHtml + "</div>" +
      '<div class="ai-msg-status" hidden></div>' +
      '<div class="ai-translation-panel" hidden>' +
      '<div class="ai-translation-head">' +
      '<div class="ai-translation-label">Amharic</div>' +
      '<button type="button" class="ai-translation-tts-btn" title="Listen to Amharic translation" aria-label="Listen to Amharic translation">' +
      '<i class="ti ti-player-play-filled" aria-hidden="true"></i><span>Speak</span>' +
      "</button>" +
      "</div>" +
      '<div class="ai-translation-content"></div>' +
      "</div>" +
      "</div>"
    );
  }

  function getThemeValue(name, fallback) {
    const value = window.getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return value || fallback;
  }

  function getAIChartTheme() {
    const accent = getThemeValue("--dh-accent", "#0f766e");
    const accentStrong = getThemeValue("--dh-accent-strong", accent);
    const accentRgb = getThemeValue("--dh-accent-rgb", "15, 118, 110");
    const text = getThemeValue("--dh-text", "#0f172a");
    const muted = getThemeValue("--dh-text-muted", "#64748b");
    const border = getThemeValue("--dh-border", "#e2e8f0");
    const elevatedBorder = getThemeValue("--dh-elevated-border", border);
    const soft = getThemeValue("--dh-surface-soft", "#f8fafc");
    const mutedSurface = getThemeValue("--dh-surface-muted", "#eef3f7");
    const isDark = (getThemeValue("--dh-body-bg", "").toLowerCase() || "").startsWith("#0");

    return {
      accent: accent,
      accentStrong: accentStrong,
      accentRgb: accentRgb,
      text: text,
      muted: muted,
      border: border,
      elevatedBorder: elevatedBorder,
      soft: soft,
      mutedSurface: mutedSurface,
      tooltipTheme: isDark ? "dark" : "light",
      pieFallback: "rgba(" + accentRgb + ", 0.18)"
    };
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function getSpeechLanguageLabel(languageCode) {
    return languageCode === "am-ET" ? "Amharic" : "English";
  }

  function syncSpeechLanguageButtons() {
    if (speechLangEnBtn) {
      speechLangEnBtn.classList.toggle("is-active", currentSpeechLanguage === "en-US");
      speechLangEnBtn.setAttribute("aria-pressed", currentSpeechLanguage === "en-US" ? "true" : "false");
    }
    if (speechLangAmBtn) {
      speechLangAmBtn.classList.toggle("is-active", currentSpeechLanguage === "am-ET");
      speechLangAmBtn.setAttribute("aria-pressed", currentSpeechLanguage === "am-ET" ? "true" : "false");
    }
    if (micBtn) {
      micBtn.title = "Voice input (" + getSpeechLanguageLabel(currentSpeechLanguage) + ")";
    }
    if (liveTranscriptLabel) {
      liveTranscriptLabel.textContent = "Recording in " + getSpeechLanguageLabel(currentSpeechLanguage);
    }
  }

  function setTranscriptState(isListening, transcriptText) {
    const inputRow = chatInput ? chatInput.closest(".ai-input-row") : null;
    if (inputRow) {
      inputRow.classList.toggle("is-listening", Boolean(isListening));
    }
    if (!liveTranscript || !liveTranscriptText) {
      return;
    }
    liveTranscript.hidden = !isListening;
    liveTranscript.classList.toggle("is-active", Boolean(isListening));
    liveTranscriptText.textContent = transcriptText || "Recording… press stop to transcribe.";
  }

  function setMicRecordingState(isRecording) {
    isVoiceRecording = Boolean(isRecording);
    if (!micBtn) {
      return;
    }
    micBtn.classList.toggle("ai-mic-on", isVoiceRecording);
    micBtn.setAttribute("aria-pressed", isVoiceRecording ? "true" : "false");
    micBtn.title = isVoiceRecording
      ? "Stop recording (" + getSpeechLanguageLabel(currentSpeechLanguage) + ")"
      : "Voice input (" + getSpeechLanguageLabel(currentSpeechLanguage) + ")";
    const icon = micBtn.querySelector("i");
    const label = micBtn.querySelector(".ai-record-label");
    if (icon) {
      icon.className = isVoiceRecording ? "ti ti-player-stop-filled" : "ti ti-microphone";
    }
    if (label) {
      label.textContent = isVoiceRecording ? "Stop" : "Record";
    }
  }

  function commitVoiceTranscript() {
    const text = (voiceTranscriptFinal || voiceTranscriptInterim || "").replace(/\s+/g, " ").trim();
    if (text) {
      chatInput.value = text;
      chatInput.focus();
    }
    voiceTranscriptFinal = "";
    voiceTranscriptInterim = "";
  }

  function setSpeechLanguage(languageCode) {
    currentSpeechLanguage = languageCode === "am-ET" ? "am-ET" : "en-US";
    syncSpeechLanguageButtons();
    try {
      window.localStorage.setItem(speechLanguageStorageKey, currentSpeechLanguage);
    } catch (_error) {
      // Ignore storage failures.
    }
  }

  function restoreSpeechLanguage() {
    try {
      const stored = window.localStorage.getItem(speechLanguageStorageKey);
      if (stored === "am-ET" || stored === "en-US") {
        currentSpeechLanguage = stored;
      }
    } catch (_error) {
      currentSpeechLanguage = "en-US";
    }
    syncSpeechLanguageButtons();
  }

  function shouldAllowSidebarCollapse() {
    return window.innerWidth >= 1200;
  }

  function syncSidebarButtons(collapsed) {
    if (sidebarExpandBtn) {
      sidebarExpandBtn.hidden = !collapsed || !shouldAllowSidebarCollapse();
    }
    if (sidebarCollapseBtn) {
      sidebarCollapseBtn.hidden = collapsed || !shouldAllowSidebarCollapse();
    }
  }

  function setSidebarCollapsed(collapsed) {
    if (!chatShell) {
      return;
    }

    const nextState = Boolean(collapsed) && shouldAllowSidebarCollapse();
    chatShell.classList.toggle("is-collapsed", nextState);
    syncSidebarButtons(nextState);

    try {
      window.localStorage.setItem(sidebarStorageKey, nextState ? "1" : "0");
    } catch (_error) {
      // Ignore storage failures.
    }
  }

  function restoreSidebarState() {
    if (!chatShell) {
      return;
    }

    let collapsed = false;
    try {
      collapsed = window.localStorage.getItem(sidebarStorageKey) === "1";
    } catch (_error) {
      collapsed = false;
    }

    setSidebarCollapsed(collapsed);
  }

  function appendUserMessage(text) {
    const el = document.createElement("div");
    el.className = "msg user";
    el.innerHTML =
      '<span class="msg-avatar" aria-hidden="true"><i class="ti ti-user-circle"></i></span>' +
      '<div class="msg-bubble"></div>';
    const bubble = el.querySelector(".msg-bubble");
    if (bubble) {
      bubble.textContent = text;
    }
    chatOutput.appendChild(el);
    scrollToBottom();
  }

  function getDocumentScrollElement() {
    return document.scrollingElement || document.documentElement;
  }

  function isViewportNearBottom() {
    const scrollRoot = getDocumentScrollElement();
    const currentOffset = scrollRoot.scrollTop + window.innerHeight;
    const remaining = scrollRoot.scrollHeight - currentOffset;
    return remaining < 180;
  }

  function getCSRFToken() {
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    if (m) {
      return decodeURIComponent(m[1]);
    }
    const hidden = document.getElementById("csrfTokenValue");
    if (hidden && hidden.value && hidden.value !== "NOTPROVIDED") {
      return hidden.value;
    }
    return "";
  }

  function getActiveInstanceElement() {
    return document.querySelector(".ai-instance.active");
  }

  function getActiveInstanceId() {
    const el = getActiveInstanceElement();
    return el ? (el.dataset.room || "") : (chatOutput.dataset.room || "");
  }

  function appendAIMessageHtml(html) {
    const el = document.createElement("div");
    el.className = "msg ai";
    const normalizedHtml = normalizeAIContent(html);
    el.innerHTML = buildAIMessageMarkup(normalizedHtml);
    chatOutput.appendChild(el);
    hydrateMessageNode(el);
    scrollToBottom();
    return el;
  }

  function appendSystemAIMessage(text) {
    appendAIMessageHtml("<p>" + escapeHtml(text) + "</p>");
  }

  function showLoading() {
    if (loadingElement) {
      return;
    }
    loadingElement = appendAIMessageHtml(
      '<div class="ai-loading"><span class="spinner-border" role="status" aria-hidden="true"></span><div class="ai-loading-copy"><strong>Generating response</strong><span>Admas AI is preparing an answer. You can keep reading earlier messages.</span></div></div>'
    );
  }

  function hideLoading() {
    if (!loadingElement) {
      return;
    }
    loadingElement.remove();
    loadingElement = null;
  }

  function ensureStreamMessage() {
    if (streamMessageElement) {
      return streamMessageElement;
    }
    streamHtmlBuffer = "";
    streamMessageElement = appendAIMessageHtml("");
    streamMessageElement.classList.add("is-streaming");
    return streamMessageElement;
  }

  function renderStreamBuffer() {
    const box = ensureStreamMessage();
    const content = box.querySelector(".ai-msg-content");
    if (!content) {
      return;
    }
    content.innerHTML = normalizeAIContent(streamHtmlBuffer);
    if (autoScrollPinned) {
      scrollToBottom();
    }
  }

  function appendStreamChunk(chunkHtml) {
    streamHtmlBuffer += chunkHtml || "";
    if (pendingStreamRender) {
      return;
    }
    pendingStreamRender = true;
    requestAnimationFrame(function () {
      pendingStreamRender = false;
      renderStreamBuffer();
    });
  }

  function hydrateMessageNode(node) {
    if (!node) {
      return;
    }
    attachTtsControls(node);
    enhanceTables(node);
    renderCharts(node);
    renderActionButtons(node);
  }

  function getReadableMessageText(node) {
    const content = node ? node.querySelector(".ai-msg-content") : null;
    if (!content) {
      return "";
    }

    const clone = content.cloneNode(true);
    const nonSpeechSelectors = [
      ".ai-chart-payload",
      ".ai-chart-card",
      ".ai-chart-title",
      ".ai-chart-canvas",
      ".ai-chart-loading",
      ".ai-chart-error",
      ".ai-bar-chart",
      ".ai-table-wrap",
      "table",
      ".ai-action-payload",
      ".ai-action-btn",
      "button",
      "svg",
      "canvas",
      "img"
    ];

    nonSpeechSelectors.forEach(function (selector) {
      clone.querySelectorAll(selector).forEach(function (element) {
        element.remove();
      });
    });

    return String(clone.innerText || clone.textContent || "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function buildTtsSourceText(node) {
    const text = getReadableMessageText(node);
    if (!text) {
      return "";
    }

    const normalized = text.replace(/\s+/g, " ").trim();
    if (!normalized) {
      return "";
    }

    const sentenceMatches = normalized.match(/[^.!?]+[.!?]?/g) || [];
    const summarySentences = [];
    let length = 0;

    for (let i = 0; i < sentenceMatches.length; i += 1) {
      const sentence = sentenceMatches[i].trim();
      if (!sentence) {
        continue;
      }
      const projected = length + sentence.length + (summarySentences.length ? 1 : 0);
      if (summarySentences.length >= 2 || projected > 320) {
        break;
      }
      summarySentences.push(sentence);
      length = projected;
    }

    if (summarySentences.length) {
      return summarySentences.join(" ");
    }

    return normalized.slice(0, 320);
  }

  function buildShortSpeechText(text, options) {
    const normalized = String(text || "").replace(/\s+/g, " ").trim();
    if (!normalized) {
      return "";
    }

    const settings = options || {};
    const maxSentences = Number(settings.maxSentences) || 2;
    const maxChars = Number(settings.maxChars) || 320;
    const sentenceMatches = normalized.match(/[^.!?]+[.!?]?/g) || [];
    const summarySentences = [];
    let length = 0;

    for (let i = 0; i < sentenceMatches.length; i += 1) {
      const sentence = sentenceMatches[i].trim();
      if (!sentence) {
        continue;
      }
      const projected = length + sentence.length + (summarySentences.length ? 1 : 0);
      if (summarySentences.length >= maxSentences || projected > maxChars) {
        break;
      }
      summarySentences.push(sentence);
      length = projected;
    }

    if (summarySentences.length) {
      return summarySentences.join(" ");
    }

    return normalized.slice(0, maxChars);
  }

  function buildTranslationSourceText(node) {
    const text = getReadableMessageText(node);
    if (!text) {
      return "";
    }
    return text.slice(0, 4000);
  }

  function setTtsButtonState(button, state) {
    if (!button) {
      return;
    }
    const icon = button.querySelector("i");
    const label = button.querySelector("span");

    button.classList.remove("is-loading", "is-playing");
    button.disabled = false;

    if (state === "loading") {
      button.classList.add("is-loading");
      button.disabled = true;
      if (icon) {
        icon.className = "ti ti-loader-2";
      }
      if (label) {
        label.textContent = "Loading";
      }
      return;
    }

    if (state === "playing") {
      button.classList.add("is-playing");
      if (icon) {
        icon.className = "ti ti-player-stop-filled";
      }
      if (label) {
        label.textContent = "Stop";
      }
      return;
    }

    if (icon) {
      icon.className = "ti ti-player-play-filled";
    }
    if (label) {
      label.textContent = "Listen";
    }
  }

  function setMessageStatus(message, text, tone) {
    const status = message ? message.querySelector(".ai-msg-status") : null;
    if (!status) {
      return;
    }
    const normalized = String(text || "").trim();
    if (!normalized) {
      status.hidden = true;
      status.textContent = "";
      status.classList.remove("is-error", "is-success", "is-muted");
      return;
    }
    status.hidden = false;
    status.textContent = normalized;
    status.classList.remove("is-error", "is-success", "is-muted");
    status.classList.add(
      tone === "error" ? "is-error" : tone === "success" ? "is-success" : "is-muted"
    );
  }

  function setTranslateButtonState(button, state) {
    if (!button) {
      return;
    }
    const icon = button.querySelector("i");
    const label = button.querySelector("span");

    button.classList.remove("is-loading", "is-active");
    button.disabled = false;

    if (state === "loading") {
      button.classList.add("is-loading");
      button.disabled = true;
      if (icon) {
        icon.className = "ti ti-loader-2";
      }
      if (label) {
        label.textContent = "Loading";
      }
      return;
    }

    if (state === "active") {
      button.classList.add("is-active");
      if (icon) {
        icon.className = "ti ti-language-hiragana";
      }
      if (label) {
        label.textContent = "Original";
      }
      return;
    }

    if (icon) {
      icon.className = "ti ti-language-hiragana";
    }
    if (label) {
      label.textContent = "Amharic";
    }
  }

  function resetActiveTtsPlayback() {
    if (activeTtsAudio) {
      activeTtsAudio.pause();
      activeTtsAudio.currentTime = 0;
      activeTtsAudio = null;
    }
    if (activeTtsButton) {
      setTtsButtonState(activeTtsButton, "idle");
      activeTtsButton = null;
    }
    if (activeTtsObjectUrl) {
      URL.revokeObjectURL(activeTtsObjectUrl);
      activeTtsObjectUrl = null;
    }
    if (activeTtsStreamSocket) {
      try {
        activeTtsStreamSocket.close();
      } catch (_error) {
        // Ignore close failures.
      }
      activeTtsStreamSocket = null;
    }
    if (activeTtsAudioContext) {
      try {
        activeTtsAudioContext.close();
      } catch (_error) {
        // Ignore close failures.
      }
      activeTtsAudioContext = null;
    }
    activeTtsNextTime = 0;
  }

  function supportsStreamingTts() {
    return STREAMING_TTS_ENABLED && Boolean(window.WebSocket && (window.AudioContext || window.webkitAudioContext));
  }

  function decodeBase64ToBytes(base64Value) {
    const binary = window.atob(base64Value || "");
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes;
  }

  function pcm16ToFloat32(bytes) {
    const sampleCount = Math.floor(bytes.length / 2);
    const samples = new Float32Array(sampleCount);
    for (let i = 0; i < sampleCount; i += 1) {
      const low = bytes[i * 2];
      const high = bytes[i * 2 + 1];
      let value = (high << 8) | low;
      if (value >= 0x8000) {
        value -= 0x10000;
      }
      samples[i] = value / 0x8000;
    }
    return samples;
  }

  function schedulePcmChunk(base64Audio, sampleRate) {
    const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextCtor) {
      throw new Error("Streaming audio is not supported in this browser.");
    }

    if (!activeTtsAudioContext) {
      activeTtsAudioContext = new AudioContextCtor();
      activeTtsNextTime = activeTtsAudioContext.currentTime;
    }
    if (activeTtsAudioContext.state === "suspended") {
      activeTtsAudioContext.resume().catch(function () {
        // Ignore resume failures and let playback fallback handle hard failures.
      });
    }

    const bytes = decodeBase64ToBytes(base64Audio);
    const float32 = pcm16ToFloat32(bytes);
    const rate = Number(sampleRate) || 24000;
    const buffer = activeTtsAudioContext.createBuffer(1, float32.length, rate);
    buffer.copyToChannel(float32, 0);

    const source = activeTtsAudioContext.createBufferSource();
    source.buffer = buffer;
    source.connect(activeTtsAudioContext.destination);
    const startAt = Math.max(activeTtsNextTime, activeTtsAudioContext.currentTime + 0.02);
    source.start(startAt);
    activeTtsNextTime = startAt + buffer.duration;
  }

  function streamTtsAudio(text, language, button, message) {
    return new Promise(function (resolve, reject) {
      if (!supportsStreamingTts()) {
        reject(new Error("Streaming speech is not supported in this browser."));
        return;
      }

      const protocol = window.location.protocol === "https:" ? "wss" : "ws";
      const ws = new WebSocket(protocol + "://" + window.location.host + "/ws/tts-stream/");
      let sessionStarted = false;
      let receivedAudio = false;
      let finished = false;

      activeTtsStreamSocket = ws;

      ws.onopen = function () {
        ws.send(JSON.stringify({
          action: "speak",
          text: text,
          language: language
        }));
      };

      ws.onmessage = function (event) {
        try {
          const payload = JSON.parse(event.data || "{}");
          if (payload.event === "start") {
            sessionStarted = true;
            setMessageStatus(message, "Streaming speech…", "muted");
            return;
          }
          if (payload.event === "audio") {
            receivedAudio = true;
            schedulePcmChunk(payload.data || "", payload.sample_rate);
            return;
          }
          if (payload.event === "complete") {
            finished = true;
            window.setTimeout(function () {
              resetActiveTtsPlayback();
              setMessageStatus(message, "", "");
            }, Math.max(180, (activeTtsNextTime - (activeTtsAudioContext ? activeTtsAudioContext.currentTime : 0)) * 1000));
            resolve(true);
            return;
          }
          if (payload.event === "error") {
            throw new Error(payload.message || "Streaming speech failed.");
          }
        } catch (error) {
          if (!finished) {
            reject(error);
          }
        }
      };

      ws.onerror = function () {
        if (!finished) {
          reject(new Error("Streaming speech failed."));
        }
      };

      ws.onclose = function () {
        if (finished) {
          return;
        }
        if (receivedAudio) {
          finished = true;
          resolve(true);
          return;
        }
        reject(new Error(sessionStarted ? "Streaming speech ended before audio arrived." : "Streaming speech failed."));
      };
    });
  }

  async function fetchTtsAudio(text, language) {
    const normalizedLanguage = String(language || "English").trim() || "English";
    const cacheKey = normalizedLanguage + "::" + text;
    if (ttsAudioCache.has(cacheKey)) {
      return ttsAudioCache.get(cacheKey);
    }

    if (ttsRequestCache.has(cacheKey)) {
      return ttsRequestCache.get(cacheKey);
    }

    const request = fetch("/api/ai-chat/tts/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "*/*",
        "X-CSRFToken": getCSRFToken()
      },
      credentials: "same-origin",
      body: JSON.stringify({ text: text, language: normalizedLanguage })
    })
      .then(async function (response) {
        if (!response.ok) {
          let message = "Unable to generate speech for this response.";
          try {
            const payload = await response.json();
            if (payload && payload.error && payload.error.message) {
              message = payload.error.message;
            }
          } catch (_error) {
            // Ignore non-JSON failure payloads.
          }
          throw new Error(message);
        }

        const blob = await response.blob();
        ttsAudioCache.set(cacheKey, blob);
        return blob;
      })
      .finally(function () {
        ttsRequestCache.delete(cacheKey);
      });

    ttsRequestCache.set(cacheKey, request);
    return request;
  }

  async function prefetchTtsAudio(text, language) {
    const normalizedLanguage = String(language || "English").trim() || "English";
    const cacheKey = normalizedLanguage + "::" + text;
    if (!text || ttsAudioCache.has(cacheKey) || ttsRequestCache.has(cacheKey) || ttsWarmRequestCache.has(cacheKey)) {
      return;
    }

    const request = fetch("/api/ai-chat/tts/prefetch/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "X-CSRFToken": getCSRFToken()
      },
      credentials: "same-origin",
      body: JSON.stringify({ text: text, language: normalizedLanguage })
    })
      .then(async function (response) {
        const payload = await response.json().catch(function () { return null; });
        if (!response.ok || !payload || payload.result !== "SUCCESS") {
          const message = payload && payload.error && payload.error.message
            ? payload.error.message
            : "Unable to prepare speech.";
          throw new Error(message);
        }
      })
      .finally(function () {
        ttsWarmRequestCache.delete(cacheKey);
      });

    ttsWarmRequestCache.set(cacheKey, request);
    return request;
  }

  async function fetchAmharicTranslation(text) {
    if (translationCache.has(text)) {
      return translationCache.get(text);
    }

    if (socket && socket.readyState === WebSocket.OPEN) {
      const requestId = "translate-" + Date.now() + "-" + Math.random().toString(36).slice(2, 8);
      const request = new Promise(function (resolve, reject) {
        translationSocketRequests.set(requestId, { resolve: resolve, reject: reject });
      });

      translationCache.set(text, request);
      socket.send(JSON.stringify({
        action: "translate",
        request_id: requestId,
        text: text,
        target_language: "Amharic"
      }));

      try {
        const translatedFromSocket = await request;
        translationCache.set(text, translatedFromSocket);
        return translatedFromSocket;
      } catch (_error) {
        translationCache.delete(text);
      }
    }

    const request = fetch("/api/ai-chat/translate/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "X-CSRFToken": getCSRFToken()
      },
      credentials: "same-origin",
      body: JSON.stringify({
        text: text,
        target_language: "Amharic"
      })
    })
      .then(async function (response) {
        const payload = await response.json().catch(function () { return null; });
        if (!response.ok || !payload || payload.result !== "SUCCESS") {
          const message = payload && payload.error && payload.error.message
            ? payload.error.message
            : "Unable to translate this response.";
          throw new Error(message);
        }
        const translated = payload.data && payload.data.translation ? String(payload.data.translation).trim() : "";
        if (!translated) {
          throw new Error("Translation response was empty.");
        }
        translationCache.set(text, translated);
        return translated;
      });

    translationCache.set(text, request);
    try {
      return await request;
    } catch (error) {
      translationCache.delete(text);
      throw error;
    }
  }

  function prefetchTtsForMessage(node) {
    const message = node && node.classList && node.classList.contains("msg") ? node : (node ? node.closest(".msg.ai") : null);
    if (!message || message.dataset.ttsPrefetched === "1") {
      return;
    }

    const text = buildTtsSourceText(message);
    const cacheKey = "English::" + text;
    if (!text || ttsAudioCache.has(cacheKey) || ttsRequestCache.has(cacheKey) || ttsWarmRequestCache.has(cacheKey)) {
      if (text) {
        message.dataset.ttsText = text;
      }
      message.dataset.ttsPrefetched = "1";
      return;
    }

    message.dataset.ttsText = text;
    message.dataset.ttsPrefetched = "1";

    window.setTimeout(function () {
      prefetchTtsAudio(text, "English").catch(function () {
        message.dataset.ttsPrefetched = "";
      });
    }, 180);
  }

  async function handleTranslationToggle(button) {
    const message = button ? button.closest(".msg.ai") : null;
    const panel = message ? message.querySelector(".ai-translation-panel") : null;
    const content = panel ? panel.querySelector(".ai-translation-content") : null;
    if (!message || !panel || !content) {
      return;
    }
    setMessageStatus(message, "", "");

    if (!panel.hidden) {
      panel.hidden = true;
      setTranslateButtonState(button, "idle");
      setMessageStatus(message, "", "");
      return;
    }

    const text = buildTranslationSourceText(message);
    if (!text) {
      return;
    }

    setTranslateButtonState(button, "loading");
    try {
      const translated = await fetchAmharicTranslation(text);
      content.textContent = translated;
      panel.hidden = false;
      setTranslateButtonState(button, "active");
      setMessageStatus(message, "Amharic translation ready.", "success");
    } catch (error) {
      panel.hidden = true;
      setTranslateButtonState(button, "idle");
      setMessageStatus(
        message,
        error && error.message ? error.message : "Unable to translate this response.",
        "error"
      );
    }
  }

  async function handleTtsPlayback(button) {
    const message = button ? button.closest(".msg.ai") : null;
    const text = (message && message.dataset.ttsText) || buildTtsSourceText(message);
    if (!text) {
      return;
    }
    setMessageStatus(message, "", "");

    if (activeTtsButton === button) {
      resetActiveTtsPlayback();
      setMessageStatus(message, "", "");
      return;
    }

    resetActiveTtsPlayback();
    setTtsButtonState(button, "loading");
    setMessageStatus(message, "Preparing speech…", "muted");

    try {
      activeTtsButton = button;
      setTtsButtonState(button, "playing");
      try {
        await streamTtsAudio(text, "English", button, message);
      } catch (_streamError) {
        const blob = await fetchTtsAudio(text, "English");
        activeTtsObjectUrl = URL.createObjectURL(blob);
        const audio = new Audio(activeTtsObjectUrl);
        activeTtsAudio = audio;

        audio.addEventListener("ended", resetActiveTtsPlayback, { once: true });
        audio.addEventListener("error", function () {
          resetActiveTtsPlayback();
          setMessageStatus(message, "Unable to play the generated speech.", "error");
        }, { once: true });

        await audio.play();
        setMessageStatus(message, "", "");
      }
    } catch (error) {
      resetActiveTtsPlayback();
      setMessageStatus(
        message,
        error && error.message ? error.message : "Unable to generate speech for this response.",
        "error"
      );
    }
  }

  function attachTtsControls(scope) {
    const root = scope || document;
    const buttons = root.querySelectorAll(".msg.ai .ai-tts-btn");
    buttons.forEach(function (button) {
      if (button.dataset.bound === "1") {
        return;
      }
      button.dataset.bound = "1";
      setTtsButtonState(button, "idle");
      button.addEventListener("click", function () {
        handleTtsPlayback(button);
      });
    });

    root.querySelectorAll(".msg.ai").forEach(function (message) {
      prefetchTtsForMessage(message);
    });

    const translateButtons = root.querySelectorAll(".msg.ai .ai-translate-btn");
    translateButtons.forEach(function (button) {
      if (button.dataset.bound === "1") {
        return;
      }
      button.dataset.bound = "1";
      setTranslateButtonState(button, "idle");
      button.addEventListener("click", function () {
        handleTranslationToggle(button);
      });
    });

    const translationTtsButtons = root.querySelectorAll(".msg.ai .ai-translation-tts-btn");
    translationTtsButtons.forEach(function (button) {
      if (button.dataset.bound === "1") {
        return;
      }
      button.dataset.bound = "1";
      setTtsButtonState(button, "idle");
      button.addEventListener("click", function () {
        const panel = button.closest(".ai-translation-panel");
        const message = button.closest(".msg.ai");
        const content = panel ? panel.querySelector(".ai-translation-content") : null;
        const fullText = String((content && (content.innerText || content.textContent)) || "")
          .replace(/\s+/g, " ")
          .trim();
        const text = buildShortSpeechText(fullText, { maxSentences: 1, maxChars: 180 });
        if (!text) {
          return;
        }

        if (activeTtsButton === button) {
          resetActiveTtsPlayback();
          return;
        }

        resetActiveTtsPlayback();
        setTtsButtonState(button, "loading");
        setMessageStatus(message, "Preparing Amharic speech…", "muted");

        activeTtsButton = button;
        setTtsButtonState(button, "playing");

        streamTtsAudio(text, "Amharic", button, message)
          .catch(function () {
            return fetchTtsAudio(text, "Amharic").then(function (blob) {
              activeTtsObjectUrl = URL.createObjectURL(blob);
              const audio = new Audio(activeTtsObjectUrl);
              activeTtsAudio = audio;

              audio.addEventListener("ended", resetActiveTtsPlayback, { once: true });
              audio.addEventListener("error", function () {
                resetActiveTtsPlayback();
                setMessageStatus(message, "Unable to play the generated speech.", "error");
              }, { once: true });

              return audio.play().then(function () {
                setMessageStatus(message, "", "");
              });
            });
          })
          .catch(function (error) {
            resetActiveTtsPlayback();
            setMessageStatus(
              message,
              error && error.message ? error.message : "Unable to generate speech for this response.",
              "error"
            );
          });
      });
    });
  }

  function normalizeAIContent(value) {
    let text = String(value || "");

    // Some providers return escaped HTML; decode once so tags can render.
    if (text.includes("&lt;table") || text.includes("&lt;tr") || text.includes("&lt;td")) {
      const parser = document.createElement("textarea");
      parser.innerHTML = text;
      text = parser.value;
    }

    text = convertMarkdownTablesToHtml(text);
    text = injectStructuredPayloadPlaceholders(text);
    return text;
  }

  function injectStructuredPayloadPlaceholders(text) {
    if (!text) {
      return text;
    }

    const blocks = extractJsonPayloadBlocks(text);
    if (!blocks.length) {
      return text;
    }

    let output = text;
    for (let i = blocks.length - 1; i >= 0; i -= 1) {
      const block = blocks[i];
      const encoded = encodeURIComponent(JSON.stringify(block.payload));
      let placeholder = "";
      if (block.payload.kind === "chart") {
        placeholder =
          '<div class="ai-chart-payload" data-chart="' + encoded + '">' +
          '<div class="ai-chart-loading">Preparing chart...</div>' +
          "</div>";
      } else if (block.payload.kind === "button") {
        placeholder = '<div class="ai-action-payload" data-action="' + encoded + '"></div>';
      } else {
        continue;
      }
      output = output.slice(0, block.start) + placeholder + output.slice(block.end);
    }
    return output;
  }

  function extractJsonPayloadBlocks(input) {
    const text = String(input || "");
    const blocks = [];
    let i = 0;

    while (i < text.length) {
      if (text[i] !== "{") {
        i += 1;
        continue;
      }

      const end = findBalancedEnd(text, i);
      if (end < 0) {
        i += 1;
        continue;
      }

      const candidate = text.slice(i, end + 1);
      const payload = parseStructuredPayload(candidate);
      if (payload) {
        blocks.push({ start: i, end: end + 1, payload: payload });
        i = end + 1;
      } else {
        i += 1;
      }
    }

    return blocks;
  }

  function findBalancedEnd(text, start) {
    let depth = 0;
    let inString = false;
    let escaped = false;
    let quote = "";

    for (let i = start; i < text.length; i += 1) {
      const ch = text[i];

      if (inString) {
        if (escaped) {
          escaped = false;
          continue;
        }
        if (ch === "\\") {
          escaped = true;
          continue;
        }
        if (ch === quote) {
          inString = false;
        }
        continue;
      }

      if (ch === '"' || ch === "'") {
        inString = true;
        quote = ch;
        continue;
      }

      if (ch === "{") depth += 1;
      if (ch === "}") {
        depth -= 1;
        if (depth === 0) {
          return i;
        }
      }
    }

    return -1;
  }

  function parseStructuredPayload(raw) {
    if (!raw || raw.indexOf("type") < 0) {
      return null;
    }

    const cleaned = String(raw)
      .replace(/[“”]/g, '"')
      .replace(/[‘’]/g, "'")
      .replace(/,\s*([}\]])/g, "$1");

    let obj = null;
    try {
      obj = JSON.parse(cleaned);
    } catch (e) {
      return null;
    }

    if (!obj || typeof obj !== "object" || !obj.type) return null;

    const type = String(obj.type).trim().toLowerCase();
    if (type === "button") {
      return {
        kind: "button",
        button_type: obj.button_type ? String(obj.button_type) : "action",
        id: obj.id ? String(obj.id) : "",
        year: obj.year ? String(obj.year) : "",
        quarter: obj.quarter ? String(obj.quarter) : ""
      };
    }

    if (!["bar", "line", "area", "pie"].includes(type)) return null;

    const labelsRaw = Array.isArray(obj.labels) ? obj.labels : [obj.labels];
    const dataRaw = Array.isArray(obj.data) ? obj.data : [obj.data];
    const labels = labelsRaw
      .filter(function (x) {
        return x !== null && x !== undefined && String(x).trim() !== "";
      })
      .map(function (x) {
        return String(x);
      });
    const data = dataRaw
      .map(function (x) {
        const n = Number(x);
        return Number.isFinite(n) ? n : null;
      })
      .filter(function (x) {
        return x !== null;
      });

    const pointCount = Math.min(labels.length, data.length);
    if (!pointCount) return null;

    const normalizedLabels = labels.slice(0, pointCount);
    const normalizedData = data.slice(0, pointCount);

    return {
      kind: "chart",
      type: type,
      label: obj.label ? String(obj.label) : "AI Chart",
      labels: normalizedLabels,
      data: normalizedData,
      score_color: obj.score_color ? String(obj.score_color).trim() : ""
    };
  }

  function convertMarkdownTablesToHtml(input) {
    const lines = String(input || "").split("\n");
    const output = [];
    let i = 0;

    function isTableRow(line) {
      return line.includes("|");
    }

    function isSeparator(line) {
      return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);
    }

    function splitCells(line) {
      let row = line.trim();
      if (row.startsWith("|")) row = row.slice(1);
      if (row.endsWith("|")) row = row.slice(0, -1);
      return row.split("|").map(function (c) {
        return c.trim();
      });
    }

    while (i < lines.length) {
      const l1 = lines[i] || "";
      const l2 = lines[i + 1] || "";
      if (isTableRow(l1) && isSeparator(l2)) {
        const headers = splitCells(l1);
        i += 2;
        const rows = [];
        while (i < lines.length && isTableRow(lines[i])) {
          rows.push(splitCells(lines[i]));
          i += 1;
        }

        let table = "<table><thead><tr>";
        headers.forEach(function (h) {
          table += "<th>" + escapeHtml(h) + "</th>";
        });
        table += "</tr></thead><tbody>";
        rows.forEach(function (r) {
          table += "<tr>";
          r.forEach(function (c) {
            table += "<td>" + escapeHtml(c) + "</td>";
          });
          table += "</tr>";
        });
        table += "</tbody></table>";
        output.push(table);
        continue;
      }

      output.push(l1);
      i += 1;
    }

    return output.join("\n");
  }

  function enhanceTables(scope) {
    const root = scope || document;
    const tables = root.querySelectorAll(".ai-msg-content table");

    tables.forEach(function (table) {
      table.classList.add("ai-table");
      stripInlineTableStyles(table);
      ensureNumberingColumn(table);
      if (!table.parentElement || !table.parentElement.classList.contains("ai-table-wrap")) {
        const wrap = document.createElement("div");
        wrap.className = "ai-table-wrap";
        table.parentNode.insertBefore(wrap, table);
        wrap.appendChild(table);
      }
    });
  }

  function renderCharts(scope) {
    const root = scope || document;
    const placeholders = root.querySelectorAll(".ai-chart-payload");

    placeholders.forEach(function (holder) {
      if (holder.dataset.rendered === "1") {
        return;
      }

      const raw = holder.dataset.chart || "";
      let payload = null;
      try {
        payload = JSON.parse(decodeURIComponent(raw));
      } catch (e) {
        holder.dataset.rendered = "1";
        holder.innerHTML = '<div class="ai-chart-error">Chart payload is invalid.</div>';
        return;
      }

      if (!window.ApexCharts) {
        if (payload.type === "bar") {
          renderBarChart(holder, payload);
          holder.dataset.rendered = "1";
          return;
        }
        holder.dataset.rendered = "1";
        holder.innerHTML = '<div class="ai-chart-error">Chart library unavailable.</div>';
        return;
      }

      holder.innerHTML =
        '<div class="ai-chart-card">' +
        '<div class="ai-chart-title">' + escapeHtml(payload.label || "AI Chart") + "</div>" +
        '<div class="ai-chart-canvas" id="aiChart' + (chartCounter += 1) + '"></div>' +
        "</div>";

      const chartEl = holder.querySelector(".ai-chart-canvas");
      const theme = getAIChartTheme();
      const color = payload.score_color || (payload.type === "line" ? theme.accent : payload.type === "area" ? theme.accentStrong : payload.type === "pie" ? theme.accent : theme.accentStrong);
      const isSingleScorePie = payload.type === "pie" && payload.data.length === 1 && payload.data[0] >= 0 && payload.data[0] <= 100;
      const pieSeries = isSingleScorePie ? [payload.data[0], Number((100 - payload.data[0]).toFixed(2))] : payload.data;
      const pieLabels = isSingleScorePie ? [payload.labels[0] || "Achieved", "Remaining"] : payload.labels;
      const pieColors = isSingleScorePie ? [color, theme.pieFallback] : [color];
      const cartesianPoints = payload.labels.map(function (label, index) {
        return {
          x: label,
          y: payload.data[index]
        };
      });
      const baseOptions = {
        chart: {
          type: payload.type,
          height: 280,
          toolbar: { show: false },
          animations: { enabled: true }
        },
        dataLabels: { enabled: false },
        colors: payload.type === "pie" ? pieColors : [color],
        grid: { borderColor: theme.border },
        tooltip: { theme: theme.tooltipTheme },
        legend: {
          position: "bottom",
          labels: { colors: theme.muted }
        },
        responsive: [{
          breakpoint: 768,
          options: { chart: { height: 240 } }
        }]
      };
      let options;

      if (payload.type === "pie") {
        options = Object.assign({}, baseOptions, {
          series: pieSeries,
          labels: pieLabels,
          plotOptions: {
            pie: {
              donut: {
                size: "58%"
              }
            }
          }
        });
      } else if (payload.type === "bar") {
        options = Object.assign({}, baseOptions, {
          series: [{
            name: payload.label || "Series",
            data: payload.data
          }],
          xaxis: {
            categories: payload.labels,
            labels: {
              rotate: -30,
              trim: false,
              hideOverlappingLabels: false,
              style: { colors: payload.labels.map(function () { return theme.muted; }) }
            },
            axisBorder: { color: theme.border },
            axisTicks: { color: theme.border }
          },
          yaxis: {
            labels: {
              style: { colors: [theme.muted] },
              formatter: function (val) {
                return val === null ? "" : Number(val).toLocaleString();
              }
            }
          },
          stroke: {
            width: 0
          },
          fill: {
            opacity: 1
          },
          plotOptions: {
            bar: {
              horizontal: false,
              borderRadius: 6,
              columnWidth: "52%",
              distributed: false
            }
          }
        });
      } else {
        options = Object.assign({}, baseOptions, {
          series: [{
            name: payload.label || "Series",
            data: cartesianPoints
          }],
          xaxis: {
            type: "category",
            labels: {
              rotate: -30,
              trim: false,
              hideOverlappingLabels: false,
              style: { colors: payload.labels.map(function () { return theme.muted; }) }
            },
            axisBorder: { color: theme.border },
            axisTicks: { color: theme.border }
          },
          yaxis: {
            labels: {
              style: { colors: [theme.muted] },
              formatter: function (val) {
                return val === null ? "" : Number(val).toLocaleString();
              }
            }
          },
          stroke: {
            curve: payload.type === "line" || payload.type === "area" ? "smooth" : "straight",
            width: 3
          },
          markers: payload.type === "line" || payload.type === "area" ? {
            size: 4,
            strokeColors: theme.accentStrong,
            hover: { size: 6 }
          } : undefined,
          fill: payload.type === "area" ? {
            type: "gradient",
            gradient: { shadeIntensity: 1, opacityFrom: 0.35, opacityTo: 0.05, stops: [0, 100] }
          } : { opacity: 1 }
        });
      }

      try {
        const chart = new window.ApexCharts(chartEl, options);
        chart.render()
          .then(function () {
            holder.dataset.rendered = "1";
          })
          .catch(function () {
            if (payload.type === "bar") {
              renderBarChart(holder, payload);
            } else {
              holder.innerHTML =
                '<div class="ai-chart-error">Chart render failed for type ' +
                escapeHtml(payload.type || "unknown") +
                '.</div>';
            }
            holder.dataset.rendered = "1";
          });
      } catch (err) {
        if (payload.type === "bar") {
          renderBarChart(holder, payload);
        } else {
          holder.innerHTML =
            '<div class="ai-chart-error">Chart render failed for type ' +
            escapeHtml(payload.type || "unknown") +
            '.</div>';
        }
        holder.dataset.rendered = "1";
      }
    });
  }

  function renderBarChart(holder, payload) {
    const color = payload.score_color || getAIChartTheme().accentStrong;
    const maxValue = Math.max.apply(null, payload.data.concat([0])) || 1;
    let bars = "";

    payload.labels.forEach(function (label, index) {
      const value = payload.data[index];
      const height = maxValue > 0 ? Math.max(8, Math.round((value / maxValue) * 100)) : 0;
      bars +=
        '<div class="ai-bar-item">' +
        '<div class="ai-bar-value">' + escapeHtml(Number(value).toLocaleString()) + "</div>" +
        '<div class="ai-bar-column-wrap">' +
        '<div class="ai-bar-column" style="height:' + height + '%; background:' + escapeHtml(color) + ';"></div>' +
        "</div>" +
        '<div class="ai-bar-label" title="' + escapeHtml(label) + '">' + escapeHtml(label) + "</div>" +
        "</div>";
    });

    holder.innerHTML =
      '<div class="ai-chart-card ai-bar-chart-card">' +
      '<div class="ai-chart-title">' + escapeHtml(payload.label || "AI Chart") + "</div>" +
      '<div class="ai-bar-chart">' + bars + "</div>" +
      "</div>";
  }

  function rerenderAICharts() {
    const holders = document.querySelectorAll(".ai-chart-payload");
    holders.forEach(function (holder) {
      holder.dataset.rendered = "0";
      holder.innerHTML = '<div class="ai-chart-loading">Refreshing chart theme...</div>';
    });
    renderCharts(document);
  }

  function renderActionButtons(scope) {
    const root = scope || document;
    const actions = root.querySelectorAll(".ai-action-payload");

    actions.forEach(function (holder) {
      if (holder.dataset.rendered === "1") {
        return;
      }

      const raw = holder.dataset.action || "";
      let payload = null;
      try {
        payload = JSON.parse(decodeURIComponent(raw));
      } catch (e) {
        holder.dataset.rendered = "1";
        holder.innerHTML = '<div class="ai-chart-error">Action payload is invalid.</div>';
        return;
      }

      const title = payload.button_type === "ministry_detail" ? "View Ministry Detail" : "Run Action";
      holder.innerHTML =
        '<button type="button" class="ai-action-btn" data-action-type="' + escapeHtml(payload.button_type || "") + '"' +
        ' data-id="' + escapeHtml(payload.id || "") + '"' +
        ' data-year="' + escapeHtml(payload.year || "") + '"' +
        ' data-quarter="' + escapeHtml(payload.quarter || "") + '">' +
        escapeHtml(title) +
        "</button>";

      const btn = holder.querySelector(".ai-action-btn");
      if (btn) {
        btn.addEventListener("click", function () {
          const actionType = btn.dataset.actionType || "";
          if (actionType === "ministry_detail") {
            const prompt = "Show ministry detail for id " + (btn.dataset.id || "") +
              " in year " + (btn.dataset.year || "") +
              " for quarter " + (btn.dataset.quarter || "") + ".";
            chatInput.value = prompt.replace(/\s+/g, " ").trim();
            sendMessage();
          }
        });
      }

      holder.dataset.rendered = "1";
    });
  }

  function hydrateExistingAIResponses(root) {
    const container = root || document;
    const blocks = container.querySelectorAll(".msg.ai .ai-msg-content");
    blocks.forEach(function (block) {
      if (block.dataset.hydrated === "1") {
        return;
      }
      block.innerHTML = normalizeAIContent(block.innerHTML);
      block.dataset.hydrated = "1";
    });
  }

  function ensureNumberingColumn(table) {
    if (!table || table.dataset.numbered === "1") {
      return;
    }

    const theadRow = table.querySelector("thead tr");
    const bodyRows = Array.from(table.querySelectorAll("tbody tr"));
    if (!bodyRows.length) {
      return;
    }

    if (theadRow) {
      const firstHeader = theadRow.firstElementChild;
      const firstHeaderText = (firstHeader && firstHeader.textContent || "").trim().toLowerCase();
      if (firstHeaderText !== "#") {
        const th = document.createElement("th");
        th.textContent = "#";
        th.className = "ai-col-number";
        theadRow.insertBefore(th, firstHeader || null);
      } else {
        firstHeader.classList.add("ai-col-number");
      }
    }

    bodyRows.forEach(function (row, index) {
      const firstCell = row.firstElementChild;
      const hasNumberCell = firstCell && firstCell.classList.contains("ai-cell-number");
      if (!hasNumberCell) {
        const td = document.createElement("td");
        td.className = "ai-cell-number";
        td.textContent = String(index + 1);
        row.insertBefore(td, firstCell || null);
      } else {
        firstCell.textContent = String(index + 1);
      }
    });

    table.dataset.numbered = "1";
  }

  function stripInlineTableStyles(table) {
    const nodes = table.querySelectorAll("thead,tbody,tr,th,td");
    table.removeAttribute("style");
    nodes.forEach(function (node) {
      node.removeAttribute("style");
    });
  }

  function finishStream() {
    if (pendingStreamRender) {
      pendingStreamRender = false;
      renderStreamBuffer();
    }
    if (streamMessageElement) {
      streamMessageElement.classList.remove("is-streaming");
      hydrateMessageNode(streamMessageElement);
    }
    streamMessageElement = null;
    streamHtmlBuffer = "";
    hideLoading();
  }

  function clearChatOutput() {
    resetActiveTtsPlayback();
    chatOutput.innerHTML = "";
    streamMessageElement = null;
    streamHtmlBuffer = "";
    loadingElement = null;
  }

  function renderHistory(entries) {
    clearChatOutput();

    if (!entries.length) {
      appendSystemAIMessage("Hello, I am Admas AI. Ask me about policy areas, ministries, or indicators.");
      return;
    }

    entries.forEach(function (item) {
      const question = (item && item.question) || "";
      const response = (item && item.response) || "";

      if (question) {
        appendUserMessage(question);
      }
      if (response) {
        appendAIMessageHtml(response);
      }
    });

    scrollToBottom();
  }

  function scrollToBottom() {
    if (!autoScrollPinned) {
      return;
    }
    requestAnimationFrame(function () {
      const lastMessage = chatOutput.lastElementChild;
      if (lastMessage && typeof lastMessage.scrollIntoView === "function") {
        lastMessage.scrollIntoView({ block: "end", behavior: "auto" });
      } else {
        window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "auto" });
      }
    });
  }

  function updateInstanceControlsState() {
    const hasActive = Boolean(getActiveInstanceElement());
    if (renameInstanceBtn) {
      renameInstanceBtn.disabled = !hasActive;
    }
    if (deleteInstanceBtn) {
      deleteInstanceBtn.disabled = !hasActive;
    }
  }

  function attachInstanceClick(item) {
    item.addEventListener("click", function () {
      instances.forEach(function (x) {
        x.classList.remove("active");
      });
      item.classList.add("active");

      const room = item.dataset.room || "";
      currentRoom = room;
      chatOutput.dataset.room = room;
      chatTitle.textContent = item.dataset.title || "Admas AI Chat";
      updateInstanceControlsState();

      hideLoading();
      finishStream();
      loadHistory(room);
      connectSocket(room);
    });
  }

  function createInstanceElement(instance) {
    const title = (instance && instance.title) ? String(instance.title) : ("History " + instance.id);
    const el = document.createElement("div");
    el.className = "ai-instance";
    el.dataset.room = String(instance.id);
    el.dataset.title = title;
    el.dataset.tags = "policy ministry indicator";
    el.innerHTML = "<h6>" + escapeHtml(title) + "</h6><p>History #" + escapeHtml(instance.id) + "</p>";
    attachInstanceClick(el);
    return el;
  }

  async function apiRequest(url, method, body) {
    const res = await fetch(url, {
      method: method,
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-CSRFToken": getCSRFToken()
      },
      credentials: "same-origin",
      body: body ? JSON.stringify(body) : null
    });
    const payload = await res.json().catch(function () { return null; });
    return { ok: res.ok, payload: payload };
  }

  async function loadHistory(room) {
    try {
      const res = await fetch("/api/ai-chat/history/" + encodeURIComponent(room) + "/", {
        headers: {
          Accept: "application/json"
        },
        credentials: "same-origin"
      });

      const payload = await res.json();
      if (!res.ok || !payload || payload.result !== "SUCCESS") {
        appendSystemAIMessage("Unable to load chat history for this room.");
        return;
      }

      const data = Array.isArray(payload.data) ? payload.data : [];
      renderHistory(data);
    } catch (err) {
      appendSystemAIMessage("Unable to load chat history for this room.");
    }
  }

  function wsUrl(room) {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    return protocol + "://" + window.location.host + "/ws/chat/" + encodeURIComponent(room) + "/";
  }

  function bindSocketEvents(ws, room) {
    ws.onmessage = function (event) {
      try {
        const payload = JSON.parse(event.data || "{}");

        if (payload.action === "translation_result") {
          const pending = translationSocketRequests.get(payload.request_id || "");
          if (pending) {
            translationSocketRequests.delete(payload.request_id || "");
            if (payload.ok) {
              pending.resolve(String(payload.translation || "").trim());
            } else {
              const message = payload.error && payload.error.message
                ? payload.error.message
                : "Unable to translate this response.";
              pending.reject(new Error(message));
            }
          }
          return;
        }

        if (payload.is_stream) {
          hideLoading();
          appendStreamChunk(payload.message || "");
          return;
        }

        if (payload.is_final) {
          finishStream();
          return;
        }

        if (payload.message) {
          hideLoading();
          appendAIMessageHtml(payload.message);
        }
      } catch (err) {
        hideLoading();
        appendSystemAIMessage("Received an invalid response from chat server.");
      }
    };

    ws.onerror = function () {
      if (currentRoom === room) {
        hideLoading();
        appendSystemAIMessage("Chat service error. Please try again.");
      }
    };

    ws.onclose = function () {
      translationSocketRequests.forEach(function (pending) {
        pending.reject(new Error("Translation channel disconnected."));
      });
      translationSocketRequests.clear();
      if (currentRoom === room) {
        hideLoading();
        finishStream();
      }
    };
  }

  function connectSocket(room) {
    if (!room) {
      return;
    }

    if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
      socket.close();
    }

    socket = new WebSocket(wsUrl(room));
    bindSocketEvents(socket, room);
  }

  function sendMessage() {
    const value = (chatInput.value || "").trim();
    if (!value) return;

    appendUserMessage(value);
    chatInput.value = "";

    if (!socket || socket.readyState !== WebSocket.OPEN) {
      appendSystemAIMessage("Chat connection is not ready. Please wait and try again.");
      return;
    }

    showLoading();
    streamMessageElement = null;
    streamHtmlBuffer = "";
    socket.send(JSON.stringify({ message: value }));
  }

  sendBtn.addEventListener("click", sendMessage);
  chatInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
      e.preventDefault();
      sendMessage();
    }
  });

  instances.forEach(attachInstanceClick);

  if (sidebarCollapseBtn) {
    sidebarCollapseBtn.addEventListener("click", function () {
      setSidebarCollapsed(true);
    });
  }

  if (sidebarExpandBtn) {
    sidebarExpandBtn.addEventListener("click", function () {
      setSidebarCollapsed(false);
    });
  }

  window.addEventListener("resize", function () {
    if (!shouldAllowSidebarCollapse()) {
      if (chatShell) {
        chatShell.classList.remove("is-collapsed");
      }
      syncSidebarButtons(false);
      return;
    }

    const collapsed = chatShell ? chatShell.classList.contains("is-collapsed") : false;
    syncSidebarButtons(collapsed);
  });

  function filterInstances() {
    const q = chatSearch ? (chatSearch.value || "").toLowerCase() : "";

    instances.forEach(function (item) {
      const txt = (item.dataset.title || "").toLowerCase();
      const itemTags = (item.dataset.tags || "").toLowerCase();
      const qMatch = txt.includes(q);
      const tagMatch = selectedTag === "all" || itemTags.includes(selectedTag);
      item.style.display = qMatch && tagMatch ? "" : "none";
    });
  }

  if (chatSearch) {
    chatSearch.addEventListener("input", filterInstances);
  }

  tags.forEach(function (tagBtn) {
    tagBtn.addEventListener("click", function () {
      tags.forEach(function (t) {
        t.classList.remove("active");
      });
      tagBtn.classList.add("active");
      selectedTag = (tagBtn.dataset.tag || "all").toLowerCase();
      filterInstances();
    });
  });

  quickTags.forEach(function (btn) {
    btn.addEventListener("click", function () {
      chatInput.value = btn.dataset.prompt || "";
      chatInput.focus();
    });
  });

  restoreSidebarState();
  restoreSpeechLanguage();
  document.addEventListener("dashboard-theme-change", function () {
    rerenderAICharts();
  });

  if (newInstanceBtn) {
    newInstanceBtn.addEventListener("click", async function () {
      const result = await apiRequest("/api/ai-chat/", "POST", {});
      if (!result.ok || !result.payload || result.payload.result !== "SUCCESS") {
        const msg = result.payload && result.payload.error && result.payload.error.message
          ? result.payload.error.message
          : "Unable to create a new chat instance.";
        appendSystemAIMessage(msg);
        return;
      }
      const instance = result.payload.data;
      const list = document.getElementById("instanceList");
      const el = createInstanceElement(instance);
      if (list) list.prepend(el);
      instances = Array.from(document.querySelectorAll(".ai-instance"));
      el.click();
    });
  }

  if (renameInstanceBtn) {
    renameInstanceBtn.addEventListener("click", async function () {
      const current = getActiveInstanceElement();
      const instanceId = getActiveInstanceId();
      if (!current || !instanceId) {
        return;
      }
      const currentTitle = current.dataset.title || ("History " + instanceId);
      const title = (window.prompt("Rename chat history:", currentTitle) || "").trim();
      if (!title) {
        return;
      }
      const result = await apiRequest("/api/ai-chat/instance/" + encodeURIComponent(instanceId) + "/", "PATCH", { title: title });
      if (!result.ok || !result.payload || result.payload.result !== "SUCCESS") {
        appendSystemAIMessage("Unable to rename this instance.");
        return;
      }
      current.dataset.title = title;
      const h6 = current.querySelector("h6");
      if (h6) h6.textContent = title;
      chatTitle.textContent = title;
      updateInstanceControlsState();
    });
  }

  if (deleteInstanceBtn) {
    deleteInstanceBtn.addEventListener("click", async function () {
      const current = getActiveInstanceElement();
      const instanceId = getActiveInstanceId();
      if (!current || !instanceId) {
        return;
      }
      if (!window.confirm("Delete this chat history?")) {
        return;
      }
      const result = await apiRequest("/api/ai-chat/delete/" + encodeURIComponent(instanceId) + "/", "DELETE");
      if (!result.ok || !result.payload || result.payload.result !== "SUCCESS") {
        appendSystemAIMessage("Unable to delete this instance.");
        return;
      }
      current.remove();
      instances = Array.from(document.querySelectorAll(".ai-instance"));
      if (instances.length) {
        instances[0].click();
      } else {
        chatOutput.innerHTML = "";
        appendSystemAIMessage("No chat history left. Use New to create one.");
        chatTitle.textContent = "Admas AI Chat";
        updateInstanceControlsState();
      }
    });
  }

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    micBtn.disabled = true;
    micBtn.title = "Voice input is not supported in this browser";
    if (speechLangEnBtn) {
      speechLangEnBtn.disabled = true;
    }
    if (speechLangAmBtn) {
      speechLangAmBtn.disabled = true;
    }
  } else {
    const recognition = new SpeechRecognition();
    recognition.lang = currentSpeechLanguage;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    recognition.onstart = function () {
      voiceTranscriptFinal = "";
      voiceTranscriptInterim = "";
      setMicRecordingState(true);
      setTranscriptState(true, "Recording… press stop to transcribe.");
    };

    recognition.onend = function () {
      const shouldCommit = isVoiceRecording;
      setMicRecordingState(false);
      setTranscriptState(false, "");
      if (shouldCommit) {
        commitVoiceTranscript();
      }
    };

    recognition.onresult = function (event) {
      let finalText = voiceTranscriptFinal;
      let interimText = "";

      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        const transcript = result && result[0] ? result[0].transcript || "" : "";
        if (!transcript) {
          continue;
        }
        if (result.isFinal) {
          finalText += transcript + " ";
        } else {
          interimText += transcript + " ";
        }
      }

      voiceTranscriptFinal = finalText;
      voiceTranscriptInterim = interimText;
      setTranscriptState(true, "Recording… press stop to transcribe.");
    };

    recognition.onerror = function () {
      setMicRecordingState(false);
      setTranscriptState(false, "");
    };

    function updateRecognitionLanguage(languageCode) {
      if (isVoiceRecording) {
        return;
      }
      recognition.lang = languageCode;
      setSpeechLanguage(languageCode);
    }

    if (speechLangEnBtn) {
      speechLangEnBtn.addEventListener("click", function () {
        updateRecognitionLanguage("en-US");
      });
    }

    if (speechLangAmBtn) {
      speechLangAmBtn.addEventListener("click", function () {
        updateRecognitionLanguage("am-ET");
      });
    }

    micBtn.addEventListener("click", function () {
      try {
        if (isVoiceRecording) {
          recognition.stop();
          return;
        }
        recognition.lang = currentSpeechLanguage;
        recognition.start();
      } catch (e) {
        // Browser may throw if start is called while already running.
      }
    });
  }

  if (currentRoom) {
    connectSocket(currentRoom);
  }

  window.addEventListener("scroll", function () {
    autoScrollPinned = isViewportNearBottom();
    const jumpBtn = document.getElementById("jumpToLatestBtn");
    if (jumpBtn) {
      jumpBtn.hidden = autoScrollPinned;
    }
  }, { passive: true });

  window.addEventListener("wheel", function (event) {
    if (event.deltaY < 0) {
      autoScrollPinned = false;
      const jumpBtn = document.getElementById("jumpToLatestBtn");
      if (jumpBtn) {
        jumpBtn.hidden = false;
      }
    }
  }, { passive: true });

  window.addEventListener("touchstart", function (event) {
    const touch = event.touches && event.touches[0];
    lastTouchY = touch ? touch.clientY : 0;
  }, { passive: true });

  window.addEventListener("touchmove", function (event) {
    const touch = event.touches && event.touches[0];
    if (!touch) {
      return;
    }
    if (touch.clientY > lastTouchY + 6) {
      autoScrollPinned = false;
      const jumpBtn = document.getElementById("jumpToLatestBtn");
      if (jumpBtn) {
        jumpBtn.hidden = false;
      }
    }
    lastTouchY = touch.clientY;
  }, { passive: true });

  const jumpToLatestBtn = document.getElementById("jumpToLatestBtn");
  if (jumpToLatestBtn) {
    jumpToLatestBtn.addEventListener("click", function () {
      autoScrollPinned = true;
      jumpToLatestBtn.hidden = true;
      scrollToBottom();
    });
  }

  // Apply table enhancement to server-rendered history on first load.
  hydrateExistingAIResponses(chatOutput);
  hydrateMessageNode(chatOutput);
  updateInstanceControlsState();
  scrollToBottom();
})();
