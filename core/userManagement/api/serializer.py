from userManagement.models import CustomUser
from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('id', 'email', 'username' ,'first_name', 'last_name', 'password', 'photo', 'excellence', 'bio')
        extra_kwargs = {'password': {'write_only': True, 'required': True}}

class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField()