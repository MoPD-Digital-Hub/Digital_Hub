from dataclasses import dataclass
import logging

from langchain_core.messages import AIMessage, HumanMessage

from AI.platform.exceptions import (
    AIServiceError,
    ERROR_BAD_PROMPT_OUTPUT,
    ERROR_LLM_TIMEOUT,
    ERROR_PROVIDER_DOWN,
    ERROR_UPSTREAM_FAILURE,
    ERROR_RETRIEVAL_EMPTY,
)
from AI.domain import INTENTS
from AI.models import QuestionHistory
from AI.platform.observability import increment, timed
from AI.infrastructure import get_llm_instance
from AI.selectors import build_context_for_intent, resolve_intent
from AI.shared import AI_RESPONSE_FAILED_HTML, AI_TEMPORARILY_UNAVAILABLE_HTML, invoke_chat_once, is_greeting
from AI.infrastructure import get_retriever

LOGGER = logging.getLogger("AI.services")


@dataclass
class AnswerResult:
    answer: str
    intent: str
    status_code: int
    message: str
    error: dict | None = None
    token_usage: dict | None = None


def get_chat_history(instance, max_turns=3):
    history = QuestionHistory.objects.filter(instance=instance, response__isnull=False).order_by("created_at")
    conversation = []
    for record in history[:max_turns]:
        conversation.append(HumanMessage(content=record.question))
        conversation.append(AIMessage(content=record.response))
    return conversation


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
            intent=INTENTS["UNKNOWN"],
            status_code=200,
            message="SUCCESS",
        )

    llm = get_llm_instance()
    if llm is None:
        record.response = AI_TEMPORARILY_UNAVAILABLE_HTML
        record.save(update_fields=["response"])
        increment("llm_provider_down")
        request_timer()
        return AnswerResult(
            answer=AI_TEMPORARILY_UNAVAILABLE_HTML,
            intent=INTENTS["UNKNOWN"],
            status_code=503,
            message="AI_SERVICE_UNAVAILABLE",
            error=AIServiceError(
                code=ERROR_PROVIDER_DOWN,
                message="LLM provider is unavailable.",
                dependency="vllm",
            ).to_dict(),
        )

    try:
        docs = _retrieve_docs(question)
    except AIServiceError as exc:
        request_timer()
        record.response = AI_RESPONSE_FAILED_HTML
        record.save(update_fields=["response"])
        return AnswerResult(
            answer=AI_RESPONSE_FAILED_HTML,
            intent=INTENTS["UNKNOWN"],
            status_code=503,
            message=exc.code,
            error=exc.to_dict(),
        )

    if not docs:
        answer_text = "No relevant indicator found in the knowledge base for this query."
        record.response = answer_text
        record.save(update_fields=["response"])
        request_timer()
        return AnswerResult(
            answer=answer_text,
            intent=INTENTS["UNKNOWN"],
            status_code=404,
            message="RETRIEVAL_EMPTY",
            error=AIServiceError(
                code=ERROR_RETRIEVAL_EMPTY,
                message="Retriever returned no matching documents.",
                dependency="milvus",
            ).to_dict(),
        )

    intent = resolve_intent(llm, question, docs)
    if intent == INTENTS["UNKNOWN"]:
        increment("bad_prompt_output")
        record.response = AI_RESPONSE_FAILED_HTML
        record.save(update_fields=["response"])
        request_timer()
        return AnswerResult(
            answer=AI_RESPONSE_FAILED_HTML,
            intent=intent,
            status_code=422,
            message="BAD_PROMPT_OUTPUT",
            error=AIServiceError(
                code=ERROR_BAD_PROMPT_OUTPUT,
                message="Classifier returned UNKNOWN for non-empty retrieval context.",
            ).to_dict(),
        )

    context = build_context_for_intent(intent, llm, question, docs)
    history = get_chat_history(chat_instance)

    try:
        llm_timer = timed("llm_invoke_latency_ms")
        ai_response = invoke_chat_once(llm, history, context, question, intent)
        llm_timer()
        increment("llm_success")
        answer_text = getattr(ai_response, "content", str(ai_response))
        metadata = getattr(ai_response, "response_metadata", {}) or {}
        token_usage = metadata.get("token_usage") or metadata.get("usage")
        if token_usage:
            increment("token_usage_reports")
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
            intent=intent,
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
        intent=intent,
        status_code=200,
        message="SUCCESS",
        token_usage=token_usage if "token_usage" in locals() else None,
    )
