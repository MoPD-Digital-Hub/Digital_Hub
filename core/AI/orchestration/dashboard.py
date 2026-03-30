import logging

import certifi
import requests

from .config import get_orchestration_settings

LOGGER = logging.getLogger("AI.orchestration.dashboard")


class DashboardServiceError(Exception):
    pass


class DashboardGenerationService:
    def __init__(self, settings=None):
        self.settings = settings or get_orchestration_settings()

    def create_dashboard(self, prompt: str) -> dict:
        payload = {"prompt": str(prompt or "").strip()}
        if not payload["prompt"]:
            raise DashboardServiceError("prompt is required")

        try:
            response = requests.post(
                self.settings.dashboard_create_url,
                json=payload,
                timeout=self.settings.dashboard_timeout_seconds,
                verify=certifi.where(),
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            LOGGER.exception("Dashboard API request failed")
            raise DashboardServiceError(str(exc)) from exc
        except ValueError as exc:
            LOGGER.exception("Dashboard API returned invalid JSON")
            raise DashboardServiceError("Dashboard API returned invalid JSON.") from exc

        normalized = {
            "id": data.get("id"),
            "prompt": data.get("prompt"),
            "share_url": str(data.get("share_url") or "").strip(),
            "title": str(data.get("title") or "").strip(),
        }
        if not normalized["share_url"]:
            raise DashboardServiceError("Dashboard API response did not include share_url.")
        return normalized
