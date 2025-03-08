from .serializer import AppSerializer
from mobile.models import App
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def app(request):
    apps = App.objects.all()
    seriliazer = AppSerializer(apps, many=True)

    if request.method == 'GET':
        return Response({"result" : "SUCCUSS", "message" : "SUCCUSS", "data" : seriliazer.data,}, status=status.HTTP_200_OK)
