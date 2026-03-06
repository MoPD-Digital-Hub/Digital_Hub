from django.urls import path

from .views import (
    admas_ai_page,
    dashboard_login,
    data_categories_page,
    data_indicator_detail_page,
    data_topic_detail_page,
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
]
