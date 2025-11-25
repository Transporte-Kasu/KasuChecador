release: python manage.py migrate && python manage.py collectstatic --noinput
web: gunicorn checador.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --worker-class sync --max-requests 1000 --max-requests-jitter 50 --timeout 120
