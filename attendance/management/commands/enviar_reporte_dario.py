from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from attendance.utils import generar_reporte_diario


class Command(BaseCommand):
    help = 'Envía el reporte diario de asistencia después de las 12:00 PM'

    def handle(self, *args, **options):
        ahora = timezone.now()

        if ahora.hour < 12:
            self.stdout.write(self.style.WARNING('Aún no es hora de enviar el reporte (después de las 12:00 PM)'))
            return

        self.stdout.write('Generando reporte diario...')
        resultado = generar_reporte_diario()

        if resultado.exitoso:
            self.stdout.write(self.style.SUCCESS('Reporte diario enviado exitosamente'))
        else:
            raise CommandError(f'Error al enviar reporte diario: {resultado.error}')
