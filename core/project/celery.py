from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')

app = Celery('project')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Keep default routing unless explicit Celery tasks are added.
app.conf.task_routes = {
    "ai.tasks.generate_answer_task": {"queue": "ai_queue"},
}

