from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import render
from django.urls import reverse
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from . models import *


def _build_vr_page_registry():
    return [
        {"title": "Dashboard Home", "url": reverse("dashboard_home")},
        {"title": "Sample Dashboard", "url": reverse("dashboard_sample")},
        {"title": "Admas AI", "url": reverse("dashboard_admas_ai")},
        {"title": "Data Catalog", "url": reverse("data_categories")},
        {"title": "Topic Detail", "url": reverse("data_topic_detail", kwargs={"topic_id": 1})},
        {"title": "Indicator Detail", "url": reverse("data_indicator_detail", kwargs={"indicator_id": 1})},
        {"title": "Policy Areas", "url": reverse("policy_area_list")},
        {"title": "Policy Area Detail", "url": reverse("policy_area_detail", kwargs={"policy_area_id": 1})},
        {"title": "Goal Detail", "url": reverse("goal_detail", kwargs={"goal_id": 1})},
        {"title": "Public Bodies", "url": reverse("public_body_list")},
        {"title": "Public Body Detail", "url": reverse("public_body_detail", kwargs={"ministry_id": 1})},
        {"title": "High Frequency Dashboard", "url": reverse("high_frequency_dashboard")},
        {"title": "Sector Projects", "url": reverse("sector_project_list")},
        {"title": "Sector Project Detail", "url": reverse("sector_project_detail", kwargs={"project_id": 1})},
        {"title": "National Initiatives", "url": reverse("initiative_list")},
        {"title": "Initiative Detail", "url": reverse("initiative_detail", kwargs={"initiative_id": 1})},
        {"title": "Edit Profile", "url": reverse("edit_profile")},
        {"title": "Change Password", "url": reverse("change_password")},
    ]


def _build_scene_profile(source_page_url, source_page_title, category_id=None):
    base_profile = {
        "scene_variant": "default",
        "menu": ["Overview", "Analytics", "Projects", "Alerts", "AI"],
        "analytics_title": "Engagement Timeline",
        "analytics_subtitle": "interactive 3D chart panel",
        "notifications_title": "Holographic Alerts",
        "widget_title": "Widget Dock",
        "widget_lines": [
            "Grab panels to reorganize the workspace.",
            "Pinch with hand tracking to scroll alert stacks.",
        ],
        "kpis": [
            {"label": "Revenue Pulse", "value": "$284K", "delta": "+18.4%", "position": "-1.45 1.95 -2.35"},
            {"label": "Active Users", "value": "12.8K", "delta": "+6.2%", "position": "0 2.08 -2.2"},
            {"label": "Alerts", "value": "3", "delta": "Needs review", "position": "1.45 1.95 -2.35"},
        ],
        "notifications": [
            "API anomaly detected in East Africa region",
            "Enterprise onboarding tour requested",
            "Video encoding latency restored to baseline",
        ],
        "charts": [0.46, 0.72, 0.58, 0.88, 0.67, 0.94],
        "section_panels": [],
    }

    if source_page_url == reverse("dashboard_home"):
        home_profile = {
            "scene_variant": "dashboard-home",
            "menu": ["Topics", "Ministries", "Summaries", "Indicators", "Projects", "Initiatives"],
            "analytics_title": "Home Dashboard Flow",
            "analytics_subtitle": "section-level activity across the landing dashboard",
            "notifications_title": "Dashboard Feed",
            "widget_title": "Home Section Dock",
            "widget_lines": [
                "The front arc matches the landing page structure from /dashboard.",
                "Use floating section panels to jump between topics, scorecards, feeds, and project views.",
            ],
            "kpis": [
                {"label": "Topics", "value": "8", "delta": "Key Development Statistics", "position": "-1.45 1.95 -2.35"},
                {"label": "Ministries", "value": "8", "delta": "Scorecards in focus", "position": "0 2.08 -2.2"},
                {"label": "Indicators", "value": "6", "delta": "High-frequency tiles", "position": "1.45 1.95 -2.35"},
            ],
            "notifications": [
                "Topic strip is available for quick drill-down into the data catalog",
                "Ministry scorecards remain pinned to the left interaction arc",
                "Projects and initiatives are staged as secondary immersive panels",
            ],
            "charts": [0.52, 0.68, 0.61, 0.74, 0.83, 0.79],
            "section_panels": [
                {"title": "Key Development Statistics", "subtitle": "Scrollable topic strip", "position": "-2.65 1.55 -4.7", "rotation": "0 18 0"},
                {"title": "Ministry Scorecard", "subtitle": "Performance cards by period", "position": "-1.05 1.9 -4.2", "rotation": "0 8 0"},
                {"title": "Program Summaries", "subtitle": "Fayda and Mesob snapshots", "position": "0.7 1.95 -4.1", "rotation": "0 -6 0"},
                {"title": "High Frequency Indicators", "subtitle": "Trending KPI feed", "position": "2.3 1.55 -4.55", "rotation": "0 -18 0"},
                {"title": "Projects", "subtitle": "Sector portfolio strip", "position": "-1.2 0.92 -4.95", "rotation": "0 10 0"},
                {"title": "Initiatives", "subtitle": "National spotlight cards", "position": "1.25 0.96 -4.85", "rotation": "0 -10 0"},
            ],
        }
        merged = base_profile.copy()
        merged.update(home_profile)
        return merged

    if category_id and source_page_url.startswith("/dashboard/data/"):
        category_profile = {
            "scene_variant": "data-category-detail",
            "menu": ["Indicators", "Trend", "Metrics", "History", "Return"],
            "analytics_title": "Category Indicator Grid",
            "analytics_subtitle": "recent operational history across category indicators",
            "notifications_title": "Category Signals",
            "widget_title": "Category Focus",
            "widget_lines": [
                "Indicators are arranged in a flat grid for faster inspection.",
                "Each tile shows the latest value and a recent-5-point trend.",
            ],
            "kpis": [
                {"label": "Category", "value": "Detail", "delta": "loading", "position": "-1.45 1.95 -2.35"},
                {"label": "Indicators", "value": "--", "delta": "loading", "position": "0 2.08 -2.2"},
                {"label": "Topic", "value": "VR", "delta": source_page_title or "Selected topic", "position": "1.45 1.95 -2.35"},
            ],
            "notifications": [
                "Category detail scene is loading indicators",
                "Recent five-point graphs are generated per indicator",
                "Use the grid to compare indicators quickly in XR",
            ],
            "charts": [0.36, 0.48, 0.62, 0.71, 0.69, 0.82],
        }
        merged = base_profile.copy()
        merged.update(category_profile)
        return merged

    if (
        source_page_url.startswith("/dashboard/data/")
        and source_page_url != reverse("data_categories")
        and not source_page_url.startswith("/dashboard/data/indicator/")
    ):
        detail_profile = {
            "scene_variant": "data-topic-detail",
            "menu": ["Overview", "Categories", "KPIs", "History", "Insights"],
            "analytics_title": "Topic Structure",
            "analytics_subtitle": "immersive category and KPI exploration",
            "notifications_title": "Topic Signals",
            "widget_title": "Topic Focus",
            "widget_lines": [
                "Open category pods to inspect the topic structure in 3D.",
                "Use the mirrored page only as reference; the XR scene is the primary detail view.",
            ],
            "kpis": [
                {"label": "Categories", "value": "--", "delta": "loading", "position": "-1.45 1.95 -2.35"},
                {"label": "KPIs", "value": "--", "delta": "loading", "position": "0 2.08 -2.2"},
                {"label": "Topic", "value": "Detail", "delta": source_page_title or "Selected topic", "position": "1.45 1.95 -2.35"},
            ],
            "notifications": [
                "Topic detail scene is loading categories",
                "KPI summaries will appear around the selected topic",
                "Use category pods to pivot into the 2D detail page when needed",
            ],
            "charts": [0.44, 0.58, 0.7, 0.62, 0.8, 0.74],
        }
        merged = base_profile.copy()
        merged.update(detail_profile)
        return merged

    profiles = [
        (
            "/dashboard/sample/",
            {
                "scene_variant": "sample",
                "menu": ["Sample", "Preview", "Widgets", "Alerts", "XR"],
                "analytics_title": "Sample Dashboard Activity",
                "analytics_subtitle": "generic demo view",
                "notifications_title": "Sample Alerts",
                "widget_title": "Sample Widget Dock",
                "widget_lines": [
                    "This route is only a scaffold and does not match the full landing dashboard.",
                    "Use /dashboard for the primary XR home experience.",
                ],
                "kpis": [
                    {"label": "Preview Panels", "value": "3", "delta": "demo tiles", "position": "-1.45 1.95 -2.35"},
                    {"label": "Widgets", "value": "4", "delta": "sample scene", "position": "0 2.08 -2.2"},
                    {"label": "Alerts", "value": "2", "delta": "demo notices", "position": "1.45 1.95 -2.35"},
                ],
                "notifications": [
                    "Sample dashboard is a placeholder route",
                    "Use the home dashboard for the richer immersive view",
                    "The live mirror now works under SAMEORIGIN framing",
                ],
                "charts": [0.36, 0.55, 0.62, 0.71, 0.59, 0.8],
            },
        ),
        (
            "/dashboard/admas-ai/",
            {
                "menu": ["AI", "Chats", "Knowledge", "Signals", "Assist"],
                "analytics_title": "AI Request Timeline",
                "analytics_subtitle": "question throughput and response quality",
                "notifications_title": "AI Assistant Events",
                "widget_title": "Prompt Workspace",
                "widget_lines": [
                    "Monitor active chat sessions and knowledge retrieval health.",
                    "Reposition insight panels to compare prompts and responses.",
                ],
                "kpis": [
                    {"label": "AI Sessions", "value": "34", "delta": "+9 today", "position": "-1.45 1.95 -2.35"},
                    {"label": "Avg Response", "value": "1.4s", "delta": "-0.3s", "position": "0 2.08 -2.2"},
                    {"label": "Open Chats", "value": "7", "delta": "2 escalated", "position": "1.45 1.95 -2.35"},
                ],
                "notifications": [
                    "Knowledge base refreshed for indicator references",
                    "Two unanswered chat threads require review",
                    "Response latency returned to nominal levels",
                ],
                "charts": [0.31, 0.52, 0.61, 0.84, 0.79, 0.92],
            },
        ),
        (
            "/dashboard/data/",
            {
                "scene_variant": "data-catalog",
                "menu": ["Catalog", "Topics", "Indicators", "Metadata", "Tables"],
                "analytics_title": "Dataset Access Pattern",
                "analytics_subtitle": "topic and indicator exploration volume",
                "notifications_title": "Catalog Notifications",
                "widget_title": "Data Explorer Dock",
                "widget_lines": [
                    "Use the floating panels to compare topics, indicators, and metadata.",
                    "Secondary panels can be moved closer for detailed inspection.",
                ],
                "kpis": [
                    {"label": "Topics", "value": "42", "delta": "6 updated", "position": "-1.45 1.95 -2.35"},
                    {"label": "Indicators", "value": "318", "delta": "+14", "position": "0 2.08 -2.2"},
                    {"label": "Coverage", "value": "87%", "delta": "metadata synced", "position": "1.45 1.95 -2.35"},
                ],
                "notifications": [
                    "Three indicator definitions were revised this week",
                    "Metadata sync completed for policy topic library",
                    "One topic detail page is pending validation",
                ],
                "charts": [0.42, 0.63, 0.74, 0.69, 0.83, 0.78],
            },
        ),
        (
            "/dashboard/statistics/",
            {
                "menu": ["Scorecards", "Goals", "Bodies", "Trends", "Benchmarks"],
                "analytics_title": "Scorecard Performance Arc",
                "analytics_subtitle": "policy, goal, and ministry comparisons",
                "notifications_title": "Performance Alerts",
                "widget_title": "Scorecard Workspace",
                "widget_lines": [
                    "Bring policy area and public body panels together for comparison.",
                    "Spatial separation keeps dense scorecard walls readable in XR.",
                ],
                "kpis": [
                    {"label": "Policy Areas", "value": "17", "delta": "4 improving", "position": "-1.45 1.95 -2.35"},
                    {"label": "Goals Tracked", "value": "63", "delta": "+5 scorecards", "position": "0 2.08 -2.2"},
                    {"label": "Bodies Flagged", "value": "9", "delta": "review needed", "position": "1.45 1.95 -2.35"},
                ],
                "notifications": [
                    "Two ministries fell below the benchmark threshold",
                    "Goal scorecards updated with this month reporting batch",
                    "High-frequency dashboard refreshed from latest feed",
                ],
                "charts": [0.58, 0.49, 0.77, 0.72, 0.64, 0.89],
            },
        ),
        (
            "/dashboard/projects/",
            {
                "menu": ["Projects", "Initiatives", "Delivery", "Risks", "Milestones"],
                "analytics_title": "Project Delivery Velocity",
                "analytics_subtitle": "implementation and milestone completion",
                "notifications_title": "Delivery Notifications",
                "widget_title": "Program Control Dock",
                "widget_lines": [
                    "Arrange sector project and initiative panels by delivery urgency.",
                    "Use depth layering to separate milestone, risk, and budget views.",
                ],
                "kpis": [
                    {"label": "Active Projects", "value": "28", "delta": "5 delayed", "position": "-1.45 1.95 -2.35"},
                    {"label": "Initiatives", "value": "12", "delta": "2 launched", "position": "0 2.08 -2.2"},
                    {"label": "Milestones", "value": "74%", "delta": "completion rate", "position": "1.45 1.95 -2.35"},
                ],
                "notifications": [
                    "One sector project moved into delayed status",
                    "National initiative milestone pack approved",
                    "Budget variance narrowed across implementation portfolio",
                ],
                "charts": [0.37, 0.56, 0.68, 0.73, 0.81, 0.87],
            },
        ),
        (
            "/dashboard/account/",
            {
                "menu": ["Profile", "Security", "Preferences", "Sessions", "Access"],
                "analytics_title": "Account Activity Pattern",
                "analytics_subtitle": "profile and security events",
                "notifications_title": "Security Notifications",
                "widget_title": "Identity Controls",
                "widget_lines": [
                    "Keep profile and password controls in the front interaction arc.",
                    "Use the alert stack to surface suspicious access or pending actions.",
                ],
                "kpis": [
                    {"label": "Sessions", "value": "3", "delta": "1 current", "position": "-1.45 1.95 -2.35"},
                    {"label": "Security Score", "value": "92%", "delta": "strong", "position": "0 2.08 -2.2"},
                    {"label": "Pending Actions", "value": "1", "delta": "password review", "position": "1.45 1.95 -2.35"},
                ],
                "notifications": [
                    "Password policy check completed successfully",
                    "Profile details were updated in the last session",
                    "No abnormal login events detected",
                ],
                "charts": [0.28, 0.47, 0.59, 0.62, 0.54, 0.71],
            },
        ),
    ]

    for prefix, profile in profiles:
        if source_page_url.startswith(prefix):
            merged = base_profile.copy()
            merged.update(profile)
            return merged

    if source_page_title:
        base_profile["analytics_title"] = f"{source_page_title} Activity"
    return base_profile


def privacy_policy(request):
    privacy_policy = Setting.objects.get(id=1)
    return render(request , 'privacy_policy.html' , {'privacy_policy':privacy_policy})


@login_required(login_url="/dashboard/login/")
def vr_image_proxy(request):
    raw_url = str(request.GET.get("url", "")).strip()
    if not raw_url:
        return HttpResponseBadRequest("Missing url")

    allowed_hosts = {"time-series.mopd.gov.et"}
    parsed = urlparse(raw_url)
    if not parsed.scheme:
        raw_url = urljoin("https://time-series.mopd.gov.et/", raw_url.lstrip("/"))
        parsed = urlparse(raw_url)

    if parsed.scheme not in {"http", "https"} or parsed.netloc not in allowed_hosts:
        return HttpResponseBadRequest("Unsupported asset host")

    try:
        upstream_request = Request(
            raw_url,
            headers={
                "User-Agent": "DigitalHubVR/1.0",
                "Accept": "image/*,*/*;q=0.8",
            },
        )
        with urlopen(upstream_request, timeout=10) as response:
            body = response.read()
            content_type = response.headers.get_content_type() or "application/octet-stream"
            proxy_response = HttpResponse(body, content_type=content_type)
            cache_control = response.headers.get("Cache-Control")
            if cache_control:
                proxy_response["Cache-Control"] = cache_control
            else:
                proxy_response["Cache-Control"] = "public, max-age=3600"
            return proxy_response
    except Exception:
        return HttpResponseNotFound("Asset unavailable")


@login_required(login_url="/dashboard/login/")
def vr_dashboard(request):
    available_pages = _build_vr_page_registry()
    source_page_url = request.GET.get("source", "").strip()
    if not source_page_url.startswith("/dashboard/") or source_page_url.startswith("/dashboard/vr/"):
        source_page_url = reverse("dashboard_home")

    source_page_title = request.GET.get("title", "").strip() or "Current Dashboard Page"
    category_id = request.GET.get("category", "").strip()
    category_title = request.GET.get("category_title", "").strip()
    scene_profile = _build_scene_profile(source_page_url, source_page_title, category_id=category_id or None)
    dashboard_payload = {
        "kpis": scene_profile["kpis"],
        "menu": scene_profile["menu"],
        "notifications": scene_profile["notifications"],
        "charts": scene_profile["charts"],
        "analyticsTitle": scene_profile["analytics_title"],
        "analyticsSubtitle": scene_profile["analytics_subtitle"],
        "notificationsTitle": scene_profile["notifications_title"],
        "widgetTitle": scene_profile["widget_title"],
        "widgetLines": scene_profile["widget_lines"],
        "sceneVariant": scene_profile["scene_variant"],
        "sectionPanels": scene_profile["section_panels"],
        "dataEndpoints": {
            "defaultTime": "/api/mobile/default-time/",
            "topics": "/api/mobile/topic-list/",
            "topicDetailBase": "/api/mobile/topic-detail/",
            "categoriesBase": "/api/mobile/categories/",
            "kpisBase": "/api/mobile/kpis/",
            "ministries": "/api/mobile/ministries/",
            "trending": "/api/mobile/trending/",
            "projects": "/api/mobile/project-list/",
            "initiatives": "/api/mobile/initiatives/",
            "mediaBaseUrl": "https://time-series.mopd.gov.et/",
            "imageProxy": reverse("vr_image_proxy"),
        },
        "pages": available_pages,
        "sourcePage": {
            "title": source_page_title,
            "url": source_page_url,
        },
        "categorySelection": {
            "id": category_id,
            "title": category_title,
        },
    }
    return render(
        request,
        'vr_dashboard.html',
        {
            "dashboard_payload": dashboard_payload,
            "available_pages": available_pages,
            "source_page_url": source_page_url,
            "source_page_title": source_page_title,
            "scene_profile": scene_profile,
        },
    )
