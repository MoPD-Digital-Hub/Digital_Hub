from django.db import models
from userManagement.models import CustomUser as User

class Video(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    like = models.IntegerField(default=0)
    video = models.FileField(upload_to='videos/')
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
    replay = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    comment = models.TextField()
    like = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.comment
    
    def add_like(self):
        self.like += 1
        self.save()
    
    def remove_like(self):
        if self.like > 0:
            self.like -= 1
            self.save()
    
    
class VideoCommentLike(models.Model):
    comment = models.ForeignKey(VideoComment, on_delete=models.CASCADE, related_name='comment_likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)  

    def __str__(self):
        return self.user.email

class VideoLike(models.Model):
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='video_likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.email