from firebase_admin import messaging
from Notification.push_notification.firebase_connect import initialize_firebase
from celery import shared_task
from django.utils import timezone

firebase_app = initialize_firebase()


@shared_task
def send_to_all(title, body, data=None, image_url=None, sound="default"):
    print(f"🔥 Running send_to_all at {timezone.localtime(timezone.now())}")
    try:
        # Notification part (for background display)
        notification = messaging.Notification(
            title=title,
            body=body,
            image=image_url
        )

        # Android config
        android_config = messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(
                # Remove or replace if this icon does not exist in Android project
                icon="ic_stat_ic_notification",
                color="#0A84FF",
                sound=sound,
                click_action="FLUTTER_NOTIFICATION_CLICK"
            )
        )

        # iOS config
        apns_config = messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(
                    sound=sound,
                    category="NEW_MESSAGE"
                )
            )
        )

        # Data payload (always delivered, even in foreground)
        payload_data = {
            "title": title,
            "body": body,
            "image": image_url or "",
            "sound": sound,
            "click_action": "FLUTTER_NOTIFICATION_CLICK"
        }
        if data:
            payload_data.update(data)

        # Final message
        message = messaging.Message(
            notification=notification,   # ensures background notifications work
            android=android_config,
            apns=apns_config,
            data=payload_data,          # ensures foreground works too
            topic="all_devices"
        )

        response = messaging.send(message)
        print(f"✅ Message sent to all devices: {response}")
        return response

    except Exception as e:
        print(f"❌ Failed to send notification: {e}")
        raise e
