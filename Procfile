release: python check_env.py && python manage.py migrate --noinput && python manage.py collectstatic --noinput
web: gunicorn checador.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --access-logfile - --error-logfile - --log-level debug
