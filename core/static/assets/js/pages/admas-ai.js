(function () {
  const chatInput = document.getElementById("chatInput");
  const sendBtn = document.getElementById("sendBtn");
  const chatOutput = document.getElementById("chatOutput");
  const chatTitle = document.getElementById("chatTitle");
  const csrfToken = document.getElementById("csrfTokenValue");
  const instanceList = document.getElementById("instanceList");
  const newInstanceBtn = document.getElementById("newInstanceBtn");
  const renameInstanceBtn = document.getElementById("renameInstanceBtn");
  const deleteInstanceBtn = document.getElementById("deleteInstanceBtn");
  const chatSearch = document.getElementById("chatSearch");
  const sidebarCollapseBtn = document.getElementById("sidebarCollapseBtn");
  const sidebarExpandBtn = document.getElementById("sidebarExpandBtn");
  const chatShell = document.getElementById("aiChatShell");

  if (!chatInput || !sendBtn || !chatOutput || !chatTitle || !instanceList) {
    return;
  }

  let socket = null;
  let activeRoom = chatOutput.dataset.room || "";
  let pendingBubble = null;
  let sending = false;
  let socketReadyPromise = null;

  function getCsrfToken() {
    return csrfToken ? csrfToken.value : "";
  }

  function setSending(next) {
    sending = next;
    sendBtn.disabled = next;
    chatInput.disabled = next;
    chatOutput.classList.toggle("is-generating", next);
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function scrollToBottom() {
    chatOutput.scrollTop = chatOutput.scrollHeight;
  }

  function syncInstanceTitle(room, title) {
    if (!title) {
      return;
    }
    const selector = '.ai-instance[data-room="' + CSS.escape(String(room)) + '"]';
    const activeNode = instanceList.querySelector(selector);
    if (activeNode) {
      activeNode.dataset.title = title;
      const label = activeNode.querySelector("h6");
      if (label) {
        label.textContent = title;
      }
    }
    if (String(activeRoom) === String(room)) {
      chatTitle.textContent = title;
    }
  }

  function userMessageMarkup(text) {
    return (
      '<div class="msg user">' +
      '<span class="msg-avatar" aria-hidden="true"><i class="ti ti-user-circle"></i></span>' +
      '<div class="msg-bubble">' + escapeHtml(text) + "</div>" +
      "</div>"
    );
  }

  function aiMessageMarkup(text) {
    return (
      '<div class="msg ai">' +
      '<span class="msg-avatar" aria-hidden="true"><img class="msg-avatar-image" src="/static/assets/images/token-branded_ais.png" alt=""></span>' +
      '<div class="msg-bubble">' +
      '<div class="ai-msg-head">' +
      '<span class="ai-msg-brand"><i class="ti ti-sparkles"></i><span>Admas AI</span></span>' +
      '<div class="ai-msg-head-tools" hidden></div>' +
      "</div>" +
      '<div class="ai-msg-meta" hidden></div>' +
      '<div class="ai-msg-content">' + text + "</div>" +
      '<div class="ai-msg-charts"></div>' +
      '<div class="ai-msg-artifacts" hidden></div>' +
      '<div class="ai-msg-actions" hidden></div>' +
      '<div class="ai-msg-status" hidden>' +
      '<span class="ai-msg-status-text">Thinking</span>' +
      '<span class="ai-msg-status-dots" aria-hidden="true">' +
      '<span></span><span></span><span></span>' +
      "</span>" +
      "</div>" +
      "</div>" +
      "</div>"
    );
  }

  function ensureSocket() {
    if (!activeRoom) {
      return Promise.reject(new Error("No active chat room."));
    }
    if (socket && socket.readyState <= 1) {
      if (socket.readyState === WebSocket.OPEN) {
        return Promise.resolve(socket);
      }
      return socketReadyPromise || Promise.resolve(socket);
    }
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(protocol + "://" + window.location.host + "/ws/chat/" + encodeURIComponent(activeRoom) + "/");
    socketReadyPromise = new Promise(function (resolve, reject) {
      socket.addEventListener("open", function handleOpen() {
        resolve(socket);
      }, { once: true });
      socket.addEventListener("error", function handleError() {
        reject(new Error("Unable to open the chat connection."));
      }, { once: true });
    });

    socket.onmessage = function (event) {
      const payload = JSON.parse(event.data || "{}");
      if (payload.error) {
        setPendingBubbleContent("<p>" + escapeHtml(payload.error.message || "Unable to generate a response.") + "</p>");
        setSending(false);
        return;
      }

      if (!pendingBubble) {
        pendingBubble = appendAiBubble("");
      }

      if (payload.is_stream) {
        setBubbleLoading(pendingBubble, true);
        appendPendingChunk(payload.message || "");
      } else if (payload.is_final) {
        setPendingBubbleContent(payload.message || "");
        applyBubbleState(pendingBubble, payload);
        setBubbleLoading(pendingBubble, false);
        if (payload.chat_title) {
          syncInstanceTitle(activeRoom, payload.chat_title);
        }
        pendingBubble = null;
        setSending(false);
      }
    };

    socket.onclose = function () {
      socket = null;
      socketReadyPromise = null;
      if (sending) {
        setPendingBubbleContent("<p>Connection closed before the answer finished.</p>");
        setBubbleLoading(pendingBubble, false);
        pendingBubble = null;
        setSending(false);
      }
    };
    return socketReadyPromise;
  }

  function appendHtml(markup) {
    const wrapper = document.createElement("div");
    wrapper.innerHTML = markup;
    const node = wrapper.firstElementChild;
    if (node) {
      chatOutput.appendChild(node);
      scrollToBottom();
      return node;
    }
    return null;
  }

  function appendAiBubble(initialHtml) {
    const bubble = appendHtml(aiMessageMarkup(initialHtml));
    if (bubble) {
      bubble.classList.add("ai-bubble-enter");
      requestAnimationFrame(function () {
        bubble.classList.add("is-visible");
      });
    }
    return bubble;
  }

  function appendPendingChunk(chunk) {
    if (!pendingBubble) {
      pendingBubble = appendAiBubble("");
    }
    const content = pendingBubble.querySelector(".ai-msg-content");
    content.innerHTML += escapeHtml(chunk);
    scrollToBottom();
  }

  function setPendingBubbleContent(html) {
    if (!pendingBubble) {
      pendingBubble = appendAiBubble("");
    }
    const content = pendingBubble.querySelector(".ai-msg-content");
    content.innerHTML = html;
    scrollToBottom();
  }

  function prettyIntent(intent) {
    return String(intent || "").replace(/_/g, " ").replace(/\b\w/g, function (char) {
      return char.toUpperCase();
    });
  }

  function safeObject(value) {
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  }

  function safeArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function safeString(value) {
    return typeof value === "string" ? value : (value === null || value === undefined ? "" : String(value));
  }

  function safeResponseType(value) {
    const allowed = ["scorecard", "time_series", "text", "table", "not_found", "dashboard_link"];
    const normalized = safeString(value).trim().toLowerCase();
    return allowed.indexOf(normalized) >= 0 ? normalized : "text";
  }

  function normalizePolicyAreas(value) {
    return safeArray(value).map(function (item) {
      const safeItem = safeObject(item);
      return {
        policy_area_eng: safeString(safeItem.policy_area_eng || safeItem.policy_area || safeItem.title),
        score: safeString(safeItem.score),
        score_color: safeString(safeItem.score_color)
      };
    }).filter(function (item) {
      return item.policy_area_eng || item.score;
    });
  }

  function normalizePrimaryData(value, responseType) {
    const safePrimary = safeObject(value);
    const period = safeObject(safePrimary.period);
    const table = safeObject(safePrimary.table);
    return {
      title: safeString(safePrimary.title || safePrimary.name || safePrimary.entity_name),
      text: safeString(safePrimary.text || safePrimary.description),
      overall_score: safeString(safePrimary.overall_score || safePrimary.score),
      score_color: safeString(safePrimary.score_color),
      period: {
        year: period.year || safePrimary.year || "",
        quarter: safeString(period.quarter || safePrimary.quarter)
      },
      policy_areas: normalizePolicyAreas(safePrimary.policy_areas),
      charts: responseType === "time_series" ? safeArray(safePrimary.charts) : [],
      series: safeArray(safePrimary.series),
      table: {
        columns: safeArray(table.columns),
        rows: safeArray(table.rows).filter(function (row) {
          return Array.isArray(row);
        })
      }
    };
  }

  function normalizeSeries(value) {
    return safeArray(value).map(function (item) {
      const safeItem = safeObject(item);
      const labels = safeArray(safeItem.labels);
      const values = safeArray(safeItem.values);
      return {
        label: safeString(safeItem.label || safeItem.title || "Trend"),
        type: safeString(safeItem.type || "line") || "line",
        labels: labels,
        values: values.map(function (entry) {
          return typeof entry === "number" ? entry : Number(entry);
        }).filter(function (entry) {
          return !Number.isNaN(entry);
        })
      };
    }).filter(function (item) {
      return item.labels.length && item.values.length && item.labels.length === item.values.length;
    });
  }

  function seriesFromCharts(value) {
    return safeArray(value).map(function (chart) {
      const normalized = normalizeChart(chart);
      if (!normalized) {
        return null;
      }
      return {
        label: normalized.label,
        type: normalized.type,
        labels: normalized.labels,
        values: normalized.data
      };
    }).filter(Boolean);
  }

  function hasStructuredSeries(state) {
    const safeState = safeObject(state);
    return normalizeSeries(safeObject(safeState.primaryData).series).length > 0;
  }

  function canRenderChart(state) {
    const safeState = safeObject(state);
    const responseType = safeResponseType(safeState.responseType);
    if (responseType === "scorecard" || responseType === "not_found") {
      return false;
    }
    return hasStructuredSeries(safeState);
  }

  function canRenderTable(state) {
    const safeState = safeObject(state);
    const responseType = safeResponseType(safeState.responseType);
    const primaryData = normalizePrimaryData(safeState.primaryData, responseType);
    const explicitTable = safeArray(safeObject(primaryData.table).columns).length && safeArray(safeObject(primaryData.table).rows).length;
    const convertibleSeries = normalizeSeries(primaryData.series).length > 0;
    if (responseType === "scorecard" || responseType === "not_found") {
      return false;
    }
    if (responseType === "table") {
      return Boolean(explicitTable || convertibleSeries);
    }
    if (responseType === "time_series") {
      return Boolean(explicitTable || convertibleSeries);
    }
    return Boolean(explicitTable || convertibleSeries);
  }

  function derivedTableFromPrimary(primaryData) {
    const safePrimary = normalizePrimaryData(primaryData, "table");
    if (safePrimary.table.columns.length && safePrimary.table.rows.length) {
      const title = safeString(safePrimary.title).trim();
      const rows = safePrimary.table.rows.filter(function (row) {
        if (!Array.isArray(row) || !row.length) {
          return false;
        }
        if (row.length === 1 && title && safeString(row[0]).trim() === title) {
          return false;
        }
        return true;
      });
      return {
        columns: safePrimary.table.columns,
        rows: rows
      };
    }
    const series = normalizeSeries(safePrimary.series);
    if (!series.length) {
      return { columns: [], rows: [] };
    }
    const first = series[0];
    return {
      columns: ["Period", first.label || "Value"],
      rows: first.labels.map(function (label, index) {
        return [label, first.values[index]];
      })
    };
  }

  function normalizeSupportingContext(value) {
    const safeContext = safeObject(value);
    const publicBody = safeObject(safeContext.responsible_public_body);
    if (!Object.keys(publicBody).length) {
      return {};
    }
    return {
      responsible_public_body: {
        name: safeString(publicBody.name),
        code: safeString(publicBody.code)
      }
    };
  }

  function normalizeSources(value) {
    return safeArray(value).map(function (item) {
      const source = safeObject(item);
      return {
        indicator: safeString(source.indicator),
        indicator_code: safeString(source.indicator_code),
        topic: safeString(source.topic),
        ministry: safeString(source.ministry),
        year: safeString(source.year),
        quarter: safeString(source.quarter),
        public_body_score: safeObject(source.public_body_score)
      };
    }).filter(function (item) {
      return item.indicator || item.indicator_code || item.topic || item.ministry || Object.keys(item.public_body_score).length;
    });
  }

  function hasRenderableScorecardData(primaryData) {
    const safePrimary = safeObject(primaryData);
    const period = safeObject(safePrimary.period);
    const policyAreas = normalizePolicyAreas(safePrimary.policy_areas);
    return Boolean(
      safeString(safePrimary.overall_score).trim() &&
      policyAreas.length &&
      (period.year || safeString(period.quarter).trim()) &&
      safeString(safePrimary.title).trim() &&
      safeString(safePrimary.text).trim()
    );
  }

  function normalizeBubbleState(payload) {
    const safePayload = safeObject(payload);
    const toolData = safeObject(safePayload.tool_data);
    const lastResult = safeObject(toolData.last_tool_result);
    const payloadData = safeObject(toolData.payload);
    const responseData = safeObject(safePayload.response_data || safePayload.responseData || toolData.response_payload);
    const explicitSources = normalizeSources(safePayload.sources);
    const fallbackSources = normalizeSources(lastResult.sources);
    const responseType = safeResponseType(safePayload.response_type || safePayload.responseType || responseData.response_type || toolData.response_type);
    const legacyPrimaryData = Object.keys(responseData).length
      ? responseData.primary_data
      : (safePayload.primaryData || toolData.primary_data);
    const legacySupportingContext = Object.keys(responseData).length
      ? responseData.supporting_context
      : (safePayload.supportingContext || toolData.supporting_context);
    const payloadTitle = safeString(responseData.title || safePayload.title);
    const payloadSummary = safeString(responseData.summary || safePayload.summary);
    const payloadDataObject = safeObject(responseData.data);
    const rawCharts = safeArray(safePayload.charts).length ? safeArray(safePayload.charts) : safeArray(lastResult.charts);
    const mergedPrimaryData = Object.keys(payloadDataObject).length
      ? Object.assign({}, payloadDataObject, { title: payloadTitle, text: payloadSummary || safeString(payloadDataObject.text || payloadDataObject.description) })
      : Object.assign({}, safeObject(legacyPrimaryData), { title: safeString(safeObject(legacyPrimaryData).title || payloadTitle), text: safeString(safeObject(legacyPrimaryData).text || payloadSummary) });
    const primaryData = normalizePrimaryData(mergedPrimaryData, responseType);
    if (!normalizeSeries(primaryData.series).length && rawCharts.length) {
      primaryData.series = seriesFromCharts(rawCharts);
    } else {
      primaryData.series = normalizeSeries(primaryData.series);
    }
    if ((!primaryData.table.columns.length || !primaryData.table.rows.length) && primaryData.series.length) {
      primaryData.table = derivedTableFromPrimary(primaryData);
    }
    const supportingContext = normalizeSupportingContext(
      payloadDataObject.supporting_context || legacySupportingContext
    );

    return {
      intent: safeString(safePayload.intent || toolData.intent),
      secondaryIntents: safeArray(safePayload.secondary_intents).length
        ? safeArray(safePayload.secondary_intents)
        : (safeArray(safePayload.secondaryIntents).length ? safeArray(safePayload.secondaryIntents) : safeArray(toolData.secondary_intents)),
      language: safeString(safePayload.language || toolData.language),
      usage: safeObject(safePayload.usage || lastResult.usage),
      contextFound: typeof safePayload.context_found === "boolean"
        ? safePayload.context_found
        : (typeof safePayload.contextFound === "boolean" ? safePayload.contextFound : Boolean(lastResult.context_found)),
      responseType: responseType,
      title: payloadTitle || primaryData.title,
      summary: payloadSummary || primaryData.text,
      primaryData: primaryData,
      supportingContext: supportingContext,
      sources: explicitSources.length ? explicitSources : fallbackSources,
      charts: rawCharts,
      dashboard: payloadData.share_url ? payloadData : (safeObject(safePayload.dashboard).share_url ? safeObject(safePayload.dashboard) : (lastResult.share_url ? lastResult : {})),
      toolData: toolData
    };
  }

  function sourceDomain(source) {
    const safeSource = safeObject(source);
    if (Object.keys(safeObject(safeSource.public_body_score)).length) {
      return "DPMES";
    }
    if (safeSource.indicator || safeSource.indicator_code) {
      return "TSMS";
    }
    return "Other";
  }

  function sourceSnippet(source) {
    return [
      source.topic,
      source.ministry,
      source.indicator_code,
      source.year,
      source.quarter
    ].filter(Boolean).join(" • ");
  }

  function renderSourcesPopover(sources) {
    const grouped = {};
    sources.forEach(function (source) {
      const domain = sourceDomain(source);
      if (!grouped[domain]) {
        grouped[domain] = [];
      }
      grouped[domain].push(source);
    });
    const sections = ["DPMES", "TSMS", "Other"].map(function (domain) {
      const items = (grouped[domain] || []).slice(0, 5);
      if (!items.length) {
        return "";
      }
      return (
        '<section class="ai-sources-section">' +
        '<div class="ai-sources-section-title">' + escapeHtml(domain) + "</div>" +
        '<div class="ai-sources-list">' +
        items.map(function (source) {
          const title = source.indicator || source.topic || source.indicator_code || source.ministry || "Source";
          const snippet = sourceSnippet(source);
          return (
            '<div class="ai-source-row">' +
            '<strong title="' + escapeHtml(title) + '">' + escapeHtml(title) + "</strong>" +
            (snippet ? '<span title="' + escapeHtml(snippet) + '">' + escapeHtml(snippet) + "</span>" : "") +
            "</div>"
          );
        }).join("") +
        "</div>" +
        "</section>"
      );
    }).join("");

    return (
      '<details class="ai-sources-popover">' +
      '<summary class="ai-icon-btn" title="View sources" aria-label="View sources"><i class="ti ti-file-info"></i></summary>' +
      '<div class="ai-sources-popover-card">' + sections + "</div>" +
      "</details>"
    );
  }

  function renderBubbleHeadTools(bubble, state) {
    const safeState = normalizeBubbleState(state);
    const tools = bubble.querySelector(".ai-msg-head-tools");
    if (!tools) {
      return;
    }
    const items = [];
    if (safeState.sources.length) {
      items.push(renderSourcesPopover(safeState.sources));
    }
    tools.innerHTML = items.join("");
    tools.hidden = !items.length;
  }

  function renderScorecardBlock(primaryData) {
    const safePrimary = safeObject(primaryData);
    const title = safeString(safePrimary.title) || "Scorecard";
    const overallScore = safeString(safePrimary.overall_score) || "--";
    const overallColor = safeString(safePrimary.score_color) || "#0f766e";
    const period = safeObject(safePrimary.period);
    const periodLabel = [period.year, period.quarter].filter(Boolean).join(" ");
    const descriptionHtml = safeString(safePrimary.text);
    const policyAreaItems = safeArray(safePrimary.policy_areas).slice(0, 8);

    return (
      '<section class="ai-scorecard-panel" style="--ai-scorecard-accent:' + escapeHtml(overallColor) + ';">' +
      '<div class="ai-scorecard-hero">' +
      '<div class="ai-scorecard-copy">' +
        '<span class="ai-scorecard-kicker">Public Body Scorecard</span>' +
        '<h4>' + escapeHtml(title) + "</h4>" +
        '<div class="ai-scorecard-meta">' +
      (periodLabel ? '<span>' + escapeHtml(periodLabel) + "</span>" : "") +
        "</div>" +
      "</div>" +
      '<div class="ai-scorecard-total">' +
        '<span>Overall score</span>' +
        '<strong>' + escapeHtml(overallScore) + "</strong>" +
      "</div>" +
      "</div>" +
      (
        descriptionHtml
          ? '<div class="ai-scorecard-summary"><span class="ai-scorecard-section-label">Short description</span><div class="ai-scorecard-summary-copy">' + descriptionHtml + "</div></div>"
          : ""
      ) +
      '<div class="ai-scorecard-policy-grid">' +
      policyAreaItems.map(function (item) {
        const title = item.policy_area_eng || "Policy area";
        const score = item.score || "--";
        const color = item.score_color || overallColor;
        return (
          '<article class="ai-scorecard-policy" style="--ai-policy-accent:' + escapeHtml(color) + ';">' +
          '<div class="ai-scorecard-policy-head">' +
          '<strong>' + escapeHtml(score) + "</strong>" +
          '<span class="ai-scorecard-policy-dot"></span>' +
          "</div>" +
          '<span class="ai-scorecard-section-label">Policy area</span>' +
          '<p>' + escapeHtml(title) + "</p>" +
          "</article>"
        );
      }).join("") +
      "</div>" +
      "</section>"
    );
  }

  function renderTableBlock(primaryData) {
    const table = derivedTableFromPrimary(primaryData);
    const title = safeString(safeObject(primaryData).title) || "Data table";
    const columns = safeArray(table.columns).slice(0, 6);
    const rows = safeArray(table.rows).slice(0, 8);
    if (!columns.length || !rows.length) {
      return "";
    }
    return (
      '<section class="ai-artifact-card ai-artifact-card-table">' +
      '<div class="ai-artifact-copy">' +
      '<span class="ai-artifact-kicker">Table</span>' +
      '<strong>' + escapeHtml(title) + "</strong>" +
      "</div>" +
      '<div class="ai-table-wrap"><table class="ai-response-table"><thead><tr>' +
      columns.map(function (column) {
        return "<th>" + escapeHtml(column) + "</th>";
      }).join("") +
      "</tr></thead><tbody>" +
      rows.map(function (row) {
        return "<tr>" + row.slice(0, columns.length).map(function (cell) {
          return "<td>" + escapeHtml(cell) + "</td>";
        }).join("") + "</tr>";
      }).join("") +
      "</tbody></table></div>" +
      "</section>"
    );
  }

  function shouldRenderScorecard(state) {
    const safeState = safeObject(state);
    if (safeResponseType(safeState.responseType) !== "scorecard") {
      return false;
    }
    const primaryData = normalizePrimaryData(safeState.primaryData, "scorecard");
    if (!hasRenderableScorecardData(primaryData)) {
      return false;
    }
    const text = safeString(primaryData.text).toLowerCase();
    const narrativeTrendTerms = ["trend", "export", "inflation", "indicator", "rate", "earnings", "over time"];
    const safeTrendTerms = Array.isArray(narrativeTrendTerms)
      ? narrativeTrendTerms
      : (typeof narrativeTrendTerms === "string" && narrativeTrendTerms.trim() ? [narrativeTrendTerms] : []);
    return !safeTrendTerms.some(function (term) {
      return text.includes(safeString(term).toLowerCase());
    });
  }

  function buildFollowUpPrompts(state) {
    const prompts = [];
    if (shouldRenderScorecard(state)) {
      prompts.push("Explain the policy area performance");
      prompts.push("Which policy area performed best?");
    } else if (state.responseType === "table") {
      prompts.push("Explain this data");
      prompts.push("Show the trend chart");
    } else if (state.intent === "time_series_query") {
      prompts.push("Explain this trend");
      prompts.push("Show the data in table format");
    } else {
      prompts.push("Give me more detail");
    }
    if (state.sources.length) {
      prompts.push("Summarize the trusted sources");
    }
    return prompts.slice(0, 3);
  }

  function buildActionConfig(state) {
    const actions = [
      { kind: "copy", icon: "ti ti-copy", label: "Copy response", title: "Copy response", primary: true }
    ];
    if (canRenderChart(state)) {
      actions.push({ kind: "toggle-view", icon: "ti ti-chart-line", label: "Chart", title: "Chart", viewMode: "chart", primary: true });
    }
    if (canRenderTable(state)) {
      actions.push({ kind: "toggle-view", icon: "ti ti-table", label: "Table", title: "Table", viewMode: "table", primary: true });
    }
    if (state.intent === "time_series_query") {
      actions.push({ kind: "follow", icon: "ti ti-bulb", label: "Explain trend", title: "Explain trend", prompt: "Explain this trend", primary: false });
    }
    if (state.sources.length) {
      actions.push({ kind: "follow", icon: "ti ti-receipt-2", label: "Summarize sources", title: "Summarize sources", prompt: "Summarize the trusted sources", primary: false });
    }
    return actions;
  }

  function renderIconAction(action) {
    if (action.kind === "copy") {
      return '<button type="button" class="ai-icon-btn ai-response-action" data-ai-action="copy" title="' + escapeHtml(action.title) + '" aria-label="' + escapeHtml(action.label) + '"><i class="' + escapeHtml(action.icon) + '"></i></button>';
    }
    if (action.kind === "toggle-view") {
      return '<button type="button" class="ai-icon-btn ai-response-action" data-ai-action="toggle-view" data-view-mode="' + escapeHtml(action.viewMode) + '" title="' + escapeHtml(action.title) + '" aria-label="' + escapeHtml(action.label) + '"><i class="' + escapeHtml(action.icon) + '"></i></button>';
    }
    return '<button type="button" class="ai-icon-btn ai-response-action" data-ai-action="follow" data-prompt="' + escapeHtml(action.prompt) + '" title="' + escapeHtml(action.title) + '" aria-label="' + escapeHtml(action.label) + '"><i class="' + escapeHtml(action.icon) + '"></i></button>';
  }

  function renderBubbleMeta(bubble, state) {
    const safeState = normalizeBubbleState(state);
    const meta = bubble.querySelector(".ai-msg-meta");
    if (!meta) {
      return;
    }
    if (shouldRenderScorecard(safeState)) {
      meta.innerHTML = "";
      meta.hidden = true;
      return;
    }
    const chips = [];
    if (safeState.intent) {
      chips.push('<span class="ai-meta-chip ai-meta-chip-intent">' + escapeHtml(prettyIntent(safeState.intent)) + "</span>");
    }
    if (safeState.language) {
      chips.push('<span class="ai-meta-chip">' + escapeHtml(safeState.language) + "</span>");
    }
    if (safeState.contextFound) {
      chips.push('<span class="ai-meta-chip ai-meta-chip-grounded"><i class="ti ti-shield-check"></i><span>Grounded</span></span>');
    }
    meta.innerHTML = chips.join("");
    meta.hidden = !chips.length;
  }

  function renderBubbleArtifacts(bubble, state) {
    const safeState = normalizeBubbleState(state);
    const artifacts = bubble.querySelector(".ai-msg-artifacts");
    if (!artifacts) {
      return;
    }
    const blocks = [];
    if (shouldRenderScorecard(safeState)) {
      blocks.push(renderScorecardBlock(safeState.primaryData));
      artifacts.innerHTML = blocks.join("");
      artifacts.hidden = false;
      return;
    }
    artifacts.innerHTML = blocks.join("");
    artifacts.hidden = !blocks.length;
  }

  function renderBubbleActions(bubble, state) {
    const safeState = normalizeBubbleState(state);
    const actions = bubble.querySelector(".ai-msg-actions");
    if (!actions) {
      return;
    }
    if (shouldRenderScorecard(safeState)) {
      actions.innerHTML = "";
      actions.hidden = true;
      return;
    }
    const config = buildActionConfig(safeState);
    const viewMode = bubble.dataset.viewMode || "none";
    const primaryItems = config.filter(function (item) { return item.primary; }).slice(0, 3);
    const secondaryItems = config.filter(function (item) { return !item.primary; });
    const items = primaryItems.map(function (item) {
      const markup = renderIconAction(item);
      if (item.kind !== "toggle-view") {
        return markup;
      }
      const activeClass = item.viewMode === viewMode ? " is-active" : "";
      return markup.replace('class="ai-icon-btn ai-response-action"', 'class="ai-icon-btn ai-response-action' + activeClass + '"');
    });
    if (secondaryItems.length) {
      items.push(
        '<details class="ai-action-menu">' +
        '<summary class="ai-icon-btn ai-response-action" title="More actions" aria-label="More actions"><i class="ti ti-dots"></i></summary>' +
        '<div class="ai-action-menu-list">' +
        secondaryItems.map(function (item) {
          return '<button type="button" class="ai-action-menu-item" data-ai-action="follow" data-prompt="' + escapeHtml(item.prompt) + '">' +
            '<i class="' + escapeHtml(item.icon) + '"></i><span>' + escapeHtml(item.label) + "</span></button>";
        }).join("") +
        "</div>" +
        "</details>"
      );
    }
    actions.innerHTML = items.join("");
    actions.hidden = !items.length;
  }

  function applyBubbleState(bubble, payload) {
    if (!bubble) {
      return;
    }
    const state = normalizeBubbleState(payload || {});
    bubble.__aiState = state;
    if (!bubble.dataset.viewMode) {
      bubble.dataset.viewMode = "none";
    }
    const content = bubble.querySelector(".ai-msg-content");
    const charts = bubble.querySelector(".ai-msg-charts");
    renderBubbleHeadTools(bubble, state);
    renderBubbleMeta(bubble, state);
    renderBubbleArtifacts(bubble, state);
    renderBubbleActions(bubble, state);
    if (content) {
      content.hidden = shouldRenderScorecard(state);
    }
    renderBubbleDataView(bubble, state);
  }

  function setBubbleLoading(bubble, isLoading) {
    if (!bubble) {
      return;
    }
    const status = bubble.querySelector(".ai-msg-status");
    const content = bubble.querySelector(".ai-msg-content");
    if (!status) {
      return;
    }
    status.hidden = !isLoading;
    bubble.classList.toggle("is-streaming", isLoading);
    if (content) {
      content.classList.toggle("ai-msg-content-streaming", isLoading);
    }
  }

  function renderBubbleCharts(bubble, charts) {
    if (!bubble) {
      return;
    }
    const chartHost = bubble.querySelector(".ai-msg-charts");
    if (!chartHost) {
      return;
    }
    chartHost.innerHTML = "";
    (charts || []).forEach(function (chart, index) {
      const config = normalizeChart(chart);
      if (!config) {
        return;
      }
      const card = document.createElement("div");
      card.className = "ai-chart-card";
      const title = document.createElement("div");
      title.className = "ai-chart-title";
      title.textContent = config.label;
      const mount = document.createElement("div");
      mount.className = "ai-chart-canvas";
      mount.id = "ai-chart-" + Date.now() + "-" + index;
      card.appendChild(title);
      card.appendChild(mount);
      chartHost.appendChild(card);
      renderSimpleLineChart(mount, config);
    });
    scrollToBottom();
  }

  function renderBubbleDataView(bubble, state) {
    if (!bubble) {
      return;
    }
    const safeState = normalizeBubbleState(state);
    const chartHost = bubble.querySelector(".ai-msg-charts");
    const artifacts = bubble.querySelector(".ai-msg-artifacts");
    if (!chartHost) {
      return;
    }
    if (shouldRenderScorecard(safeState)) {
      chartHost.innerHTML = "";
      chartHost.hidden = true;
      return;
    }
    const viewMode = bubble.dataset.viewMode || "none";
    if (viewMode === "none") {
      chartHost.innerHTML = "";
      chartHost.hidden = true;
      return;
    }
    if (viewMode === "table") {
      if (!canRenderTable(safeState)) {
        chartHost.innerHTML = "";
        chartHost.hidden = true;
        return;
      }
      chartHost.innerHTML = renderTableBlock(safeState.primaryData);
      chartHost.hidden = false;
      if (artifacts) {
        artifacts.innerHTML = "";
        artifacts.hidden = true;
      }
      return;
    }
    if (!canRenderChart(safeState)) {
      chartHost.innerHTML = "";
      chartHost.hidden = true;
      return;
    }
    const firstSeries = normalizeSeries(safeState.primaryData.series)[0];
    if (!firstSeries) {
      chartHost.innerHTML = "";
      chartHost.hidden = true;
      return;
    }
    renderBubbleCharts(bubble, [
      {
        type: firstSeries.type || "line",
        label: firstSeries.label,
        labels: firstSeries.labels,
        data: firstSeries.values
      }
    ]);
    chartHost.hidden = false;
    if (artifacts) {
      artifacts.innerHTML = "";
      artifacts.hidden = true;
    }
  }

  function normalizeChart(chart) {
    if (!chart || !Array.isArray(chart.labels) || !Array.isArray(chart.data) || !chart.labels.length || !chart.data.length) {
      return null;
    }
    const cleanData = chart.data.map(function (value) {
      return typeof value === "number" ? value : Number(value);
    }).filter(function (value) {
      return !Number.isNaN(value);
    });
    if (!cleanData.length || cleanData.length !== chart.labels.length) {
      return null;
    }
    return {
      type: chart.type || "line",
      label: chart.label || "Trend",
      labels: chart.labels,
      data: cleanData
    };
  }

  function getChartTheme() {
    const body = document.body;
    const styles = window.getComputedStyle(body);
    const modeHint = String(body.getAttribute("data-pc-theme") || "").toLowerCase();
    const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    const isDark = modeHint === "dark" || (!modeHint && prefersDark);
    const primaryColor =
      styles.getPropertyValue("--bs-primary").trim() ||
      styles.getPropertyValue("--pc-primary").trim() ||
      styles.getPropertyValue("--pc-sidebar-active-color").trim();

    if (isDark) {
      return {
        mode: "dark",
        lineColor: primaryColor || "#7cc7ff",
        foreColor: "#d7e0e8",
        axisColor: "#9fb0bf",
        gridColor: "rgba(159,176,191,0.18)"
      };
    }

    return {
      mode: "light",
      lineColor: primaryColor || "#1d4ed8",
      foreColor: "#445564",
      axisColor: "#708090",
      gridColor: "rgba(68,85,100,0.12)"
    };
  }

  function renderSimpleLineChart(container, config) {
    const theme = getChartTheme();
    const width = 720;
    const height = 260;
    const padding = { top: 16, right: 18, bottom: 42, left: 54 };
    const plotWidth = width - padding.left - padding.right;
    const plotHeight = height - padding.top - padding.bottom;
    const values = config.data.slice();
    const minValue = Math.min.apply(null, values);
    const maxValue = Math.max.apply(null, values);
    const range = maxValue - minValue || 1;
    const xStep = values.length > 1 ? plotWidth / (values.length - 1) : 0;

    const points = values.map(function (value, index) {
      const x = padding.left + xStep * index;
      const normalized = (value - minValue) / range;
      const y = padding.top + plotHeight - normalized * plotHeight;
      return { x: x, y: y, value: value, label: config.labels[index] };
    });

    const pathData = points.map(function (point, index) {
      return (index === 0 ? "M" : "L") + point.x.toFixed(2) + " " + point.y.toFixed(2);
    }).join(" ");

    const gridLines = buildGridLines(minValue, maxValue, padding, plotWidth, plotHeight);
    const xLabels = points.map(function (point, index) {
      return '<text x="' + point.x.toFixed(2) + '" y="' + (height - 12) + '" text-anchor="middle" fill="' + theme.axisColor + '" font-size="11">' +
        escapeHtml(shortLabel(point.label, index, points.length)) +
        "</text>";
    }).join("");

    const yLabels = gridLines.map(function (line) {
      return '<text x="' + (padding.left - 10) + '" y="' + (line.y + 4).toFixed(2) + '" text-anchor="end" fill="' + theme.axisColor + '" font-size="11">' +
        escapeHtml(formatChartNumber(line.value)) +
        "</text>";
    }).join("");

    const gridMarkup = gridLines.map(function (line) {
      return '<line x1="' + padding.left + '" y1="' + line.y.toFixed(2) + '" x2="' + (padding.left + plotWidth) + '" y2="' + line.y.toFixed(2) + '" stroke="' + theme.gridColor + '" stroke-width="1"/>';
    }).join("");

    const pointMarkup = points.map(function (point, index) {
      return '<circle class="ai-chart-point" data-index="' + index + '" cx="' + point.x.toFixed(2) + '" cy="' + point.y.toFixed(2) + '" r="4" fill="' + theme.lineColor + '"></circle>';
    }).join("");

    container.innerHTML =
      '<div class="ai-chart-tooltip" hidden></div>' +
      '<svg viewBox="0 0 ' + width + " " + height + '" class="ai-chart-svg" role="img" aria-label="' + escapeHtml(config.label) + '">' +
      '<line x1="' + padding.left + '" y1="' + padding.top + '" x2="' + padding.left + '" y2="' + (padding.top + plotHeight) + '" stroke="' + theme.gridColor + '" stroke-width="1.2"/>' +
      '<line x1="' + padding.left + '" y1="' + (padding.top + plotHeight) + '" x2="' + (padding.left + plotWidth) + '" y2="' + (padding.top + plotHeight) + '" stroke="' + theme.gridColor + '" stroke-width="1.2"/>' +
      gridMarkup +
      '<path class="ai-chart-line-hit" d="' + pathData + '" fill="none" stroke="transparent" stroke-width="18" stroke-linejoin="round" stroke-linecap="round"/>' +
      '<path d="' + pathData + '" fill="none" stroke="' + theme.lineColor + '" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>' +
      pointMarkup +
      xLabels +
      yLabels +
      "</svg>";

    bindChartTooltip(container, points);
  }

  function bindChartTooltip(container, points) {
    const svg = container.querySelector(".ai-chart-svg");
    const tooltip = container.querySelector(".ai-chart-tooltip");
    const hitLine = container.querySelector(".ai-chart-line-hit");
    const pointNodes = container.querySelectorAll(".ai-chart-point");
    if (!svg || !tooltip || !hitLine || !points.length) {
      return;
    }

    function showTooltip(index, clientX, clientY) {
      const point = points[index];
      if (!point) {
        return;
      }
      tooltip.hidden = false;
      tooltip.textContent = point.label + ": " + formatChartNumber(point.value);
      const rect = container.getBoundingClientRect();
      tooltip.style.left = (clientX - rect.left + 12) + "px";
      tooltip.style.top = (clientY - rect.top - 12) + "px";
    }

    function hideTooltip() {
      tooltip.hidden = true;
    }

    function nearestPointIndex(clientX) {
      const rect = svg.getBoundingClientRect();
      const relativeX = clientX - rect.left;
      let bestIndex = 0;
      let bestDistance = Number.POSITIVE_INFINITY;
      points.forEach(function (point, index) {
        const pointX = (point.x / 720) * rect.width;
        const distance = Math.abs(relativeX - pointX);
        if (distance < bestDistance) {
          bestDistance = distance;
          bestIndex = index;
        }
      });
      return bestIndex;
    }

    hitLine.addEventListener("mousemove", function (event) {
      showTooltip(nearestPointIndex(event.clientX), event.clientX, event.clientY);
    });
    hitLine.addEventListener("mouseleave", hideTooltip);

    pointNodes.forEach(function (node) {
      node.addEventListener("mouseenter", function (event) {
        showTooltip(Number(node.getAttribute("data-index") || 0), event.clientX, event.clientY);
      });
      node.addEventListener("mousemove", function (event) {
        showTooltip(Number(node.getAttribute("data-index") || 0), event.clientX, event.clientY);
      });
      node.addEventListener("mouseleave", hideTooltip);
    });
  }

  function buildGridLines(minValue, maxValue, padding, plotWidth, plotHeight) {
    const ticks = 4;
    const lines = [];
    for (let index = 0; index <= ticks; index += 1) {
      const ratio = index / ticks;
      const y = padding.top + plotHeight * ratio;
      const value = maxValue - (maxValue - minValue) * ratio;
      lines.push({ y: y, value: value });
    }
    return lines;
  }

  function shortLabel(label, index, total) {
    const text = String(label || "");
    if (total <= 6) {
      return text;
    }
    if (index === 0 || index === total - 1 || index % 2 === 0) {
      return text;
    }
    return "";
  }

  function formatChartNumber(value) {
    return typeof value === "number" ? value.toLocaleString() : String(value || "");
  }

  function clearOutput() {
    chatOutput.innerHTML = "";
  }

  async function apiRequest(url, method, body) {
    const options = {
      method: method,
      headers: {
        "X-CSRFToken": getCsrfToken(),
      },
      credentials: "same-origin",
    };
    if (body !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    const response = await fetch(url, options);
    const rawText = await response.text();
    let payload = null;
    try {
      payload = rawText ? JSON.parse(rawText) : null;
    } catch (error) {
      const message = rawText && rawText.trim().startsWith("<!DOCTYPE")
        ? "The server returned an HTML error page instead of JSON. Check the Django server logs."
        : "The server returned an invalid response.";
      throw new Error(message);
    }
    if (!response.ok || payload.result !== "SUCCESS") {
      const message = payload.error && payload.error.message ? payload.error.message : "Request failed.";
      throw new Error(message);
    }
    return payload.data;
  }

  async function loadHistory(room) {
    const rows = await apiRequest("/api/ai-chat/history/" + encodeURIComponent(room) + "/", "GET");
    clearOutput();
    if (!rows.length) {
      appendAiBubble("<p>Hello, I am Admas AI. Ask me in English or Amharic.</p>");
      return;
    }
    rows.forEach(function (item) {
      appendHtml(userMessageMarkup(item.question));
      if (item.response) {
        const bubble = appendAiBubble(item.response);
        applyBubbleState(bubble, {
          tool_data: item.tool_data || {},
          charts: item.charts || []
        });
      }
    });
  }

  function updateActiveInstance(room) {
    activeRoom = String(room || "");
    chatOutput.dataset.room = activeRoom;
    Array.prototype.forEach.call(instanceList.querySelectorAll(".ai-instance"), function (node) {
      node.classList.toggle("active", String(node.dataset.room) === activeRoom);
    });
    const activeNode = instanceList.querySelector('.ai-instance[data-room="' + CSS.escape(activeRoom) + '"]');
    chatTitle.textContent = activeNode ? activeNode.dataset.title : "New Chat";
    if (socket) {
      socket.close();
    }
    pendingBubble = null;
    ensureSocket().catch(function () {
      return null;
    });
    loadHistory(activeRoom).catch(function (error) {
      clearOutput();
      appendAiBubble("<p>" + escapeHtml(error.message) + "</p>");
    });
  }

  async function sendMessage() {
    const value = chatInput.value.trim();
    if (!value || !activeRoom || sending) {
      return;
    }
    try {
      await ensureSocket();
    } catch (error) {
      appendAiBubble("<p>" + escapeHtml(error.message || "Chat connection is not ready yet. Please try again.") + "</p>");
      return;
    }

    setSending(true);
    appendHtml(userMessageMarkup(value));
    pendingBubble = appendAiBubble("");
    setBubbleLoading(pendingBubble, true);
    chatInput.value = "";
    scrollToBottom();
    socket.send(JSON.stringify({ message: value }));
  }

  async function createInstance() {
    const data = await apiRequest("/api/ai-chat/", "POST", {});
    const node = document.createElement("div");
    node.className = "ai-instance active";
    node.dataset.room = String(data.id);
    node.dataset.title = data.title || "New Chat";
    node.dataset.tags = "policy ministry indicator";
    node.innerHTML = "<h6>" + escapeHtml(node.dataset.title) + "</h6><p>History #" + escapeHtml(node.dataset.room) + "</p>";
    instanceList.prepend(node);
    updateActiveInstance(node.dataset.room);
  }

  async function renameInstance() {
    if (!activeRoom) {
      return;
    }
    const nextTitle = window.prompt("Rename chat", chatTitle.textContent || "New Chat");
    if (!nextTitle) {
      return;
    }
    const data = await apiRequest("/api/ai-chat/instance/" + encodeURIComponent(activeRoom) + "/", "PATCH", { title: nextTitle });
    const node = instanceList.querySelector('.ai-instance[data-room="' + CSS.escape(activeRoom) + '"]');
    if (node) {
      node.dataset.title = data.title;
      node.querySelector("h6").textContent = data.title;
    }
    chatTitle.textContent = data.title;
  }

  async function deleteInstance() {
    if (!activeRoom) {
      return;
    }
    if (!window.confirm("Delete this chat?")) {
      return;
    }
    await apiRequest("/api/ai-chat/delete/" + encodeURIComponent(activeRoom) + "/", "DELETE");
    const node = instanceList.querySelector('.ai-instance[data-room="' + CSS.escape(activeRoom) + '"]');
    if (node) {
      node.remove();
    }
    const fallback = instanceList.querySelector(".ai-instance");
    if (fallback) {
      updateActiveInstance(fallback.dataset.room);
    } else {
      await createInstance();
    }
  }

  function filterInstances() {
    const query = (chatSearch.value || "").trim().toLowerCase();
    Array.prototype.forEach.call(instanceList.querySelectorAll(".ai-instance"), function (node) {
      const text = (node.dataset.title || "").toLowerCase();
      node.hidden = query && text.indexOf(query) === -1;
    });
  }

  function bindEvents() {
    document.addEventListener("click", function (event) {
      const openSourcePanels = chatOutput.querySelectorAll(".ai-sources-popover[open]");
      openSourcePanels.forEach(function (panel) {
        if (!panel.contains(event.target)) {
          panel.removeAttribute("open");
        }
      });
    });

    sendBtn.addEventListener("click", sendMessage);
    chatInput.addEventListener("keydown", function (event) {
      if (event.key === "Enter") {
        event.preventDefault();
        sendMessage();
      }
    });
    instanceList.addEventListener("click", function (event) {
      const node = event.target.closest(".ai-instance");
      if (node) {
        updateActiveInstance(node.dataset.room);
      }
    });
    chatOutput.addEventListener("click", function (event) {
      const sourceTrigger = event.target.closest(".ai-sources-popover summary");
      if (sourceTrigger) {
        const panel = sourceTrigger.closest(".ai-sources-popover");
        if (!panel) {
          return;
        }
        event.preventDefault();
        const isOpen = panel.hasAttribute("open");
        chatOutput.querySelectorAll(".ai-sources-popover[open]").forEach(function (item) {
          if (item !== panel) {
            item.removeAttribute("open");
          }
        });
        if (isOpen) {
          panel.removeAttribute("open");
        } else {
          panel.setAttribute("open", "open");
        }
        return;
      }

      const actionButton = event.target.closest("[data-ai-action]");
      if (!actionButton) {
        return;
      }
      const action = actionButton.getAttribute("data-ai-action");
      if (action === "follow") {
        const prompt = actionButton.getAttribute("data-prompt") || "";
        if (prompt) {
          const menu = actionButton.closest(".ai-action-menu");
          if (menu) {
            menu.removeAttribute("open");
          }
          chatInput.value = prompt;
          chatInput.focus();
        }
        return;
      }
      if (action === "toggle-view") {
        const bubble = actionButton.closest(".msg.ai");
        if (!bubble) {
          return;
        }
        const nextView = actionButton.getAttribute("data-view-mode") || "chart";
        bubble.dataset.viewMode = bubble.dataset.viewMode === nextView ? "none" : nextView;
        const content = bubble.querySelector(".ai-msg-content");
        const payload = {
          tool_data: safeObject(safeObject(bubble.__aiState).toolData),
          response_type: safeString(safeObject(bubble.__aiState).responseType),
          response_data: {
            response_type: safeString(safeObject(bubble.__aiState).responseType),
            title: safeString(safeObject(bubble.__aiState).title),
            summary: safeString(safeObject(bubble.__aiState).summary),
            data: safeObject(safeObject(bubble.__aiState).primaryData)
          },
          sources: safeArray(safeObject(bubble.__aiState).sources),
          charts: safeArray(safeObject(bubble.__aiState).charts),
          intent: safeString(safeObject(bubble.__aiState).intent),
          language: safeString(safeObject(bubble.__aiState).language),
          context_found: Boolean(safeObject(bubble.__aiState).contextFound)
        };
        applyBubbleState(bubble, payload);
        if (content) {
          scrollToBottom();
        }
        return;
      }
      if (action === "copy") {
        const bubble = actionButton.closest(".msg.ai");
        const content = bubble ? bubble.querySelector(".ai-msg-content") : null;
        if (!content || !navigator.clipboard) {
          return;
        }
        const text = content.innerText || content.textContent || "";
        navigator.clipboard.writeText(text).then(function () {
          actionButton.classList.add("is-done");
          window.setTimeout(function () {
            actionButton.classList.remove("is-done");
          }, 1400);
        }).catch(function () {
          return null;
        });
      }
    });
    newInstanceBtn.addEventListener("click", function () {
      createInstance().catch(function (error) {
        appendAiBubble("<p>" + escapeHtml(error.message) + "</p>");
      });
    });
    renameInstanceBtn.addEventListener("click", function () {
      renameInstance().catch(function (error) {
        appendAiBubble("<p>" + escapeHtml(error.message) + "</p>");
      });
    });
    deleteInstanceBtn.addEventListener("click", function () {
      deleteInstance().catch(function (error) {
        appendAiBubble("<p>" + escapeHtml(error.message) + "</p>");
      });
    });
    if (chatSearch) {
      chatSearch.addEventListener("input", filterInstances);
    }
    if (sidebarCollapseBtn && chatShell) {
      sidebarCollapseBtn.addEventListener("click", function () {
        chatShell.classList.add("is-collapsed");
      });
    }
    if (sidebarExpandBtn && chatShell) {
      sidebarExpandBtn.addEventListener("click", function () {
        chatShell.classList.remove("is-collapsed");
      });
    }
  }

  bindEvents();
  updateActiveInstance(activeRoom);
})();
