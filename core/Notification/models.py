from django.db import models
from django.utils import timezone
from Notification.tasks.push_notification_task import send_to_all


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
        super().save(*args, **kwargs)

        if self.should_send_now() and (not self.send_at or self.send_at <= timezone.now()):
            # Send immediately
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