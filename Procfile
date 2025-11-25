release: echo "[RELEASE] Skipping migrations until DB is provisioned"
web: gunicorn checador.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 30 --graceful-timeout 10 --access-logfile - --error-logfile - --log-level info
