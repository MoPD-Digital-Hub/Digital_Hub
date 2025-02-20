import secrets
from django.shortcuts import render
from rest_framework.response import Response
from rest_framework import status
from userManagement.api.serializer import UserSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from userManagement.api.serializer import EmailSerializer, PasswordSerializer
import datetime
from datetime import timedelta
from django.utils import timezone
from userManagement.models import CustomUser
from .services.email import send_email
from django.contrib.auth.hashers import make_password


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
    

@api_view(['POST', 'PUT'])
def reset_password(request):

    if request.method == 'POST':
        serializer = EmailSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = CustomUser.objects.get(email=serializer.data['email'])
            except CustomUser.DoesNotExist: 
                return Response({"result" : "FAILURE", "message" : "USER_NOT_FOUND", "data" : None}, status=status.HTTP_400_BAD_REQUEST)
            
            secret_token = str(secrets.randbelow(10**6)).zfill(6)
            
            now = timezone.now()
            expire_date = now + timedelta(minutes=20)

            user.token = secret_token
            user.tokenExpiration = expire_date

            ## send email
            send_email(user.email, secret_token)
            user.save()

            return Response({"result" : "SUCCESS", "message" : "EMAIL_SENT", "data" : None}, status=status.HTTP_200_OK)
    
    
    elif request.method == 'PUT':
        serializer = PasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data.get('email')
            token = serializer.validated_data.get('token')
            new_password = serializer.validated_data.get('password')

            try:
                user = CustomUser.objects.get(email=email)

            except CustomUser.DoesNotExist: 
                return Response({"result" : "FAILURE", "message" : "USER_NOT_FOUND", "data" : None}, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate token and expiration
            if user.token != token:
                return Response({"result": "FAILURE", "message": "INVALID_TOKEN", "data" : None}, status=status.HTTP_400_BAD_REQUEST)

            if timezone.now() > user.tokenExpiration:
                return Response({"result": "FAILURE", "message": "TOKEN_EXPIRED", "data" : None}, status=status.HTTP_400_BAD_REQUEST)
            
            
            if user.token == serializer.data['token'] and user.tokenExpiration > timezone.now():
                user.set_password(new_password)
                user.save()
                return Response({"result" : "SUCCESS", "message" : "PASSWORD_CHANGED", "data" : None}, status=status.HTTP_200_OK)
            
            return Response({"result" : "FAILURE", "message" : "INVALID_TOKEN", "data" : None}, status=status.HTTP_400_BAD_REQUEST)

        
    return Response({"result" : "FAILURE", "data" : None, "message" : "Invalid Input!", "data" : None}, status=status.HTTP_400_BAD_REQUEST)

