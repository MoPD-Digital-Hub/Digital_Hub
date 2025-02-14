from django.shortcuts import render
from rest_framework.response import Response
from rest_framework import status
from userManagement.api.serializer import UserSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes


@api_view(['GET' , 'PUT'])
@permission_classes([IsAuthenticated])
def user(request):
    user = request.user

    if request.method == 'GET':
        serializer = UserSerializer(user)
        data = serializer.data
        return Response({"result" : "SUCCUSS", "message" : "SUCCUSS",  "data" : data}, status=status.HTTP_200_OK)
    
    elif request.method == 'PUT':
        serializer = UserSerializer(user, data=request.data, partial=True)

        if serializer.is_valid():
          serializer.save()
          data = serializer.data
          return Response({"result" : "SUCCUSS", "message" : "SUCCUSS",  "data" : data},status=status.HTTP_200_OK)
        
        return Response({"result" : "FAILURE", "data" : None, "message" : serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    
    
    