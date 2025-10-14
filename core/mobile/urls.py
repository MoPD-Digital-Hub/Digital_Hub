from django.urls import path
from mobile.api import api, time_series_api, dpmes_api
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
    path('overview/', time_series_api.overview, name='time-series-overview'),

    #DPMEs
    path('policy-areas/', dpmes_api.policy_areas, name='dpmes-policy-area'),
    path('policy-area-detail/<str:id>/', dpmes_api.policy_area_detail, name='dpmes-policy-area-detail'),
    path('goal-detail/<str:id>/', dpmes_api.goal_detail, name='dpmes-goal-detail'),
    path('ministries/', dpmes_api.all_ministries, name='dpmes-ministries'),
    path('ministry-detail/<str:id>/', dpmes_api.ministry_detail, name='dpmes-ministry-detail'),
    path('ministry-goal-detail/<str:id>/', dpmes_api.ministry_goal_detail, name='dpmes-ministry-goal-detail'),
    path('ministry-performance/<str:id>/', dpmes_api.ministry_performance, name='dpmes-ministry-performance'),
    path('single-ministry/', dpmes_api.single_ministry, name='dpmes-single-ministry'),
    path('affiliated-ministries/', dpmes_api.affiliated_ministries, name='dpmes-affiliated-ministries'),
    path('dpmes-indicator-detail/<str:id>/', dpmes_api.indicator_detail, name='dpmes-indicator-detail'),
    path('dpmes-year-lists/', dpmes_api.year_lists, name='dpmes-year_lists'),
    path('dpmes-general-search/', dpmes_api.general_search, name='dpmes-general-search'),
    path('overview-ministries/', dpmes_api.overview_ministries, name='overview-ministries'),
    path('overview-policy-area/', dpmes_api.overview_policy_area, name='overview-policy-area'),
    path('default-time/', dpmes_api.time_frame, name='default-time'),
]