# AI Module Architecture

## Folders
- `api/`: DRF endpoints for chat, answer generation, health checks, retriever debug.
- `services/`: orchestration for answer generation and persistence.
- `selectors/`: intent resolution and context strategy selection.
- `classifiers/`: prompt-based intent and period/performance extraction.
- `infrastructure/`: external integrations (LLM, embeddings, Milvus, dependency health checks).
- `shared/`: reusable utilities split by concern:
  - `chat.py` prompt message construction and LLM invocation helpers
  - `context.py` retrieval context builders
  - `upstream.py` DPMES/time-series API clients + formatters
  - `ingestion.py` ingestion pipeline helpers
  - `constants.py` shared constants
- `domain/`: static domain artifacts (`intents`, AI system rules).
- `platform/`: cross-cutting concerns (config validation, observability, resilience, error types).

## Runtime flow
1. API/consumer receives a question.
2. `services.generate_answer` retrieves documents from Milvus.
3. `selectors` resolves intent and builds intent-specific context.
4. `shared.chat.invoke_chat_once` calls configured LLM provider.
5. Structured success/failure payload is returned with request ID.

## Health endpoints
- `GET /api/ai-chat/health/`
- `GET /api/ai-chat/health/dependencies/`
- `GET /api/ai-chat/health/dependencies/<dependency_name>/`

Dependency names:
- `llm`, `embeddings`, `milvus`, `time_series_api`, `dpmes_score_api`, `dpmes_performance_api`
