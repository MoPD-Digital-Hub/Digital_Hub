"""Chat titles made from the chat's first question.

A chat starts as "New Chat". After its first answer it gets a short title naming
the topic ("GDP growth trend", "የዋጋ ግሽበት መረጃ"), written by the gateway model in
the question's language, or the question's first words if the model is
unavailable. A title the user set is never replaced.
"""

import re

from asgiref.sync import sync_to_async

from ai.engine import llm, verify
from ai.engine.planner import detect_request_language
from ai.models import ChatInstance, QuestionHistory

# Titles clients create a chat with before anything is asked.
DEFAULT_TITLES = {"", "new chat", "new conversation", "untitled", "chat"}
MAX_CHARS = 60
FALLBACK_WORDS = 6

PROMPT = """Write a title of 2 to 6 words for a chat that starts with the user's question below.
Name the subject (the indicator, ministry, policy area, goal or topic), not the form of the question:
"What was GDP growth in 2017?" -> GDP growth in 2017; "How did the Ministry of Health perform?" -> Ministry of Health performance.
No quotation marks, no final punctuation. Write the title in {language}."""

SCHEMA = {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]}


def is_default(title):
    return str(title or "").strip().lower() in DEFAULT_TITLES


def _clean(text):
    text = re.sub(r"<[^>]+>", " ", str(text or ""))
    text = re.sub(r"\s+", " ", text).strip().strip("\"'“”‘’«»").rstrip(".?!:;,።፧").strip()
    if len(text) > MAX_CHARS:
        text = text[: MAX_CHARS - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return text


def fallback(question):
    """The question's first words."""
    words = _clean(question).split()
    title = " ".join(words[:FALLBACK_WORDS])
    return _clean(title + ("…" if len(words) > FALLBACK_WORDS else "")) or "New Chat"


async def suggest(question):
    language = detect_request_language(question)
    messages = [
        {"role": "system", "content": PROMPT.format(language=language)},
        {"role": "user", "content": str(question or "")[:500]},
    ]
    try:
        raw = await llm.json_completion(messages, SCHEMA, name="chat_title", max_tokens=40)
    except llm.LLMError:
        return fallback(question)
    title = _clean(raw.get("title"))
    # The model occasionally corrupts Amharic with other scripts; the question's words are safer then.
    if not title or verify.foreign_script(title):
        return fallback(question)
    return title


def needs_title(instance_id):
    """True right after a chat's first answer, while it still has its default title."""
    instance = ChatInstance.objects.filter(id=instance_id, is_deleted=False).only("title").first()
    return bool(instance and is_default(instance.title)
                and QuestionHistory.objects.filter(instance_id=instance_id).count() == 1)


def save_title(instance_id, title):
    """Set the title unless someone renamed the chat meanwhile. Returns True when saved.

    update() rather than save(): created_at is auto_now and orders the chat list,
    so save() would move the chat.
    """
    instance = ChatInstance.objects.filter(id=instance_id, is_deleted=False).only("title").first()
    if not instance or not is_default(instance.title):
        return False
    return ChatInstance.objects.filter(id=instance_id, title=instance.title).update(title=title) == 1


async def ensure_title(instance_id, question):
    """Title the chat if this was its first answer. Returns the new title, or None."""
    if not instance_id or not await sync_to_async(needs_title)(instance_id):
        return None
    title = await suggest(question)
    return title if await sync_to_async(save_title)(instance_id, title) else None
