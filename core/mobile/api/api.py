from .serializer import AppSerializer , SettingSerializer , FAQSerializer , ContactUsSerializer
from mobile.models import App , Setting , FAQ , ContactUs
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from Videos.models import Video
from Videos.api.serializer import VideoSerializer
from collections import defaultdict

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
    