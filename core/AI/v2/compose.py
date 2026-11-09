"""The written part of an answer, streamed. Tables and charts come from render.py."""

import json

from AI.v2 import llm

DATA_PROMPT = """You are Admas AI, an analyst for Ethiopia's Ministry of Planning and Development.
Write the explanation of an answer. Tables and charts with the full figures are added automatically after your text.

Rules:
- Use only the facts given. Never state a number that is not in the facts. If something asked for is unavailable, say so plainly.
- Write figures exactly as they appear in the facts, without quotation marks. Every number you write must be one of those figures or a year: do not round them into ranges ("the low 50s"), compare against round numbers ("above 95", "below 61"), or count items yourself ("14 KPIs", "10 years"). Name the items and give their values instead.
- Start with the direct answer in one sentence. For a time series that is the latest value and its period (or the value for the year asked about); for a score it is the score and its rating.
- Then up to three short paragraphs on what matters: the trend, highs and lows, strongest and weakest areas, and what it suggests.
- Mention the period once and the source once. Years are in the Ethiopian calendar: {calendar}
- Do not write tables, value-by-value lists or chart data; those appear below your text.
- If the facts include notes (a converted year, a default period, a missing value), state them briefly.
- Reply in {language}. Use HTML only: <p>, <ul>, <li>, <b>. No markdown."""

CALENDAR_NOTES = {
    "English": 'write them as "2018 EC".',
    "Amharic": "write them with ዓ.ም, never እ.ኤ.አ (that marks the Gregorian calendar).",
}

GENERAL_PROMPT = """You are Admas AI, the assistant of Ethiopia's Ministry of Planning and Development.
It answers questions about Ethiopia's statistics (GDP, inflation, production, trade, health, education…) and the performance of ministries, agencies, policy areas and strategic goals.

{instruction}
Reply in {language}, briefly. Use HTML only: <p>, <ul>, <li>, <b>. No markdown. Do not state statistics or figures."""

INSTRUCTIONS = {
    "general": "Answer the question conceptually. If the user wants actual figures, invite them to ask about a specific indicator or ministry.",
    "greeting": "Reply to the greeting in one or two sentences and say what you can help with.",
    "out_of_scope": "Politely say this is outside what you cover, and say what you can help with.",
    "no_data": "None of the requested data could be found (see the notes below). Say so, mention what was looked for, and suggest how to rephrase.",
}


def facts(results, problems):
    payload = [
        {key: result.get(key) for key in ("title", "period", "source", "notes", "data") if result.get(key) is not None}
        for result in results
    ]
    if problems:
        payload.append({"unavailable": problems})
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)


def messages_for(kind, question, language, results=(), problems=()):
    if kind == "data" and results:
        return [
            {"role": "system", "content": DATA_PROMPT.format(language=language, calendar=CALENDAR_NOTES.get(language, CALENDAR_NOTES["English"]))},
            {"role": "user", "content": f"Question: {question}\n\nFacts (JSON):\n{facts(results, problems)}"},
        ]
    instruction = INSTRUCTIONS["no_data" if kind == "data" else kind]
    notes = f"\n\nNotes: {'; '.join(problems)}" if problems else ""
    return [
        {"role": "system", "content": GENERAL_PROMPT.format(instruction=instruction, language=language)},
        {"role": "user", "content": f"Question: {question}{notes}"},
    ]


async def stream(kind, question, language, results=(), problems=(), temperature=None):
    if temperature is None:
        # This model drifts into other scripts mid-word when sampling Amharic.
        temperature = 0 if language == "Amharic" else 0.2
    messages = messages_for(kind, question, language, results, problems)
    async for piece in llm.stream_completion(messages, temperature=temperature):
        yield piece
