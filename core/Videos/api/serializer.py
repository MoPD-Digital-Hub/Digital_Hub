from Videos.models import Video, VideoComment, VideoCommentLike, VideoLike
from rest_framework import serializers

from django.core.exceptions import ValidationError
import magic  # python-magic for MIME type detection
import os

class VideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = '__all__'
    
    def validate_video(self, value):
        # Validate file extension
        valid_extensions = ['.mp4']
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in valid_extensions:
            raise serializers.ValidationError("Unsupported file type. Allowed: MP4.")

        # Validate MIME type using python-magic
        mime = magic.Magic(mime=True)
        mime_type = mime.from_buffer(value.read(1024))  # Read first 1KB to check type
        valid_mime_types = ['video/mp4']
        if mime_type not in valid_mime_types:
            raise serializers.ValidationError("Invalid file type. Ensure it's a valid video file.")

        # Validate file size (e.g., max 50MB)
        max_size = 100 * 1024 * 1024  # 50MB
        if value.size > max_size:
            raise serializers.ValidationError("File size exceeds 100MB limit.")

        return value

class VideoCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoComment
        fields = '__all__'


class VideoLikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoLike
        fields = '__all__'