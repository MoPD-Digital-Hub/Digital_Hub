from .serializer import AppSerializer
from mobile.models import App
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from Videos.models import Video
from Videos.api.serializer import VideoSerializer

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