import requests
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import HttpResponse
from rest_framework import status
from drf_spectacular.utils import extend_schema
from mobile.api.docs import (
    CATEGORY_LIST_RESPONSE_EXAMPLE,
    CategoryListResponseSerializer,
    EXPORT_DATA_TYPE_PARAMETER,
    EXPORT_FILE_TYPE_PARAMETER,
    HIGH_FREQUENCY_RESPONSE_EXAMPLE,
    HighFrequencyResponseSerializer,
    INDICATOR_DETAIL_RESPONSE_EXAMPLE,
    IndicatorDetailResponseSerializer,
    MONTH_LIST_RESPONSE_EXAMPLE,
    MonthListResponseSerializer,
    TIME_SERIES_ERROR_EXAMPLE,
    TOPIC_LIST_ERROR_EXAMPLE,
    TOPIC_LIST_RESPONSE_EXAMPLE,
    TimeSeriesErrorResponseSerializer,
    TopicListResponseSerializer,
    YEAR_LIST_RESPONSE_EXAMPLE,
    YearListResponseSerializer,
    mobile_export_schema,
    mobile_json_schema,
)
from drf_spectacular.utils import OpenApiResponse


TIMESERIES_URL = "https://time-series.mopd.gov.et/"

@mobile_json_schema(
    "List time-series topics",
    description="Proxies the upstream time-series topic listing endpoint for mobile clients.",
    tags=["Time Series API"],
    success_response=TopicListResponseSerializer,
    success_examples=[TOPIC_LIST_RESPONSE_EXAMPLE],
    error_response=TimeSeriesErrorResponseSerializer,
    error_examples=[TOPIC_LIST_ERROR_EXAMPLE],
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def topic_list(request):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{TIMESERIES_URL}/api/mobile/topic-list/",
            params=params,
            timeout=10
        )

        return Response(res.json(), status=res.status_code)

    except requests.exceptions.RequestException as e:
        return Response(
            {"detail": f"Failed to reach Time-Series service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )

@extend_schema(exclude=True)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def topic_detail(request, id):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{TIMESERIES_URL}/api/mobile/topic-detail/{id}/",
            params=params,
            timeout=10
        )

        return Response(res.json(), status=res.status_code)

    except requests.exceptions.RequestException as e:
        return Response(
            {"detail": f"Failed to reach Time-Series service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )
    


@mobile_json_schema(
    "Get indicator detail",
    description="Returns a single indicator detail payload from the upstream time-series service.",
    tags=["Time Series API"],
    success_response=IndicatorDetailResponseSerializer,
    success_examples=[INDICATOR_DETAIL_RESPONSE_EXAMPLE],
    error_response=TimeSeriesErrorResponseSerializer,
    error_examples=[TIME_SERIES_ERROR_EXAMPLE],
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def indicator_detail(request, id):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{TIMESERIES_URL}/api/mobile/indicator-detail/{id}/",
            params=params,
            timeout=10
        )

        return Response(res.json(), status=res.status_code)

    except requests.exceptions.RequestException as e:
        return Response(
            {"detail": f"Failed to reach Time-Series service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )
    

@extend_schema(exclude=True)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def topic_categories_auto_complete(request, id):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{TIMESERIES_URL}/api/mobile/search-auto-complete/{id}/",
            params=params,
            timeout=10
        )

        return Response(res.json(), status=res.status_code)

    except requests.exceptions.RequestException as e:
        return Response(
            {"detail": f"Failed to reach Time-Series service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )
    

@extend_schema(exclude=True)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def general_search(request):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{TIMESERIES_URL}/api/mobile/general_search",
            params=params,
            timeout=10
        )

        return Response(res.json(), status=res.status_code)

    except requests.exceptions.RequestException as e:
        return Response(
            {"detail": f"Failed to reach Time-Series service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )
    

@extend_schema(exclude=True)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def trending(request):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{TIMESERIES_URL}/api/mobile/trending/",
            params=params,
            timeout=10
        )

        return Response(res.json(), status=res.status_code)

    except requests.exceptions.RequestException as e:
        return Response(
            {"detail": f"Failed to reach Time-Series service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )
    

@mobile_json_schema(
    "List months",
    description="Returns month list metadata for mobile filters.",
    tags=["Time Series API"],
    success_response=MonthListResponseSerializer,
    success_examples=[MONTH_LIST_RESPONSE_EXAMPLE],
    error_response=TimeSeriesErrorResponseSerializer,
    error_examples=[TIME_SERIES_ERROR_EXAMPLE],
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def month_lists(request):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{TIMESERIES_URL}/api/mobile/month-lists/",
            params=params,
            timeout=10
        )

        return Response(res.json(), status=res.status_code)

    except requests.exceptions.RequestException as e:
        return Response(
            {"detail": f"Failed to reach Time-Series service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )
    
@mobile_json_schema(
    "List years",
    description="Returns year list metadata for mobile filters.",
    tags=["Time Series API"],
    success_response=YearListResponseSerializer,
    success_examples=[YEAR_LIST_RESPONSE_EXAMPLE],
    error_response=TimeSeriesErrorResponseSerializer,
    error_examples=[TIME_SERIES_ERROR_EXAMPLE],
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def year_lists(request):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{TIMESERIES_URL}/api/mobile/year-lists/",
            params=params,
            timeout=10
        )

        return Response(res.json(), status=res.status_code)

    except requests.exceptions.RequestException as e:
        return Response(
            {"detail": f"Failed to reach Time-Series service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )
    

@extend_schema(exclude=True)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def initiatives(request):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{TIMESERIES_URL}/api/mobile/initiatives/",
            params=params,
            timeout=10
        )

        return Response(res.json(), status=res.status_code)

    except requests.exceptions.RequestException as e:
        return Response(
            {"detail": f"Failed to reach Time-Series service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )


@extend_schema(exclude=True)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def project_list(request):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{TIMESERIES_URL}/api/mobile/project-list/",
            params=params,
            timeout=10
        )

        return Response(res.json(), status=res.status_code)

    except requests.exceptions.RequestException as e:
        return Response(
            {"detail": f"Failed to reach Time-Series service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )
    

@extend_schema(exclude=True)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def project_detail(request, id):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{TIMESERIES_URL}/api/mobile/project-detail/{id}/",
            params=params,
            timeout=10
        )

        return Response(res.json(), status=res.status_code)

    except requests.exceptions.RequestException as e:
        return Response(
            {"detail": f"Failed to reach Time-Series service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )
    


@extend_schema(exclude=True)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def overview(request):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{TIMESERIES_URL}/api/mobile/dashboard/overview",
            params=params,
            timeout=10
        )

        return Response(res.json(), status=res.status_code)

    except requests.exceptions.RequestException as e:
        return Response(
            {"detail": f"Failed to reach Time-Series service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )


@extend_schema(exclude=True)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def filter_initiative_indicator_by_region(request):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{TIMESERIES_URL}/api/mobile/indicators_filter/",
            params=params,
            timeout=10
        )

        return Response(res.json(), status=res.status_code)

    except requests.exceptions.RequestException as e:
        return Response(
            {"detail": f"Failed to reach Time-Series service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )

###update api
@mobile_json_schema(
    "List topic categories",
    description="Returns category list data for the provided topic.",
    tags=["Time Series API"],
    success_response=CategoryListResponseSerializer,
    success_examples=[CATEGORY_LIST_RESPONSE_EXAMPLE],
    error_response=TimeSeriesErrorResponseSerializer,
    error_examples=[TIME_SERIES_ERROR_EXAMPLE],
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def categories(request, id):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{TIMESERIES_URL}/api/mobile/categories/{id}",
            params=params,
            timeout=10
        )

        return Response(res.json(), status=res.status_code)

    except requests.exceptions.RequestException as e:
        return Response(
            {"detail": f"Failed to reach Time-Series service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )
    

@mobile_json_schema(
    "List KPIs",
    description="Returns KPI data for the provided category or topic identifier.",
    tags=["Time Series API"],
    success_response=IndicatorDetailResponseSerializer,
    success_examples=[INDICATOR_DETAIL_RESPONSE_EXAMPLE],
    error_response=TimeSeriesErrorResponseSerializer,
    error_examples=[TIME_SERIES_ERROR_EXAMPLE],
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def kpis(request, id):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{TIMESERIES_URL}/api/mobile/kpis/{id}",
            params=params,
            timeout=10
        )

        return Response(res.json(), status=res.status_code)

    except requests.exceptions.RequestException as e:
        return Response(
            {"detail": f"Failed to reach Time-Series service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )
    

@mobile_json_schema(
    "Get high-frequency dashboard data",
    description="Returns high-frequency indicator data for mobile dashboards.",
    tags=["Time Series API"],
    success_response=HighFrequencyResponseSerializer,
    success_examples=[HIGH_FREQUENCY_RESPONSE_EXAMPLE],
    error_response=TimeSeriesErrorResponseSerializer,
    error_examples=[TIME_SERIES_ERROR_EXAMPLE],
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def high_frequency(request):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{TIMESERIES_URL}/api/mobile/high-frequency/",
            params=params,
            timeout=10
        )

        return Response(res.json(), status=res.status_code)

    except requests.exceptions.RequestException as e:
        return Response(
            {"detail": f"Failed to reach Time-Series service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )


@mobile_export_schema(
    "Export topic data",
    description="Downloads the topic export file from the upstream time-series service.",
    tags=["Time Series API"],
    parameters=[EXPORT_DATA_TYPE_PARAMETER, EXPORT_FILE_TYPE_PARAMETER],
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_topic_data(request, id):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{TIMESERIES_URL}/api/mobile/export-topic-data/{id}/",
            params=params,
            timeout=30
        )

        response = HttpResponse(
            res.content,
            status=res.status_code,
            content_type=res.headers.get(
                "Content-Type",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )

        content_disposition = res.headers.get("Content-Disposition")
        if content_disposition:
            response["Content-Disposition"] = content_disposition

        return response

    except requests.exceptions.RequestException as e:
        return Response(
            {"detail": f"Failed to reach Time-Series service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )


@mobile_export_schema(
    "Export category data",
    description="Downloads the category export file from the upstream time-series service.",
    tags=["Time Series API"],
    parameters=[EXPORT_DATA_TYPE_PARAMETER, EXPORT_FILE_TYPE_PARAMETER],
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_category_data(request, id):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{TIMESERIES_URL}/api/mobile/export-category-data/{id}/",
            params=params,
            timeout=30
        )

        response = HttpResponse(
            res.content,
            status=res.status_code,
            content_type=res.headers.get(
                "Content-Type",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )

        content_disposition = res.headers.get("Content-Disposition")
        if content_disposition:
            response["Content-Disposition"] = content_disposition

        return response

    except requests.exceptions.RequestException as e:
        return Response(
            {"detail": f"Failed to reach Time-Series service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )


@mobile_export_schema(
    "Export indicator data",
    description="Downloads the indicator export file from the upstream time-series service.",
    tags=["Time Series API"],
    parameters=[EXPORT_DATA_TYPE_PARAMETER, EXPORT_FILE_TYPE_PARAMETER],
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_indicator_data(request, id):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{TIMESERIES_URL}/api/mobile/export-indicator-data/{id}/",
            params=params,
            timeout=30
        )

        response = HttpResponse(
            res.content,
            status=res.status_code,
            content_type=res.headers.get(
                "Content-Type",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )

        content_disposition = res.headers.get("Content-Disposition")
        if content_disposition:
            response["Content-Disposition"] = content_disposition

        return response

    except requests.exceptions.RequestException as e:
        return Response(
            {"detail": f"Failed to reach Time-Series service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )
