from __future__ import absolute_import, unicode_literals
from django.core.mail import send_mail
from celery import shared_task


@shared_task
def send_email(email, token):
    send_mail(
        "Subject here",
        f"MoPD Digital Hub OTP: {token}",
        "mikiyasmebrate2656@gmail.com",
        [email],
        fail_silently=False,
    )

    print("Email sent successfully")