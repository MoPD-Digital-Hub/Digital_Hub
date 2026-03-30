# AI App

## Overview

This AI app is a Gemini-first, intent-aware assistant service.

Current scope:
- intent-aware chat routing
- direct English and Amharic generation
- Milvus-backed retrieval for grounded answers
- time-series aware analysis
- dashboard generation tool integration
- HTTP and WebSocket chat flows
- persistent chat history in Django models

Removed from the active design:
- vLLM/OpenAI-compatible generation path
- translation-driven final response flow
- TTS and voice-specific AI endpoints
- legacy planner/runtime/provider abstractions

## Architecture

- `orchestration/classifier.py`: rule-based intent detection
- `orchestration/service.py`: central request router and dispatcher
- `orchestration/dashboard.py`: dashboard creation API integration
- `orchestration/time_series.py`: structured time-series query service
- `orchestration/formatter.py`: same-language tool response formatting
- `gemini/config.py`: environment-based Gemini settings and validation
- `gemini/language.py`: dominant-language detection for English vs Amharic
- `gemini/prompting.py`: prompt builder with same-language enforcement
- `gemini/client.py`: thin Gemini REST client
- `gemini/service.py`: Gemini text generation service
- `retrieval/config.py`: Milvus and embeddings settings
- `retrieval/embeddings.py`: embeddings client for Milvus queries
- `retrieval/service.py`: Milvus retrieval and context formatting
- `api.py`: thin HTTP controllers
- `consumers.py`: WebSocket chat controller
- `serializers.py`: API serializers
- `responses.py`: consistent API response helpers

## Same-Language Behavior

The system detects the dominant script in the user's message:
- Amharic script leads to Amharic output
- Latin script leads to English output

The prompt builder also repeats the required output language in the system prompt, so the model is instructed to answer directly in that language instead of translating afterward.

## Retrieval

Before text generation, the service retrieves supporting documents from Milvus and formats them into trusted context for Gemini. The generated answer is still in the user's language, but the factual grounding comes from the Milvus collection.

For documents that include an `indicator_code`, the retrieval layer also calls the time-series API and injects annual, quarterly, and monthly values into the trusted context. That enrichment is limited to a small number of indicators per request to control latency.

## Intent Routing

The request path now detects one of these intents before execution:
- `text_generation`
- `time_series_query`
- `dashboard_generation`

Routing behavior:
- normal explanatory questions go to Gemini text generation
- time-series questions go through the structured time-series tool path
- dashboard requests call the external dashboard creation API and return a same-language confirmation message

## Configuration

Required:
- `GEMINI_API_KEY`
- `MILVUS_URI`
- `MILVUS_COLLECTION_NAME`
- `EMBEDDING_API_BASE`

Optional:
- `GEMINI_TEXT_MODEL`
- `GEMINI_TIMEOUT_SECONDS`
- `GEMINI_TEMPERATURE`
- `GEMINI_TOP_P`
- `GEMINI_MAX_OUTPUT_TOKENS`
- `MAX_HISTORY_QUESTIONS`
- `GEMINI_HISTORY_TURNS`
- `GEMINI_STREAM_CHUNK_CHARS`
- `DASHBOARD_CREATE_API_URL`
- `DASHBOARD_TIMEOUT_SECONDS`
- `MILVUS_RETRIEVAL_K`
- `MILVUS_RETRIEVAL_FETCH_K`
- `MILVUS_TIMEOUT_SECONDS`
- `TIME_SERIES_API_BASE`
- `TIME_SERIES_INDICATOR_LIMIT`
- `EMBEDDING_MODEL`
- `EMBEDDING_API_KEY`
