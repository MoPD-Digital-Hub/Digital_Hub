from django.db import IntegrityError, transaction
from django.db.models import Max
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from preferences import dashboard as dashboard_data
from preferences import sources
from preferences.models import Follow, UserPreference
from project.responses import failure, success

from .serializers import (
    FollowCreateSerializer,
    FollowOrderSerializer,
    FollowSerializer,
    PreferenceSerializer,
)

TAG = ["Preferences"]


def _upstream_failure(request, exc):
    unavailable = exc.code == "DPMES2_NOT_CONFIGURED"
    return failure(
        request, exc.code,
        status.HTTP_503_SERVICE_UNAVAILABLE if unavailable else status.HTTP_502_BAD_GATEWAY,
        error_message=str(exc),
    )


def _choice(request, name, choices, default):
    """A query parameter limited to `choices`; (value, None) or (None, error response)."""
    value = request.query_params.get(name) or default
    if value not in choices:
        return None, failure(request, "INVALID_INPUT", status.HTTP_400_BAD_REQUEST,
                             details={name: [f"Must be one of: {', '.join(choices)}."]})
    return value, None


@extend_schema(methods=["GET"], summary="Get my dashboard preferences", tags=TAG, responses=PreferenceSerializer)
@extend_schema(methods=["PUT", "PATCH"], summary="Change my dashboard preferences", tags=TAG,
               description="Send only the fields to change. `sections` replaces the saved order.",
               request=PreferenceSerializer, responses=PreferenceSerializer)
@api_view(["GET", "PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def preferences(request):
    preference = dashboard_data.preference_for(request.user)
    if request.method == "GET":
        return success(request, PreferenceSerializer(preference).data)

    serializer = PreferenceSerializer(preference, data=request.data, partial=True)
    if not serializer.is_valid():
        return failure(request, "INVALID_INPUT", status.HTTP_400_BAD_REQUEST, details=serializer.errors)
    serializer.save(user=request.user)
    return success(request, serializer.data, message="PREFERENCES_SAVED")


@extend_schema(methods=["GET"], summary="List what I follow", tags=TAG, responses=FollowSerializer(many=True),
               parameters=[OpenApiParameter("kind", str, enum=Follow.KINDS, description="Only this kind.")])
@extend_schema(methods=["POST"], summary="Follow an organization, policy area, KPI or indicator", tags=TAG,
               description="`id` is the item's id from `/api/preferences/options/`. A KPI also takes the "
                           "`organization_id` whose results to show (default: the user's own organization). "
                           "Following something already followed returns the existing record.",
               request=FollowCreateSerializer, responses=FollowSerializer)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def follows(request):
    queryset = Follow.objects.filter(user=request.user)
    if request.method == "GET":
        kind = request.query_params.get("kind")
        if kind:
            queryset = queryset.filter(kind=kind)
        return success(request, FollowSerializer(queryset, many=True).data)

    serializer = FollowCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return failure(request, "INVALID_INPUT", status.HTTP_400_BAD_REQUEST, details=serializer.errors)
    kind = serializer.validated_data["kind"]

    try:
        item = dashboard_data.resolve(
            request.user, kind, serializer.validated_data["id"], serializer.validated_data["organization_id"],
        )
    except sources.SourceError as exc:
        return _upstream_failure(request, exc)
    if item is None:
        return failure(request, "ITEM_NOT_FOUND", status.HTTP_404_NOT_FOUND,
                       error_message="No such item in its source service.")

    same_kind = queryset.filter(kind=kind)
    existing = same_kind.filter(external_id=item["id"], organization_id=item["organization_id"]).first()
    if existing:
        return success(request, FollowSerializer(existing).data, message="ALREADY_FOLLOWED")
    if same_kind.count() >= Follow.LIMIT_PER_KIND:
        return failure(request, "FOLLOW_LIMIT_REACHED", status.HTTP_400_BAD_REQUEST,
                       error_message=f"You can follow at most {Follow.LIMIT_PER_KIND} of one kind.")

    last = same_kind.aggregate(last=Max("position"))["last"]
    try:
        with transaction.atomic():
            follow = Follow.objects.create(
                user=request.user, kind=kind, external_id=item["id"], organization_id=item["organization_id"],
                name=item["name"][:500], name_am=item.get("name_am", "")[:500], code=item.get("code", "")[:64],
                position=0 if last is None else last + 1,
            )
    except IntegrityError:
        # Two requests for the same item at once: the other one created it.
        follow = same_kind.get(external_id=item["id"], organization_id=item["organization_id"])
    return success(request, FollowSerializer(follow).data, message="FOLLOWED", status=status.HTTP_201_CREATED)


@extend_schema(summary="Stop following an item", tags=TAG, responses=None)
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def follow_detail(request, follow_id):
    deleted, _ = Follow.objects.filter(user=request.user, pk=follow_id).delete()
    if not deleted:
        return failure(request, "FOLLOW_NOT_FOUND", status.HTTP_404_NOT_FOUND)
    return success(request, None, message="UNFOLLOWED")


@extend_schema(summary="Reorder what I follow", tags=TAG, request=FollowOrderSerializer,
               description="`follow_ids` in the wanted order; any follows of the kind left out keep their "
                           "order after the listed ones.",
               responses=FollowSerializer(many=True))
@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def follow_order(request):
    serializer = FollowOrderSerializer(data=request.data)
    if not serializer.is_valid():
        return failure(request, "INVALID_INPUT", status.HTTP_400_BAD_REQUEST, details=serializer.errors)
    kind, wanted = serializer.validated_data["kind"], serializer.validated_data["follow_ids"]

    rows = {row.pk: row for row in Follow.objects.filter(user=request.user, kind=kind)}
    if len(set(wanted)) != len(wanted) or any(pk not in rows for pk in wanted):
        return failure(request, "INVALID_INPUT", status.HTTP_400_BAD_REQUEST,
                       details={"follow_ids": ["Must be your own follows of this kind, each listed once."]})

    listed = set(wanted)
    order = wanted + [pk for pk in rows if pk not in listed]  # rows is already in the current order
    for position, pk in enumerate(order):
        rows[pk].position = position
    Follow.objects.bulk_update(rows.values(), ["position"])
    return success(request, FollowSerializer([rows[pk] for pk in order], many=True).data, message="ORDER_SAVED")


@extend_schema(
    summary="Search items I can follow", tags=TAG,
    responses=OpenApiTypes.OBJECT,
    parameters=[
        OpenApiParameter("kind", str, enum=Follow.KINDS, required=True),
        OpenApiParameter("search", str, description="Words to match in the name or code. Indicators need "
                                                    "at least two characters and return nothing without it."),
        OpenApiParameter("organization", str, description="KPIs only: the organization whose KPIs to list "
                                                          "(default: the user's own)."),
    ],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def options(request):
    kind, error = _choice(request, "kind", Follow.KINDS, None)
    if error:
        return error
    try:
        rows = dashboard_data.options(
            request.user, list(Follow.objects.filter(user=request.user, kind=kind)), kind,
            search=request.query_params.get("search", ""), organization=request.query_params.get("organization"),
        )
    except sources.SourceError as exc:
        return _upstream_failure(request, exc)
    return success(request, rows)


@extend_schema(summary="My personal dashboard", tags=TAG, responses=OpenApiTypes.OBJECT,
               description="Everything the home screen needs in one call: the sections in the user's order, "
                           "the organizations, policy areas, KPIs and indicators they follow with scores and "
                           "change since the previous period, the biggest movers, and items needing attention. "
                           "A section that could not be loaded is listed under `errors`; the rest is returned.")
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard(request):
    return success(request, dashboard_data.build(request.user))


@extend_schema(
    summary="Biggest rises and falls in score", tags=TAG,
    responses=OpenApiTypes.OBJECT,
    description="Compares the two latest periods. Parameters default to the user's saved preferences.",
    parameters=[
        OpenApiParameter("kind", str, enum=dashboard_data.MOVER_KINDS, description="Default: kpi."),
        OpenApiParameter("period", str, enum=["quarter", "year"]),
        OpenApiParameter("direction", str, enum=["both", "rising", "declining"]),
        OpenApiParameter("scope", str, enum=["all", "following"]),
        OpenApiParameter("limit", int, description="1 to 50."),
        OpenApiParameter("organization", str, description="KPIs and categories: only this organization "
                                                          "(default: the organizations the user follows)."),
    ],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def movers(request):
    preference = dashboard_data.preference_for(request.user)
    checks = (
        ("kind", dashboard_data.MOVER_KINDS, "kpi"),
        ("period", [value for value, _ in UserPreference.PERIOD_CHOICES], preference.period),
        ("direction", [value for value, _ in UserPreference.DIRECTION_CHOICES], preference.movers_direction),
        ("scope", [value for value, _ in UserPreference.SCOPE_CHOICES], preference.movers_scope),
    )
    values = {}
    for name, choices, default in checks:
        values[name], error = _choice(request, name, choices, default)
        if error:
            return error
    try:
        limit = int(request.query_params.get("limit") or preference.movers_limit)
    except ValueError:
        limit = 0
    if not 1 <= limit <= 50:
        return failure(request, "INVALID_INPUT", status.HTTP_400_BAD_REQUEST,
                       details={"limit": ["Must be a number from 1 to 50."]})

    try:
        data = dashboard_data.movers(
            request.user, list(Follow.objects.filter(user=request.user)), limit=limit,
            organization=request.query_params.get("organization"), **values,
        )
    except sources.SourceError as exc:
        return _upstream_failure(request, exc)
    return success(request, data)
