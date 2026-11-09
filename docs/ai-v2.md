# Admas AI v2

A data assistant over typed tools. It has its own endpoints (below), and it can also answer the existing v1
endpoints in the v1 message format, so the mobile app and web chat switch without a release (see Rollout).

## How an answer is made

```
question
 1. Plan      one model call, JSON schema output: question kind + data calls with entity names
 2. Resolve   no model: names -> catalog entities (exact code/name/alias, then embedding similarity
              blended with rarity-weighted word overlap)
 3. Fetch     no model: typed tools call the time-series and DPMES APIs (cached 5 minutes)
 4. Compose   model, streamed: the written explanation, from the fetched facts only
 5. Render    no model: tables and <chart-data> blocks built from the fetched data
 6. Check     no model: numbers in the explanation must exist in the data; foreign-script detection
```

Code: `core/AI/v2/` — `planner.py`, `catalog.py`, `tools.py`, `compose.py`, `render.py`, `verify.py`, `pipeline.py`.

Every answer writes a `QuestionHistory` row (so chat history works for v1 and v2 alike) and an `AnswerTrace`
row: the plan, resolved entities with their scores and alternatives, each tool call with timing and errors,
unsupported numbers, latency. Use traces to see why an answer went wrong.

## Client protocol

### WebSocket: `/ws/v2/chat/<chat_instance_id>/`

Send:

```json
{"message": "What is Ethiopia's GDP growth?"}
```

Receive, in order:

```json
{"type": "status", "stage": "planning"}
{"type": "status", "stage": "fetching"}
{"type": "status", "stage": "writing"}
{"type": "delta", "text": "<p>GDP grew 7.7% in 2018 EC…"}
{"type": "delta", "text": "…</p>"}
{"type": "delta", "text": "<h4>GDP Growth: annual</h4><table>…</table><chart-data>{…}</chart-data>"}
{"type": "done", "history_id": 812, "sources": ["MoPD"], "verified": true}
```

- **The answer is the concatenation of all `delta` texts.** `done` does not repeat it — render the deltas
  and finish on `done`. (v1 repeated the whole answer at the end, which the mobile app showed twice.)
- `status` events are optional to display; `fetching` is skipped when no data is needed.
- On failure the stream ends with `{"type": "error", "message": "..."}` instead of `done`.
- The answer HTML uses the same tags and `<chart-data>` blocks as v1 (`bar`, `line`, `pie`, and the
  `ministry_detail` button), so existing renderers work unchanged.
- `verified: false` means the explanation contains a number not found in the fetched data, or text in an
  unexpected script. The tables and charts are always exact.
- One question at a time per connection; a question sent mid-answer gets an `error` event.
- A signed-in user can only open their own chat instance.

### REST: `POST /api/ai-chat/v2/answer/<chat_instance_id>/`

```json
{"question": "Which ministries performed worst?"}
```

Returns the usual envelope with `data: {answer, history_id, sources, verified}`. Same pipeline, no streaming.

## Rollout: v2 behind the v1 endpoints

`/ws/chat/<id>/` and `POST /api/ai-chat/answer/<id>/` can be answered by v2 without any client change.
Set in `.env`, then restart Daphne:

| Setting | Effect |
|---|---|
| `AI_ENGINE=v1` (default) | Everyone gets v1. |
| `AI_ENGINE=v1` + `AI_ENGINE_V2_USERS=a@mopd.gov.et,b@mopd.gov.et` | Chats owned by those users get v2; everyone else v1 (pilot). |
| `AI_ENGINE=v2` | Everyone gets v2. |

Rolling back is `AI_ENGINE=v1` and a restart. What the v1 clients receive from v2 (`core/AI/v2/compat.py`):

- English: the same `{"message", "preview", "is_stream": true}` pieces as v1. Browsers then get the final
  `{"message", "is_stream": false, "is_final": true, "route"}` with the full answer; the mobile app (no
  `Origin` header) does not, as since `e918740`.
- Amharic and errors: one final message, as in v1.
- `route` uses v1's names (`get_time_series_context`, `get_ministry_score_context`, …) so nothing that reads it breaks.
- REST returns v1's `data: {chat_instance_id, question, answer, route, token_usage}`; `token_usage` is null.
- Status events and `verified` are not sent on the v1 endpoints; they are in the `AnswerTrace` row.
- With `AI_USE_ASYNC_QUEUE=True` the REST endpoint keeps using v1 (Celery); the socket uses the setting above.

## Operations

| Command | When |
|---|---|
| `python manage.py sync_ai_catalog` | After deploying v2, then daily (new indicators/organizations become answerable). Embeds only new or changed entries. |
| `python manage.py eval_ai_v2` | Before every release: kind, tool and entity accuracy on `core/AI/v2/eval_questions.json`. |
| `python manage.py eval_ai_v2 --full` | Also answers every question end to end and reports verified rate and latency. |
| `python manage.py ask_ai_v2 "question"` | Try one question from a terminal and see its full trace. |

Schedule the sync daily, for example with cron as the app user:

```
15 2 * * * cd /mnt/data/Digital_Hub/core && ../.venv/bin/python manage.py sync_ai_catalog >> /var/log/ai-catalog.log 2>&1
```

Configuration (in `.env`): `VLLM_API_BASE`, `VLLM_MODEL`, `VLLM_API_KEY`, `EMBEDDING_API_BASE`, `EMBEDDING_MODEL`,
`EMBEDDING_API_KEY`, `DPMES2_API_BASE`, `DPMES2_API_KEY`, optional `TIME_SERIES_API_BASE`. v2 does not use
Milvus or Gemini.

## Notes

- The gateway's vLLM does not enable native tool calling, so planning uses `response_format: json_schema`.
  If the gateway is started with `--enable-auto-tool-choice --tool-call-parser …`, the planner could switch
  to native tools without changing the rest of the pipeline.
- The catalog is about a thousand entities, so vectors are held in memory and compared with one matrix product;
  no vector database is needed at this size.
- Years: DPMES and the time-series data use the Ethiopian calendar. A year later than the current Ethiopian year
  is read as Gregorian and converted (Y − 8), and the answer says so. DPMES questions without a year use the
  last completed year, like the dashboard.
- Amharic questions are planned and answered by the gateway model directly. It occasionally drifts into other
  scripts mid-word; answers are written with temperature 0 and checked for foreign script.
