from django.db import models
from userManagement.models import CustomUser as User

class Document(models.Model):
    file = models.FileField(upload_to='documents/')
    is_loaded = models.BooleanField(default=False)

class LoadedFile(models.Model):
    number = models.IntegerField(default=0)


class ChatInstance(models.Model):
    user = models.ForeignKey(User, null=True, blank=True ,on_delete=models.SET_NULL)
    title = models.CharField(null=True, blank=True, max_length=100)
    created_at = models.DateTimeField(auto_now=True, auto_now_add=False)

    class Meta:
        ordering = ['-created_at']

class QuestionHistory(models.Model):
    question = models.CharField(max_length=500)
    response = models.TextField(null=True , blank=True)
    instance = models.ForeignKey(ChatInstance, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now=True, auto_now_add=False)
    response_at = models.DateTimeField(auto_now=False, auto_now_add=True , null=True , blank=True)