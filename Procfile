release: echo "[RELEASE] Skipping migrations until DB is ready"
web: echo "[WEB] Starting web process..." && echo "[WEB] PORT=$PORT" && echo "[WEB] Starting gunicorn..." && gunicorn checador.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --access-logfile - --error-logfile - --log-level info
