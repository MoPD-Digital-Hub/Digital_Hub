from django.db import models
from userManagement.models import CustomUser as User

class Document(models.Model):
    name = models.CharField(null=True, blank=True, max_length=100)
    file = models.FileField(upload_to='documents/')
    is_loaded = models.BooleanField(default=False)

    def __str__(self):
        return self.name

class LoadedFile(models.Model):
    number = models.IntegerField(default=0)


class ChatInstance(models.Model):
    user = models.ForeignKey(User, null=True, blank=True ,on_delete=models.SET_NULL)
    title = models.CharField(null=True, blank=True, max_length=100)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now=True, auto_now_add=False)

    class Meta:
        ordering = ['-created_at']

class QuestionHistory(models.Model):
    question = models.CharField(max_length=500)
    response = models.TextField(null=True , blank=True)
    instance = models.ForeignKey(ChatInstance, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now=True, auto_now_add=False)
    response_at = models.DateTimeField(auto_now=False, auto_now_add=True , null=True , blank=True)

class CatalogEntity(models.Model):
    """Something a question can be about: an indicator, organization, policy
    area or goal. Synced from the time-series and DPMES APIs; the v2 assistant
    resolves names in a question to these rows before fetching any data."""

    INDICATOR = "indicator"
    ORGANIZATION = "organization"
    POLICY_AREA = "policy_area"
    GOAL = "goal"
    KIND_CHOICES = [
        (INDICATOR, "Indicator"),
        (ORGANIZATION, "Organization"),
        (POLICY_AREA, "Policy area"),
        (GOAL, "Goal"),
    ]

    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    # Time-series indicator code, or the DPMES id for everything else.
    external_id = models.CharField(max_length=64)
    code = models.CharField(max_length=64, blank=True)
    name = models.CharField(max_length=500)
    name_am = models.CharField(max_length=500, blank=True)
    aliases = models.JSONField(default=list, blank=True)
    context = models.CharField(max_length=500, blank=True)
    details = models.JSONField(default=dict, blank=True)
    search_text = models.TextField()
    # float32 vector, little-endian; re-embedded only when search_text changes.
    embedding = models.BinaryField(null=True, blank=True)
    embedding_model = models.CharField(max_length=100, blank=True)
    text_hash = models.CharField(max_length=64, blank=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("kind", "external_id")]
        indexes = [models.Index(fields=["kind", "is_active"]), models.Index(fields=["code"])]

    def __str__(self):
        return f"{self.kind}: {self.name}"


class AnswerTrace(models.Model):
    """One v2 answer: what was planned, resolved and fetched, and how long it took."""

    instance = models.ForeignKey(ChatInstance, null=True, blank=True, on_delete=models.SET_NULL)
    question = models.TextField()
    language = models.CharField(max_length=20, blank=True)
    plan = models.JSONField(default=dict, blank=True)
    resolved = models.JSONField(default=list, blank=True)
    tool_calls = models.JSONField(default=list, blank=True)
    unsupported_numbers = models.JSONField(default=list, blank=True)
    answer = models.TextField(blank=True)
    error = models.CharField(max_length=500, blank=True)
    latency_ms = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
