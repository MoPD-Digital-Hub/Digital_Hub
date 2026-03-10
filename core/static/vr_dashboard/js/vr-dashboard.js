(function () {
    const dataNode = document.getElementById("vr-dashboard-data");
    const enterVrButton = document.getElementById("enter-vr-button");
    const previewButton = document.getElementById("focus-vr-preview");
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
                    const params = new URLSearchParams({
                        source: this.data.url,
                        title: this.data.title,
                    });
                    window.location.href = `/dashboard/vr/?${params.toString()}`;
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

        const homeTopicPanels = (dashboardData.homeTopics || []).map((topic, index) => `
            <a-entity
                class="interactive"
                geometry="primitive: box; width: 1.12; height: 0.82; depth: 0.05"
                material="color: #16374d; opacity: 0.98"
                position="${-1.72 + index * 1.18} 1.54 -3.28"
                rotation="0 0 0">
                <a-entity
                    geometry="primitive: box; width: 1.02; height: 0.18; depth: 0.01"
                    material="color: #1f4d69; opacity: 0.95"
                    position="0 0.26 0.04">
                </a-entity>
                <a-text value="Data Topic" width="0.68" color="#d5eef7" position="-0.46 0.24 0.05"></a-text>
                <a-text value="${topic.title}" width="1" wrap-count="16" color="#ffffff" position="-0.46 0.02 0.05"></a-text>
                <a-text value="${topic.metaPrimary}" width="0.7" color="#5de4c7" position="-0.46 -0.24 0.05"></a-text>
                <a-text value="${topic.metaSecondary}" width="0.64" color="#9fd5ff" position="-0.46 -0.38 0.05"></a-text>
            </a-entity>
        `).join("");

        const homeMinistryPanels = (dashboardData.homeMinistries || []).map((ministry, index) => `
            <a-entity
                class="interactive"
                geometry="primitive: box; width: 1.02; height: 1.02; depth: 0.06"
                material="color: #d7efe8; opacity: 0.98"
                position="${-1.56 + index * 1.08} 0.36 -3.12"
                rotation="0 0 0">
                <a-entity
                    geometry="primitive: box; width: 0.9; height: 0.5; depth: 0.01"
                    material="color: #4ea48f; opacity: 0.92"
                    position="0 0.2 0.04">
                </a-entity>
                <a-text value="${ministry.code}" width="0.7" color="#ffffff" position="-0.36 0.28 0.05"></a-text>
                <a-text value="${ministry.title}" width="0.76" wrap-count="14" color="#16313f" position="-0.36 0.0 0.05"></a-text>
                <a-text value="Score" width="0.36" color="#36586a" position="-0.36 -0.22 0.05"></a-text>
                <a-text value="${ministry.score}" width="0.62" color="#0f172a" position="-0.36 -0.36 0.05"></a-text>
                <a-text value="${ministry.indicators}" width="0.6" color="#36586a" position="-0.36 -0.5 0.05"></a-text>
            </a-entity>
        `).join("");

        const homeSummaryPanels = `
            <a-entity geometry="primitive: box; width: 1.12; height: 0.66; depth: 0.05" material="color: #15293a; opacity: 0.96" position="2.18 1.54 -3.24">
                <a-text value="Program Summaries" width="1.1" color="#f0fbff" position="-0.46 0.18 0.04"></a-text>
                <a-text value="Fayda and Mesob snapshots" width="0.9" color="#8fb5c7" position="-0.46 0.02 0.04"></a-text>
                <a-text value="Fayda eKYC" width="0.7" color="#5de4c7" position="-0.46 -0.18 0.04"></a-text>
                <a-text value="Mesob service snapshot" width="0.9" color="#9fd5ff" position="-0.46 -0.3 0.04"></a-text>
            </a-entity>
            <a-entity geometry="primitive: box; width: 1.12; height: 0.66; depth: 0.05" material="color: #173447; opacity: 0.96" position="3.42 1.54 -3.24">
                <a-text value="High Frequency Indicators" width="1.1" color="#f0fbff" position="-0.46 0.18 0.04"></a-text>
                <a-text value="${(dashboardData.homeIndicators || []).slice(0, 2).join(" | ") || "Trending KPI feed"}" width="0.88" wrap-count="20" color="#5de4c7" position="-0.46 -0.02 0.04"></a-text>
            </a-entity>
        `;

        const homeProjectPanels = `
            <a-entity geometry="primitive: box; width: 2.18; height: 0.72; depth: 0.05" material="color: #112233; opacity: 0.95" position="-0.22 -0.78 -3.12">
                <a-text value="Projects" width="0.9" color="#f0fbff" position="-0.96 0.18 0.04"></a-text>
                <a-text value="${(dashboardData.homeProjects || []).join(" | ") || "Sector portfolio strip"}" width="1.8" wrap-count="36" color="#8fb5c7" position="-0.96 -0.02 0.04"></a-text>
            </a-entity>
            <a-entity geometry="primitive: box; width: 2.18; height: 0.72; depth: 0.05" material="color: #15293a; opacity: 0.95" position="2.28 -0.78 -3.12">
                <a-text value="Initiatives" width="0.9" color="#f0fbff" position="-0.96 0.18 0.04"></a-text>
                <a-text value="${(dashboardData.homeInitiatives || []).join(" | ") || "National spotlight cards"}" width="1.8" wrap-count="36" color="#8fb5c7" position="-0.96 -0.02 0.04"></a-text>
            </a-entity>
        `;

        const homeDashboardReplica = isHomeScene ? `
            <a-entity geometry="primitive: box; width: 7.2; height: 4.45; depth: 0.04" material="color: #091520; opacity: 0.24" position="0.8 0.62 -3.46"></a-entity>
            <a-text value="Key Development Statistics" width="1.7" color="#f0fbff" position="-1.72 2.02 -3.28"></a-text>
            <a-text value="Ministry Scorecard" width="1.5" color="#f0fbff" position="-1.56 0.96 -3.12"></a-text>
            <a-text value="Program Summaries" width="1.15" color="#f0fbff" position="2.18 2.02 -3.24"></a-text>
            <a-text value="High Frequency Indicators" width="1.4" color="#f0fbff" position="3.42 2.02 -3.24"></a-text>
            <a-text value="Projects and Initiatives" width="1.5" color="#f0fbff" position="-0.22 -0.22 -3.12"></a-text>
            ${homeTopicPanels}
            ${homeMinistryPanels}
            ${homeSummaryPanels}
            ${homeProjectPanels}
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

        const topicDetailCategoryPods = (dashboardData.topicCategories || []).map((category, index) => {
            const angle = (360 / Math.max((dashboardData.topicCategories || []).length, 1)) * index;
            const radians = angle * (Math.PI / 180);
            const radius = 3.2;
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

        const categoryIndicatorCards = (dashboardData.categoryDetail && dashboardData.categoryDetail.indicators || []).map((indicator, index) => {
            const column = index % 2;
            const row = Math.floor(index / 2);
            const x = column === 0 ? -1.78 : 1.78;
            const y = 1.92 - row * 1.16;
            const z = -2.62 - row * 0.28 + (column === 0 ? 0.2 : -0.2);
            const rotationY = column === 0 ? 8 : -8;
            const bars = (indicator.points || []).slice(-5);
            const maxValue = Math.max(...bars.map((item) => Number(item && item.value || 0)), 1);
            const graphBars = bars.map((point, barIndex) => {
                const normalized = Math.max(0.18, Number(point && point.value || 0) / maxValue);
                const height = (normalized * 0.56).toFixed(3);
                const yPos = (-0.12 + normalized * 0.28).toFixed(3);
                const xPos = (-0.44 + barIndex * 0.22).toFixed(3);
                return `
                    <a-cylinder radius="0.05" height="${height}" color="${barIndex % 2 === 0 ? "#5de4c7" : "#7dd3fc"}" position="${xPos} ${yPos} 0.1"></a-cylinder>
                    <a-box
                        width="0.12"
                        depth="0.08"
                        height="0.02"
                        color="#08111a"
                        position="${xPos} -0.42 0.08">
                    </a-box>
                    <a-text value="${escapeAttribute(truncate(point.label, 10))}" width="0.3" align="center" color="#7c93a8" position="${(Number(xPos) - 0.08).toFixed(3)} -0.54 0.1"></a-text>
                `;
            }).join("");

            return `
                <a-entity position="${x.toFixed(2)} ${y.toFixed(2)} ${z.toFixed(2)}" rotation="-8 ${rotationY} 0">
                    <a-cylinder radius="0.92" height="0.04" color="#07111a" position="0 -0.52 0" rotation="90 0 0"></a-cylinder>
                    <a-box width="2.28" height="1.02" depth="0.16" color="#07111a" material="metalness: 0.22; roughness: 0.24; opacity: 0.98"></a-box>
                    <a-box width="2.12" height="0.86" depth="0.04" color="#112638" position="0 0.04 0.081" material="opacity: 0.97"></a-box>
                    <a-ring radius-inner="0.78" radius-outer="0.88" color="#5de4c7" material="opacity: 0.1" position="0 0 0.09"></a-ring>
                    <a-plane width="0.92" height="0.54" color="#0b1622" material="opacity: 0.96" position="0.48 -0.1 0.1"></a-plane>
                    <a-text value="${escapeAttribute(indicator.title)}" width="2.02" wrap-count="18" color="#f8fafc" position="-1 0.34 0.1"></a-text>
                    <a-text value="${escapeAttribute(indicator.latestValue)}" width="1.04" color="#8ef1e5" position="-1 -0.02 0.1"></a-text>
                    <a-text value="${escapeAttribute(indicator.unit)}" width="0.72" color="#7dd3fc" position="0.02 -0.02 0.1"></a-text>
                    <a-text value="Recent 5" width="0.72" color="#cbd5e1" position="0.34 0.32 0.1"></a-text>
                    ${graphBars || `<a-text value="No recent points" width="1.1" color="#cbd5e1" position="0.08 -0.02 0.1"></a-text>`}
                </a-entity>
            `;
        }).join("");

        const categoryDetailScene = isCategoryDetailScene ? `
            <a-cylinder radius="5.8" height="0.08" color="#07111a" opacity="0.98" position="0 0.02 0"></a-cylinder>
            <a-cylinder radius="2.6" height="0.05" color="#0b1622" opacity="0.98" position="0 0.05 -2.55"></a-cylinder>
            <a-ring position="0 0.06 -2.55" radius-inner="2.18" radius-outer="2.32" rotation="-90 0 0" color="#173447" material="opacity: 0.28"></a-ring>
            <a-ring position="0 0.07 -2.55" radius-inner="1.12" radius-outer="1.2" rotation="-90 0 0" color="#5de4c7" material="opacity: 0.14"></a-ring>
            <a-box width="5.6" height="0.86" depth="0.16" color="#0b1622" material="metalness: 0.18; roughness: 0.26; opacity: 0.96" position="0 2.58 -2.72" rotation="-4 0 0"></a-box>
            <a-ring radius-inner="0.38" radius-outer="0.46" color="#7dd3fc" material="opacity: 0.14" position="0 2.98 -2.58"></a-ring>
            <a-text value="${dashboardData.categoryDetail ? dashboardData.categoryDetail.title : "Category Detail"}" width="3.8" align="center" color="#ffffff" position="-1.88 2.8 -2.58"></a-text>
            <a-text value="${dashboardData.categoryDetail ? `${dashboardData.categoryDetail.topicTitle} | ${dashboardData.categoryDetail.code}` : ""}" width="3.1" align="center" color="#8ef1e5" position="-1.54 2.46 -2.56"></a-text>
            <a-text value="${dashboardData.categoryDetail ? `${dashboardData.categoryDetail.indicatorCount} indicators with recent 5-point history` : ""}" width="3.2" align="center" color="#7dd3fc" position="-1.58 2.14 -2.54"></a-text>
            ${categoryIndicatorCards || `<a-text value="No indicators available for this category." width="2.9" align="center" color="#cbd5e1" position="-1.42 1.4 -2.7"></a-text>`}
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

        return `
            <a-scene
                embedded
                style="width: 100%; height: 640px;"
                renderer="antialias: true; colorManagement: true; physicallyCorrectLights: false; sortObjects: true"
                vr-mode-ui="enabled: false"
                background="color: #04131d">
                <a-assets timeout="10000"></a-assets>

                <a-entity id="workspace-root">
                    <a-sky color="#04131d"></a-sky>
                    <a-plane rotation="-90 0 0" width="24" height="24" color="#07111a" material="roughness: 1"></a-plane>
                    <a-plane position="0 0 -9" width="22" height="10" color="#061420"></a-plane>
                    <a-ring position="0 3.2 -7.8" radius-inner="1.8" radius-outer="1.92" color="#16364a" material="opacity: 0.24"></a-ring>
                    <a-entity light="type: ambient; intensity: 0.8; color: #8db7c7"></a-entity>
                    <a-entity light="type: directional; intensity: 0.55; color: #d9f7ff" position="-1 3 1"></a-entity>
                    <a-entity light="type: point; intensity: 0.85; distance: 12; color: #5de4c7" position="0 2.8 -2.5"></a-entity>
                    <a-box position="0 1.5 -4.6" depth="0.3" height="0.3" width="0.3" color="${isDataCatalogScene ? "#0f766e" : "#ff7a59"}"></a-box>
                    ${isDataCatalogScene || isTopicDetailScene || isCategoryDetailScene ? "" : `<a-text value="${(dashboardData.sourcePage && dashboardData.sourcePage.title) || "Current Page"}" width="3.4" align="center" color="#f0fbff" position="0 2.32 -2.3"></a-text>`}
                    ${isDataCatalogScene || isTopicDetailScene || isCategoryDetailScene ? "" : `<a-text value="Page wall" width="1.4" color="#5de4c7" position="-2.45 2.62 -5.18"></a-text>`}
                    ${isDataCatalogScene || isTopicDetailScene || isCategoryDetailScene ? "" : pageTiles}
                    ${isHomeScene ? "" : sectionPanels}
                    ${homeDashboardReplica}
                    ${dataCatalogWorkspace}
                    ${topicDetailScene}
                    ${categoryDetailScene}
                    ${isHomeScene || isDataCatalogScene || isTopicDetailScene || isCategoryDetailScene ? "" : defaultWorkspace}

                    ${isDataCatalogScene || isTopicDetailScene || isCategoryDetailScene ? "" : menuItems}

                    ${isDataCatalogScene || isTopicDetailScene || isCategoryDetailScene ? "" : `<a-text id="active-menu-title" value="Overview" width="3" align="center" color="#5de4c7" position="0 2.65 -3.15"></a-text>`}
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
        `;
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

    warmDesktopPreview();
    checkXRSupport();
})();
