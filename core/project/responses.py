"""The response shape for JSON APIs (docs/api.md).

    {"result": "SUCCESS" | "FAILURE",
     "message": "...",
     "request_id": "...",
     "data": ...,
     "error": {"code": "...", "message": "...", "details": {...}}   # failures only}

Views build responses with `success()` and `failure()`. Every JSON response
under /api/ also passes through `complete()` (project.middleware.
api_envelope_middleware), which adds whichever of these fields are missing,
e.g. on data passed through from the time-series service or on Django REST
framework's own errors. It only adds fields: values the installed mobile app
already reads are never changed, renamed or removed.
"""

import re

from rest_framework.response import Response

SUCCESS = "SUCCESS"
FAILURE = "FAILURE"
# Misspelling some endpoints (and the time-series service) return; kept because
# the installed mobile app may match it. See docs/api.md.
LEGACY_SUCCESS = "SUCCUSS"

STATUS_CODES = {
    400: "INVALID_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    429: "RATE_LIMITED",
    502: "UPSTREAM_ERROR",
    503: "SERVICE_UNAVAILABLE",
}
CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


def request_id(request):
    return getattr(request, "request_id", None)


def error_code(message, status_code):
    """`message` when it is already a code (LOGIN_FAILED), else one from the status."""
    if isinstance(message, str) and CODE_PATTERN.match(message):
        return message
    return STATUS_CODES.get(status_code, "SERVER_ERROR" if status_code >= 500 else "REQUEST_FAILED")


def success(request, data=None, message=SUCCESS, status=200, *, result=SUCCESS, headers=None, **extra):
    """A successful response. `extra` keys are added at the top level (legacy fields)."""
    body = {"result": result, "message": message, "request_id": request_id(request), "data": data, **extra}
    return Response(body, status=status, headers=headers)


def failure(request, message, status=400, *, code=None, details=None, error_message=None, data=None, **extra):
    """A failed response. `message` stays what clients already show; `error` adds a stable code."""
    if details is None and isinstance(extra.get("errors"), dict):
        details = extra["errors"]  # legacy top-level field errors, also exposed under error.details
    body = {
        "result": FAILURE,
        "message": message,
        "request_id": request_id(request),
        "data": data,
        "error": {
            "code": code or error_code(message, status),
            "message": error_message or message,
            "details": details or {},
        },
        **extra,
    }
    return Response(body, status=status)


# Fields the standard shape owns; anything else in a body is payload.
STANDARD_FIELDS = ("result", "message", "request_id", "data", "error", "errors", "detail", "code")


def complete(data, status_code, request):
    """`data` with the missing standard fields added. Existing fields are left exactly as they are."""
    if not isinstance(data, dict):
        return data  # a bare list or string cannot gain fields without changing its type
    failed = status_code >= 400
    body = dict(data)
    payload = {k: v for k, v in data.items() if k not in STANDARD_FIELDS}

    body.setdefault("result", FAILURE if failed else SUCCESS)
    if "message" not in body:
        text = next((data[k] for k in ("detail", "error") if isinstance(data.get(k), str)), None)
        body["message"] = text or (STATUS_CODES.get(status_code, "REQUEST_FAILED") if failed else SUCCESS)
    if not body.get("request_id"):
        body["request_id"] = request_id(request)
    if "data" not in body:
        # A bare object ({"years": [...]}) keeps its fields and is also offered under `data`.
        body["data"] = None if failed or not payload else payload
    if failed and "error" not in body:
        details = data.get("errors") if isinstance(data.get("errors"), dict) else payload
        body["error"] = {
            "code": str(data.get("code") or error_code(body["message"], status_code)),
            "message": str(body["message"]),
            "details": details,
        }
    return body


def exception_handler(exc, context):
    """DRF's handler, plus the error's code next to "detail" (e.g. "not_authenticated").

    Only adds a field, so existing clients keep working; complete() uses it as error.code.
    """
    from rest_framework.views import exception_handler as drf_exception_handler

    response = drf_exception_handler(exc, context)
    if response is not None and isinstance(response.data, dict) and "detail" in response.data \
            and "code" not in response.data and hasattr(exc, "get_codes"):
        codes = exc.get_codes()
        if isinstance(codes, str):
            response.data["code"] = codes
    return response
