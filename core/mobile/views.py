from django.shortcuts import render
from . models import *


def privacy_policy(request):
    privacy_policy = Setting.objects.get(id=1)
    return render(request , 'privacy_policy.html' , {'privacy_policy':privacy_policy})


def vr_dashboard(request):
    dashboard_payload = {
        "kpis": [
            {"label": "Revenue Pulse", "value": "$284K", "delta": "+18.4%", "position": "-1.45 1.95 -2.35"},
            {"label": "Active Users", "value": "12.8K", "delta": "+6.2%", "position": "0 2.08 -2.2"},
            {"label": "Alerts", "value": "3", "delta": "Needs review", "position": "1.45 1.95 -2.35"},
        ],
        "menu": ["Overview", "Analytics", "Users", "Alerts", "Media"],
        "notifications": [
            "API anomaly detected in East Africa region",
            "Enterprise onboarding tour requested",
            "Video encoding latency restored to baseline",
        ],
        "charts": [0.46, 0.72, 0.58, 0.88, 0.67, 0.94],
    }
    return render(request, 'vr_dashboard.html', {"dashboard_payload": dashboard_payload})
