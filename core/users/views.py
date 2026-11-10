import secrets
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status
from users.api.serializers import UserSerializer
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from users.api.serializers import EmailSerializer, PasswordSerializer
from datetime import timedelta
from django.utils import timezone
from users.models import CustomUser
from .tasks import send_email
from django.contrib.auth import authenticate
from .api.serializers import LoginSerializer, ValidateOTPSerializer
import logging
import random
from django.conf import settings
from axes.handlers.proxy import AxesProxyHandler
from kombu.exceptions import OperationalError as KombuOperationalError
from users.api.docs import (
    login_schema,
    password_login_schema,
    reset_password_confirm_schema,
    reset_password_request_schema,
    verify_otp_schema,
)
from project.responses import LEGACY_SUCCESS, failure, success

LOGGER = logging.getLogger("users.auth")


@login_schema
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def generate_login_opt(request):
    serializer = LoginSerializer(data=request.data)
    handler = AxesProxyHandler()

    if handler.is_locked(request):
        return failure(request, "Too many failed attempts. Try again later.", status.HTTP_403_FORBIDDEN)

    if serializer.is_valid():
        email = serializer.data['email'].lower().strip()
        password = serializer.data['password']
        user = authenticate(request=request, email=email, password=password)

        if user is not None:
            handler.reset_attempts(username=email, ip_address=request.META.get('REMOTE_ADDR'))

            if user.waiting_period and timezone.now() < user.waiting_period:
                remaining_time = user.waiting_period - timezone.now()
                minutes = int(remaining_time.total_seconds() // 60)
                return failure(request, f"This account is temporarily blocked. Try again in {minutes} minutes.", status.HTTP_400_BAD_REQUEST)

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

            if settings.DEBUG:
                # OTPs must never reach production logs.
                LOGGER.info("Login OTP for %s: %s", user.email, user.token)

            try:
                send_email.delay(user.email, otp)
            except (KombuOperationalError, ConnectionRefusedError, OSError):
                # Dev/local fallback when broker is unavailable.
                send_email(user.email, otp)

            return success(request, None, message="OTP_GENERATED")

        else:
            #user_login_failed.send(sender=None, request=request, credentials=serializer.data)

            return failure(request, "LOGIN_FAILED", status.HTTP_401_UNAUTHORIZED)

    else:
        return failure(request, "INVALID_INPUT", status.HTTP_400_BAD_REQUEST, errors=serializer.errors)

@password_login_schema
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def password_login(request):
    """Email + password login that returns JWTs directly, without an OTP email.

    The OTP endpoints stay in place for flows that need email verification
    (signup, password reset).
    """
    serializer = LoginSerializer(data=request.data)
    handler = AxesProxyHandler()

    if handler.is_locked(request):
        return failure(request, "Too many failed attempts. Try again later.", status.HTTP_403_FORBIDDEN)

    if not serializer.is_valid():
        return failure(request, "INVALID_INPUT", status.HTTP_400_BAD_REQUEST, errors=serializer.errors)

    email = serializer.validated_data['email'].lower().strip()
    password = serializer.validated_data['password']
    # Passing request lets Axes count failed attempts toward the lockout.
    user = authenticate(request=request, email=email, password=password)

    if user is None:
        return failure(request, "LOGIN_FAILED", status.HTTP_401_UNAUTHORIZED)

    if user.waiting_period and timezone.now() < user.waiting_period:
        remaining_time = user.waiting_period - timezone.now()
        minutes = int(remaining_time.total_seconds() // 60)
        return failure(request, f"This account is temporarily blocked. Try again in {minutes} minutes.", status.HTTP_400_BAD_REQUEST)

    handler.reset_attempts(username=email, ip_address=request.META.get('REMOTE_ADDR'))

    refresh = RefreshToken.for_user(user)
    return success(request, {
            "user": UserSerializer(user).data,
            "refresh": str(refresh),
            "access": str(refresh.access_token)
        }, message="TOKEN_CREATED")


@verify_otp_schema
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def validate_login_opt(request):
    serializer = ValidateOTPSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email'].strip()
        otp = serializer.validated_data['otp']

        try:
            user = CustomUser.objects.get(email__iexact=email)
        except CustomUser.DoesNotExist:
            return failure(request, "USER_NOT_FOUND", status.HTTP_404_NOT_FOUND)

        if user.waiting_period and timezone.now() < user.waiting_period:
            remaining_time = user.waiting_period - timezone.now()
            minutes = int(remaining_time.total_seconds() // 60)
            return failure(request, f"This account is temporarily blocked. Try again in {minutes} minutes.", status.HTTP_400_BAD_REQUEST)


        if not user.token or timezone.now() > user.tokenExpiration:
            return failure(request, "OTP_EXPIRED", status.HTTP_400_BAD_REQUEST)

        
        if str(user.token) != str(otp):
            user.trial += 1
            if user.trial >= 5:
                user.waiting_period = timezone.now() + timedelta(minutes=30)
                user.trial = 0  
                user.save()
                return failure(request, "Too many invalid attempts. Account locked for 30 minutes.", status.HTTP_400_BAD_REQUEST)

            user.save()
            return failure(request, "INVALID_OTP", status.HTTP_400_BAD_REQUEST)

     
        refresh = RefreshToken.for_user(user)
        user.token = None
        user.tokenExpiration = None
        user.trial = 0
        user.waiting_period = None
        user.save()

        return success(request, {
                "user": UserSerializer(user).data,
                "refresh": str(refresh),
                "access": str(refresh.access_token)
            }, message="TOKEN_CREATED")

    return failure(request, "INVALID_INPUT", status.HTTP_400_BAD_REQUEST)


@api_view(['GET' , 'PUT'])
@permission_classes([IsAuthenticated])
def user(request):
    user_instance = request.user

    if request.method == 'GET':
        serializer = UserSerializer(user_instance)
        data = serializer.data
        return success(request, data, message="SUCCUSS", result=LEGACY_SUCCESS)
    
    elif request.method == 'PUT':
        serializer = UserSerializer(user_instance, data=request.data, partial=True)

        if serializer.is_valid():
          serializer.save()
          
          data = serializer.data
          return success(request, data, message="SUCCUSS", result=LEGACY_SUCCESS)
        
        return failure(request, serializer.errors, status.HTTP_400_BAD_REQUEST)
    
@reset_password_request_schema
@reset_password_confirm_schema
@api_view(['POST', 'PUT'])
@authentication_classes([])
@permission_classes([AllowAny])
def reset_password(request):

    if request.method == 'POST':
        serializer = EmailSerializer(data=request.data)
        if serializer.is_valid():
            try:
                email = serializer.data['email'].lower().strip()
                user = CustomUser.objects.get(email__iexact=email)
            except CustomUser.DoesNotExist: 
                return failure(request, "USER_NOT_FOUND", status.HTTP_400_BAD_REQUEST)
            
            secret_token = str(secrets.randbelow(10**6)).zfill(6)
            
            now = timezone.now()
            expire_date = now + timedelta(minutes=20)

            user.token = secret_token
            user.tokenExpiration = expire_date

            ## send email
            send_email(user.email, secret_token, purpose="reset")
            user.save()

            return success(request, None, message="EMAIL_SENT")

        return failure(request, serializer.errors, status.HTTP_400_BAD_REQUEST)

    elif request.method == 'PUT':
        serializer = PasswordSerializer(data=request.data)
        if not serializer.is_valid():
            # Return serializer validation errors (e.g., weak password, invalid email, etc.)
            return failure(request, serializer.errors, status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data.get('email')
        token = serializer.validated_data.get('token')
        new_password = serializer.validated_data.get('password')

        try:
            user = CustomUser.objects.get(email__iexact=email)
        except CustomUser.DoesNotExist:
            return failure(request, "USER_NOT_FOUND", status.HTTP_400_BAD_REQUEST)

        # Validate token
        if user.token != token:
            return failure(request, "INVALID_TOKEN", status.HTTP_400_BAD_REQUEST)

        # Check token expiration
        if timezone.now() > user.tokenExpiration:
            return failure(request, "TOKEN_EXPIRED", status.HTTP_400_BAD_REQUEST)

        # Token is valid and active → update password
        user.set_password(new_password)
        user.token = None  # Optional: clear token after successful reset
        user.tokenExpiration = None
        user.save()

        return success(request, None, message="PASSWORD_CHANGED")


        
    return failure(request, "Invalid Input!", status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ministries(request):
    """List active ministries/organizations, for profile and filter pickers."""
    from users.models import Ministry

    queryset = Ministry.objects.filter(is_active=True).order_by('name')
    search = request.query_params.get('search', '').strip()
    if search:
        from django.db.models import Q
        queryset = queryset.filter(Q(name__icontains=search) | Q(abbreviation__icontains=search))

    data = [
        {"id": m.id, "name": m.name, "name_am": m.name_am, "abbreviation": m.abbreviation, "image": m.image}
        for m in queryset
    ]
    return success(request, data)
