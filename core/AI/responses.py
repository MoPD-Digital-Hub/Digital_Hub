from rest_framework import status
from rest_framework.response import Response


def request_id_for(request):
    return getattr(request, "request_id", None)


def ok(request, data=None, message="SUCCESS", status_code=status.HTTP_200_OK):
    return Response(
        {
            "result": "SUCCESS",
            "message": message,
            "request_id": request_id_for(request),
            "data": data,
        },
        status=status_code,
    )


def error(request, code, detail, status_code, details=None):
    return Response(
        {
            "result": "FAILURE",
            "message": code,
            "request_id": request_id_for(request),
            "error": {
                "code": code,
                "message": detail,
                "details": details or {},
            },
            "data": None,
        },
        status=status_code,
    )
