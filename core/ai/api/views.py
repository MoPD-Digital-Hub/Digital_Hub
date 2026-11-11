import hashlib
import logging

import requests
from celery.result import AsyncResult
from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from ai.engine import compat
from ai.infrastructure.health import run_dependency_checks
from ai.infrastructure.translation import translate_text_with_gemini
from ai.infrastructure.tts import synthesize_gemini_tts
from ai.models import ChatInstance, QuestionHistory
from ai.tasks import generate_answer_task
from project.celery import app as celery_app
from project.responses import failure, request_id, success

from .serializers import ChatInstanceSerializer, QuestionHistorySerializer

LOGGER = logging.getLogger("ai.api")


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_chat_list(request, chat_instance_id):
    try:
        chat_instance = ChatInstance.objects.get(id=chat_instance_id, user=request.user)
    except ChatInstance.DoesNotExist:
        return failure(request, "INSTANCE_NOT_FOUND", status.HTTP_404_NOT_FOUND, code="INSTANCE_NOT_FOUND", error_message="Instance doesn't exist!")

    histories = QuestionHistory.objects.filter(instance=chat_instance)
    histories_serializer = QuestionHistorySerializer(histories, many=True)
    return success(request, histories_serializer.data)


@api_view(['POST', 'GET'])
@permission_classes([IsAuthenticated])
def chat(request):
    if request.method == 'GET':
        chat_instances = ChatInstance.objects.filter(user=request.user, is_deleted=False)
        serializer = ChatInstanceSerializer(chat_instances, many=True)
        return success(request, serializer.data)

    elif request.method == 'POST':
        title = str((request.data or {}).get("title", "")).strip()
        instance = ChatInstance(user=request.user, title=title or "New Chat")
        instance.save()
        serializer = ChatInstanceSerializer(instance)
        return success(request, serializer.data)

    return failure(request, "INVALID_METHOD", status.HTTP_400_BAD_REQUEST, code="INVALID_METHOD", error_message="Page not found!")


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def update_chat_instance(request, chat_instance_id):
    try:
        chat_instance = ChatInstance.objects.get(user=request.user, id=chat_instance_id, is_deleted=False)
    except ChatInstance.DoesNotExist:
        return failure(request, "INSTANCE_NOT_FOUND", status.HTTP_404_NOT_FOUND, code="INSTANCE_NOT_FOUND", error_message="Instance doesn't exist!")

    title = str((request.data or {}).get("title", "")).strip()
    if not title:
        return failure(request, "TITLE_REQUIRED", status.HTTP_400_BAD_REQUEST, code="TITLE_REQUIRED", error_message="title is required")

    chat_instance.title = title
    chat_instance.save(update_fields=["title"])
    return success(request, ChatInstanceSerializer(chat_instance).data, message="Instance updated successfully!")


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
        return failure(request, "INSTANCE_NOT_FOUND", status.HTTP_404_NOT_FOUND, code="INSTANCE_NOT_FOUND", error_message="Instance doesn't exist!")

    if request.method == 'GET':
        answers = QuestionHistory.objects.filter(instance=chat_instance, response__isnull=False).order_by("created_at")
        serializer = QuestionHistorySerializer(answers, many=True)
        return success(request, serializer.data)

    question = (request.data or {}).get("question", "")
    question = str(question).strip()
    if not question:
        return failure(request, "QUESTION_REQUIRED", status.HTTP_400_BAD_REQUEST, code="QUESTION_REQUIRED", error_message="question is required")

    mode = request.query_params.get("mode", "").lower()
    if settings.AI_USE_ASYNC_QUEUE or mode == "async":
        try:
            task = generate_answer_task.delay(chat_instance.id, question, request_id(request))
            return success(request, {
                    "task_id": task.id,
                    "chat_instance_id": chat_instance.id,
                    "question": question,
                    "status_url": f"/api/ai-chat/task-status/{task.id}/",
                }, message="QUEUED", status=status.HTTP_202_ACCEPTED)
        except Exception as exc:
            return failure(request, "QUEUE_UNAVAILABLE", status.HTTP_503_SERVICE_UNAVAILABLE, code="QUEUE_UNAVAILABLE", error_message="Async queue unavailable; try synchronous mode.", details={"exception": str(exc)})

    data, ok = compat.answer_payload(question, instance=chat_instance)
    if not ok:
        return failure(request, "AI_UNAVAILABLE", status.HTTP_503_SERVICE_UNAVAILABLE, code="AI_UNAVAILABLE", error_message=data["message"])
    return success(request, data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def tts(request):
    text = str((request.data or {}).get("text", "")).strip()
    voice = str((request.data or {}).get("voice", "")).strip() or None
    language = str((request.data or {}).get("language", "English")).strip() or "English"
    if not text:
        return failure(request, "TEXT_REQUIRED", status.HTTP_400_BAD_REQUEST, code="TEXT_REQUIRED", error_message="text is required")

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
        return failure(request, "TEXT_REQUIRED", status.HTTP_400_BAD_REQUEST, code="TEXT_REQUIRED", error_message=str(exc))
    except requests.HTTPError as exc:
        details = {}
        if exc.response is not None:
            try:
                details = exc.response.json()
            except ValueError:
                details = {"response_text": exc.response.text[:500]}
        LOGGER.exception("Gemini TTS provider failure", extra={"details": details})
        return failure(request, "TTS_PROVIDER_FAILURE", status.HTTP_502_BAD_GATEWAY, code="TTS_PROVIDER_FAILURE", error_message=details.get("error", {}).get("message") or "Gemini TTS request failed.", details=details)
    except Exception as exc:
        return failure(request, "TTS_UNAVAILABLE", status.HTTP_503_SERVICE_UNAVAILABLE, code="TTS_UNAVAILABLE", error_message=str(exc))

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
        return failure(request, "TEXT_REQUIRED", status.HTTP_400_BAD_REQUEST, code="TEXT_REQUIRED", error_message="text is required")

    cache_key = "ai_tts:{digest}".format(
        digest=hashlib.sha256(
            "{voice}:{language}:{text}".format(voice=voice or "", language=language, text=text).encode("utf-8")
        ).hexdigest()
    )
    if cache.get(cache_key):
        return success(request, {"cached": True}, message="TTS_CACHE_HIT")

    try:
        audio_bytes, mime_type = synthesize_gemini_tts(text, voice_name=voice, language_hint=language)
    except ValueError as exc:
        return failure(request, "TEXT_REQUIRED", status.HTTP_400_BAD_REQUEST, code="TEXT_REQUIRED", error_message=str(exc))
    except requests.HTTPError as exc:
        details = {}
        if exc.response is not None:
            try:
                details = exc.response.json()
            except ValueError:
                details = {"response_text": exc.response.text[:500]}
        LOGGER.exception("Gemini TTS prefetch provider failure", extra={"details": details})
        return failure(request, "TTS_PROVIDER_FAILURE", status.HTTP_502_BAD_GATEWAY, code="TTS_PROVIDER_FAILURE", error_message=details.get("error", {}).get("message") or "Gemini TTS request failed.", details=details)
    except Exception as exc:
        return failure(request, "TTS_UNAVAILABLE", status.HTTP_503_SERVICE_UNAVAILABLE, code="TTS_UNAVAILABLE", error_message=str(exc))

    cache.set(
        cache_key,
        (audio_bytes, mime_type),
        timeout=int(getattr(settings, "AI_TTS_CACHE_TIMEOUT", 3600)),
    )
    return success(request, {"cached": False}, message="TTS_WARMED")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def translate(request):
    text = str((request.data or {}).get("text", "")).strip()
    target_language = str((request.data or {}).get("target_language", "Amharic")).strip() or "Amharic"
    if not text:
        return failure(request, "TEXT_REQUIRED", status.HTTP_400_BAD_REQUEST, code="TEXT_REQUIRED", error_message="text is required")

    cache_key = "ai_translate:{lang}:{digest}".format(
        lang=target_language.lower(),
        digest=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )
    cached_translation = cache.get(cache_key)
    if cached_translation:
        return success(request, {
                "translation": cached_translation,
                "target_language": target_language,
            }, message="TRANSLATION_CACHE_HIT")

    try:
        translated_text = translate_text_with_gemini(text, target_language=target_language)
    except ValueError as exc:
        return failure(request, "TEXT_REQUIRED", status.HTTP_400_BAD_REQUEST, code="TEXT_REQUIRED", error_message=str(exc))
    except requests.HTTPError as exc:
        details = {}
        if exc.response is not None:
            try:
                details = exc.response.json()
            except ValueError:
                details = {"response_text": exc.response.text[:500]}
        return failure(request, "TRANSLATION_PROVIDER_FAILURE", status.HTTP_502_BAD_GATEWAY, code="TRANSLATION_PROVIDER_FAILURE", error_message="Gemini translation request failed.", details=details)
    except Exception as exc:
        return failure(request, "TRANSLATION_UNAVAILABLE", status.HTTP_503_SERVICE_UNAVAILABLE, code="TRANSLATION_UNAVAILABLE", error_message=str(exc))

    cache.set(
        cache_key,
        translated_text,
        timeout=int(getattr(settings, "AI_TRANSLATION_CACHE_TIMEOUT", 3600)),
    )

    return success(request, {
            "translation": translated_text,
            "target_language": target_language,
        }, message="TRANSLATED")


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def task_status(request, task_id):
    task = AsyncResult(task_id, app=celery_app)
    payload = {"task_id": task_id, "state": task.state}
    if task.successful():
        payload["result"] = task.result
    elif task.failed():
        payload["error"] = str(task.result)
    return success(request, payload)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def health(request):
    checks = run_dependency_checks(names=["llm", "embeddings"])
    summary = {
        "llm_configured": checks["llm"]["ok"],
        "embeddings_configured": checks["embeddings"]["ok"],
    }
    return success(request, {"checks": summary, "dependency_checks": checks})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dependency_health(request):
    return success(request, {"dependencies": run_dependency_checks()})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dependency_health_item(request, dependency_name):
    checks = run_dependency_checks(names=[dependency_name])
    payload = checks.get(dependency_name) or {"ok": False, "error": "UNKNOWN_DEPENDENCY"}
    if payload.get("ok"):
        return success(request, {"name": dependency_name, **payload})
    return failure(request, "DEPENDENCY_UNHEALTHY", status.HTTP_503_SERVICE_UNAVAILABLE, code="DEPENDENCY_UNHEALTHY", error_message=f"Dependency '{dependency_name}' is unhealthy", details={"name": dependency_name, **payload})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_chat_instance(request, chat_instance_id):
    try:
        chat_instance = ChatInstance.objects.get(user=request.user, id=chat_instance_id)
    except ChatInstance.DoesNotExist:
        return failure(request, "INSTANCE_NOT_FOUND", status.HTTP_404_NOT_FOUND, code="INSTANCE_NOT_FOUND", error_message="Instance doesn't exist!")

    chat_instance.is_deleted = True
    chat_instance.save()
    return success(request, None, message="Instance deleted successfully!")
