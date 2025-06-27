import secrets
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
from rest_framework import status
from userManagement.api.serializer import UserSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from userManagement.api.serializer import EmailSerializer, PasswordSerializer
from datetime import timedelta
from django.utils import timezone
from userManagement.models import CustomUser
from .tasks.email_tasks import send_email
from django.contrib.auth.hashers import make_password
from django.contrib.auth import authenticate
from .api.serializer import LoginSerializer, ValidateOTPSerializer
import random


@api_view(['POST'])
def generate_login_opt(request):
    if request.method == 'POST':
        serializer = LoginSerializer(data = request.data)

        if serializer.is_valid():
            user = authenticate(email__iexact=serializer.data['email'].strip(), password=serializer.data['password'])

            if user is not None:
                # Generate 6-digit OTP
                otp = random.randint(100000, 999999)
                
                now = timezone.now()
                expire_date = now + timedelta(minutes=20)

                user.token = otp
                user.tokenExpiration = expire_date
                user.save()

                ## send email
                send_email.delay(user.email, otp)

                return Response({
                    "result": "SUCCESS",
                    "message": "OTP_GENERATED",
                    "data": None
                }, status=status.HTTP_200_OK)
            
            else:
                return Response({
                    "result": "FAILURE",
                    "message": "LOGIN_FAILED",
                    "data": None
                }, status=status.HTTP_401_UNAUTHORIZED)
            
        else:
            return Response({
                "result": "FAILURE",
                "message": "INVALID_INPUT",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
    else:
        return Response({
            "result": "FAILURE",
            "message": "INVALID_METHOD",
            "errors": None
        }, status=status.HTTP_405_METHOD_NOT_ALLOWED)

@api_view(['POST'])
def validate_login_opt(request):
    serializer = ValidateOTPSerializer(data=request.data)
    if serializer.is_valid():
        try:
            user = CustomUser.objects.get(email__iexact=serializer.data['email'].strip())
        except CustomUser.DoesNotExist:
            return Response({
                "result": "FAILURE",
                "message": "USER_NOT_FOUND",
                "data" : None
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Validate token and expiration
        otp = serializer.data['otp']
 
        if str(user.token) != str(otp):
            return Response({"result": "FAILURE", "message": "INVALID_OTP", "data" : None}, status=status.HTTP_400_BAD_REQUEST)
        
        if timezone.now() > user.tokenExpiration:
            return Response({"result": "FAILURE", "message": "OTP_EXPIRED", "data" : None}, status=status.HTTP_400_BAD_REQUEST)
        
        if str(user.token) == str(otp) and user.tokenExpiration > timezone.now():
            refresh = RefreshToken.for_user(user)
            user.token = None
            user.tokenExpiration = None
            user.save()

            return Response({
            "result": "SUCCESS",
            "message": "TOKEN_CREATED",
            "data": {
                "user" : UserSerializer(user).data,
                "refresh": str(refresh),
                "access": str(refresh.access_token)
            }
        }, status=status.HTTP_200_OK)


        return Response({"result" : "FAILURE", "message" : "INVALID_OTP", "data" : None}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"result" : "FAILURE", "message" : "INVALID_INPUT", "data" : None}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET' , 'PUT'])
@permission_classes([IsAuthenticated])
def user(request):
    user_instance = request.user

    if request.method == 'GET':
        serializer = UserSerializer(user_instance)
        data = serializer.data
        return Response({"result" : "SUCCUSS", "message" : "SUCCUSS",  "data" : data}, status=status.HTTP_200_OK)
    
    elif request.method == 'PUT':
        serializer = UserSerializer(user_instance, data=request.data, partial=True)

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
                user = CustomUser.objects.get(email__iexact=serializer.data['email'])
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
                user = CustomUser.objects.get(email__iexact=email)

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

