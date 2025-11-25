release: python manage.py migrate --noinput && python manage.py collectstatic --noinput
web: echo "[WEB] Starting web process..." && echo "[WEB] PORT=$PORT" && python test_startup.py && echo "[WEB] Starting gunicorn..." && gunicorn checador.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --access-logfile - --error-logfile - --log-level info
