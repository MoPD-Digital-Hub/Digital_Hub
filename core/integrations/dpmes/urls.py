from django.urls import path

from integrations.dpmes import views

# Served under /api/mobile/ (project/urls.py), where the website's scorecard
# pages and older app versions already call them.
urlpatterns = [
    path('policy-areas/', views.policy_areas, name='dpmes-policy-area'),
    path('policy-area-detail/<str:id>/', views.policy_area_detail, name='dpmes-policy-area-detail'),
    path('goal-detail/<str:id>/', views.goal_detail, name='dpmes-goal-detail'),
    path('ministries/', views.all_ministries, name='dpmes-ministries'),
    path('ministry-detail/<str:id>/', views.ministry_detail, name='dpmes-ministry-detail'),
    path('ministry-goal-detail/<str:id>/', views.ministry_goal_detail, name='dpmes-ministry-goal-detail'),
    path('ministry-performance/<str:id>/', views.ministry_performance, name='dpmes-ministry-performance'),
    path('affiliated-ministries/', views.affiliated_ministries, name='dpmes-affiliated-ministries'),
    path('dpmes-indicator-detail/<str:id>/', views.indicator_detail, name='dpmes-indicator-detail'),
    path('dpmes-year-lists/', views.year_lists, name='dpmes-year_lists'),
    path('default-time/', views.time_frame, name='default-time'),
]
