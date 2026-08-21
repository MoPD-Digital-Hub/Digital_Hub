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

OTP_EXPIRY_MINUTES = 20

# Copy for each context in which we send a one-time code. Keeping these
# separate means the login mail never talks about resetting a password.
EMAIL_CONTEXTS = {
    "login": {
        "subject": "Your MoPD Digital Hub sign-in code",
        "preheader": "Use this code to finish signing in. It expires in 20 minutes.",
        "heading": "Confirm it's you",
        "intro": (
            "We received a request to sign in to your MoPD Digital Hub account. "
            "Enter the code below to complete sign-in."
        ),
        "code_label": "Sign-in code",
    },
    "reset": {
        "subject": "Reset your MoPD Digital Hub password",
        "preheader": "Use this code to reset your password. It expires in 20 minutes.",
        "heading": "Reset your password",
        "intro": (
            "We received a request to reset the password for your MoPD Digital Hub "
            "account. Enter the code below to choose a new password."
        ),
        "code_label": "Password reset code",
    },
}


@shared_task
def send_email(email, token, purpose="login"):
    """Send a one-time code as a multipart (plain text + HTML) message.

    `purpose` selects the copy: "login" for the sign-in OTP, "reset" for the
    password reset code. Unknown values fall back to the login wording.
    """
    context_copy = EMAIL_CONTEXTS.get(purpose) or EMAIL_CONTEXTS["login"]

    context = {
        **context_copy,
        "code": token,
        "expiry_minutes": OTP_EXPIRY_MINUTES,
        "year": timezone.now().year,
    }

    text_body = render_to_string("emails/otp_code.txt", context)
    html_body = render_to_string("emails/otp_code.html", context)

    message = EmailMultiAlternatives(
        subject=context_copy["subject"],
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[email],
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)

    LOGGER.info("Sent %s code email to %s", purpose, email)
