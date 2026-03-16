import hashlib
import logging
import requests

from django.http import HttpResponse
from django.core.cache import cache
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from AI.models import QuestionHistory, ChatInstance
from .serializer import ChatInstanceSerializer, QuestionHistorySerializer
from AI.services import generate_answer
from AI.platform.observability import get_last_ingestion_report, snapshot_metrics
from AI.infrastructure import get_vector_store, run_dependency_checks
from AI.infrastructure.translation import translate_text_with_gemini
from AI.infrastructure.tts import synthesize_gemini_tts
from celery.result import AsyncResult
from project.celery import app as celery_app
from django.conf import settings
from AI.tasks import generate_answer_task

LOGGER = logging.getLogger("AI.api")


def _request_id(request):
    return getattr(request, "request_id", None)


def _ok(request, data=None, message="SUCCESS", status_code=status.HTTP_200_OK):
    return Response(
        {
            "result": "SUCCESS",
            "message": message,
            "request_id": _request_id(request),
            "data": data,
        },
        status=status_code,
    )


def _err(request, code, message, status_code, details=None):
    return Response(
        {
            "result": "FAILURE",
            "message": code,
            "request_id": _request_id(request),
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            },
            "data": None,
        },
        status=status_code,
    )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_chat_list(request, chat_instance_id):
    try:
        chat_instance = ChatInstance.objects.get(id=chat_instance_id)
    except ChatInstance.DoesNotExist:
        return _err(request, "INSTANCE_NOT_FOUND", "Instance doesn't exist!", status.HTTP_404_NOT_FOUND)

    histories = QuestionHistory.objects.filter(instance=chat_instance)
    histories_serializer = QuestionHistorySerializer(histories, many=True)
    return _ok(request, histories_serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_answers(request, chat_instance_id):
    """
    Compatibility endpoint:
    GET /api/ai-chat/answer/<chat_instance_id>/
    Returns answered Q/A rows for a given chat instance.
    """
    try:
        chat_instance = ChatInstance.objects.get(id=chat_instance_id, user=request.user, is_deleted=False)
    except ChatInstance.DoesNotExist:
        return _err(request, "INSTANCE_NOT_FOUND", "Instance doesn't exist!", status.HTTP_404_NOT_FOUND)

    answers = QuestionHistory.objects.filter(instance=chat_instance, response__isnull=False).order_by("created_at")
    serializer = QuestionHistorySerializer(answers, many=True)
    return _ok(request, serializer.data)


@api_view(['POST', 'GET'])
@permission_classes([IsAuthenticated])
def chat(request):
    if request.method == 'GET':
        chat_instances = ChatInstance.objects.filter(user=request.user, is_deleted=False)
        serializer = ChatInstanceSerializer(chat_instances, many=True)
        return _ok(request, serializer.data)

    elif request.method == 'POST':
        title = str((request.data or {}).get("title", "")).strip()
        instance = ChatInstance(user=request.user, title=title or "New Chat")
        instance.save()
        serializer = ChatInstanceSerializer(instance)
        return _ok(request, serializer.data)

    return _err(request, "INVALID_METHOD", "Page not found!", status.HTTP_400_BAD_REQUEST)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def update_chat_instance(request, chat_instance_id):
    try:
        chat_instance = ChatInstance.objects.get(user=request.user, id=chat_instance_id, is_deleted=False)
    except ChatInstance.DoesNotExist:
        return _err(request, "INSTANCE_NOT_FOUND", "Instance doesn't exist!", status.HTTP_404_NOT_FOUND)

    title = str((request.data or {}).get("title", "")).strip()
    if not title:
        return _err(request, "TITLE_REQUIRED", "title is required", status.HTTP_400_BAD_REQUEST)

    chat_instance.title = title
    chat_instance.save(update_fields=["title"])
    return _ok(request, ChatInstanceSerializer(chat_instance).data, message="Instance updated successfully!")


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def answer(request, chat_instance_id):
    """
    GET  -> list answered Q/A rows (compatibility behavior).
    POST -> accepts {"question": "..."} and returns generated answer.
    """
    try:
        chat_instance = ChatInstance.objects.get(id=chat_instance_id, user=request.user, is_deleted=False)
    except ChatInstance.DoesNotExist:
        return _err(request, "INSTANCE_NOT_FOUND", "Instance doesn't exist!", status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        answers = QuestionHistory.objects.filter(instance=chat_instance, response__isnull=False).order_by("created_at")
        serializer = QuestionHistorySerializer(answers, many=True)
        return _ok(request, serializer.data)

    question = (request.data or {}).get("question", "")
    question = str(question).strip()
    if not question:
        return _err(request, "QUESTION_REQUIRED", "question is required", status.HTTP_400_BAD_REQUEST)

    mode = request.query_params.get("mode", "").lower()
    if settings.AI_USE_ASYNC_QUEUE or mode == "async":
        try:
            task = generate_answer_task.delay(chat_instance.id, question, _request_id(request))
            return _ok(
                request,
                {
                    "task_id": task.id,
                    "chat_instance_id": chat_instance.id,
                    "question": question,
                    "status_url": f"/api/ai-chat/task-status/{task.id}/",
                },
                message="QUEUED",
                status_code=status.HTTP_202_ACCEPTED,
            )
        except Exception as exc:
            return _err(
                request,
                "QUEUE_UNAVAILABLE",
                "Async queue unavailable; try synchronous mode.",
                status.HTTP_503_SERVICE_UNAVAILABLE,
                details={"exception": str(exc)},
            )

    result = generate_answer(chat_instance, question)

    if result.status_code >= 400:
        return _err(
            request,
            result.message,
            result.error.get("message") if result.error else "AI request failed",
            result.status_code,
            details=result.error,
        )

    return _ok(
        request,
        {
            "chat_instance_id": chat_instance.id,
            "question": question,
            "answer": result.answer,
            "intent": result.intent,
            "token_usage": result.token_usage,
        },
        message=result.message,
        status_code=result.status_code,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def tts(request):
    text = str((request.data or {}).get("text", "")).strip()
    voice = str((request.data or {}).get("voice", "")).strip() or None
    language = str((request.data or {}).get("language", "English")).strip() or "English"
    if not text:
        return _err(request, "TEXT_REQUIRED", "text is required", status.HTTP_400_BAD_REQUEST)

    cache_key = "ai_tts:{digest}".format(
        digest=hashlib.sha256(
            "{voice}:{language}:{text}".format(voice=voice or "", language=language, text=text).encode("utf-8")
        ).hexdigest()
    )
    cached = cache.get(cache_key)
    if cached:
        audio_bytes, mime_type = cached
        response = HttpResponse(audio_bytes, content_type=mime_type or "audio/wav")
        response["Content-Disposition"] = 'inline; filename="admas-ai-response.wav"'
        response["Cache-Control"] = "private, max-age=3600"
        response["X-TTS-Cache"] = "HIT"
        return response

    try:
        audio_bytes, mime_type = synthesize_gemini_tts(text, voice_name=voice, language_hint=language)
    except ValueError as exc:
        return _err(request, "TEXT_REQUIRED", str(exc), status.HTTP_400_BAD_REQUEST)
    except requests.HTTPError as exc:
        details = {}
        if exc.response is not None:
            try:
                details = exc.response.json()
            except ValueError:
                details = {"response_text": exc.response.text[:500]}
        LOGGER.exception("Gemini TTS provider failure", extra={"details": details})
        return _err(
            request,
            "TTS_PROVIDER_FAILURE",
            details.get("error", {}).get("message") or "Gemini TTS request failed.",
            status.HTTP_502_BAD_GATEWAY,
            details=details,
        )
    except Exception as exc:
        return _err(
            request,
            "TTS_UNAVAILABLE",
            str(exc),
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    cache.set(
        cache_key,
        (audio_bytes, mime_type),
        timeout=int(getattr(settings, "AI_TTS_CACHE_TIMEOUT", 3600)),
    )

    response = HttpResponse(audio_bytes, content_type=mime_type or "audio/wav")
    response["Content-Disposition"] = 'inline; filename="admas-ai-response.wav"'
    response["Cache-Control"] = "private, max-age=3600"
    response["X-TTS-Cache"] = "MISS"
    return response


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def tts_prefetch(request):
    text = str((request.data or {}).get("text", "")).strip()
    voice = str((request.data or {}).get("voice", "")).strip() or None
    language = str((request.data or {}).get("language", "English")).strip() or "English"
    if not text:
        return _err(request, "TEXT_REQUIRED", "text is required", status.HTTP_400_BAD_REQUEST)

    cache_key = "ai_tts:{digest}".format(
        digest=hashlib.sha256(
            "{voice}:{language}:{text}".format(voice=voice or "", language=language, text=text).encode("utf-8")
        ).hexdigest()
    )
    if cache.get(cache_key):
        return _ok(request, {"cached": True}, message="TTS_CACHE_HIT")

    try:
        audio_bytes, mime_type = synthesize_gemini_tts(text, voice_name=voice, language_hint=language)
    except ValueError as exc:
        return _err(request, "TEXT_REQUIRED", str(exc), status.HTTP_400_BAD_REQUEST)
    except requests.HTTPError as exc:
        details = {}
        if exc.response is not None:
            try:
                details = exc.response.json()
            except ValueError:
                details = {"response_text": exc.response.text[:500]}
        LOGGER.exception("Gemini TTS prefetch provider failure", extra={"details": details})
        return _err(
            request,
            "TTS_PROVIDER_FAILURE",
            details.get("error", {}).get("message") or "Gemini TTS request failed.",
            status.HTTP_502_BAD_GATEWAY,
            details=details,
        )
    except Exception as exc:
        return _err(
            request,
            "TTS_UNAVAILABLE",
            str(exc),
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    cache.set(
        cache_key,
        (audio_bytes, mime_type),
        timeout=int(getattr(settings, "AI_TTS_CACHE_TIMEOUT", 3600)),
    )
    return _ok(request, {"cached": False}, message="TTS_WARMED")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def translate(request):
    text = str((request.data or {}).get("text", "")).strip()
    target_language = str((request.data or {}).get("target_language", "Amharic")).strip() or "Amharic"
    if not text:
        return _err(request, "TEXT_REQUIRED", "text is required", status.HTTP_400_BAD_REQUEST)

    cache_key = "ai_translate:{lang}:{digest}".format(
        lang=target_language.lower(),
        digest=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )
    cached_translation = cache.get(cache_key)
    if cached_translation:
        return _ok(
            request,
            {
                "translation": cached_translation,
                "target_language": target_language,
            },
            message="TRANSLATION_CACHE_HIT",
        )

    try:
        translated_text = translate_text_with_gemini(text, target_language=target_language)
    except ValueError as exc:
        return _err(request, "TEXT_REQUIRED", str(exc), status.HTTP_400_BAD_REQUEST)
    except requests.HTTPError as exc:
        details = {}
        if exc.response is not None:
            try:
                details = exc.response.json()
            except ValueError:
                details = {"response_text": exc.response.text[:500]}
        return _err(
            request,
            "TRANSLATION_PROVIDER_FAILURE",
            "Gemini translation request failed.",
            status.HTTP_502_BAD_GATEWAY,
            details=details,
        )
    except Exception as exc:
        return _err(
            request,
            "TRANSLATION_UNAVAILABLE",
            str(exc),
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    cache.set(
        cache_key,
        translated_text,
        timeout=int(getattr(settings, "AI_TRANSLATION_CACHE_TIMEOUT", 3600)),
    )

    return _ok(
        request,
        {
            "translation": translated_text,
            "target_language": target_language,
        },
        message="TRANSLATED",
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def task_status(request, task_id):
    task = AsyncResult(task_id, app=celery_app)
    payload = {"task_id": task_id, "state": task.state}
    if task.successful():
        payload["result"] = task.result
    elif task.failed():
        payload["error"] = str(task.result)
    return _ok(request, payload)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def health(request):
    checks = run_dependency_checks(names=["llm", "embeddings", "milvus"])
    summary = {
        "llm_configured": checks["llm"]["ok"],
        "embeddings_configured": checks["embeddings"]["ok"],
        "milvus_connected": checks["milvus"]["ok"],
    }
    return _ok(
        request,
        {
            "checks": summary,
            "dependency_checks": checks,
            "metrics": snapshot_metrics(),
            "ingestion_report": get_last_ingestion_report(),
        },
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dependency_health(request):
    return _ok(request, {"dependencies": run_dependency_checks()})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dependency_health_item(request, dependency_name):
    checks = run_dependency_checks(names=[dependency_name])
    payload = checks.get(dependency_name) or {"ok": False, "error": "UNKNOWN_DEPENDENCY"}
    if payload.get("ok"):
        return _ok(request, {"name": dependency_name, **payload})
    return _err(
        request,
        "DEPENDENCY_UNHEALTHY",
        f"Dependency '{dependency_name}' is unhealthy",
        status.HTTP_503_SERVICE_UNAVAILABLE,
        details={"name": dependency_name, **payload},
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def retriever_debug(request):
    query = str((request.data or {}).get("query", "")).strip()
    k = int((request.data or {}).get("k", 4))
    if not query:
        return _err(request, "QUERY_REQUIRED", "query is required", status.HTTP_400_BAD_REQUEST)

    try:
        vector_store = get_vector_store()
        docs_with_scores = vector_store.similarity_search_with_score(query, k=k)
        results = []
        for doc, score in docs_with_scores:
            results.append(
                {
                    "score": score,
                    "metadata": getattr(doc, "metadata", {}) or {},
                    "snippet": (getattr(doc, "page_content", "") or "")[:300],
                }
            )
        return _ok(request, {"query": query, "k": k, "results": results})
    except Exception as exc:
        return _err(
            request,
            "RETRIEVER_DEBUG_FAILED",
            "Unable to run retriever debug query.",
            status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"exception": str(exc)},
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ingestion_report(request):
    return _ok(request, get_last_ingestion_report())


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_chat_instance(request, chat_instance_id):
    try:
        chat_instance = ChatInstance.objects.get(user=request.user, id=chat_instance_id)
    except ChatInstance.DoesNotExist:
        return _err(request, "INSTANCE_NOT_FOUND", "Instance doesn't exist!", status.HTTP_404_NOT_FOUND)

    chat_instance.is_deleted = True
    chat_instance.save()
    return _ok(request, None, message="Instance deleted successfully!")
