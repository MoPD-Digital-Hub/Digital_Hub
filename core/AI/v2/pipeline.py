"""The one answer pipeline, shared by the WebSocket, REST and evaluation.

Events (dicts), in order:
    {"type": "status", "stage": "planning" | "fetching" | "writing"}   (writing also carries "language")
    {"type": "delta", "text": "..."}          zero or more; the answer is their concatenation
    {"type": "done", "history_id", "sources", "tools", "verified"}   or   {"type": "error", "message"}

`done` deliberately does not repeat the answer: clients already have it from
the deltas (repeating it is what made the mobile app show answers twice in v1).
"""

import asyncio
import logging
import time

from asgiref.sync import sync_to_async

from AI.models import AnswerTrace, CatalogEntity, QuestionHistory
from AI.v2 import catalog, compose, planner, render, verify
from AI.v2.llm import LLMError
from AI.v2.tools import TOOLS, ToolError

LOGGER = logging.getLogger(__name__)
# Below this blended similarity a match is more likely wrong than right.
MIN_MATCH_SCORE = 0.45
OPTIONAL_ENTITY_KINDS = {"organization": CatalogEntity.ORGANIZATION}
AMHARIC_ATTEMPT_TEMPERATURES = (0, 0.4)


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
        LOGGER.exception("v2 tool %s failed", call["tool"])
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


async def answer_stream(question, *, instance=None):
    question = str(question or "").strip()
    started = time.monotonic()
    trace = {"language": "", "plan": {}, "resolved": [], "tool_calls": [], "unsupported_numbers": [], "error": ""}
    pieces = []
    try:
        yield {"type": "status", "stage": "planning"}
        plan = await planner.plan(question, await _history(instance))
        trace["language"], trace["plan"] = plan.language, plan.as_dict()

        results, problems = [], []
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
                    plan.kind, question, plan.language, results, problems, temperature=temperature)])
                if not verify.foreign_script(narrative):
                    break
            pieces.append(narrative)
            yield {"type": "delta", "text": narrative}
        else:
            async for piece in compose.stream(plan.kind, question, plan.language, results, problems):
                pieces.append(piece)
                yield {"type": "delta", "text": piece}

        narrative = "".join(pieces)
        trace["unsupported_numbers"] = verify.unsupported_numbers(narrative, results, question)
        foreign = verify.foreign_script(narrative)
        if foreign:
            LOGGER.warning("v2 answer contains unexpected script characters: %s", "".join(foreign))
            trace["error"] = f"foreign script: {''.join(foreign)}"[:500]
        sections = render.sections(results)
        if sections:
            pieces.append(sections)
            yield {"type": "delta", "text": sections}

        answer = "".join(pieces)
        trace["latency_ms"] = int((time.monotonic() - started) * 1000)
        history_id = await _save(instance, question, answer, trace)
        yield {
            "type": "done",
            "history_id": history_id,
            "sources": sorted({r["source"] for r in results if r.get("source")}),
            "tools": [call["tool"] for call in plan.calls],
            "verified": not trace["unsupported_numbers"] and not foreign,
        }
    except LLMError as exc:
        LOGGER.warning("v2 answer failed: %s", exc)
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
