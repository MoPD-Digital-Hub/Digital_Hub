from django.apps import AppConfig


class UsersConfig(AppConfig):
    """Users, sign-in and organizations.

    The label keeps the app's original name, so database tables, migrations,
    permissions and admin URLs are unchanged by the package rename.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "users"
    label = "userManagement"
