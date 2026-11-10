from celery import shared_task

from ai.models import ChatInstance
from ai.engine import compat


@shared_task(bind=True)
def generate_answer_task(self, chat_instance_id, question, request_id=None):
    """The REST answer, queued (AI_USE_ASYNC_QUEUE or ?mode=async); polled via task-status."""
    try:
        chat_instance = ChatInstance.objects.get(id=chat_instance_id, is_deleted=False)
    except ChatInstance.DoesNotExist:
        return {
            "status": "FAILURE",
            "error": {"code": "INSTANCE_NOT_FOUND", "message": "Instance doesn't exist"},
            "request_id": request_id,
        }

    data, ok = compat.answer_payload(question, instance=chat_instance)
    return {
        "status": "SUCCESS" if ok else "FAILURE",
        "request_id": request_id,
        "data": data if ok else None,
        "error": None if ok else {"code": "AI_UNAVAILABLE", "message": data["message"]},
        "message": "SUCCESS" if ok else "AI_UNAVAILABLE",
        "status_code": 200 if ok else 503,
    }
