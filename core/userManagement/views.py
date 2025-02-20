import secrets
from django.shortcuts import render
from rest_framework.response import Response
from rest_framework import status
from userManagement.api.serializer import UserSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from userManagement.api.serializer import EmailSerializer
import datetime
from datetime import timedelta
from userManagement.models import CustomUser
from .services.email import send_email



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
    

@api_view(['POST'])
def reset_password(request):
    serializer = EmailSerializer(data=request.data)
    
    if serializer.is_valid():
        try:
            user = CustomUser.objects.get(email=serializer.data['email'])
        except CustomUser.DoesNotExist: 
            return Response({"result" : "FAILURE", "message" : "USER_NOT_FOUND"}, status=status.HTTP_400_BAD_REQUEST)
        
        secret_token = secrets.token_hex(20)
        
        now = datetime.datetime.now()
        expire_date = now + timedelta(minutes=20)

        user.token = secret_token
        user.tokenExpiration = expire_date
        user.save()
        
        send_email()
        print("email sent")
        return Response({"result" : "SUCCESS", "message" : "EMAIL_SENT"}, status=status.HTTP_200_OK)

        
    return Response({"result" : "FAILURE", "data" : None, "message" : "Invalid Input!"}, status=status.HTTP_400_BAD_REQUEST)
    