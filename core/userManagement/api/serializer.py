from userManagement.models import CustomUser
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.exceptions import AuthenticationFailed


from rest_framework import serializers
from django.contrib.auth.hashers import make_password

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('id', 'email', 'username', 'first_name', 'last_name', 'password', 'photo', 'excellence', 'bio')
        extra_kwargs = {
            'password': {'write_only': True, 'required': True}  # Ensure password is write-only
        }

    def create(self, validated_data):
        """Override create to hash the password before saving."""
        if 'password' in validated_data:
            validated_data['password'] = make_password(validated_data['password'])
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Override update to hash password if it's being changed."""
        if 'password' in validated_data:
            validated_data['password'] = make_password(validated_data['password'])
        return super().update(instance, validated_data)


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField()


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()


class ValidateOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.IntegerField()

class PasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    token = serializers.CharField()
    password = serializers.CharField()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        try:
            data = super().validate(attrs)
            return data
        except AuthenticationFailed as e:
            raise AuthenticationFailed("Incorrect username or password. Please try again.")
