from django.db import models
from userManagement.models import CustomUser
from django.contrib.contenttypes.fields import GenericRelation
from comment.models import Comment


class Post(models.Model):
    user = models.ForeignKey(CustomUser, null=True, on_delete=models.SET_NULL)
    content = models.TextField()
    tag = models.CharField(max_length=300)
    comment = GenericRelation(Comment)
    like_count = models.IntegerField(default=0)


class Images(models.Model):
    path = models.ImageField()
    for_post = models.ForeignKey(Post,null=True ,on_delete=models.SET_NULL)

class Like(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    post = models.ForeignKey(Post,on_delete=models.CASCADE )


