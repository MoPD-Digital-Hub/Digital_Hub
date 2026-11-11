from django.db import migrations, models
from django.db.models import F, Q
from django.utils import timezone


def mark_existing_as_sent(apps, schema_editor):
    """Notifications that were already due have been pushed (every save used to
    push them); record that, so editing an old one does not push it again."""
    Notification = apps.get_model("Notification", "Notification")
    now = timezone.now()
    Notification.objects.filter(
        Q(is_active=True),
        Q(send_at__isnull=True) | Q(send_at__lte=now),
        Q(expire_at__isnull=True) | Q(expire_at__gte=F("created_at")),
    ).update(sent_at=F("created_at"))


class Migration(migrations.Migration):

    dependencies = [
        ("Notification", "0002_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="sent_at",
            field=models.DateTimeField(
                blank=True, editable=False, null=True,
                help_text="When the push was sent. A notification is pushed once; later edits do not send it again.",
            ),
        ),
        migrations.RunPython(mark_existing_as_sent, migrations.RunPython.noop),
    ]
