from django.urls import path

from integrations.time_series import views

# Served under /api/mobile/ (project/urls.py), where the mobile app and the
# website call them.
urlpatterns = [
    path('topic-list/', views.topic_list, name='time-series-topic-list'),
    path('topic-detail/<str:id>/', views.topic_detail, name='time-series-topic-detail'),
    path('indicator-detail/<str:id>/', views.indicator_detail, name='time-series-indicator-detail'),
    path('search-auto-complete/<str:id>/', views.topic_categories_auto_complete, name='time-series-search-auto-complete'),
    path('general_search/', views.general_search, name='time-series-general_search'),
    path('trending/', views.trending, name='time-series-trending'),
    path('month-lists/', views.month_lists, name='time-series-month_lists'),
    path('year-lists/', views.year_lists, name='time-series-year_lists'),
    path('initiatives/', views.initiatives, name='time-series-initiatives'),
    path('project-list/', views.project_list, name='time-series-project-list'),
    path('project-detail/<str:id>/', views.project_detail, name='time-series-project-detail'),
    path('overview/', views.overview, name='time-series-overview'),
    path('filter-initiative-indicator-by-region/', views.filter_initiative_indicator_by_region, name='filter_initiative_indicator_by_region'),
    path('high-frequency/', views.high_frequency, name='time-series-high-frequency'),
    path('categories/<str:id>/', views.categories, name='time-series-categories'),
    path('kpis/<str:id>/', views.kpis, name='time-series-kpis'),
    path('export-topic-data/<str:id>/', views.export_topic_data, name='time-series-export-topic-data'),
    path('export-category-data/<str:id>/', views.export_category_data, name='time-series-export-category-data'),
    path('export-indicator-data/<str:id>/', views.export_indicator_data, name='time-series-export-indicator-data'),
]
