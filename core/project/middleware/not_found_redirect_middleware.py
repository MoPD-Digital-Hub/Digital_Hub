from django.shortcuts import redirect


class NotFoundRedirectMiddleware:
    """
    Redirect browser page 404s to the dashboard home.

    API, admin, media, and static 404s should keep their normal response.
    """

    EXCLUDED_PREFIXES = (
        "/api/",
        "/admin/",
        "/media/",
        "/static/",
        "/oidc/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if response.status_code != 404:
            return response

        if request.method != "GET":
            return response

        if any(request.path.startswith(prefix) for prefix in self.EXCLUDED_PREFIXES):
            return response

        accepts_html = "text/html" in request.headers.get("Accept", "")
        is_browser_navigation = not request.headers.get("X-Requested-With")
        if not (accepts_html and is_browser_navigation):
            return response

        return redirect("dashboard_home")
