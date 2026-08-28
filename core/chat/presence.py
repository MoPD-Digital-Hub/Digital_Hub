"""Tracks which conversation a user is currently viewing ("focus").

The chat websocket writes a short-lived Redis key while a user has a chat
page open; the push task checks it to skip FCM for messages the user is
already looking at. Every failure path degrades to "not focused" so the
worst case is a redundant push, never a missed one.
"""

import logging

from django.conf import settings

try:
    import redis
except ImportError:  # pragma: no cover
    redis = None

LOGGER = logging.getLogger("chat.presence")

# Must be refreshed by client heartbeats (~25s) while a chat page stays open.
FOCUS_TTL_SECONDS = getattr(settings, "CHAT_FOCUS_TTL_SECONDS", 60)

_client = None


def _get_client():
    global _client
    if redis is None:
        return None
    if _client is None:
        _client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=getattr(settings, "CHAT_PRESENCE_REDIS_DB", 2),
            socket_timeout=2,
            socket_connect_timeout=2,
            decode_responses=True,
        )
    return _client


def _key(user_id):
    return f"chat:focus:{user_id}"


def set_focus(user_id, conversation_id):
    client = _get_client()
    if client is None:
        return
    try:
        client.setex(_key(user_id), FOCUS_TTL_SECONDS, str(conversation_id))
    except Exception:
        LOGGER.warning("Failed to set chat focus for user %s", user_id, exc_info=True)


def refresh_focus(user_id, conversation_id):
    set_focus(user_id, conversation_id)


def clear_focus(user_id, conversation_id=None):
    """Clear the focus key. When conversation_id is given, only clear if it
    still points at that conversation (avoids clobbering another device)."""
    client = _get_client()
    if client is None:
        return
    try:
        if conversation_id is None:
            client.delete(_key(user_id))
        elif client.get(_key(user_id)) == str(conversation_id):
            client.delete(_key(user_id))
    except Exception:
        LOGGER.warning("Failed to clear chat focus for user %s", user_id, exc_info=True)


def is_focused(user_id, conversation_id):
    client = _get_client()
    if client is None:
        return False
    try:
        return client.get(_key(user_id)) == str(conversation_id)
    except Exception:
        LOGGER.warning("Failed to read chat focus for user %s", user_id, exc_info=True)
        return False
