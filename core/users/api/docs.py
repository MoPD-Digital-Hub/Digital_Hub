from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers

from users.api.serializers import (
    EmailSerializer,
    LoginSerializer,
    PasswordSerializer,
    UserSerializer,
)


class AuthEnvelopeSerializer(serializers.Serializer):
    result = serializers.CharField()
    message = serializers.CharField()
    data = serializers.JSONField(allow_null=True, required=False)


class AuthErrorEnvelopeSerializer(serializers.Serializer):
    result = serializers.CharField()
    message = serializers.CharField()
    data = serializers.JSONField(allow_null=True, required=False)
    errors = serializers.JSONField(required=False)
    error = serializers.CharField(required=False)


class LoginDataSerializer(serializers.Serializer):
    user = UserSerializer()
    refresh = serializers.CharField()
    access = serializers.CharField()


class LoginSuccessSerializer(serializers.Serializer):
    result = serializers.CharField()
    message = serializers.CharField()
    data = LoginDataSerializer()


class TokenRefreshRequestSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class TokenRefreshDataSerializer(serializers.Serializer):
    access = serializers.CharField()


class TokenRefreshSuccessSerializer(serializers.Serializer):
    result = serializers.CharField()
    message = serializers.CharField()
    data = TokenRefreshDataSerializer()


password_login_schema = extend_schema(
    summary="Log in with email and password",
    description="Authenticates email and password and returns the user with refresh and access tokens.",
    tags=["Mobile Authentication"],
    request=LoginSerializer,
    responses={
        200: OpenApiResponse(response=LoginSuccessSerializer, description="Credentials accepted and tokens created."),
        400: OpenApiResponse(response=AuthErrorEnvelopeSerializer, description="Invalid input or temporarily blocked account."),
        401: OpenApiResponse(response=AuthErrorEnvelopeSerializer, description="Invalid credentials."),
        403: OpenApiResponse(response=AuthErrorEnvelopeSerializer, description="Too many failed attempts."),
    },
)


reset_password_request_schema = extend_schema(
    methods=["POST"],
    summary="Request a password reset code",
    description="Emails a 6-digit reset code, valid for 20 minutes, to the supplied address.",
    tags=["Mobile Authentication"],
    request=EmailSerializer,
    responses={
        200: OpenApiResponse(response=AuthEnvelopeSerializer, description="Reset token sent."),
        400: OpenApiResponse(response=AuthErrorEnvelopeSerializer, description="User not found or invalid input."),
    },
)


reset_password_confirm_schema = extend_schema(
    methods=["PUT"],
    summary="Confirm password reset",
    description="Changes the password using email, the emailed reset code (as `token`), and a new password. Five wrong codes cancel the code.",
    tags=["Mobile Authentication"],
    request=PasswordSerializer,
    responses={
        200: OpenApiResponse(response=AuthEnvelopeSerializer, description="Password changed."),
        400: OpenApiResponse(response=AuthErrorEnvelopeSerializer, description="Invalid token, expired token, weak password, or user not found."),
    },
)


token_refresh_schema = extend_schema(
    summary="Refresh access token",
    description="Exchanges a refresh token for a new access token.",
    tags=["Mobile Authentication"],
    request=TokenRefreshRequestSerializer,
    responses={
        200: OpenApiResponse(response=TokenRefreshSuccessSerializer, description="Access token refreshed."),
        400: OpenApiResponse(response=AuthErrorEnvelopeSerializer, description="Invalid refresh token."),
        500: OpenApiResponse(response=AuthErrorEnvelopeSerializer, description="Unexpected refresh error."),
    },
)
