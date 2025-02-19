from django.db import models
from userManagement.models import CustomUser as User

class Video(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    like = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
    
    def add_like(self):
        self.like += 1
        self.save()
    
    def remove_like(self):
        if self.like > 0:
            self.like -= 1
            self.save()
    
class VideoComment(models.Model):
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    reply = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.comment

class VideoCommentLike(models.Model):
    comment = models.ForeignKey(VideoComment, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    like = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)  

    def __str__(self):
        return self.user.email

    def add_like(self):
        self.like += 1
        self.save()
    
    def remove_like(self):
        if self.like > 0:
            self.like -= 1
            self.save()

class VideoLike(models.Model):
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.email