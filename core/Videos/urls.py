from django.urls import path, include
from Videos.api.api import video_api , comments_api , toggle_like , toogle_like_comment


urlpatterns = [
    path('', video_api),
    path('comments/<int:video_id>/', comments_api),
    path('toggle-like/<int:video_id>/' ,  toggle_like),
    path('toogle-like-comment/<int:comment_id>/' ,  toogle_like_comment)
]