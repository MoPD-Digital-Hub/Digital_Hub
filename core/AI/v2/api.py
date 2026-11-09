from asgiref.sync import async_to_sync
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from AI.endpoints.api import _err, _ok
from AI.models import ChatInstance
from AI.v2.pipeline import answer


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def answer_v2(request, chat_instance_id):
    """POST {"question": "..."} -> the whole v2 answer (no streaming)."""
    instance = ChatInstance.objects.filter(id=chat_instance_id, user=request.user, is_deleted=False).first()
    if instance is None:
        return _err(request, "INSTANCE_NOT_FOUND", "Instance doesn't exist!", status.HTTP_404_NOT_FOUND)

    question = str((request.data or {}).get("question", "")).strip()
    if not question:
        return _err(request, "QUESTION_REQUIRED", "question is required", status.HTTP_400_BAD_REQUEST)

    result = async_to_sync(answer)(question, instance=instance)
    if result.get("type") == "error":
        return _err(request, "AI_UNAVAILABLE", result["message"], status.HTTP_503_SERVICE_UNAVAILABLE)
    return _ok(request, {
        "answer": result["answer"],
        "history_id": result.get("history_id"),
        "sources": result.get("sources", []),
        "verified": result.get("verified", True),
    })
