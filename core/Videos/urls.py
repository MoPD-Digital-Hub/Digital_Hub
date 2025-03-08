from django.urls import path, include
from Videos.api.api import video_api , comments_api , toggle_like , like_comment_api


urlpatterns = [
    path('', video_api),
    path('comments/<int:video_id>/', comments_api),
    path('toggle-like/<int:video_id>/' ,  toggle_like),
    path('like_comment/<int:comment_id>/' ,  like_comment_api)
]