from django.db import models
from django.contrib.auth.models import AbstractUser


class Ministry(models.Model):
    """Organization a user belongs to (ministry, agency, institution).

    Seeded from the DPMES all-ministries API (manage.py seed_ministries);
    external_id is the ministry's id in DPMES, used to fetch its detail
    and performance data.
    """

    name = models.CharField(max_length=200, unique=True)
    name_am = models.CharField(max_length=200, blank=True)
    abbreviation = models.CharField(max_length=50, blank=True)
    external_id = models.IntegerField(unique=True, null=True, blank=True, help_text="Ministry id in the DPMES service.")
    image = models.URLField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'ministries'
        ordering = ['name']

    def __str__(self):
        return self.name


def default_ministry():
    """MoPD is every user's default organization."""
    from django.db.utils import OperationalError, ProgrammingError

    try:
        ministry = Ministry.objects.filter(abbreviation__iexact='MoPD').first()
    except (OperationalError, ProgrammingError):
        # The ministry table doesn't exist yet (makemigrations/migrate on a
        # fresh database evaluates this default before creating it).
        return None
    return ministry.id if ministry else None


class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    photo = models.ImageField(upload_to='User/Photo', null=True, blank=True)
    is_first_time = models.BooleanField(default = True)
    excellence = models.CharField(max_length=100, blank=True, null=True, default='Mr')
    bio = models.CharField(max_length=100, null=True, blank=True)
    token = models.CharField(max_length=600, null=True, blank=True)
    tokenExpiration = models.DateTimeField(null=True, blank=True)
    trial = models.IntegerField(default=0)
    waiting_period = models.DateTimeField(null=True, blank=True)
    ministry = models.ForeignKey(
        Ministry, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='users', default=default_ministry,
    )

    USERNAME_FIELD='email'
    REQUIRED_FIELDS=['first_name','last_name', 'username']

    def save(self, *args, **kwargs):
        # A user always belongs to an organization; fall back to MoPD.
        if self.ministry_id is None:
            self.ministry_id = default_ministry()
        super().save(*args, **kwargs)