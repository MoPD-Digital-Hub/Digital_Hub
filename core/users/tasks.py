from __future__ import absolute_import, unicode_literals

import logging
import os
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(os.path.join(BASE_DIR.parent, '.env'))

LOGGER = logging.getLogger(__name__)

RESET_CODE_EXPIRY_MINUTES = 20

RESET_EMAIL = {
    "subject": "Reset your MoNS Digital Hub password",
    "preheader": "Use this code to reset your password. It expires in 20 minutes.",
    "heading": "Reset your password",
    "intro": (
        "We received a request to reset the password for your MoNS Digital Hub "
        "account. Enter the code below to choose a new password."
    ),
    "code_label": "Password reset code",
}


@shared_task
def send_email(email, token):
    """Email a password reset code as a multipart (plain text + HTML) message."""
    context = {
        **RESET_EMAIL,
        "code": token,
        "expiry_minutes": RESET_CODE_EXPIRY_MINUTES,
        "year": timezone.now().year,
    }

    text_body = render_to_string("emails/password_reset_code.txt", context)
    html_body = render_to_string("emails/password_reset_code.html", context)

    message = EmailMultiAlternatives(
        subject=RESET_EMAIL["subject"],
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[email],
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)

    LOGGER.info("Sent password reset code email to %s", email)
