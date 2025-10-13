from django.urls import path
from mobile.api import api, time_series_api 
from .views import *

urlpatterns = [
    path('dashboard/apps/', api.app),
    path('dashboard/lastest-videos/', api.latest_videos),
    path('setting/' , api.setting),
    path('faq/' , api.faq),
    path('contact-us/' , api.contact_us),
    path('check-update/', api.check_update, name='check-update'),

    #Time Series
    path('topic-list/', time_series_api.topic_list, name='time-series-topic-list'),
    path('topic-detail/<str:id>/', time_series_api.topic_detail, name='time-series-topic-detail'),
    path('indicator-detail/<str:id>/', time_series_api.indicator_detail, name='time-series-indicator-detail'),
    path('search-auto-complete/<str:id>/', time_series_api.topic_categories_auto_complete, name='time-series-search-auto-complete'),
    path('general_search/', time_series_api.general_search, name='time-series-general_search'),
    path('trending/', time_series_api.trending, name='time-series-trending'),
    path('month-lists/', time_series_api.month_lists, name='time-series-month_lists'),
    path('year-lists/', time_series_api.year_lists, name='time-series-year_lists'),
    path('initiatives/', time_series_api.initiatives, name='time-series-initiatives'),
    path('project-list/', time_series_api.project_list, name='time-series-project-list'),
    path('project-detail/<str:id>/', time_series_api.project_detail, name='time-series-project-detail'),
]