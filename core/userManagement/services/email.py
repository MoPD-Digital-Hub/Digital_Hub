from django.core.mail import send_mail


def send_email():
    send_mail(
        "Subject here",
        "Here is the message.",
        "mikiyasmebrate2656@gmail.com",
        ["mikiyasmebrate@gmail.com"],
        fail_silently=False,
    )