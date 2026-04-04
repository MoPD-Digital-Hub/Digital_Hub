from rest_framework import serializers
from drf_spectacular.utils import OpenApiResponse, extend_schema

from userManagement.api.serializer import (
    EmailSerializer,
    LoginSerializer,
    PasswordSerializer,
    UserSerializer,
    ValidateOTPSerializer,
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


class OTPTokenDataSerializer(serializers.Serializer):
    user = UserSerializer()
    refresh = serializers.CharField()
    access = serializers.CharField()


class OTPValidationSuccessSerializer(serializers.Serializer):
    result = serializers.CharField()
    message = serializers.CharField()
    data = OTPTokenDataSerializer()


class TokenRefreshRequestSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class TokenRefreshDataSerializer(serializers.Serializer):
    access = serializers.CharField()


class TokenRefreshSuccessSerializer(serializers.Serializer):
    result = serializers.CharField()
    message = serializers.CharField()
    data = TokenRefreshDataSerializer()


login_schema = extend_schema(
    summary="Request login OTP",
    description="Authenticates email and password, then generates and sends a one-time password.",
    tags=["Mobile Authentication"],
    request=LoginSerializer,
    responses={
        200: OpenApiResponse(response=AuthEnvelopeSerializer, description="OTP generated."),
        400: OpenApiResponse(response=AuthErrorEnvelopeSerializer, description="Invalid input or temporarily blocked account."),
        401: OpenApiResponse(response=AuthErrorEnvelopeSerializer, description="Invalid credentials."),
        403: OpenApiResponse(response=AuthErrorEnvelopeSerializer, description="Too many failed attempts."),
    },
)


verify_otp_schema = extend_schema(
    summary="Verify login OTP",
    description="Verifies the one-time password and returns refresh and access tokens.",
    tags=["Mobile Authentication"],
    request=ValidateOTPSerializer,
    responses={
        200: OpenApiResponse(response=OTPValidationSuccessSerializer, description="OTP accepted and tokens created."),
        400: OpenApiResponse(response=AuthErrorEnvelopeSerializer, description="Invalid, expired, or blocked OTP flow."),
        404: OpenApiResponse(response=AuthErrorEnvelopeSerializer, description="User not found."),
    },
)


reset_password_request_schema = extend_schema(
    methods=["POST"],
    summary="Request password reset OTP",
    description="Sends a reset token to the supplied email address.",
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
    description="Changes the password using email, reset token, and a new password.",
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
