from django.urls import path
from mobile.api import api 

urlpatterns = [
    path('dashboard/apps/', api.app),
    path('dashboard/lastest-videos/', api.latest_videos),
    path('setting/' , api.setting),
    path('faq/' , api.faq),
    path('contact-us/' , api.contact_us)
    
]