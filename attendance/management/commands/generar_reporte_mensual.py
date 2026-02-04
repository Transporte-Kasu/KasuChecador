from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import EmailMessage
from django.conf import settings
from datetime import timedelta
from calendar import monthrange
import os

from attendance.models import ConfiguracionSistema
from attendance.utils import generar_excel_reporte_mensual


class Command(BaseCommand):
    help = 'Genera el reporte mensual de asistencias en Excel del mes anterior'

    def add_arguments(self, parser):
        parser.add_argument(
            '--mes',
            type=int,
            help='Mes a procesar (1-12). Por defecto: mes anterior',
        )
        parser.add_argument(
            '--anio',
            type=int,
            help='Año a procesar. Por defecto: año actual',
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Email alternativo para enviar el reporte',
        )

    def handle(self, *args, **options):
        # Determinar mes y año
        hoy = timezone.now().date()
        
        if options['mes']:
            mes = options['mes']
            anio = options['anio'] if options['anio'] else hoy.year
        else:
            # Mes anterior por defecto
            primer_dia_mes_actual = hoy.replace(day=1)
            ultimo_dia_mes_anterior = primer_dia_mes_actual - timedelta(days=1)
            mes = ultimo_dia_mes_anterior.month
            anio = ultimo_dia_mes_anterior.year
        
        self.stdout.write(f"Generando reporte mensual para {mes}/{anio}...")
        
        # Obtener configuración
        config = ConfiguracionSistema.objects.first()
        if not config:
            self.stdout.write(self.style.ERROR('No se encontró configuración del sistema'))
            return
        
        # Generar Excel
        try:
            excel_buffer = generar_excel_reporte_mensual(mes, anio)
            nombre_excel = f"reporte_mensual_{anio}_{mes:02d}.xlsx"
            
            self.stdout.write(self.style.SUCCESS(f'✓ Archivo Excel generado: {nombre_excel}'))
            
            # Guardar en ruta de red si está configurada
            if config.ruta_red_reportes:
                ruta_completa = os.path.join(config.ruta_red_reportes, nombre_excel)
                try:
                    with open(ruta_completa, 'wb') as f:
                        f.write(excel_buffer.getvalue())
                    self.stdout.write(self.style.SUCCESS(f'✓ Archivo guardado en: {ruta_completa}'))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'⚠ No se pudo guardar en red: {e}'))
            
            # Enviar por email
            email_destino = options['email'] if options['email'] else config.email_gerente
            
            # Resetear buffer para adjuntar
            excel_buffer.seek(0)
            
            email = EmailMessage(
                subject=f'Reporte Mensual de Asistencias - {mes:02d}/{anio}',
                body=f'''
Reporte mensual de asistencias del período {mes:02d}/{anio}.

El archivo Excel adjunto contiene:
- Hoja 1: Resumen por empleado (días asistidos, retardos, faltas, permisos)
- Hoja 2: Detalle de todas las asistencias del mes
- Hoja 3: Empleados con retardos y faltas

Este reporte se genera automáticamente el día 1 de cada mes.
                '''.strip(),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email_destino]
            )
            
            email.attach(nombre_excel, excel_buffer.read(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            email.send(fail_silently=False)
            
            self.stdout.write(self.style.SUCCESS(f'✓ Email enviado a: {email_destino}'))
            self.stdout.write(self.style.SUCCESS('✅ Reporte mensual generado exitosamente'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error al generar reporte: {str(e)}'))
            raise
