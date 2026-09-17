import requests
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from mobile.api.dpmes_api import DPMES_URL


def _envelope(result, message, data, status_code):
    return Response({"result": result, "message": message, "data": data}, status=status_code)


def _fetch_dpmes(path, params):
    """Fetch a DPMES endpoint and unwrap its {result, data} envelope."""
    response = requests.get(f"{DPMES_URL}{path}", params=params, timeout=10)
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def organization_overview(request):
    """Overview of the requesting user's organization: the local ministry
    record combined with its DPMES detail and performance data."""
    ministry = getattr(request.user, "ministry", None)
    if ministry is None:
        return _envelope(
            "FAILURE", "NO_MINISTRY",
            None, status.HTTP_400_BAD_REQUEST,
        )
    if ministry.external_id is None:
        return _envelope(
            "FAILURE", "MINISTRY_NOT_LINKED",
            None, status.HTTP_400_BAD_REQUEST,
        )

    params = request.query_params.dict()
    try:
        detail = _fetch_dpmes(f"/api/digital-hub/ministry-detail/{ministry.external_id}/", params)
        performance = _fetch_dpmes(f"/api/digital-hub/ministry-performance/{ministry.external_id}/", params)
    except (requests.exceptions.RequestException, ValueError) as exc:
        return _envelope(
            "FAILURE", f"Failed to reach DPMES service: {exc}",
            None, status.HTTP_502_BAD_GATEWAY,
        )

    return _envelope(
        "SUCCESS", "SUCCESS",
        {
            "ministry": {
                "id": ministry.id,
                "name": ministry.name,
                "name_am": ministry.name_am,
                "abbreviation": ministry.abbreviation,
                "image": ministry.image,
                "external_id": ministry.external_id,
            },
            "detail": detail,
            "performance": performance,
        },
        status.HTTP_200_OK,
    )
