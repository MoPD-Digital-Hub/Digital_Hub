from django.urls import path

from mobile.api import views as api

urlpatterns = [
    path('dashboard/apps/', api.app),
    path('setting/' , api.setting),
    path('faq/' , api.faq),
    path('contact-us/' , api.contact_us),
    path('check-update/', api.check_update, name='check-update'),
]
