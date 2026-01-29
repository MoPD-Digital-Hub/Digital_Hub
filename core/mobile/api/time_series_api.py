import requests
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.conf import settings
from rest_framework import status


TIMESERIES_URL = "https://time-series.mopd.gov.et/"

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