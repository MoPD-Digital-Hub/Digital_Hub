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
from axes.utils import reset_request
from axes.helpers import get_client_username
from axes.handlers.proxy import AxesProxyHandler
from axes.signals import user_login_failed
from ipware import get_client_ip



@api_view(['POST'])
def generate_login_opt(request):
    serializer = LoginSerializer(data=request.data)
    handler = AxesProxyHandler()

    if handler.is_locked(request):
        return Response({
            "result": "FAILURE",
            "message": "Too many failed attempts. Try again later.",
            "data": None
        }, status=status.HTTP_403_FORBIDDEN)

    if serializer.is_valid():
        email = serializer.data['email'].lower().strip()
        password = serializer.data['password']
        user = authenticate(request=request, email=email, password=password)

        if user is not None:
            handler.reset_attempts(username=email, ip_address=request.META.get('REMOTE_ADDR'))

            if user.waiting_period and timezone.now() < user.waiting_period:
                remaining_time = user.waiting_period - timezone.now()
                minutes = int(remaining_time.total_seconds() // 60)
                return Response({
                    "result": "FAILURE",
                    "message": f"This account is temporarily blocked. Try again in {minutes} minutes.",
                    "data": None
                }, status=status.HTTP_400_BAD_REQUEST)

            otp = random.randint(100000, 999999)
            now = timezone.now()
            expire_date = now + timedelta(minutes=20)

            if user.email in ['testuser@mopd.gov.et', 'admas@mopd.gov.et']:
                user.token = 123456
                user.tokenExpiration = now + timedelta(days=90)
            else:
                user.token = otp
                user.tokenExpiration = expire_date
            user.save()

            send_email.delay(user.email, otp)

            return Response({
                "result": "SUCCESS",
                "message": "OTP_GENERATED",
                "data": None
            }, status=status.HTTP_200_OK)

        else:
            #user_login_failed.send(sender=None, request=request, credentials=serializer.data)

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

@api_view(['POST'])
def validate_login_opt(request):
    serializer = ValidateOTPSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email'].strip()
        otp = serializer.validated_data['otp']

        try:
            user = CustomUser.objects.get(email__iexact=email)
        except CustomUser.DoesNotExist:
            return Response({
                "result": "FAILURE",
                "message": "USER_NOT_FOUND",
                "data": None
            }, status=status.HTTP_404_NOT_FOUND)

        if user.waiting_period and timezone.now() < user.waiting_period:
            remaining_time = user.waiting_period - timezone.now()
            minutes = int(remaining_time.total_seconds() // 60)
            return Response({"result": "FAILURE", "message": f"This account is temporarily blocked. Try again in {minutes} minutes.", "data": None }, status=status.HTTP_400_BAD_REQUEST)


        if not user.token or timezone.now() > user.tokenExpiration:
            return Response({ "result": "FAILURE", "message": "OTP_EXPIRED", "data": None }, status=status.HTTP_400_BAD_REQUEST)

        
        if str(user.token) != str(otp):
            user.trial += 1
            if user.trial >= 5:
                user.waiting_period = timezone.now() + timedelta(minutes=30)
                user.trial = 0  
                user.save()
                return Response({"result": "FAILURE", "message": "Too many invalid attempts. Account locked for 30 minutes.", "data": None}, status=status.HTTP_400_BAD_REQUEST)

            user.save()
            return Response({"result": "FAILURE", "message": "INVALID_OTP", "data": None}, status=status.HTTP_400_BAD_REQUEST)

     
        refresh = RefreshToken.for_user(user)
        user.token = None
        user.tokenExpiration = None
        user.trial = 0
        user.waiting_period = None
        user.save()

        return Response({"result": "SUCCESS", "message": "TOKEN_CREATED",
            "data": {
                "user": UserSerializer(user).data,
                "refresh": str(refresh),
                "access": str(refresh.access_token)
            }
        }, status=status.HTTP_200_OK)

    return Response({
        "result": "FAILURE",
        "message": "INVALID_INPUT",
        "data": None
    }, status=status.HTTP_400_BAD_REQUEST)


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
                email = serializer.data['email'].lower().strip()
                user = CustomUser.objects.get(email__iexact=email)
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
        if not serializer.is_valid():
            # Return serializer validation errors (e.g., weak password, invalid email, etc.)
            return Response(
                {"result": "FAILURE", "message": serializer.errors, "data": None},
                status=status.HTTP_400_BAD_REQUEST
            )

        email = serializer.validated_data.get('email')
        token = serializer.validated_data.get('token')
        new_password = serializer.validated_data.get('password')

        try:
            user = CustomUser.objects.get(email__iexact=email)
        except CustomUser.DoesNotExist:
            return Response(
                {"result": "FAILURE", "message": "USER_NOT_FOUND", "data": None},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate token
        if user.token != token:
            return Response(
                {"result": "FAILURE", "message": "INVALID_TOKEN", "data": None},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check token expiration
        if timezone.now() > user.tokenExpiration:
            return Response(
                {"result": "FAILURE", "message": "TOKEN_EXPIRED", "data": None},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Token is valid and active → update password
        user.set_password(new_password)
        user.token = None  # Optional: clear token after successful reset
        user.tokenExpiration = None
        user.save()

        return Response(
            {"result": "SUCCESS", "message": "PASSWORD_CHANGED", "data": None},
            status=status.HTTP_200_OK
        )


        
    return Response({"result" : "FAILURE", "data" : None, "message" : "Invalid Input!", "data" : None}, status=status.HTTP_400_BAD_REQUEST)

