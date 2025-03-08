from Videos.models import Video, VideoComment, VideoCommentLike, VideoLike
from rest_framework import serializers

from django.core.exceptions import ValidationError

class VideoSerializer(serializers.ModelSerializer):
    is_liked = serializers.SerializerMethodField()
    class Meta:
        model = Video
        fields = '__all__'
    
    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request.user.is_authenticated:
            return obj.video_likes.filter(user=request.user).exists()
        return False
class VideoCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoComment
        fields = '__all__'


class VideoLikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoLike
        fields = '__all__'