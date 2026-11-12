"""Building, storing and linking a document."""

from datetime import timedelta

from asgiref.sync import sync_to_async
from django.conf import settings
from django.core import signing
from django.urls import reverse
from django.utils import timezone

from ai.documents import design, pdf, slides, word
from ai.models import GeneratedDocument

BUILDERS = {"pptx": slides.build, "docx": word.build, "pdf": pdf.build}
SALT = "ai-document"
MAX_BYTES = 20 * 1024 * 1024


def build(document_format, outline, datasets, sources, language):
    """(bytes, number of slides, sections or pages)."""
    return BUILDERS[document_format](outline, datasets, sources, language)


def token(document_id):
    return signing.dumps(str(document_id), salt=SALT)


def token_matches(document_id, value):
    try:
        return signing.loads(value, salt=SALT, max_age=timedelta(days=settings.AI_DOCUMENT_DAYS)) == str(document_id)
    except signing.BadSignature:
        return False


def download_url(document):
    """An absolute link (for the mobile app, opened in the phone's browser) when SITE_URL is set."""
    path = reverse("ai-document", args=[document.id]) + "?t=" + token(document.id)
    return settings.SITE_URL + path


@sync_to_async
def quota_left(instance):
    limit = settings.AI_DOCUMENTS_DAILY_LIMIT
    if not limit or instance is None or not instance.user_id:
        return True
    today = timezone.localdate()
    return GeneratedDocument.objects.filter(user_id=instance.user_id, created_at__date=today).count() < limit


@sync_to_async
def save(instance, document_format, title, content):
    return GeneratedDocument.objects.create(
        instance=instance, user_id=getattr(instance, "user_id", None), title=title[:200], format=document_format,
        filename=design.safe_filename(title, design.EXTENSIONS[document_format]), content=content,
        size=len(content), expires_at=timezone.now() + timedelta(days=settings.AI_DOCUMENT_DAYS))


def delete_expired():
    deleted, _ = GeneratedDocument.objects.filter(expires_at__lte=timezone.now()).delete()
    return deleted
