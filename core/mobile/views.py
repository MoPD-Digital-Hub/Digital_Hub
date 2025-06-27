from django.shortcuts import render
from . models import *


def privacy_policy(request):
    privacy_policy = Setting.objects.get(id=1)
    return render(request , 'privacy_policy.html' , {'privacy_policy':privacy_policy})