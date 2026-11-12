from django.conf import settings
from django.db import models

# Home sections in their default order. The first group is personal (built from
# what the user follows); the second is the sections every user already sees.
SECTIONS = (
    "my_organizations",
    "my_policy_areas",
    "pinned_kpis",
    "pinned_indicators",
    "movers",
    "needs_attention",
    "topics",
    "ministry_scorecard",
    "program_summaries",
    "high_frequency",
    "projects",
    "initiatives",
)


class UserPreference(models.Model):
    """One user's dashboard settings. Missing rows mean the defaults below."""

    QUARTER, YEAR = "quarter", "year"
    PERIOD_CHOICES = [(QUARTER, "Quarter"), (YEAR, "Year")]

    BOTH, RISING, DECLINING = "both", "rising", "declining"
    DIRECTION_CHOICES = [(BOTH, "Rising and declining"), (RISING, "Rising only"), (DECLINING, "Declining only")]

    ALL, FOLLOWING = "all", "following"
    SCOPE_CHOICES = [(ALL, "Everything"), (FOLLOWING, "Only what I follow")]

    ENGLISH, AMHARIC = "en", "am"
    LANGUAGE_CHOICES = [(ENGLISH, "English"), (AMHARIC, "Amharic")]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="preference")
    # [{"key": "movers", "visible": true}, ...] in display order; see ordered_sections().
    sections = models.JSONField(default=list, blank=True)
    # Scores are compared between the two latest periods of this length.
    period = models.CharField(max_length=10, choices=PERIOD_CHOICES, default=QUARTER)
    movers_direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, default=BOTH)
    movers_scope = models.CharField(max_length=10, choices=SCOPE_CHOICES, default=ALL)
    movers_limit = models.PositiveSmallIntegerField(default=5)
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default=ENGLISH)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Preferences of {self.user}"

    def ordered_sections(self):
        """Every known section once: the user's saved order first, then any
        section added since they last saved (visible, in the default order)."""
        result, seen = [], set()
        for entry in self.sections or []:
            key = entry.get("key") if isinstance(entry, dict) else None
            if key in SECTIONS and key not in seen:
                seen.add(key)
                result.append({"key": key, "visible": bool(entry.get("visible", True))})
        result += [{"key": key, "visible": True} for key in SECTIONS if key not in seen]
        return result

    def shows(self, key):
        return any(entry["key"] == key and entry["visible"] for entry in self.ordered_sections())


class Follow(models.Model):
    """Something a user chose to see on their dashboard.

    The item lives in another service, so it is referenced by kind and that
    service's id: DPMES for organizations, policy areas and KPIs, the
    time-series service for indicators. The name is copied when the user
    follows it, so lists render without a call to the other service.
    """

    ORGANIZATION, POLICY_AREA, KPI, INDICATOR = "organization", "policy_area", "kpi", "indicator"
    KIND_CHOICES = [
        (ORGANIZATION, "Organization"),
        (POLICY_AREA, "Policy area"),
        (KPI, "KPI"),
        (INDICATOR, "Indicator"),
    ]
    KINDS = tuple(kind for kind, _label in KIND_CHOICES)
    # Most a user may follow of one kind; keeps the dashboard to a bounded number of calls.
    LIMIT_PER_KIND = 30

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="follows")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    external_id = models.CharField(max_length=64)
    # KPIs only: the DPMES organization whose records for the KPI are shown.
    organization_id = models.CharField(max_length=64, blank=True)
    name = models.CharField(max_length=500)
    name_am = models.CharField(max_length=500, blank=True)
    code = models.CharField(max_length=64, blank=True)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["kind", "position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "kind", "external_id", "organization_id"], name="unique_follow_per_user",
            ),
        ]
        indexes = [models.Index(fields=["user", "kind"])]

    def __str__(self):
        return f"{self.user} follows {self.kind} {self.name}"
