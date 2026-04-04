def mobile_only_schema_endpoints(endpoints, **kwargs):
    allowed_prefixes = (
        "/api/mobile/",
        "/api/user/auth/login/",
        "/api/user/auth/verify-otp/",
        "/api/user/reset-password/",
        "/api/auth/token/refresh/",
        "/api/schema/",
        "/api/docs/swagger/",
        "/api/docs/redoc/",
    )

    filtered = []
    for path, path_regex, method, callback in endpoints:
        if path.startswith(allowed_prefixes):
            filtered.append((path, path_regex, method, callback))
    return filtered


def mobile_schema_sort_key(endpoint):
    path, _path_regex, method, _callback = endpoint

    priority = {
        ("/api/mobile/topic-list/", "GET"): 0,
        ("/api/mobile/categories/{id}/", "GET"): 1,
        ("/api/mobile/kpis/{id}/", "GET"): 2,
        ("/api/mobile/indicator-detail/{id}/", "GET"): 3,
    }
    export_paths = {
        "/api/mobile/export-topic-data/{id}/",
        "/api/mobile/export-category-data/{id}/",
        "/api/mobile/export-indicator-data/{id}/",
    }

    method_rank = {
        "GET": 0,
        "POST": 1,
        "PUT": 2,
        "PATCH": 3,
        "DELETE": 4,
    }

    return (
        priority.get((path, method), 100),
        1 if path in export_paths else 0,
        path,
        method_rank.get(method, 99),
        method,
    )
