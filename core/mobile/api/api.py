from .serializer import AppSerializer , SettingSerializer , FAQSerializer , ContactUsSerializer
from mobile.models import App , Setting , FAQ , ContactUs,AppVersion
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from Videos.models import Video
from Videos.api.serializer import VideoSerializer
from collections import defaultdict
from packaging import version as v

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def app(request):
    apps = App.objects.all()
    seriliazer = AppSerializer(apps, many=True)

    if request.method == 'GET':
        return Response({"result" : "SUCCUSS", "message" : "SUCCUSS", "data" : seriliazer.data,}, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def latest_videos(request):
    videos = Video.objects.all().order_by('-created_at')[:3]
    serializer = VideoSerializer(videos, many=True, context={"request": request})

    return Response({"result" : "SUCCUSS", "message" : "SUCCUSS", "data" : serializer.data,}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def setting(request):
    settings = Setting.objects.all()
    serializer = SettingSerializer(settings , many=True, context={"request": request})

    return Response({"result" : "SUCCUSS", "message" : "SUCCUSS", "data" : serializer.data,}, status=status.HTTP_200_OK)
    


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def faq(request):
    faq_items = FAQ.objects.all()
    serializer = FAQSerializer(faq_items, many=True, context={"request": request})

    grouped_data = defaultdict(list)
    for item in serializer.data:
        faq_type = item.get('type')
        grouped_data[faq_type].append(item)

    return Response({
        "result": "SUCCESS",
        "message": "SUCCESS",
        "data": grouped_data
    }, status=status.HTTP_200_OK)
    


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def contact_us(request):
    contact_us = ContactUs.objects.all()
    serializer = ContactUsSerializer(contact_us , many=True, context={"request": request})

    return Response({"result" : "SUCCUSS", "message" : "SUCCUSS", "data" : serializer.data,}, status=status.HTTP_200_OK)

@api_view(['GET'])
def check_update(request):
    user_version = request.query_params.get('version')

    if not user_version:
        return Response(
            {"detail": "version query param is required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    app_version = AppVersion.objects.last()
    if not app_version:
        return Response(
            {"detail": "No version info found"},
            status=status.HTTP_404_NOT_FOUND
        )

    current = v.parse(user_version)
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

    return Response(
        {"result": "SUCCESS", "message": "SUCCESS", "data": data},
        status=status.HTTP_200_OK
    )