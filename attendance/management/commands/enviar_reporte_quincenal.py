# attendance/management/commands/enviar_reporte_quincenal.py
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from attendance.utils import generar_reporte_quincenal


class Command(BaseCommand):
    help = 'Envía el reporte quincenal (días 13 y 28)'

    def handle(self, *args, **options):
        hoy = timezone.now().date()

        if hoy.day != 13 and hoy.day != 28:
            self.stdout.write(self.style.WARNING(f'Hoy no es día de reporte quincenal (día {hoy.day})'))
            return

        self.stdout.write(f'Generando reporte quincenal para el día {hoy.day}...')
        resultado = generar_reporte_quincenal(hoy.day)

        if resultado.exitoso:
            self.stdout.write(self.style.SUCCESS('Reporte quincenal enviado exitosamente'))
        else:
            raise CommandError(f'Error al enviar reporte quincenal: {resultado.error}')
