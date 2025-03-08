from django.db import models

# Create your models here.
class App(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.FileField(upload_to='app/icons/')

    def __str__(self):
        return self.name