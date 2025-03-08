from django.db import models

# Create your models here.
class Apps(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.TextField()

    def __str__(self):
        return self.name