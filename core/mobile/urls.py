from django.urls import path
from mobile.api import time_series, views as api
from .views import *

urlpatterns = [
    path('dashboard/apps/', api.app),
    path('setting/' , api.setting),
    path('faq/' , api.faq),
    path('contact-us/' , api.contact_us),
    path('check-update/', api.check_update, name='check-update'),

    #Time Series
    path('topic-list/', time_series.topic_list, name='time-series-topic-list'),
    path('topic-detail/<str:id>/', time_series.topic_detail, name='time-series-topic-detail'),
    path('indicator-detail/<str:id>/', time_series.indicator_detail, name='time-series-indicator-detail'),
    path('search-auto-complete/<str:id>/', time_series.topic_categories_auto_complete, name='time-series-search-auto-complete'),
    path('general_search/', time_series.general_search, name='time-series-general_search'),
    path('trending/', time_series.trending, name='time-series-trending'),
    path('month-lists/', time_series.month_lists, name='time-series-month_lists'),
    path('year-lists/', time_series.year_lists, name='time-series-year_lists'),
    path('initiatives/', time_series.initiatives, name='time-series-initiatives'),
    path('project-list/', time_series.project_list, name='time-series-project-list'),
    path('project-detail/<str:id>/', time_series.project_detail, name='time-series-project-detail'),
    path('overview/', time_series.overview, name='time-series-overview'),
    path('filter-initiative-indicator-by-region/', time_series.filter_initiative_indicator_by_region, name='filter_initiative_indicator_by_region'),
    path('high-frequency/', time_series.high_frequency, name='time-series-high-frequency'),

    ##updated
    path('categories/<str:id>/', time_series.categories, name='time-series-categories'),
    path('kpis/<str:id>/', time_series.kpis, name='time-series-kpis'),
    path('export-topic-data/<str:id>/', time_series.export_topic_data, name='time-series-export-topic-data'),
    path('export-category-data/<str:id>/', time_series.export_category_data, name='time-series-export-category-data'),
    path('export-indicator-data/<str:id>/', time_series.export_indicator_data, name='time-series-export-indicator-data'),
]
