from django.apps import AppConfig


class PreferencesConfig(AppConfig):
    """What each user follows and how their home dashboard is laid out."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "preferences"
