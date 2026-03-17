# AI Module Architecture

## Folders
- `endpoints/`: DRF endpoints for chat, answer generation, health checks, retriever debug.
- `application/`: orchestration for answer generation and persistence.
- `mcp_tools.py`: thin FastMCP entrypoint and compatibility facade.
- `tools/`: MCP runtime pieces split into `runtime`, `planner`, `handlers`, and helper utilities.
- `parsing/`: question parsing helpers for tool fallback, year/quarter extraction, and performance filtering.
- `infrastructure/`: external integrations (LLM, embeddings, Milvus, dependency health checks).
- `shared/`: reusable utilities split by concern:
  - `chat.py` prompt message construction and LLM invocation helpers
  - `context.py` retrieval context builders
  - `upstream.py` upstream response formatting helpers
  - `ingestion.py` ingestion pipeline helpers
  - `constants.py` shared constants
- `prompts/`: AI system rules and other stable prompt text artifacts.
- `runtime/`: cross-cutting concerns (config validation, observability, resilience, error types).

## Runtime flow
1. API/consumer receives a question.
2. `application.generate_answer` retrieves documents from Milvus.
3. `tools.planner.resolve_mcp_tool_plan` selects the best tool and `execute_mcp_tool_plan` builds the context.
4. `shared.chat.invoke_chat_once` or `run_chain_stream` calls the configured LLM provider with the selected route.
5. Structured success/failure payload is returned with request ID.

## Health endpoints
- `GET /api/ai-chat/health/`
- `GET /api/ai-chat/health/dependencies/`
- `GET /api/ai-chat/health/dependencies/<dependency_name>/`

Dependency names:
- `llm`, `embeddings`, `milvus`, `time_series_api`, `dpmes_score_api`, `dpmes_performance_api`
