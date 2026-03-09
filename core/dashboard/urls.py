from django.urls import path

from .views import (
    admas_ai_page,
    dashboard_login,
    data_categories_page,
    data_indicator_detail_page,
    data_topic_detail_page,
    goal_detail_page,
    policy_area_detail_page,
    policy_area_list_page,
    public_body_detail_page,
    public_body_list_page,
    sample_dashboard,
)

urlpatterns = [
    path("login/", dashboard_login, name="dashboard_login"),
    path("", sample_dashboard, name="dashboard_home"),
    path("sample/", sample_dashboard, name="dashboard_sample"),
    path("admas-ai/", admas_ai_page, name="dashboard_admas_ai"),
    path("data/", data_categories_page, name="data_categories"),
    path("data/<int:topic_id>/", data_topic_detail_page, name="data_topic_detail"),
    path("data/indicator/<int:indicator_id>/", data_indicator_detail_page, name="data_indicator_detail"),
    path("statistics/policy-areas/", policy_area_list_page, name="policy_area_list"),
    path("statistics/public-bodies/", public_body_list_page, name="public_body_list"),
    path("statistics/public-bodies/<int:ministry_id>/", public_body_detail_page, name="public_body_detail"),
    path("statistics/policy-areas/<int:policy_area_id>/", policy_area_detail_page, name="policy_area_detail"),
    path("statistics/goals/<int:goal_id>/", goal_detail_page, name="goal_detail"),
]
