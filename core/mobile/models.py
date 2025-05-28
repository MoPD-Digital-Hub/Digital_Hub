from django.db import models
from ckeditor.fields import RichTextField

# Create your models here.
class App(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.FileField(upload_to='app/icons/')
    route = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return self.name
    
class Setting(models.Model):
    name = models.CharField(max_length=150)
    content = RichTextField()

class FAQ(models.Model):
    faq_type = [
        ('general', 'General'),
        ('account', 'Account'),
        ('app', 'App'),
        ('other', 'Other'),
    ]
    question = models.CharField(max_length=150)
    answer = models.TextField()
    type = models.CharField( choices=faq_type , max_length=50)

class ContactUs(models.Model):
    name = models.CharField(max_length=50)
    content = models.CharField(max_length=150)
    icon = models.FileField(("/icons"), upload_to=None, max_length=100)
