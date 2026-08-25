# attendance/management/commands/generar_reporte_tiempo_extra.py
from django.core.management.base import BaseCommand, CommandError
from attendance.utils import generar_reporte_tiempo_extra_mensual


class Command(BaseCommand):
    help = 'Genera el reporte mensual de tiempo extra'

    def handle(self, *args, **options):
        self.stdout.write('Generando reporte mensual de tiempo extra...')
        resultado = generar_reporte_tiempo_extra_mensual()

        if resultado.exitoso:
            self.stdout.write(self.style.SUCCESS('Reporte de tiempo extra generado exitosamente'))
        else:
            raise CommandError(f'Error al generar reporte de tiempo extra: {resultado.error}')


"""
CONFIGURACIÓN DE CRON JOBS EN EL SERVIDOR

Para automatizar estos comandos, agrega lo siguiente al crontab:

# Reporte diario a las 12:05 PM todos los días
5 12 * * * cd /ruta/proyecto && /ruta/venv/bin/python manage.py enviar_reporte_diario

# Reporte quincenal los días 13 y 28 a las 6:00 PM
0 18 13,28 * * cd /ruta/proyecto && /ruta/venv/bin/python manage.py enviar_reporte_quincenal

# Reporte mensual de tiempo extra el primer día de cada mes a las 8:00 AM
0 8 1 * * cd /ruta/proyecto && /ruta/venv/bin/python manage.py generar_reporte_tiempo_extra

Ejecutar crontab -e para editar el crontab
"""
