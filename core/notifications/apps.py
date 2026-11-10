from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    """Notifications and push messages.

    The label keeps the app's original name, so database tables, migrations,
    permissions and admin URLs are unchanged by the package rename.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "notifications"
    label = "Notification"
