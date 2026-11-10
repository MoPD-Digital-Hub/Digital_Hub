# AI app (`ai`, app label `AI`)

How answers are made, the client protocol and the operations commands are in [docs/ai.md](../../docs/ai.md).

- `engine/`: the answer pipeline (plan → resolve → fetch → compose → render → check).
- `consumers.py`: `/ws/chat/` and `/ws/chat-web/` (app and web chat), `/ws/tts-stream/` (read-aloud).
- `api/`: REST views and serializers: chat instances, history, answer, translate, TTS, health.
- `infrastructure/`: Gemini translation and TTS, dependency health checks.
- `config.py`: checks the gateway settings at startup.
- `models.py`: chats and history, the entity catalog, answer traces.
- `management/commands/`: `sync_ai_catalog`, `eval_ai`, `ask_ai`.

Health: `GET /api/ai-chat/health/`, `/health/dependencies/`, `/health/dependencies/<name>/` with names
`llm`, `embeddings`, `time_series_api`, `dpmes_score_api`, `dpmes_performance_api`.
