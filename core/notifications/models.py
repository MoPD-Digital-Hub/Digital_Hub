from django.conf import settings
from django.db import models
from django.utils import timezone

from notifications.tasks import send_to_all


class DeviceToken(models.Model):
    PLATFORM_CHOICES = [
        ('android', 'Android'),
        ('ios', 'iOS'),
        ('web', 'Web'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='device_tokens')
    token = models.CharField(max_length=512, unique=True)
    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES, default='android')
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} ({self.platform})"


class NotificationCategory(models.Model):
    icon = models.FileField(upload_to='icons/', max_length=200, null=True, blank=True)
    title = models.CharField(max_length=50)
    color = models.CharField(max_length=20, blank=True, help_text="Optional hex/tailwind class")

    def __str__(self):
        return self.title
    


class Notification(models.Model):
    title = models.CharField(max_length=200)
    message = models.TextField()
    category = models.ForeignKey(NotificationCategory, null=True, blank=True, on_delete=models.SET_NULL)

    # Schedule / send controls
    send_at = models.DateTimeField(blank=True, null=True, help_text="If set, schedule delivery for this time; otherwise send immediately.")
    expire_at = models.DateTimeField(blank=True, null=True, help_text="Optional: don't deliver after this time.")
    is_active = models.BooleanField(default=True)
    sent_at = models.DateTimeField(
        blank=True, null=True, editable=False,
        help_text="When the push was sent. A notification is pushed once; later edits do not send it again.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-send_at', '-created_at']

    def __str__(self):
        category = self.category.title if self.category else "General"
        return f"{category} — {self.title}"

    def should_send_now(self):
        now = timezone.now()
        if not self.is_active:
            return False
        if self.send_at and self.send_at > now:
            return False
        if self.expire_at and self.expire_at < now:
            return False
        return True
    
    def save(self, *args, **kwargs):
        if not self._state.adding and kwargs.get("update_fields") is None:
            # sent_at is written only by send_if_due(). A copy loaded before the
            # scheduler sent the notification must not clear it on save.
            kwargs["update_fields"] = [
                field.name for field in self._meta.concrete_fields
                if not field.primary_key and field.name != "sent_at"
            ]
        super().save(*args, **kwargs)
        self.send_if_due()

    def send_if_due(self):
        """Push to every device if this notification is due and not yet sent.

        Called on save (immediate notifications) and every minute by Celery beat
        (scheduled ones, see notifications.tasks.send_due_notifications).
        Returns True when the push was queued.
        """
        if self.sent_at is not None or not self.should_send_now():
            return False
        # Claim it in the database first, so a save and the scheduler running
        # at the same moment cannot both push it.
        now = timezone.now()
        if not type(self).objects.filter(pk=self.pk, sent_at__isnull=True).update(sent_at=now):
            return False
        try:
            send_to_all.delay(
                title=self.title,
                body=self.message,
                data={
                    "route": "/notification",
                    "notification_id": str(self.id),
                    "click_action": "FLUTTER_NOTIFICATION_CLICK",
                    "priority": "high"
                },
                image_url="https://africaclimatesummit2.et/media/icons/2649569.png",
                sound="default"
            )
        except Exception:
            # Not queued: release the claim so the scheduler retries it.
            type(self).objects.filter(pk=self.pk).update(sent_at=None)
            raise
        self.sent_at = now
        return True
