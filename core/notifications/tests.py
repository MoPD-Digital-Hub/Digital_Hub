from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from firebase_admin import messaging
from rest_framework.test import APIClient

from notifications.models import DeviceToken, Notification, NotificationCategory
from notifications.tasks import send_due_notifications, send_push_to_user


class NoRealPushTestCase(TestCase):
    """Saving a Notification queues a push to every device: never let a test send one."""

    def setUp(self):
        for target in ("notifications.models.send_to_all", "notifications.tasks.initialize_firebase",
                       "notifications.tasks.messaging.send"):
            patcher = patch(target)
            setattr(self, target.rsplit(".", 1)[1], patcher.start())
            self.addCleanup(patcher.stop)


class NotificationModelTests(NoRealPushTestCase):
    def test_saving_an_active_notification_pushes_it_to_everyone(self):
        notification = Notification.objects.create(title="Report published", message="Q2 is out")
        self.send_to_all.delay.assert_called_once()
        kwargs = self.send_to_all.delay.call_args.kwargs
        self.assertEqual((kwargs["title"], kwargs["body"]), ("Report published", "Q2 is out"))
        self.assertEqual(kwargs["data"]["notification_id"], str(notification.id))

    def test_inactive_scheduled_or_expired_notifications_are_not_pushed(self):
        now = timezone.now()
        Notification.objects.create(title="Off", message="m", is_active=False)
        Notification.objects.create(title="Later", message="m", send_at=now + timedelta(hours=1))
        Notification.objects.create(title="Too late", message="m", expire_at=now - timedelta(hours=1))
        self.send_to_all.delay.assert_not_called()

    def test_editing_a_sent_notification_does_not_push_it_again(self):
        notification = Notification.objects.create(title="Report publshed", message="Q2 is out")
        self.assertIsNotNone(notification.sent_at)
        notification.title = "Report published"          # fixing a typo in the admin
        notification.save()
        Notification.objects.get(pk=notification.pk).save()   # a fresh copy, as the admin loads it
        self.send_to_all.delay.assert_called_once()

    def test_a_notification_held_back_is_pushed_once_when_it_becomes_due(self):
        notification = Notification.objects.create(title="Draft", message="m", is_active=False)
        self.assertIsNone(notification.sent_at)
        notification.is_active = True
        notification.save()
        notification.save()
        self.send_to_all.delay.assert_called_once()
        self.assertIsNotNone(Notification.objects.get(pk=notification.pk).sent_at)

    def test_a_failed_send_is_not_recorded_as_sent(self):
        self.send_to_all.delay.side_effect = ConnectionError("broker down")
        with self.assertRaises(ConnectionError):
            Notification.objects.create(title="t", message="m")
        self.assertIsNone(Notification.objects.get().sent_at)

    def test_should_send_now(self):
        now = timezone.now()
        self.assertTrue(Notification(title="t", message="m", send_at=now - timedelta(minutes=1)).should_send_now())
        self.assertFalse(Notification(title="t", message="m", send_at=now + timedelta(minutes=1)).should_send_now())


class ScheduledNotificationTests(NoRealPushTestCase):
    """send_due_notifications, run every minute by Celery beat."""

    def scheduled(self, **fields):
        notification = Notification.objects.create(title="Launch", message="m", send_at=timezone.now() + timedelta(hours=1),
                                                   **fields)
        self.send_to_all.delay.assert_not_called()        # not due yet
        return notification

    def make_due(self, notification):
        Notification.objects.filter(pk=notification.pk).update(send_at=timezone.now() - timedelta(seconds=5))

    def test_a_scheduled_notification_is_pushed_once_its_time_comes(self):
        notification = self.scheduled()
        self.assertEqual(send_due_notifications(), 0)      # still in the future
        self.make_due(notification)
        self.assertEqual(send_due_notifications(), 1)
        self.assertEqual(send_due_notifications(), 0)      # the next minute: nothing left to send
        self.send_to_all.delay.assert_called_once()
        self.assertEqual(self.send_to_all.delay.call_args.kwargs["data"]["notification_id"], str(notification.id))
        self.assertIsNotNone(Notification.objects.get(pk=notification.pk).sent_at)

    def test_inactive_and_expired_notifications_are_never_pushed(self):
        off = self.scheduled(is_active=False)
        late = self.scheduled(expire_at=timezone.now() + timedelta(minutes=30))
        for notification in (off, late):
            self.make_due(notification)
        Notification.objects.filter(pk=late.pk).update(expire_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(send_due_notifications(), 0)
        self.send_to_all.delay.assert_not_called()

    def test_a_push_that_could_not_be_queued_is_retried(self):
        self.send_to_all.delay.side_effect = ConnectionError("broker down")
        with self.assertRaises(ConnectionError):
            Notification.objects.create(title="t", message="m")
        self.assertEqual(send_due_notifications(), 0)      # still down: logged, not raised
        self.send_to_all.delay.side_effect = None
        self.assertEqual(send_due_notifications(), 1)

    def test_a_save_and_the_scheduler_cannot_both_push(self):
        notification = self.scheduled()
        self.make_due(notification)
        first, second = Notification.objects.get(pk=notification.pk), Notification.objects.get(pk=notification.pk)
        self.assertTrue(first.send_if_due())
        self.assertFalse(second.send_if_due())             # the other copy still thinks it is unsent
        self.send_to_all.delay.assert_called_once()

    def test_saving_a_stale_copy_does_not_clear_or_repeat_the_send(self):
        notification = self.scheduled()
        stale = Notification.objects.get(pk=notification.pk)   # e.g. an admin form opened before it was sent
        self.make_due(notification)
        self.assertEqual(send_due_notifications(), 1)
        stale.title = "Launch day"
        stale.save()
        saved = Notification.objects.get(pk=notification.pk)
        self.assertEqual(saved.title, "Launch day")
        self.assertIsNotNone(saved.sent_at)
        self.send_to_all.delay.assert_called_once()

    def test_beat_runs_the_task_every_minute(self):
        from django.conf import settings

        from project.celery import app

        entry = settings.CELERY_BEAT_SCHEDULE["send-due-notifications"]
        self.assertEqual((entry["task"], entry["schedule"]), ("notifications.tasks.send_due_notifications", 60.0))
        self.assertIn(entry["task"], app.tasks)
        self.assertEqual(app.conf.beat_schedule["send-due-notifications"]["task"], entry["task"])


class NotificationApiTests(NoRealPushTestCase):
    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user(username="n", email="n@example.test", password="Str0ng!pass")
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_list_and_filter_by_category(self):
        alerts = NotificationCategory.objects.create(title="Alerts")
        Notification.objects.create(title="A", message="m", category=alerts)
        Notification.objects.create(title="B", message="m")
        everything = self.api.get("/api/notification/", HTTP_HOST="localhost").json()
        self.assertEqual(everything["result"], "SUCCESS")
        self.assertEqual(sorted(n["title"] for n in everything["data"]), ["A", "B"])
        filtered = self.api.get(f"/api/notification/?category={alerts.id}", HTTP_HOST="localhost").json()["data"]
        self.assertEqual([(n["title"], n["category"]["title"]) for n in filtered], [("A", "Alerts")])
        categories = self.api.get("/api/notification/categories", HTTP_HOST="localhost").json()["data"]
        self.assertEqual([c["title"] for c in categories], ["Alerts"])

    def test_registering_a_device_moves_the_token_to_the_current_user(self):
        other = get_user_model().objects.create_user(username="o", email="o@example.test", password="Str0ng!pass")
        DeviceToken.objects.create(user=other, token="tok-1", platform="ios")
        response = self.api.post("/api/notification/devices", {"token": "tok-1", "platform": "windows-phone"},
                                 format="json", HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        device = DeviceToken.objects.get()
        self.assertEqual((device.user, device.platform), (self.user, "android"))  # unknown platform -> android

    def test_device_token_is_required_and_delete_only_removes_your_own(self):
        response = self.api.post("/api/notification/devices", {}, format="json", HTTP_HOST="localhost")
        self.assertEqual((response.status_code, response.json()["message"]), (400, "token is required"))
        other = get_user_model().objects.create_user(username="o", email="o@example.test", password="Str0ng!pass")
        DeviceToken.objects.create(user=other, token="theirs")
        DeviceToken.objects.create(user=self.user, token="mine")
        for token in ("theirs", "mine"):
            self.api.delete("/api/notification/devices", {"token": token}, format="json", HTTP_HOST="localhost")
        self.assertEqual(list(DeviceToken.objects.values_list("token", flat=True)), ["theirs"])

    def test_devices_need_sign_in(self):
        response = APIClient().post("/api/notification/devices", {"token": "t"}, format="json", HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 403)


class PushToUserTests(NoRealPushTestCase):
    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user(username="p", email="p@example.test", password="Str0ng!pass")

    def test_no_devices_sends_nothing(self):
        with patch("notifications.tasks.messaging.send_each_for_multicast") as send:
            self.assertEqual(send_push_to_user(self.user.id, "t", "b"), 0)
        send.assert_not_called()
        self.initialize_firebase.assert_not_called()

    def test_dead_tokens_are_removed_and_successes_counted(self):
        for token in ("good", "gone", "flaky"):
            DeviceToken.objects.create(user=self.user, token=token)
        results = {"good": None, "gone": messaging.UnregisteredError("unregistered"), "flaky": Exception("timeout")}

        def fake_send(message):
            return Mock(success_count=1, responses=[Mock(exception=results[t]) for t in message.tokens])

        with patch("notifications.tasks.messaging.send_each_for_multicast", side_effect=fake_send) as send:
            sent = send_push_to_user(self.user.id, "Abebe", "Selam", data={"conversation_id": 7})
        self.assertEqual(sent, 1)
        message = send.call_args.args[0]
        self.assertEqual(message.data["conversation_id"], "7")           # FCM data values must be strings
        self.assertEqual((message.notification.title, message.notification.body), ("Abebe", "Selam"))
        self.assertEqual(sorted(DeviceToken.objects.values_list("token", flat=True)), ["flaky", "good"])


class SentAtMigrationTests(TransactionTestCase):
    """0003 marks notifications that were already pushed, so an old one is not pushed again when edited."""

    def test_existing_due_notifications_are_marked_sent(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        executor = MigrationExecutor(connection)
        executor.migrate([("Notification", "0002_initial")])
        try:
            Old = executor.loader.project_state([("Notification", "0002_initial")]).apps.get_model(
                "Notification", "Notification")
            now = timezone.now()
            Old.objects.create(title="already pushed", message="m")
            Old.objects.create(title="scheduled", message="m", send_at=now + timedelta(days=1))
            Old.objects.create(title="switched off", message="m", is_active=False)
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate([("Notification", "0003_notification_sent_at")])
        sent = {n.title: n.sent_at is not None for n in Notification.objects.all()}
        self.assertEqual(sent, {"already pushed": True, "scheduled": False, "switched off": False})
        pushed = Notification.objects.get(title="already pushed")
        self.assertEqual(pushed.sent_at, pushed.created_at)
