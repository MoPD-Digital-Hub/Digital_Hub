from django.db import models
from django.contrib.auth.models import AbstractUser


class Ministry(models.Model):
    """Organization a user belongs to (ministry, agency, institution)."""

    name = models.CharField(max_length=200, unique=True)
    abbreviation = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'ministries'
        ordering = ['name']

    def __str__(self):
        return self.name


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
    ministry = models.ForeignKey(Ministry, null=True, blank=True, on_delete=models.SET_NULL, related_name='users')

    USERNAME_FIELD='email'
    REQUIRED_FIELDS=['first_name','last_name', 'username']