from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from attendance.utils import generar_reporte_semanal


class Command(BaseCommand):
    help = 'Envía el reporte semanal de asistencia todos los jueves'

    def handle(self, *args, **options):
        ahora = timezone.now()

        # Verificar si es jueves (weekday = 3)
        if ahora.weekday() != 3:
            self.stdout.write(self.style.WARNING('Hoy no es jueves. El reporte semanal se envía los jueves.'))
            return

        self.stdout.write('Generando reporte semanal...')
        resultado = generar_reporte_semanal()

        if resultado.exitoso:
            self.stdout.write(self.style.SUCCESS('Reporte semanal enviado exitosamente'))
        else:
            raise CommandError(f'Error al enviar reporte semanal: {resultado.error}')
