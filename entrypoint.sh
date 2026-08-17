#!/bin/sh
set -e

python manage.py migrate --noinput

# Mark documents/questions stuck mid-task (e.g. after a kill/restart) as failed
python manage.py recover_stuck_tasks

if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
  python manage.py shell -c "
import os
from django.contrib.auth import get_user_model
User = get_user_model()
username = os.environ['DJANGO_SUPERUSER_USERNAME']
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '')
password = os.environ['DJANGO_SUPERUSER_PASSWORD']
if User.objects.filter(username=username).exists():
    print('Superuser already exists')
else:
    User.objects.create_superuser(username, email, password)
    print('Superuser created')
"
fi

exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers ${GUNICORN_WORKERS:-2} \
  --timeout 300