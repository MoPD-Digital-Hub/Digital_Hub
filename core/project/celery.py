from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')

app = Celery('project')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()



app.conf.task_routes = {
    'AI.tasks.handle_question_task': {'queue': 'async_worker'}
}


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')