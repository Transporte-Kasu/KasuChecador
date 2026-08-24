from django.db import migrations


TIPOS_REPORTE = ['DIARIO', 'SEMANAL', 'QUINCENAL', 'MENSUAL', 'TIEMPO_EXTRA']
EMAIL_EXTRA_HARDCODEADO = 'zuly.becerra@loginco.com.mx'
TIPOS_CON_EMAIL_EXTRA = ['DIARIO', 'SEMANAL']
TIPOS_CON_EMAIL_GERENTE = ['DIARIO', 'SEMANAL', 'QUINCENAL', 'MENSUAL']


def seed_configuracion_reporte(apps, schema_editor):
    """Crea la configuración de los 5 tipos de reporte y precarga los
    destinatarios que hoy están hardcodeados en attendance/utils.py,
    para no perder envíos al desplegar."""
    ConfiguracionReporte = apps.get_model('attendance', 'ConfiguracionReporte')
    DestinatarioReporte = apps.get_model('attendance', 'DestinatarioReporte')
    ConfiguracionSistema = apps.get_model('attendance', 'ConfiguracionSistema')

    configs = {}
    for tipo in TIPOS_REPORTE:
        configs[tipo] = ConfiguracionReporte.objects.create(tipo=tipo, activo=True)

    config_sistema = ConfiguracionSistema.objects.first()
    if config_sistema and config_sistema.email_gerente:
        for tipo in TIPOS_CON_EMAIL_GERENTE:
            DestinatarioReporte.objects.create(
                configuracion=configs[tipo],
                email=config_sistema.email_gerente,
                nombre='Gerente (migrado)',
                activo=True
            )

    for tipo in TIPOS_CON_EMAIL_EXTRA:
        DestinatarioReporte.objects.create(
            configuracion=configs[tipo],
            email=EMAIL_EXTRA_HARDCODEADO,
            nombre='Destinatario adicional (migrado)',
            activo=True
        )


def reverse_seed_configuracion_reporte(apps, schema_editor):
    ConfiguracionReporte = apps.get_model('attendance', 'ConfiguracionReporte')
    ConfiguracionReporte.objects.filter(tipo__in=TIPOS_REPORTE).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0006_configuracionreporte_destinatarioreporte_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_configuracion_reporte, reverse_seed_configuracion_reporte),
    ]
