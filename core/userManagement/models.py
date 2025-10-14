from django.db import models
from django.contrib.auth.models import AbstractUser


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

    USERNAME_FIELD='email'
    REQUIRED_FIELDS=['first_name','last_name', 'username']