(function () {
  const chatInput = document.getElementById("chatInput");
  const sendBtn = document.getElementById("sendBtn");
  const chatOutput = document.getElementById("chatOutput");
  const micBtn = document.getElementById("micBtn");
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
  const composer = document.querySelector(".ai-composer");
  const mainHead = document.querySelector(".ai-chat-name");
  const chatTitleForm = document.getElementById("chatTitleForm");
  const chatTitleInput = document.getElementById("chatTitleInput");
  const chatTitleCancel = document.getElementById("chatTitleCancel");
  const railScrim = document.getElementById("aiRailScrim");
  const chatSearchEmpty = document.getElementById("chatSearchEmpty");
  const instanceList = document.getElementById("instanceList");

  if (!chatInput || !sendBtn || !chatOutput || !micBtn || !chatTitle) {
    return;
  }

  let instances = Array.from(document.querySelectorAll(".ai-instance"));
  let currentRoom = chatOutput.dataset.room || "";
  let socket = null;
  let streamMessageElement = null;
  let streamHtmlBuffer = "";
  let pendingStreamRender = false;
  let streamRenderTimer = null;
  let streamViewAnchored = false;
  let streamPreviewText = "";
  let awaitingAssistantResponse = false;
  let loadingElement = null;
  let chartCounter = 0;
  const sidebarStorageKey = "admas-ai-sidebar-collapsed";
  const aiAvatarSrc = "/static/assets/images/token-branded_ais.png";
  // Voice input uses the browser's own speech recognition, in English.
  const SPEECH_LANGUAGE = "en-US";
  let isVoiceRecording = false;
  let voiceTranscriptFinal = "";
  let voiceTranscriptInterim = "";
  let autoScrollPinned = true;
  let suppressNextScrollEventsUntil = 0;
  let lastTouchY = 0;

  function buildAIMessageMarkup(contentHtml) {
    return (
      '<div class="msg-bubble">' +
      '<div class="ai-msg-content">' + contentHtml + "</div>" +
      '<div class="ai-msg-head">' +
      '<div class="ai-msg-actions">' +
      '<button type="button" class="ai-copy-btn" title="Copy the written answer" aria-label="Copy the written answer">' +
      '<i class="ti ti-copy" aria-hidden="true"></i><span>Copy</span>' +
      "</button>" +
      "</div>" +
      "</div>" +
      "</div>"
    );
  }

  function buildAIStreamingMessageMarkup() {
    return (
      '<div class="msg-bubble ai-stream-bubble">' +
      '<div class="ai-stream-draft">' +
      '<div class="ai-stream-draft-label">Writing the answer</div>' +
      '<div class="ai-stream-draft-text"></div>' +
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
    const surface = getThemeValue("--dh-surface-bg", "#ffffff");
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
      surface: surface,
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
    micBtn.title = isVoiceRecording ? "Stop recording" : "Voice input (English)";
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
      chatInput.dispatchEvent(new Event("input"));
      chatInput.focus({ preventScroll: true });
    }
    voiceTranscriptFinal = "";
    voiceTranscriptInterim = "";
  }

  function shouldAllowSidebarCollapse() {
    return window.innerWidth >= 1200;
  }

  // Desktop: the chats rail can be hidden. Smaller screens: it is a drawer, so "Chats" always shows.
  function syncSidebarButtons(collapsed) {
    const desktop = shouldAllowSidebarCollapse();
    if (sidebarExpandBtn) {
      sidebarExpandBtn.hidden = desktop && !collapsed;
    }
    if (sidebarCollapseBtn) {
      sidebarCollapseBtn.hidden = desktop && collapsed;
      sidebarCollapseBtn.setAttribute("aria-label", desktop ? "Hide chats" : "Close chats");
      sidebarCollapseBtn.title = desktop ? "Hide chats" : "Close chats";
    }
  }

  function openDrawer() {
    if (!chatShell) return;
    chatShell.classList.add("is-drawer-open");
    if (railScrim) railScrim.hidden = false;
    const active = getActiveInstanceElement() || document.getElementById("newInstanceBtn");
    if (active) active.focus();
  }

  function closeDrawer() {
    if (!chatShell || !chatShell.classList.contains("is-drawer-open")) return;
    chatShell.classList.remove("is-drawer-open");
    if (railScrim) railScrim.hidden = true;
  }

  function setSidebarCollapsed(collapsed) {
    if (!chatShell) {
      return;
    }

    const nextState = Boolean(collapsed) && shouldAllowSidebarCollapse();
    chatShell.classList.toggle("is-collapsed", nextState);
    syncSidebarButtons(nextState);
    // Charts size themselves on window resize only; the answer column just changed width.
    window.setTimeout(function () {
      window.dispatchEvent(new Event("resize"));
    }, 220);

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

  // A question and its answer are one entry.
  let currentEntry = chatOutput.querySelector(".entry:last-of-type");

  function newEntry() {
    const entry = document.createElement("article");
    entry.className = "entry";
    chatOutput.appendChild(entry);
    currentEntry = entry;
    return entry;
  }

  function entryForAnswer() {
    return currentEntry && currentEntry.isConnected ? currentEntry : newEntry();
  }

  function appendUserMessage(text) {
    const el = document.createElement("div");
    el.className = "msg user";
    el.innerHTML = '<div class="msg-bubble"></div>';
    const bubble = el.querySelector(".msg-bubble");
    if (bubble) {
      bubble.textContent = text;
    }
    newEntry().appendChild(el);
    scrollToBottom();
  }

  function setJumpButtonVisibility() {
    const jumpBtn = document.getElementById("jumpToLatestBtn");
    if (jumpBtn) {
      jumpBtn.hidden = autoScrollPinned;
    }
  }

  function markProgrammaticScroll(durationMs) {
    suppressNextScrollEventsUntil = Date.now() + (durationMs || 180);
  }

  function syncComposerSpace() {
    if (!composer) {
      return;
    }
    const composerHeight = Math.ceil(composer.getBoundingClientRect().height || 0);
    document.documentElement.style.setProperty("--ai-composer-space", Math.max(96, composerHeight + 20) + "px");
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
    entryForAnswer().appendChild(el);
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
      '<div class="ai-loading" role="status"><img class="ai-loading-mark" src="' + aiAvatarSrc + '" alt=""><span>Finding the data…</span></div>'
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
    // The buffer is not reset here: sendMessage already did, and when the tab is in
    // the background (no animation frames) this first runs with the final answer in it.
    if (chatOutput) {
      chatOutput.classList.add("is-generating");
    }
    const el = document.createElement("div");
    el.className = "msg ai is-streaming";
    el.innerHTML = buildAIStreamingMessageMarkup();
    entryForAnswer().appendChild(el);
    streamMessageElement = el;
    streamMessageElement.classList.add("is-streaming");
    streamViewAnchored = false;
    if (autoScrollPinned) {
      scrollToBottom();
    }
    return streamMessageElement;
  }

  function decodeEntities(value) {
    const parser = document.createElement("textarea");
    parser.innerHTML = String(value || "");
    return parser.value;
  }

  function extractStreamingPreviewText(value) {
    const text = String(value || "");
    if (!text) {
      return "";
    }

    const cleaned = text
      .replace(/<chart-data[\s\S]*?<\/chart-data>/gi, " ")
      .replace(/```[\s\S]*?```/g, " ");

    const container = document.createElement("div");
    container.innerHTML = cleaned;

    return decodeEntities(container.textContent || container.innerText || "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function renderStreamBuffer() {
    if (!streamMessageElement && !String(streamHtmlBuffer || "").trim()) {
      return;
    }
    const box = ensureStreamMessage();
    const content = box.querySelector(".ai-stream-draft-text");
    if (!content) {
      return;
    }
    const derivedPreview = extractStreamingPreviewText(streamHtmlBuffer);
    const livePreview = String(streamPreviewText || "").trim() || derivedPreview;
    streamPreviewText = livePreview;
    content.textContent = livePreview || "Thinking...";

    if (autoScrollPinned) {
      scrollToBottom();
    }
  }

  function appendStreamChunk(chunkHtml, previewText) {
    if (!awaitingAssistantResponse) {
      return;
    }
    streamHtmlBuffer += chunkHtml || "";
    if (previewText !== undefined && previewText !== null) {
      streamPreviewText = String(previewText || "").trim();
    }
    if (pendingStreamRender || streamRenderTimer) {
      return;
    }

    streamRenderTimer = window.setTimeout(function () {
      streamRenderTimer = null;
      pendingStreamRender = true;
      requestAnimationFrame(function () {
        pendingStreamRender = false;
        renderStreamBuffer();
      });
    }, 48);
  }

  function flushStreamRender() {
    if (streamRenderTimer) {
      window.clearTimeout(streamRenderTimer);
      streamRenderTimer = null;
    }
    pendingStreamRender = false;
    if (!streamMessageElement && !String(streamHtmlBuffer || "").trim()) {
      return;
    }
    renderStreamBuffer();
  }

  function hydrateMessageNode(node) {
    if (!node) {
      return;
    }
    enhanceTables(node);
    buildDataCards(node);
    renderCharts(node);
    renderActionButtons(node);
  }

  // The three sources answers come from (ai/engine/tools.py), each with questions it answers well.
  const SOURCES = [
    {
      key: "time_series",
      name: "National statistics",
      note: "Time-series database: GDP, inflation, trade, production, health, education.",
      questions: ["What is the GDP growth rate over the last 10 years?", "የዋጋ ግሽበት ስንት ነው?"]
    },
    {
      key: "dpmes",
      name: "Ministry performance",
      note: "DPMES: scores and KPIs of ministries, agencies, policy areas and goals.",
      questions: ["How did the Ministry of Health perform in 2017?", "Which ministries performed best?"]
    },
    {
      key: "sdg",
      name: "SDG progress",
      note: "National SDG platform: the 17 goals, with regional and sex breakdowns.",
      questions: ["How is Ethiopia progressing on SDG 4?", "What is the stunting rate by region?"]
    }
  ];

  const starters = document.getElementById("aiStarters");

  function greeting() {
    const hour = new Date().getHours();
    const part = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
    const name = (chatOutput.dataset.userName || "").trim();
    return part + (name ? ", " + name : "");
  }

  function emptyStateHtml() {
    return (
      '<section class="ai-hello" aria-label="New chat">' +
      '<img class="ai-hello-mark" src="' + aiAvatarSrc + '" alt="">' +
      '<h2 class="ai-hello-title">' + escapeHtml(greeting()) + "</h2>" +
      "</section>"
    );
  }

  // One chip per source; a chip opens two questions that source answers well.
  function startersHtml() {
    return (
      '<div class="ai-starter-row">' +
      SOURCES.map(function (source) {
        return '<button type="button" class="ai-starter" data-source="' + source.key + '" aria-expanded="false" ' +
          'title="' + escapeHtml(source.note) + '">' +
          '<span class="ai-starter-dot" aria-hidden="true"></span>' + escapeHtml(source.name) + "</button>";
      }).join("") +
      "</div>" +
      SOURCES.map(function (source) {
        return '<ul class="ai-starter-list" data-source="' + source.key + '" hidden>' +
          source.questions.map(function (question) {
            return '<li><button type="button" class="ai-suggestion" data-prompt="' + escapeHtml(question) + '">' +
              escapeHtml(question) + "</button></li>";
          }).join("") +
          "</ul>";
      }).join("")
    );
  }

  function showEmptyState() {
    if (!chatOutput.querySelector(".ai-hello")) {
      chatOutput.insertAdjacentHTML("beforeend", emptyStateHtml());
    }
    chatShell.classList.add("is-empty");
    if (starters) {
      starters.innerHTML = startersHtml();
      starters.hidden = false;
    }
  }

  function clearEmptyState() {
    const empty = chatOutput.querySelector(".ai-hello");
    if (empty) {
      empty.remove();
    }
    chatShell.classList.remove("is-empty");
    if (starters) {
      starters.hidden = true;
      starters.innerHTML = "";
    }
  }

  if (starters) {
    starters.addEventListener("click", function (event) {
      const chip = event.target.closest(".ai-starter");
      if (chip) {
        const open = chip.getAttribute("aria-expanded") !== "true";
        starters.querySelectorAll(".ai-starter").forEach(function (other) {
          other.setAttribute("aria-expanded", other === chip && open ? "true" : "false");
        });
        starters.querySelectorAll(".ai-starter-list").forEach(function (list) {
          list.hidden = !(open && list.dataset.source === chip.dataset.source);
        });
        return;
      }
      const question = event.target.closest(".ai-suggestion");
      if (question) {
        chatInput.value = question.dataset.prompt || "";
        syncComposerInput();
        sendMessage();
      }
    });
  }

  // ---- Answer layout: written answer first, then one card per data block ----

  const FREQUENCY_NAMES = { monthly: "Monthly", quarterly: "Quarterly", annual: "Annual" };

  function readPayload(holder, attribute) {
    try {
      return JSON.parse(decodeURIComponent(holder.getAttribute(attribute) || ""));
    } catch (_error) {
      return null;
    }
  }

  // "Ministry of Health: performance score, 2017 EC (annual)"
  //   -> {title: "Ministry of Health", subtitle: "Performance score", chips: ["2017 EC", "Annual"]}
  function parseCardTitle(text) {
    let rest = String(text || "").replace(/\s+/g, " ").trim();
    const chips = [];
    let frequency = "";

    const trailingFrequency = rest.match(/\s*\((monthly|quarterly|annual)\)$/i);
    if (trailingFrequency) {
      frequency = trailingFrequency[1].toLowerCase();
      rest = rest.slice(0, trailingFrequency.index).trim();
    }
    const period = rest.match(/,\s*([^,]*\d{4}[^,]*)$/);
    if (period) {
      chips.push(period[1].trim());
      rest = rest.slice(0, period.index).trim();
    }
    const suffixFrequency = rest.match(/:\s*(monthly|quarterly|annual)$/i);
    if (suffixFrequency) {
      frequency = frequency || suffixFrequency[1].toLowerCase();
      rest = rest.slice(0, suffixFrequency.index).trim();
    }
    if (frequency) {
      chips.push(FREQUENCY_NAMES[frequency]);
    }

    let title = rest;
    let subtitle = "";
    const split = rest.indexOf(": ");
    if (split > 0) {
      title = rest.slice(0, split).trim();
      subtitle = rest.slice(split + 2).trim();
      subtitle = subtitle.charAt(0).toUpperCase() + subtitle.slice(1);
    }
    return { title: title, subtitle: subtitle, chips: chips };
  }

  function decimalsOf(values) {
    return values.reduce(function (most, value) {
      const text = String(value);
      const dot = text.indexOf(".");
      return Math.max(most, dot < 0 ? 0 : Math.min(3, text.length - dot - 1));
    }, 0);
  }

  function formatNumber(value, decimals) {
    return Number(value).toLocaleString(undefined, {
      minimumFractionDigits: 0,
      maximumFractionDigits: decimals
    });
  }

  function unitOf(label) {
    const match = String(label || "").match(/\(([^()]+)\)\s*$/);
    return match ? match[1].trim() : "";
  }

  // Latest / change / high / low, read straight from the chart's own points.
  function buildSeriesStats(payload) {
    const values = payload.data || [];
    const labels = payload.labels || [];
    if (values.length < 2) {
      return "";
    }
    const unit = unitOf(payload.label);
    const percent = unit === "%";
    const decimals = decimalsOf(values);
    const show = function (value) {
      return formatNumber(value, decimals) + (percent ? "%" : "");
    };
    const last = values.length - 1;
    const delta = Number((values[last] - values[last - 1]).toFixed(decimals));
    let high = 0;
    let low = 0;
    values.forEach(function (value, index) {
      if (value > values[high]) high = index;
      if (value < values[low]) low = index;
    });

    const deltaText = (delta > 0 ? "+" : delta < 0 ? "−" : "") + formatNumber(Math.abs(delta), decimals) + (percent ? " pts" : "");
    const deltaIcon = delta > 0 ? "ti-trending-up" : delta < 0 ? "ti-trending-down" : "ti-minus";
    const stat = function (name, value, note, extraClass) {
      return '<div class="ai-stat' + (extraClass ? " " + extraClass : "") + '">' +
        '<span class="ai-stat-name">' + escapeHtml(name) + "</span>" +
        '<span class="ai-stat-value">' + value + "</span>" +
        '<span class="ai-stat-note">' + escapeHtml(note) + "</span>" +
        "</div>";
    };

    return (
      '<div class="ai-stats">' +
      stat("Latest", escapeHtml(show(values[last])), labels[last] || "", "is-primary") +
      stat("Change", '<i class="ti ' + deltaIcon + '" aria-hidden="true"></i>' + escapeHtml(deltaText), "from " + (labels[last - 1] || "previous")) +
      stat("High", escapeHtml(show(values[high])), labels[high] || "") +
      stat("Low", escapeHtml(show(values[low])), labels[low] || "") +
      "</div>" +
      (unit && !percent ? '<div class="ai-stats-unit">Values in ' + escapeHtml(unit) + "</div>" : "")
    );
  }

  function isScorePayload(payload) {
    return payload && payload.type === "pie" && payload.data.length === 1 && payload.data[0] >= 0 && payload.data[0] <= 100;
  }

  function buildScoreHero(_holder, payload) {
    const value = payload.data[0];
    const band = payload.labels && payload.labels[0] ? payload.labels[0] : "";
    const hero = document.createElement("div");
    hero.className = "ai-score";
    hero.style.setProperty("--score-color", payload.score_color || "var(--dh-text)");
    hero.innerHTML =
      '<div class="ai-score-figure">' +
      '<span class="ai-score-number">' + escapeHtml(formatNumber(value, 2)) + "<small>%</small></span>" +
      (band ? '<span class="ai-score-band"><span class="ai-score-dot" aria-hidden="true"></span>' + escapeHtml(band) + "</span>" : "") +
      "</div>" +
      '<div class="ai-score-meter" role="img" aria-label="' + escapeHtml(formatNumber(value, 2)) + ' out of 100">' +
      '<span style="width:' + Math.max(0, Math.min(100, value)) + '%"></span></div>' +
      '<span class="ai-score-caption">Overall score, out of 100</span>';
    return hero;
  }

  // render.py marks the source line; answers saved before that are told apart by its text.
  function sourceKind(line) {
    if (line.dataset.source) {
      return line.dataset.source;
    }
    const text = line.textContent || "";
    if (/SDG platform/i.test(text)) return "sdg";
    if (/\bDPMES\b/.test(text)) return "dpmes";
    return "time_series";
  }

  // SDG panels carry their goal's official icon from the national SDG platform
  // (the dashboard's SDG pages use the same ones). render.py marks the goal on
  // the source line; older answers have only the title ("SDG 4 …", "4.1.1 …").
  const SDG_ICON_BASE = "https://sdg.mopd.gov.et/icons/frameworks/sdg-icons/";

  function sdgGoalFor(group) {
    const source = group.sources[0];
    let goal = source && source.dataset.sdgGoal;
    if (!goal && source && sourceKind(source) === "sdg") {
      const title = group.heading ? group.heading.textContent : "";
      const match = title.match(/\bSDG\s*(\d{1,2})\b/i) || title.match(/\b(\d{1,2})\.[0-9a-z]{1,2}\.\d/i);
      goal = match ? match[1] : "";
    }
    const number = parseInt(goal, 10);
    return number >= 1 && number <= 17 ? String(number) : "";
  }

  function sdgIcon(goal) {
    const icon = document.createElement("img");
    icon.className = "ai-sdg-icon";
    icon.src = SDG_ICON_BASE + goal + ".svg";
    icon.alt = "SDG " + goal;
    icon.title = "Sustainable Development Goal " + goal;
    icon.width = 40;
    icon.height = 40;
    icon.loading = "lazy";
    icon.decoding = "async";
    icon.addEventListener("error", function () { icon.remove(); });
    return icon;
  }

  function buildDataCard(group) {
    const card = document.createElement("section");
    card.className = "ai-data-card";

    const parsed = parseCardTitle(group.heading ? group.heading.textContent : "");
    const head = document.createElement("header");
    head.className = "ai-data-card-head";
    const facts = [parsed.subtitle].concat(parsed.chips).filter(Boolean);
    const frequency = parsed.chips.find(function (chip) {
      return Object.values(FREQUENCY_NAMES).indexOf(chip) >= 0;
    }) || "";
    // render.py writes one source line per result, after its last block, so the
    // series' earlier frequencies have none: match on the indicator alone.
    card.dataset.key = parsed.title || "";
    card.dataset.freq = frequency;
    card.dataset.metaBase = facts.filter(function (fact) { return fact !== frequency; }).join(" · ");
    head.innerHTML =
      '<div class="ai-data-card-titles">' +
      '<h4 class="ai-data-card-title">' + escapeHtml(parsed.title || "Data") + "</h4>" +
      (facts.length ? '<span class="ai-data-card-meta">' + escapeHtml(facts.join(" · ")) + "</span>" : "") +
      "</div>";
    const sdgGoal = sdgGoalFor(group);
    if (sdgGoal) {
      head.insertBefore(sdgIcon(sdgGoal), head.firstChild);
      card.classList.add("has-sdg-icon");
    }
    card.appendChild(head);

    const charts = [];
    let scoreHero = null;
    let stats = "";
    group.charts.forEach(function (holder) {
      const payload = readPayload(holder, "data-chart");
      if (isScorePayload(payload)) {
        // Drawn as a number with a meter (buildScoreHero), not as a chart.
        holder.remove();
        scoreHero = buildScoreHero(holder, payload);
        return;
      }
      if (payload && payload.type === "line" && !stats && !(payload.series && payload.series.length > 1)) {
        stats = buildSeriesStats(payload);
      }
      charts.push({ holder: holder, payload: payload });
    });

    const variant = document.createElement("div");
    variant.className = "ai-variant";
    variant.dataset.freq = frequency;
    card.appendChild(variant);

    if (scoreHero || stats) {
      const summary = document.createElement("div");
      summary.className = "ai-data-card-summary";
      if (scoreHero) {
        summary.appendChild(scoreHero);
      }
      if (stats) {
        summary.insertAdjacentHTML("beforeend", stats);
      }
      variant.appendChild(summary);
    }

    const body = document.createElement("div");
    body.className = "ai-data-card-body";
    const panes = {};
    if (charts.length) {
      panes.chart = document.createElement("div");
      panes.chart.className = "ai-view-pane";
      panes.chart.dataset.view = "chart";
      charts.forEach(function (chart) { panes.chart.appendChild(chart.holder); });
      body.appendChild(panes.chart);
    }
    if (group.tables.length) {
      panes.table = document.createElement("div");
      panes.table.className = "ai-view-pane";
      panes.table.dataset.view = "table";
      group.tables.forEach(function (table) { panes.table.appendChild(table); });
      body.appendChild(panes.table);
    }
    if (panes.chart || panes.table) {
      variant.appendChild(body);
    }

    if (panes.chart && panes.table) {
      // A time series reads best as a chart; scores read best as the table, which carries its own bars.
      const firstType = charts[0].payload ? charts[0].payload.type : "";
      const initial = firstType === "line" || firstType === "area" ? "chart" : "table";
      const toggle = document.createElement("div");
      toggle.className = "ai-view-toggle";
      toggle.setAttribute("role", "group");
      toggle.setAttribute("aria-label", "Show as");
      toggle.innerHTML =
        '<button type="button" class="ai-view-btn" data-view="chart"><i class="ti ti-chart-line" aria-hidden="true"></i><span>Chart</span></button>' +
        '<button type="button" class="ai-view-btn" data-view="table"><i class="ti ti-table" aria-hidden="true"></i><span>Table</span></button>';
      head.appendChild(toggle);
      setCardView(card, initial);
    }

    const sourceKey = group.sources.length ? sourceKind(group.sources[0]) : "";
    if (sourceKey) {
      card.dataset.source = sourceKey;
    }

    if (group.actions.length || group.sources.length) {
      const foot = document.createElement("footer");
      foot.className = "ai-data-card-foot";
      group.sources.forEach(function (source) {
        source.title = source.textContent.trim();
        source.insertAdjacentHTML("afterbegin", '<span class="ai-source-dot" aria-hidden="true"></span>');
        foot.appendChild(source);
      });
      group.actions.forEach(function (action) { foot.appendChild(action); });
      card.appendChild(foot);
    }
    return card;
  }

  // One panel per series: its monthly, quarterly and annual blocks become tabs.
  function mergeFrequencyCards(content) {
    let lead = null;
    Array.from(content.children).forEach(function (card) {
      if (!card.classList.contains("ai-data-card")) {
        lead = null;
        return;
      }
      if (lead && card.dataset.freq && card.dataset.key === lead.dataset.key) {
        const variant = card.querySelector(".ai-variant");
        if (variant) {
          lead.insertBefore(variant, lead.querySelector(".ai-data-card-foot"));
        }
        // The series' source line comes with its last block.
        const foot = card.querySelector(".ai-data-card-foot");
        if (foot && !lead.querySelector(".ai-data-card-foot")) {
          lead.appendChild(foot);
        }
        if (card.dataset.source && !lead.dataset.source) {
          lead.dataset.source = card.dataset.source;
        }
        card.remove();
        return;
      }
      lead = card.dataset.freq ? card : null;
    });

    content.querySelectorAll(".ai-data-card").forEach(function (card) {
      const variants = card.querySelectorAll(".ai-variant");
      if (variants.length < 2) {
        return;
      }
      const meta = card.querySelector(".ai-data-card-meta");
      if (meta) {
        meta.textContent = card.dataset.metaBase || "";
      }
      const tabs = document.createElement("div");
      tabs.className = "ai-freq-tabs";
      tabs.setAttribute("role", "tablist");
      tabs.setAttribute("aria-label", "Frequency");
      tabs.innerHTML = Array.from(variants).map(function (variant) {
        return '<button type="button" class="ai-freq-btn" role="tab" data-freq="' + escapeHtml(variant.dataset.freq) + '">' +
          escapeHtml(variant.dataset.freq) + "</button>";
      }).join("");
      const head = card.querySelector(".ai-data-card-head");
      head.insertBefore(tabs, head.querySelector(".ai-view-toggle"));
      // Annual first when there is one: it is the figure the written answer usually quotes.
      const annual = Array.from(variants).find(function (variant) { return variant.dataset.freq === FREQUENCY_NAMES.annual; });
      setCardFrequency(card, (annual || variants[0]).dataset.freq);
    });
  }

  function setCardFrequency(card, frequency) {
    // Collapsed, not display:none, so each variant's chart keeps its width.
    card.querySelectorAll(".ai-variant").forEach(function (variant) {
      const off = variant.dataset.freq !== frequency;
      variant.classList.toggle("is-off", off);
      variant.setAttribute("aria-hidden", off ? "true" : "false");
    });
    card.querySelectorAll(".ai-freq-btn").forEach(function (button) {
      const active = button.dataset.freq === frequency;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-selected", active ? "true" : "false");
    });
  }

  function setCardView(card, view) {
    // Panes are collapsed, not display:none, so a chart keeps its width (and survives window resizes).
    card.querySelectorAll(".ai-view-pane").forEach(function (pane) {
      const off = pane.dataset.view !== view;
      pane.classList.toggle("is-off", off);
      pane.setAttribute("aria-hidden", off ? "true" : "false");
    });
    card.querySelectorAll(".ai-view-btn").forEach(function (button) {
      const active = button.dataset.view === view;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
  }

  function buildDataCards(node) {
    const content = node.querySelector(".ai-msg-content");
    if (!content || content.dataset.cards === "1") {
      return;
    }
    content.dataset.cards = "1";


    const groups = [];
    let current = null;
    Array.from(content.children).forEach(function (child) {
      if (/^H[34]$/.test(child.tagName)) {
        current = { anchor: child, heading: child, tables: [], charts: [], actions: [], sources: [] };
        groups.push(current);
        return;
      }
      // The line naming where a block's figures come from (render.py) closes that block.
      if (child.classList.contains("ai-source")) {
        if (current) {
          current.sources.push(child);
          current = null;
        }
        return;
      }
      const isTable = child.classList.contains("ai-table-wrap");
      const isChart = child.classList.contains("ai-chart-payload");
      const isAction = child.classList.contains("ai-action-payload");
      if (!isTable && !isChart && !isAction) {
        current = null;
        return;
      }
      if (!current) {
        current = { anchor: child, heading: null, tables: [], charts: [], actions: [], sources: [] };
        groups.push(current);
      }
      (isTable ? current.tables : isChart ? current.charts : current.actions).push(child);
    });

    // A data answer opens with the direct answer (see compose.py); give that sentence weight.
    const first = content.firstElementChild;
    if (groups.length && first && first.tagName === "P" && first.textContent.trim().length <= 200) {
      first.classList.add("ai-lead");
    }

    groups.forEach(function (group) {
      if (!group.tables.length && !group.charts.length && !group.actions.length) {
        return;
      }
      const placeholder = document.createElement("div");
      content.insertBefore(placeholder, group.anchor);
      const card = buildDataCard(group);
      if (group.heading && group.heading.parentNode) {
        group.heading.remove();
      }
      content.replaceChild(card, placeholder);
    });
    mergeFrequencyCards(content);
  }

  function getReadableMessageText(node) {
    const content = node ? node.querySelector(".ai-msg-content") : null;
    if (!content) {
      return "";
    }

    const clone = content.cloneNode(true);
    const nonSpeechSelectors = [
      ".ai-data-card",
      ".ai-suggestions",
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

  function normalizeAIContent(value) {
    let text = String(value || "");

    // Some providers return escaped HTML; decode once so tags can render.
    if (text.includes("&lt;table") || text.includes("&lt;tr") || text.includes("&lt;td")) {
      const parser = document.createElement("textarea");
      parser.innerHTML = text;
      text = parser.value;
    }

    text = convertMarkdownTablesToHtml(text);
    text = injectChartDataTagPlaceholders(text);
    text = injectStructuredPayloadPlaceholders(text);
    return text;
  }

  function injectChartDataTagPlaceholders(text) {
    if (!text || text.indexOf("chart-data") < 0) {
      return text;
    }

    const pattern = /<chart-data[^>]*>([\s\S]*?)<\/chart-data>/gi;
    return String(text).replace(pattern, function (_match, body) {
      const payload = parseStructuredPayload(String(body || "").trim());
      if (!payload) {
        return "";
      }
      return buildPayloadPlaceholder(payload);
    });
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
      const placeholder = buildPayloadPlaceholder(block.payload);
      if (!placeholder) {
        continue;
      }
      output = output.slice(0, block.start) + placeholder + output.slice(block.end);
    }
    return output;
  }

  function buildPayloadPlaceholder(payload) {
    if (!payload || !payload.kind) {
      return "";
    }

    const encoded = encodeURIComponent(JSON.stringify(payload));

    if (payload.kind === "chart") {
      return (
        '<div class="ai-chart-payload" data-chart="' +
        encoded +
        '">' +
        '<div class="ai-chart-loading">Preparing chart...</div>' +
        "</div>"
      );
    }

    if (payload.kind === "button") {
      return '<div class="ai-action-payload" data-action="' + encoded + '"></div>';
    }

    return "";
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
    if (!raw) {
      return null;
    }

    const decoded = String(raw)
      .replace(/&quot;/g, '"')
      .replace(/&#34;/g, '"')
      .replace(/&apos;/g, "'")
      .replace(/&#39;/g, "'")
      .replace(/&lt;/g, "<")
      .replace(/&gt;/g, ">")
      .replace(/&amp;/g, "&")
      .trim();

    const withoutTags = decoded
      .replace(/<chart-data[^>]*>/gi, "")
      .replace(/<\/chart-data>/gi, "")
      .trim();

    const withoutFence = withoutTags
      .replace(/^```(?:json)?\s*/i, "")
      .replace(/\s*```$/i, "")
      .trim();

    const candidates = [];
    const baseCandidate = withoutFence
      .replace(/[“”]/g, '"')
      .replace(/[‘’]/g, "'")
      .replace(/,\s*([}\]])/g, "$1")
      .trim();

    if (baseCandidate) {
      candidates.push(baseCandidate);
      if (!baseCandidate.includes('"') && baseCandidate.includes("'")) {
        candidates.push(baseCandidate.replace(/'/g, '"'));
      }
      if (baseCandidate.includes('\\"')) {
        candidates.push(baseCandidate.replace(/\\"/g, '"'));
      }
    }

    let obj = null;
    for (let i = 0; i < candidates.length; i += 1) {
      const candidate = candidates[i];
      try {
        obj = JSON.parse(candidate);
      } catch (_parseError) {
        continue;
      }
      if (typeof obj === "string") {
        try {
          obj = JSON.parse(obj);
        } catch (_nestedParseError) {
          // Keep raw string object if nested parse fails.
        }
      }
      if (obj && typeof obj === "object") {
        break;
      }
      obj = null;
    }

    if (!obj || typeof obj !== "object") {
      return null;
    }

    if (obj.chart && typeof obj.chart === "object") {
      obj = obj.chart;
    }

    const typeRaw = obj.type || obj.chart_type || obj.chartType || obj.kind || "";
    const type = String(typeRaw).trim().toLowerCase();
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

    const labelsSource = obj.labels || obj.categories || obj.x || [];
    const dataSource = obj.data || obj.values || obj.y || [];
    const labelsRaw = Array.isArray(labelsSource) ? labelsSource : [labelsSource];
    let dataRaw = Array.isArray(dataSource) ? dataSource : [dataSource];

    if (!dataRaw.length && Array.isArray(obj.series) && obj.series.length) {
      const primarySeries = obj.series[0];
      if (Array.isArray(primarySeries)) {
        dataRaw = primarySeries;
      } else if (primarySeries && typeof primarySeries === "object") {
        dataRaw = Array.isArray(primarySeries.data) ? primarySeries.data : [];
      }
    }

    if (dataRaw.length && typeof dataRaw[0] === "object" && dataRaw[0] !== null) {
      const points = dataRaw.filter(function (point) {
        return point && typeof point === "object";
      });
      if (points.length) {
        dataRaw = points.map(function (point) {
          return point.y !== undefined ? point.y : point.value;
        });
        if (!labelsRaw.length || String(labelsRaw[0] || "").trim() === "") {
          labelsRaw.splice(0, labelsRaw.length);
          points.forEach(function (point, index) {
            labelsRaw.push(point.x !== undefined ? point.x : point.label !== undefined ? point.label : String(index + 1));
          });
        }
      }
    }

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

    const pointCount = data.length;
    if (!pointCount) return null;

    const normalizedLabels = (labels.length ? labels : data.map(function (_value, index) {
      return String(index + 1);
    })).slice(0, pointCount);
    const normalizedData = data.slice(0, pointCount);

    return {
      kind: "chart",
      type: type,
      label: obj.label ? String(obj.label) : "AI Chart",
      labels: normalizedLabels,
      data: normalizedData,
      score_color: obj.score_color ? String(obj.score_color).trim() : "",
      frequency: normalizeFrequencyKey(obj.frequency || obj.group || obj.data_type || obj.frequency_type || ""),
      section_title: obj.section_title ? String(obj.section_title) : (obj.title ? String(obj.title) : ""),
      value_label: obj.value_label ? String(obj.value_label) : "",
      period_label: obj.period_label ? String(obj.period_label) : "",
      // Several named lines (SDG breakdowns); "labels"/"data" hold the first.
      series: Array.isArray(obj.series) ? obj.series.filter(function (s) {
        return s && Array.isArray(s.points) && s.points.length;
      }).map(function (s) {
        return {
          name: String(s.name || ""),
          points: s.points.map(function (pt) { return [String(pt[0]), Number(pt[1])]; }).filter(function (pt) {
            return Number.isFinite(pt[1]);
          })
        };
      }) : []
    };
  }

  function normalizeFrequencyKey(value) {
    const normalized = String(value || "").trim().toLowerCase();
    if (!normalized) {
      return "";
    }
    if (["month", "months", "monthly"].includes(normalized)) {
      return "monthly";
    }
    if (["quarter", "quarters", "quarterly"].includes(normalized)) {
      return "quarterly";
    }
    if (["year", "years", "yearly", "annual", "annually"].includes(normalized)) {
      return "annual";
    }
    return normalized;
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
      const firstHeader = table.querySelector("thead th");
      // A period column already orders the rows; a row number would only add noise.
      if (!firstHeader || firstHeader.textContent.trim().toLowerCase() !== "period") {
        ensureNumberingColumn(table);
      }
      decorateTableCells(table);
      if (!table.parentElement || !table.parentElement.classList.contains("ai-table-wrap")) {
        const wrap = document.createElement("div");
        wrap.className = "ai-table-wrap";
        table.parentNode.insertBefore(wrap, table);
        wrap.appendChild(table);
      }
    });
  }

  const MAX_CHART_BARS = 12;

  function shortLabel(label, max) {
    const text = String(label || "");
    return text.length > max ? text.slice(0, max - 1).trimEnd() + "…" : text;
  }

  function chartOptions(payload, theme, width) {
    const color = payload.score_color || theme.accent;
    const decimals = decimalsOf(payload.data);
    const unit = unitOf(payload.label);
    const valueText = function (val) {
      return val === null || val === undefined ? "" : formatNumber(val, decimals) + (unit === "%" ? "%" : "");
    };
    const base = {
      chart: {
        height: width && width < 480 ? 180 : 210,
        background: "transparent",
        fontFamily: "inherit",
        toolbar: { show: false },
        zoom: { enabled: false },
        animations: { enabled: true, speed: 420 }
      },
      dataLabels: { enabled: false },
      colors: [color],
      grid: {
        borderColor: theme.border,
        strokeDashArray: 4,
        padding: { left: 8, right: 12 }
      },
      tooltip: { theme: theme.tooltipTheme, y: { formatter: valueText } },
      legend: { show: false },
      states: { hover: { filter: { type: "darken", value: 0.92 } } }
    };

    if (isScorePayload(payload)) {
      return Object.assign({}, base, {
        chart: Object.assign({}, base.chart, { type: "radialBar", height: 150, sparkline: { enabled: true } }),
        series: [payload.data[0]],
        labels: [payload.labels[0] || "Score"],
        plotOptions: {
          radialBar: {
            startAngle: -120,
            endAngle: 120,
            hollow: { size: "62%" },
            track: { background: theme.pieFallback, strokeWidth: "100%" },
            dataLabels: { show: false }
          }
        },
        stroke: { lineCap: "round" },
        tooltip: { enabled: false }
      });
    }

    if (payload.type === "pie") {
      return Object.assign({}, base, {
        chart: Object.assign({}, base.chart, { type: "donut", height: 280 }),
        series: payload.data,
        labels: payload.labels,
        colors: [theme.accent, theme.accentStrong, "#d97706", "#6366f1", "#0ea5e9", "#e11d48", theme.muted],
        legend: { show: true, position: "bottom", labels: { colors: theme.muted } },
        plotOptions: { pie: { donut: { size: "64%" } } }
      });
    }

    // Several named lines (an SDG indicator by poverty type, by sex…), one colour each.
    if (payload.series && payload.series.length > 1) {
      const years = Array.from(new Set(payload.series.reduce(function (all, s) {
        return all.concat(s.points.map(function (pt) { return pt[0]; }));
      }, []))).sort(function (a, b) { return Number(a) - Number(b) || String(a).localeCompare(String(b)); });
      const allValues = payload.series.reduce(function (all, s) {
        return all.concat(s.points.map(function (pt) { return pt[1]; }));
      }, []);
      const seriesDecimals = decimalsOf(allValues);
      const seriesText = function (val) {
        return val === null || val === undefined ? "–" : formatNumber(val, seriesDecimals) + (unit === "%" ? "%" : "");
      };
      return Object.assign({}, base, {
        chart: Object.assign({}, base.chart, { type: payload.type === "bar" ? "bar" : "line" }),
        // The first line in the source's colour; the rest in ink, since colour marks sources only.
        colors: [theme.accent, theme.text, theme.muted, theme.elevatedBorder, theme.text, theme.muted],
        stroke: payload.type === "bar" ? { width: 0 } : { curve: "monotoneCubic", width: [2.5, 2, 2, 2, 2, 2], dashArray: [0, 0, 5, 0, 3, 8] },
        series: payload.series.map(function (s) {
          const byYear = {};
          s.points.forEach(function (pt) { byYear[pt[0]] = pt[1]; });
          return { name: s.name, data: years.map(function (year) { return year in byYear ? byYear[year] : null; }) };
        }),
        markers: payload.type === "bar" ? undefined : { size: 4, strokeWidth: 2, strokeColors: theme.surface, hover: { size: 5 } },
        plotOptions: { bar: { borderRadius: 4, borderRadiusApplication: "end", columnWidth: "56%" } },
        legend: { show: true, position: "bottom", labels: { colors: theme.muted }, markers: { size: 5 } },
        tooltip: { theme: theme.tooltipTheme, shared: true, intersect: false, y: { formatter: seriesText } },
        xaxis: {
          categories: years,
          labels: { style: { colors: theme.muted }, rotate: 0, hideOverlappingLabels: true },
          axisBorder: { show: false },
          axisTicks: { show: false },
          tooltip: { enabled: false }
        },
        yaxis: {
          tickAmount: 4,
          labels: { style: { colors: [theme.muted] }, formatter: function (val) { return formatNumber(val, seriesDecimals); } }
        }
      });
    }

    if (payload.type === "bar") {
      const longest =payload.labels.reduce(function (most, label) { return Math.max(most, String(label).length); }, 0);
      const horizontal = longest > 12 || payload.labels.length > 8;
      const common = Object.assign({}, base, {
        series: [{ name: shortLabel(payload.label, 60), data: payload.data }],
        plotOptions: {
          bar: {
            horizontal: horizontal,
            borderRadius: 5,
            borderRadiusApplication: "end",
            barHeight: "68%",
            columnWidth: "48%"
          }
        },
        tooltip: {
          theme: theme.tooltipTheme,
          x: { formatter: function (_val, opts) { return payload.labels[opts.dataPointIndex] || ""; } },
          y: { formatter: valueText, title: { formatter: function () { return ""; } } }
        }
      });
      if (horizontal) {
        return Object.assign(common, {
          chart: Object.assign({}, base.chart, { type: "bar", height: Math.max(150, payload.labels.length * 24 + 44) }),
          grid: Object.assign({}, base.grid, { xaxis: { lines: { show: true } }, yaxis: { lines: { show: false } } }),
          xaxis: {
            categories: payload.labels,
            labels: { style: { colors: theme.muted }, formatter: function (val) { return formatNumber(val, decimals); } },
            axisBorder: { show: false },
            axisTicks: { show: false }
          },
          yaxis: {
            labels: {
              maxWidth: 240,
              style: { colors: [theme.text], fontSize: "12px" },
              formatter: function (val) { return shortLabel(val, 34); }
            }
          }
        });
      }
      return Object.assign(common, {
        chart: Object.assign({}, base.chart, { type: "bar" }),
        xaxis: {
          categories: payload.labels,
          labels: { style: { colors: theme.muted }, hideOverlappingLabels: true, rotate: 0, trim: true },
          axisBorder: { show: false },
          axisTicks: { show: false }
        },
        yaxis: { labels: { style: { colors: [theme.muted] }, formatter: function (val) { return formatNumber(val, decimals); } } }
      });
    }

    // line / area: a time series. Label every nth period so labels never collide; always label the latest.
    const count = payload.labels.length;
    const longestPeriod = payload.labels.reduce(function (most, label) { return Math.max(most, String(label).length); }, 0);
    const fits = Math.max(2, Math.floor((width || 600) / Math.max(48, longestPeriod * 7 + 16)));
    const step = Math.max(1, Math.ceil(count / fits));
    const many = count > 8;
    return Object.assign({}, base, {
      chart: Object.assign({}, base.chart, { type: "area" }),
      series: [{
        name: shortLabel(payload.label, 60),
        data: payload.labels.map(function (label, index) { return { x: label, y: payload.data[index] }; })
      }],
      // Monotone: the line never swings past the real highs and lows between points.
      stroke: { curve: "monotoneCubic", width: 2.5 },
      tooltip: {
        theme: theme.tooltipTheme,
        x: { formatter: function (_value, opts) { return payload.labels[opts.dataPointIndex] || ""; } },
        y: { formatter: valueText }
      },
      fill: {
        type: "gradient",
        gradient: { shadeIntensity: 1, opacityFrom: 0.28, opacityTo: 0.02, stops: [0, 95] }
      },
      markers: {
        size: many ? 0 : 4,
        strokeWidth: 2,
        strokeColors: theme.surface,
        hover: { size: 5 },
        discrete: [{
          seriesIndex: 0,
          dataPointIndex: payload.data.length - 1,
          fillColor: color,
          strokeColor: theme.surface,
          size: 6
        }]
      },
      xaxis: {
        type: "category",
        labels: {
          style: { colors: theme.muted },
          rotate: 0,
          hideOverlappingLabels: false,
          trim: false,
          formatter: function (value) {
            const index = payload.labels.indexOf(value);
            return index < 0 || (count - 1 - index) % step === 0 ? value : "";
          }
        },
        axisBorder: { show: false },
        axisTicks: { show: false },
        tooltip: { enabled: false }
      },
      yaxis: {
        tickAmount: 4,
        labels: { style: { colors: [theme.muted] }, formatter: function (val) { return formatNumber(val, decimals); } }
      },
      annotations: Math.min.apply(null, payload.data) < 0 ? {
        yaxis: [{ y: 0, borderColor: theme.muted, strokeDashArray: 0, opacity: 0.6 }]
      } : undefined
    });
  }

  function renderCharts(scope) {
    const root = scope || document;
    const placeholders = root.querySelectorAll(".ai-chart-payload");

    placeholders.forEach(function (holder) {
      if (holder.dataset.rendered === "1") {
        return;
      }
      // A chart needs the page's width to draw; cards are built before they are inserted.
      if (!holder.isConnected) {
        return;
      }

      let payload = readPayload(holder, "data-chart");
      if (!payload) {
        holder.dataset.rendered = "1";
        holder.innerHTML = '<div class="ai-chart-error">This chart could not be read.</div>';
        return;
      }

      // A long bar list (25 KPIs) charts its first bars only; the table lists them all.
      let shortened = "";
      if (payload.type === "bar" && !(payload.series && payload.series.length > 1) && payload.labels.length > MAX_CHART_BARS) {
        shortened = "First " + MAX_CHART_BARS + " of " + payload.labels.length + ". The table lists all of them.";
        payload = Object.assign({}, payload, {
          labels: payload.labels.slice(0, MAX_CHART_BARS),
          data: payload.data.slice(0, MAX_CHART_BARS)
        });
      }

      const inCard = Boolean(holder.closest(".ai-data-card"));
      if (!window.ApexCharts) {
        holder.dataset.rendered = "1";
        if (payload.type === "bar") {
          renderBarChart(holder, payload);
        } else {
          holder.innerHTML = '<div class="ai-chart-error">Charts are unavailable; see the table.</div>';
        }
        return;
      }

      holder.innerHTML =
        (inCard ? "" : '<div class="ai-chart-title">' + escapeHtml(payload.label || "Chart") + "</div>") +
        '<div class="ai-chart-canvas" id="aiChart' + (chartCounter += 1) + '"></div>' +
        (shortened ? '<p class="ai-chart-note">' + escapeHtml(shortened) + "</p>" : "");

      const chartEl = holder.querySelector(".ai-chart-canvas");
      holder.dataset.rendered = "1";
      try {
        const theme = getAIChartTheme();
        const block = holder.closest(".ai-data-card[data-source]");
        const band = block ? window.getComputedStyle(block).getPropertyValue("--band").trim() : "";
        if (band) {
          // The source's band colour, resolved from var() to a value ApexCharts can use.
          const probe = document.createElement("span");
          probe.style.color = band;
          block.appendChild(probe);
          theme.accent = window.getComputedStyle(probe).color;
          probe.remove();
        }
        const chart = new window.ApexCharts(chartEl, chartOptions(payload, theme, chartEl.clientWidth));
        holder.aiChart = chart;
        chart.render().catch(function () {
          if (payload.type === "bar") {
            renderBarChart(holder, payload);
          } else {
            holder.innerHTML = '<div class="ai-chart-error">This chart could not be drawn; see the table.</div>';
          }
        });
      } catch (_err) {
        if (payload.type === "bar") {
          renderBarChart(holder, payload);
        } else {
          holder.innerHTML = '<div class="ai-chart-error">This chart could not be drawn; see the table.</div>';
        }
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
      '<div class="ai-chart-title">' + escapeHtml(payload.label || "AI Chart") + "</div>" +
      '<div class="ai-bar-chart">' + bars + "</div>";
  }

  // Destroy before the element goes away: a chart left behind keeps redrawing into a detached node.
  function destroyCharts(root) {
    (root || document).querySelectorAll(".ai-chart-payload").forEach(function (holder) {
      if (holder.aiChart) {
        try {
          holder.aiChart.destroy();
        } catch (_error) {
          // Already gone.
        }
        holder.aiChart = null;
      }
    });
  }

  function rerenderAICharts() {
    destroyCharts(document);
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

      const title = payload.button_type === "ministry_detail" ? "View ministry detail" : "Run action";
      holder.innerHTML =
        '<button type="button" class="ai-action-btn" data-action-type="' + escapeHtml(payload.button_type || "") + '"' +
        ' data-id="' + escapeHtml(payload.id || "") + '"' +
        ' data-year="' + escapeHtml(payload.year || "") + '"' +
        ' data-quarter="' + escapeHtml(payload.quarter || "") + '">' +
        "<span>" + escapeHtml(title) + '</span><i class="ti ti-arrow-right" aria-hidden="true"></i>' +
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
    const messages = container.querySelectorAll(".msg.ai");
    messages.forEach(function (message) {
      if (message.dataset.hydrated === "1") {
        return;
      }
      const block = message.querySelector(".ai-msg-content");
      if (!block) {
        return;
      }
      block.innerHTML = normalizeAIContent(block.innerHTML);
      hydrateMessageNode(message);
      message.dataset.hydrated = "1";
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

    let alreadyNumbered = false;
    if (theadRow) {
      const firstHeader = theadRow.firstElementChild;
      const firstHeaderText = (firstHeader && firstHeader.textContent || "").trim().toLowerCase();
      alreadyNumbered = firstHeaderText === "#";
      if (!alreadyNumbered) {
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
      if (alreadyNumbered && firstCell) {
        // The server sent its own "#" column (rankings): keep its numbers.
        firstCell.classList.add("ai-cell-number");
        return;
      }
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

  const NUMBER_PATTERN = /^[−-]?\d[\d,]*(\.\d+)?%?$/;

  // Right-align number columns; turn coloured score cells into a value with a bar.
  function decorateTableCells(table) {
    if (table.dataset.decorated === "1") {
      return;
    }
    table.dataset.decorated = "1";
    const headers = Array.from(table.querySelectorAll("thead th"));
    const rows = Array.from(table.querySelectorAll("tbody tr"));

    headers.forEach(function (th, column) {
      if (th.classList.contains("ai-col-number")) {
        return;
      }
      const cells = rows.map(function (row) { return row.children[column]; }).filter(Boolean);
      const filled = cells.filter(function (cell) {
        const text = cell.textContent.trim();
        return text && text !== "–";
      });
      const numeric = filled.length > 0 && filled.every(function (cell) {
        return NUMBER_PATTERN.test(cell.textContent.trim());
      });
      if (!numeric) {
        return;
      }
      th.classList.add("ai-col-num");
      const isScore = /score/i.test(th.textContent);
      cells.forEach(function (cell) {
        cell.classList.add("ai-cell-num");
        const coloured = cell.querySelector("span[style]");
        const value = parseFloat(cell.textContent.replace(/,/g, "").replace("−", "-"));
        if (!isScore || !coloured || !Number.isFinite(value)) {
          return;
        }
        const color = coloured.style.color || "";
        const width = Math.max(0, Math.min(100, value));
        cell.classList.add("ai-cell-score");
        cell.innerHTML =
          '<span class="ai-score-cell" style="--score-color:' + escapeHtml(color) + '">' +
          '<span class="ai-score-track" aria-hidden="true"><span class="ai-score-fill" style="width:' + width + '%"></span></span>' +
          '<span class="ai-score-value">' + escapeHtml(cell.textContent.trim()) + "</span>" +
          "</span>";
      });
    });
  }

  function stripInlineTableStyles(table) {
    const nodes = table.querySelectorAll("thead,tbody,tr,th,td");
    table.removeAttribute("style");
    nodes.forEach(function (node) {
      node.removeAttribute("style");
    });
  }

  function finishStream(finalMessageHtml) {
    awaitingAssistantResponse = false;
    const hasFinalHtml = Boolean(String(finalMessageHtml || "").trim());
    if (hasFinalHtml) {
      streamHtmlBuffer = String(finalMessageHtml || "");
    }

    flushStreamRender();

    if (streamMessageElement) {
      streamMessageElement.classList.remove("is-streaming");
      streamMessageElement.classList.add("is-fresh");
      streamMessageElement.innerHTML = buildAIMessageMarkup(normalizeAIContent(streamHtmlBuffer));
      hydrateMessageNode(streamMessageElement);
    } else if (hasFinalHtml) {
      appendAIMessageHtml(finalMessageHtml).classList.add("is-fresh");
    }

    if (chatOutput) {
      chatOutput.classList.remove("is-generating");
    }
    streamMessageElement = null;
    streamHtmlBuffer = "";
    streamViewAnchored = false;
    streamPreviewText = "";
    hideLoading();
  }

  function clearChatOutput() {
    destroyCharts(chatOutput);
    chatOutput.innerHTML = "";
    clearEmptyState();
    currentEntry = null;
    chatOutput.classList.remove("is-generating");
    streamMessageElement = null;
    streamHtmlBuffer = "";
    streamViewAnchored = false;
    streamPreviewText = "";
    awaitingAssistantResponse = false;
    loadingElement = null;
  }

  function renderHistory(entries) {
    clearChatOutput();

    if (!entries.length) {
      showEmptyState();
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
    // An empty chat is a centred greeting; there is nothing to follow.
    if (!autoScrollPinned || chatShell.classList.contains("is-empty")) {
      return;
    }
    requestAnimationFrame(function () {
      markProgrammaticScroll(220);
      const scrollRoot = getDocumentScrollElement();
      window.scrollTo({ top: Math.max(0, scrollRoot.scrollHeight - window.innerHeight), behavior: "auto" });
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
      chatTitle.textContent = item.dataset.title || "New Chat";
      stopRenaming();
      updateInstanceControlsState();
      closeDrawer();

      hideLoading();
      finishStream();
      loadHistory(room);
      connectSocket(room);
    });
  }

  function createInstanceElement(instance) {
    const title = (instance && instance.title) ? String(instance.title) : "New Chat";
    const el = document.createElement("button");
    el.type = "button";
    el.className = "ai-instance";
    el.dataset.room = String(instance.id);
    el.dataset.title = title;
    el.dataset.created = instance.created_at || new Date().toISOString();
    el.innerHTML = '<span class="ai-instance-title">' + escapeHtml(title) + "</span>";
    attachInstanceClick(el);
    return el;
  }

  // Today / Yesterday / Previous 7 days / Older, from each chat's date (the list is newest first).
  function groupLabel(isoDate) {
    const date = new Date(isoDate);
    if (Number.isNaN(date.getTime())) {
      return "Older";
    }
    const startOfToday = new Date();
    startOfToday.setHours(0, 0, 0, 0);
    const days = Math.floor((startOfToday - date) / 86400000) + 1;
    if (date >= startOfToday) return "Today";
    if (days <= 1) return "Yesterday";
    if (days <= 7) return "Previous 7 days";
    return "Older";
  }

  function groupInstances() {
    if (!instanceList) {
      return;
    }
    instanceList.querySelectorAll(".ai-group-label").forEach(function (label) { label.remove(); });
    let previous = null;
    instances.forEach(function (item) {
      if (item.style.display === "none") {
        return;
      }
      const label = groupLabel(item.dataset.created);
      if (label !== previous) {
        const heading = document.createElement("p");
        heading.className = "ai-group-label";
        heading.textContent = label;
        instanceList.insertBefore(heading, item);
        previous = label;
      }
    });
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

  function applyChatTitle(room, title) {
    if (!room || !title) {
      return;
    }
    instances.forEach(function (item) {
      if (item.dataset.room !== room) {
        return;
      }
      item.dataset.title = title;
      const heading = item.querySelector(".ai-instance-title");
      if (heading) {
        heading.textContent = title;
        heading.classList.remove("is-titled");
        // Restart the highlight so the new name is noticed.
        void heading.offsetWidth;
        heading.classList.add("is-titled");
      }
    });
    if (currentRoom === room) {
      chatTitle.textContent = title;
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

        // After a chat's first answer the server names the chat (ai/engine/titles.py).
        if (payload.event === "chat_title") {
          applyChatTitle(String(payload.chat_instance_id || ""), String(payload.title || ""));
          return;
        }

        // Suggested next questions for the latest answer (ai/engine/followups.py).
        if (payload.event === "followups") {
          showFollowups(String(payload.chat_instance_id || ""), payload.questions);
          return;
        }

        if (payload.is_stream) {
          if (!awaitingAssistantResponse) {
            return;
          }
          hideLoading();
          appendStreamChunk(payload.message || "", payload.preview);
          return;
        }

        if (payload.is_final) {
          awaitingAssistantResponse = false;
          finishStream(payload.message || "");
          return;
        }

        if (payload.message) {
          awaitingAssistantResponse = false;
          hideLoading();
          appendAIMessageHtml(payload.message).classList.add("is-fresh");
        }
      } catch (err) {
        hideLoading();
        appendSystemAIMessage("Received an invalid response from chat server.");
      }
    };

    ws.onerror = function () {
      awaitingAssistantResponse = false;
      if (currentRoom === room) {
        hideLoading();
        appendSystemAIMessage("Chat service error. Please try again.");
      }
    };

    ws.onclose = function () {
      awaitingAssistantResponse = false;
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

  // ---- Suggested next questions --------------------------------------------
  // Shown under the latest answer only; asking anything clears them.

  function clearFollowups() {
    chatOutput.querySelectorAll(".ai-followups").forEach(function (node) { node.remove(); });
  }

  function showFollowups(room, questions) {
    const items = (Array.isArray(questions) ? questions : [])
      .map(function (question) { return String(question || "").trim(); })
      .filter(Boolean)
      .slice(0, 3);
    if (!items.length || awaitingAssistantResponse || room !== String(chatOutput.dataset.room || "")) {
      return;
    }
    const entries = chatOutput.querySelectorAll("article.entry");
    const bubble = entries.length ? entries[entries.length - 1].querySelector(".msg.ai .msg-bubble") : null;
    if (!bubble) {
      return;
    }
    clearFollowups();
    const group = document.createElement("div");
    group.className = "ai-followups";
    group.setAttribute("role", "group");
    group.setAttribute("aria-label", "Suggested next questions");
    items.forEach(function (question, index) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "ai-followup";
      button.dataset.prompt = question;
      button.style.setProperty("--i", index);
      button.innerHTML = '<i class="ti ti-arrow-up-right" aria-hidden="true"></i><span></span>';
      button.querySelector("span").textContent = question;
      group.appendChild(button);
    });
    bubble.appendChild(group);
    scrollToBottom();
  }

  function sendMessage() {
    const value = (chatInput.value || "").trim();
    if (!value) return;
    clearFollowups();

    autoScrollPinned = true;
    setJumpButtonVisibility();
    clearEmptyState();
    appendUserMessage(value);
    chatInput.value = "";
    syncComposerInput();

    if (!socket || socket.readyState !== WebSocket.OPEN) {
      appendSystemAIMessage("Chat connection is not ready. Please wait and try again.");
      return;
    }

    showLoading();
    awaitingAssistantResponse = true;
    streamMessageElement = null;
    streamHtmlBuffer = "";
    streamPreviewText = "";
    streamViewAnchored = false;
    socket.send(JSON.stringify({ message: value }));
  }

  sendBtn.addEventListener("click", sendMessage);
  // Enter sends; Shift+Enter starts a new line. A composing IME (Amharic keyboards) keeps Enter.
  chatInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      sendMessage();
    }
  });

  function syncComposerInput() {
    chatInput.style.height = "auto";
    chatInput.style.height = Math.min(chatInput.scrollHeight, 200) + "px";
    sendBtn.disabled = !chatInput.value.trim();
    syncComposerSpace();
  }

  chatInput.addEventListener("input", syncComposerInput);

  if (chatOutput) {
    chatOutput.addEventListener("click", function (event) {
      const freqButton = event.target.closest(".ai-freq-btn");
      if (freqButton && chatOutput.contains(freqButton)) {
        setCardFrequency(freqButton.closest(".ai-data-card"), freqButton.dataset.freq);
        return;
      }

      const viewButton = event.target.closest(".ai-view-btn");
      if (viewButton && chatOutput.contains(viewButton)) {
        setCardView(viewButton.closest(".ai-data-card"), viewButton.dataset.view);
        return;
      }

      const suggestion = event.target.closest(".ai-suggestion, .ai-followup");
      if (suggestion && chatOutput.contains(suggestion)) {
        chatInput.value = suggestion.dataset.prompt || "";
        syncComposerInput();
        sendMessage();
        return;
      }

      const copyButton = event.target.closest(".ai-copy-btn");
      if (copyButton && chatOutput.contains(copyButton)) {
        const text = getReadableMessageText(copyButton.closest(".msg.ai"));
        const label = copyButton.querySelector("span");
        const icon = copyButton.querySelector("i");
        const done = function (ok) {
          if (label) label.textContent = ok ? "Copied" : "Copy failed";
          if (icon) icon.className = ok ? "ti ti-check" : "ti ti-alert-circle";
          window.setTimeout(function () {
            if (label) label.textContent = "Copy";
            if (icon) icon.className = "ti ti-copy";
          }, 1600);
        };
        if (navigator.clipboard && text) {
          navigator.clipboard.writeText(text).then(function () { done(true); }, function () { done(false); });
        } else {
          done(false);
        }
        return;
      }
    });
  }

  instances.forEach(attachInstanceClick);

  if (sidebarCollapseBtn) {
    sidebarCollapseBtn.addEventListener("click", function () {
      if (shouldAllowSidebarCollapse()) {
        setSidebarCollapsed(true);
      } else {
        closeDrawer();
      }
    });
  }

  if (sidebarExpandBtn) {
    sidebarExpandBtn.addEventListener("click", function () {
      if (shouldAllowSidebarCollapse()) {
        setSidebarCollapsed(false);
      } else {
        openDrawer();
      }
    });
  }

  if (railScrim) {
    railScrim.addEventListener("click", closeDrawer);
  }
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      closeDrawer();
    }
  });

  window.addEventListener("resize", function () {
    syncComposerSpace();
    if (!shouldAllowSidebarCollapse()) {
      if (chatShell) {
        chatShell.classList.remove("is-collapsed");
      }
      syncSidebarButtons(false);
      return;
    }
    closeDrawer();

    const collapsed = chatShell ? chatShell.classList.contains("is-collapsed") : false;
    syncSidebarButtons(collapsed);
  });

  function filterInstances() {
    const q = chatSearch ? (chatSearch.value || "").trim().toLowerCase() : "";
    let shown = 0;
    instances.forEach(function (item) {
      const match = (item.dataset.title || "").toLowerCase().includes(q);
      item.style.display = match ? "" : "none";
      shown += match ? 1 : 0;
    });
    if (chatSearchEmpty) {
      chatSearchEmpty.hidden = shown > 0 || !instances.length;
    }
    groupInstances();
  }

  if (chatSearch) {
    chatSearch.addEventListener("input", filterInstances);
  }

  restoreSidebarState();
  document.addEventListener("dashboard-theme-change", function () {
    rerenderAICharts();
  });

  if (newInstanceBtn) {
    newInstanceBtn.addEventListener("click", async function () {
      // The open chat is still empty: use it rather than piling up blank chats.
      if (getActiveInstanceElement() && !chatOutput.querySelector(".msg")) {
        closeDrawer();
        chatInput.focus({ preventScroll: true });
        return;
      }
      const result = await apiRequest("/api/ai-chat/", "POST", {});
      if (!result.ok || !result.payload || result.payload.result !== "SUCCESS") {
        const msg = result.payload && result.payload.error && result.payload.error.message
          ? result.payload.error.message
          : "Unable to create a new chat instance.";
        appendSystemAIMessage(msg);
        return;
      }
      const instance = result.payload.data;
      const el = createInstanceElement(instance);
      if (instanceList) instanceList.prepend(el);
      instances = Array.from(document.querySelectorAll(".ai-instance"));
      if (chatSearch && chatSearch.value) {
        chatSearch.value = "";
      }
      filterInstances();
      el.click();
      chatInput.focus({ preventScroll: true });
    });
  }

  function startRenaming() {
    const current = getActiveInstanceElement();
    if (!current || !chatTitleForm || !chatTitleInput) {
      return;
    }
    chatTitleInput.value = current.dataset.title || chatTitle.textContent || "";
    chatTitleForm.hidden = false;
    if (mainHead) mainHead.classList.add("is-renaming");
    chatTitleInput.focus();
    chatTitleInput.select();
  }

  function stopRenaming() {
    if (chatTitleForm) chatTitleForm.hidden = true;
    if (mainHead) mainHead.classList.remove("is-renaming");
  }

  if (renameInstanceBtn) {
    renameInstanceBtn.addEventListener("click", startRenaming);
  }
  if (chatTitleCancel) {
    chatTitleCancel.addEventListener("click", stopRenaming);
  }
  if (chatTitleInput) {
    chatTitleInput.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        event.preventDefault();
        stopRenaming();
      }
    });
  }
  if (chatTitleForm) {
    chatTitleForm.addEventListener("submit", async function (event) {
      event.preventDefault();
      const current = getActiveInstanceElement();
      const instanceId = getActiveInstanceId();
      const title = (chatTitleInput.value || "").trim();
      if (!current || !instanceId || !title || title === current.dataset.title) {
        stopRenaming();
        return;
      }
      const result = await apiRequest("/api/ai-chat/instance/" + encodeURIComponent(instanceId) + "/", "PATCH", { title: title });
      if (!result.ok || !result.payload || result.payload.result !== "SUCCESS") {
        chatTitleInput.setCustomValidity("The name could not be saved. Try again.");
        chatTitleInput.reportValidity();
        chatTitleInput.setCustomValidity("");
        return;
      }
      stopRenaming();
      current.dataset.title = title;
      const heading = current.querySelector(".ai-instance-title");
      if (heading) heading.textContent = title;
      chatTitle.textContent = title;
    });
  }

  if (deleteInstanceBtn) {
    deleteInstanceBtn.addEventListener("click", async function () {
      const current = getActiveInstanceElement();
      const instanceId = getActiveInstanceId();
      if (!current || !instanceId) {
        return;
      }
      if (!window.confirm("Delete \u201c" + (current.dataset.title || "this chat") + "\u201d? Its questions and answers are removed.")) {
        return;
      }
      const result = await apiRequest("/api/ai-chat/delete/" + encodeURIComponent(instanceId) + "/", "DELETE");
      if (!result.ok || !result.payload || result.payload.result !== "SUCCESS") {
        appendSystemAIMessage("Unable to delete this instance.");
        return;
      }
      current.remove();
      instances = Array.from(document.querySelectorAll(".ai-instance"));
      filterInstances();
      if (instances.length) {
        instances[0].click();
      } else {
        clearChatOutput();
        showEmptyState();
        chatTitle.textContent = "New Chat";
        updateInstanceControlsState();
      }
    });
  }

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    micBtn.disabled = true;
    micBtn.title = "Voice input is not supported in this browser";
  } else {
    const recognition = new SpeechRecognition();
    recognition.lang = SPEECH_LANGUAGE;
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

    micBtn.addEventListener("click", function () {
      try {
        if (isVoiceRecording) {
          recognition.stop();
          return;
        }
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
    if (Date.now() < suppressNextScrollEventsUntil) {
      setJumpButtonVisibility();
      return;
    }
    autoScrollPinned = isViewportNearBottom();
    setJumpButtonVisibility();
  }, { passive: true });

  window.addEventListener("wheel", function (event) {
    if (event.deltaY < 0) {
      autoScrollPinned = false;
      setJumpButtonVisibility();
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
      setJumpButtonVisibility();
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

  groupInstances();
  syncComposerInput();
  // Apply table enhancement to server-rendered history on first load.
  hydrateExistingAIResponses(chatOutput);
  if (!chatOutput.querySelector(".msg")) {
    showEmptyState();
  }
  updateInstanceControlsState();
  scrollToBottom();
})();
