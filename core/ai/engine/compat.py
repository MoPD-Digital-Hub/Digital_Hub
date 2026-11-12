"""Answers in the message format of /ws/chat/ and /api/ai-chat/answer/.

The mobile app and the web chat were built against these endpoints; this keeps
their message shapes while the pipeline in ai.engine produces the answers.
"""

import logging

from ai.engine import followups, titles
from ai.engine.pipeline import answer, answer_stream

LOGGER = logging.getLogger(__name__)

# Clients read `route` (the kind of answer); keep the names they know.
ROUTES = {
    "indicator_series": "get_time_series_context",
    "organization_score": "get_ministry_score_context",
    "organization_kpis": "get_ministry_performance_context",
    "policy_area_score": "get_policy_area_context",
    "goal_detail": "get_goal_context",
    "rank_organizations": "get_ministry_score_context",
    "rank_policy_areas": "get_policy_area_context",
    "sdg_indicator": "get_time_series_context",
    "sdg_goal": "get_time_series_context",
}
GENERAL_ROUTE = "get_general_context"
# Errors arrive as an ordinary final message.
ERROR_HTML = "<p>{message}</p>"


def route_for(tools):
    return ROUTES.get((tools or [None])[0], GENERAL_ROUTE)


def _final(message, route):
    return {"message": message, "is_stream": False, "is_final": True, "route": route}


async def stream_answer(question, *, instance, send, is_native_client, preview):
    """Answer `question`, sending the chat socket's messages through `send`.

    English streams as {"message", "preview", "is_stream": true}; Amharic and
    errors arrive as one final message. After a stream, browsers get the full
    answer again as the final message (the web chat finishes its render with
    it); the mobile app does not, or it shows the answer twice.

    After a chat's first answer the chat is given a title (titles.py). Browsers
    are told with {"event": "chat_title", "chat_instance_id", "title"}; the app
    is sent nothing new and reads the title from the chat list.

    Browsers then get suggested next questions (followups.py) as
    {"event": "followups", "chat_instance_id", "history_id", "questions"}.
    The app is not sent them.
    """
    so_far, streamed, buffer_only, answered, history_id, language = [], False, False, False, None, None
    async for event in answer_stream(question, instance=instance):
        kind = event["type"]
        if kind == "status":
            if event.get("stage") == "writing":
                buffer_only = event.get("language") == "Amharic"
        elif kind == "delta":
            so_far.append(event["text"])
            if not buffer_only:
                streamed = True
                await send({"message": event["text"], "preview": preview("".join(so_far)), "is_stream": True})
        elif kind == "done":
            answered = True
            history_id = event.get("history_id")
            language = event.get("language")
            if not streamed or not is_native_client:
                await send(_final("".join(so_far), route_for(event.get("tools"))))
        elif kind == "error":
            await send(_final(ERROR_HTML.format(message=event["message"]), GENERAL_ROUTE))

    if not answered or instance is None:
        return
    try:
        title = await titles.ensure_title(instance.id, question)
    except Exception:  # a title is a nicety; it must never break the chat
        LOGGER.exception("Chat title failed for chat %s", instance.id)
        title = None
    if title and not is_native_client:
        await send({"event": "chat_title", "chat_instance_id": instance.id, "title": title})

    if is_native_client:
        return
    try:
        questions = await followups.suggest(question, "".join(so_far), language=language)
    except Exception:  # suggestions are a nicety too
        LOGGER.exception("Follow-up suggestions failed for chat %s", instance.id)
        return
    if questions:
        await send({"event": "followups", "chat_instance_id": instance.id, "history_id": history_id,
                    "questions": questions})


def answer_payload(question, *, instance):
    """The REST answer payload. Returns (data, ok)."""
    from asgiref.sync import async_to_sync

    result = async_to_sync(answer)(question, instance=instance)
    if result.get("type") == "error":
        return {"message": result["message"]}, False
    _queue_title(instance, question)
    return {
        "chat_instance_id": instance.id,
        "question": question,
        "answer": result["answer"],
        "route": route_for(result.get("tools")),
        # Kept for clients that read it; tokens are not counted.
        "token_usage": None,
    }, True



def _queue_title(instance, question):
    """Title the chat in the background, so the REST answer does not wait for it."""
    from ai.tasks import generate_chat_title

    try:
        if instance is not None and titles.needs_title(instance.id):
            generate_chat_title.delay(instance.id, question)
    except Exception:  # the queue being down must not fail the answer
        LOGGER.exception("Could not queue the title for chat %s", getattr(instance, "id", None))
