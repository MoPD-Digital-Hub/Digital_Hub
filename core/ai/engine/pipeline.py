"""The one answer pipeline, shared by the WebSocket, REST and evaluation.

Events (dicts), in order:
    {"type": "status", "stage": "planning" | "fetching" | "writing"}   (writing also carries "language")
    {"type": "delta", "text": "..."}          zero or more; the answer is their concatenation
    {"type": "done", "history_id", "sources", "tools", "verified"}   or   {"type": "error", "message"}

`done` deliberately does not repeat the answer: clients already have it from
the deltas (repeating it made the mobile app show answers twice).
"""

import asyncio
import logging
import time

from asgiref.sync import sync_to_async
from django.conf import settings
from django.utils import timezone

from ai.engine import catalog, compose, planner, render, verify
from ai.engine.llm import LLMError
from ai.engine.tools import TOOLS, ToolError
from ai.models import AnswerTrace, CatalogEntity, QuestionHistory
from integrations.websearch import client as websearch

LOGGER = logging.getLogger(__name__)
# Below this blended similarity a match is more likely wrong than right.
MIN_MATCH_SCORE = 0.45
OPTIONAL_ENTITY_KINDS = {"organization": CatalogEntity.ORGANIZATION}
AMHARIC_ATTEMPT_TEMPERATURES = (0, 0.4)
# How much of each earlier answer the writer sees (the planner sees 300 characters).
WRITER_ANSWER_CHARS = 700
# Web answers: results considered, pages read in full, and text kept per page.
WEB_RESULTS = 6
WEB_PAGES_READ = 3
WEB_PAGE_CHARS = 3500


async def _resolve_call(call):
    """Tool arguments with entity names replaced by catalog matches."""
    tool = TOOLS[call["tool"]]
    args = {k: v for k, v in call.items() if k != "tool" and k not in planner.ENTITY_ARGS}
    resolved = []
    wanted = list(tool.entities.items()) + [
        (arg, OPTIONAL_ENTITY_KINDS[arg]) for arg in tool.optional_entities if call.get(arg)
    ]
    for arg, kind in wanted:
        text = call[arg]
        matches = await catalog.resolve(text, kind)
        if not matches or matches[0].score < MIN_MATCH_SCORE:
            return None, f'No {kind.replace("_", " ")} matching "{text}" was found.', resolved
        args[arg] = matches[0]
        resolved.append({"tool": tool.name, "arg": arg, "text": text, "match": matches[0].as_dict(),
                         "alternatives": [m.as_dict() for m in matches[1:]]})
    return args, None, resolved


async def _run_call(call):
    """(result or None, problem or None, resolved entities, trace entry)."""
    started = time.monotonic()
    entry = {"tool": call["tool"], "call": call}
    try:
        args, problem, resolved = await _resolve_call(call)
        if problem:
            entry.update(ok=False, error=problem)
            return None, problem, resolved, entry
        result = await asyncio.to_thread(TOOLS[call["tool"]].run, **args)
        entry.update(ok=True)
        return result, None, resolved, entry
    except (ToolError, LLMError) as exc:
        entry.update(ok=False, error=str(exc))
        return None, str(exc), [], entry
    except Exception as exc:  # a bug in one tool must not sink the whole answer
        LOGGER.exception("AI tool %s failed", call["tool"])
        entry.update(ok=False, error=f"{type(exc).__name__}: {exc}")
        return None, "One of the data lookups failed unexpectedly.", [], entry
    finally:
        entry["ms"] = int((time.monotonic() - started) * 1000)


@sync_to_async
def _history(instance):
    if instance is None:
        return []
    rows = QuestionHistory.objects.filter(instance=instance, response__isnull=False).order_by("-created_at")
    return list(rows.values("question", "response")[: planner.HISTORY_TURNS])[::-1]


@sync_to_async
def _save(instance, question, answer, trace):
    history = QuestionHistory.objects.create(instance=instance, question=question[:500], response=answer)
    AnswerTrace.objects.create(instance=instance, question=question, answer=answer, **trace)
    return history.id


@sync_to_async
def _web_quota_left(instance):
    """False when the chat's owner has used today's web searches (WEB_SEARCH_DAILY_LIMIT)."""
    limit = settings.WEB_SEARCH_DAILY_LIMIT
    if not limit or instance is None or not instance.user_id:
        return True
    used = AnswerTrace.objects.filter(instance__user_id=instance.user_id, created_at__date=timezone.localdate(),
                                      plan__kind="web").count()
    return used < limit


async def _web_research(plan, instance):
    """Search the web for a "web" question and read the best pages.

    Returns (pages, trace entry, problem). Each page: {"title", "url", "site",
    "published", "snippet", "text"}; the first WEB_PAGES_READ are read in full,
    the rest keep their search snippet.
    """
    entry = {"tool": "web_search", "query": plan.search_query, "urls": [], "error": ""}
    if not await _web_quota_left(instance):
        entry["error"] = "daily limit"
        return [], entry, "today's web search limit has been reached"
    try:
        found = await asyncio.to_thread(websearch.search, plan.search_query, WEB_RESULTS)
    except websearch.WebSearchError as exc:
        LOGGER.warning("Web search failed: %s", exc)
        entry["error"] = str(exc)[:300]
        return [], entry, "web search is unavailable right now"
    texts = await asyncio.gather(*(asyncio.to_thread(websearch.read_page, r["url"], WEB_PAGE_CHARS)
                                   for r in found[:WEB_PAGES_READ]))
    pages = [dict(result, text=(texts[i] if i < len(texts) else "") or result["snippet"])
             for i, result in enumerate(found)]
    pages = [page for page in pages if page["text"]]
    entry["urls"] = [page["url"] for page in pages]
    if not pages:
        return [], entry, f'the web search for "{plan.search_query}" found nothing usable'
    return pages, entry, ""


async def answer_stream(question, *, instance=None):
    question = str(question or "").strip()
    started = time.monotonic()
    trace = {"language": "", "plan": {}, "resolved": [], "tool_calls": [], "unsupported_numbers": [], "error": ""}
    pieces = []
    try:
        yield {"type": "status", "stage": "planning"}
        history = await _history(instance)
        plan = await planner.plan(question, history)
        # The writer sees the recent turns too, so it can refer back; figures it
        # quotes from them count as supported by the number check below.
        context = planner.conversation(history, answer_chars=WRITER_ANSWER_CHARS)
        trace["language"], trace["plan"] = plan.language, plan.as_dict()

        results, problems = [], []
        if plan.kind == "web":
            yield {"type": "status", "stage": "searching"}
            results, entry, problem = await _web_research(plan, instance)
            trace["tool_calls"].append(entry)
            if problem:
                problems.append(problem)
        if plan.calls:
            yield {"type": "status", "stage": "fetching"}
            for result, problem, resolved, entry in await asyncio.gather(*(_run_call(c) for c in plan.calls)):
                trace["resolved"] += resolved
                trace["tool_calls"].append(entry)
                if result:
                    results.append(result)
                if problem:
                    problems.append(problem)

        yield {"type": "status", "stage": "writing", "language": plan.language}
        if plan.language == "Amharic":
            # Written in full and checked before sending: the model sometimes
            # corrupts Amharic words with other scripts, and a streamed word
            # cannot be taken back. Greedy decoding would repeat the same
            # corruption, so the retry samples a little.
            for temperature in AMHARIC_ATTEMPT_TEMPERATURES:
                narrative = "".join([p async for p in compose.stream(
                    plan.kind, question, plan.language, results, problems, temperature=temperature,
                    conversation=context)])
                if not verify.foreign_script(narrative):
                    break
            else:
                # Every attempt slipped (the gateway's character restriction should
                # prevent this): drop the stray characters rather than send them.
                trace["error"] = f"foreign script removed: {''.join(verify.foreign_script(narrative))}"[:500]
                LOGGER.warning("Amharic answer still had other scripts after retries; %s", trace["error"])
                narrative = verify.scrub_foreign(narrative)
            pieces.append(narrative)
            yield {"type": "delta", "text": narrative}
        else:
            async for piece in compose.stream(plan.kind, question, plan.language, results, problems,
                                              conversation=context):
                pieces.append(piece)
                yield {"type": "delta", "text": piece}

        narrative = "".join(pieces)
        trace["unsupported_numbers"] = verify.unsupported_numbers(narrative, results, f"{question}\n{context}")
        foreign = verify.foreign_script(narrative)
        if foreign:
            LOGGER.warning("AI answer contains unexpected script characters: %s", "".join(foreign))
            trace["error"] = f"foreign script: {''.join(foreign)}"[:500]
        sections = render.web_sources(results) if plan.kind == "web" else render.sections(results)
        if sections:
            pieces.append(sections)
            yield {"type": "delta", "text": sections}

        answer = "".join(pieces)
        trace["latency_ms"] = int((time.monotonic() - started) * 1000)
        history_id = await _save(instance, question, answer, trace)
        yield {
            "type": "done",
            "history_id": history_id,
            "sources": (["the web"] if plan.kind == "web" and results
                        else sorted({r["source"] for r in results if r.get("source")})),
            "tools": [call["tool"] for call in plan.calls],
            "verified": not trace["unsupported_numbers"] and not foreign,
            "language": plan.language,
        }
    except LLMError as exc:
        LOGGER.warning("AI answer failed: %s", exc)
        trace.update(error=str(exc)[:500], latency_ms=int((time.monotonic() - started) * 1000))
        await _save(instance, question, "".join(pieces), trace)
        yield {"type": "error", "message": "The AI service is unavailable right now. Please try again shortly."}


async def answer(question, *, instance=None):
    """The whole answer at once, for REST and evaluation."""
    text, final = [], {}
    async for event in answer_stream(question, instance=instance):
        if event["type"] == "delta":
            text.append(event["text"])
        elif event["type"] in ("done", "error"):
            final = event
    return {"answer": "".join(text), **final}
