from django.urls import path

from preferences.api import views

urlpatterns = [
    path("", views.preferences, name="preferences"),
    path("follows/", views.follows, name="preference-follows"),
    path("follows/order/", views.follow_order, name="preference-follow-order"),
    path("follows/<int:follow_id>/", views.follow_detail, name="preference-follow-detail"),
    path("options/", views.options, name="preference-options"),
    path("dashboard/", views.dashboard, name="preference-dashboard"),
    path("movers/", views.movers, name="preference-movers"),
]
