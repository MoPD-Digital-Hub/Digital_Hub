from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from AI.models import ChatInstance, QuestionHistory


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
def sample_dashboard(request):
    context = {
    }
    return render(request, "dashboard/sample.html", context)


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
