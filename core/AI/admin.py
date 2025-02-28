from django.contrib import admin
from .models import *


admin.site.register(Document)
admin.site.register(LoadedFile)
admin.site.register(ChatInstance)
admin.site.register(QuestionHistory)