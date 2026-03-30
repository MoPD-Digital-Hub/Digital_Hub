import logging
import re
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from AI.gemini import get_gemini_settings
from AI.models import ChatInstance, QuestionHistory
from AI.retrieval import MilvusContextRetriever, RetrievalError
from AI.orchestration import AIOrchestrator, OrchestrationError, get_orchestration_settings
from AI.responses import error, ok
from AI.serializers import ChatInstanceSerializer, QuestionHistorySerializer

LOGGER = logging.getLogger("AI.api")
GENERIC_INSTANCE_TITLES = {"", "new chat", "new instance"}


def _instance_for_user(user, chat_instance_id):
    return ChatInstance.objects.filter(id=chat_instance_id, user=user, is_deleted=False).first()


def _history_records(instance, *, exclude_empty=True):
    queryset = QuestionHistory.objects.filter(instance=instance).order_by("created_at")
    if exclude_empty:
        queryset = queryset.exclude(response__isnull=True).exclude(response="")
    return list(queryset.values("question", "response", "tool_data", "chart_data"))


def _looks_generic_title(title: str) -> bool:
    return str(title or "").strip().lower() in GENERIC_INSTANCE_TITLES


def _build_instance_title(question: str) -> str:
    text = re.sub(r"\s+", " ", str(question or "").strip())
    if not text:
        return "General Chat"
    text = re.sub(r"[?.!]+$", "", text).strip()
    if len(text) <= 60:
        return text
    shortened = text[:57].rsplit(" ", 1)[0].strip()
    return (shortened or text[:57].strip()) + "..."


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def health(request):
    settings = get_gemini_settings()
    return ok(
        request,
        {
            "provider": "gemini",
            "model": settings.model,
            "configured": bool(settings.api_key),
        },
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dependency_health(request):
    settings = get_gemini_settings()
    orchestration = get_orchestration_settings()
    retrieval = MilvusContextRetriever()
    return ok(
        request,
        {
            "dependencies": {
                "gemini": {
                    "ok": bool(settings.api_key),
                    "model": settings.model,
                },
                "milvus": retrieval.health(),
                "dashboard": {
                    "ok": bool(orchestration.dashboard_create_url),
                    "url": orchestration.dashboard_create_url,
                },
            }
        },
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def chat_instances(request):
    if request.method == "GET":
        instances = ChatInstance.objects.filter(user=request.user, is_deleted=False).order_by("-created_at")
        return ok(request, ChatInstanceSerializer(instances, many=True).data)

    title = str((request.data or {}).get("title") or "").strip() or "New Chat"
    instance = ChatInstance.objects.create(user=request.user, title=title)
    return ok(request, ChatInstanceSerializer(instance).data, status_code=status.HTTP_201_CREATED)


@api_view(["PATCH", "PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def chat_instance_detail(request, chat_instance_id):
    instance = _instance_for_user(request.user, chat_instance_id)
    if instance is None:
        return error(request, "INSTANCE_NOT_FOUND", "Chat instance not found.", status.HTTP_404_NOT_FOUND)

    if request.method == "DELETE":
        instance.is_deleted = True
        instance.save(update_fields=["is_deleted"])
        return ok(request, {"id": instance.id}, message="INSTANCE_DELETED")

    title = str((request.data or {}).get("title") or "").strip()
    if not title:
        return error(request, "TITLE_REQUIRED", "title is required", status.HTTP_400_BAD_REQUEST)

    instance.title = title
    instance.save(update_fields=["title"])
    return ok(request, ChatInstanceSerializer(instance).data, message="INSTANCE_UPDATED")


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def chat_history(request, chat_instance_id):
    instance = _instance_for_user(request.user, chat_instance_id)
    if instance is None:
        return error(request, "INSTANCE_NOT_FOUND", "Chat instance not found.", status.HTTP_404_NOT_FOUND)

    rows = QuestionHistory.objects.filter(instance=instance).order_by("created_at")
    return ok(request, QuestionHistorySerializer(rows, many=True).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def answer(request, chat_instance_id):
    instance = _instance_for_user(request.user, chat_instance_id)
    if instance is None:
        return error(request, "INSTANCE_NOT_FOUND", "Chat instance not found.", status.HTTP_404_NOT_FOUND)

    question = str((request.data or {}).get("question") or "").strip()
    if not question:
        return error(request, "QUESTION_REQUIRED", "question is required", status.HTTP_400_BAD_REQUEST)

    history = _history_records(instance)
    record = QuestionHistory.objects.create(instance=instance, question=question)
    orchestrator = AIOrchestrator()
    try:
        result = orchestrator.handle(question=question, history_records=history)
    except OrchestrationError as exc:
        return error(
            request,
            exc.code,
            exc.message,
            status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"exception": exc.detail, "intent": exc.intent},
        )

    record.response = result.message
    record.chart_data = result.charts or []
    record.tool_data = result.tool_state or {}
    record.save(update_fields=["response", "chart_data", "tool_data"])
    if _looks_generic_title(instance.title):
        instance.title = _build_instance_title(question)
        instance.save(update_fields=["title"])
    return ok(
        request,
        {
            "chat_instance_id": instance.id,
            "chat_title": instance.title,
            "question": question,
            "intent": result.intent,
            "response_type": result.response_type,
            "secondary_intents": result.secondary_intents,
            "answer": result.message,
            "language": result.language,
            "usage": result.usage,
            "context_found": result.context_found,
            "sources": result.sources or [],
            "charts": result.charts or [],
            "tool_data": result.tool_state or {},
            "response_data": result.data or {},
        },
    )
