from django.apps import AppConfig


class AiConfig(AppConfig):
    """Admas AI: chat and answers.

    The label keeps the app's original name, so database tables, migrations,
    permissions and admin URLs are unchanged by the package rename.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "ai"
    label = "AI"
