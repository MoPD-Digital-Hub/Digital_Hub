"""Answers in the message format of /ws/chat/ and /api/ai-chat/answer/.

The mobile app and the web chat were built against these endpoints; this keeps
their message shapes while the pipeline in ai.engine produces the answers.
"""

from ai.engine.pipeline import answer, answer_stream

# Clients read `route` (the kind of answer); keep the names they know.
ROUTES = {
    "indicator_series": "get_time_series_context",
    "organization_score": "get_ministry_score_context",
    "organization_kpis": "get_ministry_performance_context",
    "policy_area_score": "get_policy_area_context",
    "goal_detail": "get_goal_context",
    "rank_organizations": "get_ministry_score_context",
    "rank_policy_areas": "get_policy_area_context",
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
    """
    so_far, streamed, buffer_only = [], False, False
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
            if not streamed or not is_native_client:
                await send(_final("".join(so_far), route_for(event.get("tools"))))
        elif kind == "error":
            await send(_final(ERROR_HTML.format(message=event["message"]), GENERAL_ROUTE))


def answer_payload(question, *, instance):
    """The REST answer payload. Returns (data, ok)."""
    from asgiref.sync import async_to_sync

    result = async_to_sync(answer)(question, instance=instance)
    if result.get("type") == "error":
        return {"message": result["message"]}, False
    return {
        "chat_instance_id": instance.id,
        "question": question,
        "answer": result["answer"],
        "route": route_for(result.get("tools")),
        # Kept for clients that read it; tokens are not counted.
        "token_usage": None,
    }, True

