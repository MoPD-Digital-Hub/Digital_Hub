# API responses

Every JSON endpoint under `/api/` returns the same shape.

Success:

```json
{"result": "SUCCESS", "message": "SUCCESS", "request_id": "6f1c…", "data": {}}
```

Failure:

```json
{
  "result": "FAILURE",
  "message": "Email or password is incorrect",
  "request_id": "6f1c…",
  "data": null,
  "error": {"code": "LOGIN_FAILED", "message": "Email or password is incorrect", "details": {}}
}
```

- Decide success or failure by the HTTP status (2xx or not). On failure, branch on `error.code`.
- `message` is the text to show; `error.details` holds field errors, e.g. `{"email": ["This field is required."]}`.
- `request_id` is also the `X-Request-ID` header; send your own `X-Request-ID` to trace a request.
- Framework errors use the framework's code: `not_authenticated`, `permission_denied`, `token_not_valid`,
  `method_not_allowed`, `not_found`, `throttled`. Refresh the access token on `token_not_valid`; when the
  refresh itself is rejected (401, `token_not_valid`), sign in again.

## Admas AI documents

`GET /api/ai-chat/documents/<uuid>/?t=<token>` downloads a PowerPoint, Word or PDF file the assistant made (the
link is in the answer, inside `<p class="ai-document" data-format="pptx|docx|pdf">`). It returns the file, not
JSON: 404 for an unknown id or wrong token, 410 once the file has expired (after 7 days).

## Compatibility with the installed mobile app

Responses are completed, never changed: fields the app already reads keep their exact names and values, and
the standard fields are added only where missing (`project.responses.complete()`). So some responses still
carry older extras, which new code should not rely on:

| Older value or field | Where | Use instead |
|---|---|---|
| `"result": "SUCCUSS"` (misspelled) | a few `/api/mobile/` and `/api/user/` endpoints, and data from the time-series service | the HTTP status |
| `"result": "FAILED"` | failures from the time-series service | the HTTP status, `error.code` |
| `"detail"`, `"code"` | framework errors | `message`, `error.code` |
| `"errors"` | invalid input on the sign-in endpoint | `error.details` |
| `"error": "…"` as text | one time-series error (`filter-initiative-indicator-by-region`) | `message` |
| top-level `years` / bucket fields | `/api/mobile/dpmes-year-lists/`, `/api/mobile/ministry-performance/…` | `data` |

Once no installed app version reads them, these can be removed and `result` corrected in one change.

Responses that are not JSON (Excel exports) are unaffected. The WebSocket protocols are in
`docs/ai.md` and `docs/flutter-chat-integration.md`.

## In code

Views build responses with `project.responses.success()` and `failure()`; never write the envelope by hand.

```python
from project.responses import failure, success

return success(request, serializer.data)
return failure(request, "INVALID_INPUT", status.HTTP_400_BAD_REQUEST, errors=serializer.errors)
```

`project/middleware/api_envelope_middleware.py` runs `complete()` on every JSON response under `/api/`, which
covers responses the views do not build themselves (time-series data passed through, framework errors).
Tests: `core/project/tests.py`.
