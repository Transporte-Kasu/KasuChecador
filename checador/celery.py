# proyecto/celery.py
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proyecto.settings')

app = Celery('proyecto')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Configuración de tareas periódicas
app.conf.beat_schedule = {
    'reporte-diario': {
        'task': 'attendance.tasks.enviar_reporte_diario_task',
        'schedule': crontab(hour=12, minute=5),  # 12:05 PM diario
    },
    'reporte-semanal': {
        'task': 'attendance.tasks.enviar_reporte_semanal_task',
        'schedule': crontab(day_of_week=4, hour=12, minute=0),  # Todos los jueves a las 12:00 PM
    },
    'reporte-tiempo-extra-mensual': {
        'task': 'attendance.tasks.generar_reporte_tiempo_extra_task',
        'schedule': crontab(day_of_month=1, hour=8, minute=0),  # Día 1 de cada mes, 8:00 AM
    },
}


# attendance/tasks.py
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

@shared_task
def enviar_reporte_diario_task():
    """Tarea para enviar el reporte diario"""
    try:
        from attendance.utils import generar_reporte_diario
        generar_reporte_diario()
        return "Reporte diario enviado exitosamente"
    except Exception as e:
        return f"Error al enviar reporte diario: {str(e)}"

@shared_task
def enviar_reporte_semanal_task():
    """Tarea para enviar el reporte semanal (todos los jueves)"""
    try:
        from attendance.utils import generar_reporte_semanal
        generar_reporte_semanal()
        return "Reporte semanal enviado exitosamente"
    except Exception as e:
        return f"Error al enviar reporte semanal: {str(e)}"

@shared_task
def generar_reporte_tiempo_extra_task():
    """Tarea para generar el reporte mensual de tiempo extra"""
    try:
        from attendance.utils import generar_reporte_tiempo_extra_mensual
        generar_reporte_tiempo_extra_mensual()
        return "Reporte de tiempo extra generado exitosamente"
    except Exception as e:
        return f"Error al generar reporte de tiempo extra: {str(e)}"


# proyecto/__init__.py
from .celery import app as celery_app

__all__ = ('celery_app',)


"""
COMANDOS PARA EJECUTAR CELERY:

1. Iniciar el worker de Celery:
celery -A proyecto worker -l info

2. Iniciar el beat scheduler (tareas programadas):
celery -A proyecto beat -l info

3. Para producción, usar ambos en un solo comando:
celery -A proyecto worker -B -l info

4. Para monitoreo (opcional):
celery -A proyecto flower

NOTA: Asegúrate de tener Redis instalado y corriendo:
sudo apt-get install redis-server
sudo systemctl start redis
"""