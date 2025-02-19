from django.contrib import admin
from .models import Video, VideoComment, VideoCommentLike, VideoLike

# Register your models here.
admin.site.register(Video)
admin.site.register(VideoComment)
admin.site.register(VideoCommentLike)
admin.site.register(VideoLike)