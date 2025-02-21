from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .serializer import CustomTokenObtainPairSerializer
from rest_framework.exceptions import AuthenticationFailed

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
            return Response({
                "result": "SUCCESS",
                "message": "TOKEN_CREATED",
                "data": serializer.validated_data
            }, status=status.HTTP_200_OK)
        except AuthenticationFailed as e:
            return Response({
                "result": "FAILURE",
                "message": "LOGIN_FAILED",
                "data": None
            }, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response({
                "result": "FAILURE",
                "message": "INVALID_INPUT",
                "errors": None
            }, status=status.HTTP_400_BAD_REQUEST)
        

class CustomTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            return Response({
                "result": "SUCCESS",
                "message": "TOKEN_REFRESHED",
                "data": serializer.validated_data
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                "result": "FAILURE",
                "message": "INVALID_TOKEN",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)


