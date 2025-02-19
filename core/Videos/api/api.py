from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from Videos.models import Video
from .serializer import VideoSerializer , VideoCommentSerializer

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def video_api(request):
    """
    Fetch all videos.
    """
    if request.method == 'GET':
        videos = Video.objects.all()
        serializer = VideoSerializer(videos, many=True)
        return Response({"result" : "SUCCESS", "message" : "Videos fetched successfully!", "data" : serializer.data}, status=status.HTTP_200_OK)
       
    
