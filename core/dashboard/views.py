import json
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from AI.models import ChatInstance, QuestionHistory

from .forms import DashboardPasswordChangeForm, DashboardProfileForm


SDG_DATA_TEMPLATE = "https://sdg.mopd.gov.et/_next/data/IKzAUZqfiBSFdEHfm_tML/goals/sdg/{goal_id}.json"


def _open_remote_json(url):
    request = Request(url, headers={"User-Agent": "DigitalHub/1.0"})
    contexts = [ssl.create_default_context(), ssl._create_unverified_context()]

    last_error = None
    for context in contexts:
        try:
            with urlopen(request, timeout=20, context=context) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError, ssl.SSLError, json.JSONDecodeError) as exc:
            last_error = exc

    raise last_error or RuntimeError("Unable to load remote SDG data")


def _build_sdg_payload(goal_id):
    remote_payload = _open_remote_json(SDG_DATA_TEMPLATE.format(goal_id=goal_id))
    page_props = remote_payload.get("pageProps", {})
    sdg_data = page_props.get("data", {}).get("sdg", {})

    goals = list(sdg_data.get("goals") or [])
    selected_goal = next((goal for goal in goals if str(goal.get("id")) == str(goal_id)), None)
    targets = [
        target
        for target in (sdg_data.get("targets") or [])
        if str(target.get("goal")) == str(goal_id)
    ]
    indicators = [
        indicator
        for indicator in (sdg_data.get("indicators") or [])
        if str(indicator.get("goal")) == str(goal_id)
    ]

    return {
        "countryName": page_props.get("countryName") or "Ethiopia",
        "country": page_props.get("country") or "ethiopia",
        "framework": page_props.get("framework") or "sdg",
        "goal": selected_goal,
        "goals": goals,
        "targets": targets,
        "indicators": indicators,
    }


def dashboard_login(request):
    if request.user.is_authenticated:
        return redirect("dashboard_home")

    next_url = request.GET.get("next") or request.POST.get("next") or "/dashboard/"
    error = None

    if request.method == "POST":
        email = str(request.POST.get("email", "")).strip().lower()
        password = request.POST.get("password", "")

        user = authenticate(request=request, email=email, password=password)
        if user is None:
            user = authenticate(request=request, username=email, password=password)

        if user is not None:
            login(request, user)
            if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                next_url = "/dashboard/"
            return redirect(next_url)

        error = "Invalid email or password."
        messages.error(request, error)

    return render(request, "dashboard/login.html", {"next": next_url, "error": error})


@login_required(login_url="/dashboard/login/")
def dashboard_logout(request):
    logout(request)
    return redirect("dashboard_login")


@login_required(login_url="/dashboard/login/")
def sample_dashboard(request):
    context = {
    }
    return render(request, "dashboard/sample.html", context)


@login_required(login_url="/dashboard/login/")
def about_dpmes_page(request):
    context = {
        "page_title": "About DPMES",
        "subtitle": "Understand the national platform story, governance model, and result framework.",
    }
    return render(request, "data-hub/pages/about-dpmes.html", context)


@login_required(login_url="/dashboard/login/")
def edit_profile_page(request):
    if request.method == "POST":
        form = DashboardProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("edit_profile")
    else:
        form = DashboardProfileForm(instance=request.user)

    context = {
        "page_title": "Edit Profile",
        "subtitle": "Update your personal and account information.",
        "form": form,
    }
    return render(request, "data-hub/pages/account-profile.html", context)


@login_required(login_url="/dashboard/login/")
def change_password_page(request):
    if request.method == "POST":
        form = DashboardPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Password changed successfully.")
            return redirect("change_password")
    else:
        form = DashboardPasswordChangeForm(request.user)

    context = {
        "page_title": "Change Password",
        "subtitle": "Manage your dashboard password securely.",
        "form": form,
    }
    return render(request, "data-hub/pages/account-password.html", context)


@login_required(login_url="/dashboard/login/")
def admas_ai_page(request):
    chat_instances = list(
        ChatInstance.objects.filter(user=request.user, is_deleted=False).order_by("-created_at")
    )
    if not chat_instances:
        chat_instances = [ChatInstance.objects.create(user=request.user, title="New Chat")]

    active_instance = chat_instances[0]
    history = list(
        QuestionHistory.objects.filter(instance=active_instance)
        .order_by("created_at")
        .values("question", "response")
    )

    context = {
        "page_title": "Admas AI",
        "subtitle": "Ask policy and indicator questions with AI assistance.",
        "chat_instances": chat_instances,
        "active_instance": active_instance,
        "history": history,
    }
    return render(request, "data-hub/admas-ai.html", context)


@login_required(login_url="/dashboard/login/")
def data_categories_page(request):
    context = {
        "page_title": "Data",
        "subtitle": "Browse policy topics, datasets, and KPI groups from a dedicated data catalog.",
    }
    return render(request, "data-hub/pages/data.html", context)


@login_required(login_url="/dashboard/login/")
def data_topic_detail_page(request, topic_id):
    context = {
        "page_title": "Topic Detail",
        "subtitle": "Inspect topic metadata, KPI coverage, and related content.",
        "topic_id": topic_id,
    }
    return render(request, "data-hub/pages/data-topic-detail.html", context)


@login_required(login_url="/dashboard/login/")
def data_indicator_detail_page(request, indicator_id):
    context = {
        "page_title": "Indicator Detail",
        "subtitle": "Inspect indicator metadata, trends, tables, and historical values.",
        "indicator_id": indicator_id,
    }
    return render(request, "data-hub/pages/data-indicator-detail.html", context)


@login_required(login_url="/dashboard/login/")
def policy_area_detail_page(request, policy_area_id):
    context = {
        "page_title": "Policy Area Detail",
        "subtitle": "Review policy area scorecards, metadata, and related program structures.",
        "policy_area_id": policy_area_id,
    }
    return render(request, "data-hub/pages/policy-area-detail.html", context)


@login_required(login_url="/dashboard/login/")
def goal_detail_page(request, goal_id):
    context = {
        "page_title": "Goal Detail",
        "subtitle": "Review goal-level scorecards, ownership, and supporting structures.",
        "goal_id": goal_id,
    }
    return render(request, "data-hub/pages/goal-detail.html", context)


@login_required(login_url="/dashboard/login/")
def policy_area_list_page(request):
    context = {
        "page_title": "Policy Areas",
        "subtitle": "Browse policy area scorecards and open detailed views.",
    }
    return render(request, "data-hub/pages/policy-area-list.html", context)


@login_required(login_url="/dashboard/login/")
def public_body_list_page(request):
    context = {
        "page_title": "Public Bodies",
        "subtitle": "Browse public body scorecards and compare ministry performance by reporting period.",
    }
    return render(request, "data-hub/pages/public-body-list.html", context)


@login_required(login_url="/dashboard/login/")
def public_body_detail_page(request, ministry_id):
    context = {
        "page_title": "Public Body Detail",
        "subtitle": "Review public body scorecards across policy areas and strategic goals.",
        "ministry_id": ministry_id,
    }
    return render(request, "data-hub/pages/public-body-detail.html", context)


@login_required(login_url="/dashboard/login/")
def high_frequency_dashboard_page(request):
    context = {
        "page_title": "High Frequency Dashboard",
        "subtitle": "Review configured high-frequency indicator widgets in a dashboard layout.",
    }
    return render(request, "data-hub/pages/high-frequency-dashboard.html", context)


@login_required(login_url="/dashboard/login/")
def sector_project_list_page(request):
    context = {
        "page_title": "Sector Projects",
        "subtitle": "Browse sector-level projects, implementation domains, and supporting project narratives.",
    }
    return render(request, "data-hub/pages/sector-project-list.html", context)


@login_required(login_url="/dashboard/login/")
def sector_project_detail_page(request, project_id):
    context = {
        "page_title": "Project Detail",
        "subtitle": "Review sector project context, sub-project delivery, and implementation details.",
        "project_id": project_id,
    }
    return render(request, "data-hub/pages/sector-project-detail.html", context)


@login_required(login_url="/dashboard/login/")
def initiative_list_page(request):
    context = {
        "page_title": "National Initiatives",
        "subtitle": "Review national initiatives, strategic narratives, and implementation focus areas in one place.",
    }
    return render(request, "data-hub/pages/initiative-list.html", context)


@login_required(login_url="/dashboard/login/")
def initiative_detail_page(request, initiative_id):
    context = {
        "page_title": "Initiative Detail",
        "subtitle": "Review initiative context, implementation narrative, and summary metadata.",
        "initiative_id": initiative_id,
    }
    return render(request, "data-hub/pages/initiative-detail.html", context)


@login_required(login_url="/dashboard/login/")
def sdg_list_page(request):
    context = {
        "page_title": "Sustainable Development Goals",
        "subtitle": "Browse the 17 SDGs, open goal-level detail views, and explore targets and indicators from the national SDG platform.",
    }
    return render(request, "data-hub/pages/sdg-list.html", context)


@login_required(login_url="/dashboard/login/")
def sdg_detail_page(request, goal_id):
    context = {
        "page_title": "SDG Detail",
        "subtitle": "Review goal narratives, targets, and indicator evidence from the national SDG platform.",
        "goal_id": goal_id,
    }
    return render(request, "data-hub/pages/sdg-detail.html", context)


@login_required(login_url="/dashboard/login/")
def sdg_data_page(request, goal_id):
    context = {
        "page_title": "SDG Data Explorer",
        "subtitle": "Explore goal indicators, charts, downloads, and disaggregation views from the national SDG platform.",
        "goal_id": goal_id,
    }
    return render(request, "data-hub/pages/sdg-data.html", context)


@login_required(login_url="/dashboard/login/")
def sdg_list_data(request):
    try:
        payload = _build_sdg_payload(goal_id=1)
    except Exception as exc:
        return JsonResponse({"detail": "Unable to load SDG catalog.", "error": str(exc)}, status=502)

    return JsonResponse(
        {
            "countryName": payload["countryName"],
            "goals": payload["goals"],
        }
    )


@login_required(login_url="/dashboard/login/")
def sdg_detail_data(request, goal_id):
    try:
        payload = _build_sdg_payload(goal_id=goal_id)
    except Exception as exc:
        return JsonResponse({"detail": "Unable to load SDG detail.", "error": str(exc)}, status=502)

    if payload["goal"] is None:
        return JsonResponse({"detail": "SDG goal not found."}, status=404)

    return JsonResponse(payload)
