from django.core.management.base import BaseCommand
from attendance.utils import generar_reporte_mensual


class Command(BaseCommand):
    help = 'Genera y envía el reporte mensual de asistencias en Excel (por defecto, del mes anterior)'

    def add_arguments(self, parser):
        parser.add_argument('--mes', type=int, help='Mes a procesar (1-12). Por defecto: mes anterior')
        parser.add_argument('--anio', type=int, help='Año a procesar. Por defecto: año actual')

    def handle(self, *args, **options):
        mes = options['mes']
        anio = options['anio']

        resultado = generar_reporte_mensual(mes=mes, anio=anio)

        if resultado.exitoso:
            self.stdout.write(self.style.SUCCESS(f'✓ Reporte mensual enviado a: {resultado.destinatarios}'))
        else:
            self.stdout.write(self.style.ERROR(f'❌ No se pudo enviar el reporte mensual: {resultado.error}'))
