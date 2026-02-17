import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings
from django_apscheduler.jobstores import DjangoJobStore
from django_apscheduler.models import DjangoJobExecution

logger = logging.getLogger(__name__)


def job_reporte_diario():
    """Envia reporte diario de asistencia - L-V a las 12:05 PM"""
    from attendance.utils import generar_reporte_diario
    logger.info("Ejecutando reporte diario de asistencia")
    generar_reporte_diario()


def job_reporte_semanal():
    """Envia reporte semanal - Jueves a las 12:00 PM"""
    from attendance.utils import generar_reporte_semanal
    logger.info("Ejecutando reporte semanal de asistencia")
    generar_reporte_semanal()


def delete_old_job_executions(max_age=604_800):
    """Limpia ejecuciones de jobs mayores a 7 dias"""
    DjangoJobExecution.objects.delete_old_job_executions(max_age)


def start():
    try:
        scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
        scheduler.add_jobstore(DjangoJobStore(), "default")

        scheduler.add_job(
            job_reporte_diario,
            trigger=CronTrigger(
                day_of_week="mon-fri", hour=12, minute=5,
                timezone=settings.TIME_ZONE,
            ),
            id="reporte_diario",
            max_instances=1,
            replace_existing=True,
        )

        scheduler.add_job(
            job_reporte_semanal,
            trigger=CronTrigger(
                day_of_week="thu", hour=12, minute=0,
                timezone=settings.TIME_ZONE,
            ),
            id="reporte_semanal",
            max_instances=1,
            replace_existing=True,
        )

        scheduler.add_job(
            delete_old_job_executions,
            trigger=CronTrigger(
                day_of_week="mon", hour=0, minute=0,
                timezone=settings.TIME_ZONE,
            ),
            id="delete_old_job_executions",
            max_instances=1,
            replace_existing=True,
        )

        scheduler.start()
        logger.info("Scheduler iniciado con jobs: reporte_diario, reporte_semanal, delete_old_job_executions")
    except Exception:
        logger.exception("No se pudo iniciar el scheduler. Verifica que las migraciones esten aplicadas.")
