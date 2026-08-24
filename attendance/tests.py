from django.test import TestCase


class ReporteModelsTest(TestCase):
    def test_tipo_es_unico(self):
        from django.db import IntegrityError
        from attendance.models import ConfiguracionReporte

        ConfiguracionReporte.objects.create(tipo='PRUEBA_UNICIDAD')
        with self.assertRaises(IntegrityError):
            ConfiguracionReporte.objects.create(tipo='PRUEBA_UNICIDAD')

    def test_destinatario_reporte_str_incluye_nombre(self):
        from attendance.models import ConfiguracionReporte, DestinatarioReporte

        config = ConfiguracionReporte.objects.create(tipo='PRUEBA_DESTINATARIO')
        destinatario = DestinatarioReporte.objects.create(
            configuracion=config, email='ana@example.com', nombre='Ana'
        )
        self.assertIn('Ana', str(destinatario))

    def test_envio_reporte_str_incluye_estado(self):
        from attendance.models import EnvioReporte, TipoReporte, OrigenEnvio

        envio = EnvioReporte.objects.create(
            tipo=TipoReporte.DIARIO,
            periodo_descripcion='24/08/2026',
            destinatarios='a@example.com',
            origen=OrigenEnvio.AUTOMATICO,
            exitoso=True
        )
        self.assertIn('OK', str(envio))


class ConfiguracionReporteSeedTest(TestCase):
    def test_seed_crea_las_5_configuraciones(self):
        from attendance.models import ConfiguracionReporte, TipoReporte

        self.assertEqual(ConfiguracionReporte.objects.count(), 5)
        tipos = set(ConfiguracionReporte.objects.values_list('tipo', flat=True))
        self.assertEqual(tipos, set(TipoReporte.values))

    def test_configuraciones_estan_activas_por_defecto(self):
        from attendance.models import ConfiguracionReporte

        self.assertFalse(ConfiguracionReporte.objects.filter(activo=False).exists())
