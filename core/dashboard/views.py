from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from AI.models import ChatInstance, QuestionHistory

from .forms import DashboardPasswordChangeForm, DashboardProfileForm


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
