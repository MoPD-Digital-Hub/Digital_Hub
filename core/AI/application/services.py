from dataclasses import dataclass
import logging
import re

from langchain_core.messages import AIMessage, HumanMessage

from AI.runtime.exceptions import (
    AIServiceError,
    ERROR_LLM_TIMEOUT,
    ERROR_PROVIDER_DOWN,
    ERROR_UPSTREAM_FAILURE,
    ERROR_RETRIEVAL_EMPTY,
)
from AI.models import QuestionHistory
from AI.runtime.observability import increment, timed
from AI.infrastructure import get_llm_instance
from AI.infrastructure.translation import (
    normalize_question_for_retrieval,
    translate_text_with_gemini,
)
from AI.mcp_tools import execute_mcp_tool_plan, resolve_mcp_tool_plan
from AI.shared import (
    AI_RESPONSE_FAILED_HTML,
    AI_TEMPORARILY_UNAVAILABLE_HTML,
    invoke_chat_once,
    is_greeting,
)
from AI.infrastructure import get_retriever

LOGGER = logging.getLogger("AI.application")
FOLLOW_UP_TERMS = {
    "more",
    "more indicators",
    "more kpis",
    "continue",
    "next",
    "show more",
    "others",
    "other indicators",
    "more of them",
    "what about more",
    "add more",
}


@dataclass
class AnswerResult:
    answer: str
    route: str
    status_code: int
    message: str
    error: dict | None = None
    token_usage: dict | None = None


@dataclass
class PreparedAnswer:
    docs: list
    route: str
    context: str
    response_language: str
    normalized_question: str


def get_chat_history(instance, max_turns=3):
    history = (
        QuestionHistory.objects.filter(instance=instance, response__isnull=False)
        .order_by("-created_at")[:max_turns]
    )
    conversation = []
    for record in reversed(list(history)):
        conversation.append(HumanMessage(content=record.question))
        conversation.append(AIMessage(content=record.response))
    return conversation


def get_history_records(instance, max_turns=3):
    history = (
        QuestionHistory.objects.filter(instance=instance, response__isnull=False)
        .order_by("-created_at")[:max_turns]
        .values("question", "response")
    )
    return list(reversed(list(history)))


def _retrieve_docs(question):
    try:
        retriever = get_retriever()
        done = timed("retriever_latency_ms")
        docs = retriever.invoke(question) if retriever else []
        done()
        increment("retriever_calls")
        if docs:
            increment("retriever_hits")
        else:
            increment("retriever_misses")
        return docs
    except Exception as exc:
        increment("retriever_failures")
        raise AIServiceError(
            code=ERROR_UPSTREAM_FAILURE,
            message=f"Retriever failed: {exc}",
            dependency="milvus",
        )


def retrieve_docs(question):
    return _retrieve_docs(question)


def _strip_html(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", str(text or ""))
    return re.sub(r"\s+", " ", cleaned).strip()


def _is_follow_up_question(question: str) -> bool:
    normalized = re.sub(r"\s+", " ", str(question or "").strip().lower())
    if not normalized:
        return False
    if normalized in FOLLOW_UP_TERMS:
        return True
    token_count = len(re.findall(r"[a-z0-9]+", normalized))
    return token_count <= 5 and any(term in normalized for term in FOLLOW_UP_TERMS)


def build_retrieval_query(question: str, history_records=None) -> str:
    if not _is_follow_up_question(question):
        return question

    records = history_records or []
    if not records:
        return question

    last_turn = records[-1]
    previous_question = str(last_turn.get("question") or "").strip()
    previous_response = _strip_html(last_turn.get("response") or "")[:600]
    if not previous_question:
        return question

    return (
        f"Previous user request: {previous_question}\n"
        f"Previous assistant answer: {previous_response}\n"
        f"Follow-up request: {question}"
    )


def prepare_answer(question: str, llm, history_records=None) -> PreparedAnswer:
    retrieval_query = build_retrieval_query(question, history_records)
    normalized_question, response_language = normalize_question_for_retrieval(question)
    normalized_retrieval_query = (
        normalized_question
        if retrieval_query == question
        else normalize_question_for_retrieval(retrieval_query)[0]
    )

    docs = _retrieve_docs(normalized_retrieval_query)
    if not docs and normalized_retrieval_query != normalized_question:
        docs = _retrieve_docs(normalized_question)
    if not docs:
        raise AIServiceError(
            code=ERROR_RETRIEVAL_EMPTY,
            message="Retriever returned no matching documents.",
            dependency="milvus",
        )

    plan = resolve_mcp_tool_plan(llm, normalized_question, docs)
    return PreparedAnswer(
        docs=docs,
        route=plan.tool_name,
        context=execute_mcp_tool_plan(plan, llm, normalized_question, docs),
        response_language=response_language,
        normalized_question=normalized_question,
    )


def format_history_records_for_llm(history_records, max_turns=3):
    messages = []
    records = (history_records or [])[-max_turns:]
    for entry in records:
        question = entry.get("question")
        response = entry.get("response")
        if question:
            messages.append({"role": "user", "content": question})
        if response:
            messages.append({"role": "assistant", "content": response})
    return messages


def generate_answer(chat_instance, question: str) -> AnswerResult:
    request_timer = timed("answer_request_latency_ms")
    question = (question or "").strip()
    record = QuestionHistory.objects.create(instance=chat_instance, question=question)

    if is_greeting(question):
        answer_text = "Hello, I'm MoPD Chat Bot. How can I assist you?"
        record.response = answer_text
        record.save(update_fields=["response"])
        request_timer()
        return AnswerResult(
            answer=answer_text,
            route="get_general_context",
            status_code=200,
            message="SUCCESS",
        )

    history_records = get_history_records(chat_instance)
    llm = get_llm_instance()
    if llm is None:
        record.response = AI_TEMPORARILY_UNAVAILABLE_HTML
        record.save(update_fields=["response"])
        increment("llm_provider_down")
        request_timer()
        return AnswerResult(
            answer=AI_TEMPORARILY_UNAVAILABLE_HTML,
            route="get_general_context",
            status_code=503,
            message="AI_SERVICE_UNAVAILABLE",
            error=AIServiceError(
                code=ERROR_PROVIDER_DOWN,
                message="LLM provider is unavailable.",
                dependency="vllm",
            ).to_dict(),
        )

    try:
        prepared = prepare_answer(question, llm, history_records=history_records)
    except AIServiceError as exc:
        request_timer()
        answer_text = (
            "No relevant indicator found in the knowledge base for this query."
            if exc.code == ERROR_RETRIEVAL_EMPTY
            else AI_RESPONSE_FAILED_HTML
        )
        status_code = 404 if exc.code == ERROR_RETRIEVAL_EMPTY else 503
        route = "get_general_context"
        record.response = answer_text
        record.save(update_fields=["response"])
        return AnswerResult(
            answer=answer_text,
            route=route,
            status_code=status_code,
            message=exc.code,
            error=exc.to_dict(),
        )
    route = prepared.route
    context = prepared.context
    history = [] if prepared.response_language == "Amharic" else get_chat_history(chat_instance)

    try:
        llm_timer = timed("llm_invoke_latency_ms")
        ai_response = invoke_chat_once(llm, history, context, prepared.normalized_question, route)
        answer_text = getattr(ai_response, "content", str(ai_response))
        if prepared.response_language == "Amharic":
            answer_text = translate_text_with_gemini(answer_text, "Amharic")
        metadata = getattr(ai_response, "response_metadata", {}) or {}
        token_usage = metadata.get("token_usage") or metadata.get("usage")
        if token_usage:
            increment("token_usage_reports")
        llm_timer()
        increment("llm_success")
    except Exception as exc:
        increment("llm_failures")
        message = str(exc).lower()
        code = ERROR_LLM_TIMEOUT if "timeout" in message else "LLM_FAILURE"
        LOGGER.exception("LLM invocation failed: %s", str(exc))
        request_timer()
        answer_text = AI_RESPONSE_FAILED_HTML
        record.response = answer_text
        record.save(update_fields=["response"])
        return AnswerResult(
            answer=answer_text,
            route=route,
            status_code=503,
            message=code,
            error=AIServiceError(
                code=code,
                message="LLM invocation failed.",
                dependency="vllm",
            ).to_dict(),
        )

    record.response = answer_text
    record.save(update_fields=["response"])
    request_timer()
    return AnswerResult(
        answer=answer_text,
        route=route,
        status_code=200,
        message="SUCCESS",
        token_usage=token_usage if "token_usage" in locals() else None,
    )
