from django.core.mail import send_mail


def send_email(email, token):
    send_mail(
        "Subject here",
        f"MoPD Digital Hub Password Reset Token: {token}",
        "mikiyasmebrate2656@gmail.com",
        [email],
        fail_silently=False,
    )

    print("Email sent successfully")