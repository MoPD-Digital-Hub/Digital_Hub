import re

from AI.prompts import MINISTRY_PERFORMANCE_SYSTEM_RULES, MINISTRY_SCORE_SYSTEM_RULES, SYSTEM_RULES
from AI.infrastructure import get_streaming_client, get_streaming_client_config

from .constants import AI_RESPONSE_FAILED_HTML, AI_TEMPORARILY_UNAVAILABLE_HTML


def select_system_rule(route=None):
    if route == "get_ministry_score_context":
        return MINISTRY_SCORE_SYSTEM_RULES
    if route == "get_ministry_performance_context":
        return MINISTRY_PERFORMANCE_SYSTEM_RULES
    return SYSTEM_RULES


def normalize_history_for_messages(conversation_list):
    messages = []
    for m in conversation_list:
        role = m.get("role") if isinstance(m, dict) else getattr(m, "type", "user")
        content = m.get("content") if isinstance(m, dict) else getattr(m, "content", "")
        if role not in {"system", "user", "assistant"}:
            role = "user"
        if not str(content).strip():
            continue
        messages.append({"role": role, "content": content})
    return messages


def build_chat_messages(conversation_list, context, question, route=None):
    messages = [{"role": "system", "content": select_system_rule(route)}]
    if str(context or "").strip():
        messages.append({"role": "user", "content": f"Context:\n{context}"})
    messages.extend(normalize_history_for_messages(conversation_list))
    messages.append({"role": "user", "content": question})
    return messages


def run_chain(prompt, llm, conversation_list, context, question):
    if llm is None:
        return None

    messages = build_chat_messages(conversation_list, context, question)
    return llm.invoke(messages)


def invoke_chat_once(llm, conversation_list, context, question, route=None):
    if llm is None:
        raise ValueError("LLM is not initialized")

    return llm.invoke(build_chat_messages(conversation_list, context, question, route))


def is_greeting(text: str) -> bool:
    normalized = text.strip().lower()
    return bool(
        re.fullmatch(
            r"(hi|hello|hey|selam|good morning|good afternoon|good evening)[!. ]*",
            normalized,
        )
    )


async def run_chain_stream(llm, conversation_list, context, question, route=None):
    messages = build_chat_messages(conversation_list, context, question, route)

    try:
        streaming_client = get_streaming_client()
        if streaming_client is not None:
            config = get_streaming_client_config()
            stream = await streaming_client.chat.completions.create(
                model=config["model"],
                messages=messages,
                temperature=0,
                stream=True,
            )
            async for chunk in stream:
                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    continue
                delta = getattr(choices[0], "delta", None)
                content = getattr(delta, "content", None) if delta is not None else None

                if isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict):
                            text = part.get("text") or ""
                        else:
                            text = getattr(part, "text", "") or ""
                        if text:
                            yield text
                elif content:
                    yield content
            return

        if llm is None:
            yield AI_TEMPORARILY_UNAVAILABLE_HTML
            return

        async for chunk in llm.astream(messages):
            if hasattr(chunk, "content"):
                yield chunk.content
            else:
                yield str(chunk)
    except Exception:
        if llm is None:
            yield AI_RESPONSE_FAILED_HTML
            return

        try:
            async for chunk in llm.astream(messages):
                if hasattr(chunk, "content"):
                    yield chunk.content
                else:
                    yield str(chunk)
        except Exception:
            yield AI_RESPONSE_FAILED_HTML
