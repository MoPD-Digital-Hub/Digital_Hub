from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from integrations.dpmes import client as dpmes_client
from project.responses import failure, success


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def organization_overview(request):
    """Overview of the requesting user's organization from DPMES2: the
    local ministry record, its scorecard by policy area and goal (detail),
    and its score plus KPI distribution across score bands (performance).

    Query params: year (Ethiopian calendar, defaults to the current year),
    quarter (1-4), month (1-12), plan — passed through to DPMES2.
    """
    ministry = getattr(request.user, "ministry", None)
    if ministry is None:
        return failure(request, "NO_MINISTRY", status.HTTP_400_BAD_REQUEST)
    if ministry.dpmes2_id is None:
        return failure(request, "MINISTRY_NOT_LINKED", status.HTTP_400_BAD_REQUEST)
    if not dpmes_client.is_configured():
        return failure(request, "DPMES2_NOT_CONFIGURED", status.HTTP_503_SERVICE_UNAVAILABLE)

    try:
        period = dpmes_client.period_from_query(request.query_params)
        scorecard = dpmes_client.organization_scorecard(ministry.dpmes2_id, period)
        ranges = dpmes_client.score_ranges()
    except dpmes_client.DPMES2Error as exc:
        return failure(request, str(exc), status.HTTP_502_BAD_GATEWAY)

    return success(request, {
            "ministry": {
                "id": ministry.id,
                "name": ministry.name,
                "name_am": ministry.name_am,
                "abbreviation": ministry.abbreviation,
                "image": ministry.image,
                "external_id": ministry.external_id,
                "dpmes2_id": ministry.dpmes2_id,
            },
            "period": period,
            "detail": {
                "organization": {
                    "id": scorecard.get("id"),
                    "name": scorecard.get("name"),
                    "name_eth": scorecard.get("name_eth"),
                    "code": scorecard.get("code"),
                    "icon": scorecard.get("icon"),
                },
                "policy_areas": scorecard.get("policy_areas", []),
            },
            "performance": {
                "score": scorecard.get("score"),
                "performance_analysis": scorecard.get("performance_analysis", {}),
                "score_ranges": ranges,
            },
        }, message="SUCCESS", status=status.HTTP_200_OK)
