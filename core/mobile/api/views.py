from collections import defaultdict

from drf_spectacular.utils import extend_schema
from packaging import version as v
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated

from mobile.models import FAQ, App, AppVersion, ContactUs, Setting
from project.responses import LEGACY_SUCCESS, failure, success

from .serializers import AppSerializer, ContactUsSerializer, FAQSerializer, SettingSerializer


@extend_schema(exclude=True)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def app(request):
    apps = App.objects.all()
    seriliazer = AppSerializer(apps, many=True)

    if request.method == 'GET':
        return success(request, seriliazer.data, message="SUCCUSS", result=LEGACY_SUCCESS)

@extend_schema(exclude=True)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def setting(request):
    settings = Setting.objects.all()
    serializer = SettingSerializer(settings , many=True, context={"request": request})

    return success(request, serializer.data, message="SUCCUSS", result=LEGACY_SUCCESS)
    
@extend_schema(exclude=True)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def faq(request):
    faq_items = FAQ.objects.all()
    serializer = FAQSerializer(faq_items, many=True, context={"request": request})

    grouped_data = defaultdict(list)
    for item in serializer.data:
        faq_type = item.get('type')
        grouped_data[faq_type].append(item)

    return success(request, grouped_data)
    
@extend_schema(exclude=True)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def contact_us(request):
    contact_us = ContactUs.objects.all()
    serializer = ContactUsSerializer(contact_us , many=True, context={"request": request})

    return success(request, serializer.data, message="SUCCUSS", result=LEGACY_SUCCESS)

@extend_schema(exclude=True)
@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def check_update(request):
    user_version = request.query_params.get('version')

    if not user_version:
        return failure(request, "version query param is required", status.HTTP_400_BAD_REQUEST,
                       code="VERSION_REQUIRED", detail="version query param is required")

    app_version = AppVersion.objects.last()
    if not app_version:
        return failure(request, "No version info found", status.HTTP_404_NOT_FOUND,
                       code="NO_VERSION_INFO", detail="No version info found")

    try:
        current = v.parse(user_version)
    except v.InvalidVersion:
        return failure(request, "version must look like 2.1.0", status.HTTP_400_BAD_REQUEST,
                       code="VERSION_INVALID", detail="version must look like 2.1.0")
    min_supported = v.parse(app_version.min_supported_version)
    latest = v.parse(app_version.latest_version)

    if current < min_supported:
        force_update = True
        optional_update = False
    elif current < latest:
        force_update = False
        optional_update = True
    elif current == latest:
        force_update = False
        optional_update = False
    else:
        force_update = False
        optional_update = False

    data = {
        "force_update": force_update,
        "optional_update": optional_update,
        "latest_version": app_version.latest_version,
        "message": app_version.message if force_update else "",
    }

    return success(request, data)
