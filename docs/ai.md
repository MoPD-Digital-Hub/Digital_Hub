# Admas AI

A data assistant over typed tools. It answers the mobile app and the web chat on `/ws/chat/`,
`/ws/chat-web/` and `/api/ai-chat/answer/`.

## How an answer is made

```
question
 1. Plan      one model call, JSON schema output: question kind + data calls with entity names
 2. Resolve   no model: names -> catalog entities (exact code/name/alias, then embedding similarity
              blended with rarity-weighted word overlap)
 3. Fetch     no model: typed tools call the time-series and DPMES APIs (cached 5 minutes) and read the
              national SDG platform (cached 1 hour)
 4. Compose   model, streamed: the written explanation, from the fetched facts only
 5. Render    no model: tables, <chart-data> blocks and a source line built from the fetched data
 6. Check     no model: numbers in the explanation must exist in the data; foreign-script detection
```

Code: `core/ai/engine/` — `planner.py`, `catalog.py` (built from `sources.py`, which reads the time-series, DPMES and SDG clients in `core/integrations/`), `tools.py`, `compose.py`, `render.py`,
`verify.py`, `pipeline.py`; `llm.py` is the gateway client.

Every answer writes a `QuestionHistory` row (the chat history) and an `AnswerTrace`
row: the plan, resolved entities with their scores and alternatives, each tool call with timing and errors,
unsupported numbers, latency. Use traces to see why an answer went wrong.

## Client protocol

`/ws/chat/<id>/`, `/ws/chat-web/<id>/` and `POST /api/ai-chat/answer/<id>/` use the message format the mobile
app and the web chat were built against (`core/ai/engine/compat.py`):

- Send `{"message": "your question"}` on the socket, or POST `{"question": "..."}`.
- English: `{"message", "preview", "is_stream": true}` pieces. Browsers then get a final
  `{"message", "is_stream": false, "is_final": true, "route"}` with the full answer; the mobile app (no
  `Origin` header) does not, or it would show the answer twice.
- Amharic and errors: one final message.
- `route` names the kind of answer (`get_time_series_context`, `get_ministry_score_context`, …).
- REST returns `data: {chat_instance_id, question, answer, route, token_usage}`; `token_usage` is always null.
- With `AI_USE_ASYNC_QUEUE=True` (or `?mode=async`) the REST answer is queued on Celery and polled at
  `/api/ai-chat/task-status/<task_id>/`.
- Each data block ends with `<p class="ai-source">Source: …</p>`, naming where its figures come from
  (for the SDG platform, also the survey or ministry behind them). Its `data-source` attribute names the source
  (`time_series`, `dpmes`, `sdg`); SDG lines also carry `data-sdg-goal` (1–17), which the web chat uses to show
  the goal's icon from sdg.mopd.gov.et. A `<chart-data>` block may carry `series`
  (several named lines); `labels`/`data` always hold the first, for clients that read only those.
- The answer HTML uses `<h4>`, `<table>` and `<chart-data>` blocks (`bar`, `line`, `pie`, and the
  `ministry_detail` button), which the app and web chat render.
- After a chat's first answer the chat is named from its question (`core/ai/engine/titles.py`): 2–6 words from
  the gateway model in the question's language, or the question's first words if the model is unavailable.
  Only chats still called "New Chat" (or untitled) are named, so a rename is never overwritten. Browsers get
  `{"event": "chat_title", "chat_instance_id", "title"}` on the socket; the app gets nothing new and reads the
  title from the chat list. On the REST path the title is made by the `ai.tasks.generate_chat_title` Celery task.
- Conversation memory: the planner and the writer both see the chat's last 5 turns (`planner.conversation`;
  the planner gets 300 characters of each earlier answer, the writer 700). Follow-ups like "what about 2016?"
  fetch new data; "explain that simply" or "summarise this for a briefing" are answered from the earlier answers.
  Figures quoted from those turns count as supported in the number check.
- After each answer browsers get up to three suggested next questions (`core/ai/engine/followups.py`) as
  `{"event": "followups", "chat_instance_id", "history_id", "questions"}`, shown as chips under the latest
  answer. The app is sent nothing new. Any failure gives no suggestions.
- A signed-in user can only open their own chat; `/ws/chat-web/` also replays the chat's history on connect.
- Whether the explanation's numbers were verified is not sent to clients; it is in the `AnswerTrace` row.
  The tables and charts are always exact.

## Operations

| Command | When |
|---|---|
| `python manage.py sync_ai_catalog` | After the first deploy, then daily (new indicators/organizations become answerable). Embeds only new or changed entries. |
| `python manage.py eval_ai` | Before every release: kind, tool and entity accuracy on `core/ai/engine/eval_questions.json`. |
| `python manage.py eval_ai --full` | Also answers every question end to end and reports verified rate and latency. |
| `python manage.py ask_ai "question"` | Try one question from a terminal and see its full trace. |

Run them inside the web container: `docker compose exec web python manage.py …` locally, or
`docker compose -f deploy/compose.production.yaml exec web python manage.py …` on the server.

Schedule the sync daily on the server with cron (as in `docs/deploy.md`):

```
15 2 * * * cd /mnt/data/Digital_Hub && docker compose -f deploy/compose.production.yaml run --rm --no-deps web python manage.py sync_ai_catalog >> /tmp/ai-catalog.log 2>&1
```

Configuration (in `.env`): `VLLM_API_BASE`, `VLLM_MODEL`, `VLLM_API_KEY`, `EMBEDDING_API_BASE`, `EMBEDDING_MODEL`,
`EMBEDDING_API_KEY`, `DPMES2_API_BASE`, `DPMES2_API_KEY`, optional `TIME_SERIES_API_BASE` and `SDG_PLATFORM_BASE`;
`SEARXNG_URL`, `WEB_SEARCH_ENABLED` and `WEB_SEARCH_DAILY_LIMIT` for web search.
The gateway is the only AI provider.

## Documents (PowerPoint, Word, PDF)

- "Make a PowerPoint on GDP growth", "Prepare a PDF report on the ministries in 2017", «በዋጋ ግሽበት ላይ የWord ሪፖርት
  አዘጋጅልኝ»: the planner marks these kind `document` with `document_format` `pptx`, `docx` or `pdf` (PowerPoint if
  unsaid) and plans the same lookups as a data question (or a web search for a general topic). A year named in
  the request is put on every lookup that takes one.
- `core/ai/documents/`: `datasets.py` reads the fetched results back from their chat rendering into charts and
  tables (so documents show exactly the chat's figures); `outline.py` has the model fill a structured outline
  (title, key messages, 3–6 sections with points, a chosen chart or table and speaker notes, conclusion);
  `slides.py`, `word.py` and `pdf.py` lay it out in the hub's design. PowerPoint charts are native and editable;
  Word and PDF use chart images (`charts.py`). PDFs embed Noto Sans and Noto Sans Ethiopic (`fonts/`, SIL OFL);
  Office files use Ebrima for Amharic and Calibri for English.
- The outline's numbers are checked like a chat answer's; if any are not in the data, the outline is rewritten
  once, told which numbers to drop. Amharic outlines get the glossary and the script check.
- Files are kept in the database (`GeneratedDocument`), not under `/media/` (which nginx serves publicly), so the
  web and worker containers share them. The answer links to `/api/ai-chat/documents/<id>/?t=<signed token>`: the
  token alone downloads (the mobile app opens the link in the browser); the signed-in owner needs none. Links
  are absolute when `SITE_URL` is set (both compose files set it). Files expire after `AI_DOCUMENT_DAYS` (7);
  beat runs `ai.tasks.delete_expired_documents` hourly. `AI_DOCUMENTS_DAILY_LIMIT` (10) caps files per user per
  day.
- A document takes 15–40 seconds (two model calls when the outline is rewritten).

## Web search (general questions)

- The planner marks a general question that needs current or outside facts (news, international organisations
  and programmes, other countries, laws, institutions) as kind `web`, with a short English `search_query`
  (Amharic questions are translated). Ethiopia's official statistics, ministry performance and SDG indicators
  are never `web`: they stay on the three national sources. Concepts ("what is inflation?") stay `general`.
- `core/integrations/websearch/client.py` asks the private SearXNG for results, drops social media and video
  sites, lifts official, international and established sources, and reads the top three pages as plain text.
  Pages are fetched only from public internet addresses, also after redirects. Only the query leaves the
  server, never the chat or the user.
- The writer answers from those pages only, cites them as [1], [2], treats page text as information and never
  as instructions, and the number check accepts only figures the pages contain. The answer ends with
  `<p class="ai-source" data-source="web">Source: the web: <a href="…">[1] imf.org</a> …</p>`.
- Mixed questions ("compare coffee exports of Brazil and Ethiopia", "Ethiopia's inflation vs Kenya's", "our GDP
  growth vs the Sub-Saharan average") are kind `data` (or `document`) with both calls and a `search_query`: the
  calls fetch Ethiopia's figures from the national sources, the search covers only the rest. Both run at once.
  The writer gets the facts and the pages with `compose.MIXED_RULES`: Ethiopia's figures only from the national
  data, the others cited [n], each figure's source named, no differences or ratios across sources, and a plain
  note when figures are not comparable (calendar, year, unit, value vs volume). The answer shows the official
  data panels and the web source line; the number check covers both. A `data` plan with no usable calls but a
  query is answered as `web`.
- The search query, the pages used or the error are kept in `AnswerTrace.tool_calls` (`"tool": "web_search"`).
  `WEB_SEARCH_DAILY_LIMIT` (default 50) caps answers that searched (web and mixed) per user per day. If the search is off,
  over the limit or finds nothing usable, the question is answered briefly from general knowledge, saying that
  current information could not be checked.

## Notes

- The gateway's vLLM does not enable native tool calling, so planning uses `response_format: json_schema`.
  If the gateway is started with `--enable-auto-tool-choice --tool-call-parser …`, the planner could switch
  to native tools without changing the rest of the pipeline.
- The catalog is about fifteen hundred entities, so vectors are held in memory and compared with one matrix
  product; no vector database is needed at this size.
- SDG data comes from the national SDG platform (sdg.mopd.gov.et, `core/integrations/sdg/`). It has no JSON
  API, so the client reads the data each goal page embeds (`__NEXT_DATA__`). Tools: `sdg_goal` (latest national
  value of each of a goal's indicators) and `sdg_indicator` (one indicator by year, nationally or broken down by
  region, sex, age, area, education or wealth). An indicator without data of its own (1.1.1) is answered by its
  proxy or additional indicator (1.1.1P1). For topics both sources cover (GDP, inflation, maternal mortality) the
  planner uses the time-series database unless the question mentions the SDGs.
- Years: DPMES and the time-series data use the Ethiopian calendar; the SDG platform uses Gregorian years,
  and its results say so (`"calendar": "Gregorian"`), so the answer does not write them as EC. A year later than the current Ethiopian year
  is read as Gregorian and converted (Y − 8), and the answer says so. DPMES questions without a year use the
  last completed year, like the dashboard.
- Amharic questions are planned and answered by the gateway model directly. Unconstrained, it writes words it
  does not know in other scripts ("ያልمركزነት", "በгосударство"). Defences (`core/ai/engine/amharic.py`):
  1. The writer may only generate Ethiopic, Latin, digits, punctuation and HTML: `amharic.ALLOWED_PATTERN`
     is sent as vLLM structured outputs (`extra_body={"structured_outputs": {"regex": …}}`). The gateway honours
     it (tested 2026-11-12; the older `guided_regex` is ignored). If the gateway rejects it, the answer is
     written without it. `AI_AMHARIC_CONSTRAINED=False` turns it off.
  2. Amharic prompts include a glossary of standard government and economic terms (`amharic.GLOSSARY`) and
     say to put an unknown term in English in parentheses. The glossary is a draft until reviewed by someone
     who writes the Ministry's official Amharic.
  3. The answer is checked for other scripts and rewritten once; if both attempts fail, the stray characters
     are removed before sending and the trace's `error` records it ("foreign script removed").
  4. `eval_questions.json` has Amharic questions; `manage.py eval_ai --full` reports how many Amharic answers
     needed repair or still contain other scripts.
