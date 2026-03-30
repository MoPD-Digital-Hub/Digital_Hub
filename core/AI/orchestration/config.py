import os
from dataclasses import dataclass


@dataclass(frozen=True)
class OrchestrationSettings:
    dashboard_create_url: str
    dashboard_timeout_seconds: int


def get_orchestration_settings() -> OrchestrationSettings:
    return OrchestrationSettings(
        dashboard_create_url=(
            os.getenv("DASHBOARD_CREATE_API_URL", "https://analytics.mopd.gov.et/api/ai-dashboard-create/").strip()
            or "https://analytics.mopd.gov.et/api/ai-dashboard-create/"
        ),
        dashboard_timeout_seconds=int(os.getenv("DASHBOARD_TIMEOUT_SECONDS", "30")),
    )


def validate_orchestration_settings(debug: bool):
    settings = get_orchestration_settings()
    errors = []
    if not debug and not settings.dashboard_create_url:
        errors.append("DASHBOARD_CREATE_API_URL is required in production")
    if settings.dashboard_timeout_seconds <= 0:
        errors.append("DASHBOARD_TIMEOUT_SECONDS must be greater than 0")
    if errors:
        raise ValueError("; ".join(errors))
