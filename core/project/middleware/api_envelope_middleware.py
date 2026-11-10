"""Complete every JSON response under /api/ to the standard shape (project.responses).

Only missing fields are added (request_id, result, message, data, error), so the
installed mobile app keeps reading exactly what it reads today. Non-JSON
responses (audio, Excel exports, the OpenAPI schema) pass through untouched.
"""

from rest_framework.response import Response

from project.responses import complete

API_PREFIX = "/api/"
SKIPPED_PREFIXES = ("/api/schema/", "/api/docs/")


class ApiEnvelopeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (not request.path.startswith(API_PREFIX) or request.path.startswith(SKIPPED_PREFIXES)
                or not isinstance(response, Response)
                or not response.get("Content-Type", "").startswith("application/json")):
            return response
        completed = complete(response.data, response.status_code, request)
        if completed == response.data:
            return response
        response.data = completed
        # Re-render with the new body (DRF renders before middleware runs).
        response._is_rendered = False
        response.render()
        # CommonMiddleware runs before this one on the way out and has already set
        # Content-Length for the old body; a stale value truncates the response.
        if response.has_header("Content-Length"):
            response["Content-Length"] = str(len(response.content))
        return response
