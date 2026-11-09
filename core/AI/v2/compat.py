"""Serve v2 answers through the v1 endpoints, in the v1 message format.

The mobile app and the web chat keep talking to /ws/chat/ and
/api/ai-chat/answer/ exactly as before; only the engine behind them changes.

Switch with settings (from .env):
    AI_ENGINE=v1|v2           v2 for everyone, or v1 (default) for everyone
    AI_ENGINE_V2_USERS=a@x,…  owners whose chats use v2 while AI_ENGINE=v1 (pilot)

Rolling back is AI_ENGINE=v1 and a Daphne restart; no client release either way.
"""

from django.conf import settings

from AI.v2.pipeline import answer, answer_stream

# v1 reported which tool answered as `route`; keep its names for clients that read it.
V1_ROUTES = {
    "indicator_series": "get_time_series_context",
    "organization_score": "get_ministry_score_context",
    "organization_kpis": "get_ministry_performance_context",
    "policy_area_score": "get_policy_area_context",
    "goal_detail": "get_goal_context",
    "rank_organizations": "get_ministry_score_context",
    "rank_policy_areas": "get_policy_area_context",
}
GENERAL_ROUTE = "get_general_context"
# v1 showed errors as an ordinary final message.
ERROR_HTML = "<p>{message}</p>"


def uses_v2(owner_email=None):
    if getattr(settings, "AI_ENGINE", "v1") == "v2":
        return True
    pilot = {email.strip().lower() for email in getattr(settings, "AI_ENGINE_V2_USERS", []) if email.strip()}
    return bool(owner_email) and owner_email.strip().lower() in pilot


def v1_route(tools):
    return V1_ROUTES.get((tools or [None])[0], GENERAL_ROUTE)


def _final(message, route):
    return {"message": message, "is_stream": False, "is_final": True, "route": route}


async def stream_as_v1(question, *, instance, send, is_native_client, preview):
    """Run v2 and emit what the v1 socket would have sent.

    English streams as {"message", "preview", "is_stream": true}; Amharic and
    errors arrive as one final message, as in v1. After a stream, browsers get
    the full answer again as the final message (the web chat finishes its
    render with it); the mobile app does not, or it shows the answer twice.
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
                await send(_final("".join(so_far), v1_route(event.get("tools"))))
        elif kind == "error":
            await send(_final(ERROR_HTML.format(message=event["message"]), GENERAL_ROUTE))


def answer_as_v1(question, *, instance):
    """The v1 REST answer payload, produced by v2. Returns (data, ok)."""
    from asgiref.sync import async_to_sync

    result = async_to_sync(answer)(question, instance=instance)
    if result.get("type") == "error":
        return {"message": result["message"]}, False
    return {
        "chat_instance_id": instance.id,
        "question": question,
        "answer": result["answer"],
        "route": v1_route(result.get("tools")),
        # v2 does not count tokens.
        "token_usage": None,
    }, True

