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
`EMBEDDING_API_KEY`, `DPMES2_API_BASE`, `DPMES2_API_KEY`, optional `TIME_SERIES_API_BASE` and `SDG_PLATFORM_BASE`.
The gateway is the only AI provider.

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
- Amharic questions are planned and answered by the gateway model directly. It occasionally drifts into other
  scripts mid-word; answers are written with temperature 0 and checked for foreign script.
