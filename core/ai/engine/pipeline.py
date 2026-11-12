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

# Imported late by _document: the document builders pull in matplotlib and the Office libraries.
DOCUMENT_UNITS = {
    "English": {"pptx": ("slide", "slides"), "docx": ("section", "sections"), "pdf": ("page", "pages")},
    "Amharic": {"pptx": ("ስላይድ", "ስላይዶች"), "docx": ("ክፍል", "ክፍሎች"), "pdf": ("ገጽ", "ገጾች")},
}
DOCUMENT_MESSAGES = {
    "English": {
        "ready": "Your {kind} <b>{title}</b> is ready: {count} {unit}, built from {sources}.",
        "official": "official data",
        "web": "web sources",
        "download": "Download {filename}",
        "limit": "You have reached today's limit for documents. Please try again tomorrow.",
        "no_data": "I could not find the data for this document ({problems}). Try naming the indicator, "
                   "ministry or SDG you want it to cover.",
        "missing": "Some of the data could not be found: {problems}.",
    },
    "Amharic": {
        "ready": "{kind}ዎ <b>{title}</b> ዝግጁ ነው፦ {count} {unit}፣ ከ{sources} የተዘጋጀ።",
        "official": "ይፋዊ መረጃዎች",
        "web": "የድር ምንጮች",
        "download": "{filename} ያውርዱ",
        "limit": "የዛሬውን የሰነድ ገደብ ጨርሰዋል። እባክዎ ነገ እንደገና ይሞክሩ።",
        "no_data": "ለዚህ ሰነድ የሚያስፈልገውን መረጃ ማግኘት አልቻልኩም ({problems})። መሸፈን የሚፈልጉትን አመልካች፣ ሚኒስቴር ወይም "
                   "የዘላቂ ልማት ግብ በስም ይጥቀሱ።",
        "missing": "አንዳንድ መረጃዎች አልተገኙም፦ {problems}።",
    },
}

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
    # Every answer that searched counts: "web" questions and mixed ones (their plan has a search_query).
    used = AnswerTrace.objects.filter(instance__user_id=instance.user_id, created_at__date=timezone.localdate(),
                                      plan__has_key="search_query").count()
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


async def _document(plan, question, instance, results, pages, problems, context, trace):
    """Make the requested document; the chat message announcing it, with its download link."""
    from html import escape

    from ai.documents import datasets as document_datasets
    from ai.documents import design as document_design
    from ai.documents import outline as document_outline
    from ai.documents import service as document_service

    text = DOCUMENT_MESSAGES.get(plan.language, DOCUMENT_MESSAGES["English"])
    entry = {"tool": "document", "format": plan.document_format, "error": ""}
    trace["tool_calls"].append(entry)
    if not await document_service.quota_left(instance):
        entry["error"] = "daily limit"
        return f"<p>{text['limit']}</p>"
    data = document_datasets.build(results)
    if plan.calls and not data and not pages:
        entry["error"] = "no data"
        return f"<p>{escape(text['no_data'].format(problems='; '.join(problems) or '-'))}</p>"

    def unsupported(draft):
        return verify.unsupported_numbers(" ".join(document_outline.texts(draft)), list(results) + list(pages),
                                          f"{question}\n{context}")

    outline = await document_outline.write(question, plan.document_format, plan.language, data, results, pages,
                                           context)
    flagged = unsupported(outline)
    if flagged:
        # Documents are shared beyond the chat: rewrite once without the figures the data does not support.
        entry["rewritten_for"] = flagged
        retry = await document_outline.write(question, plan.document_format, plan.language, data, results, pages,
                                             context, avoid=flagged)
        if len(unsupported(retry)) < len(flagged):
            outline, flagged = retry, unsupported(retry)
    trace["unsupported_numbers"] = flagged
    sources = document_datasets.sources(data, pages)
    content, count = await asyncio.to_thread(document_service.build, plan.document_format, outline, data, sources,
                                             plan.language)
    if len(content) > document_service.MAX_BYTES:
        entry["error"] = f"too large ({len(content)} bytes)"
        raise LLMError("The document came out too large to send.")
    document = await document_service.save(instance, plan.document_format, outline["title"], content)
    entry.update(id=str(document.id), count=count, size=len(content))

    units = DOCUMENT_UNITS.get(plan.language, DOCUMENT_UNITS["English"])[plan.document_format]
    kind = document_design.FORMAT_NAMES.get(plan.language, document_design.FORMAT_NAMES["English"])[plan.document_format]
    where = " + ".join(filter(None, [text["official"] if data else "", text["web"] if pages else ""])) or text["official"]
    ready = text["ready"].format(kind=escape(kind), title=escape(outline["title"]), count=count,
                                 unit=units[0] if count == 1 else units[1], sources=where)
    message = f"<p>{ready}</p>"
    if problems:
        message += f"<p>{escape(text['missing'].format(problems='; '.join(problems)))}</p>"
    message += (f'<p class="ai-document" data-format="{plan.document_format}">'
                f'<a href="{escape(document_service.download_url(document), quote=True)}" '
                f'download="{escape(document.filename, quote=True)}">'
                f'{escape(text["download"].format(filename=document.filename))}</a> '
                f'<span>{max(1, round(len(content) / 1024))} KB</span></p>')
    return message


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

        results, problems, pages = [], [], []
        # The web search (a "web" question, or the outside part of a mixed one) runs
        # alongside the national-data lookups.
        research = None
        if plan.search_query and plan.kind in ("web", "data", "document"):
            yield {"type": "status", "stage": "searching"}
            research = asyncio.create_task(_web_research(plan, instance))
        if plan.calls:
            yield {"type": "status", "stage": "fetching"}
            for result, problem, resolved, entry in await asyncio.gather(*(_run_call(c) for c in plan.calls)):
                trace["resolved"] += resolved
                trace["tool_calls"].append(entry)
                if result:
                    results.append(result)
                if problem:
                    problems.append(problem)
        if research is not None:
            pages, entry, problem = await research
            trace["tool_calls"].append(entry)
            if problem:
                problems.append(problem)
            if plan.kind == "web":
                results, pages = pages, []

        yield {"type": "status", "stage": "writing", "language": plan.language}
        if plan.kind == "document":
            narrative = await _document(plan, question, instance, results, pages, problems, context, trace)
            pieces.append(narrative)
            yield {"type": "delta", "text": narrative}
        elif plan.language == "Amharic":
            # Written in full and checked before sending: the model sometimes
            # corrupts Amharic words with other scripts, and a streamed word
            # cannot be taken back. Greedy decoding would repeat the same
            # corruption, so the retry samples a little.
            for temperature in AMHARIC_ATTEMPT_TEMPERATURES:
                narrative = "".join([p async for p in compose.stream(
                    plan.kind, question, plan.language, results, problems, temperature=temperature,
                    conversation=context, pages=pages)])
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
                                              conversation=context, pages=pages):
                pieces.append(piece)
                yield {"type": "delta", "text": piece}

        narrative = "".join(pieces)
        if plan.kind != "document":  # a document's own text is checked in _document
            trace["unsupported_numbers"] = verify.unsupported_numbers(
                narrative, list(results) + list(pages), f"{question}\n{context}")
        foreign = verify.foreign_script(narrative)
        if foreign:
            LOGGER.warning("AI answer contains unexpected script characters: %s", "".join(foreign))
            trace["error"] = f"foreign script: {''.join(foreign)}"[:500]
        if plan.kind == "web":
            sections = render.web_sources(results)
        else:
            sections = render.sections(results) + render.web_sources(pages)
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
                        else sorted({r["source"] for r in results if r.get("source")}) + (["the web"] if pages else [])),
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
