(function () {
    const dataNode = document.getElementById("vr-dashboard-data");
    const enterVrButton = document.getElementById("enter-vr-button");
    const previewButton = document.getElementById("focus-vr-preview");
    const themeDarkButton = document.getElementById("theme-dark-button");
    const themeLightButton = document.getElementById("theme-light-button");
    const statusNode = document.getElementById("xr-status");
    const stageNode = document.getElementById("vr-stage");
    const dashboardData = dataNode ? JSON.parse(dataNode.textContent) : {
        kpis: [],
        menu: [],
        notifications: [],
        charts: [],
    };

    let aframeReady = false;
    let sceneBuilt = false;
    let sceneLoading = null;
    let currentTheme = "dark";

    function applyThemeToMarkup(markup) {
        if (currentTheme !== "light") {
            return markup;
        }

        const replacements = [
            ["#04131d", "#f2f7fa"],
            ["#061420", "#e4edf2"],
            ["#07111a", "#e6eef3"],
            ["#08111a", "#edf4f7"],
            ["#09090b", "#f4f8fb"],
            ["#0b1622", "#fbfdff"],
            ["#0d1824", "#f3f8fb"],
            ["#0d1922", "#f3f8fb"],
            ["#10202f", "#dce8ef"],
            ["#10293b", "#d9e8ef"],
            ["#10354a", "#d6e8ef"],
            ["#112638", "#dbe8ef"],
            ["#123c42", "#d6eef1"],
            ["#0f2b32", "#dceff3"],
            ["#1a2a46", "#e1e8fb"],
            ["#1d3a62", "#d6e0f8"],
            ["#23311a", "#e7f1db"],
            ["#365314", "#d8ebb9"],
            ["#3a2413", "#fbe7d9"],
            ["#1a120d", "#fff3eb"],
            ["#120b07", "#fff4ee"],
            ["#7c2d12", "#efc0a8"],
            ["#4a2d16", "#efd4c4"],
            ["#3a102e", "#f8ddea"],
            ["#190713", "#fdf0f7"],
            ["#4d1739", "#f0d7e6"],
            ["#831843", "#e8bfd3"],
            ["#4c1d95", "#ddd6fe"],
            ["#f8fafc", "#ffffff"],
            ["#f0fbff", "#ffffff"],
            ["#eff9ff", "#ffffff"],
            ["#dffaff", "#ffffff"],
            ["#ffffff", "#ffffff"],
            ["#dbeafe", "#ffffff"],
            ["#cbd5e1", "#ffffff"],
            ["#b7d3df", "#ffffff"],
            ["#8fb5c7", "#ffffff"],
            ["#8eb3c6", "#ffffff"],
            ["#7ea2b4", "#ffffff"],
            ["#5de4c7", "#0f766e"],
            ["#8ef1e5", "#0f766e"],
            ["#7dd3fc", "#0369a1"],
            ["#7cb8ff", "#2563eb"],
            ["#fb923c", "#ea580c"],
            ["#fdba74", "#c2410c"],
            ["#fed7aa", "#ffffff"],
            ["#fde7d4", "#ffffff"],
            ["#fff7ed", "#ffffff"],
            ["#f472b6", "#db2777"],
            ["#fce7f3", "#ffffff"],
            ["#fdf2f8", "#ffffff"],
            ["#a3e635", "#65a30d"],
            ["#bef264", "#4d7c0f"],
            ["#d7fff5", "#0f766e"],
            ["#c4e7ff", "#075985"],
        ];

        return replacements.reduce((result, [from, to]) => result.replaceAll(from, to), markup);
    }

    function refreshThemeButtons() {
        if (themeDarkButton) {
            themeDarkButton.disabled = currentTheme === "dark";
        }
        if (themeLightButton) {
            themeLightButton.disabled = currentTheme === "light";
        }
    }

    function pickLabel(item, keys) {
        if (!item) {
            return "";
        }
        for (const key of keys) {
            const value = item[key];
            if (value !== null && value !== undefined && String(value).trim()) {
                return String(value).trim();
            }
        }
        return "";
    }

    function escapeAttribute(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll('"', "&quot;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;");
    }

    function truncate(value, maxLength = 140) {
        const text = String(value ?? "").trim();
        if (!text) {
            return "";
        }
        return text.length > maxLength ? `${text.slice(0, maxLength).trim()}...` : text;
    }

    function buildMediaUrl(path) {
        if (!path) {
            return "";
        }
        try {
            return new URL(path, (dashboardData.dataEndpoints && dashboardData.dataEndpoints.mediaBaseUrl) || window.location.origin).toString();
        } catch (_error) {
            return String(path);
        }
    }

    function buildProxyMediaUrl(path) {
        const resolved = buildMediaUrl(path);
        if (!resolved) {
            return "";
        }
        const proxy = dashboardData.dataEndpoints && dashboardData.dataEndpoints.imageProxy;
        if (!proxy) {
            return resolved;
        }
        return `${proxy}?url=${encodeURIComponent(resolved)}`;
    }

    function parsePictureList(value) {
        if (Array.isArray(value)) {
            return value.map((item) => buildProxyMediaUrl(item)).filter(Boolean);
        }
        const raw = String(value ?? "").trim();
        if (!raw) {
            return [];
        }
        try {
            const parsed = JSON.parse(raw);
            if (Array.isArray(parsed)) {
                return parsed.map((item) => buildProxyMediaUrl(item)).filter(Boolean);
            }
        } catch (_error) {
            return [buildProxyMediaUrl(raw)].filter(Boolean);
        }
        return [];
    }

    function formatValue(value) {
        if (value === null || value === undefined || value === "") {
            return "--";
        }

        const numeric = Number(value);
        if (!Number.isFinite(numeric)) {
            return String(value);
        }

        const formatted = numeric % 1 === 0 ? numeric.toFixed(0) : numeric.toFixed(2);
        return formatted.replace(/\.00$/, "");
    }

    function getSeriesByLatestData(indicator) {
        const latestData = String(indicator && indicator.latest_data || "").toLowerCase();
        if (!latestData) {
            return [];
        }

        const seriesMap = {
            annual: indicator.annual_data || [],
            yearly: indicator.annual_data || [],
            quarter: indicator.quarter_data || [],
            quarterly: indicator.quarter_data || [],
            month: indicator.month_data || [],
            monthly: indicator.month_data || [],
            week: indicator.week_data || [],
            weekly: indicator.week_data || [],
            day: indicator.day_data || [],
            daily: indicator.day_data || [],
        };

        return seriesMap[latestData] || [];
    }

    function getPointSortValue(point, frequency) {
        const year = Number(point && point.for_datapoint || 0);
        const quarterValue = Number(String(point && point.for_quarter || "").replace(/[^0-9]/g, "") || 0);
        const monthMap = {
            "መስከረም": 1,
            "ጥቅምት": 2,
            "ኅዳር": 3,
            "ህዳር": 3,
            "ታኅሣሥ": 4,
            "ታህሳስ": 4,
            "ጥር": 5,
            "የካቲት": 6,
            "መጋቢት": 7,
            "ሚያዝያ": 8,
            "ግንቦት": 9,
            "ሰኔ": 10,
            "ሐምሌ": 11,
            "ሀምሌ": 11,
            "ነሐሴ": 12,
            "ነሀሴ": 12,
        };
        const rawMonth = String(point && point.for_month || "").trim();
        const monthValue = monthMap[rawMonth] || Number(rawMonth.replace(/[^0-9]/g, "") || 0);
        const weekValue = Number(point && point.for_week || 0);
        const dayValue = Number(point && point.for_day || 0);

        if (frequency === "quarter" || frequency === "quarterly") {
            return year * 10 + quarterValue;
        }
        if (frequency === "month" || frequency === "monthly") {
            return year * 100 + monthValue;
        }
        if (frequency === "week" || frequency === "weekly") {
            return year * 100 + weekValue;
        }
        if (frequency === "day" || frequency === "daily") {
            return year * 1000 + dayValue;
        }
        return year;
    }

    function getLatestPoint(indicator) {
        const series = getSeriesByLatestData(indicator);
        if (!Array.isArray(series) || !series.length) {
            return null;
        }

        const frequency = String(indicator && indicator.latest_data || "").toLowerCase();
        return [...series].sort((left, right) => getPointSortValue(left, frequency) - getPointSortValue(right, frequency)).at(-1) || null;
    }

    function getRecentPoints(indicator, limit = 5) {
        const series = getSeriesByLatestData(indicator)
            .filter((point) => point && point.performance !== null && point.performance !== undefined);
        if (!series.length) {
            return [];
        }
        const frequency = String(indicator && indicator.latest_data || "").toLowerCase();
        return [...series]
            .sort((left, right) => getPointSortValue(left, frequency) - getPointSortValue(right, frequency))
            .slice(-limit);
    }

    function getRecentPointLabel(point, frequency) {
        if (frequency === "quarter" || frequency === "quarterly") {
            return `${point.for_datapoint || ""} ${point.for_quarter || ""}`.trim();
        }
        if (frequency === "month" || frequency === "monthly") {
            return `${point.for_datapoint || ""} ${point.for_month || ""}`.trim();
        }
        return String(point.for_datapoint || point.for_month || point.for_quarter || "Point");
    }

    async function fetchJson(url) {
        const response = await fetch(url, {
            headers: { Accept: "application/json" },
            credentials: "same-origin",
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        return response.json();
    }

    function getSourceQueryParams() {
        try {
            return new URL(String(dashboardData.sourcePage && dashboardData.sourcePage.url || ""), window.location.origin).searchParams;
        } catch (_error) {
            return new URLSearchParams();
        }
    }

    function getDpmesState() {
        const params = getSourceQueryParams();
        return {
            year: params.get("year") || "2018",
            quarter: params.get("quarter") || "3month",
            dateType: params.get("quarter") ? "quarterly" : "yearly",
        };
    }

    function formatPercent(value) {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) {
            return "--";
        }
        return `${numeric.toFixed(2)}%`;
    }

    function getDpmesQuarterSortValue(value) {
        const map = { "3month": 1, "6month": 2, "9month": 3, "12month": 4 };
        return map[String(value || "").trim()] || 0;
    }

    function getDpmesIndicatorSeries(indicator, state) {
        if (state.dateType === "quarterly") {
            return Array.isArray(indicator && indicator.quarter_indicators) ? indicator.quarter_indicators : [];
        }
        return Array.isArray(indicator && indicator.annual_indicators) ? indicator.annual_indicators : [];
    }

    function getDpmesSortedSeries(indicator, state) {
        return [...getDpmesIndicatorSeries(indicator, state)].sort((left, right) => {
            const leftYear = Number(left && left.year || 0);
            const rightYear = Number(right && right.year || 0);
            if (leftYear !== rightYear) {
                return leftYear - rightYear;
            }
            if (state.dateType === "quarterly") {
                return getDpmesQuarterSortValue(left && left.quarter) - getDpmesQuarterSortValue(right && right.quarter);
            }
            return 0;
        });
    }

    function getDpmesLatestIndicatorRecord(indicator, state) {
        return getDpmesSortedSeries(indicator, state).at(-1) || null;
    }

    function getDpmesRecentIndicatorPoints(indicator, state, limit = 5) {
        return getDpmesSortedSeries(indicator, state)
            .slice(-limit)
            .map((record) => ({
                label: state.dateType === "quarterly"
                    ? `${record.year || "--"} ${record.quarter || ""}`.trim()
                    : String(record.year || "--"),
                value: Number(state.dateType === "quarterly" ? record.quarter_performance : record.annual_performance || 0),
                score: Number(record && record.score || 0),
            }));
    }

    async function hydrateDashboardHomeData() {
        if (dashboardData.sceneVariant !== "dashboard-home" || dashboardData.__homeHydrated) {
            return;
        }

        dashboardData.__homeHydrated = true;
        const endpoints = dashboardData.dataEndpoints || {};
        const defaultTimePayload = endpoints.defaultTime ? await fetchJson(endpoints.defaultTime).catch(() => null) : null;
        const defaultTime = defaultTimePayload && defaultTimePayload.data ? defaultTimePayload.data : {};
        const year = defaultTime.year ? String(defaultTime.year) : "2018";
        const quarter = defaultTime.quarter || "3month";
        const ministriesUrl = `${endpoints.ministries || "/api/mobile/ministries/"}?year=${encodeURIComponent(year)}&quarter=${encodeURIComponent(quarter)}`;

        const [topicsPayload, ministriesPayload, indicatorsPayload, projectsPayload, initiativesPayload] = await Promise.all([
            endpoints.topics ? fetchJson(endpoints.topics).catch(() => null) : null,
            fetchJson(ministriesUrl).catch(() => null),
            endpoints.trending ? fetchJson(endpoints.trending).catch(() => null) : null,
            endpoints.projects ? fetchJson(endpoints.projects).catch(() => null) : null,
            endpoints.initiatives ? fetchJson(endpoints.initiatives).catch(() => null) : null,
        ]);

        const topics = Array.isArray(topicsPayload && topicsPayload.data)
            ? topicsPayload.data.slice().sort((a, b) => Number(a.rank || 0) - Number(b.rank || 0)).slice(0, 3)
            : [];
        const ministries = Array.isArray(ministriesPayload && ministriesPayload.data)
            ? ministriesPayload.data
                .filter((item) => item && item.show_mobile_dashboard && item.ministry_is_visable)
                .sort((a, b) => Number(a.ministry_rank || 9999) - Number(b.ministry_rank || 9999))
                .slice(0, 3)
            : [];
        const indicators = Array.isArray(indicatorsPayload && indicatorsPayload.data)
            ? indicatorsPayload.data.filter((item) => item && item.indicator).slice(0, 3)
            : [];
        const projectRows = Array.isArray(projectsPayload && projectsPayload.data) ? projectsPayload.data : [];
        const projects = projectRows.filter((item) => item && item.is_initiative !== true).slice(0, 3);
        const initiatives = Array.isArray(initiativesPayload && initiativesPayload.data)
            ? initiativesPayload.data.slice(0, 3)
            : projectRows.filter((item) => item && item.is_initiative === true).slice(0, 3);

        dashboardData.kpis = [
            {
                label: "Topics",
                value: String(topics.length || 0),
                delta: pickLabel(topics[0], ["title_ENG", "title_AMH"]) || "Key Development Statistics",
                position: "-1.45 1.95 -2.35",
            },
            {
                label: "Ministries",
                value: String(ministries.length || 0),
                delta: pickLabel(ministries[0], ["code", "responsible_ministry_eng", "responsible_ministry_amh"]) || "Scorecards in focus",
                position: "0 2.08 -2.2",
            },
            {
                label: "Indicators",
                value: String(indicators.length || 0),
                delta: pickLabel(indicators[0] && indicators[0].indicator, ["title_ENG", "title_AMH"]) || "High-frequency tiles",
                position: "1.45 1.95 -2.35",
            },
        ];

        dashboardData.notifications = [
            topics[0] ? `Topic strip lead: ${pickLabel(topics[0], ["title_ENG", "title_AMH"])}` : "Topic strip is ready for drill-down",
            ministries[0]
                ? `Ministry scorecard focus: ${pickLabel(ministries[0], ["code", "responsible_ministry_eng", "responsible_ministry_amh"])}`
                : "Ministry scorecards remain pinned in the left arc",
            projects[0]
                ? `Project spotlight: ${pickLabel(projects[0], ["title_ENG", "title_AMH"])}`
                : "Projects and initiatives are staged as secondary panels",
        ];
        dashboardData.homeTopics = topics.map((item) => ({
            title: pickLabel(item, ["title_ENG", "title_AMH"]) || "Topic",
            metaPrimary: `${Number(item.count_category || 0)} categories`,
            metaSecondary: `${Number(item.count_kpis || 0)} KPIs`,
        }));
        dashboardData.homeMinistries = ministries.map((item) => ({
            code: pickLabel(item, ["code"]) || "N/A",
            title: pickLabel(item, ["responsible_ministry_eng", "responsible_ministry_amh"]) || "Ministry",
            score: item && item.ministry_score_card && item.ministry_score_card.avg_score !== undefined
                ? `${Number(item.ministry_score_card.avg_score).toFixed(1)}%`
                : "--",
            indicators: `${Number(item.count_indicator || 0)} indicators`,
        }));
        dashboardData.homeIndicators = indicators
            .map((item) => pickLabel(item && item.indicator, ["title_ENG", "title_AMH"]))
            .filter(Boolean)
            .slice(0, 3);
        dashboardData.homeProjects = projects
            .map((item) => pickLabel(item, ["title_ENG", "title_AMH"]))
            .filter(Boolean)
            .slice(0, 3);
        dashboardData.homeInitiatives = initiatives
            .map((item) => pickLabel(item, ["title_ENG", "title_AMH"]))
            .filter(Boolean)
            .slice(0, 3);

        dashboardData.sectionPanels = [
            {
                title: "Key Development Statistics",
                subtitle: "Scrollable topic strip",
                position: "-2.65 1.55 -4.7",
                rotation: "0 18 0",
                items: topics.map((item) => pickLabel(item, ["title_ENG", "title_AMH"])).filter(Boolean),
            },
            {
                title: "Ministry Scorecard",
                subtitle: `Performance cards for ${year}${quarter ? ` ${quarter}` : ""}`,
                position: "-1.05 1.9 -4.2",
                rotation: "0 8 0",
                items: ministries.map((item) => {
                    const name = pickLabel(item, ["code", "responsible_ministry_eng", "responsible_ministry_amh"]);
                    const score = item && item.ministry_score_card ? item.ministry_score_card.avg_score : null;
                    return score !== null && score !== undefined ? `${name} ${Number(score).toFixed(1)}%` : name;
                }).filter(Boolean),
            },
            {
                title: "Program Summaries",
                subtitle: "Fayda and Mesob snapshots",
                position: "0.7 1.95 -4.1",
                rotation: "0 -6 0",
                items: ["Fayda eKYC", "Fayda registrations", "Mesob service snapshot"],
            },
            {
                title: "High Frequency Indicators",
                subtitle: "Trending KPI feed",
                position: "2.3 1.55 -4.55",
                rotation: "0 -18 0",
                items: indicators.map((item) => pickLabel(item && item.indicator, ["title_ENG", "title_AMH"])).filter(Boolean),
            },
            {
                title: "Projects",
                subtitle: "Sector portfolio strip",
                position: "-1.2 0.92 -4.95",
                rotation: "0 10 0",
                items: projects.map((item) => pickLabel(item, ["title_ENG", "title_AMH"])).filter(Boolean),
            },
            {
                title: "Initiatives",
                subtitle: "National spotlight cards",
                position: "1.25 0.96 -4.85",
                rotation: "0 -10 0",
                items: initiatives.map((item) => pickLabel(item, ["title_ENG", "title_AMH"])).filter(Boolean),
            },
        ];
    }

    async function hydrateDataCatalogSceneData() {
        if (dashboardData.sceneVariant !== "data-catalog" || dashboardData.__dataCatalogHydrated) {
            return;
        }

        dashboardData.__dataCatalogHydrated = true;
        const endpoints = dashboardData.dataEndpoints || {};
        const [topicsPayload, indicatorsPayload] = await Promise.all([
            endpoints.topics ? fetchJson(endpoints.topics).catch(() => null) : null,
            endpoints.trending ? fetchJson(endpoints.trending).catch(() => null) : null,
        ]);

        const topics = Array.isArray(topicsPayload && topicsPayload.data)
            ? topicsPayload.data.slice().sort((a, b) => Number(a.rank || 9999) - Number(b.rank || 9999)).slice(0, 8)
            : [];
        const indicatorRows = Array.isArray(indicatorsPayload && indicatorsPayload.data)
            ? indicatorsPayload.data.filter((item) => item && item.indicator).slice(0, 6)
            : [];

        dashboardData.dataCatalogTopics = topics.map((topic) => ({
            id: topic.id,
            title: pickLabel(topic, ["title_ENG", "title_AMH"]) || "Topic",
            description: truncate(topic.description || "Explore indicators, categories, and topic-specific data assets.", 120),
            categories: `${Number(topic.count_category || 0)} categories`,
            kpis: `${Number(topic.count_kpis || 0)} KPIs`,
            image: buildProxyMediaUrl(topic.background_image || topic.image),
            icon: buildProxyMediaUrl(topic.image_icons),
        }));

        dashboardData.dataCatalogIndicators = indicatorRows.map((row) => {
            const indicator = row.indicator || {};
            const latestPoint = getLatestPoint(indicator);
            const unit =
                indicator[`measurement_units_${String(indicator.latest_data || "").toLowerCase()}`] ||
                indicator.measurement_units ||
                "-";
            return {
                id: indicator.id,
                title: pickLabel(indicator, ["title_ENG", "title_AMH"]) || "Indicator",
                value: formatValue(latestPoint ? latestPoint.performance : null),
                unit: unit || "-",
            };
        });

        if (topics.length) {
            dashboardData.kpis = [
                {
                    label: "Topics",
                    value: String(topics.length),
                    delta: pickLabel(topics[0], ["title_ENG", "title_AMH"]) || "Topic Catalog",
                    position: "-1.45 1.95 -2.35",
                },
                {
                    label: "Categories",
                    value: String(topics.reduce((sum, item) => sum + Number(item.count_category || 0), 0)),
                    delta: "Across featured topics",
                    position: "0 2.08 -2.2",
                },
                {
                    label: "Indicators",
                    value: String(indicatorRows.length),
                    delta: "High frequency feed",
                    position: "1.45 1.95 -2.35",
                },
            ];

            dashboardData.notifications = [
                `Lead topic: ${pickLabel(topics[0], ["title_ENG", "title_AMH"]) || "Topic Catalog"}`,
                topics[1]
                    ? `Next topic: ${pickLabel(topics[1], ["title_ENG", "title_AMH"])}`
                    : "Topic catalog is ready for browsing",
                indicatorRows[0]
                    ? `Live indicator: ${pickLabel(indicatorRows[0].indicator, ["title_ENG", "title_AMH"])}`
                    : "High frequency indicators are staged below",
            ];
        }
    }

    async function hydrateTopicDetailSceneData() {
        if (dashboardData.sceneVariant !== "data-topic-detail" || dashboardData.__topicDetailHydrated) {
            return;
        }

        dashboardData.__topicDetailHydrated = true;
        const match = String(dashboardData.sourcePage && dashboardData.sourcePage.url || "").match(/\/dashboard\/data\/(\d+)\/?$/);
        const topicId = match ? match[1] : "";
        if (!topicId) {
            return;
        }

        const endpoints = dashboardData.dataEndpoints || {};
        const [topicPayload, categoriesPayload, topicsPayload] = await Promise.all([
            fetchJson(`${endpoints.topicDetailBase || "/api/mobile/topic-detail/"}${topicId}/`).catch(() => null),
            fetchJson(`${endpoints.categoriesBase || "/api/mobile/categories/"}${topicId}/`).catch(() => null),
            endpoints.topics ? fetchJson(endpoints.topics).catch(() => null) : null,
        ]);

        const topicData = topicPayload && topicPayload.data ? topicPayload.data : topicPayload || {};
        const topic = Array.isArray(topicData) ? (topicData[0] || {}) : topicData;
        const topicList = Array.isArray(topicsPayload && topicsPayload.data) ? topicsPayload.data : [];
        const topicListMatch = topicList.find((item) => String(item && item.id) === String(topicId)) || {};
        const detailCategories = Array.isArray(topic && topic.categories) ? topic.categories : [];
        const detailCategoryMap = new Map(
            detailCategories.map((item) => [String(item && (item.id ?? item.category_id ?? item.code ?? "")), item])
        );
        const categories = Array.isArray(categoriesPayload && categoriesPayload.data) ? categoriesPayload.data.slice(0, 8) : [];
        const categoryNames = categories.map((item) => pickLabel(item, ["name_ENG", "name_AMH"])).filter(Boolean);
        dashboardData.topicDetail = {
            id: topicId,
            title: pickLabel(topic, ["title_ENG", "title_AMH"]) || (dashboardData.sourcePage && dashboardData.sourcePage.title) || `Topic ${topicId}`,
            description: truncate(topic.description || "Explore topic categories and KPI groups in an immersive layout.", 180),
            image: buildProxyMediaUrl(
                topic.background_image ||
                topic.image ||
                topic.image_icons ||
                topicListMatch.background_image ||
                topicListMatch.image ||
                topicListMatch.image_icons
            ),
            icon: buildProxyMediaUrl(topic.image_icons || topicListMatch.image_icons || topicListMatch.image || topicListMatch.background_image),
            categoryCount: Number(topic.count_category || categories.length || 0),
            kpiCount: 0,
            code: pickLabel(topic, ["code", "topic_code"]) || "No code",
        };
        dashboardData.topicCategories = categories.map((item) => {
            const detailCategory = detailCategoryMap.get(String(item && (item.id ?? item.category_id ?? item.code ?? "")));
            const embeddedIndicators = Array.isArray(detailCategory && detailCategory.indicators) ? detailCategory.indicators : [];
            return {
                id: item.id,
                title: pickLabel(item, ["name_ENG", "name_AMH"]) || "Category",
                code: pickLabel(item, ["code"]) || "No code",
                indicatorCount: embeddedIndicators.length,
            };
        });
        dashboardData.topicDetail.kpiCount = dashboardData.topicCategories.reduce(
            (sum, item) => sum + Number(item.indicatorCount || 0),
            0
        );
        dashboardData.kpis = [
            { label: "Categories", value: String(dashboardData.topicDetail.categoryCount), delta: categoryNames[0] || "Topic structure", position: "-1.45 1.95 -2.35" },
            { label: "KPIs", value: String(dashboardData.topicDetail.kpiCount), delta: categoryNames[1] || "Category summaries", position: "0 2.08 -2.2" },
            { label: "Code", value: dashboardData.topicDetail.code, delta: dashboardData.topicDetail.title, position: "1.45 1.95 -2.35" },
        ];
        dashboardData.notifications = [
            categoryNames[0] ? `Lead category: ${categoryNames[0]}` : "No categories available yet",
            categoryNames[1] ? `Next category: ${categoryNames[1]}` : "Category pods are ready",
            `${dashboardData.topicDetail.kpiCount} KPIs linked to this topic`,
        ];
    }

    async function hydrateCategoryDetailSceneData() {
        if (dashboardData.sceneVariant !== "data-category-detail" || dashboardData.__categoryDetailHydrated) {
            return;
        }

        dashboardData.__categoryDetailHydrated = true;
        const match = String(dashboardData.sourcePage && dashboardData.sourcePage.url || "").match(/\/dashboard\/data\/(\d+)\/?$/);
        const topicId = match ? match[1] : "";
        const categoryId = String(dashboardData.categorySelection && dashboardData.categorySelection.id || "");
        if (!topicId || !categoryId) {
            return;
        }

        const endpoints = dashboardData.dataEndpoints || {};
        const [topicPayload, categoriesPayload, kpisPayload] = await Promise.all([
            fetchJson(`${endpoints.topicDetailBase || "/api/mobile/topic-detail/"}${topicId}/`).catch(() => null),
            fetchJson(`${endpoints.categoriesBase || "/api/mobile/categories/"}${topicId}/`).catch(() => null),
            fetchJson(`${endpoints.kpisBase || "/api/mobile/kpis/"}${categoryId}/`).catch(() => null),
        ]);

        const topicData = topicPayload && topicPayload.data ? topicPayload.data : topicPayload || {};
        const topic = Array.isArray(topicData) ? (topicData[0] || {}) : topicData;
        const detailCategories = Array.isArray(topic && topic.categories) ? topic.categories : [];
        const detailCategory = detailCategories.find((item) => String(item && item.id) === categoryId) || null;

        const categories = Array.isArray(categoriesPayload && categoriesPayload.data) ? categoriesPayload.data : [];
        const categoryMeta = categories.find((item) => String(item && item.id) === categoryId) || {};

        const indicatorRows = Array.isArray(kpisPayload && kpisPayload.data) ? kpisPayload.data : [];
        const indicators = indicatorRows
            .map((row) => row && (row.indicator || row))
            .filter(Boolean)
            .map((indicator) => {
                const latestPoint = getLatestPoint(indicator);
                const frequency = String(indicator.latest_data || "").toLowerCase();
                const unit =
                    indicator[`measurement_units_${frequency}`] ||
                    indicator.measurement_units ||
                    "-";
                return {
                    id: indicator.id,
                    title: pickLabel(indicator, ["title_ENG", "title_AMH"]) || "Indicator",
                    unit: unit || "-",
                    latestValue: formatValue(latestPoint ? latestPoint.performance : null),
                    points: getRecentPoints(indicator, 5).map((point) => ({
                        label: getRecentPointLabel(point, frequency),
                        value: Number(point && point.performance || 0),
                    })),
                };
            });

        const categoryTitle =
            pickLabel(detailCategory, ["name_ENG", "name_AMH"]) ||
            pickLabel(categoryMeta, ["name_ENG", "name_AMH"]) ||
            (dashboardData.categorySelection && dashboardData.categorySelection.title) ||
            "Category";
        const categoryCode =
            pickLabel(detailCategory, ["code"]) ||
            pickLabel(categoryMeta, ["code"]) ||
            "No code";
        const topicTitle =
            pickLabel(topic, ["title_ENG", "title_AMH"]) ||
            (dashboardData.sourcePage && dashboardData.sourcePage.title) ||
            `Topic ${topicId}`;

        dashboardData.categoryDetail = {
            id: categoryId,
            title: categoryTitle,
            code: categoryCode,
            topicTitle: topicTitle,
            indicators: indicators,
            indicatorCount: indicators.length,
        };

        dashboardData.kpis = [
            { label: "Category", value: categoryTitle, delta: topicTitle, position: "-1.45 1.95 -2.35" },
            { label: "Indicators", value: String(indicators.length), delta: categoryCode, position: "0 2.08 -2.2" },
            {
                label: "Latest",
                value: indicators[0] ? indicators[0].latestValue : "--",
                delta: indicators[0] ? `${indicators[0].title} ${indicators[0].unit}` : "No indicators yet",
                position: "1.45 1.95 -2.35",
            },
        ];
        dashboardData.notifications = [
            `Topic: ${topicTitle}`,
            `${categoryTitle} has ${indicators.length} indicators in this VR board`,
            indicators[0] ? `Lead indicator: ${indicators[0].title}` : "No indicator data is available for this category",
        ];
    }

    async function hydrateProjectCatalogSceneData() {
        if (dashboardData.sceneVariant !== "project-catalog" || dashboardData.__projectCatalogHydrated) {
            return;
        }

        dashboardData.__projectCatalogHydrated = true;
        const endpoints = dashboardData.dataEndpoints || {};
        const payload = endpoints.projects ? await fetchJson(endpoints.projects).catch(() => null) : null;
        const rows = Array.isArray(payload && payload.data) ? payload.data : [];
        const projects = rows.filter((item) => item && item.is_initiative !== true).slice(0, 14);

        dashboardData.projectCatalog = projects.map((project) => ({
            id: project.id,
            title: pickLabel(project, ["title_ENG", "title_AMH"]) || "Project",
            description: truncate(project.description || "Sector project detail is available in the immersive view.", 120),
            image: buildProxyMediaUrl(project.image || project.background_image),
            icon: buildProxyMediaUrl(project.image_icons),
        }));

        dashboardData.kpis = [
            { label: "Projects", value: String(projects.length), delta: "Loaded into VR", position: "-1.45 1.95 -2.35" },
            { label: "Images", value: String(projects.filter((item) => item && (item.image || item.background_image)).length), delta: "Image-backed cards", position: "0 2.08 -2.2" },
            { label: "Types", value: "Sector", delta: "Project catalog", position: "1.45 1.95 -2.35" },
        ];
        dashboardData.notifications = [
            projects[0] ? `Lead project: ${pickLabel(projects[0], ["title_ENG", "title_AMH"])}` : "No projects available",
            projects[1] ? `Next project: ${pickLabel(projects[1], ["title_ENG", "title_AMH"])}` : "Project cards are ready",
            "Open a project card to enter its detail room",
        ];
    }

    async function hydrateProjectDetailSceneData() {
        if (dashboardData.sceneVariant !== "project-detail" || dashboardData.__projectDetailHydrated) {
            return;
        }

        dashboardData.__projectDetailHydrated = true;
        const match = String(dashboardData.sourcePage && dashboardData.sourcePage.url || "").match(/\/dashboard\/projects\/sector\/(\d+)\/?/);
        const projectId = match ? match[1] : "";
        if (!projectId) {
            return;
        }

        const endpoints = dashboardData.dataEndpoints || {};
        const [detailPayload, listPayload] = await Promise.all([
            fetchJson(`${endpoints.projectDetailBase || "/api/mobile/project-detail/"}${projectId}/`).catch(() => null),
            endpoints.projects ? fetchJson(endpoints.projects).catch(() => null) : null,
        ]);

        const detail = detailPayload && detailPayload.data ? detailPayload.data : detailPayload || {};
        const projectRows = Array.isArray(listPayload && listPayload.data) ? listPayload.data : [];
        const projectListMatch = projectRows.find((item) => String(item && item.id) === String(projectId)) || {};
        const subProjects = Array.isArray(detail && detail.sub_projects && detail.sub_projects.projects)
            ? detail.sub_projects.projects
            : [];

        dashboardData.projectDetail = {
            id: projectId,
            title: pickLabel(detail, ["title_ENG", "title_AMH"]) || pickLabel(projectListMatch, ["title_ENG", "title_AMH"]) || `Project ${projectId}`,
            description: truncate(detail.description || projectListMatch.description || "Explore the selected project and its sub-project metrics.", 180),
            image: buildProxyMediaUrl(
                detail.image ||
                detail.background_image ||
                projectListMatch.image ||
                projectListMatch.background_image
            ),
            icon: buildProxyMediaUrl(detail.image_icons || projectListMatch.image_icons),
            subProjectCount: subProjects.length,
            metricCount: subProjects.reduce((sum, item) => sum + Number(Array.isArray(item && item.data) ? item.data.length : 0), 0),
            pictureCount: subProjects.reduce((sum, item) => {
                const dataRows = Array.isArray(item && item.data) ? item.data : [];
                const firstRow = dataRows[0] || {};
                return sum + (parsePictureList(firstRow.Pictures || firstRow.pictures || item.pictures).length ? 1 : 0);
            }, 0) + ((detail.image || detail.background_image || projectListMatch.image || projectListMatch.background_image) ? 1 : 0),
        };

        dashboardData.projectSubProjects = subProjects.map((item, index) => {
            const dataRows = Array.isArray(item && item.data) ? item.data : [];
            const firstRow = dataRows[0] || {};
            const pictures = parsePictureList(firstRow.Pictures || firstRow.pictures || item.pictures);
            const detailEntries = Object.entries(firstRow || {})
                .filter(([key, value]) => {
                    if (!String(value ?? "").trim()) {
                        return false;
                    }
                    return !["Pictures", "pictures", "Description", "description", "Name", "title"].includes(key);
                })
                .slice(0, 4)
                .map(([key, value]) => `${key}: ${String(value).trim()}`);

            return {
                id: item.id || index + 1,
                title: pickLabel(item, ["title_ENG", "title_AMH"]) || `Sub Project ${index + 1}`,
                description: truncate(firstRow.Description || firstRow.description || item.description || "Sub-project detail pack", 110),
                metrics: `${Number(dataRows.length)} data rows`,
                pictureLabel: pictures.length ? `${pictures.length} picture${pictures.length === 1 ? "" : "s"}` : "No picture",
                image: buildProxyMediaUrl(item.image || item.background_image) || pictures[0] || "",
                pictures: pictures,
                detailLines: detailEntries,
                isRegional: Boolean(item && item.is_regional),
            };
        });

        dashboardData.kpis = [
            { label: "Project", value: dashboardData.projectDetail.title, delta: "Selected project", position: "-1.45 1.95 -2.35" },
            { label: "Sub Projects", value: String(dashboardData.projectDetail.subProjectCount), delta: "Around the center", position: "0 2.08 -2.2" },
            { label: "Pictures", value: String(dashboardData.projectDetail.pictureCount), delta: "Image-backed project view", position: "1.45 1.95 -2.35" },
        ];
        dashboardData.notifications = [
            dashboardData.projectSubProjects[0] ? `Lead sub-project: ${dashboardData.projectSubProjects[0].title}` : "No sub-projects available",
            dashboardData.projectSubProjects[1] ? `Next sub-project: ${dashboardData.projectSubProjects[1].title}` : "Sub-project cards are ready",
            "Project detail uses the project image on the center cube when available",
        ];
    }

    async function hydrateProjectSubDetailSceneData() {
        if (dashboardData.sceneVariant !== "project-sub-detail" || dashboardData.__projectSubDetailHydrated) {
            return;
        }

        dashboardData.__projectSubDetailHydrated = true;
        const match = String(dashboardData.sourcePage && dashboardData.sourcePage.url || "").match(/\/dashboard\/projects\/sector\/(\d+)\/?/);
        const projectId = match ? match[1] : "";
        const projectSubId = String(dashboardData.projectSubSelection && dashboardData.projectSubSelection.id || "");
        if (!projectId || !projectSubId) {
            return;
        }

        const endpoints = dashboardData.dataEndpoints || {};
        const payload = await fetchJson(`${endpoints.projectDetailBase || "/api/mobile/project-detail/"}${projectId}/`).catch(() => null);
        const detail = payload && payload.data ? payload.data : payload || {};
        const subProjects = Array.isArray(detail && detail.sub_projects && detail.sub_projects.projects)
            ? detail.sub_projects.projects
            : [];
        const subProject = subProjects.find((item) => String(item && item.id) === projectSubId) || {};
        const dataRows = Array.isArray(subProject && subProject.data) ? subProject.data : [];
        const firstRow = dataRows[0] || {};
        const pictures = parsePictureList(firstRow.Pictures || firstRow.pictures || subProject.pictures);
        const detailEntries = Object.entries(firstRow || {})
            .filter(([key, value]) => String(value ?? "").trim() && !["Pictures", "pictures"].includes(key))
            .map(([key, value]) => ({
                key: String(key),
                value: truncate(String(value).trim(), 88),
            }));

        dashboardData.projectSubDetail = {
            id: projectSubId,
            title: pickLabel(subProject, ["title_ENG", "title_AMH"]) || (dashboardData.projectSubSelection && dashboardData.projectSubSelection.title) || "Sub-Project",
            description: truncate(firstRow.Description || firstRow.description || subProject.description || "Project sub-detail", 200),
            image: buildProxyMediaUrl(subProject.image || subProject.background_image) || pictures[0] || "",
            pictures: pictures,
            details: detailEntries,
            rowCount: dataRows.length,
            pictureCount: pictures.length,
        };

        dashboardData.kpis = [
            { label: "Sub-Project", value: dashboardData.projectSubDetail.title, delta: "Selected sub-project", position: "-1.45 1.95 -2.35" },
            { label: "Pictures", value: String(dashboardData.projectSubDetail.pictureCount), delta: "From project data", position: "0 2.08 -2.2" },
            { label: "Fields", value: String(dashboardData.projectSubDetail.details.length), delta: `${dashboardData.projectSubDetail.rowCount} data rows`, position: "1.45 1.95 -2.35" },
        ];
        dashboardData.notifications = [
            dashboardData.projectSubDetail.title,
            dashboardData.projectSubDetail.pictureCount ? `${dashboardData.projectSubDetail.pictureCount} pictures available` : "No pictures available",
            dashboardData.projectSubDetail.details[0] ? `${dashboardData.projectSubDetail.details[0].key}: ${dashboardData.projectSubDetail.details[0].value}` : "Structured detail fields are not available",
        ];
    }

    async function hydrateInitiativeCatalogSceneData() {
        if (dashboardData.sceneVariant !== "initiative-catalog" || dashboardData.__initiativeCatalogHydrated) {
            return;
        }

        dashboardData.__initiativeCatalogHydrated = true;
        const endpoints = dashboardData.dataEndpoints || {};
        const payload = endpoints.initiatives ? await fetchJson(endpoints.initiatives).catch(() => null) : null;
        const initiatives = Array.isArray(payload && payload.data) ? payload.data.slice(0, 14) : [];

        dashboardData.initiativeCatalog = initiatives.map((item) => ({
            id: item.id,
            title: pickLabel(item, ["title_ENG", "title_AMH"]) || "Initiative",
            description: truncate(item.description || "National initiative detail is available in the immersive view.", 120),
            categories: `${Number(item.count_category || 0)} categories`,
            kpis: `${Number(item.count_kpis || 0)} KPIs`,
            image: buildProxyMediaUrl(item.background_image || item.image),
            icon: buildProxyMediaUrl(item.image_icons || item.icon),
        }));

        dashboardData.kpis = [
            { label: "Initiatives", value: String(initiatives.length), delta: "Loaded into VR", position: "-1.45 1.95 -2.35" },
            { label: "Categories", value: String(initiatives.reduce((sum, item) => sum + Number(item && item.count_category || 0), 0)), delta: "Across initiatives", position: "0 2.08 -2.2" },
            { label: "KPIs", value: String(initiatives.reduce((sum, item) => sum + Number(item && item.count_kpis || 0), 0)), delta: "Across initiatives", position: "1.45 1.95 -2.35" },
        ];
        dashboardData.notifications = [
            initiatives[0] ? `Lead initiative: ${pickLabel(initiatives[0], ["title_ENG", "title_AMH"])}` : "No initiatives available",
            initiatives[1] ? `Next initiative: ${pickLabel(initiatives[1], ["title_ENG", "title_AMH"])}` : "Initiative cards are ready",
            "Open an initiative card to enter its detail room",
        ];
    }

    async function hydrateInitiativeDetailSceneData() {
        if (dashboardData.sceneVariant !== "initiative-detail" || dashboardData.__initiativeDetailHydrated) {
            return;
        }

        dashboardData.__initiativeDetailHydrated = true;
        const match = String(dashboardData.sourcePage && dashboardData.sourcePage.url || "").match(/\/dashboard\/projects\/initiatives\/(\d+)\/?/);
        const initiativeId = match ? match[1] : "";
        if (!initiativeId) {
            return;
        }

        const endpoints = dashboardData.dataEndpoints || {};
        const [detailPayload, listPayload] = await Promise.all([
            fetchJson(`${endpoints.initiativeDetailBase || "/api/mobile/initiative-detail/"}${initiativeId}/`).catch(() => null),
            endpoints.initiatives ? fetchJson(endpoints.initiatives).catch(() => null) : null,
        ]);

        const detail = detailPayload && detailPayload.data ? detailPayload.data : detailPayload || {};
        const initiatives = Array.isArray(listPayload && listPayload.data) ? listPayload.data : [];
        const listMatch = initiatives.find((item) => String(item && item.id) === String(initiativeId)) || {};
        const categoryCount = Number(detail.count_category || listMatch.count_category || 0);
        const kpiCount = Number(detail.count_kpis || listMatch.count_kpis || 0);

        dashboardData.initiativeDetail = {
            id: initiativeId,
            title: pickLabel(detail, ["title_ENG", "title_AMH"]) || pickLabel(listMatch, ["title_ENG", "title_AMH"]) || `Initiative ${initiativeId}`,
            description: truncate(detail.description || listMatch.description || "Explore this initiative in an immersive summary layout.", 220),
            image: buildProxyMediaUrl(
                detail.background_image ||
                detail.image ||
                listMatch.background_image ||
                listMatch.image
            ),
            icon: buildProxyMediaUrl(detail.image_icons || detail.icon || listMatch.image_icons || listMatch.icon),
            categoryCount,
            kpiCount,
        };

        dashboardData.initiativeDetailPanels = [
            {
                title: "Categories",
                value: String(categoryCount),
                accent: "#8ef1e5",
                subtitle: "Structured groups in this initiative",
            },
            {
                title: "Indicators",
                value: String(kpiCount),
                accent: "#7dd3fc",
                subtitle: "KPIs tracked across the initiative",
            },
            {
                title: "Focus",
                value: detail.is_dashboard || listMatch.is_dashboard ? "Dashboard" : "Overview",
                accent: "#fbbf24",
                subtitle: "Presentation mode from the source API",
            },
            {
                title: "Type",
                value: detail.is_initiative || listMatch.is_initiative ? "Initiative" : "Program",
                accent: "#f472b6",
                subtitle: "Time-series initiative record",
            },
        ];

        dashboardData.kpis = [
            { label: "Initiative", value: dashboardData.initiativeDetail.title, delta: "Selected initiative", position: "-1.45 1.95 -2.35" },
            { label: "Categories", value: String(categoryCount), delta: "Detail summary", position: "0 2.08 -2.2" },
            { label: "KPIs", value: String(kpiCount), delta: "Detail summary", position: "1.45 1.95 -2.35" },
        ];
        dashboardData.notifications = [
            dashboardData.initiativeDetail.title,
            categoryCount ? `${categoryCount} categories are linked to this initiative` : "No category count is available",
            kpiCount ? `${kpiCount} KPIs are linked to this initiative` : "No KPI count is available",
        ];
    }

    async function hydratePolicyAreaCatalogSceneData() {
        if (dashboardData.sceneVariant !== "policy-area-catalog" || dashboardData.__policyAreaCatalogHydrated) {
            return;
        }

        dashboardData.__policyAreaCatalogHydrated = true;
        const endpoints = dashboardData.dataEndpoints || {};
        const state = getDpmesState();
        const params = new URLSearchParams({ year: state.year });
        if (state.dateType === "quarterly") {
            params.set("quarter", state.quarter);
        }

        const payload = endpoints.policyAreas
            ? await fetchJson(`${endpoints.policyAreas}?${params.toString()}`).catch(() => null)
            : null;
        const areas = Array.isArray(payload && payload.data) ? payload.data.slice(0, 12) : [];
        dashboardData.policyAreaCatalog = areas.map((area) => {
            const scoreCard = area && area.policy_area_score_card || {};
            const goalCount = Number(area && area.count_goal || 0);
            return {
                id: area.id,
                title: pickLabel(area, ["policyAreaEng", "policyAreaAmh"]) || "Policy Area",
                score: formatPercent(scoreCard.avg_score),
                color: scoreCard.scorecard_color || "#5d9444",
                goals: `${goalCount} goals`,
                subtitle: state.dateType === "quarterly" ? `${state.year} ${state.quarter}` : state.year,
                image: buildProxyMediaUrl(area && area.bg_image),
            };
        });
        dashboardData.kpis = [
            { label: "Policy Areas", value: String(areas.length), delta: "Loaded into VR", position: "-1.45 1.95 -2.35" },
            {
                label: "Goals",
                value: String(areas.reduce((sum, item) => sum + Number(item && item.count_goal || 0), 0)),
                delta: "Across listed areas",
                position: "0 2.08 -2.2",
            },
            { label: "Period", value: state.year, delta: state.dateType === "quarterly" ? state.quarter : "yearly", position: "1.45 1.95 -2.35" },
        ];
        dashboardData.notifications = [
            areas[0] ? `Lead policy area: ${pickLabel(areas[0], ["policyAreaEng", "policyAreaAmh"])}` : "No policy areas available",
            areas[1] ? `Next policy area: ${pickLabel(areas[1], ["policyAreaEng", "policyAreaAmh"])}` : "Policy area cards are ready",
            "Open a policy area card to inspect its goals",
        ];
    }

    async function hydratePolicyAreaDetailSceneData() {
        if (dashboardData.sceneVariant !== "policy-area-detail" || dashboardData.__policyAreaDetailHydrated) {
            return;
        }

        dashboardData.__policyAreaDetailHydrated = true;
        const match = String(dashboardData.sourcePage && dashboardData.sourcePage.url || "").match(/\/dashboard\/statistics\/policy-areas\/(\d+)\/?/);
        const policyAreaId = match ? match[1] : "";
        if (!policyAreaId) {
            return;
        }

        const endpoints = dashboardData.dataEndpoints || {};
        const state = getDpmesState();
        const params = new URLSearchParams({ year: state.year });
        if (state.dateType === "quarterly") {
            params.set("quarter", state.quarter);
        }

        const [overviewPayload, detailPayload] = await Promise.all([
            endpoints.policyAreas ? fetchJson(`${endpoints.policyAreas}?${params.toString()}`).catch(() => null) : null,
            fetchJson(`${endpoints.policyAreaDetailBase || "/api/mobile/policy-area-detail/"}${policyAreaId}/?${params.toString()}`).catch(() => null),
        ]);

        const overviewItems = Array.isArray(overviewPayload && overviewPayload.data) ? overviewPayload.data : [];
        const overview = overviewItems.find((item) => String(item && item.id) === String(policyAreaId)) || {};
        const detail = detailPayload && detailPayload.data ? detailPayload.data : detailPayload || {};
        const goals = Array.isArray(detail && detail.policy_area_goal) ? detail.policy_area_goal : [];
        const scoreCard = overview.policy_area_score_card || detail.policy_area_score_card || {};

        dashboardData.policyAreaDetail = {
            id: policyAreaId,
            title: pickLabel(overview, ["policyAreaEng", "policyAreaAmh"]) || pickLabel(detail, ["policyAreaEng", "policyAreaAmh"]) || "Policy Area",
            score: formatPercent(scoreCard.avg_score),
            color: scoreCard.scorecard_color || "#5d9444",
            periodLabel: state.dateType === "quarterly" ? `${state.year} ${state.quarter}` : state.year,
            image: buildProxyMediaUrl(overview.bg_image || detail.bg_image),
        };
        dashboardData.policyAreaGoals = goals.map((goal) => {
            const score = goal && goal.goal_score_card ? goal.goal_score_card.avg_score : null;
            const goalIndicators = Array.isArray(goal && goal.kra_goal)
                ? goal.kra_goal.reduce((sum, kra) => sum + (Array.isArray(kra && kra.indicators) ? kra.indicators.length : 0), 0)
                : 0;
            return {
                id: goal.id,
                title: pickLabel(goal, ["goal_name_eng", "goal_name_amh"]) || "Goal",
                score: formatPercent(score),
                color: goal && goal.goal_score_card ? goal.goal_score_card.scorecard_color || "#5d9444" : "#5d9444",
                kras: `${Array.isArray(goal && goal.kra_goal) ? goal.kra_goal.length : 0} KRAs`,
                indicators: `${goalIndicators} indicators`,
            };
        });
        dashboardData.kpis = [
            { label: "Goals", value: String(goals.length), delta: dashboardData.policyAreaDetail.title, position: "-1.45 1.95 -2.35" },
            { label: "Score", value: dashboardData.policyAreaDetail.score, delta: dashboardData.policyAreaDetail.periodLabel, position: "0 2.08 -2.2" },
            { label: "Period", value: state.year, delta: state.dateType === "quarterly" ? state.quarter : "yearly", position: "1.45 1.95 -2.35" },
        ];
        dashboardData.notifications = [
            goals[0] ? `Lead goal: ${pickLabel(goals[0], ["goal_name_eng", "goal_name_amh"])}` : "No goals available",
            goals[1] ? `Next goal: ${pickLabel(goals[1], ["goal_name_eng", "goal_name_amh"])}` : "Goal cards are ready",
            "Open a goal card to inspect key result areas",
        ];
    }

    async function hydratePolicyGoalDetailSceneData() {
        if (dashboardData.sceneVariant !== "policy-goal-detail" || dashboardData.__policyGoalDetailHydrated) {
            return;
        }

        dashboardData.__policyGoalDetailHydrated = true;
        const match = String(dashboardData.sourcePage && dashboardData.sourcePage.url || "").match(/\/dashboard\/statistics\/goals\/(\d+)\/?/);
        const goalId = match ? match[1] : "";
        if (!goalId) {
            return;
        }

        const endpoints = dashboardData.dataEndpoints || {};
        const state = getDpmesState();
        const params = new URLSearchParams({ year: state.year });
        if (state.dateType === "quarterly") {
            params.set("quarter", state.quarter);
        }

        const payload = await fetchJson(`${endpoints.goalDetailBase || "/api/mobile/goal-detail/"}${goalId}/?${params.toString()}`).catch(() => null);
        const detail = payload && payload.data ? payload.data : payload || {};
        const kras = Array.isArray(detail && detail.kra_goal) ? detail.kra_goal : [];
        const goalScoreCard = detail.goal_score_card || detail.ministry_strategic_goal_score_card || {};
        const indicatorCount = kras.reduce((sum, kra) => sum + (Array.isArray(kra && kra.indicators) ? kra.indicators.length : 0), 0);

        dashboardData.policyGoalDetail = {
            id: goalId,
            title: pickLabel(detail, ["goal_name_eng", "goal_name_amh"]) || "Goal",
            score: formatPercent(goalScoreCard.avg_score),
            color: goalScoreCard.scorecard_color || "#5d9444",
            periodLabel: state.dateType === "quarterly" ? `${state.year} ${state.quarter}` : state.year,
        };
        dashboardData.policyGoalKras = kras.map((kra) => {
            const indicators = Array.isArray(kra && kra.indicators) ? kra.indicators : [];
            const scoreCard = kra && (kra.kra_score_card || kra.ministry_key_result_area_score_card) || {};
            return {
                id: kra.id,
                title: pickLabel(kra, ["activity_name_eng", "activity_name_amh"]) || "Key Result Area",
                score: formatPercent(scoreCard.avg_score),
                color: scoreCard.scorecard_color || "#5d9444",
                indicators: `${indicators.length} indicators`,
                period: dashboardData.policyGoalDetail.periodLabel,
            };
        });
        dashboardData.kpis = [
            { label: "KRAs", value: String(kras.length), delta: dashboardData.policyGoalDetail.title, position: "-1.45 1.95 -2.35" },
            { label: "Indicators", value: String(indicatorCount), delta: dashboardData.policyGoalDetail.score, position: "0 2.08 -2.2" },
            { label: "Period", value: state.year, delta: state.dateType === "quarterly" ? state.quarter : "yearly", position: "1.45 1.95 -2.35" },
        ];
        dashboardData.notifications = [
            kras[0] ? `Lead KRA: ${pickLabel(kras[0], ["activity_name_eng", "activity_name_amh"])}` : "No KRAs available",
            kras[1] ? `Next KRA: ${pickLabel(kras[1], ["activity_name_eng", "activity_name_amh"])}` : "KRA cards are ready",
            "Open a KRA card to inspect indicators with recent 5 records",
        ];
    }

    async function hydratePolicyKraDetailSceneData() {
        if (dashboardData.sceneVariant !== "policy-kra-detail" || dashboardData.__policyKraDetailHydrated) {
            return;
        }

        dashboardData.__policyKraDetailHydrated = true;
        const match = String(dashboardData.sourcePage && dashboardData.sourcePage.url || "").match(/\/dashboard\/statistics\/goals\/(\d+)\/?/);
        const goalId = match ? match[1] : "";
        const kraId = String(dashboardData.kraSelection && dashboardData.kraSelection.id || "");
        if (!goalId || !kraId) {
            return;
        }

        const endpoints = dashboardData.dataEndpoints || {};
        const state = getDpmesState();
        const params = new URLSearchParams({ year: state.year });
        if (state.dateType === "quarterly") {
            params.set("quarter", state.quarter);
        }

        const payload = await fetchJson(`${endpoints.goalDetailBase || "/api/mobile/goal-detail/"}${goalId}/?${params.toString()}`).catch(() => null);
        const detail = payload && payload.data ? payload.data : payload || {};
        const kras = Array.isArray(detail && detail.kra_goal) ? detail.kra_goal : [];
        const kra = kras.find((item) => String(item && item.id) === kraId) || {};
        const indicators = (Array.isArray(kra && kra.indicators) ? kra.indicators : []).map((indicator) => {
            const latestRecord = getDpmesLatestIndicatorRecord(indicator, state);
            return {
                id: indicator.id,
                title: pickLabel(indicator, ["kpi_name_eng", "kpi_name_amh"]) || "Indicator",
                latestValue: latestRecord
                    ? formatValue(state.dateType === "quarterly" ? latestRecord.quarter_performance : latestRecord.annual_performance)
                    : "--",
                unit: latestRecord ? formatPercent(latestRecord.score) : "--",
                points: getDpmesRecentIndicatorPoints(indicator, state, 5),
            };
        });

        dashboardData.policyKraDetail = {
            id: kraId,
            title: pickLabel(kra, ["activity_name_eng", "activity_name_amh"]) || (dashboardData.kraSelection && dashboardData.kraSelection.title) || "Key Result Area",
            goalTitle: pickLabel(detail, ["goal_name_eng", "goal_name_amh"]) || "Goal",
            periodLabel: state.dateType === "quarterly" ? `${state.year} ${state.quarter}` : state.year,
            indicators: indicators,
        };
        dashboardData.kpis = [
            { label: "KRA", value: dashboardData.policyKraDetail.title, delta: dashboardData.policyKraDetail.goalTitle, position: "-1.45 1.95 -2.35" },
            { label: "Indicators", value: String(indicators.length), delta: dashboardData.policyKraDetail.periodLabel, position: "0 2.08 -2.2" },
            { label: "Goal", value: dashboardData.policyKraDetail.goalTitle, delta: "Recent 5", position: "1.45 1.95 -2.35" },
        ];
        dashboardData.notifications = [
            indicators[0] ? `Lead indicator: ${indicators[0].title}` : "No indicators available",
            indicators[1] ? `Next indicator: ${indicators[1].title}` : "Indicator cards are ready",
            "Indicator cards use recent 5 records from the goal detail payload",
        ];
    }

    async function hydrateMinistryCatalogSceneData() {
        if (dashboardData.sceneVariant !== "ministry-catalog" || dashboardData.__ministryCatalogHydrated) {
            return;
        }

        dashboardData.__ministryCatalogHydrated = true;
        const endpoints = dashboardData.dataEndpoints || {};
        const state = getDpmesState();
        const params = new URLSearchParams({ year: state.year });
        if (state.dateType === "quarterly") {
            params.set("quarter", state.quarter);
        }

        const payload = endpoints.dpmesMinistries
            ? await fetchJson(`${endpoints.dpmesMinistries}?${params.toString()}`).catch(() => null)
            : null;
        const ministries = Array.isArray(payload && payload.data)
            ? payload.data.filter((item) => item && item.ministry_is_visable).slice(0, 12)
            : [];
        dashboardData.ministryCatalog = ministries.map((item) => {
            const scoreCard = item && item.ministry_score_card || {};
            return {
                id: item.id,
                title: pickLabel(item, ["responsible_ministry_eng", "responsible_ministry_amh"]) || "Ministry",
                code: pickLabel(item, ["code"]) || "MO",
                score: formatPercent(scoreCard.avg_score),
                color: scoreCard.scorecard_color || "#5d9444",
                indicators: `${Number(item && item.count_indicator || 0)} indicators`,
                image: buildProxyMediaUrl(item && (item.background_image || item.image)),
            };
        });
        dashboardData.kpis = [
            { label: "Ministries", value: String(ministries.length), delta: "Loaded into VR", position: "-1.45 1.95 -2.35" },
            {
                label: "Indicators",
                value: String(ministries.reduce((sum, item) => sum + Number(item && item.count_indicator || 0), 0)),
                delta: "Across listed ministries",
                position: "0 2.08 -2.2",
            },
            { label: "Period", value: state.year, delta: state.dateType === "quarterly" ? state.quarter : "yearly", position: "1.45 1.95 -2.35" },
        ];
        dashboardData.notifications = [
            ministries[0] ? `Lead ministry: ${pickLabel(ministries[0], ["responsible_ministry_eng", "responsible_ministry_amh"])}` : "No ministries available",
            ministries[1] ? `Next ministry: ${pickLabel(ministries[1], ["responsible_ministry_eng", "responsible_ministry_amh"])}` : "Ministry cards are ready",
            "Open a ministry card to inspect goals",
        ];
    }

    async function hydrateMinistryDetailSceneData() {
        if (dashboardData.sceneVariant !== "ministry-detail" || dashboardData.__ministryDetailHydrated) {
            return;
        }

        dashboardData.__ministryDetailHydrated = true;
        const match = String(dashboardData.sourcePage && dashboardData.sourcePage.url || "").match(/\/dashboard\/statistics\/public-bodies\/(\d+)\/?/);
        const ministryId = match ? match[1] : "";
        if (!ministryId) {
            return;
        }

        const endpoints = dashboardData.dataEndpoints || {};
        const state = getDpmesState();
        const params = new URLSearchParams({ year: state.year });
        if (state.dateType === "quarterly") {
            params.set("quarter", state.quarter);
        }

        const [overviewPayload, detailPayload] = await Promise.all([
            endpoints.dpmesMinistries ? fetchJson(`${endpoints.dpmesMinistries}?${params.toString()}`).catch(() => null) : null,
            fetchJson(`${endpoints.ministryDetailBase || "/api/mobile/ministry-detail/"}${ministryId}/?${params.toString()}`).catch(() => null),
        ]);

        const overviewItems = Array.isArray(overviewPayload && overviewPayload.data) ? overviewPayload.data : [];
        const overview = overviewItems.find((item) => String(item && item.id) === String(ministryId)) || {};
        const detailItems = Array.isArray(detailPayload && detailPayload.data) ? detailPayload.data : [];
        const goals = detailItems.flatMap((item) => {
            const policyAreaTitle = pickLabel(item, ["policyAreaEng", "policyAreaAmh"]) || "Policy Area";
            return (Array.isArray(item && item.policy_area_goal) ? item.policy_area_goal : []).map((goal) => ({
                ...goal,
                __policyAreaTitle: policyAreaTitle,
            }));
        });
        const scoreCard = overview.ministry_score_card || {};

        dashboardData.ministryDetail = {
            id: ministryId,
            title: pickLabel(overview, ["responsible_ministry_eng", "responsible_ministry_amh"]) || "Ministry",
            code: pickLabel(overview, ["code"]) || "MO",
            score: formatPercent(scoreCard.avg_score),
            color: scoreCard.scorecard_color || "#5d9444",
            periodLabel: state.dateType === "quarterly" ? `${state.year} ${state.quarter}` : state.year,
            image: buildProxyMediaUrl(overview.background_image || overview.image),
        };
        dashboardData.ministryGoals = goals.map((goal) => {
            const scoreCard = goal && goal.ministry_strategic_goal_score_card || {};
            const indicators = Array.isArray(goal && goal.kra_goal)
                ? goal.kra_goal.reduce((sum, kra) => sum + (Array.isArray(kra && kra.indicators) ? kra.indicators.length : 0), 0)
                : 0;
            return {
                id: goal.id,
                title: pickLabel(goal, ["goal_name_eng", "goal_name_amh"]) || "Goal",
                policyArea: goal.__policyAreaTitle,
                score: formatPercent(scoreCard.avg_score),
                color: scoreCard.scorecard_color || "#5d9444",
                kras: `${Array.isArray(goal && goal.kra_goal) ? goal.kra_goal.length : 0} KRAs`,
                indicators: `${indicators} indicators`,
            };
        });
        dashboardData.kpis = [
            { label: "Goals", value: String(goals.length), delta: dashboardData.ministryDetail.title, position: "-1.45 1.95 -2.35" },
            { label: "Score", value: dashboardData.ministryDetail.score, delta: dashboardData.ministryDetail.periodLabel, position: "0 2.08 -2.2" },
            { label: "Indicators", value: String(goals.reduce((sum, goal) => sum + (Array.isArray(goal && goal.kra_goal) ? goal.kra_goal.reduce((acc, kra) => acc + (Array.isArray(kra && kra.indicators) ? kra.indicators.length : 0), 0) : 0), 0)), delta: dashboardData.ministryDetail.code, position: "1.45 1.95 -2.35" },
        ];
        dashboardData.notifications = [
            goals[0] ? `Lead goal: ${pickLabel(goals[0], ["goal_name_eng", "goal_name_amh"])}` : "No goals available",
            goals[1] ? `Next goal: ${pickLabel(goals[1], ["goal_name_eng", "goal_name_amh"])}` : "Goal cards are ready",
            "Open a goal to inspect ministry key result areas",
        ];
    }

    async function hydrateMinistryGoalDetailSceneData() {
        if (dashboardData.sceneVariant !== "ministry-goal-detail" || dashboardData.__ministryGoalDetailHydrated) {
            return;
        }

        dashboardData.__ministryGoalDetailHydrated = true;
        const match = String(dashboardData.sourcePage && dashboardData.sourcePage.url || "").match(/\/dashboard\/statistics\/goals\/(\d+)\/?/);
        const goalId = match ? match[1] : "";
        const state = getDpmesState();
        const ministryId = getSourceQueryParams().get("ministry_id") || "";
        if (!goalId || !ministryId) {
            return;
        }

        const endpoints = dashboardData.dataEndpoints || {};
        const params = new URLSearchParams({ ministry_id: ministryId, year: state.year });
        if (state.dateType === "quarterly") {
            params.set("quarter", state.quarter);
        }

        const payload = await fetchJson(`${endpoints.ministryGoalDetailBase || "/api/mobile/ministry-goal-detail/"}${goalId}/?${params.toString()}`).catch(() => null);
        const detail = payload && payload.data ? payload.data : payload || {};
        const kras = Array.isArray(detail && detail.kra_goal) ? detail.kra_goal : [];
        const scoreCard = detail.ministry_strategic_goal_score_card || detail.goal_score_card || {};
        const indicatorCount = kras.reduce((sum, kra) => sum + (Array.isArray(kra && kra.indicators) ? kra.indicators.length : 0), 0);

        dashboardData.ministryGoalDetail = {
            id: goalId,
            title: pickLabel(detail, ["goal_name_eng", "goal_name_amh"]) || "Goal",
            score: formatPercent(scoreCard.avg_score),
            color: scoreCard.scorecard_color || "#5d9444",
            periodLabel: state.dateType === "quarterly" ? `${state.year} ${state.quarter}` : state.year,
        };
        dashboardData.ministryGoalKras = kras.map((kra) => {
            const indicators = Array.isArray(kra && kra.indicators) ? kra.indicators : [];
            const scoreCard = kra && (kra.ministry_key_result_area_score_card || kra.kra_score_card) || {};
            return {
                id: kra.id,
                title: pickLabel(kra, ["activity_name_eng", "activity_name_amh"]) || "Key Result Area",
                score: formatPercent(scoreCard.avg_score),
                color: scoreCard.scorecard_color || "#5d9444",
                indicators: `${indicators.length} indicators`,
                period: dashboardData.ministryGoalDetail.periodLabel,
            };
        });
        dashboardData.kpis = [
            { label: "KRAs", value: String(kras.length), delta: dashboardData.ministryGoalDetail.title, position: "-1.45 1.95 -2.35" },
            { label: "Indicators", value: String(indicatorCount), delta: dashboardData.ministryGoalDetail.score, position: "0 2.08 -2.2" },
            { label: "Period", value: state.year, delta: state.dateType === "quarterly" ? state.quarter : "yearly", position: "1.45 1.95 -2.35" },
        ];
        dashboardData.notifications = [
            kras[0] ? `Lead KRA: ${pickLabel(kras[0], ["activity_name_eng", "activity_name_amh"])}` : "No KRAs available",
            kras[1] ? `Next KRA: ${pickLabel(kras[1], ["activity_name_eng", "activity_name_amh"])}` : "KRA cards are ready",
            "Open a KRA to inspect ministry indicators with recent 5 records",
        ];
    }

    async function hydrateMinistryKraDetailSceneData() {
        if (dashboardData.sceneVariant !== "ministry-kra-detail" || dashboardData.__ministryKraDetailHydrated) {
            return;
        }

        dashboardData.__ministryKraDetailHydrated = true;
        const match = String(dashboardData.sourcePage && dashboardData.sourcePage.url || "").match(/\/dashboard\/statistics\/goals\/(\d+)\/?/);
        const goalId = match ? match[1] : "";
        const kraId = String(dashboardData.kraSelection && dashboardData.kraSelection.id || "");
        const state = getDpmesState();
        const ministryId = getSourceQueryParams().get("ministry_id") || "";
        if (!goalId || !kraId || !ministryId) {
            return;
        }

        const endpoints = dashboardData.dataEndpoints || {};
        const params = new URLSearchParams({ ministry_id: ministryId, year: state.year });
        if (state.dateType === "quarterly") {
            params.set("quarter", state.quarter);
        }

        const payload = await fetchJson(`${endpoints.ministryGoalDetailBase || "/api/mobile/ministry-goal-detail/"}${goalId}/?${params.toString()}`).catch(() => null);
        const detail = payload && payload.data ? payload.data : payload || {};
        const kras = Array.isArray(detail && detail.kra_goal) ? detail.kra_goal : [];
        const kra = kras.find((item) => String(item && item.id) === kraId) || {};
        const indicators = (Array.isArray(kra && kra.indicators) ? kra.indicators : []).map((indicator) => {
            const latestRecord = getDpmesLatestIndicatorRecord(indicator, state);
            return {
                id: indicator.id,
                title: pickLabel(indicator, ["kpi_name_eng", "kpi_name_amh"]) || "Indicator",
                latestValue: latestRecord
                    ? formatValue(state.dateType === "quarterly" ? latestRecord.quarter_performance : latestRecord.annual_performance)
                    : "--",
                unit: latestRecord ? formatPercent(latestRecord.score) : "--",
                points: getDpmesRecentIndicatorPoints(indicator, state, 5),
            };
        });

        dashboardData.ministryKraDetail = {
            id: kraId,
            title: pickLabel(kra, ["activity_name_eng", "activity_name_amh"]) || (dashboardData.kraSelection && dashboardData.kraSelection.title) || "Key Result Area",
            goalTitle: pickLabel(detail, ["goal_name_eng", "goal_name_amh"]) || "Goal",
            periodLabel: state.dateType === "quarterly" ? `${state.year} ${state.quarter}` : state.year,
            indicators: indicators,
        };
        dashboardData.kpis = [
            { label: "KRA", value: dashboardData.ministryKraDetail.title, delta: dashboardData.ministryKraDetail.goalTitle, position: "-1.45 1.95 -2.35" },
            { label: "Indicators", value: String(indicators.length), delta: dashboardData.ministryKraDetail.periodLabel, position: "0 2.08 -2.2" },
            { label: "Goal", value: dashboardData.ministryKraDetail.goalTitle, delta: "Recent 5", position: "1.45 1.95 -2.35" },
        ];
        dashboardData.notifications = [
            indicators[0] ? `Lead indicator: ${indicators[0].title}` : "No indicators available",
            indicators[1] ? `Next indicator: ${indicators[1].title}` : "Indicator cards are ready",
            "Indicator cards use recent 5 records from the ministry goal payload",
        ];
    }

    async function checkXRSupport() {
        if (!navigator.xr) {
            statusNode.textContent = "WebXR unavailable in this browser. Desktop 3D preview is loading.";
            enterVrButton.disabled = true;
            return;
        }

        try {
            const supported = await navigator.xr.isSessionSupported("immersive-vr");
            statusNode.textContent = supported
                ? "WebXR immersive VR is available. Quest, Vive, and Chrome-compatible headsets can enter XR."
                : "WebXR detected, but immersive VR is not available on this device. Desktop 3D preview is loading.";
            enterVrButton.disabled = !supported;
        } catch (error) {
            statusNode.textContent = "WebXR check failed. Desktop 3D preview is loading instead.";
            enterVrButton.disabled = true;
            console.error(error);
        }
    }

    function loadScript(src) {
        return new Promise((resolve, reject) => {
            const existing = document.querySelector(`script[src="${src}"]`);
            if (existing) {
                if (existing.dataset.loaded === "true") {
                    resolve();
                    return;
                }

                existing.addEventListener("load", resolve, { once: true });
                existing.addEventListener("error", reject, { once: true });
                return;
            }

            const script = document.createElement("script");
            script.src = src;
            script.async = true;
            script.addEventListener("load", () => {
                script.dataset.loaded = "true";
                resolve();
            }, { once: true });
            script.addEventListener("error", reject, { once: true });
            document.head.appendChild(script);
        });
    }

    async function ensureAFrame() {
        if (aframeReady) {
            return;
        }

        await loadScript("https://aframe.io/releases/1.7.0/aframe.min.js");
        registerComponents();
        aframeReady = true;
    }

    function registerComponents() {
        if (!window.AFRAME || AFRAME.components["draggable-panel"]) {
            return;
        }

        AFRAME.registerComponent("draggable-panel", {
            schema: {
                distance: { default: 0.7 },
            },
            init: function () {
                this.isGrabbed = false;
                this.grabber = null;
                this.offset = new AFRAME.THREE.Vector3();
                this.onGrabStart = this.onGrabStart.bind(this);
                this.onGrabEnd = this.onGrabEnd.bind(this);
                this.el.classList.add("interactive");
                this.el.addEventListener("grab-start", this.onGrabStart);
                this.el.addEventListener("grab-end", this.onGrabEnd);
            },
            tick: function () {
                if (!this.isGrabbed || !this.grabber) {
                    return;
                }

                const direction = new AFRAME.THREE.Vector3();
                const worldTarget = new AFRAME.THREE.Vector3();
                this.grabber.object3D.getWorldDirection(direction);
                this.grabber.object3D.getWorldPosition(worldTarget);
                worldTarget.add(direction.multiplyScalar(-this.data.distance));
                const localTarget = this.el.object3D.parent.worldToLocal(worldTarget);
                localTarget.add(this.offset);
                this.el.object3D.position.lerp(localTarget, 0.3);
            },
            onGrabStart: function (event) {
                const hand = event.detail && event.detail.hand;
                if (!hand) {
                    return;
                }

                this.isGrabbed = true;
                this.grabber = hand;
                const handWorld = new AFRAME.THREE.Vector3();
                const panelWorld = new AFRAME.THREE.Vector3();
                hand.object3D.getWorldPosition(handWorld);
                this.el.object3D.getWorldPosition(panelWorld);
                this.offset.copy(panelWorld.sub(handWorld).multiplyScalar(0.18));
            },
            onGrabEnd: function () {
                this.isGrabbed = false;
                this.grabber = null;
                this.offset.set(0, 0, 0);
            },
        });

        AFRAME.registerComponent("xr-pointer", {
            init: function () {
                this.grabbedEl = null;
                this.startGrab = this.startGrab.bind(this);
                this.endGrab = this.endGrab.bind(this);
                this.el.addEventListener("triggerdown", this.startGrab);
                this.el.addEventListener("triggerup", this.endGrab);
                this.el.addEventListener("pinchstarted", this.startGrab);
                this.el.addEventListener("pinchended", this.endGrab);
            },
            startGrab: function () {
                const raycaster = this.el.components.raycaster;
                if (!raycaster || !raycaster.intersections.length) {
                    return;
                }

                const hit = raycaster.intersections[0].object.el;
                if (!hit || !hit.components["draggable-panel"]) {
                    return;
                }

                this.grabbedEl = hit;
                hit.emit("grab-start", { hand: this.el });
            },
            endGrab: function () {
                if (!this.grabbedEl) {
                    return;
                }

                this.grabbedEl.emit("grab-end", { hand: this.el });
                this.grabbedEl = null;
            },
        });

        AFRAME.registerComponent("menu-action", {
            schema: { label: { default: "" } },
            init: function () {
                this.defaultColor = "#10202f";
                this.hoverColor = "#1d6fa2";
                this.el.addEventListener("mouseenter", () => {
                    this.el.setAttribute("material", "color", this.hoverColor);
                });
                this.el.addEventListener("mouseleave", () => {
                    this.el.setAttribute("material", "color", this.defaultColor);
                });
                this.el.addEventListener("click", () => {
                    const title = document.querySelector("#active-menu-title");
                    if (title) {
                        title.setAttribute("value", this.data.label);
                    }
                });
            },
        });

        AFRAME.registerComponent("page-link", {
            schema: {
                url: { default: "" },
                title: { default: "" },
                target: { default: "vr" },
                categoryId: { default: "" },
            },
            init: function () {
                this.el.addEventListener("mouseenter", () => {
                    if (this.el.hasAttribute("material")) {
                        this.el.setAttribute("material", "color", "#1d6fa2");
                    }
                });
                this.el.addEventListener("mouseleave", () => {
                    if (this.el.hasAttribute("material")) {
                        this.el.setAttribute("material", "color", "#112638");
                    }
                });
                this.el.addEventListener("click", () => {
                    if (this.data.target === "page") {
                        window.location.href = this.data.url;
                        return;
                    }
                    if (this.data.target === "vr-category") {
                        const params = new URLSearchParams({
                            source: this.data.url,
                            title: this.data.title,
                            category: this.data.categoryId,
                            category_title: this.data.title,
                        });
                        window.location.href = `/dashboard/vr/?${params.toString()}`;
                        return;
                    }
                    if (this.data.target === "vr-kra") {
                        const params = new URLSearchParams({
                            source: this.data.url,
                            title: this.data.title,
                            kra: this.data.categoryId,
                            kra_title: this.data.title,
                        });
                        window.location.href = `/dashboard/vr/?${params.toString()}`;
                        return;
                    }
                    if (this.data.target === "vr-project-sub") {
                        const params = new URLSearchParams({
                            source: this.data.url,
                            title: this.data.title,
                            project_sub: this.data.categoryId,
                            project_sub_title: this.data.title,
                        });
                        window.location.href = `/dashboard/vr/?${params.toString()}`;
                        return;
                    }
                    const params = new URLSearchParams({
                        source: this.data.url,
                        title: this.data.title,
                    });
                    window.location.href = `/dashboard/vr/?${params.toString()}`;
                });
            },
        });

        AFRAME.registerComponent("nav-action", {
            schema: {
                action: { default: "back" },
            },
            init: function () {
                this.el.addEventListener("mouseenter", () => {
                    if (this.el.hasAttribute("material")) {
                        this.el.setAttribute("material", "color", "#1d6fa2");
                    }
                });
                this.el.addEventListener("mouseleave", () => {
                    if (this.el.hasAttribute("material")) {
                        this.el.setAttribute("material", "color", "#112638");
                    }
                });
                this.el.addEventListener("click", () => {
                    if (this.data.action === "back") {
                        window.history.back();
                    }
                });
            },
        });

        AFRAME.registerComponent("gesture-scroll", {
            init: function () {
                this.target = null;
                this.lastY = null;
                this.el.addEventListener("pinchstarted", (event) => {
                    this.target = document.querySelector("#notifications-rig");
                    this.lastY = event.detail.position.y;
                });
                this.el.addEventListener("pinchmoved", (event) => {
                    if (!this.target || this.lastY === null) {
                        return;
                    }

                    const delta = event.detail.position.y - this.lastY;
                    this.lastY = event.detail.position.y;
                    const position = this.target.getAttribute("position");
                    const nextY = Math.min(1.85, Math.max(0.75, position.y + delta * 1.45));
                    this.target.setAttribute("position", `${position.x} ${nextY.toFixed(3)} ${position.z}`);
                });
                this.el.addEventListener("pinchended", () => {
                    this.lastY = null;
                });
            },
        });

        AFRAME.registerComponent("hologram-pulse", {
            tick: function (time) {
                const opacity = 0.48 + Math.sin(time / 280) * 0.14;
                this.el.setAttribute("material", "opacity", opacity);
            },
        });
    }

    function buildSceneMarkup() {
        const isHomeScene = dashboardData.sceneVariant === "dashboard-home";
        const isDataCatalogScene = dashboardData.sceneVariant === "data-catalog";
        const isTopicDetailScene = dashboardData.sceneVariant === "data-topic-detail";
        const isCategoryDetailScene = dashboardData.sceneVariant === "data-category-detail";
        const isPolicyAreaCatalogScene = dashboardData.sceneVariant === "policy-area-catalog";
        const isPolicyAreaDetailScene = dashboardData.sceneVariant === "policy-area-detail";
        const isPolicyGoalDetailScene = dashboardData.sceneVariant === "policy-goal-detail";
        const isPolicyKraDetailScene = dashboardData.sceneVariant === "policy-kra-detail";
        const isMinistryCatalogScene = dashboardData.sceneVariant === "ministry-catalog";
        const isMinistryDetailScene = dashboardData.sceneVariant === "ministry-detail";
        const isMinistryGoalDetailScene = dashboardData.sceneVariant === "ministry-goal-detail";
        const isMinistryKraDetailScene = dashboardData.sceneVariant === "ministry-kra-detail";
        const isProjectCatalogScene = dashboardData.sceneVariant === "project-catalog";
        const isProjectDetailScene = dashboardData.sceneVariant === "project-detail";
        const isInitiativeCatalogScene = dashboardData.sceneVariant === "initiative-catalog";
        const isInitiativeDetailScene = dashboardData.sceneVariant === "initiative-detail";
        const isProjectSubDetailScene = dashboardData.sceneVariant === "project-sub-detail";
        const sourceParams = getSourceQueryParams();
        let backLink = null;
        if (isDataCatalogScene) {
            backLink = { url: "/dashboard/", title: "Dashboard Home", target: "vr" };
        } else if (isTopicDetailScene) {
            backLink = { url: "/dashboard/data/", title: "Data Catalog", target: "vr" };
        } else if (isCategoryDetailScene) {
            const topicUrl = `/dashboard/data/${dashboardData.topicDetail ? dashboardData.topicDetail.id : String((dashboardData.sourcePage && dashboardData.sourcePage.url || "").match(/\/dashboard\/data\/(\d+)\/?$/)?.[1] || "")}/`;
            backLink = { url: topicUrl, title: dashboardData.topicDetail ? dashboardData.topicDetail.title : "Topic Detail", target: "vr" };
        } else if (isPolicyAreaCatalogScene) {
            backLink = { url: "/dashboard/", title: "Dashboard Home", target: "vr" };
        } else if (isPolicyAreaDetailScene) {
            backLink = { url: `/dashboard/statistics/policy-areas/?year=${encodeURIComponent(getDpmesState().year)}&quarter=${encodeURIComponent(getDpmesState().quarter)}`, title: "Policy Areas", target: "vr" };
        } else if (isPolicyGoalDetailScene) {
            const match = String(dashboardData.sourcePage && dashboardData.sourcePage.url || "").match(/\/dashboard\/statistics\/goals\/(\d+)\/?/);
            backLink = { url: sourceParams.get("policy_area_id") ? `/dashboard/statistics/policy-areas/${sourceParams.get("policy_area_id")}/?year=${encodeURIComponent(getDpmesState().year)}&quarter=${encodeURIComponent(getDpmesState().quarter)}` : "/dashboard/statistics/policy-areas/?year=2018&quarter=3month", title: "Policy Area Detail", target: "vr" };
        } else if (isPolicyKraDetailScene) {
            backLink = { url: dashboardData.sourcePage && dashboardData.sourcePage.url || "/dashboard/statistics/goals/1/", title: dashboardData.sourcePage && dashboardData.sourcePage.title || "Goal Detail", target: "vr" };
        } else if (isMinistryCatalogScene) {
            backLink = { url: "/dashboard/", title: "Dashboard Home", target: "vr" };
        } else if (isMinistryDetailScene) {
            backLink = { url: `/dashboard/statistics/public-bodies/?year=${encodeURIComponent(getDpmesState().year)}&quarter=${encodeURIComponent(getDpmesState().quarter)}`, title: "Ministries", target: "vr" };
        } else if (isMinistryGoalDetailScene) {
            const ministryId = sourceParams.get("ministry_id") || "";
            backLink = { url: `/dashboard/statistics/public-bodies/${ministryId}/?year=${encodeURIComponent(getDpmesState().year)}&quarter=${encodeURIComponent(getDpmesState().quarter)}`, title: "Ministry Detail", target: "vr" };
        } else if (isMinistryKraDetailScene) {
            backLink = { url: dashboardData.sourcePage && dashboardData.sourcePage.url || "/dashboard/statistics/goals/1/", title: dashboardData.sourcePage && dashboardData.sourcePage.title || "Goal Detail", target: "vr" };
        } else if (isProjectCatalogScene) {
            backLink = { url: "/dashboard/", title: "Dashboard Home", target: "vr" };
        } else if (isProjectDetailScene) {
            backLink = { url: "/dashboard/projects/sector/", title: "Sector Projects", target: "vr" };
        } else if (isProjectSubDetailScene) {
            backLink = { url: dashboardData.sourcePage && dashboardData.sourcePage.url || "/dashboard/projects/sector/1/", title: dashboardData.sourcePage && dashboardData.sourcePage.title || "Project Detail", target: "vr" };
        } else if (isInitiativeCatalogScene) {
            backLink = { url: "/dashboard/", title: "Dashboard Home", target: "vr" };
        } else if (isInitiativeDetailScene) {
            backLink = { url: "/dashboard/projects/initiatives/", title: "Initiatives", target: "vr" };
        }
        const backControl = backLink ? `
            <a-entity position="-3.72 2.64 -2.04" rotation="0 18 0">
                <a-box class="interactive" page-link="url: ${backLink.url}; title: ${backLink.title}; target: ${backLink.target}" width="1.18" height="0.34" depth="0.08" material="color: #112638; opacity: 0.96"></a-box>
                <a-text value="Back" width="0.72" align="center" color="#ffffff" position="-0.36 0.03 0.05"></a-text>
                <a-text value="${escapeAttribute(backLink.title)}" width="0.88" align="center" color="#8ef1e5" position="-0.44 -0.11 0.05"></a-text>
            </a-entity>
        ` : "";
        const kpiCards = dashboardData.kpis.map((card) => `
            <a-entity class="interactive dashboard-panel"
                geometry="primitive: box; width: 1.05; height: 0.62; depth: 0.06"
                material="color: #0c1622; metalness: 0.15; roughness: 0.24; opacity: 0.94"
                position="${card.position}"
                draggable-panel
                shadow="cast: true; receive: true">
                <a-text value="${card.label}" width="1.2" color="#8eb3c6" position="-0.42 0.18 0.04"></a-text>
                <a-text value="${card.value}" width="2.1" color="#f0fbff" position="-0.42 -0.02 0.04"></a-text>
                <a-text value="${card.delta}" width="1.25" color="#5de4c7" position="-0.42 -0.2 0.04"></a-text>
            </a-entity>
        `).join("");

        const chartBars = dashboardData.charts.map((value, index) => `
            <a-box
                position="${-0.75 + index * 0.3} ${-0.48 + value * 0.7} 0.06"
                width="0.18"
                depth="0.12"
                height="${Math.max(0.2, value * 1.4)}"
                color="${index % 2 === 0 ? "#5de4c7" : "#7cb8ff"}"
                shadow="cast: true">
            </a-box>
        `).join("");

        const menuItems = dashboardData.menu.map((item, index) => {
            const angle = -48 + index * 24;
            const radians = angle * (Math.PI / 180);
            const x = Math.sin(radians) * 2.15;
            const z = -3.4 + Math.cos(radians) * 0.45;
            return `
                <a-entity
                    geometry="primitive: box; width: 0.72; height: 0.22; depth: 0.06"
                    material="color: #10202f; opacity: 0.95"
                    position="${x.toFixed(2)} 0.9 ${z.toFixed(2)}"
                    rotation="0 ${-angle} 0"
                    class="interactive"
                    menu-action="label: ${item}">
                    <a-text value="${item}" width="1" align="center" color="#f0fbff" position="0 -0.03 0.04"></a-text>
                </a-entity>
            `;
        }).join("");

        const notifications = dashboardData.notifications.map((item, index) => `
            <a-entity
                geometry="primitive: box; width: 1.4; height: 0.25; depth: 0.04"
                material="color: #10354a; emissive: #1d85aa; emissiveIntensity: 0.14; opacity: 0.72"
                position="0 ${0.32 - index * 0.32} 0"
                hologram-pulse>
                <a-text value="${item}" wrap-count="28" width="1.28" color="#dffaff" position="-0.62 -0.03 0.03"></a-text>
            </a-entity>
        `).join("");

        const pageTiles = (dashboardData.pages || []).map((page, index) => {
            const column = index % 3;
            const row = Math.floor(index / 3);
            const x = -2.4 + column * 1.7;
            const y = 2.2 - row * 0.42;
            return `
                <a-entity
                    class="interactive"
                    geometry="primitive: box; width: 1.45; height: 0.24; depth: 0.05"
                    material="color: #112638; opacity: 0.95"
                    position="${x.toFixed(2)} ${y.toFixed(2)} -5.2"
                    page-link="url: ${page.url}; title: ${page.title}">
                    <a-text value="${page.title}" width="1.25" align="center" color="#eff9ff" position="0 -0.03 0.04"></a-text>
                </a-entity>
            `;
        }).join("");

        const widgetLines = (dashboardData.widgetLines || []).map((line, index) => `
            <a-text
                value="${line}"
                width="1.2"
                wrap-count="25"
                color="${index === 0 ? "#b7d3df" : "#7ea2b4"}"
                position="-0.68 ${0.06 - index * 0.28} 0.04">
            </a-text>
        `).join("");

        const sectionPanels = (dashboardData.sectionPanels || []).map((panel) => `
            <a-entity
                class="interactive"
                geometry="primitive: box; width: 1.38; height: 0.52; depth: 0.05"
                material="color: #0f2030; opacity: 0.92"
                position="${panel.position}"
                rotation="${panel.rotation || "0 0 0"}">
                <a-text value="${panel.title}" width="1.35" color="#eff9ff" position="-0.56 0.1 0.04"></a-text>
                <a-text value="${panel.subtitle}" width="1.1" wrap-count="22" color="#8fb5c7" position="-0.56 -0.12 0.04"></a-text>
                ${(panel.items || []).slice(0, 3).map((item, index) => `
                    <a-text
                        value="${item}"
                        width="1.05"
                        wrap-count="24"
                        color="#5de4c7"
                        position="-0.56 ${-0.28 - index * 0.11} 0.04">
                    </a-text>
                `).join("")}
            </a-entity>
        `).join("");

        const homeLogoUrl = buildProxyMediaUrl("https://time-series.mopd.gov.et/static/assets/images/logo-light.png");
        const sharedPageWall = !isHomeScene ? `
            <a-entity position="0 1.58 -6.02">
                <a-box width="6.2" height="0.86" depth="0.12" color="#0b1622" material="metalness: 0.14; roughness: 0.28; opacity: 0.95"></a-box>
                <a-text value="Page Wall" width="1.2" align="center" color="#8ef1e5" position="-0.6 0.28 0.08"></a-text>
                <a-entity position="-2.28 -0.02 0.08">
                    <a-box class="interactive" page-link="url: /dashboard/statistics/public-bodies/?year=2017&quarter=3month; title: Ministries; target: vr" width="0.92" height="0.24" depth="0.06" material="color: #0f2b32; opacity: 0.98"></a-box>
                    <a-text value="Ministries" width="0.7" align="center" color="#ffffff" position="-0.35 -0.03 0.04"></a-text>
                </a-entity>
                <a-entity position="-1.12 -0.02 0.08">
                    <a-box class="interactive" page-link="url: /dashboard/statistics/policy-areas/?year=2018&quarter=3month; title: Policy Areas; target: vr" width="0.92" height="0.24" depth="0.06" material="color: #1a2a46; opacity: 0.98"></a-box>
                    <a-text value="Policy Areas" width="0.7" align="center" color="#ffffff" position="-0.35 -0.03 0.04"></a-text>
                </a-entity>
                <a-entity position="0.04 -0.02 0.08">
                    <a-box class="interactive" page-link="url: /dashboard/data/; title: Data Catalog; target: vr" width="0.92" height="0.24" depth="0.06" material="color: #23311a; opacity: 0.98"></a-box>
                    <a-text value="Data Catalog" width="0.7" align="center" color="#ffffff" position="-0.35 -0.03 0.04"></a-text>
                </a-entity>
                <a-entity position="1.2 -0.02 0.08">
                    <a-box class="interactive" page-link="url: /dashboard/projects/sector/; title: Sector Projects; target: vr" width="0.92" height="0.24" depth="0.06" material="color: #3a2413; opacity: 0.98"></a-box>
                    <a-text value="Projects" width="0.7" align="center" color="#ffffff" position="-0.35 -0.03 0.04"></a-text>
                </a-entity>
                <a-entity position="2.36 -0.02 0.08">
                    <a-box class="interactive" page-link="url: /dashboard/projects/initiatives/; title: Initiatives; target: vr" width="0.92" height="0.24" depth="0.06" material="color: #3a102e; opacity: 0.98"></a-box>
                    <a-text value="Initiatives" width="0.7" align="center" color="#ffffff" position="-0.35 -0.03 0.04"></a-text>
                </a-entity>
            </a-entity>
        ` : "";

        const homeDashboardReplica = isHomeScene ? `
            <a-cylinder radius="5.4" height="0.08" color="#07111a" opacity="0.98" position="0 0.02 0"></a-cylinder>
            <a-ring position="0 0.06 0" radius-inner="2.42" radius-outer="2.54" rotation="-90 0 0" color="#173447" material="opacity: 0.26"></a-ring>
            <a-ring position="0 0.07 -2.85" radius-inner="5.18" radius-outer="5.32" rotation="-90 0 0" color="#1f4d63" material="opacity: 0.14"></a-ring>
            <a-box width="5.8" height="1" depth="0.16" color="#0b1622" material="metalness: 0.16; roughness: 0.28; opacity: 0.96" position="0 2.36 -2.42" rotation="-6 0 0"></a-box>
            <a-cylinder radius="1.06" height="0.04" color="#10293b" material="opacity: 0.88" position="0 3.04 -2.18" rotation="90 0 0"></a-cylinder>
            <a-ring radius-inner="0.84" radius-outer="0.95" color="#8ef1e5" material="opacity: 0.16" position="0 3.04 -2.16"></a-ring>
            ${homeLogoUrl ? `
                <a-plane width="1.78" height="0.72" position="0 3.06 -2.11" material="color: #ffffff; opacity: 0.98; shader: flat"></a-plane>
                <a-image src="${escapeAttribute(homeLogoUrl)}" width="1.52" height="0.56" position="0 3.06 -2.1"></a-image>
            ` : ""}
            <a-text value="Ministry of Planning Data Hub" width="2.6" align="center" color="#dbeafe" position="-1.3 2.84 -2.28"></a-text>
            <a-text value="Digital Hub VR" width="3.2" align="center" color="#ffffff" position="-1.6 2.56 -2.32"></a-text>
            <a-text value="Choose one workspace to start" width="2.6" align="center" color="#8ef1e5" position="-1.3 2.04 -2.28"></a-text>

            <a-entity position="-4.75 1.08 -1.55" rotation="0 68 0">
                <a-cylinder radius="1.14" height="0.04" color="#08131b" position="0 -0.64 0" rotation="90 0 0"></a-cylinder>
                <a-ring radius-inner="0.92" radius-outer="1.04" color="#5de4c7" material="opacity: 0.2" position="0 -0.01 0.09"></a-ring>
                <a-ring radius-inner="0.92" radius-outer="1.04" color="#5de4c7" material="opacity: 0.2" position="0 -0.01 -0.09" rotation="0 180 0"></a-ring>
                <a-box class="interactive" page-link="url: /dashboard/statistics/public-bodies/?year=2017&quarter=3month; title: Ministries; target: vr" width="1.78" height="1.24" depth="0.16" material="color: #0f2b32; opacity: 0.98"></a-box>
                <a-plane width="1.58" height="1.02" position="0 0 0.085" material="color: #123c42; opacity: 0.36; side: double"></a-plane>
                <a-plane width="1.58" height="1.02" position="0 0 -0.085" rotation="0 180 0" material="color: #123c42; opacity: 0.36; side: double"></a-plane>
                <a-plane width="0.14" height="1.02" position="-0.76 0 0.09" material="color: #5de4c7; opacity: 0.95"></a-plane>
                <a-plane width="0.14" height="1.02" position="0.76 0 -0.09" rotation="0 180 0" material="color: #5de4c7; opacity: 0.95"></a-plane>
                <a-ring radius-inner="0.28" radius-outer="0.34" color="#5de4c7" material="opacity: 0.22" position="0 0.32 0.09"></a-ring>
                <a-ring radius-inner="0.28" radius-outer="0.34" color="#5de4c7" material="opacity: 0.22" position="0 0.32 -0.09" rotation="0 180 0"></a-ring>
                <a-text value="Ministries" width="1.4" align="center" color="#ffffff" position="-0.7 0.18 0.1"></a-text>
                <a-text value="Ministries" width="1.4" align="center" color="#ffffff" position="0.7 0.18 -0.1" rotation="0 180 0"></a-text>
                <a-text value="Public body scorecards, goals, KRAs, and indicators" width="1.26" wrap-count="18" align="center" color="#cbd5e1" position="-0.64 -0.12 0.1"></a-text>
                <a-text value="Public body scorecards, goals, KRAs, and indicators" width="1.26" wrap-count="18" align="center" color="#cbd5e1" position="0.64 -0.12 -0.1" rotation="0 180 0"></a-text>
                <a-text value="Open VR Flow" width="0.96" align="center" color="#8ef1e5" position="-0.48 -0.46 0.1"></a-text>
                <a-text value="Open VR Flow" width="0.96" align="center" color="#8ef1e5" position="0.48 -0.46 -0.1" rotation="0 180 0"></a-text>
            </a-entity>

            <a-entity position="-2.9 1.16 -3.72" rotation="0 36 0">
                <a-cylinder radius="1.14" height="0.04" color="#0a101b" position="0 -0.64 0" rotation="90 0 0"></a-cylinder>
                <a-ring radius-inner="0.92" radius-outer="1.04" color="#7dd3fc" material="opacity: 0.2" position="0 -0.01 0.09"></a-ring>
                <a-ring radius-inner="0.92" radius-outer="1.04" color="#7dd3fc" material="opacity: 0.2" position="0 -0.01 -0.09" rotation="0 180 0"></a-ring>
                <a-box class="interactive" page-link="url: /dashboard/statistics/policy-areas/?year=2018&quarter=3month; title: Policy Areas; target: vr" width="1.78" height="1.24" depth="0.16" material="color: #1a2a46; opacity: 0.98"></a-box>
                <a-plane width="1.58" height="1.02" position="0 0 0.085" material="color: #1d3a62; opacity: 0.34; side: double"></a-plane>
                <a-plane width="1.58" height="1.02" position="0 0 -0.085" rotation="0 180 0" material="color: #1d3a62; opacity: 0.34; side: double"></a-plane>
                <a-plane width="0.14" height="1.02" position="-0.76 0 0.09" material="color: #7dd3fc; opacity: 0.95"></a-plane>
                <a-plane width="0.14" height="1.02" position="0.76 0 -0.09" rotation="0 180 0" material="color: #7dd3fc; opacity: 0.95"></a-plane>
                <a-ring radius-inner="0.28" radius-outer="0.34" color="#7dd3fc" material="opacity: 0.22" position="0 0.32 0.09"></a-ring>
                <a-ring radius-inner="0.28" radius-outer="0.34" color="#7dd3fc" material="opacity: 0.22" position="0 0.32 -0.09" rotation="0 180 0"></a-ring>
                <a-text value="Policy Areas" width="1.4" align="center" color="#ffffff" position="-0.7 0.18 0.1"></a-text>
                <a-text value="Policy Areas" width="1.4" align="center" color="#ffffff" position="0.7 0.18 -0.1" rotation="0 180 0"></a-text>
                <a-text value="Policy areas, goals, KRAs, and recent indicator history" width="1.26" wrap-count="18" align="center" color="#cbd5e1" position="-0.64 -0.12 0.1"></a-text>
                <a-text value="Policy areas, goals, KRAs, and recent indicator history" width="1.26" wrap-count="18" align="center" color="#cbd5e1" position="0.64 -0.12 -0.1" rotation="0 180 0"></a-text>
                <a-text value="Open VR Flow" width="0.96" align="center" color="#7dd3fc" position="-0.48 -0.46 0.1"></a-text>
                <a-text value="Open VR Flow" width="0.96" align="center" color="#7dd3fc" position="0.48 -0.46 -0.1" rotation="0 180 0"></a-text>
            </a-entity>

            <a-entity position="0 1.2 -4.05" rotation="0 0 0">
                <a-cylinder radius="1.14" height="0.04" color="#0b1607" position="0 -0.64 0" rotation="90 0 0"></a-cylinder>
                <a-ring radius-inner="0.92" radius-outer="1.04" color="#a3e635" material="opacity: 0.2" position="0 -0.01 0.09"></a-ring>
                <a-ring radius-inner="0.92" radius-outer="1.04" color="#a3e635" material="opacity: 0.2" position="0 -0.01 -0.09" rotation="0 180 0"></a-ring>
                <a-box class="interactive" page-link="url: /dashboard/data/; title: Data Catalog; target: vr" width="1.78" height="1.24" depth="0.16" material="color: #23311a; opacity: 0.98"></a-box>
                <a-plane width="1.58" height="1.02" position="0 0 0.085" material="color: #365314; opacity: 0.3; side: double"></a-plane>
                <a-plane width="1.58" height="1.02" position="0 0 -0.085" rotation="0 180 0" material="color: #365314; opacity: 0.3; side: double"></a-plane>
                <a-plane width="0.14" height="1.02" position="-0.76 0 0.09" material="color: #a3e635; opacity: 0.95"></a-plane>
                <a-plane width="0.14" height="1.02" position="0.76 0 -0.09" rotation="0 180 0" material="color: #a3e635; opacity: 0.95"></a-plane>
                <a-ring radius-inner="0.28" radius-outer="0.34" color="#a3e635" material="opacity: 0.2" position="0 0.32 0.09"></a-ring>
                <a-ring radius-inner="0.28" radius-outer="0.34" color="#a3e635" material="opacity: 0.2" position="0 0.32 -0.09" rotation="0 180 0"></a-ring>
                <a-text value="Data Catalog" width="1.4" align="center" color="#ffffff" position="-0.7 0.18 0.1"></a-text>
                <a-text value="Data Catalog" width="1.4" align="center" color="#ffffff" position="0.7 0.18 -0.1" rotation="0 180 0"></a-text>
                <a-text value="Topics, categories, and indicators in the immersive catalog" width="1.26" wrap-count="18" align="center" color="#cbd5e1" position="-0.64 -0.12 0.1"></a-text>
                <a-text value="Topics, categories, and indicators in the immersive catalog" width="1.26" wrap-count="18" align="center" color="#cbd5e1" position="0.64 -0.12 -0.1" rotation="0 180 0"></a-text>
                <a-text value="Open VR Flow" width="0.96" align="center" color="#bef264" position="-0.48 -0.46 0.1"></a-text>
                <a-text value="Open VR Flow" width="0.96" align="center" color="#bef264" position="0.48 -0.46 -0.1" rotation="0 180 0"></a-text>
            </a-entity>

            <a-entity position="2.9 1.16 -3.72" rotation="0 -36 0">
                <a-cylinder radius="1.16" height="0.04" color="#160f08" position="0 -0.64 0" rotation="90 0 0"></a-cylinder>
                <a-ring radius-inner="0.94" radius-outer="1.06" color="#fb923c" material="opacity: 0.2" position="0 -0.02 0.09"></a-ring>
                <a-ring radius-inner="0.94" radius-outer="1.06" color="#fb923c" material="opacity: 0.2" position="0 -0.02 -0.09" rotation="0 180 0"></a-ring>
                <a-box class="interactive" page-link="url: /dashboard/projects/sector/; title: Sector Projects; target: vr" width="1.86" height="1.1" depth="0.16" material="color: #3a2413; opacity: 0.98"></a-box>
                <a-plane width="1.64" height="0.9" position="0 0 0.085" material="color: #7c2d12; opacity: 0.28; side: double"></a-plane>
                <a-plane width="1.64" height="0.9" position="0 0 -0.085" rotation="0 180 0" material="color: #7c2d12; opacity: 0.28; side: double"></a-plane>
                <a-plane width="0.14" height="0.9" position="-0.8 0 0.09" material="color: #fb923c; opacity: 0.95"></a-plane>
                <a-plane width="0.14" height="0.9" position="0.8 0 -0.09" rotation="0 180 0" material="color: #fb923c; opacity: 0.95"></a-plane>
                <a-ring radius-inner="0.28" radius-outer="0.34" color="#fb923c" material="opacity: 0.22" position="0 0.28 0.09"></a-ring>
                <a-ring radius-inner="0.28" radius-outer="0.34" color="#fb923c" material="opacity: 0.22" position="0 0.28 -0.09" rotation="0 180 0"></a-ring>
                <a-text value="Projects" width="1.4" align="center" color="#ffffff" position="-0.7 0.16 0.1"></a-text>
                <a-text value="Projects" width="1.4" align="center" color="#ffffff" position="0.7 0.16 -0.1" rotation="0 180 0"></a-text>
                <a-text value="Sector project image catalog and project detail rooms" width="1.28" wrap-count="18" align="center" color="#fde7d4" position="-0.64 -0.12 0.1"></a-text>
                <a-text value="Sector project image catalog and project detail rooms" width="1.28" wrap-count="18" align="center" color="#fde7d4" position="0.64 -0.12 -0.1" rotation="0 180 0"></a-text>
                <a-text value="Open VR Flow" width="0.98" align="center" color="#fdba74" position="-0.49 -0.44 0.1"></a-text>
                <a-text value="Open VR Flow" width="0.98" align="center" color="#fdba74" position="0.49 -0.44 -0.1" rotation="0 180 0"></a-text>
            </a-entity>

            <a-entity position="4.75 1.08 -1.55" rotation="0 -68 0">
                <a-cylinder radius="1.16" height="0.04" color="#180914" position="0 -0.64 0" rotation="90 0 0"></a-cylinder>
                <a-ring radius-inner="0.94" radius-outer="1.06" color="#f472b6" material="opacity: 0.2" position="0 -0.02 0.09"></a-ring>
                <a-ring radius-inner="0.94" radius-outer="1.06" color="#f472b6" material="opacity: 0.2" position="0 -0.02 -0.09" rotation="0 180 0"></a-ring>
                <a-box class="interactive" page-link="url: /dashboard/projects/initiatives/; title: Initiatives; target: vr" width="1.86" height="1.1" depth="0.16" material="color: #3a102e; opacity: 0.98"></a-box>
                <a-plane width="1.64" height="0.9" position="0 0 0.085" material="color: #831843; opacity: 0.3; side: double"></a-plane>
                <a-plane width="1.64" height="0.9" position="0 0 -0.085" rotation="0 180 0" material="color: #831843; opacity: 0.3; side: double"></a-plane>
                <a-plane width="0.14" height="0.9" position="-0.8 0 0.09" material="color: #f472b6; opacity: 0.95"></a-plane>
                <a-plane width="0.14" height="0.9" position="0.8 0 -0.09" rotation="0 180 0" material="color: #f472b6; opacity: 0.95"></a-plane>
                <a-ring radius-inner="0.28" radius-outer="0.34" color="#f472b6" material="opacity: 0.22" position="0 0.28 0.09"></a-ring>
                <a-ring radius-inner="0.28" radius-outer="0.34" color="#f472b6" material="opacity: 0.22" position="0 0.28 -0.09" rotation="0 180 0"></a-ring>
                <a-text value="Initiatives" width="1.4" align="center" color="#ffffff" position="-0.7 0.16 0.1"></a-text>
                <a-text value="Initiatives" width="1.4" align="center" color="#ffffff" position="0.7 0.16 -0.1" rotation="0 180 0"></a-text>
                <a-text value="National initiative image catalog and immersive detail rooms" width="1.28" wrap-count="18" align="center" color="#fce7f3" position="-0.64 -0.12 0.1"></a-text>
                <a-text value="National initiative image catalog and immersive detail rooms" width="1.28" wrap-count="18" align="center" color="#fce7f3" position="0.64 -0.12 -0.1" rotation="0 180 0"></a-text>
                <a-text value="Open VR Flow" width="0.98" align="center" color="#f9a8d4" position="-0.49 -0.44 0.1"></a-text>
                <a-text value="Open VR Flow" width="0.98" align="center" color="#f9a8d4" position="0.49 -0.44 -0.1" rotation="0 180 0"></a-text>
            </a-entity>
        ` : "";

        const dataTopicPanels = (dashboardData.dataCatalogTopics || []).map((topic, index) => {
            const total = Math.max((dashboardData.dataCatalogTopics || []).length, 1);
            const angle = (360 / total) * index;
            const radians = angle * (Math.PI / 180);
            const radius = 4.8;
            const x = Math.sin(radians) * radius;
            const z = Math.cos(radians) * radius;
            const y = 1.15;
            const faceCenterRotation = 180 + angle;
            const topicUrl = `/dashboard/data/${topic.id}/`;
            const imageMarkup = topic.image
                ? `
                    <a-plane
                        width="1.92"
                        height="1.22"
                        position="0 0.1 0.052"
                        material="src: url(${escapeAttribute(topic.image)}); shader: flat; side: double; transparent: false; alphaTest: 0.01">
                    </a-plane>
                    <a-plane
                        width="1.92"
                        height="1.22"
                        position="0 0.1 -0.052"
                        rotation="0 180 0"
                        material="src: url(${escapeAttribute(topic.image)}); shader: flat; side: double; transparent: false; alphaTest: 0.01">
                    </a-plane>
                  `
                : `
                    <a-plane width="1.92" height="1.22" position="0 0.1 0.052" material="color: #0f766e; shader: flat; side: double"></a-plane>
                    <a-plane width="1.92" height="1.22" position="0 0.1 -0.052" rotation="0 180 0" material="color: #0f766e; shader: flat; side: double"></a-plane>
                  `;
            const iconMarkup = topic.icon
                ? `
                    <a-image
                        src="${escapeAttribute(topic.icon)}"
                        width="0.18"
                        height="0.18"
                        position="-0.68 -0.06 0.084">
                    </a-image>
                    <a-image
                        src="${escapeAttribute(topic.icon)}"
                        width="0.18"
                        height="0.18"
                        position="0.68 -0.06 -0.084"
                        rotation="0 180 0">
                    </a-image>
                  `
                : `
                    <a-circle radius="0.09" color="#dff3ea" position="-0.68 -0.06 0.084"></a-circle>
                    <a-circle radius="0.09" color="#dff3ea" position="0.68 -0.06 -0.084" rotation="0 180 0"></a-circle>
                  `;
            return `
                <a-entity
                    position="${x.toFixed(2)} ${y.toFixed(2)} ${z.toFixed(2)}"
                    rotation="0 ${faceCenterRotation.toFixed(2)} 0"
                    draggable-panel>
                    <a-box
                        class="interactive"
                    page-link="url: ${topicUrl}; title: ${topic.title}; target: vr"
                        width="2.06"
                        height="1.36"
                        depth="0.18"
                        position="0 0 0"
                        material="transparent: true; opacity: 0.001; side: double">
                    </a-box>
                    <a-box
                        width="2"
                        height="1.3"
                        depth="0.06"
                        color="#08111a"
                        material="metalness: 0.12; roughness: 0.34; opacity: 0.98">
                    </a-box>
                    <a-entity
                        geometry="primitive: cylinder; radius: 1.08; height: 0.04"
                        material="color: #0b1622; opacity: 0.96"
                        position="0 0 0"
                        rotation="90 0 0">
                    </a-entity>
                    <a-ring
                        radius-inner="0.9"
                        radius-outer="1.01"
                        color="#5de4c7"
                        material="opacity: 0.24"
                        position="0 0 0.076">
                    </a-ring>
                    <a-ring
                        radius-inner="0.9"
                        radius-outer="1.01"
                        color="#5de4c7"
                        material="opacity: 0.18"
                        position="0 0 -0.076"
                        rotation="0 180 0">
                    </a-ring>
                    ${imageMarkup}
                    <a-plane width="1.68" height="0.58" position="0 -0.33 0.088" material="shader: flat; color: #020617; opacity: 0.84; side: double"></a-plane>
                    <a-plane width="1.68" height="0.58" position="0 -0.33 -0.088" rotation="0 180 0" material="shader: flat; color: #020617; opacity: 0.84; side: double"></a-plane>
                    <a-ring radius-inner="0.12" radius-outer="0.145" color="#ffffff" material="opacity: 0.18" position="-0.68 -0.06 0.086"></a-ring>
                    <a-ring radius-inner="0.12" radius-outer="0.145" color="#ffffff" material="opacity: 0.18" position="0.68 -0.06 -0.086" rotation="0 180 0"></a-ring>
                    <a-ring radius-inner="0.82" radius-outer="0.88" color="#ffffff" material="opacity: 0.08" position="0 0.08 0.082"></a-ring>
                    <a-ring radius-inner="0.82" radius-outer="0.88" color="#ffffff" material="opacity: 0.08" position="0 0.08 -0.082" rotation="0 180 0"></a-ring>
                    ${iconMarkup}
                    <a-text value="${escapeAttribute(topic.title)}" width="1.28" wrap-count="16" align="center" color="#ffffff" position="-0.64 0.18 0.096"></a-text>
                    <a-text value="${escapeAttribute(topic.title)}" width="1.28" wrap-count="16" align="center" color="#ffffff" position="0.64 0.18 -0.096" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(topic.description)}" width="1.4" wrap-count="24" align="center" color="#e2e8f0" position="-0.7 -0.2 0.096"></a-text>
                    <a-text value="${escapeAttribute(topic.description)}" width="1.4" wrap-count="24" align="center" color="#e2e8f0" position="0.7 -0.2 -0.096" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(topic.categories)}" width="0.7" color="#8ef1e5" position="-0.64 -0.49 0.096"></a-text>
                    <a-text value="${escapeAttribute(topic.categories)}" width="0.7" color="#8ef1e5" position="0.04 -0.49 -0.096" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(topic.kpis)}" width="0.56" color="#7dd3fc" position="0.16 -0.49 0.096"></a-text>
                    <a-text value="${escapeAttribute(topic.kpis)}" width="0.56" color="#7dd3fc" position="-0.48 -0.49 -0.096" rotation="0 180 0"></a-text>
                    <a-text value="Open Categories" width="0.9" align="center" color="#5de4c7" position="-0.45 0.52 0.094"></a-text>
                    <a-text value="Open Categories" width="0.9" align="center" color="#5de4c7" position="0.45 0.52 -0.094" rotation="0 180 0"></a-text>
                </a-entity>
            `;
        }).join("");

        const dataIndicatorPanels = (dashboardData.dataCatalogIndicators || []).map((indicator, index) => {
            const column = index % 3;
            const row = Math.floor(index / 3);
            const x = 1.2 + column * 1.34;
            const y = 1.16 - row * 1.02;
            return `
                <a-entity
                    class="interactive"
                    geometry="primitive: box; width: 1.12; height: 0.84; depth: 0.05"
                    material="color: #fbfdf9; opacity: 0.98"
                    position="${x.toFixed(2)} ${y.toFixed(2)} -3.18"
                    draggable-panel>
                    <a-cylinder radius="0.12" height="0.02" color="#edf6ea" position="-0.36 0.24 0.045" rotation="90 0 0"></a-cylinder>
                    <a-cylinder radius="0.09" height="0.02" color="#f3f4f6" position="0.36 0.24 0.045" rotation="90 0 0"></a-cylinder>
                    <a-text value="${escapeAttribute(indicator.value)}" width="1.02" align="center" color="#111827" position="0 0 0.05"></a-text>
                    <a-text value="${escapeAttribute(indicator.unit)}" width="0.72" align="center" color="#4b5563" position="0 -0.18 0.05"></a-text>
                    <a-text value="${escapeAttribute(indicator.title)}" width="0.95" wrap-count="18" align="center" color="#6b7280" position="-0.42 -0.42 0.05"></a-text>
                </a-entity>
            `;
        }).join("");

        const dataCatalogWorkspace = isDataCatalogScene ? `
            <a-cylinder radius="6.4" height="0.08" color="#07111a" opacity="0.98" position="0 0.02 0"></a-cylinder>
            <a-ring position="0 0.06 0" radius-inner="4.68" radius-outer="4.82" rotation="-90 0 0" color="#173447" material="opacity: 0.3"></a-ring>
            <a-ring position="0 0.061 0" radius-inner="3.14" radius-outer="3.24" rotation="-90 0 0" color="#5de4c7" material="opacity: 0.14"></a-ring>
            <a-ring position="0 2.34 -1.6" radius-inner="0.72" radius-outer="0.76" color="#7dd3fc" material="opacity: 0.16"></a-ring>
            <a-text value="Sector Catalog" width="2.2" align="center" color="#f8fafc" position="0 2.42 -1.6"></a-text>
            <a-text value="Turn around to inspect all sectors. Cards are placed in a full 360 degree circle around you." width="3.6" align="center" wrap-count="54" color="#cbd5e1" position="-1.8 2.06 -1.6"></a-text>
            ${dataTopicPanels}
        ` : "";

        const projectCatalogCards = (dashboardData.projectCatalog || []).map((project, index) => {
            const total = Math.max((dashboardData.projectCatalog || []).length, 1);
            const angle = (360 / total) * index;
            const radians = angle * (Math.PI / 180);
            const radius = 4.95;
            const x = Math.sin(radians) * radius;
            const z = Math.cos(radians) * radius;
            const rotation = 180 + angle;
            const url = `/dashboard/projects/sector/${project.id}/`;
            const imageMarkup = project.image
                ? `
                    <a-plane width="1.74" height="0.84" position="0 0.16 0.082" material="src: url(${escapeAttribute(project.image)}); shader: flat; side: double; alphaTest: 0.01"></a-plane>
                    <a-plane width="1.74" height="0.84" position="0 0.16 -0.082" rotation="0 180 0" material="src: url(${escapeAttribute(project.image)}); shader: flat; side: double; alphaTest: 0.01"></a-plane>
                  `
                : `
                    <a-plane width="1.74" height="0.84" position="0 0.16 0.082" material="color: #3a2413; side: double"></a-plane>
                    <a-plane width="1.74" height="0.84" position="0 0.16 -0.082" rotation="0 180 0" material="color: #3a2413; side: double"></a-plane>
                  `;
            const iconMarkup = project.icon
                ? `
                    <a-image src="${escapeAttribute(project.icon)}" width="0.18" height="0.18" position="-0.64 -0.04 0.09"></a-image>
                    <a-image src="${escapeAttribute(project.icon)}" width="0.18" height="0.18" position="0.64 -0.04 -0.09" rotation="0 180 0"></a-image>
                  `
                : "";
            return `
                <a-entity position="${x.toFixed(2)} 1.2 ${z.toFixed(2)}" rotation="0 ${rotation.toFixed(2)} 0">
                    <a-box class="interactive" page-link="url: ${url}; title: ${project.title}; target: vr" width="1.9" height="1.16" depth="0.16" material="color: #1a120d; opacity: 0.98"></a-box>
                    ${imageMarkup}
                    <a-plane width="1.56" height="0.34" position="0 -0.32 0.088" material="color: #09090b; opacity: 0.9; side: double"></a-plane>
                    <a-plane width="1.56" height="0.34" position="0 -0.32 -0.088" rotation="0 180 0" material="color: #09090b; opacity: 0.9; side: double"></a-plane>
                    ${iconMarkup}
                    <a-text value="${escapeAttribute(project.title)}" width="1.18" wrap-count="18" align="center" color="#ffffff" position="-0.58 0.06 0.094"></a-text>
                    <a-text value="${escapeAttribute(project.title)}" width="1.18" wrap-count="18" align="center" color="#ffffff" position="0.58 0.06 -0.094" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(project.description)}" width="1.3" wrap-count="22" align="center" color="#fed7aa" position="-0.66 -0.28 0.094"></a-text>
                    <a-text value="${escapeAttribute(project.description)}" width="1.3" wrap-count="22" align="center" color="#fed7aa" position="0.66 -0.28 -0.094" rotation="0 180 0"></a-text>
                    <a-text value="Open Project" width="0.94" align="center" color="#fb923c" position="-0.47 0.48 0.094"></a-text>
                    <a-text value="Open Project" width="0.94" align="center" color="#fb923c" position="0.47 0.48 -0.094" rotation="0 180 0"></a-text>
                </a-entity>
            `;
        }).join("");

        const projectCatalogScene = isProjectCatalogScene ? `
            <a-cylinder radius="6.2" height="0.08" color="#07111a" opacity="0.98" position="0 0.02 0"></a-cylinder>
            <a-ring position="0 0.06 0" radius-inner="4.74" radius-outer="4.88" rotation="-90 0 0" color="#3f2b1d" material="opacity: 0.28"></a-ring>
            <a-ring position="0 0.061 0" radius-inner="3.2" radius-outer="3.3" rotation="-90 0 0" color="#fb923c" material="opacity: 0.16"></a-ring>
            <a-text value="Sector Projects" width="2.4" align="center" color="#fff7ed" position="-1.2 2.4 -1.54"></a-text>
            <a-text value="Turn in any direction to browse project cards and open project detail." width="3.3" align="center" wrap-count="48" color="#fed7aa" position="-1.65 2.12 -1.52"></a-text>
            ${projectCatalogCards}
        ` : "";

        const projectSubProjectCards = (dashboardData.projectSubProjects || []).map((item, index) => {
            const total = Math.max((dashboardData.projectSubProjects || []).length, 1);
            const angle = (360 / total) * index;
            const radians = angle * (Math.PI / 180);
            const radius = 3.7;
            const x = Math.sin(radians) * radius;
            const z = Math.cos(radians) * radius;
            const rotation = 180 + angle;
            const url = `/dashboard/projects/sector/${dashboardData.projectDetail ? dashboardData.projectDetail.id : ""}/`;
            const imageMarkup = item.image
                ? `
                    <a-plane width="1.28" height="0.46" position="0 0.18 0.072" material="src: url(${escapeAttribute(item.image)}); shader: flat; side: double; alphaTest: 0.01"></a-plane>
                    <a-plane width="1.28" height="0.46" position="0 0.18 -0.072" rotation="0 180 0" material="src: url(${escapeAttribute(item.image)}); shader: flat; side: double; alphaTest: 0.01"></a-plane>
                  `
                : `
                    <a-plane width="1.28" height="0.46" position="0 0.18 0.072" material="color: ${item.isRegional ? "#4c1d95" : "#0f766e"}; opacity: 0.78; side: double"></a-plane>
                    <a-plane width="1.28" height="0.46" position="0 0.18 -0.072" rotation="0 180 0" material="color: ${item.isRegional ? "#4c1d95" : "#0f766e"}; opacity: 0.78; side: double"></a-plane>
                    <a-ring radius-inner="0.15" radius-outer="0.19" color="${item.isRegional ? "#c4b5fd" : "#8ef1e5"}" material="opacity: 0.18" position="0 0.18 0.086"></a-ring>
                    <a-ring radius-inner="0.15" radius-outer="0.19" color="${item.isRegional ? "#c4b5fd" : "#8ef1e5"}" material="opacity: 0.18" position="0 0.18 -0.086" rotation="0 180 0"></a-ring>
                    <a-text value="${escapeAttribute(item.isRegional ? "Regional" : "National")}" width="0.7" align="center" color="#ffffff" position="-0.35 0.12 0.086"></a-text>
                    <a-text value="${escapeAttribute(item.isRegional ? "Regional" : "National")}" width="0.7" align="center" color="#ffffff" position="0.35 0.12 -0.086" rotation="0 180 0"></a-text>
                  `;
            return `
                <a-entity position="${x.toFixed(2)} 1.26 ${z.toFixed(2)}" rotation="0 ${rotation.toFixed(2)} 0">
                    <a-box class="interactive" page-link="url: ${url}; title: ${item.title}; target: vr-project-sub; categoryId: ${item.id}" width="1.52" height="1.18" depth="0.14" material="color: #120b07; opacity: 0.001; side: double"></a-box>
                    <a-box width="1.52" height="1.18" depth="0.14" color="#120b07" material="metalness: 0.16; roughness: 0.3; opacity: 0.98"></a-box>
                    ${imageMarkup}
                    <a-plane width="1.28" height="0.44" position="0 -0.24 0.078" material="color: #09090b; opacity: 0.9; side: double"></a-plane>
                    <a-plane width="1.28" height="0.44" position="0 -0.24 -0.078" rotation="0 180 0" material="color: #09090b; opacity: 0.9; side: double"></a-plane>
                    <a-text value="${escapeAttribute(item.title)}" width="0.98" wrap-count="15" align="center" color="#ffffff" position="-0.49 0.02 0.084"></a-text>
                    <a-text value="${escapeAttribute(item.title)}" width="0.98" wrap-count="15" align="center" color="#ffffff" position="0.49 0.02 -0.084" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(item.pictureLabel)}" width="0.8" align="center" color="#fb923c" position="-0.4 -0.18 0.084"></a-text>
                    <a-text value="${escapeAttribute(item.pictureLabel)}" width="0.8" align="center" color="#fb923c" position="0.4 -0.18 -0.084" rotation="0 180 0"></a-text>
                    <a-text value="Open Detail" width="0.86" align="center" color="#fed7aa" position="-0.43 -0.4 0.084"></a-text>
                    <a-text value="Open Detail" width="0.86" align="center" color="#fed7aa" position="0.43 -0.4 -0.084" rotation="0 180 0"></a-text>
                </a-entity>
            `;
        }).join("");

        const projectDetailCenter = dashboardData.projectDetail && dashboardData.projectDetail.image
            ? `
                <a-box width="1.36" height="1.36" depth="1.36" material="opacity: 0" position="0 1.5 0" animation="property: rotation; to: 0 360 0; loop: true; dur: 18000; easing: linear">
                    <a-plane width="1.34" height="1.34" position="0 0 0.675" material="src: url(${escapeAttribute(dashboardData.projectDetail.image)}); shader: flat; side: double; alphaTest: 0.01"></a-plane>
                    <a-plane width="1.34" height="1.34" position="0 0 -0.675" rotation="0 180 0" material="src: url(${escapeAttribute(dashboardData.projectDetail.image)}); shader: flat; side: double; alphaTest: 0.01"></a-plane>
                    <a-plane width="1.34" height="1.34" position="0.675 0 0" rotation="0 -90 0" material="src: url(${escapeAttribute(dashboardData.projectDetail.image)}); shader: flat; side: double; alphaTest: 0.01"></a-plane>
                    <a-plane width="1.34" height="1.34" position="-0.675 0 0" rotation="0 90 0" material="src: url(${escapeAttribute(dashboardData.projectDetail.image)}); shader: flat; side: double; alphaTest: 0.01"></a-plane>
                    <a-plane width="1.34" height="1.34" position="0 0.675 0" rotation="-90 0 0" material="src: url(${escapeAttribute(dashboardData.projectDetail.image)}); shader: flat; side: double; alphaTest: 0.01"></a-plane>
                    <a-plane width="1.34" height="1.34" position="0 -0.675 0" rotation="90 0 0" material="src: url(${escapeAttribute(dashboardData.projectDetail.image)}); shader: flat; side: double; alphaTest: 0.01"></a-plane>
                </a-box>
              `
            : `<a-box width="1.36" height="1.36" depth="1.36" color="#3a2413" position="0 1.5 0" animation="property: rotation; to: 0 360 0; loop: true; dur: 18000; easing: linear"></a-box>`;

        const projectDetailScene = isProjectDetailScene ? `
            <a-cylinder radius="5.6" height="0.08" color="#07111a" opacity="0.98" position="0 0.02 0"></a-cylinder>
            <a-ring position="0 0.06 0" radius-inner="3.58" radius-outer="3.68" rotation="-90 0 0" color="#4a2d16" material="opacity: 0.28"></a-ring>
            <a-ring position="0 0.061 0" radius-inner="1.04" radius-outer="1.12" rotation="-90 0 0" color="#fb923c" material="opacity: 0.18"></a-ring>
            ${projectDetailCenter}
            <a-text value="${dashboardData.projectDetail ? dashboardData.projectDetail.title : "Project Detail"}" width="2.9" align="center" color="#fff7ed" position="-1.45 2.58 -1.46"></a-text>
            <a-text value="${dashboardData.projectDetail ? dashboardData.projectDetail.description : ""}" width="2.8" align="center" wrap-count="48" color="#fed7aa" position="-1.4 2.22 -1.44"></a-text>
            <a-text value="${dashboardData.projectDetail ? `${dashboardData.projectDetail.subProjectCount} sub-projects | ${dashboardData.projectDetail.pictureCount} pictures` : ""}" width="2.6" align="center" color="#fdba74" position="-1.3 1.96 -1.42"></a-text>
            ${projectSubProjectCards || `<a-text value="No sub-project details are available for this project." width="2.8" align="center" color="#fed7aa" position="-1.4 1.32 -1.64"></a-text>`}
        ` : "";

        const projectSubDetailTiles = (dashboardData.projectSubDetail && dashboardData.projectSubDetail.details || []).slice(0, 8).map((entry, index) => {
            const total = Math.max(Math.min((dashboardData.projectSubDetail && dashboardData.projectSubDetail.details || []).length, 8), 1);
            const angle = (360 / total) * index;
            const radians = angle * (Math.PI / 180);
            const radius = 3.45;
            const x = Math.sin(radians) * radius;
            const z = Math.cos(radians) * radius;
            const rotation = 180 + angle;
            return `
                <a-entity position="${x.toFixed(2)} 1.3 ${z.toFixed(2)}" rotation="0 ${rotation.toFixed(2)} 0">
                    <a-box width="1.5" height="0.92" depth="0.14" color="#120b07" material="metalness: 0.16; roughness: 0.28; opacity: 0.98"></a-box>
                    <a-plane width="1.24" height="0.68" position="0 0 0.078" material="color: #09090b; opacity: 0.9; side: double"></a-plane>
                    <a-plane width="1.24" height="0.68" position="0 0 -0.078" rotation="0 180 0" material="color: #09090b; opacity: 0.9; side: double"></a-plane>
                    <a-text value="${escapeAttribute(entry.key)}" width="0.92" wrap-count="16" align="center" color="#fb923c" position="-0.46 0.18 0.084"></a-text>
                    <a-text value="${escapeAttribute(entry.key)}" width="0.92" wrap-count="16" align="center" color="#fb923c" position="0.46 0.18 -0.084" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(entry.value)}" width="1.02" wrap-count="22" align="center" color="#fed7aa" position="-0.5 -0.08 0.084"></a-text>
                    <a-text value="${escapeAttribute(entry.value)}" width="1.02" wrap-count="22" align="center" color="#fed7aa" position="0.5 -0.08 -0.084" rotation="0 180 0"></a-text>
                </a-entity>
            `;
        }).join("");

        const projectSubDetailCenter = dashboardData.projectSubDetail && dashboardData.projectSubDetail.image
            ? `
                <a-box width="1.42" height="1.42" depth="1.42" material="opacity: 0" position="0 1.52 0" animation="property: rotation; to: 0 360 0; loop: true; dur: 18000; easing: linear">
                    <a-plane width="1.4" height="1.4" position="0 0 0.705" material="src: url(${escapeAttribute(dashboardData.projectSubDetail.image)}); shader: flat; side: double; alphaTest: 0.01"></a-plane>
                    <a-plane width="1.4" height="1.4" position="0 0 -0.705" rotation="0 180 0" material="src: url(${escapeAttribute(dashboardData.projectSubDetail.image)}); shader: flat; side: double; alphaTest: 0.01"></a-plane>
                    <a-plane width="1.4" height="1.4" position="0.705 0 0" rotation="0 -90 0" material="src: url(${escapeAttribute(dashboardData.projectSubDetail.image)}); shader: flat; side: double; alphaTest: 0.01"></a-plane>
                    <a-plane width="1.4" height="1.4" position="-0.705 0 0" rotation="0 90 0" material="src: url(${escapeAttribute(dashboardData.projectSubDetail.image)}); shader: flat; side: double; alphaTest: 0.01"></a-plane>
                    <a-plane width="1.4" height="1.4" position="0 0.705 0" rotation="-90 0 0" material="src: url(${escapeAttribute(dashboardData.projectSubDetail.image)}); shader: flat; side: double; alphaTest: 0.01"></a-plane>
                    <a-plane width="1.4" height="1.4" position="0 -0.705 0" rotation="90 0 0" material="src: url(${escapeAttribute(dashboardData.projectSubDetail.image)}); shader: flat; side: double; alphaTest: 0.01"></a-plane>
                </a-box>
              `
            : `<a-box width="1.42" height="1.42" depth="1.42" color="#3a2413" position="0 1.52 0" animation="property: rotation; to: 0 360 0; loop: true; dur: 18000; easing: linear"></a-box>`;

        const projectSubDetailScene = isProjectSubDetailScene ? `
            <a-cylinder radius="5.6" height="0.08" color="#07111a" opacity="0.98" position="0 0.02 0"></a-cylinder>
            <a-ring position="0 0.06 0" radius-inner="3.58" radius-outer="3.68" rotation="-90 0 0" color="#4a2d16" material="opacity: 0.28"></a-ring>
            <a-ring position="0 0.061 0" radius-inner="1.02" radius-outer="1.12" rotation="-90 0 0" color="#fb923c" material="opacity: 0.18"></a-ring>
            ${projectSubDetailCenter}
            <a-text value="${dashboardData.projectSubDetail ? dashboardData.projectSubDetail.title : "Sub-Project Detail"}" width="3" align="center" color="#fff7ed" position="-1.5 2.6 -1.46"></a-text>
            <a-text value="${dashboardData.projectSubDetail ? dashboardData.projectSubDetail.description : ""}" width="2.8" align="center" wrap-count="50" color="#fed7aa" position="-1.4 2.24 -1.44"></a-text>
            <a-text value="${dashboardData.projectSubDetail ? `${dashboardData.projectSubDetail.pictureCount} pictures | ${dashboardData.projectSubDetail.details.length} fields` : ""}" width="2.6" align="center" color="#fdba74" position="-1.3 1.98 -1.42"></a-text>
            ${projectSubDetailTiles || `<a-text value="No structured details are available for this sub-project." width="2.8" align="center" color="#fed7aa" position="-1.4 1.42 -1.62"></a-text>`}
        ` : "";

        const initiativeCatalogCards = (dashboardData.initiativeCatalog || []).map((initiative, index) => {
            const total = Math.max((dashboardData.initiativeCatalog || []).length, 1);
            const angle = (360 / total) * index;
            const radians = angle * (Math.PI / 180);
            const radius = 4.95;
            const x = Math.sin(radians) * radius;
            const z = Math.cos(radians) * radius;
            const rotation = 180 + angle;
            const url = `/dashboard/projects/initiatives/${initiative.id}/`;
            const imageMarkup = initiative.image
                ? `
                    <a-plane width="1.72" height="0.82" position="0 0.17 0.082" material="src: url(${escapeAttribute(initiative.image)}); shader: flat; side: double; alphaTest: 0.01"></a-plane>
                    <a-plane width="1.72" height="0.82" position="0 0.17 -0.082" rotation="0 180 0" material="src: url(${escapeAttribute(initiative.image)}); shader: flat; side: double; alphaTest: 0.01"></a-plane>
                  `
                : `
                    <a-plane width="1.72" height="0.82" position="0 0.17 0.082" material="color: #3a102e; side: double"></a-plane>
                    <a-plane width="1.72" height="0.82" position="0 0.17 -0.082" rotation="0 180 0" material="color: #3a102e; side: double"></a-plane>
                  `;
            const iconMarkup = initiative.icon
                ? `
                    <a-image src="${escapeAttribute(initiative.icon)}" width="0.18" height="0.18" position="-0.64 -0.04 0.09"></a-image>
                    <a-image src="${escapeAttribute(initiative.icon)}" width="0.18" height="0.18" position="0.64 -0.04 -0.09" rotation="0 180 0"></a-image>
                  `
                : "";
            return `
                <a-entity position="${x.toFixed(2)} 1.2 ${z.toFixed(2)}" rotation="0 ${rotation.toFixed(2)} 0">
                    <a-box class="interactive" page-link="url: ${url}; title: ${initiative.title}; target: vr" width="1.9" height="1.16" depth="0.16" material="color: #190713; opacity: 0.98"></a-box>
                    ${imageMarkup}
                    <a-plane width="1.56" height="0.34" position="0 -0.32 0.088" material="color: #09090b; opacity: 0.9; side: double"></a-plane>
                    <a-plane width="1.56" height="0.34" position="0 -0.32 -0.088" rotation="0 180 0" material="color: #09090b; opacity: 0.9; side: double"></a-plane>
                    ${iconMarkup}
                    <a-text value="${escapeAttribute(initiative.title)}" width="1.14" wrap-count="18" align="center" color="#ffffff" position="-0.56 0.06 0.094"></a-text>
                    <a-text value="${escapeAttribute(initiative.title)}" width="1.14" wrap-count="18" align="center" color="#ffffff" position="0.56 0.06 -0.094" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(initiative.categories)}" width="0.76" align="center" color="#f9a8d4" position="-0.38 -0.22 0.094"></a-text>
                    <a-text value="${escapeAttribute(initiative.categories)}" width="0.76" align="center" color="#f9a8d4" position="0.38 -0.22 -0.094" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(initiative.kpis)}" width="0.72" align="center" color="#93c5fd" position="-0.36 -0.38 0.094"></a-text>
                    <a-text value="${escapeAttribute(initiative.kpis)}" width="0.72" align="center" color="#93c5fd" position="0.36 -0.38 -0.094" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(initiative.description)}" width="1.28" wrap-count="22" align="center" color="#fce7f3" position="-0.64 0.46 0.094"></a-text>
                    <a-text value="${escapeAttribute(initiative.description)}" width="1.28" wrap-count="22" align="center" color="#fce7f3" position="0.64 0.46 -0.094" rotation="0 180 0"></a-text>
                </a-entity>
            `;
        }).join("");

        const initiativeCatalogScene = isInitiativeCatalogScene ? `
            <a-cylinder radius="6.2" height="0.08" color="#07111a" opacity="0.98" position="0 0.02 0"></a-cylinder>
            <a-ring position="0 0.06 0" radius-inner="4.74" radius-outer="4.88" rotation="-90 0 0" color="#4d1739" material="opacity: 0.28"></a-ring>
            <a-ring position="0 0.061 0" radius-inner="3.2" radius-outer="3.3" rotation="-90 0 0" color="#f472b6" material="opacity: 0.16"></a-ring>
            <a-text value="National Initiatives" width="2.6" align="center" color="#fdf2f8" position="-1.3 2.4 -1.54"></a-text>
            <a-text value="Turn around to browse initiative cards and open immersive initiative detail." width="3.5" align="center" wrap-count="52" color="#fbcfe8" position="-1.75 2.12 -1.52"></a-text>
            ${initiativeCatalogCards}
        ` : "";

        const initiativeDetailPanels = (dashboardData.initiativeDetailPanels || []).map((panel, index) => {
            const angle = -45 + index * 30;
            const radians = angle * (Math.PI / 180);
            const radius = 3.4;
            const x = Math.sin(radians) * radius;
            const z = -0.4 + Math.cos(radians) * radius;
            return `
                <a-entity position="${x.toFixed(2)} 1.34 ${z.toFixed(2)}" rotation="0 ${(-angle).toFixed(2)} 0">
                    <a-box width="1.48" height="0.92" depth="0.14" color="#17060f" material="metalness: 0.14; roughness: 0.3; opacity: 0.98"></a-box>
                    <a-ring radius-inner="0.2" radius-outer="0.24" color="${panel.accent}" material="opacity: 0.24" position="0 0.22 0.076"></a-ring>
                    <a-ring radius-inner="0.2" radius-outer="0.24" color="${panel.accent}" material="opacity: 0.24" position="0 0.22 -0.076" rotation="0 180 0"></a-ring>
                    <a-text value="${escapeAttribute(panel.title)}" width="0.94" align="center" color="#ffffff" position="-0.47 0.18 0.084"></a-text>
                    <a-text value="${escapeAttribute(panel.title)}" width="0.94" align="center" color="#ffffff" position="0.47 0.18 -0.084" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(panel.value)}" width="1.02" align="center" color="${panel.accent}" position="-0.51 -0.02 0.084"></a-text>
                    <a-text value="${escapeAttribute(panel.value)}" width="1.02" align="center" color="${panel.accent}" position="0.51 -0.02 -0.084" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(panel.subtitle)}" width="1.08" wrap-count="18" align="center" color="#fbcfe8" position="-0.54 -0.28 0.084"></a-text>
                    <a-text value="${escapeAttribute(panel.subtitle)}" width="1.08" wrap-count="18" align="center" color="#fbcfe8" position="0.54 -0.28 -0.084" rotation="0 180 0"></a-text>
                </a-entity>
            `;
        }).join("");

        const initiativeDetailCenter = dashboardData.initiativeDetail && dashboardData.initiativeDetail.image
            ? `
                <a-box width="1.28" height="1.28" depth="1.28" material="opacity: 0" position="0 1.52 0" animation="property: rotation; to: 0 360 0; loop: true; dur: 20000; easing: linear">
                    <a-plane width="1.26" height="1.26" position="0 0 0.635" material="src: url(${escapeAttribute(dashboardData.initiativeDetail.image)}); shader: flat; side: double; alphaTest: 0.01"></a-plane>
                    <a-plane width="1.26" height="1.26" position="0 0 -0.635" rotation="0 180 0" material="src: url(${escapeAttribute(dashboardData.initiativeDetail.image)}); shader: flat; side: double; alphaTest: 0.01"></a-plane>
                    <a-plane width="1.26" height="1.26" position="0.635 0 0" rotation="0 -90 0" material="src: url(${escapeAttribute(dashboardData.initiativeDetail.image)}); shader: flat; side: double; alphaTest: 0.01"></a-plane>
                    <a-plane width="1.26" height="1.26" position="-0.635 0 0" rotation="0 90 0" material="src: url(${escapeAttribute(dashboardData.initiativeDetail.image)}); shader: flat; side: double; alphaTest: 0.01"></a-plane>
                    <a-plane width="1.26" height="1.26" position="0 0.635 0" rotation="-90 0 0" material="src: url(${escapeAttribute(dashboardData.initiativeDetail.image)}); shader: flat; side: double; alphaTest: 0.01"></a-plane>
                    <a-plane width="1.26" height="1.26" position="0 -0.635 0" rotation="90 0 0" material="src: url(${escapeAttribute(dashboardData.initiativeDetail.image)}); shader: flat; side: double; alphaTest: 0.01"></a-plane>
                </a-box>
              `
            : `<a-box width="1.28" height="1.28" depth="1.28" color="#3a102e" position="0 1.52 0" animation="property: rotation; to: 0 360 0; loop: true; dur: 20000; easing: linear"></a-box>`;

        const initiativeDetailScene = isInitiativeDetailScene ? `
            <a-cylinder radius="5.6" height="0.08" color="#07111a" opacity="0.98" position="0 0.02 0"></a-cylinder>
            <a-ring position="0 0.06 0" radius-inner="3.58" radius-outer="3.68" rotation="-90 0 0" color="#4d1739" material="opacity: 0.28"></a-ring>
            <a-ring position="0 0.061 0" radius-inner="1.02" radius-outer="1.1" rotation="-90 0 0" color="#f472b6" material="opacity: 0.18"></a-ring>
            ${initiativeDetailCenter}
            <a-text value="${dashboardData.initiativeDetail ? dashboardData.initiativeDetail.title : "Initiative Detail"}" width="3" align="center" color="#fdf2f8" position="-1.5 2.6 -1.48"></a-text>
            <a-text value="${dashboardData.initiativeDetail ? dashboardData.initiativeDetail.description : ""}" width="2.9" align="center" wrap-count="50" color="#fbcfe8" position="-1.45 2.22 -1.46"></a-text>
            ${initiativeDetailPanels}
        ` : "";

        const policyAreaCatalogCards = (dashboardData.policyAreaCatalog || []).map((area, index) => {
            const total = Math.max((dashboardData.policyAreaCatalog || []).length, 1);
            const angle = (360 / total) * index;
            const radians = angle * (Math.PI / 180);
            const radius = 4.9;
            const x = Math.sin(radians) * radius;
            const z = Math.cos(radians) * radius;
            const rotation = 180 + angle;
            const areaUrl = `/dashboard/statistics/policy-areas/${area.id}/?year=${encodeURIComponent(getDpmesState().year)}&quarter=${encodeURIComponent(getDpmesState().quarter)}`;
            const imageMarkup = area.image
                ? `
                    <a-plane width="1.7" height="0.68" position="0 0.16 0.082" material="src: url(${escapeAttribute(area.image)}); shader: flat; side: double"></a-plane>
                    <a-plane width="1.7" height="0.68" position="0 0.16 -0.082" rotation="0 180 0" material="src: url(${escapeAttribute(area.image)}); shader: flat; side: double"></a-plane>
                  `
                : `
                    <a-plane width="1.7" height="0.68" position="0 0.16 0.082" material="color: #173447; opacity: 0.92; side: double"></a-plane>
                    <a-plane width="1.7" height="0.68" position="0 0.16 -0.082" rotation="0 180 0" material="color: #173447; opacity: 0.92; side: double"></a-plane>
                  `;
            return `
                <a-entity position="${x.toFixed(2)} 1.18 ${z.toFixed(2)}" rotation="0 ${rotation.toFixed(2)} 0">
                    <a-box class="interactive" page-link="url: ${areaUrl}; title: ${area.title}; target: vr" width="1.82" height="1.06" depth="0.14" material="color: #10202f; opacity: 0.98"></a-box>
                    ${imageMarkup}
                    <a-ring radius-inner="0.38" radius-outer="0.44" color="${area.color}" material="opacity: 0.22" position="0 0.18 0.086"></a-ring>
                    <a-ring radius-inner="0.38" radius-outer="0.44" color="${area.color}" material="opacity: 0.22" position="0 0.18 -0.086" rotation="0 180 0"></a-ring>
                    <a-plane width="1.52" height="0.34" position="0 -0.28 0.088" material="color: #08111a; opacity: 0.9; side: double"></a-plane>
                    <a-plane width="1.52" height="0.34" position="0 -0.28 -0.088" rotation="0 180 0" material="color: #08111a; opacity: 0.9; side: double"></a-plane>
                    <a-text value="${escapeAttribute(area.title)}" width="1.12" wrap-count="18" align="center" color="#ffffff" position="-0.54 0.02 0.094"></a-text>
                    <a-text value="${escapeAttribute(area.title)}" width="1.12" wrap-count="18" align="center" color="#ffffff" position="0.54 0.02 -0.094" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(area.score)}" width="0.92" align="center" color="#8ef1e5" position="-0.44 -0.24 0.094"></a-text>
                    <a-text value="${escapeAttribute(area.score)}" width="0.92" align="center" color="#8ef1e5" position="0.44 -0.24 -0.094" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(area.goals)}" width="0.92" align="center" color="#7dd3fc" position="-0.44 -0.4 0.094"></a-text>
                    <a-text value="${escapeAttribute(area.goals)}" width="0.92" align="center" color="#7dd3fc" position="0.44 -0.4 -0.094" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(area.subtitle)}" width="0.92" align="center" color="#cbd5e1" position="-0.44 -0.56 0.094"></a-text>
                    <a-text value="${escapeAttribute(area.subtitle)}" width="0.92" align="center" color="#cbd5e1" position="0.44 -0.56 -0.094" rotation="0 180 0"></a-text>
                </a-entity>
            `;
        }).join("");

        const policyAreaCatalogScene = isPolicyAreaCatalogScene ? `
            <a-cylinder radius="6.2" height="0.08" color="#07111a" opacity="0.98" position="0 0.02 0"></a-cylinder>
            <a-ring position="0 0.06 0" radius-inner="4.8" radius-outer="4.94" rotation="-90 0 0" color="#173447" material="opacity: 0.3"></a-ring>
            <a-text value="Policy Area Catalog" width="2.4" align="center" color="#f8fafc" position="0 2.42 -1.4"></a-text>
            <a-text value="Turn around to inspect all policy areas and open one to continue into goals." width="3.8" align="center" wrap-count="56" color="#cbd5e1" position="-1.9 2.06 -1.4"></a-text>
            ${policyAreaCatalogCards}
        ` : "";

        const ministryCatalogCards = (dashboardData.ministryCatalog || []).map((ministry, index) => {
            const total = Math.max((dashboardData.ministryCatalog || []).length, 1);
            const angle = (360 / total) * index;
            const radians = angle * (Math.PI / 180);
            const radius = 4.9;
            const x = Math.sin(radians) * radius;
            const z = Math.cos(radians) * radius;
            const rotation = 180 + angle;
            const url = `/dashboard/statistics/public-bodies/${ministry.id}/?year=${encodeURIComponent(getDpmesState().year)}&quarter=${encodeURIComponent(getDpmesState().quarter)}`;
            const imageMarkup = ministry.image
                ? `
                    <a-plane width="1.7" height="0.68" position="0 0.16 0.082" material="src: url(${escapeAttribute(ministry.image)}); shader: flat; side: double"></a-plane>
                    <a-plane width="1.7" height="0.68" position="0 0.16 -0.082" rotation="0 180 0" material="src: url(${escapeAttribute(ministry.image)}); shader: flat; side: double"></a-plane>
                  `
                : `
                    <a-plane width="1.7" height="0.68" position="0 0.16 0.082" material="color: #173447; opacity: 0.92; side: double"></a-plane>
                    <a-plane width="1.7" height="0.68" position="0 0.16 -0.082" rotation="0 180 0" material="color: #173447; opacity: 0.92; side: double"></a-plane>
                  `;
            return `
                <a-entity position="${x.toFixed(2)} 1.18 ${z.toFixed(2)}" rotation="0 ${rotation.toFixed(2)} 0">
                    <a-box class="interactive" page-link="url: ${url}; title: ${ministry.title}; target: vr" width="1.82" height="1.06" depth="0.14" material="color: #10202f; opacity: 0.98"></a-box>
                    ${imageMarkup}
                    <a-ring radius-inner="0.38" radius-outer="0.44" color="${ministry.color}" material="opacity: 0.22" position="0 0.18 0.086"></a-ring>
                    <a-ring radius-inner="0.38" radius-outer="0.44" color="${ministry.color}" material="opacity: 0.22" position="0 0.18 -0.086" rotation="0 180 0"></a-ring>
                    <a-plane width="1.52" height="0.34" position="0 -0.28 0.088" material="color: #08111a; opacity: 0.9; side: double"></a-plane>
                    <a-plane width="1.52" height="0.34" position="0 -0.28 -0.088" rotation="0 180 0" material="color: #08111a; opacity: 0.9; side: double"></a-plane>
                    <a-text value="${escapeAttribute(ministry.title)}" width="1.08" wrap-count="18" align="center" color="#ffffff" position="-0.52 0.02 0.094"></a-text>
                    <a-text value="${escapeAttribute(ministry.title)}" width="1.08" wrap-count="18" align="center" color="#ffffff" position="0.52 0.02 -0.094" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(ministry.score)}" width="0.9" align="center" color="#8ef1e5" position="-0.44 -0.24 0.094"></a-text>
                    <a-text value="${escapeAttribute(ministry.score)}" width="0.9" align="center" color="#8ef1e5" position="0.44 -0.24 -0.094" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(ministry.indicators)}" width="0.92" align="center" color="#7dd3fc" position="-0.44 -0.42 0.094"></a-text>
                    <a-text value="${escapeAttribute(ministry.indicators)}" width="0.92" align="center" color="#7dd3fc" position="0.44 -0.42 -0.094" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(ministry.code)}" width="0.8" align="center" color="#cbd5e1" position="-0.38 -0.58 0.094"></a-text>
                    <a-text value="${escapeAttribute(ministry.code)}" width="0.8" align="center" color="#cbd5e1" position="0.38 -0.58 -0.094" rotation="0 180 0"></a-text>
                </a-entity>
            `;
        }).join("");

        const ministryCatalogScene = isMinistryCatalogScene ? `
            <a-cylinder radius="6.2" height="0.08" color="#07111a" opacity="0.98" position="0 0.02 0"></a-cylinder>
            <a-ring position="0 0.06 0" radius-inner="4.8" radius-outer="4.94" rotation="-90 0 0" color="#173447" material="opacity: 0.3"></a-ring>
            <a-text value="Ministry Catalog" width="2.4" align="center" color="#f8fafc" position="0 2.42 -1.4"></a-text>
            <a-text value="Turn around to inspect all ministries and open one to continue into goals." width="3.8" align="center" wrap-count="56" color="#cbd5e1" position="-1.9 2.06 -1.4"></a-text>
            ${ministryCatalogCards}
        ` : "";

        const topicDetailCategoryPods = (dashboardData.topicCategories || []).map((category, index) => {
            const angle = (360 / Math.max((dashboardData.topicCategories || []).length, 1)) * index;
            const radians = angle * (Math.PI / 180);
            const radius = 2.7;
            const x = Math.sin(radians) * radius;
            const z = Math.cos(radians) * radius;
            const rotation = 180 + angle;
            return `
                <a-entity position="${x.toFixed(2)} 1.18 ${z.toFixed(2)}" rotation="0 ${rotation.toFixed(2)} 0">
                    <a-box class="interactive" page-link="url: /dashboard/data/${dashboardData.topicDetail ? dashboardData.topicDetail.id : ""}/; title: ${category.title}; target: vr-category; categoryId: ${category.id}" width="1.16" height="0.72" depth="0.12" material="color: #10202f; opacity: 0.98"></a-box>
                    <a-ring radius-inner="0.16" radius-outer="0.19" color="#5de4c7" material="opacity: 0.22" position="0 0.18 0.07"></a-ring>
                    <a-ring radius-inner="0.16" radius-outer="0.19" color="#5de4c7" material="opacity: 0.22" position="0 0.18 -0.07" rotation="0 180 0"></a-ring>
                    <a-text value="${category.title}" width="1" wrap-count="16" align="center" color="#f8fafc" position="-0.48 0.1 0.07"></a-text>
                    <a-text value="${category.title}" width="1" wrap-count="16" align="center" color="#f8fafc" position="0.48 0.1 -0.07" rotation="0 180 0"></a-text>
                    <a-text value="${category.code}" width="0.72" align="center" color="#8ef1e5" position="-0.34 -0.12 0.07"></a-text>
                    <a-text value="${category.code}" width="0.72" align="center" color="#8ef1e5" position="0.34 -0.12 -0.07" rotation="0 180 0"></a-text>
                    <a-text value="${category.indicatorCount} indicators" width="0.86" align="center" color="#7dd3fc" position="-0.42 -0.28 0.07"></a-text>
                    <a-text value="${category.indicatorCount} indicators" width="0.86" align="center" color="#7dd3fc" position="0.42 -0.28 -0.07" rotation="0 180 0"></a-text>
                </a-entity>
            `;
        }).join("");

        const topicDetailScene = isTopicDetailScene ? `
            <a-cylinder radius="5.2" height="0.08" color="#07111a" opacity="0.98" position="0 0.02 0"></a-cylinder>
            <a-ring position="0 0.06 0" radius-inner="3.12" radius-outer="3.24" rotation="-90 0 0" color="#173447" material="opacity: 0.28"></a-ring>
            <a-ring position="0 0.061 0" radius-inner="1.1" radius-outer="1.16" rotation="-90 0 0" color="#5de4c7" material="opacity: 0.12"></a-ring>
            <a-entity position="0 1.58 0">
                <a-box width="1.1" height="1.1" depth="1.1" color="#10202f" material="opacity: 0.96"></a-box>
                <a-entity animation="property: rotation; to: 0 360 0; loop: true; dur: 16000; easing: linear">
                    ${
                        dashboardData.topicDetail && dashboardData.topicDetail.image
                            ? `
                                <a-plane width="1.08" height="1.08" position="0 0 0.61" material="src: url(${escapeAttribute(dashboardData.topicDetail.image)}); shader: flat; side: double"></a-plane>
                                <a-plane width="1.08" height="1.08" position="0 0 -0.61" rotation="0 180 0" material="src: url(${escapeAttribute(dashboardData.topicDetail.image)}); shader: flat; side: double"></a-plane>
                                <a-plane width="1.08" height="1.08" position="0.61 0 0" rotation="0 -90 0" material="src: url(${escapeAttribute(dashboardData.topicDetail.image)}); shader: flat; side: double"></a-plane>
                                <a-plane width="1.08" height="1.08" position="-0.61 0 0" rotation="0 90 0" material="src: url(${escapeAttribute(dashboardData.topicDetail.image)}); shader: flat; side: double"></a-plane>
                                <a-plane width="1.08" height="1.08" position="0 0.61 0" rotation="-90 0 0" material="src: url(${escapeAttribute(dashboardData.topicDetail.image)}); shader: flat; side: double"></a-plane>
                                <a-plane width="1.08" height="1.08" position="0 -0.61 0" rotation="90 0 0" material="src: url(${escapeAttribute(dashboardData.topicDetail.image)}); shader: flat; side: double"></a-plane>
                              `
                            : ""
                    }
                </a-entity>
                <a-ring radius-inner="0.82" radius-outer="0.9" color="#5de4c7" material="opacity: 0.18" rotation="-90 0 0" position="0 -0.7 0"></a-ring>
                <a-text value="${(dashboardData.topicDetail && dashboardData.topicDetail.title) || "Topic Detail"}" width="2.7" align="center" color="#ffffff" position="-1.28 0.98 0"></a-text>
                <a-text value="${dashboardData.topicDetail ? `${dashboardData.topicDetail.categoryCount} categories | ${dashboardData.topicDetail.kpiCount} indicators` : ""}" width="2.2" align="center" color="#8ef1e5" position="-1.08 -1.05 0"></a-text>
                <a-text value="${dashboardData.topicDetail ? dashboardData.topicDetail.code : ""}" width="1.1" align="center" color="#7dd3fc" position="-0.52 -0.84 0"></a-text>
                <a-text value="${(dashboardData.topicDetail && dashboardData.topicDetail.description) || ""}" width="2.5" align="center" wrap-count="44" color="#cbd5e1" position="-1.22 -1.38 0"></a-text>
            </a-entity>
            ${topicDetailCategoryPods}
        ` : "";

        const policyAreaGoalCards = (dashboardData.policyAreaGoals || []).map((goal, index) => {
            const total = Math.max((dashboardData.policyAreaGoals || []).length, 1);
            const angle = (360 / total) * index;
            const radians = angle * (Math.PI / 180);
            const radius = 3.35;
            const x = Math.sin(radians) * radius;
            const z = Math.cos(radians) * radius;
            const rotation = 180 + angle;
            const goalUrl = `/dashboard/statistics/goals/${goal.id}/?year=${encodeURIComponent(getDpmesState().year)}&quarter=${encodeURIComponent(getDpmesState().quarter)}`;
            return `
                <a-entity position="${x.toFixed(2)} 1.22 ${z.toFixed(2)}" rotation="0 ${rotation.toFixed(2)} 0">
                    <a-box class="interactive" page-link="url: ${goalUrl}; title: ${goal.title}; target: vr" width="1.48" height="0.92" depth="0.12" material="color: #10202f; opacity: 0.98"></a-box>
                    <a-ring radius-inner="0.18" radius-outer="0.22" color="${goal.color}" material="opacity: 0.24" position="0 0.22 0.07"></a-ring>
                    <a-ring radius-inner="0.18" radius-outer="0.22" color="${goal.color}" material="opacity: 0.24" position="0 0.22 -0.07" rotation="0 180 0"></a-ring>
                    <a-text value="${escapeAttribute(goal.title)}" width="1.1" wrap-count="18" align="center" color="#ffffff" position="-0.54 0.16 0.07"></a-text>
                    <a-text value="${escapeAttribute(goal.title)}" width="1.1" wrap-count="18" align="center" color="#ffffff" position="0.54 0.16 -0.07" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(goal.score)}" width="0.76" align="center" color="#8ef1e5" position="-0.36 -0.12 0.07"></a-text>
                    <a-text value="${escapeAttribute(goal.score)}" width="0.76" align="center" color="#8ef1e5" position="0.36 -0.12 -0.07" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(goal.kras)}" width="0.7" align="center" color="#7dd3fc" position="-0.32 -0.28 0.07"></a-text>
                    <a-text value="${escapeAttribute(goal.kras)}" width="0.7" align="center" color="#7dd3fc" position="0.32 -0.28 -0.07" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(goal.indicators)}" width="0.86" align="center" color="#cbd5e1" position="-0.42 -0.44 0.07"></a-text>
                    <a-text value="${escapeAttribute(goal.indicators)}" width="0.86" align="center" color="#cbd5e1" position="0.42 -0.44 -0.07" rotation="0 180 0"></a-text>
                </a-entity>
            `;
        }).join("");

        const policyAreaDetailScene = isPolicyAreaDetailScene ? `
            <a-cylinder radius="5.2" height="0.08" color="#07111a" opacity="0.98" position="0 0.02 0"></a-cylinder>
            <a-ring position="0 0.06 0" radius-inner="3.22" radius-outer="3.34" rotation="-90 0 0" color="#173447" material="opacity: 0.28"></a-ring>
            <a-entity position="0 1.58 0">
                ${
                    dashboardData.policyAreaDetail && dashboardData.policyAreaDetail.image
                        ? `
                            <a-box width="1.12" height="1.12" depth="1.12" color="#10202f" material="opacity: 0.98"></a-box>
                            <a-entity animation="property: rotation; to: 0 360 0; loop: true; dur: 16000; easing: linear">
                                <a-plane width="1.1" height="1.1" position="0 0 0.62" material="src: url(${escapeAttribute(dashboardData.policyAreaDetail.image)}); shader: flat; side: double"></a-plane>
                                <a-plane width="1.1" height="1.1" position="0 0 -0.62" rotation="0 180 0" material="src: url(${escapeAttribute(dashboardData.policyAreaDetail.image)}); shader: flat; side: double"></a-plane>
                                <a-plane width="1.1" height="1.1" position="0.62 0 0" rotation="0 -90 0" material="src: url(${escapeAttribute(dashboardData.policyAreaDetail.image)}); shader: flat; side: double"></a-plane>
                                <a-plane width="1.1" height="1.1" position="-0.62 0 0" rotation="0 90 0" material="src: url(${escapeAttribute(dashboardData.policyAreaDetail.image)}); shader: flat; side: double"></a-plane>
                                <a-plane width="1.1" height="1.1" position="0 0.62 0" rotation="-90 0 0" material="src: url(${escapeAttribute(dashboardData.policyAreaDetail.image)}); shader: flat; side: double"></a-plane>
                                <a-plane width="1.1" height="1.1" position="0 -0.62 0" rotation="90 0 0" material="src: url(${escapeAttribute(dashboardData.policyAreaDetail.image)}); shader: flat; side: double"></a-plane>
                            </a-entity>
                          `
                        : `<a-box width="1.12" height="1.12" depth="1.12" color="#10202f" material="opacity: 0.98"></a-box>`
                }
                <a-ring radius-inner="0.88" radius-outer="0.96" color="${dashboardData.policyAreaDetail ? dashboardData.policyAreaDetail.color : "#5d9444"}" material="opacity: 0.18" rotation="-90 0 0" position="0 -0.56 0"></a-ring>
            </a-entity>
            ${policyAreaGoalCards}
        ` : "";

        const policyGoalKraCards = (dashboardData.policyGoalKras || []).map((kra, index) => {
            const total = Math.max((dashboardData.policyGoalKras || []).length, 1);
            const angle = (360 / total) * index;
            const radians = angle * (Math.PI / 180);
            const radius = 3.3;
            const x = Math.sin(radians) * radius;
            const z = Math.cos(radians) * radius;
            const rotation = 180 + angle;
            const goalUrl = String(dashboardData.sourcePage && dashboardData.sourcePage.url || "").split("?")[0] + `?year=${encodeURIComponent(getDpmesState().year)}&quarter=${encodeURIComponent(getDpmesState().quarter)}`;
            return `
                <a-entity position="${x.toFixed(2)} 1.18 ${z.toFixed(2)}" rotation="0 ${rotation.toFixed(2)} 0">
                    <a-box class="interactive" page-link="url: ${goalUrl}; title: ${kra.title}; target: vr-kra; categoryId: ${kra.id}" width="1.44" height="0.92" depth="0.12" material="color: #10202f; opacity: 0.98"></a-box>
                    <a-ring radius-inner="0.16" radius-outer="0.2" color="${kra.color}" material="opacity: 0.22" position="0 0.2 0.07"></a-ring>
                    <a-ring radius-inner="0.16" radius-outer="0.2" color="${kra.color}" material="opacity: 0.22" position="0 0.2 -0.07" rotation="0 180 0"></a-ring>
                    <a-text value="${escapeAttribute(kra.title)}" width="1.06" wrap-count="16" align="center" color="#ffffff" position="-0.52 0.16 0.07"></a-text>
                    <a-text value="${escapeAttribute(kra.title)}" width="1.06" wrap-count="16" align="center" color="#ffffff" position="0.52 0.16 -0.07" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(kra.score)}" width="0.76" align="center" color="#8ef1e5" position="-0.36 -0.12 0.07"></a-text>
                    <a-text value="${escapeAttribute(kra.score)}" width="0.76" align="center" color="#8ef1e5" position="0.36 -0.12 -0.07" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(kra.indicators)}" width="0.9" align="center" color="#7dd3fc" position="-0.44 -0.32 0.07"></a-text>
                    <a-text value="${escapeAttribute(kra.indicators)}" width="0.9" align="center" color="#7dd3fc" position="0.44 -0.32 -0.07" rotation="0 180 0"></a-text>
                </a-entity>
            `;
        }).join("");

        const policyGoalDetailScene = isPolicyGoalDetailScene ? `
            <a-cylinder radius="5.2" height="0.08" color="#07111a" opacity="0.98" position="0 0.02 0"></a-cylinder>
            <a-ring position="0 0.06 0" radius-inner="3.18" radius-outer="3.28" rotation="-90 0 0" color="#173447" material="opacity: 0.28"></a-ring>
            <a-entity position="0 1.58 0">
                <a-box width="1.02" height="1.02" depth="1.02" color="#10202f" material="opacity: 0.96"></a-box>
                <a-ring radius-inner="0.84" radius-outer="0.92" color="${dashboardData.policyGoalDetail ? dashboardData.policyGoalDetail.color : "#5d9444"}" material="opacity: 0.18" rotation="-90 0 0" position="0 -0.62 0"></a-ring>
                <a-text value="${dashboardData.policyGoalDetail ? dashboardData.policyGoalDetail.title : "Goal Detail"}" width="2.6" align="center" color="#ffffff" position="-1.24 0.62 0"></a-text>
                <a-text value="${dashboardData.policyGoalDetail ? dashboardData.policyGoalDetail.score : "--"}" width="1.1" align="center" color="#8ef1e5" position="-0.54 0.1 0"></a-text>
                <a-text value="Key result areas around you" width="1.8" align="center" color="#cbd5e1" position="-0.9 -0.42 0"></a-text>
            </a-entity>
            ${policyGoalKraCards}
        ` : "";

        const ministryGoalCards = (dashboardData.ministryGoals || []).map((goal, index) => {
            const total = Math.max((dashboardData.ministryGoals || []).length, 1);
            const angle = (360 / total) * index;
            const radians = angle * (Math.PI / 180);
            const radius = 3.35;
            const x = Math.sin(radians) * radius;
            const z = Math.cos(radians) * radius;
            const rotation = 180 + angle;
            const url = `/dashboard/statistics/goals/${goal.id}/?ministry_id=${encodeURIComponent(dashboardData.ministryDetail ? dashboardData.ministryDetail.id : "")}&year=${encodeURIComponent(getDpmesState().year)}&quarter=${encodeURIComponent(getDpmesState().quarter)}`;
            return `
                <a-entity position="${x.toFixed(2)} 1.22 ${z.toFixed(2)}" rotation="0 ${rotation.toFixed(2)} 0">
                    <a-box class="interactive" page-link="url: ${url}; title: ${goal.title}; target: vr" width="1.5" height="0.96" depth="0.12" material="color: #10202f; opacity: 0.98"></a-box>
                    <a-ring radius-inner="0.18" radius-outer="0.22" color="${goal.color}" material="opacity: 0.24" position="0 0.24 0.07"></a-ring>
                    <a-ring radius-inner="0.18" radius-outer="0.22" color="${goal.color}" material="opacity: 0.24" position="0 0.24 -0.07" rotation="0 180 0"></a-ring>
                    <a-text value="${escapeAttribute(goal.title)}" width="1.06" wrap-count="16" align="center" color="#ffffff" position="-0.52 0.18 0.07"></a-text>
                    <a-text value="${escapeAttribute(goal.title)}" width="1.06" wrap-count="16" align="center" color="#ffffff" position="0.52 0.18 -0.07" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(goal.score)}" width="0.78" align="center" color="#8ef1e5" position="-0.36 -0.1 0.07"></a-text>
                    <a-text value="${escapeAttribute(goal.score)}" width="0.78" align="center" color="#8ef1e5" position="0.36 -0.1 -0.07" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(goal.kras)}" width="0.72" align="center" color="#7dd3fc" position="-0.32 -0.28 0.07"></a-text>
                    <a-text value="${escapeAttribute(goal.kras)}" width="0.72" align="center" color="#7dd3fc" position="0.32 -0.28 -0.07" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(goal.policyArea)}" width="0.9" wrap-count="18" align="center" color="#cbd5e1" position="-0.44 -0.46 0.07"></a-text>
                    <a-text value="${escapeAttribute(goal.policyArea)}" width="0.9" wrap-count="18" align="center" color="#cbd5e1" position="0.44 -0.46 -0.07" rotation="0 180 0"></a-text>
                </a-entity>
            `;
        }).join("");

        const ministryDetailScene = isMinistryDetailScene ? `
            <a-cylinder radius="5.2" height="0.08" color="#07111a" opacity="0.98" position="0 0.02 0"></a-cylinder>
            <a-ring position="0 0.06 0" radius-inner="3.22" radius-outer="3.34" rotation="-90 0 0" color="#173447" material="opacity: 0.28"></a-ring>
            <a-entity position="0 1.58 0">
                ${
                    dashboardData.ministryDetail && dashboardData.ministryDetail.image
                        ? `
                            <a-box width="1.12" height="1.12" depth="1.12" color="#10202f" material="opacity: 0.98"></a-box>
                            <a-entity animation="property: rotation; to: 0 360 0; loop: true; dur: 16000; easing: linear">
                                <a-plane width="1.1" height="1.1" position="0 0 0.62" material="src: url(${escapeAttribute(dashboardData.ministryDetail.image)}); shader: flat; side: double"></a-plane>
                                <a-plane width="1.1" height="1.1" position="0 0 -0.62" rotation="0 180 0" material="src: url(${escapeAttribute(dashboardData.ministryDetail.image)}); shader: flat; side: double"></a-plane>
                                <a-plane width="1.1" height="1.1" position="0.62 0 0" rotation="0 -90 0" material="src: url(${escapeAttribute(dashboardData.ministryDetail.image)}); shader: flat; side: double"></a-plane>
                                <a-plane width="1.1" height="1.1" position="-0.62 0 0" rotation="0 90 0" material="src: url(${escapeAttribute(dashboardData.ministryDetail.image)}); shader: flat; side: double"></a-plane>
                                <a-plane width="1.1" height="1.1" position="0 0.62 0" rotation="-90 0 0" material="src: url(${escapeAttribute(dashboardData.ministryDetail.image)}); shader: flat; side: double"></a-plane>
                                <a-plane width="1.1" height="1.1" position="0 -0.62 0" rotation="90 0 0" material="src: url(${escapeAttribute(dashboardData.ministryDetail.image)}); shader: flat; side: double"></a-plane>
                            </a-entity>
                          `
                        : `<a-box width="1.12" height="1.12" depth="1.12" color="#10202f" material="opacity: 0.98"></a-box>`
                }
                <a-ring radius-inner="0.88" radius-outer="0.96" color="${dashboardData.ministryDetail ? dashboardData.ministryDetail.color : "#5d9444"}" material="opacity: 0.18" rotation="-90 0 0" position="0 -0.56 0"></a-ring>
                <a-text value="${dashboardData.ministryDetail ? dashboardData.ministryDetail.title : "Ministry Detail"}" width="2.6" align="center" color="#ffffff" position="-1.24 0.48 0"></a-text>
                <a-text value="${dashboardData.ministryDetail ? dashboardData.ministryDetail.score : "--"}" width="1.2" align="center" color="#8ef1e5" position="-0.58 0.06 0"></a-text>
                <a-text value="${dashboardData.ministryDetail ? dashboardData.ministryDetail.periodLabel : ""}" width="1.12" align="center" color="#7dd3fc" position="-0.56 -0.18 0"></a-text>
                <a-text value="Goals around you" width="1.6" align="center" color="#cbd5e1" position="-0.78 -0.46 0"></a-text>
            </a-entity>
            ${ministryGoalCards}
        ` : "";

        const ministryGoalKraCards = (dashboardData.ministryGoalKras || []).map((kra, index) => {
            const total = Math.max((dashboardData.ministryGoalKras || []).length, 1);
            const angle = (360 / total) * index;
            const radians = angle * (Math.PI / 180);
            const radius = 3.3;
            const x = Math.sin(radians) * radius;
            const z = Math.cos(radians) * radius;
            const rotation = 180 + angle;
            const url = String(dashboardData.sourcePage && dashboardData.sourcePage.url || "").split("?")[0] + `?ministry_id=${encodeURIComponent(getSourceQueryParams().get("ministry_id") || "")}&year=${encodeURIComponent(getDpmesState().year)}&quarter=${encodeURIComponent(getDpmesState().quarter)}`;
            return `
                <a-entity position="${x.toFixed(2)} 1.18 ${z.toFixed(2)}" rotation="0 ${rotation.toFixed(2)} 0">
                    <a-box class="interactive" page-link="url: ${url}; title: ${kra.title}; target: vr-kra; categoryId: ${kra.id}" width="1.44" height="0.92" depth="0.12" material="color: #10202f; opacity: 0.98"></a-box>
                    <a-ring radius-inner="0.16" radius-outer="0.2" color="${kra.color}" material="opacity: 0.22" position="0 0.2 0.07"></a-ring>
                    <a-ring radius-inner="0.16" radius-outer="0.2" color="${kra.color}" material="opacity: 0.22" position="0 0.2 -0.07" rotation="0 180 0"></a-ring>
                    <a-text value="${escapeAttribute(kra.title)}" width="1.06" wrap-count="16" align="center" color="#ffffff" position="-0.52 0.16 0.07"></a-text>
                    <a-text value="${escapeAttribute(kra.title)}" width="1.06" wrap-count="16" align="center" color="#ffffff" position="0.52 0.16 -0.07" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(kra.score)}" width="0.76" align="center" color="#8ef1e5" position="-0.36 -0.12 0.07"></a-text>
                    <a-text value="${escapeAttribute(kra.score)}" width="0.76" align="center" color="#8ef1e5" position="0.36 -0.12 -0.07" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(kra.indicators)}" width="0.9" align="center" color="#7dd3fc" position="-0.44 -0.32 0.07"></a-text>
                    <a-text value="${escapeAttribute(kra.indicators)}" width="0.9" align="center" color="#7dd3fc" position="0.44 -0.32 -0.07" rotation="0 180 0"></a-text>
                </a-entity>
            `;
        }).join("");

        const ministryGoalDetailScene = isMinistryGoalDetailScene ? `
            <a-cylinder radius="5.2" height="0.08" color="#07111a" opacity="0.98" position="0 0.02 0"></a-cylinder>
            <a-ring position="0 0.06 0" radius-inner="3.18" radius-outer="3.28" rotation="-90 0 0" color="#173447" material="opacity: 0.28"></a-ring>
            <a-entity position="0 1.58 0">
                <a-box width="1.02" height="1.02" depth="1.02" color="#10202f" material="opacity: 0.96"></a-box>
                <a-ring radius-inner="0.84" radius-outer="0.92" color="${dashboardData.ministryGoalDetail ? dashboardData.ministryGoalDetail.color : "#5d9444"}" material="opacity: 0.18" rotation="-90 0 0" position="0 -0.62 0"></a-ring>
                <a-text value="${dashboardData.ministryGoalDetail ? dashboardData.ministryGoalDetail.title : "Ministry Goal Detail"}" width="2.6" align="center" color="#ffffff" position="-1.24 0.62 0"></a-text>
                <a-text value="${dashboardData.ministryGoalDetail ? dashboardData.ministryGoalDetail.score : "--"}" width="1.1" align="center" color="#8ef1e5" position="-0.54 0.1 0"></a-text>
                <a-text value="Key result areas around you" width="1.8" align="center" color="#cbd5e1" position="-0.9 -0.42 0"></a-text>
            </a-entity>
            ${ministryGoalKraCards}
        ` : "";

        const categoryIndicatorCards = (dashboardData.categoryDetail && dashboardData.categoryDetail.indicators || []).map((indicator, index) => {
            const total = Math.max((dashboardData.categoryDetail && dashboardData.categoryDetail.indicators || []).length, 1);
            const cardsPerRing = total > 12 ? 7 : total > 7 ? 5 : total;
            const ringIndex = Math.floor(index / cardsPerRing);
            const ringCount = Math.ceil(total / cardsPerRing);
            const ringItems = Math.min(cardsPerRing, total - ringIndex * cardsPerRing);
            const indexInRing = index % cardsPerRing;
            const angleOffset = ringIndex % 2 === 0 ? 0 : 360 / Math.max(ringItems * 2, 2);
            const angle = (360 / Math.max(ringItems, 1)) * indexInRing + angleOffset;
            const radians = angle * (Math.PI / 180);
            const radius = Math.min(8.6, 3.7 + Math.max(0, ringItems - 4) * 0.36 + ringIndex * 1.9);
            const cardScale = Math.max(0.6, 1 - Math.max(0, total - 5) * 0.038 - ringIndex * 0.05);
            const cardWidth = (2.28 * cardScale).toFixed(3);
            const cardHeight = (1.02 * cardScale).toFixed(3);
            const panelWidth = (2.12 * cardScale).toFixed(3);
            const panelHeight = (0.86 * cardScale).toFixed(3);
            const chartWidth = (1.02 * cardScale).toFixed(3);
            const chartHeight = (0.52 * cardScale).toFixed(3);
            const baseRadius = (0.92 * cardScale).toFixed(3);
            const x = Math.sin(radians) * radius;
            const z = Math.cos(radians) * radius;
            const y = 1.36 + ringIndex * 0.6 + (indexInRing % 2 === 0 ? 0.14 : -0.08);
            const rotationY = 180 + angle;
            const bars = (indicator.points || []).slice(-5);
            const maxValue = Math.max(...bars.map((item) => Number(item && item.value || 0)), 1);
            const graphBars = bars.map((point, barIndex) => {
                const normalized = Math.max(0.18, Number(point && point.value || 0) / maxValue);
                const height = (normalized * 0.56).toFixed(3);
                const yPos = (-0.04 + normalized * 0.28).toFixed(3);
                const xPos = (-0.44 + barIndex * 0.22).toFixed(3);
                return `
                    <a-cylinder radius="0.05" height="${height}" color="${barIndex % 2 === 0 ? "#5de4c7" : "#7dd3fc"}" position="${xPos} ${yPos} 0.1"></a-cylinder>
                    <a-box
                        width="0.12"
                        depth="0.08"
                        height="0.02"
                        color="#08111a"
                        position="${xPos} -0.34 0.08">
                    </a-box>
                    <a-text value="${escapeAttribute(truncate(point.label, 10))}" width="0.56" align="center" color="#e2e8f0" position="${(Number(xPos) - 0.16).toFixed(3)} -0.28 0.1"></a-text>
                `;
            }).join("");
            const graphBarsBack = bars.map((point, barIndex) => {
                const normalized = Math.max(0.18, Number(point && point.value || 0) / maxValue);
                const height = (normalized * 0.56).toFixed(3);
                const yPos = (-0.04 + normalized * 0.28).toFixed(3);
                const xPos = (0.44 - barIndex * 0.22).toFixed(3);
                return `
                    <a-cylinder radius="0.05" height="${height}" color="${barIndex % 2 === 0 ? "#5de4c7" : "#7dd3fc"}" position="${xPos} ${yPos} -0.1"></a-cylinder>
                    <a-box
                        width="0.12"
                        depth="0.08"
                        height="0.02"
                        color="#08111a"
                        position="${xPos} -0.34 -0.08">
                    </a-box>
                    <a-text value="${escapeAttribute(truncate(point.label, 10))}" width="0.56" align="center" color="#e2e8f0" position="${(Number(xPos) - 0.16).toFixed(3)} -0.28 -0.1" rotation="0 180 0"></a-text>
                `;
            }).join("");

            return `
                <a-entity position="${x.toFixed(2)} ${y.toFixed(2)} ${z.toFixed(2)}" rotation="-6 ${rotationY.toFixed(2)} 0">
                    <a-cylinder radius="${baseRadius}" height="0.04" color="#07111a" position="0 ${(-0.52 * cardScale).toFixed(3)} 0" rotation="90 0 0"></a-cylinder>
                    <a-box width="${cardWidth}" height="${cardHeight}" depth="0.16" color="#07111a" material="metalness: 0.22; roughness: 0.24; opacity: 0.98"></a-box>
                    <a-box width="${panelWidth}" height="${panelHeight}" depth="0.04" color="#112638" position="0 ${(0.04 * cardScale).toFixed(3)} 0.081" material="opacity: 0.97"></a-box>
                    <a-box width="${panelWidth}" height="${panelHeight}" depth="0.04" color="#112638" position="0 ${(0.04 * cardScale).toFixed(3)} -0.081" material="opacity: 0.97"></a-box>
                    <a-ring radius-inner="${(0.78 * cardScale).toFixed(3)}" radius-outer="${(0.88 * cardScale).toFixed(3)}" color="#5de4c7" material="opacity: 0.1" position="0 0 0.09"></a-ring>
                    <a-ring radius-inner="${(0.78 * cardScale).toFixed(3)}" radius-outer="${(0.88 * cardScale).toFixed(3)}" color="#5de4c7" material="opacity: 0.1" position="0 0 -0.09"></a-ring>
                    <a-plane width="${chartWidth}" height="${chartHeight}" color="#0b1622" material="opacity: 0.96" position="0 ${(-0.02 * cardScale).toFixed(3)} 0.1"></a-plane>
                    <a-plane width="${chartWidth}" height="${chartHeight}" color="#0b1622" material="opacity: 0.96" position="0 ${(-0.02 * cardScale).toFixed(3)} -0.1" rotation="0 180 0"></a-plane>
                    <a-text value="${escapeAttribute(indicator.title)}" width="${(0.82 * cardScale).toFixed(3)}" wrap-count="15" align="center" color="#ffffff" position="${(-0.41 * cardScale).toFixed(3)} ${(0.84 * cardScale).toFixed(3)} 0.1"></a-text>
                    <a-text value="${escapeAttribute(indicator.title)}" width="${(0.82 * cardScale).toFixed(3)}" wrap-count="15" align="center" color="#ffffff" position="${(0.41 * cardScale).toFixed(3)} ${(0.84 * cardScale).toFixed(3)} -0.1" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(indicator.latestValue)}" width="${(1.2 * cardScale).toFixed(3)}" color="#d7fff5" position="${(-0.9 * cardScale).toFixed(3)} ${(-0.42 * cardScale).toFixed(3)} 0.1"></a-text>
                    <a-text value="${escapeAttribute(indicator.latestValue)}" width="${(1.2 * cardScale).toFixed(3)}" color="#d7fff5" position="${(0.9 * cardScale).toFixed(3)} ${(-0.42 * cardScale).toFixed(3)} -0.1" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(indicator.unit)}" width="${(0.94 * cardScale).toFixed(3)}" color="#c4e7ff" position="${(0.08 * cardScale).toFixed(3)} ${(-0.42 * cardScale).toFixed(3)} 0.1"></a-text>
                    <a-text value="${escapeAttribute(indicator.unit)}" width="${(0.94 * cardScale).toFixed(3)}" color="#c4e7ff" position="${(-0.08 * cardScale).toFixed(3)} ${(-0.42 * cardScale).toFixed(3)} -0.1" rotation="0 180 0"></a-text>
                    <a-text value="Recent 5" width="${(0.88 * cardScale).toFixed(3)}" color="#ffffff" position="${(0.06 * cardScale).toFixed(3)} ${(0.34 * cardScale).toFixed(3)} 0.1"></a-text>
                    <a-text value="Recent 5" width="${(0.88 * cardScale).toFixed(3)}" color="#ffffff" position="${(-0.06 * cardScale).toFixed(3)} ${(0.34 * cardScale).toFixed(3)} -0.1" rotation="0 180 0"></a-text>
                    ${graphBars || `<a-text value="No recent points" width="1.3" color="#cbd5e1" position="-0.42 -0.02 0.1"></a-text>`}
                    ${graphBarsBack || `<a-text value="No recent points" width="1.3" color="#cbd5e1" position="0.42 -0.02 -0.1" rotation="0 180 0"></a-text>`}
                </a-entity>
            `;
        }).join("");

        const categoryDetailScene = isCategoryDetailScene ? `
            <a-cylinder radius="5.8" height="0.08" color="#07111a" opacity="0.98" position="0 0.02 0"></a-cylinder>
            <a-cylinder radius="1.26" height="0.08" color="#0b1622" opacity="0.98" position="0 0.05 0"></a-cylinder>
            <a-ring position="0 0.06 0" radius-inner="3.42" radius-outer="3.56" rotation="-90 0 0" color="#173447" material="opacity: 0.28"></a-ring>
            <a-ring position="0 0.07 0" radius-inner="2.08" radius-outer="2.16" rotation="-90 0 0" color="#5de4c7" material="opacity: 0.14"></a-ring>
            <a-box width="3.9" height="0.88" depth="0.18" color="#0b1622" material="metalness: 0.18; roughness: 0.26; opacity: 0.96" position="0 2.44 -1.7" rotation="-6 0 0"></a-box>
            <a-ring radius-inner="0.34" radius-outer="0.42" color="#7dd3fc" material="opacity: 0.14" position="0 2.82 -1.58"></a-ring>
            <a-text value="${dashboardData.categoryDetail ? dashboardData.categoryDetail.title : "Category Detail"}" width="3" align="center" color="#ffffff" position="-1.5 2.62 -1.56"></a-text>
            <a-text value="${dashboardData.categoryDetail ? `${dashboardData.categoryDetail.topicTitle} | ${dashboardData.categoryDetail.code}` : ""}" width="2.5" align="center" color="#8ef1e5" position="-1.26 2.34 -1.54"></a-text>
            <a-text value="${dashboardData.categoryDetail ? `${dashboardData.categoryDetail.indicatorCount} indicators around you` : ""}" width="2.6" align="center" color="#7dd3fc" position="-1.3 2.08 -1.52"></a-text>
            ${categoryIndicatorCards || `<a-text value="No indicators available for this category." width="2.6" align="center" color="#cbd5e1" position="-1.28 1.44 -1.8"></a-text>`}
        ` : "";

        const policyKraIndicatorCards = (dashboardData.policyKraDetail && dashboardData.policyKraDetail.indicators || []).map((indicator, index) => {
            const total = Math.max((dashboardData.policyKraDetail && dashboardData.policyKraDetail.indicators || []).length, 1);
            const angle = (360 / total) * index;
            const radians = angle * (Math.PI / 180);
            const radius = total > 10 ? 4.2 : 3.55;
            const x = Math.sin(radians) * radius;
            const z = Math.cos(radians) * radius;
            const y = 1.48;
            const rotationY = 180 + angle;
            const points = (indicator.points || []).slice(-5);
            const maxValue = Math.max(...points.map((item) => Number(item && item.value || 0)), 1);
            const graphBars = points.map((point, barIndex) => {
                const normalized = Math.max(0.18, Number(point && point.value || 0) / maxValue);
                const height = (normalized * 0.54).toFixed(3);
                const yPos = (-0.04 + normalized * 0.27).toFixed(3);
                const xPos = (-0.42 + barIndex * 0.21).toFixed(3);
                return `
                    <a-cylinder radius="0.05" height="${height}" color="${barIndex % 2 === 0 ? "#5de4c7" : "#7dd3fc"}" position="${xPos} ${yPos} 0.1"></a-cylinder>
                    <a-text value="${escapeAttribute(truncate(point.label, 10))}" width="0.5" align="center" color="#e2e8f0" position="${(Number(xPos) - 0.14).toFixed(3)} -0.28 0.1"></a-text>
                `;
            }).join("");
            return `
                <a-entity position="${x.toFixed(2)} ${y.toFixed(2)} ${z.toFixed(2)}" rotation="-6 ${rotationY.toFixed(2)} 0">
                    <a-box width="2.18" height="1.02" depth="0.16" color="#07111a" material="metalness: 0.22; roughness: 0.24; opacity: 0.98"></a-box>
                    <a-box width="2.02" height="0.86" depth="0.04" color="#112638" position="0 0.04 0.081" material="opacity: 0.97"></a-box>
                    <a-box width="2.02" height="0.86" depth="0.04" color="#112638" position="0 0.04 -0.081" material="opacity: 0.97"></a-box>
                    <a-text value="${escapeAttribute(indicator.title)}" width="1.18" wrap-count="16" align="center" color="#f8fafc" position="-0.58 0.58 0.1"></a-text>
                    <a-text value="${escapeAttribute(indicator.title)}" width="1.18" wrap-count="16" align="center" color="#f8fafc" position="0.58 0.58 -0.1" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(indicator.latestValue)}" width="1.08" color="#8ef1e5" position="-0.88 -0.36 0.1"></a-text>
                    <a-text value="${escapeAttribute(indicator.latestValue)}" width="1.08" color="#8ef1e5" position="0.88 -0.36 -0.1" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(indicator.unit)}" width="0.88" color="#7dd3fc" position="0.06 -0.36 0.1"></a-text>
                    <a-text value="${escapeAttribute(indicator.unit)}" width="0.88" color="#7dd3fc" position="-0.06 -0.36 -0.1" rotation="0 180 0"></a-text>
                    <a-text value="Recent 5" width="0.9" color="#ffffff" position="0.02 0.26 0.1"></a-text>
                    <a-text value="Recent 5" width="0.9" color="#ffffff" position="-0.02 0.26 -0.1" rotation="0 180 0"></a-text>
                    ${graphBars || `<a-text value="No recent points" width="1.2" color="#cbd5e1" position="-0.46 0.02 0.1"></a-text>`}
                </a-entity>
            `;
        }).join("");

        const policyKraDetailScene = isPolicyKraDetailScene ? `
            <a-cylinder radius="5.8" height="0.08" color="#07111a" opacity="0.98" position="0 0.02 0"></a-cylinder>
            <a-cylinder radius="1.18" height="0.08" color="#0b1622" opacity="0.98" position="0 0.05 0"></a-cylinder>
            <a-ring position="0 0.06 0" radius-inner="3.44" radius-outer="3.56" rotation="-90 0 0" color="#173447" material="opacity: 0.28"></a-ring>
            <a-ring position="0 0.07 0" radius-inner="2.1" radius-outer="2.18" rotation="-90 0 0" color="#5de4c7" material="opacity: 0.14"></a-ring>
            <a-box width="3.7" height="0.86" depth="0.18" color="#0b1622" material="metalness: 0.18; roughness: 0.26; opacity: 0.96" position="0 2.42 -1.62" rotation="-6 0 0"></a-box>
            <a-text value="${dashboardData.policyKraDetail ? dashboardData.policyKraDetail.title : "KRA Detail"}" width="2.9" align="center" color="#ffffff" position="-1.44 2.58 -1.54"></a-text>
            <a-text value="${dashboardData.policyKraDetail ? dashboardData.policyKraDetail.goalTitle : ""}" width="2.4" align="center" color="#8ef1e5" position="-1.2 2.32 -1.52"></a-text>
            <a-text value="${dashboardData.policyKraDetail ? `${dashboardData.policyKraDetail.indicators.length} indicators around you` : ""}" width="2.5" align="center" color="#7dd3fc" position="-1.24 2.06 -1.5"></a-text>
            ${policyKraIndicatorCards || `<a-text value="No indicators available for this key result area." width="2.8" align="center" color="#cbd5e1" position="-1.4 1.42 -1.8"></a-text>`}
        ` : "";

        const ministryKraIndicatorCards = (dashboardData.ministryKraDetail && dashboardData.ministryKraDetail.indicators || []).map((indicator, index) => {
            const total = Math.max((dashboardData.ministryKraDetail && dashboardData.ministryKraDetail.indicators || []).length, 1);
            const angle = (360 / total) * index;
            const radians = angle * (Math.PI / 180);
            const radius = total > 10 ? 4.2 : 3.55;
            const x = Math.sin(radians) * radius;
            const z = Math.cos(radians) * radius;
            const y = 1.48;
            const rotationY = 180 + angle;
            const points = (indicator.points || []).slice(-5);
            const maxValue = Math.max(...points.map((item) => Number(item && item.value || 0)), 1);
            const graphBars = points.map((point, barIndex) => {
                const normalized = Math.max(0.18, Number(point && point.value || 0) / maxValue);
                const height = (normalized * 0.54).toFixed(3);
                const yPos = (-0.04 + normalized * 0.27).toFixed(3);
                const xPos = (-0.42 + barIndex * 0.21).toFixed(3);
                return `
                    <a-cylinder radius="0.05" height="${height}" color="${barIndex % 2 === 0 ? "#5de4c7" : "#7dd3fc"}" position="${xPos} ${yPos} 0.1"></a-cylinder>
                    <a-text value="${escapeAttribute(truncate(point.label, 10))}" width="0.5" align="center" color="#e2e8f0" position="${(Number(xPos) - 0.14).toFixed(3)} -0.28 0.1"></a-text>
                `;
            }).join("");
            const graphBarsBack = points.map((point, barIndex) => {
                const normalized = Math.max(0.18, Number(point && point.value || 0) / maxValue);
                const height = (normalized * 0.54).toFixed(3);
                const yPos = (-0.04 + normalized * 0.27).toFixed(3);
                const xPos = (0.42 - barIndex * 0.21).toFixed(3);
                return `
                    <a-cylinder radius="0.05" height="${height}" color="${barIndex % 2 === 0 ? "#5de4c7" : "#7dd3fc"}" position="${xPos} ${yPos} -0.1"></a-cylinder>
                    <a-text value="${escapeAttribute(truncate(point.label, 10))}" width="0.5" align="center" color="#e2e8f0" position="${(Number(xPos) - 0.14).toFixed(3)} -0.28 -0.1" rotation="0 180 0"></a-text>
                `;
            }).join("");
            return `
                <a-entity position="${x.toFixed(2)} ${y.toFixed(2)} ${z.toFixed(2)}" rotation="-6 ${rotationY.toFixed(2)} 0">
                    <a-box width="2.18" height="1.02" depth="0.16" color="#07111a" material="metalness: 0.22; roughness: 0.24; opacity: 0.98"></a-box>
                    <a-box width="2.02" height="0.86" depth="0.04" color="#112638" position="0 0.04 0.081" material="opacity: 0.97"></a-box>
                    <a-box width="2.02" height="0.86" depth="0.04" color="#112638" position="0 0.04 -0.081" material="opacity: 0.97"></a-box>
                    <a-text value="${escapeAttribute(indicator.title)}" width="1.16" wrap-count="16" align="center" color="#f8fafc" position="-0.56 0.6 0.1"></a-text>
                    <a-text value="${escapeAttribute(indicator.title)}" width="1.16" wrap-count="16" align="center" color="#f8fafc" position="0.56 0.6 -0.1" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(indicator.latestValue)}" width="1.34" color="#8ef1e5" position="-1 -0.36 0.1"></a-text>
                    <a-text value="${escapeAttribute(indicator.latestValue)}" width="1.34" color="#8ef1e5" position="1 -0.36 -0.1" rotation="0 180 0"></a-text>
                    <a-text value="${escapeAttribute(indicator.unit)}" width="1.02" color="#7dd3fc" position="0.1 -0.36 0.1"></a-text>
                    <a-text value="${escapeAttribute(indicator.unit)}" width="1.02" color="#7dd3fc" position="-0.1 -0.36 -0.1" rotation="0 180 0"></a-text>
                    <a-text value="Recent 5" width="0.96" color="#ffffff" position="0.08 0.24 0.1"></a-text>
                    <a-text value="Recent 5" width="0.96" color="#ffffff" position="-0.08 0.24 -0.1" rotation="0 180 0"></a-text>
                    ${graphBars || `<a-text value="No recent points" width="1.3" color="#cbd5e1" position="-0.42 -0.02 0.1"></a-text>`}
                    ${graphBarsBack || `<a-text value="No recent points" width="1.3" color="#cbd5e1" position="0.42 -0.02 -0.1" rotation="0 180 0"></a-text>`}
                </a-entity>
            `;
        }).join("");

        const ministryKraDetailScene = isMinistryKraDetailScene ? `
            <a-cylinder radius="5.8" height="0.08" color="#07111a" opacity="0.98" position="0 0.02 0"></a-cylinder>
            <a-cylinder radius="1.18" height="0.08" color="#0b1622" opacity="0.98" position="0 0.05 0"></a-cylinder>
            <a-ring position="0 0.06 0" radius-inner="3.44" radius-outer="3.56" rotation="-90 0 0" color="#173447" material="opacity: 0.28"></a-ring>
            <a-ring position="0 0.07 0" radius-inner="2.1" radius-outer="2.18" rotation="-90 0 0" color="#5de4c7" material="opacity: 0.14"></a-ring>
            <a-box width="3.7" height="0.86" depth="0.18" color="#0b1622" material="metalness: 0.18; roughness: 0.26; opacity: 0.96" position="0 2.42 -1.62" rotation="-6 0 0"></a-box>
            <a-text value="${dashboardData.ministryKraDetail ? dashboardData.ministryKraDetail.title : "Ministry KRA Detail"}" width="2.9" align="center" color="#ffffff" position="-1.44 2.58 -1.54"></a-text>
            <a-text value="${dashboardData.ministryKraDetail ? dashboardData.ministryKraDetail.goalTitle : ""}" width="2.4" align="center" color="#8ef1e5" position="-1.2 2.32 -1.52"></a-text>
            <a-text value="${dashboardData.ministryKraDetail ? `${dashboardData.ministryKraDetail.indicators.length} indicators around you` : ""}" width="2.5" align="center" color="#7dd3fc" position="-1.24 2.06 -1.5"></a-text>
            ${ministryKraIndicatorCards || `<a-text value="No indicators available for this key result area." width="2.8" align="center" color="#cbd5e1" position="-1.4 1.42 -1.8"></a-text>`}
        ` : "";

        const defaultWorkspace = `
            ${kpiCards}

            <a-entity
                id="analytics-wall"
                class="interactive"
                geometry="primitive: box; width: 2.4; height: 1.6; depth: 0.06"
                material="color: #0d1824; roughness: 0.25"
                position="0 1.18 -3.15"
                draggable-panel>
                <a-text value="${dashboardData.analyticsTitle || "Engagement Timeline"}" width="2.1" color="#f0fbff" position="-1 0.6 0.04"></a-text>
                <a-text value="${dashboardData.analyticsSubtitle || "interactive 3D chart panel"}" width="1.5" color="#7ea2b4" position="-1 0.42 0.04"></a-text>
                ${chartBars}
            </a-entity>

            <a-entity
                id="notifications-rig"
                class="interactive"
                position="2.3 1.2 -2.75"
                draggable-panel>
                <a-entity geometry="primitive: box; width: 1.6; height: 1.45; depth: 0.05" material="color: #0d1922; opacity: 0.9"></a-entity>
                <a-text value="${dashboardData.notificationsTitle || "Holographic Alerts"}" width="1.6" color="#f0fbff" position="-0.65 0.55 0.04"></a-text>
                ${notifications}
            </a-entity>

            <a-entity
                class="interactive"
                geometry="primitive: box; width: 1.7; height: 1.08; depth: 0.06"
                material="color: #0d1824; opacity: 0.92"
                position="-2.35 1.08 -2.75"
                rotation="0 18 0"
                draggable-panel>
                <a-text value="${dashboardData.widgetTitle || "Widget Dock"}" width="1.7" color="#f0fbff" position="-0.68 0.34 0.04"></a-text>
                ${widgetLines}
            </a-entity>
        `;

        const roomBackgroundColor = currentTheme === "light" ? "#f2f7fa" : "#04131d";
        const roomSkyColor = currentTheme === "light" ? "#f5f9fb" : "#04131d";
        const roomFloorColor = currentTheme === "light" ? "#e7eff4" : "#07111a";
        const roomBackWallColor = currentTheme === "light" ? "#dfeaf0" : "#061420";
        const roomRingColor = currentTheme === "light" ? "#9fb4c1" : "#16364a";
        const roomAmbientColor = currentTheme === "light" ? "#ffffff" : "#8db7c7";
        const roomDirectionalColor = currentTheme === "light" ? "#fffefb" : "#d9f7ff";
        const roomAccentLightColor = currentTheme === "light" ? "#60a5fa" : "#5de4c7";
        const roomMarkerColor = isDataCatalogScene ? "#0f766e" : isProjectCatalogScene || isProjectDetailScene || isProjectSubDetailScene ? "#fb923c" : isInitiativeCatalogScene || isInitiativeDetailScene ? "#f472b6" : (currentTheme === "light" ? "#0284c7" : "#ff7a59");

        return applyThemeToMarkup(`
            <a-scene
                embedded
                style="width: 100%; height: 640px;"
                renderer="antialias: true; colorManagement: true; physicallyCorrectLights: false; sortObjects: true"
                vr-mode-ui="enabled: false"
                background="color: ${roomBackgroundColor}">
                <a-assets timeout="10000"></a-assets>

                <a-entity id="workspace-root">
                    <a-sky color="${roomSkyColor}"></a-sky>
                    <a-plane rotation="-90 0 0" width="24" height="24" color="${roomFloorColor}" material="roughness: 1"></a-plane>
                    <a-plane position="0 0 -9" width="22" height="10" color="${roomBackWallColor}"></a-plane>
                    <a-ring position="0 3.2 -7.8" radius-inner="1.8" radius-outer="1.92" color="${roomRingColor}" material="opacity: 0.24"></a-ring>
                    <a-entity light="type: ambient; intensity: ${isHomeScene ? "0.96" : "0.8"}; color: ${roomAmbientColor}"></a-entity>
                    <a-entity light="type: directional; intensity: ${isHomeScene ? "0.72" : "0.55"}; color: ${roomDirectionalColor}" position="-1 3 1"></a-entity>
                    <a-entity light="type: point; intensity: ${isHomeScene ? "0.62" : "0.85"}; distance: 12; color: ${roomAccentLightColor}" position="0 2.8 -2.5"></a-entity>
                    <a-box position="0 1.5 -4.6" depth="0.3" height="0.3" width="0.3" color="${roomMarkerColor}"></a-box>
                    ${isHomeScene || isDataCatalogScene || isTopicDetailScene || isCategoryDetailScene || isPolicyAreaCatalogScene || isPolicyAreaDetailScene || isPolicyGoalDetailScene || isPolicyKraDetailScene || isMinistryCatalogScene || isMinistryDetailScene || isMinistryGoalDetailScene || isMinistryKraDetailScene || isProjectCatalogScene || isProjectDetailScene || isProjectSubDetailScene || isInitiativeCatalogScene || isInitiativeDetailScene ? "" : `<a-text value="${(dashboardData.sourcePage && dashboardData.sourcePage.title) || "Current Page"}" width="3.4" align="center" color="#f0fbff" position="0 2.32 -2.3"></a-text>`}
                    ${isHomeScene || isDataCatalogScene || isTopicDetailScene || isCategoryDetailScene || isPolicyAreaCatalogScene || isPolicyAreaDetailScene || isPolicyGoalDetailScene || isPolicyKraDetailScene || isMinistryCatalogScene || isMinistryDetailScene || isMinistryGoalDetailScene || isMinistryKraDetailScene || isProjectCatalogScene || isProjectDetailScene || isProjectSubDetailScene || isInitiativeCatalogScene || isInitiativeDetailScene ? "" : `<a-text value="Page wall" width="1.4" color="#5de4c7" position="-2.45 2.62 -5.18"></a-text>`}
                    ${isHomeScene || isDataCatalogScene || isTopicDetailScene || isCategoryDetailScene || isPolicyAreaCatalogScene || isPolicyAreaDetailScene || isPolicyGoalDetailScene || isPolicyKraDetailScene || isMinistryCatalogScene || isMinistryDetailScene || isMinistryGoalDetailScene || isMinistryKraDetailScene || isProjectCatalogScene || isProjectDetailScene || isProjectSubDetailScene || isInitiativeCatalogScene || isInitiativeDetailScene ? "" : pageTiles}
                    ${isHomeScene ? "" : sectionPanels}
                    ${backControl}
                    ${sharedPageWall}
                    ${homeDashboardReplica}
                    ${dataCatalogWorkspace}
                    ${projectCatalogScene}
                    ${initiativeCatalogScene}
                    ${projectDetailScene}
                    ${projectSubDetailScene}
                    ${initiativeDetailScene}
                    ${policyAreaCatalogScene}
                    ${ministryCatalogScene}
                    ${policyAreaDetailScene}
                    ${ministryDetailScene}
                    ${policyGoalDetailScene}
                    ${ministryGoalDetailScene}
                    ${topicDetailScene}
                    ${categoryDetailScene}
                    ${policyKraDetailScene}
                    ${ministryKraDetailScene}
                    ${isHomeScene || isDataCatalogScene || isTopicDetailScene || isCategoryDetailScene || isPolicyAreaCatalogScene || isPolicyAreaDetailScene || isPolicyGoalDetailScene || isPolicyKraDetailScene || isMinistryCatalogScene || isMinistryDetailScene || isMinistryGoalDetailScene || isMinistryKraDetailScene || isProjectCatalogScene || isProjectDetailScene || isProjectSubDetailScene || isInitiativeCatalogScene || isInitiativeDetailScene ? "" : defaultWorkspace}

                    ${isHomeScene || isDataCatalogScene || isTopicDetailScene || isCategoryDetailScene || isPolicyAreaCatalogScene || isPolicyAreaDetailScene || isPolicyGoalDetailScene || isPolicyKraDetailScene || isMinistryCatalogScene || isMinistryDetailScene || isMinistryGoalDetailScene || isMinistryKraDetailScene || isProjectCatalogScene || isProjectDetailScene || isProjectSubDetailScene || isInitiativeCatalogScene || isInitiativeDetailScene ? "" : menuItems}

                    ${isHomeScene || isDataCatalogScene || isTopicDetailScene || isCategoryDetailScene || isPolicyAreaCatalogScene || isPolicyAreaDetailScene || isPolicyGoalDetailScene || isPolicyKraDetailScene || isMinistryCatalogScene || isMinistryDetailScene || isMinistryGoalDetailScene || isMinistryKraDetailScene || isProjectCatalogScene || isProjectDetailScene || isProjectSubDetailScene || isInitiativeCatalogScene || isInitiativeDetailScene ? "" : `<a-text id="active-menu-title" value="Overview" width="3" align="center" color="#5de4c7" position="0 2.65 -3.15"></a-text>`}
                </a-entity>

                <a-entity id="cameraRig" position="0 1.6 0">
                    <a-camera position="0 0 0" look-controls wasd-controls="enabled: true">
                        <a-cursor raycaster="objects: .interactive" fuse="false" material="color: #5de4c7; shader: flat"></a-cursor>
                    </a-camera>
                </a-entity>

                <a-entity
                    id="leftHand"
                    hand-tracking-controls="hand: left; modelStyle: dots"
                    laser-controls="hand: left"
                    raycaster="objects: .interactive"
                    line="color: #5de4c7"
                    xr-pointer
                    gesture-scroll>
                </a-entity>
                <a-entity
                    id="rightHand"
                    hand-tracking-controls="hand: right; modelStyle: dots"
                    laser-controls="hand: right"
                    raycaster="objects: .interactive"
                    line="color: #7cb8ff"
                    xr-pointer>
                </a-entity>
            </a-scene>
        `);
    }

    async function ensureScene(mode) {
        if (sceneLoading) {
            await sceneLoading;
        }

        if (sceneBuilt) {
            stageNode.scrollIntoView({ behavior: "smooth", block: "center" });
            const readyScene = stageNode.querySelector("a-scene");
            if (mode === "vr" && readyScene && readyScene.enterVR) {
                readyScene.enterVR();
            }
            return;
        }

        sceneLoading = (async () => {
            stageNode.dataset.state = "loading";
            await hydrateDashboardHomeData().catch((error) => {
                console.error(error);
            });
            await hydrateDataCatalogSceneData().catch((error) => {
                console.error(error);
            });
            await hydrateProjectCatalogSceneData().catch((error) => {
                console.error(error);
            });
            await hydrateInitiativeCatalogSceneData().catch((error) => {
                console.error(error);
            });
            await hydratePolicyAreaCatalogSceneData().catch((error) => {
                console.error(error);
            });
            await hydrateMinistryCatalogSceneData().catch((error) => {
                console.error(error);
            });
            await hydrateProjectDetailSceneData().catch((error) => {
                console.error(error);
            });
            await hydrateProjectSubDetailSceneData().catch((error) => {
                console.error(error);
            });
            await hydrateInitiativeDetailSceneData().catch((error) => {
                console.error(error);
            });
            await hydratePolicyAreaDetailSceneData().catch((error) => {
                console.error(error);
            });
            await hydrateMinistryDetailSceneData().catch((error) => {
                console.error(error);
            });
            await hydratePolicyGoalDetailSceneData().catch((error) => {
                console.error(error);
            });
            await hydrateMinistryGoalDetailSceneData().catch((error) => {
                console.error(error);
            });
            await hydratePolicyKraDetailSceneData().catch((error) => {
                console.error(error);
            });
            await hydrateMinistryKraDetailSceneData().catch((error) => {
                console.error(error);
            });
            await hydrateTopicDetailSceneData().catch((error) => {
                console.error(error);
            });
            await hydrateCategoryDetailSceneData().catch((error) => {
                console.error(error);
            });
            await ensureAFrame();

            if (!sceneBuilt) {
                stageNode.innerHTML = buildSceneMarkup();
                stageNode.dataset.state = "loaded";
                sceneBuilt = true;
            }
        })();

        try {
            await sceneLoading;
        } finally {
            sceneLoading = null;
        }

        stageNode.scrollIntoView({ behavior: "smooth", block: "center" });

        const sceneEl = stageNode.querySelector("a-scene");
        if (mode === "vr" && sceneEl && sceneEl.enterVR) {
            sceneEl.enterVR();
        }
    }

    function rerenderScene() {
        if (!sceneBuilt) {
            return;
        }
        stageNode.innerHTML = buildSceneMarkup();
        stageNode.dataset.state = "loaded";
    }

    async function warmDesktopPreview() {
        try {
            await ensureScene("preview");
            statusNode.textContent = "Desktop 3D preview loaded. Use Enter VR only on supported headsets.";
        } catch (error) {
            statusNode.textContent = "Unable to load the 3D preview. Check static asset loading and external CDN access.";
            console.error(error);
        }
    }

    enterVrButton.addEventListener("click", async () => {
        enterVrButton.disabled = true;
        statusNode.textContent = "Loading WebXR scene...";
        try {
            await ensureScene("vr");
            statusNode.textContent = "VR scene loaded. Use controllers, hand rays, pinch gestures, and grab interactions.";
        } catch (error) {
            statusNode.textContent = "Unable to load VR scene. Check browser permissions or network access to the A-Frame CDN.";
            console.error(error);
        } finally {
            enterVrButton.disabled = false;
        }
    });

    previewButton.addEventListener("click", async () => {
        previewButton.disabled = true;
        try {
            await ensureScene("preview");
            statusNode.textContent = "3D preview loaded inline. Desktop mode still uses the standard 2D dashboard.";
        } catch (error) {
            statusNode.textContent = "Unable to load 3D preview.";
            console.error(error);
        } finally {
            previewButton.disabled = false;
        }
    });

    if (themeDarkButton) {
        themeDarkButton.addEventListener("click", () => {
            currentTheme = "dark";
            refreshThemeButtons();
            rerenderScene();
        });
    }

    if (themeLightButton) {
        themeLightButton.addEventListener("click", () => {
            currentTheme = "light";
            refreshThemeButtons();
            rerenderScene();
        });
    }

    refreshThemeButtons();
    warmDesktopPreview();
    checkXRSupport();
})();
