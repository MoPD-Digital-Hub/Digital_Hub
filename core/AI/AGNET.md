# AI App Agent Notes

## Scope
- The AI app is the Admas AI backend inside `core/AI/`.
- It supports:
- authenticated REST chat
- authenticated WebSocket chat streaming
- same-language English/Amharic answers
- Milvus-grounded retrieval
- time-series enrichment and chart payloads
- dashboard generation via an external API
- persistent chat history in Django models

## Main Files
- `api.py`: REST endpoints for health, dependency health, chat instances, history, and answers.
- `consumers.py`: Channels WebSocket consumer for streamed chat.
- `models.py`: `Document`, `LoadedFile`, `ChatInstance`, `QuestionHistory`.
- `serializers.py`: output serializers for instances and history.
- `responses.py`: standardized success/error envelopes.
- `routing.py`: WebSocket route `ws/chat/<room_name>/`.

## Data Model
- `ChatInstance`: one conversation per user, soft-deletable, title auto-derived from first real question.
- `QuestionHistory`: stores `question`, rendered `response`, `chart_data`, `tool_data`, timestamps.
- `tool_data` is the key memory mechanism for follow-up behavior. It stores intent, topic, resolved prompt, and tool result metadata.

## HTTP Flow
1. `POST /api/ai-chat/answer/<chat_instance_id>/` enters `api.answer`.
2. The endpoint validates ownership and non-empty `question`.
3. Prior non-empty history is loaded with `question`, `response`, `tool_data`, `chart_data`.
4. A blank `QuestionHistory` row is created before orchestration.
5. `AIOrchestrator.handle()` is called.
6. The result message, charts, and tool state are written back to `QuestionHistory`.
7. If the chat title is generic, it is replaced with a shortened version of the current question.
8. The response returns intent, secondary intents, language, usage, sources, charts, tool data, and whether context was found.

## WebSocket Flow
1. `ChatConsumer.connect()` loads the chat instance by room name and ensures the socket user owns it.
2. `receive()` validates JSON and requires `message`.
3. It loads history and creates a `QuestionHistory` row.
4. `AIOrchestrator.stream()` yields streamed events.
5. Each chunk is sent immediately with `is_stream=true`.
6. On completion, the full answer plus charts/tool data is persisted and sent with `is_final=true`.
7. On orchestration failure, the error message is persisted and an error envelope is sent.

## Layered Architecture
- `gemini/`: generation settings, language detection, prompt construction, Gemini HTTP/SSE client, generation service.
- `orchestration/`: intent classification, follow-up resolution, dashboard/time-series dispatch, error normalization.
- `retrieval/`: query normalization, alias expansion, embeddings setup, Milvus retrieval, reranking, time-series API enrichment.

## Intent System
- `IntentClassifier` is rule-based, not model-based.
- Primary intents:
- `text_generation`
- `time_series_query`
- `dashboard_generation`
- Dashboard intent requires both:
- a dashboard term like `dashboard` or `ዳሽቦርድ`
- an action pattern like `generate`, `create`, `build`, `make`
- Time-series intent is triggered by:
- indicator-code pattern match
- or any configured time-series keywords such as `trend`, `annual`, `quarterly`, `graph`, `አዝማሚያ`, `ግራፍ`
- Dashboard intent can carry `time_series_query` as a secondary intent.

## Query Preprocessing
- `QueryPreprocessor` runs before classification and retrieval candidate construction.
- Empty input returns an empty `PreprocessedQuery`.
- Amharic input is preserved exactly.
- English input gets:
- whitespace normalization
- typo correction against domain terms
- semantic expansion variants, e.g. `gdp` => `gross domestic product`
- a `best_query` selection using similarity plus bonuses for corrected/expanded candidates
- This is why misspelled prompts like `genrate dashabord about inlation` still route correctly.

## Conversation Resolution
- `ConversationStateResolver` upgrades vague follow-ups into explicit prompts.
- It inspects previous `tool_data`, `chart_data`, last question, and last response.
- Supported follow-up behaviors:
- `generate it` after a previous dashboard topic => generate that dashboard
- `show me the link` after dashboard creation => return the stored share URL without creating again
- `explain more`, `detail analysis`, `table format`, `what does this mean` => reconstruct a richer prompt about the previous topic
- If a follow-up is context-dependent and the previous intent was dashboard generation, the resolver downgrades the follow-up to `text_generation` so it explains the dashboard instead of trying to create another one.

## Orchestrator
- `AIOrchestrator.handle()` is the synchronous path.
- `AIOrchestrator.stream()` is the WebSocket path.
- Dispatch logic:
- dashboard intent => `DashboardGenerationService`
- time-series intent => `TimeSeriesQueryService`
- otherwise => `GeminiChatService`
- Error mapping:
- dashboard failures => `DASHBOARD_FAILED`
- time-series failures => `TIME_SERIES_FAILED`
- retrieval failures => `RETRIEVAL_FAILED`
- Gemini client failures => `GENERATION_FAILED`
- For context-dependent time-series follow-ups, if no structured data is found but previous context exists, the stream path can fall back to plain text generation using reconstructed context.

## Gemini Layer
- `gemini/language.py` uses script counts only:
- Amharic Unicode block count >= Latin count => `Amharic`
- otherwise => `English`
- `gemini/prompting.py` builds a system prompt that enforces:
- same-language output
- HTML-only output
- no fabricated official data
- grounded, analytical answers
- short HTML paragraphs instead of markdown
- `GeminiTextClient` uses:
- blocking `requests` for normal generation
- `aiohttp` SSE for streaming generation
- `iter_chunks()` is a local sentence-based chunker used on full text when needed.
- `GeminiChatService` always performs retrieval first, then generates against the retrieved context.
- History is trimmed to the last `MAX_HISTORY_QUESTIONS` question/response pairs.
- Charts are filtered to at most one relevant chart and suppressed if the user explicitly asks for no chart/graph.

## Retrieval Layer
- `normalize_retrieval_query()` translates Amharic retrieval queries into concise English using Gemini, but leaves English unchanged.
- `resolve_indicator_query()` expands metric aliases and ministry aliases, e.g. `gdp`, `cpi`, `moh`.
- `MilvusContextRetriever.retrieve()`:
- preprocesses the question
- builds up to four query candidates
- queries Milvus for each candidate
- deduplicates documents
- reranks them by metadata/content token overlap and indicator-code bonus
- formats final context blocks
- Each context block includes metadata such as:
- `indicator_eng`
- `indicator_code`
- `topic_name`
- `category_name`
- `responsible_ministry_eng`
- `source`
- `year`
- `quarter`
- The retriever can enrich a limited number of documents with time-series API results using `indicator_code`.
- The retriever can also enrich ministry/public body documents with DPMES scorecard data when retrieval metadata contains a ministry/public body name or ID.
- The score enrichment forwards `year` and `quarter` from the user question when present.
- Supported quarter inputs are `3month`, `6month`, `9month`, `12month`, and `Q1` to `Q4`.

## Time-Series Enrichment
- `fetch_indicator_time_series()` calls `${TIME_SERIES_API_BASE}/annual_value/?code=<indicator_code>`.
- `format_time_series_context()` appends annual/quarter/month values into the trusted context text.
- `build_time_series_chart()` converts the payload into a frontend-friendly chart dict.
- The chart prefers:
- annual data first
- otherwise quarter data
- otherwise month data
- `TimeSeriesQueryService` requires at least one chart-like structured series; otherwise it raises `TimeSeriesQueryError`.

## API Output Shapes
- REST success envelope:
- `result`
- `message`
- `request_id`
- `data`
- AI answer payload contains:
- `chat_instance_id`
- `chat_title`
- `question`
- `intent`
- `secondary_intents`
- `answer`
- `language`
- `usage`
- `context_found`
- `sources`
- `charts`
- `tool_data`
- History serializer exposes `charts` from `chart_data` and `tool_data` as normalized dict/list fields.

## Health Endpoints
- `/api/ai-chat/health/`: Gemini provider/model/configured flag.
- `/api/ai-chat/health/dependencies/`: Gemini status, Milvus health, dashboard API config presence.

## Key Environment Variables
- Gemini:
- `GEMINI_API_KEY`
- `GEMINI_TEXT_MODEL`
- `GEMINI_TIMEOUT_SECONDS`
- `GEMINI_TEMPERATURE`
- `GEMINI_TOP_P`
- `GEMINI_MAX_OUTPUT_TOKENS`
- `MAX_HISTORY_QUESTIONS` or `GEMINI_HISTORY_TURNS`
- `GEMINI_STREAM_CHUNK_CHARS`
- Retrieval:
- `MILVUS_URI`
- `MILVUS_COLLECTION_NAME`
- `MILVUS_RETRIEVAL_K`
- `MILVUS_RETRIEVAL_FETCH_K`
- `MILVUS_TIMEOUT_SECONDS`
- `EMBEDDING_API_BASE`
- `EMBEDDING_MODEL`
- `EMBEDDING_API_KEY`
- `TIME_SERIES_API_BASE`
- `TIME_SERIES_INDICATOR_LIMIT`
- `DPMES_API_BASE`
- `PUBLIC_BODY_SCORE_LIMIT`
- Orchestration:
- `DASHBOARD_CREATE_API_URL`
- `DASHBOARD_TIMEOUT_SECONDS`

## Important Behavioral Constraints
- Responses are HTML, not markdown.
- Same-language output is a hard rule.
- Retrieval is always attempted before text generation.
- Time-series intent is stricter than generic retrieval: no structured series means failure or fallback depending on context.
- Dashboard follow-ups rely on persisted `tool_data`; if that is missing, follow-up quality drops.
- The app assumes authenticated users for all AI API endpoints and WebSocket sessions.

## Tests That Define Behavior
- `GeminiLanguageTests`: script-based language detection.
- `GeminiPromptTests`: prompt language enforcement.
- `IntentClassifierTests`: dashboard/time-series routing.
- `GeminiServiceTests`: retrieval-first generation, history trimming, chart suppression.
- `OrchestrationTests`: prompt correction, dashboard follow-ups, existing-link retrieval, context-dependent follow-up reconstruction.
- `TimeSeriesEnrichmentTests`: chart/context building from indicator API payloads.
- `QueryPreprocessingTests`: typo correction, expansion, Amharic preservation.
- `RetrievalNormalizationTests`: Amharic retrieval normalization and alias expansion.
- `AIApiTests`: answer payloads, persistence, error handling, title updates.

## Practical Debug Order
- If routing is wrong, inspect:
- `query_preprocessing.py`
- `orchestration/classifier.py`
- `orchestration/context.py`
- If text is wrong but routing is right, inspect:
- `gemini/prompting.py`
- `gemini/service.py`
- `retrieval/service.py`
- If charts are missing, inspect:
- `retrieval/time_series.py`
- `retrieval/service.py`
- `orchestration/time_series.py`
- If follow-ups behave badly, inspect saved `QuestionHistory.tool_data` first.

## Current Repo Reality
- This app is in the middle of a refactor.
- The newer path is the one to trust:
- `api.py`
- `serializers.py`
- `responses.py`
- `gemini/`
- `orchestration/`
- `retrieval/`
- There are deleted/legacy AI modules still visible in git status from the older architecture. Do not rebuild against those by accident.
