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
        {"title": "Data Catalog", "url": reverse("data_categories")},
        {"title": "Topic Detail", "url": reverse("data_topic_detail", kwargs={"topic_id": 1})},
        {"title": "Indicator Detail", "url": reverse("data_indicator_detail", kwargs={"indicator_id": 1})},
        {"title": "Policy Areas", "url": reverse("policy_area_list")},
        {"title": "Policy Area Detail", "url": reverse("policy_area_detail", kwargs={"policy_area_id": 1})},
        {"title": "Goal Detail", "url": reverse("goal_detail", kwargs={"goal_id": 1})},
        {"title": "Public Bodies", "url": reverse("public_body_list")},
        {"title": "Public Body Detail", "url": reverse("public_body_detail", kwargs={"ministry_id": 1})},
        {"title": "Sector Projects", "url": reverse("sector_project_list")},
        {"title": "Sector Project Detail", "url": reverse("sector_project_detail", kwargs={"project_id": 1})},
        {"title": "National Initiatives", "url": reverse("initiative_list")},
        {"title": "Initiative Detail", "url": reverse("initiative_detail", kwargs={"initiative_id": 1})},
    ]


def _build_scene_profile(source_page_url, source_page_title, category_id=None, kra_id=None, project_sub_id=None):
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

    if source_page_url == reverse("policy_area_list") or source_page_url.startswith(f"{reverse('policy_area_list')}?"):
        policy_catalog_profile = {
            "scene_variant": "policy-area-catalog",
            "menu": ["Policy Areas", "Scores", "Goals", "Ministries", "Insights"],
            "analytics_title": "Policy Area Overview",
            "analytics_subtitle": "immersive policy area catalog",
            "notifications_title": "Policy Area Signals",
            "widget_title": "Policy Explorer",
            "widget_lines": [
                "Browse policy areas in a circular VR catalog.",
                "Open a policy area to inspect its goals and scorecards.",
            ],
            "kpis": [
                {"label": "Policy Areas", "value": "--", "delta": "loading", "position": "-1.45 1.95 -2.35"},
                {"label": "Goals", "value": "--", "delta": "loading", "position": "0 2.08 -2.2"},
                {"label": "Period", "value": "2018", "delta": "3month", "position": "1.45 1.95 -2.35"},
            ],
            "notifications": [
                "Policy area catalog is loading",
                "Goal counts and scorecards will populate per area",
                "Open a policy area to continue the VR drill-down",
            ],
            "charts": [0.41, 0.55, 0.62, 0.7, 0.68, 0.84],
        }
        merged = base_profile.copy()
        merged.update(policy_catalog_profile)
        return merged

    if source_page_url == reverse("public_body_list") or source_page_url.startswith(f"{reverse('public_body_list')}?"):
        ministry_catalog_profile = {
            "scene_variant": "ministry-catalog",
            "menu": ["Ministries", "Scores", "Goals", "Indicators", "Insights"],
            "analytics_title": "Ministry Overview",
            "analytics_subtitle": "immersive public body catalog",
            "notifications_title": "Ministry Signals",
            "widget_title": "Ministry Explorer",
            "widget_lines": [
                "Browse ministries in a circular VR catalog.",
                "Open a ministry to inspect its goals and delivery structure.",
            ],
            "kpis": [
                {"label": "Ministries", "value": "--", "delta": "loading", "position": "-1.45 1.95 -2.35"},
                {"label": "Indicators", "value": "--", "delta": "loading", "position": "0 2.08 -2.2"},
                {"label": "Period", "value": "2017", "delta": "3month", "position": "1.45 1.95 -2.35"},
            ],
            "notifications": [
                "Ministry catalog is loading",
                "Indicator counts and scorecards will populate per ministry",
                "Open a ministry card to continue the VR drill-down",
            ],
            "charts": [0.38, 0.52, 0.61, 0.69, 0.74, 0.82],
        }
        merged = base_profile.copy()
        merged.update(ministry_catalog_profile)
        return merged

    if source_page_url == reverse("sector_project_list") or source_page_url.startswith(f"{reverse('sector_project_list')}?"):
        project_catalog_profile = {
            "scene_variant": "project-catalog",
            "menu": ["Projects", "Sectors", "Details", "Delivery", "Insights"],
            "analytics_title": "Sector Project Catalog",
            "analytics_subtitle": "immersive project entry ring",
            "notifications_title": "Project Signals",
            "widget_title": "Project Explorer",
            "widget_lines": [
                "Browse sector projects in a circular VR catalog.",
                "Open a project card to inspect sub-projects and implementation metrics.",
            ],
            "kpis": [
                {"label": "Projects", "value": "--", "delta": "loading", "position": "-1.45 1.95 -2.35"},
                {"label": "Images", "value": "--", "delta": "loading", "position": "0 2.08 -2.2"},
                {"label": "Scene", "value": "VR", "delta": "sector projects", "position": "1.45 1.95 -2.35"},
            ],
            "notifications": [
                "Project catalog is loading",
                "Each card uses the project image when available",
                "Open a project card to inspect its detail scene",
            ],
            "charts": [0.39, 0.53, 0.61, 0.69, 0.75, 0.82],
        }
        merged = base_profile.copy()
        merged.update(project_catalog_profile)
        return merged

    if source_page_url == reverse("initiative_list") or source_page_url.startswith(f"{reverse('initiative_list')}?"):
        initiative_catalog_profile = {
            "scene_variant": "initiative-catalog",
            "menu": ["Initiatives", "Focus", "Categories", "Indicators", "Insights"],
            "analytics_title": "National Initiative Catalog",
            "analytics_subtitle": "immersive initiative entry ring",
            "notifications_title": "Initiative Signals",
            "widget_title": "Initiative Explorer",
            "widget_lines": [
                "Browse national initiatives in a circular VR catalog.",
                "Open an initiative card to inspect its detail scene.",
            ],
            "kpis": [
                {"label": "Initiatives", "value": "--", "delta": "loading", "position": "-1.45 1.95 -2.35"},
                {"label": "Categories", "value": "--", "delta": "loading", "position": "0 2.08 -2.2"},
                {"label": "Scene", "value": "VR", "delta": "national initiatives", "position": "1.45 1.95 -2.35"},
            ],
            "notifications": [
                "Initiative catalog is loading",
                "Each card uses the initiative image when available",
                "Open an initiative card to inspect its detail scene",
            ],
            "charts": [0.36, 0.48, 0.58, 0.66, 0.73, 0.8],
        }
        merged = base_profile.copy()
        merged.update(initiative_catalog_profile)
        return merged

    if (
        source_page_url.startswith("/dashboard/statistics/public-bodies/")
        and source_page_url != reverse("public_body_list")
        and not source_page_url.startswith(f"{reverse('public_body_list')}?")
    ):
        ministry_detail_profile = {
            "scene_variant": "ministry-detail",
            "menu": ["Overview", "Goals", "Policy Areas", "Indicators", "Insights"],
            "analytics_title": "Ministry Structure",
            "analytics_subtitle": "goal-level exploration across the selected ministry",
            "notifications_title": "Ministry Signals",
            "widget_title": "Ministry Focus",
            "widget_lines": [
                "Goal cards around the center open ministry goal detail in VR.",
                "The room uses the selected reporting period from the 2D page.",
            ],
            "kpis": [
                {"label": "Goals", "value": "--", "delta": "loading", "position": "-1.45 1.95 -2.35"},
                {"label": "Score", "value": "--", "delta": "loading", "position": "0 2.08 -2.2"},
                {"label": "Ministry", "value": "Detail", "delta": source_page_title or "Selected ministry", "position": "1.45 1.95 -2.35"},
            ],
            "notifications": [
                "Ministry detail scene is loading goals",
                "Goal scorecards will appear around the selected ministry",
                "Open a goal to inspect key result areas",
            ],
            "charts": [0.42, 0.58, 0.64, 0.72, 0.78, 0.84],
        }
        merged = base_profile.copy()
        merged.update(ministry_detail_profile)
        return merged

    if project_sub_id and (
        source_page_url.startswith("/dashboard/projects/sector/")
        and source_page_url != reverse("sector_project_list")
        and not source_page_url.startswith(f"{reverse('sector_project_list')}?")
    ):
        project_sub_detail_profile = {
            "scene_variant": "project-sub-detail",
            "menu": ["Overview", "Pictures", "Details", "Delivery", "Return"],
            "analytics_title": "Sub-Project Detail Room",
            "analytics_subtitle": "pictures and structured detail fields for the selected sub-project",
            "notifications_title": "Sub-Project Signals",
            "widget_title": "Sub-Project Focus",
            "widget_lines": [
                "The selected sub-project sits at the center of the room.",
                "Detail panels show the structured fields from the project data row.",
            ],
            "kpis": [
                {"label": "Sub-Project", "value": "Detail", "delta": "loading", "position": "-1.45 1.95 -2.35"},
                {"label": "Pictures", "value": "--", "delta": "loading", "position": "0 2.08 -2.2"},
                {"label": "Fields", "value": "--", "delta": "loading", "position": "1.45 1.95 -2.35"},
            ],
            "notifications": [
                "Sub-project detail scene is loading",
                "Pictures and structured fields will populate around the center",
                "Use this room for the full sub-project details",
            ],
            "charts": [0.34, 0.47, 0.59, 0.66, 0.73, 0.81],
        }
        merged = base_profile.copy()
        merged.update(project_sub_detail_profile)
        return merged

    if (
        source_page_url.startswith("/dashboard/projects/sector/")
        and source_page_url != reverse("sector_project_list")
        and not source_page_url.startswith(f"{reverse('sector_project_list')}?")
    ):
        project_detail_profile = {
            "scene_variant": "project-detail",
            "menu": ["Overview", "Sub Projects", "Metrics", "Delivery", "Insights"],
            "analytics_title": "Project Detail Room",
            "analytics_subtitle": "sub-projects and implementation metrics for the selected project",
            "notifications_title": "Project Detail Signals",
            "widget_title": "Project Focus",
            "widget_lines": [
                "Sub-project cards are arranged around the selected project.",
                "Project imagery is used on the center cube when available.",
            ],
            "kpis": [
                {"label": "Project", "value": "Detail", "delta": "loading", "position": "-1.45 1.95 -2.35"},
                {"label": "Sub Projects", "value": "--", "delta": "loading", "position": "0 2.08 -2.2"},
                {"label": "Metrics", "value": "--", "delta": "loading", "position": "1.45 1.95 -2.35"},
            ],
            "notifications": [
                "Project detail scene is loading",
                "Sub-project metric cards will appear around the center",
                "Project imagery will anchor the room when available",
            ],
            "charts": [0.37, 0.51, 0.62, 0.7, 0.76, 0.83],
        }
        merged = base_profile.copy()
        merged.update(project_detail_profile)
        return merged

    if (
        source_page_url.startswith("/dashboard/projects/initiatives/")
        and source_page_url != reverse("initiative_list")
        and not source_page_url.startswith(f"{reverse('initiative_list')}?")
    ):
        initiative_detail_profile = {
            "scene_variant": "initiative-detail",
            "menu": ["Overview", "Categories", "Indicators", "Story", "Insights"],
            "analytics_title": "Initiative Detail Room",
            "analytics_subtitle": "immersive initiative summary with category and KPI totals",
            "notifications_title": "Initiative Detail Signals",
            "widget_title": "Initiative Focus",
            "widget_lines": [
                "The selected initiative sits at the center of the room.",
                "Detail panels summarize categories, KPIs, and descriptive context.",
            ],
            "kpis": [
                {"label": "Initiative", "value": "Detail", "delta": "loading", "position": "-1.45 1.95 -2.35"},
                {"label": "Categories", "value": "--", "delta": "loading", "position": "0 2.08 -2.2"},
                {"label": "KPIs", "value": "--", "delta": "loading", "position": "1.45 1.95 -2.35"},
            ],
            "notifications": [
                "Initiative detail scene is loading",
                "Image-backed center cube will appear when available",
                "Summary panels will show counts and narrative context",
            ],
            "charts": [0.35, 0.49, 0.57, 0.65, 0.72, 0.79],
        }
        merged = base_profile.copy()
        merged.update(initiative_detail_profile)
        return merged

    if (
        source_page_url.startswith("/dashboard/statistics/policy-areas/")
        and source_page_url != reverse("policy_area_list")
        and not source_page_url.startswith(f"{reverse('policy_area_list')}?")
    ):
        policy_detail_profile = {
            "scene_variant": "policy-area-detail",
            "menu": ["Overview", "Goals", "Scores", "Ministries", "Insights"],
            "analytics_title": "Policy Area Structure",
            "analytics_subtitle": "goal-level exploration across the selected policy area",
            "notifications_title": "Policy Area Signals",
            "widget_title": "Policy Focus",
            "widget_lines": [
                "Goal cards around the center open goal detail in VR.",
                "Use the current reporting period from the 2D page for continuity.",
            ],
            "kpis": [
                {"label": "Goals", "value": "--", "delta": "loading", "position": "-1.45 1.95 -2.35"},
                {"label": "Score", "value": "--", "delta": "loading", "position": "0 2.08 -2.2"},
                {"label": "Policy Area", "value": "Detail", "delta": source_page_title or "Selected policy area", "position": "1.45 1.95 -2.35"},
            ],
            "notifications": [
                "Policy area detail scene is loading goals",
                "Goal scorecards will appear around the selected policy area",
                "Open a goal to inspect key result areas",
            ],
            "charts": [0.46, 0.59, 0.67, 0.72, 0.78, 0.83],
        }
        merged = base_profile.copy()
        merged.update(policy_detail_profile)
        return merged

    if kra_id and source_page_url.startswith("/dashboard/statistics/goals/") and "ministry_id=" in source_page_url:
        ministry_kra_detail_profile = {
            "scene_variant": "ministry-kra-detail",
            "menu": ["Indicators", "Trends", "Records", "History", "Return"],
            "analytics_title": "Ministry KRA Indicator Ring",
            "analytics_subtitle": "recent five-point history for indicators under this ministry key result area",
            "notifications_title": "Ministry KRA Signals",
            "widget_title": "Ministry KRA Focus",
            "widget_lines": [
                "Indicator cards surround the user for fast comparison.",
                "Each indicator card surfaces recent-5 trend points.",
            ],
            "kpis": [
                {"label": "KRA", "value": "Detail", "delta": "loading", "position": "-1.45 1.95 -2.35"},
                {"label": "Indicators", "value": "--", "delta": "loading", "position": "0 2.08 -2.2"},
                {"label": "Goal", "value": "VR", "delta": source_page_title or "Selected goal", "position": "1.45 1.95 -2.35"},
            ],
            "notifications": [
                "Ministry KRA detail scene is loading indicators",
                "Recent 5-point trend history will render around you",
                "Use the indicator ring to compare delivery quickly",
            ],
            "charts": [0.34, 0.48, 0.59, 0.69, 0.74, 0.81],
        }
        merged = base_profile.copy()
        merged.update(ministry_kra_detail_profile)
        return merged

    if kra_id and source_page_url.startswith("/dashboard/statistics/goals/"):
        kra_detail_profile = {
            "scene_variant": "policy-kra-detail",
            "menu": ["Indicators", "Trends", "Records", "History", "Return"],
            "analytics_title": "KRA Indicator Ring",
            "analytics_subtitle": "recent five-point history for indicators under this key result area",
            "notifications_title": "KRA Signals",
            "widget_title": "KRA Focus",
            "widget_lines": [
                "Indicator cards surround the user for fast comparison.",
                "Each indicator card surfaces recent-5 trend points.",
            ],
            "kpis": [
                {"label": "KRA", "value": "Detail", "delta": "loading", "position": "-1.45 1.95 -2.35"},
                {"label": "Indicators", "value": "--", "delta": "loading", "position": "0 2.08 -2.2"},
                {"label": "Goal", "value": "VR", "delta": source_page_title or "Selected goal", "position": "1.45 1.95 -2.35"},
            ],
            "notifications": [
                "KRA detail scene is loading indicators",
                "Recent 5-point trend history will render around you",
                "Use the indicator ring to compare delivery quickly",
            ],
            "charts": [0.34, 0.48, 0.59, 0.69, 0.74, 0.81],
        }
        merged = base_profile.copy()
        merged.update(kra_detail_profile)
        return merged

    if source_page_url.startswith("/dashboard/statistics/goals/") and "ministry_id=" in source_page_url:
        ministry_goal_detail_profile = {
            "scene_variant": "ministry-goal-detail",
            "menu": ["Overview", "KRAs", "Indicators", "Scores", "Insights"],
            "analytics_title": "Ministry Goal Structure",
            "analytics_subtitle": "key result areas arranged for immersive navigation",
            "notifications_title": "Ministry Goal Signals",
            "widget_title": "Ministry Goal Focus",
            "widget_lines": [
                "KRA cards open their own VR detail scene.",
                "Indicator counts and ministry goal scorecards stay visible in the room.",
            ],
            "kpis": [
                {"label": "KRAs", "value": "--", "delta": "loading", "position": "-1.45 1.95 -2.35"},
                {"label": "Indicators", "value": "--", "delta": "loading", "position": "0 2.08 -2.2"},
                {"label": "Goal", "value": "Detail", "delta": source_page_title or "Selected goal", "position": "1.45 1.95 -2.35"},
            ],
            "notifications": [
                "Ministry goal detail scene is loading key result areas",
                "Open a KRA to inspect indicators with recent history",
                "Scorecards mirror the current reporting period",
            ],
            "charts": [0.39, 0.54, 0.63, 0.68, 0.76, 0.82],
        }
        merged = base_profile.copy()
        merged.update(ministry_goal_detail_profile)
        return merged

    if source_page_url.startswith("/dashboard/statistics/goals/"):
        goal_detail_profile = {
            "scene_variant": "policy-goal-detail",
            "menu": ["Overview", "KRAs", "Indicators", "Scores", "Insights"],
            "analytics_title": "Goal Structure",
            "analytics_subtitle": "key result areas arranged for immersive navigation",
            "notifications_title": "Goal Signals",
            "widget_title": "Goal Focus",
            "widget_lines": [
                "KRA cards open their own VR detail scene.",
                "Indicator counts and goal scorecards stay visible in the room.",
            ],
            "kpis": [
                {"label": "KRAs", "value": "--", "delta": "loading", "position": "-1.45 1.95 -2.35"},
                {"label": "Indicators", "value": "--", "delta": "loading", "position": "0 2.08 -2.2"},
                {"label": "Goal", "value": "Detail", "delta": source_page_title or "Selected goal", "position": "1.45 1.95 -2.35"},
            ],
            "notifications": [
                "Goal detail scene is loading key result areas",
                "Open a KRA to inspect indicators with recent history",
                "Scorecards mirror the current reporting period",
            ],
            "charts": [0.39, 0.54, 0.63, 0.68, 0.76, 0.82],
        }
        merged = base_profile.copy()
        merged.update(goal_detail_profile)
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

    allowed_hosts = {"time-series.mopd.gov.et", "dpmes.mopd.gov.et"}
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
    kra_id = request.GET.get("kra", "").strip()
    kra_title = request.GET.get("kra_title", "").strip()
    project_sub_id = request.GET.get("project_sub", "").strip()
    project_sub_title = request.GET.get("project_sub_title", "").strip()
    scene_profile = _build_scene_profile(
        source_page_url,
        source_page_title,
        category_id=category_id or None,
        kra_id=kra_id or None,
        project_sub_id=project_sub_id or None,
    )
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
            "projectDetailBase": "/api/mobile/project-detail/",
            "initiatives": "/api/mobile/initiatives/",
            "initiativeDetailBase": "/api/mobile/initiative-detail/",
            "policyAreas": "/api/mobile/policy-areas/",
            "policyAreaDetailBase": "/api/mobile/policy-area-detail/",
            "goalDetailBase": "/api/mobile/goal-detail/",
            "dpmesIndicatorDetailBase": "/api/mobile/dpmes-indicator-detail/",
            "dpmesMinistries": "/api/mobile/ministries/",
            "ministryDetailBase": "/api/mobile/ministry-detail/",
            "ministryGoalDetailBase": "/api/mobile/ministry-goal-detail/",
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
        "kraSelection": {
            "id": kra_id,
            "title": kra_title,
        },
        "projectSubSelection": {
            "id": project_sub_id,
            "title": project_sub_title,
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
