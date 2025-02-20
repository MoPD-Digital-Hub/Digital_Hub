from django.urls import path, include
from Videos.api.api import video_api , comments_api , like_video_api , like_comment_api


urlpatterns = [
    path('', video_api),
    path('comments/<int:video_id>', comments_api),
    path('like_video/<int:video_id>' ,  like_video_api),
    path('like_comment/<int:comment_id>' ,  like_comment_api)
]