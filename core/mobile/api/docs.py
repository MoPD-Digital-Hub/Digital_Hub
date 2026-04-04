from rest_framework import serializers
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
)


class SuccessEnvelopeSerializer(serializers.Serializer):
    result = serializers.CharField()
    message = serializers.CharField()
    data = serializers.JSONField()


class ErrorEnvelopeSerializer(serializers.Serializer):
    detail = serializers.CharField()


class UpdateCheckDataSerializer(serializers.Serializer):
    force_update = serializers.BooleanField()
    optional_update = serializers.BooleanField()
    latest_version = serializers.CharField()
    message = serializers.CharField(allow_blank=True)


class UpdateCheckResponseSerializer(serializers.Serializer):
    result = serializers.CharField()
    message = serializers.CharField()
    data = UpdateCheckDataSerializer()


class TopicListItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    count_category = serializers.IntegerField()
    count_kpis = serializers.IntegerField()
    title_ENG = serializers.CharField()
    title_AMH = serializers.CharField()
    is_dashboard = serializers.BooleanField()
    is_mobile_dashaboard_overview = serializers.BooleanField()
    rank = serializers.IntegerField()
    icon = serializers.CharField(allow_blank=True)
    image = serializers.CharField()
    image_icons = serializers.CharField()
    background_image = serializers.CharField()
    is_initiative = serializers.BooleanField()
    description = serializers.CharField(allow_blank=True)
    updated = serializers.DateTimeField()
    created = serializers.DateTimeField()


class TopicListResponseSerializer(serializers.Serializer):
    result = serializers.CharField()
    message = serializers.CharField()
    data = TopicListItemSerializer(many=True)


class TimeSeriesErrorResponseSerializer(serializers.Serializer):
    result = serializers.CharField()
    message = serializers.CharField()
    data = serializers.ListField(child=serializers.JSONField(), allow_empty=True)


class CategoryListItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name_ENG = serializers.CharField()
    name_AMH = serializers.CharField()
    code = serializers.CharField()
    is_reginal = serializers.BooleanField()
    is_dashboard_visible = serializers.BooleanField()
    rank = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    is_deleted = serializers.BooleanField()
    topic = serializers.IntegerField()


class CategoryListResponseSerializer(serializers.Serializer):
    result = serializers.CharField()
    message = serializers.CharField()
    data = CategoryListItemSerializer(many=True)


class IndicatorDataPointSerializer(serializers.Serializer):
    for_datapoint = serializers.CharField()
    target = serializers.FloatField(allow_null=True)
    performance = serializers.FloatField(allow_null=True)


class IndicatorCategoryNameSerializer(serializers.Serializer):
    name_ENG = serializers.CharField()


class IndicatorDetailChildSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    annual_data = IndicatorDataPointSerializer(many=True)
    quarter_data = IndicatorDataPointSerializer(many=True)
    month_data = IndicatorDataPointSerializer(many=True)
    week_data = IndicatorDataPointSerializer(many=True)
    day_data = IndicatorDataPointSerializer(many=True)
    latest_data = serializers.CharField(allow_blank=True, allow_null=True)
    children = serializers.ListField(child=serializers.JSONField(), allow_empty=True)
    title_ENG = serializers.CharField()
    title_AMH = serializers.CharField()
    code = serializers.CharField(allow_blank=True, allow_null=True)
    rank = serializers.IntegerField()
    description = serializers.CharField(allow_blank=True, allow_null=True)
    measurement_units = serializers.CharField(allow_blank=True, allow_null=True)
    measurement_units_quarter = serializers.CharField(allow_blank=True, allow_null=True)
    measurement_units_month = serializers.CharField(allow_blank=True, allow_null=True)
    frequency = serializers.CharField(allow_blank=True, allow_null=True)
    source = serializers.CharField(allow_blank=True, allow_null=True)
    methodology = serializers.CharField(allow_blank=True, allow_null=True)
    disaggregation_dimensions = serializers.CharField(allow_blank=True, allow_null=True)
    data_type = serializers.CharField(allow_blank=True, allow_null=True)
    responsible_entity = serializers.CharField(allow_blank=True, allow_null=True)
    tags = serializers.CharField(allow_blank=True, allow_null=True)
    sdg_link = serializers.CharField(allow_blank=True, allow_null=True)
    status = serializers.CharField(allow_blank=True, allow_null=True)
    version = serializers.IntegerField(allow_null=True)
    collection_Instrument = serializers.CharField(allow_blank=True, allow_null=True)
    kpi_characteristics = serializers.CharField(allow_blank=True, allow_null=True)
    is_dashboard_visible = serializers.BooleanField()
    is_public = serializers.BooleanField()
    is_verified = serializers.BooleanField()
    main_parent = serializers.BooleanField()
    image = serializers.CharField(allow_blank=True, allow_null=True)
    created_at = serializers.DateTimeField(allow_null=True)
    updated_at = serializers.DateTimeField(allow_null=True)
    time_coverage_start_year = serializers.IntegerField(allow_null=True)
    time_coverage_end_year = serializers.IntegerField(allow_null=True)
    parent = serializers.IntegerField(allow_null=True)
    for_category = serializers.ListField(child=serializers.IntegerField())


class IndicatorDetailItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    annual_data = IndicatorDataPointSerializer(many=True)
    quarter_data = IndicatorDataPointSerializer(many=True)
    month_data = IndicatorDataPointSerializer(many=True)
    week_data = IndicatorDataPointSerializer(many=True)
    day_data = IndicatorDataPointSerializer(many=True)
    latest_data = serializers.CharField(allow_blank=True, allow_null=True)
    children = IndicatorDetailChildSerializer(many=True)
    title_ENG = serializers.CharField()
    title_AMH = serializers.CharField()
    code = serializers.CharField(allow_blank=True, allow_null=True)
    rank = serializers.IntegerField()
    description = serializers.CharField(allow_blank=True, allow_null=True)
    measurement_units = serializers.CharField(allow_blank=True, allow_null=True)
    measurement_units_quarter = serializers.CharField(allow_blank=True, allow_null=True)
    measurement_units_month = serializers.CharField(allow_blank=True, allow_null=True)
    frequency = serializers.CharField(allow_blank=True, allow_null=True)
    source = serializers.CharField(allow_blank=True, allow_null=True)
    methodology = serializers.CharField(allow_blank=True, allow_null=True)
    disaggregation_dimensions = serializers.CharField(allow_blank=True, allow_null=True)
    data_type = serializers.CharField(allow_blank=True, allow_null=True)
    responsible_entity = serializers.CharField(allow_blank=True, allow_null=True)
    tags = serializers.CharField(allow_blank=True, allow_null=True)
    sdg_link = serializers.CharField(allow_blank=True, allow_null=True)
    status = serializers.CharField(allow_blank=True, allow_null=True)
    version = serializers.IntegerField(allow_null=True)
    collection_Instrument = serializers.CharField(allow_blank=True, allow_null=True)
    kpi_characteristics = serializers.CharField(allow_blank=True, allow_null=True)
    is_dashboard_visible = serializers.BooleanField()
    is_public = serializers.BooleanField()
    is_verified = serializers.BooleanField()
    main_parent = serializers.BooleanField()
    image = serializers.CharField(allow_blank=True, allow_null=True)
    created_at = serializers.DateTimeField(allow_null=True)
    updated_at = serializers.DateTimeField(allow_null=True)
    time_coverage_start_year = serializers.IntegerField(allow_null=True)
    time_coverage_end_year = serializers.IntegerField(allow_null=True)
    parent = serializers.IntegerField(allow_null=True)
    for_category = serializers.ListField(child=serializers.IntegerField())


class IndicatorDetailObjectSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    annual_data = IndicatorDataPointSerializer(many=True)
    quarter_data = IndicatorDataPointSerializer(many=True)
    month_data = IndicatorDataPointSerializer(many=True)
    week_data = IndicatorDataPointSerializer(many=True)
    day_data = IndicatorDataPointSerializer(many=True)
    for_category = IndicatorCategoryNameSerializer(many=True)
    latest_data = serializers.CharField(allow_blank=True, allow_null=True)
    children = IndicatorDetailChildSerializer(many=True)
    title_ENG = serializers.CharField()
    title_AMH = serializers.CharField()
    code = serializers.CharField(allow_blank=True, allow_null=True)
    rank = serializers.IntegerField()
    description = serializers.CharField(allow_blank=True, allow_null=True)
    measurement_units = serializers.CharField(allow_blank=True, allow_null=True)
    measurement_units_quarter = serializers.CharField(allow_blank=True, allow_null=True)
    measurement_units_month = serializers.CharField(allow_blank=True, allow_null=True)
    frequency = serializers.CharField(allow_blank=True, allow_null=True)
    source = serializers.CharField(allow_blank=True, allow_null=True)
    methodology = serializers.CharField(allow_blank=True, allow_null=True)
    disaggregation_dimensions = serializers.CharField(allow_blank=True, allow_null=True)
    data_type = serializers.CharField(allow_blank=True, allow_null=True)
    responsible_entity = serializers.CharField(allow_blank=True, allow_null=True)
    tags = serializers.CharField(allow_blank=True, allow_null=True)
    sdg_link = serializers.CharField(allow_blank=True, allow_null=True)
    status = serializers.CharField(allow_blank=True, allow_null=True)
    version = serializers.IntegerField(allow_null=True)
    collection_Instrument = serializers.CharField(allow_blank=True, allow_null=True)
    kpi_characteristics = serializers.CharField(allow_blank=True, allow_null=True)
    is_dashboard_visible = serializers.BooleanField()
    is_public = serializers.BooleanField()
    is_verified = serializers.BooleanField()
    main_parent = serializers.BooleanField()
    image = serializers.CharField(allow_blank=True, allow_null=True)
    created_at = serializers.DateTimeField(allow_null=True)
    updated_at = serializers.DateTimeField(allow_null=True)
    time_coverage_start_year = serializers.IntegerField(allow_null=True)
    time_coverage_end_year = serializers.IntegerField(allow_null=True)
    parent = serializers.IntegerField(allow_null=True)


class IndicatorDetailResponseSerializer(serializers.Serializer):
    result = serializers.CharField()
    message = serializers.CharField()
    data = IndicatorDetailObjectSerializer()


class HighFrequencyIndicatorSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title_ENG = serializers.CharField()
    code = serializers.CharField(allow_blank=True, allow_null=True)
    measurement_units = serializers.CharField(allow_blank=True, allow_null=True)
    measurement_units_quarter = serializers.CharField(allow_blank=True, allow_null=True)
    measurement_units_month = serializers.CharField(allow_blank=True, allow_null=True)
    latest_data = serializers.CharField(allow_blank=True, allow_null=True)
    annual_data = serializers.ListField(child=serializers.JSONField(), allow_empty=True)
    quarter_data = serializers.ListField(child=serializers.JSONField(), allow_empty=True)
    month_data = serializers.ListField(child=serializers.JSONField(), allow_empty=True)
    children = serializers.ListField(child=serializers.JSONField(), allow_empty=True)
    kpi_characteristics = serializers.CharField(allow_blank=True, allow_null=True)


class HighFrequencyItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    indicator = HighFrequencyIndicatorSerializer()
    year = serializers.CharField(allow_blank=True, allow_null=True)
    quarter = serializers.CharField(allow_blank=True, allow_null=True)
    month = serializers.CharField(allow_blank=True, allow_null=True)
    row = serializers.IntegerField()
    chart_type = serializers.CharField(allow_blank=True, allow_null=True)
    width = serializers.IntegerField()
    include_children = serializers.BooleanField()


class HighFrequencyResponseSerializer(serializers.Serializer):
    result = serializers.CharField()
    message = serializers.CharField(allow_blank=True)
    data = serializers.ListField(
        child=serializers.ListSerializer(child=HighFrequencyItemSerializer()),
        allow_empty=True,
    )


class MonthListItemSerializer(serializers.Serializer):
    month_AMH = serializers.CharField()


class MonthListResponseSerializer(serializers.Serializer):
    result = serializers.CharField()
    message = serializers.CharField()
    data = MonthListItemSerializer(many=True)


class YearListItemSerializer(serializers.Serializer):
    year_EC = serializers.IntegerField()


class YearListResponseSerializer(serializers.Serializer):
    result = serializers.CharField()
    message = serializers.CharField()
    data = YearListItemSerializer(many=True)


TOPIC_LIST_RESPONSE_EXAMPLE = OpenApiExample(
    "Topic list success response",
    value={
        "result": "string",
        "message": "string",
        "data": [
            {
                "id": 0,
                "count_category": 0,
                "count_kpis": 0,
                "title_ENG": "string",
                "title_AMH": "string",
                "is_dashboard": True,
                "is_mobile_dashaboard_overview": True,
                "rank": 0,
                "icon": "string",
                "image": "string",
                "image_icons": "string",
                "background_image": "string",
                "is_initiative": False,
                "description": "string",
                "updated": "2025-01-01T00:00:00Z",
                "created": "2025-01-01T00:00:00Z",
            }
        ],
    },
    response_only=True,
)


TOPIC_LIST_ERROR_EXAMPLE = OpenApiExample(
    "Topic list error response",
    value={
        "result": "ERROR",
        "message": "string",
        "data": [],
    },
    response_only=True,
    status_codes=["400"],
)


TIME_SERIES_ERROR_EXAMPLE = OpenApiExample(
    "Time series error response",
    value={
        "result": "ERROR",
        "message": "string",
        "data": [],
    },
    response_only=True,
    status_codes=["400"],
)


CATEGORY_LIST_RESPONSE_EXAMPLE = OpenApiExample(
    "Category list success response",
    value={
        "result": "string",
        "message": "string",
        "data": [
            {
                "id": 0,
                "name_ENG": "string",
                "name_AMH": "string",
                "code": "string",
                "is_reginal": False,
                "is_dashboard_visible": True,
                "rank": 0,
                "created_at": "2025-01-01T00:00:00Z",
                "is_deleted": False,
                "topic": 0,
            }
        ],
    },
    response_only=True,
)


INDICATOR_DETAIL_RESPONSE_EXAMPLE = OpenApiExample(
    "Indicator detail success response",
    value={
        "result": "string",
        "message": "string",
        "data": {
            "id": 0,
            "annual_data": [
                {
                    "for_datapoint": "string",
                    "target": 0.0,
                    "performance": 0.0,
                }
            ],
            "quarter_data": [],
            "month_data": [],
            "week_data": [],
            "day_data": [],
            "for_category": [
                {
                    "name_ENG": "string",
                }
            ],
            "latest_data": "string",
            "children": [
                {
                    "id": 0,
                    "annual_data": [
                        {
                            "for_datapoint": "string",
                            "target": 0.0,
                            "performance": 0.0,
                        }
                    ],
                    "quarter_data": [],
                    "month_data": [],
                    "week_data": [],
                    "day_data": [],
                    "latest_data": "string",
                    "children": [],
                    "title_ENG": "string",
                    "title_AMH": "string",
                    "code": "string",
                    "rank": 0,
                    "description": "string",
                    "measurement_units": "string",
                    "measurement_units_quarter": "string",
                    "measurement_units_month": "string",
                    "frequency": "string",
                    "source": "string",
                    "methodology": "string",
                    "disaggregation_dimensions": "string",
                    "data_type": "string",
                    "responsible_entity": "string",
                    "tags": "string",
                    "sdg_link": "string",
                    "status": "string",
                    "version": 0,
                    "collection_Instrument": "string",
                    "kpi_characteristics": "string",
                    "is_dashboard_visible": True,
                    "is_public": True,
                    "is_verified": True,
                    "main_parent": False,
                    "image": "string",
                    "created_at": "2025-01-01T00:00:00Z",
                    "updated_at": "2025-01-01T00:00:00Z",
                    "time_coverage_start_year": 0,
                    "time_coverage_end_year": 0,
                    "parent": 0,
                    "for_category": [0],
                }
            ],
            "title_ENG": "string",
            "title_AMH": "string",
            "code": "string",
            "rank": 0,
            "description": "string",
            "measurement_units": "string",
            "measurement_units_quarter": "string",
            "measurement_units_month": "string",
            "frequency": "string",
            "source": "string",
            "methodology": "string",
            "disaggregation_dimensions": "string",
            "data_type": "string",
            "responsible_entity": "string",
            "tags": "string",
            "sdg_link": "string",
            "status": "string",
            "version": 0,
            "collection_Instrument": "string",
            "kpi_characteristics": "string",
            "is_dashboard_visible": True,
            "is_public": True,
            "is_verified": True,
            "main_parent": False,
            "image": "string",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
            "time_coverage_start_year": 0,
            "time_coverage_end_year": 0,
            "parent": 0,
        },
    },
    response_only=True,
)


HIGH_FREQUENCY_RESPONSE_EXAMPLE = OpenApiExample(
    "High frequency success response",
    value={
        "result": "string",
        "message": "string",
        "data": [
            [
                {
                    "id": 0,
                    "indicator": {
                        "id": 0,
                        "title_ENG": "string",
                        "code": "string",
                        "measurement_units": "string",
                        "measurement_units_quarter": "string",
                        "measurement_units_month": "string",
                        "latest_data": "string",
                        "annual_data": [],
                        "quarter_data": [],
                        "month_data": [],
                        "children": [],
                        "kpi_characteristics": "string",
                    },
                    "year": "string",
                    "quarter": "string",
                    "month": "string",
                    "row": 0,
                    "chart_type": "string",
                    "width": 0,
                    "include_children": False,
                }
            ]
        ],
    },
    response_only=True,
)


MONTH_LIST_RESPONSE_EXAMPLE = OpenApiExample(
    "Month list success response",
    value={
        "result": "string",
        "message": "string",
        "data": [
            {
                "month_AMH": "string",
            }
        ],
    },
    response_only=True,
)


YEAR_LIST_RESPONSE_EXAMPLE = OpenApiExample(
    "Year list success response",
    value={
        "result": "string",
        "message": "string",
        "data": [
            {
                "year_EC": 0,
            }
        ],
    },
    response_only=True,
)


YEAR_PARAMETER = OpenApiParameter(
    name="year",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    required=False,
    description="Reporting year filter.",
)

QUARTER_PARAMETER = OpenApiParameter(
    name="quarter",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    required=False,
    description="Reporting period filter such as 3month, 6month, 9month, or 12month.",
)

VERSION_PARAMETER = OpenApiParameter(
    name="version",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    required=True,
    description="Current mobile app semantic version, for example 2.1.0.",
)

EXPORT_DATA_TYPE_PARAMETER = OpenApiParameter(
    name="data_type",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    required=True,
    description="Export data frequency.",
    enum=["annual", "quarter", "month"],
)

EXPORT_FILE_TYPE_PARAMETER = OpenApiParameter(
    name="file_type",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    required=True,
    description="Requested export file type.",
    enum=["excel", "html"],
)


def mobile_json_schema(
    summary: str,
    *,
    description: str,
    tags: list[str],
    parameters=None,
    success_response=None,
    success_examples=None,
    error_response=None,
    error_examples=None,
):
    return extend_schema(
        summary=summary,
        description=description,
        tags=tags,
        parameters=parameters or [],
        responses={
            200: OpenApiResponse(
                response=success_response or SuccessEnvelopeSerializer,
                description="Successful response.",
                examples=success_examples or [],
            ),
            400: OpenApiResponse(
                response=error_response or TimeSeriesErrorResponseSerializer,
                description="Invalid request.",
                examples=error_examples or [],
            ),
            401: OpenApiResponse(description="Authentication credentials were missing or invalid."),
            502: OpenApiResponse(
                response=error_response or TimeSeriesErrorResponseSerializer,
                description="Upstream service was unavailable.",
                examples=error_examples or [],
            ),
        },
    )


def mobile_export_schema(summary: str, *, description: str, tags: list[str], parameters=None):
    return extend_schema(
        summary=summary,
        description=description,
        tags=tags,
        parameters=parameters or [],
        responses={
            200: OpenApiResponse(description="Binary export file response."),
            401: OpenApiResponse(description="Authentication credentials were missing or invalid."),
            502: OpenApiResponse(response=ErrorEnvelopeSerializer, description="Upstream service was unavailable."),
        },
    )
