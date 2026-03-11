(function () {
  const chatInput = document.getElementById("chatInput");
  const sendBtn = document.getElementById("sendBtn");
  const chatOutput = document.getElementById("chatOutput");
  const micBtn = document.getElementById("micBtn");
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
  let loadingElement = null;
  let chartCounter = 0;
  const sidebarStorageKey = "admas-ai-sidebar-collapsed";
  const aiAvatarSrc = "/static/assets/images/token-branded_ais.png";

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
    el.innerHTML =
      '<span class="msg-avatar" aria-hidden="true"><img class="msg-avatar-image" src="' + aiAvatarSrc + '" alt=""></span>' +
      '<div class="msg-bubble">' +
      '<div class="ai-msg-head"><i class="ti ti-sparkles"></i><span>Admas AI</span></div>' +
      '<div class="ai-msg-content">' + normalizedHtml + "</div>" +
      "</div>";
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
      '<div class="ai-loading"><span class="spinner-border" role="status" aria-hidden="true"></span><span>Generating response...</span></div>'
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
    return streamMessageElement;
  }

  function appendStreamChunk(chunkHtml) {
    const box = ensureStreamMessage();
    const content = box.querySelector(".ai-msg-content");
    if (!content) {
      return;
    }

    streamHtmlBuffer += chunkHtml || "";
    content.innerHTML = normalizeAIContent(streamHtmlBuffer);
    hydrateMessageNode(box);
    scrollToBottom();
  }

  function hydrateMessageNode(node) {
    if (!node) {
      return;
    }
    enhanceTables(node);
    renderCharts(node);
    renderActionButtons(node);
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
    streamMessageElement = null;
    streamHtmlBuffer = "";
    hideLoading();
  }

  function clearChatOutput() {
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
    requestAnimationFrame(function () {
      chatOutput.scrollTop = chatOutput.scrollHeight;
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
    const title = (instance && instance.title) ? String(instance.title) : ("Chat " + instance.id);
    const el = document.createElement("div");
    el.className = "ai-instance";
    el.dataset.room = String(instance.id);
    el.dataset.title = title;
    el.dataset.tags = "policy ministry indicator";
    el.innerHTML = "<h6>" + escapeHtml(title) + "</h6><p>Instance #" + escapeHtml(instance.id) + "</p>";
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
      const currentTitle = current.dataset.title || ("Chat " + instanceId);
      const title = (window.prompt("Rename chat instance:", currentTitle) || "").trim();
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
      if (!window.confirm("Delete this chat instance?")) {
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
        appendSystemAIMessage("No chat instances left. Use New to create one.");
        chatTitle.textContent = "Admas AI Chat";
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
    recognition.lang = "en-US";
    recognition.interimResults = false;

    recognition.onstart = function () {
      micBtn.classList.add("ai-mic-on");
    };

    recognition.onend = function () {
      micBtn.classList.remove("ai-mic-on");
    };

    recognition.onresult = function (event) {
      const spoken = event.results[0][0].transcript || "";
      chatInput.value = spoken;
      chatInput.focus();
    };

    micBtn.addEventListener("click", function () {
      try {
        recognition.start();
      } catch (e) {
        // Browser may throw if start is called while already running.
      }
    });
  }

  if (currentRoom) {
    connectSocket(currentRoom);
  }

  // Apply table enhancement to server-rendered history on first load.
  hydrateExistingAIResponses(chatOutput);
  hydrateMessageNode(chatOutput);
  updateInstanceControlsState();
  scrollToBottom();
})();
