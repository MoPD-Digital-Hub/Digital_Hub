"""Downloading a generated document.

GET /api/ai-chat/documents/<id>/?t=<signed token>: the link in the answer. The
signed token is enough (the mobile app opens it in the phone's browser, with no
session); a signed-in owner may also download without it.
"""

from urllib.parse import quote

from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from ai.documents import design, service
from ai.models import GeneratedDocument

GONE = "This file is no longer available. Ask Admas AI to make it again."


@require_GET
def download_document(request, document_id):
    document = GeneratedDocument.objects.filter(id=document_id).first()
    user = request.user if request.user.is_authenticated else None
    allowed = document is not None and (
        service.token_matches(document_id, request.GET.get("t", ""))
        or (user is not None and document.user_id == user.id)
    )
    if not allowed:
        return HttpResponse("Not found.", status=404, content_type="text/plain; charset=utf-8")
    if document.expires_at <= timezone.now():
        return HttpResponse(GONE, status=410, content_type="text/plain; charset=utf-8")
    response = HttpResponse(bytes(document.content), content_type=design.CONTENT_TYPES[document.format])
    response["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(document.filename)}"
    response["Content-Length"] = str(document.size)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
