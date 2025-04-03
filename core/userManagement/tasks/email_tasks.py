from __future__ import absolute_import, unicode_literals
import os
from pathlib import Path
from django.core.mail import send_mail
from celery import shared_task
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(os.path.join(BASE_DIR.parent, '.env'))


@shared_task
def send_email(email, token):
    send_mail(
        "Subject here",
        f"MoPD Digital Hub OTP: {token}",
        os.getenv('EMAIL'),
        [email],
        fail_silently=False,
    )

    print("Email sent successfully")