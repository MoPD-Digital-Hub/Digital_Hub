from django.shortcuts import render
from . models import *


def privacy_policy(request):
    return render(request, 'privacy_policy.html')