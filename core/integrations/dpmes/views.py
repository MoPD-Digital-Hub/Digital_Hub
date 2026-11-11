from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from integrations.dpmes import client as dpmes_client
from integrations.dpmes import compat as dpmes_compat
from project.responses import failure, success


def _org_id(request, *keys):
    """First organization id named in the query, else the API key's own org.

    Goal and KPI data is organization-scoped in DPMES; without an org the
    pages get the national (key-level) view, which matches the old behaviour.
    """
    for key in keys:
        value = request.query_params.get(key)
        if value not in (None, "", "all"):
            return value
    return dpmes_client.key_organization_id()


def _goal_detail_response(request, goal_id, org_keys):
    try:
        period = dpmes_compat.build_period(request.query_params)
        org_id = _org_id(request, *org_keys)
        kras = dpmes_client.goal_kras(goal_id, org_id, period)
        scorecard = dpmes_client.organization_scorecard(org_id, period)
        ranges = dpmes_client.score_ranges()
    except dpmes_client.DPMES2Error as exc:
        return failure(request, str(exc), status.HTTP_502_BAD_GATEWAY)

    goal_score = dpmes_compat.find_goal_score(scorecard, goal_id)
    return success(request, dpmes_compat.goal_detail(kras or {}, ranges or [], goal_score), message="")

@extend_schema(exclude=True)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def policy_areas(request):
    """Policy areas with their weighted score for the requested period."""
    try:
        period = dpmes_compat.build_period(request.query_params)
        rows = dpmes_client.policy_area_scores(period)
    except dpmes_client.DPMES2Error as exc:
        return failure(request, str(exc), status.HTTP_502_BAD_GATEWAY)

    return success(request, dpmes_compat.map_rows(rows, dpmes_compat.policy_area), message="")

@extend_schema(exclude=True)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def policy_area_detail(request, id):
    """A policy area's score and its goals for the requested period."""
    try:
        period = dpmes_compat.build_period(request.query_params)
        data = dpmes_client.policy_area_scorecard(id, period)
    except dpmes_client.DPMES2Error as exc:
        return failure(request, str(exc), status.HTTP_502_BAD_GATEWAY)
    return success(request, dpmes_compat.policy_area_detail(data or {}), message="")


@extend_schema(exclude=True)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def goal_detail(request, id):
    """A goal's KRAs and KPIs, at national scope unless an org is named."""
    return _goal_detail_response(request, id, ("org", "org_id", "ministry_id"))


@extend_schema(exclude=True)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def all_ministries(request):
    """Public bodies under the API key's organization, with their scores."""
    try:
        period = dpmes_compat.build_period(request.query_params)
        rows = dpmes_client.child_organizations(period)
    except dpmes_client.DPMES2Error as exc:
        return failure(request, str(exc), status.HTTP_502_BAD_GATEWAY)

    return success(request, dpmes_compat.map_rows(rows, dpmes_compat.ministry), message="")
    


@extend_schema(exclude=True)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ministry_detail(request, id):
    """An organization's policy areas, each with its goals and scores."""
    try:
        period = dpmes_compat.build_period(request.query_params)
        data = dpmes_client.organization_scorecard(id, period)
    except dpmes_client.DPMES2Error as exc:
        return failure(request, str(exc), status.HTTP_502_BAD_GATEWAY)
    return success(request, dpmes_compat.organization_policy_areas(data or {}), message="")


@extend_schema(exclude=True)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ministry_goal_detail(request, id):
    """A goal's KRAs and KPIs for the organization named in the query."""
    return _goal_detail_response(request, id, ("org_id", "ministry_id", "org"))


@extend_schema(exclude=True)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ministry_performance(request, id):
    """An organization's KPIs grouped into the legacy performance buckets."""
    try:
        period = dpmes_compat.build_period(request.query_params)
        rows = dpmes_client.kpis_by_score_range(id, period)
    except dpmes_client.DPMES2Error as exc:
        return failure(request, str(exc), status.HTTP_502_BAD_GATEWAY)
    return Response(dpmes_compat.organization_performance(rows), status=status.HTTP_200_OK)


@extend_schema(exclude=True)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def affiliated_ministries(request):
    """An organization and the organizations directly under it, with scores.

    DPMES only lists the key's direct children, so a ministry's own
    sub-agencies appear only if DPMES places them at that level. `solo=true`
    returns just the named organization.
    """
    ministry_id = request.query_params.get("ministry_id")
    solo = request.query_params.get("solo") == "true"
    try:
        period = dpmes_compat.build_period(request.query_params)
        rows = dpmes_client.child_organizations(period)
    except dpmes_client.DPMES2Error as exc:
        return failure(request, str(exc), status.HTTP_502_BAD_GATEWAY)

    mapped = dpmes_compat.map_rows(rows, dpmes_compat.ministry)
    if ministry_id:
        mapped = [
            row for row in mapped
            if str(row["id"]) == str(ministry_id)
            or (not solo and str(row.get("parent")) == str(ministry_id))
        ]
    return success(request, mapped, message="")


@extend_schema(exclude=True)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def indicator_detail(request, id):
    """A KPI with all its yearly and quarterly records for an organization."""
    try:
        org_id = _org_id(request, "org", "org_id", "ministry_id")
        data = dpmes_client.kpi_detail(id, org_id)
    except dpmes_client.DPMES2Error as exc:
        return failure(request, str(exc), status.HTTP_502_BAD_GATEWAY)
    if not isinstance(data, dict):
        return failure(request, "KPI_NOT_FOUND", status.HTTP_404_NOT_FOUND)
    return success(request, dpmes_compat.indicator(data), message="")


@extend_schema(exclude=True)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def year_lists(request):
    """Selectable Ethiopian years, newest first.

    DPMES publishes the span it holds data for; we stop at the current year
    so the filter never offers a future period.
    """
    try:
        date = dpmes_client.server_date()
        current = dpmes_client.current_ethiopian_year()
    except (dpmes_client.DPMES2Error, KeyError, ValueError) as exc:
        return failure(request, str(exc), status.HTTP_502_BAD_GATEWAY)

    first = int(date.get("ethio_min_year") or current)
    last = min(int(date.get("ethio_max_year") or current), current)

    years = [
        {
            "year_eng": year,
            "year_amh": year,
            "is_current_year": year == current,
        }
        for year in range(last, first - 1, -1)
    ]
    return Response({"years": years}, status=status.HTTP_200_OK)
    

@extend_schema(exclude=True)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def time_frame(request):
    """Period the scorecards open on: the last completed Ethiopian year.

    DPMES no longer publishes a default reporting period, so we pick one. The
    current year is only partly reported for most of its length, which would
    open every scorecard on near-zero scores, so we step back to the last year
    that is complete and show its final quarter.
    """
    try:
        current = dpmes_client.current_ethiopian_year()
    except (dpmes_client.DPMES2Error, KeyError, ValueError) as exc:
        return failure(request, str(exc), status.HTTP_502_BAD_GATEWAY)

    return success(request, {
                "year": current - 1,
                "quarter": "12month",
                "is_quarter": False,
            }, message="")
