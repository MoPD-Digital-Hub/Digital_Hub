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
    is_liked = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()
    excellence = serializers.CharField(source='user.excellence', read_only=True)
    user_first_name = serializers.CharField(source='user.first_name', read_only=True)
    user_last_name = serializers.CharField(source='user.last_name', read_only=True)
    class Meta:
        model = VideoComment
        fields = '__all__'

    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request.user.is_authenticated:
            return obj.comment_likes.filter(user=request.user).exists()
        return False
    
    def get_replies(self, obj):
        replies = VideoComment.objects.filter(replay=obj)
        request = self.context.get('request')
        return VideoCommentSerializer(replies, many=True, context = {"request" : request}).data
    
    



class VideoLikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoLike
        fields = '__all__'