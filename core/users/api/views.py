import logging
import secrets
from datetime import timedelta

from axes.handlers.proxy import AxesProxyHandler
from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from project.responses import LEGACY_SUCCESS, failure, success
from users.api.docs import (
    password_login_schema,
    reset_password_confirm_schema,
    reset_password_request_schema,
    token_refresh_schema,
)
from users.api.serializers import (
    EmailSerializer,
    LoginSerializer,
    PasswordSerializer,
    UserSerializer,
)
from users.models import CustomUser
from users.tasks import send_email

LOGGER = logging.getLogger("users.auth")
RESET_CODE_MINUTES = 20
# Wrong codes allowed before a reset code is cancelled and a new one must be requested.
RESET_CODE_ATTEMPTS = 5


@password_login_schema
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def password_login(request):
    """Sign in with email and password; returns the user and JWT refresh/access tokens."""
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

            user.token = secret_token
            user.tokenExpiration = timezone.now() + timedelta(minutes=RESET_CODE_MINUTES)
            user.trial = 0

            ## send email
            send_email(user.email, secret_token)
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

        # No code was requested, or it was cancelled after too many wrong tries.
        if not user.token or not user.tokenExpiration:
            return failure(request, "INVALID_TOKEN", status.HTTP_400_BAD_REQUEST)

        if not secrets.compare_digest(str(user.token), str(token)):
            # A 6-digit code can be guessed if tries are unlimited: cancel it
            # after a few wrong ones, so a new code has to be requested.
            user.trial += 1
            if user.trial >= RESET_CODE_ATTEMPTS:
                user.token = None
                user.tokenExpiration = None
                user.trial = 0
            user.save()
            return failure(request, "INVALID_TOKEN", status.HTTP_400_BAD_REQUEST)

        # Check token expiration
        if timezone.now() > user.tokenExpiration:
            return failure(request, "TOKEN_EXPIRED", status.HTTP_400_BAD_REQUEST)

        # Token is valid and active → update password
        user.set_password(new_password)
        user.token = None
        user.tokenExpiration = None
        user.trial = 0
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


class CustomTokenRefreshView(TokenRefreshView):
    @token_refresh_schema
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            if serializer.is_valid():
                return success(request, serializer.validated_data, message="TOKEN_REFRESHED")
            return failure(request, "INVALID_TOKEN", status.HTTP_400_BAD_REQUEST, errors=serializer.errors)
        except TokenError as exc:
            # An expired, blacklisted or malformed refresh token: the client must sign in again.
            return failure(request, "INVALID_TOKEN", status.HTTP_401_UNAUTHORIZED, code="token_not_valid",
                           error_message=str(exc))
        except Exception:
            LOGGER.exception("Token refresh failed")
            return failure(request, "EXCEPTION_OCCURRED", status.HTTP_500_INTERNAL_SERVER_ERROR)
