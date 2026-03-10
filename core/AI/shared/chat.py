import re

from AI.domain import MINISTRY_PERFORMANCE_SYSTEM_RULES, MINISTRY_SCORE_SYSTEM_RULES, SYSTEM_RULES

from .constants import AI_RESPONSE_FAILED_HTML, AI_TEMPORARILY_UNAVAILABLE_HTML


def select_system_rule(intent=None):
    if intent == "MINISTRY_SCORE":
        return MINISTRY_SCORE_SYSTEM_RULES
    if intent == "MINISTRY_PERFORMANCE":
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


def run_chain(prompt, llm, conversation_list, context, question):
    if llm is None:
        return None

    messages = [
        {"role": "system", "content": SYSTEM_RULES},
        {"role": "user", "content": f"Context:\n{context}"},
    ]
    messages.extend(normalize_history_for_messages(conversation_list))
    messages.append({"role": "user", "content": question})
    return llm.invoke(messages)


def invoke_chat_once(llm, conversation_list, context, question, intent=None):
    if llm is None:
        raise ValueError("LLM is not initialized")

    messages = [
        {"role": "system", "content": select_system_rule(intent)},
        {"role": "user", "content": f"Context:\n{context}"},
    ]
    messages.extend(normalize_history_for_messages(conversation_list))
    messages.append({"role": "user", "content": question})
    return llm.invoke(messages)


def is_greeting(text: str) -> bool:
    normalized = text.strip().lower()
    return bool(
        re.fullmatch(
            r"(hi|hello|hey|selam|good morning|good afternoon|good evening)[!. ]*",
            normalized,
        )
    )


async def run_chain_stream(llm, conversation_list, context, question, intent=None):
    selected_system_rule = select_system_rule(intent)

    if llm is None:
        yield AI_TEMPORARILY_UNAVAILABLE_HTML
        return

    messages = [
        {"role": "system", "content": selected_system_rule},
        {"role": "user", "content": f"Context:\n{context}"},
    ]
    messages.extend(normalize_history_for_messages(conversation_list))
    messages.append({"role": "user", "content": question})

    try:
        async for chunk in llm.astream(messages):
            if hasattr(chunk, "content"):
                yield chunk.content
            else:
                yield str(chunk)
    except Exception:
        yield AI_RESPONSE_FAILED_HTML
