import requests
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.conf import settings
from rest_framework import status


DPMES_URL = "https://dpmes.mopd.gov.et"

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def policy_areas(request):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{DPMES_URL}/api/digital-hub/all-policy-area/",
            params=params,
            timeout=10
        )

        return Response(res.json(), status=res.status_code)

    except requests.exceptions.RequestException as e:
        return Response(
            {"detail": f"Failed to reach DPMES service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def policy_area_detail(request, id):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{DPMES_URL}/api/digital-hub/policy-area-detail/{id}/",
            params=params,
            timeout=10
        )

        return Response(res.json(), status=res.status_code)

    except requests.exceptions.RequestException as e:
        return Response(
            {"detail": f"Failed to reach DPMES service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )
    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def goal_detail(request, id):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{DPMES_URL}/api/digital-hub/goal-detail/{id}",
            params=params,
            timeout=10
        )

        return Response(res.json(), status=res.status_code)

    except requests.exceptions.RequestException as e:
        return Response(
            {"detail": f"Failed to reach DPMES service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )
    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def all_ministries(request):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{DPMES_URL}/api/digital-hub/all-ministries/",
            params=params,
            timeout=10
        )

        return Response(res.json(), status=res.status_code)

    except requests.exceptions.RequestException as e:
        return Response(
            {"detail": f"Failed to reach DPMES service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )
    


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ministry_detail(request, id):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{DPMES_URL}/api/digital-hub/ministry-detail/{id}",
            params=params,
            timeout=10
        )

        return Response(res.json(), status=res.status_code)

    except requests.exceptions.RequestException as e:
        return Response(
            {"detail": f"Failed to reach DPMES service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )
    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ministry_goal_detail(request, id):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{DPMES_URL}/api/digital-hub/ministry-goal-detail/{id}/",
            params=params,
            timeout=10
        )

        return Response(res.json(), status=res.status_code)

    except requests.exceptions.RequestException as e:
        return Response(
            {"detail": f"Failed to reach DPMES service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ministry_performance(request, id):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{DPMES_URL}/api/digital-hub/ministry-performance/{id}",
            params=params,
            timeout=10
        )

        return Response(res.json(), status=res.status_code)

    except requests.exceptions.RequestException as e:
        return Response(
            {"detail": f"Failed to reach DPMES service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def single_ministry(request):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{DPMES_URL}/api/digital-hub/single_ministry/",
            params=params,
            timeout=10
        )

        return Response(res.json(), status=res.status_code)

    except requests.exceptions.RequestException as e:
        return Response(
            {"detail": f"Failed to reach DPMES service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def affiliated_ministries(request):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{DPMES_URL}/api/digital-hub/affilated-ministries",
            params=params,
            timeout=10
        )

        return Response(res.json(), status=res.status_code)

    except requests.exceptions.RequestException as e:
        return Response(
            {"detail": f"Failed to reach DPMES service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )
    


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def indicator_detail(request, id):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{DPMES_URL}/api/digital-hub/indicator-detail/{id}/",
            params=params,
            timeout=10
        )

        return Response(res.json(), status=res.status_code)

    except requests.exceptions.RequestException as e:
        return Response(
            {"detail": f"Failed to reach DPMES service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def year_lists(request):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{DPMES_URL}/year_quarter_list",
            params=params,
            timeout=10
        )

        return Response(res.json(), status=res.status_code)

    except requests.exceptions.RequestException as e:
        return Response(
            {"detail": f"Failed to reach DPMES service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )
    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def general_search(request):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{DPMES_URL}/api/digital-hub/general_search/",
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
def overview_ministries(request):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{DPMES_URL}/api/digital-hub/dashboard/ministries/",
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
def overview_policy_area(request):
    try:
        params = request.query_params.dict()

        res = requests.get(
            f"{DPMES_URL}/api/digital-hub/dashboard/policy-area/",
            params=params,
            timeout=10
        )

        return Response(res.json(), status=res.status_code)

    except requests.exceptions.RequestException as e:
        return Response(
            {"detail": f"Failed to reach Time-Series service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )