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


class ObtenerDestinatariosReporteTest(TestCase):
    def test_sin_configuracion_devuelve_lista_vacia(self):
        from attendance.utils import obtener_destinatarios_reporte

        self.assertEqual(obtener_destinatarios_reporte('NO_EXISTE'), [])

    def test_configuracion_inactiva_devuelve_lista_vacia(self):
        from attendance.models import ConfiguracionReporte, DestinatarioReporte, TipoReporte
        from attendance.utils import obtener_destinatarios_reporte

        config = ConfiguracionReporte.objects.get(tipo=TipoReporte.DIARIO)
        config.activo = False
        config.save()
        DestinatarioReporte.objects.create(configuracion=config, email='a@example.com', activo=True)

        self.assertEqual(obtener_destinatarios_reporte(TipoReporte.DIARIO), [])

    def test_solo_devuelve_destinatarios_activos(self):
        from attendance.models import ConfiguracionReporte, DestinatarioReporte, TipoReporte
        from attendance.utils import obtener_destinatarios_reporte

        config = ConfiguracionReporte.objects.get(tipo=TipoReporte.SEMANAL)
        # Clear seeded recipients first
        config.destinatarios.all().delete()
        DestinatarioReporte.objects.create(configuracion=config, email='activo@example.com', activo=True)
        DestinatarioReporte.objects.create(configuracion=config, email='inactivo@example.com', activo=False)

        self.assertEqual(obtener_destinatarios_reporte(TipoReporte.SEMANAL), ['activo@example.com'])


class RegistrarEnvioReporteTest(TestCase):
    def test_crea_registro_con_destinatarios_unidos_por_coma(self):
        from attendance.models import TipoReporte, OrigenEnvio
        from attendance.utils import registrar_envio_reporte

        envio = registrar_envio_reporte(
            TipoReporte.MENSUAL, '08/2026', ['a@example.com', 'b@example.com'],
            OrigenEnvio.MANUAL, exitoso=True
        )

        self.assertEqual(envio.destinatarios, 'a@example.com, b@example.com')
        self.assertTrue(envio.exitoso)


class DiaQuincenaActualTest(TestCase):
    def test_devuelve_13_o_28(self):
        from attendance.utils import dia_quincena_actual

        self.assertIn(dia_quincena_actual(), [13, 28])


class GenerarReporteDiarioTest(TestCase):
    def test_sin_destinatarios_registra_envio_fallido(self):
        from attendance.models import ConfiguracionSistema, ConfiguracionReporte, TipoReporte, EnvioReporte
        from attendance.utils import generar_reporte_diario

        ConfiguracionSistema.objects.create(
            hora_entrada='09:00:00', minutos_tolerancia=15,
            email_gerente='gerente@example.com', ruta_red_reportes=''
        )
        config_reporte = ConfiguracionReporte.objects.get(tipo=TipoReporte.DIARIO)
        config_reporte.destinatarios.all().delete()

        resultado = generar_reporte_diario()

        self.assertFalse(resultado.exitoso)
        self.assertEqual(resultado.error, 'Sin destinatarios configurados')
        self.assertEqual(EnvioReporte.objects.filter(tipo=TipoReporte.DIARIO).count(), 1)

    def test_envia_email_a_destinatarios_configurados(self):
        from django.contrib.auth.models import User
        from django.core import mail
        from attendance.models import (
            ConfiguracionSistema, ConfiguracionReporte, DestinatarioReporte,
            TipoReporte, OrigenEnvio
        )
        from attendance.utils import generar_reporte_diario

        ConfiguracionSistema.objects.create(
            hora_entrada='09:00:00', minutos_tolerancia=15,
            email_gerente='gerente@example.com', ruta_red_reportes=''
        )
        config_reporte = ConfiguracionReporte.objects.get(tipo=TipoReporte.DIARIO)
        config_reporte.destinatarios.all().delete()
        DestinatarioReporte.objects.create(configuracion=config_reporte, email='destino@example.com', activo=True)

        resultado = generar_reporte_diario(origen=OrigenEnvio.MANUAL)

        self.assertTrue(resultado.exitoso)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['destino@example.com'])
        self.assertEqual(resultado.origen, OrigenEnvio.MANUAL)


class GenerarReporteSemanalTest(TestCase):
    def test_sin_destinatarios_registra_envio_fallido(self):
        from attendance.models import ConfiguracionSistema, ConfiguracionReporte, TipoReporte, EnvioReporte
        from attendance.utils import generar_reporte_semanal

        ConfiguracionSistema.objects.create(
            hora_entrada='09:00:00', minutos_tolerancia=15,
            email_gerente='gerente@example.com', ruta_red_reportes=''
        )
        config_reporte = ConfiguracionReporte.objects.get(tipo=TipoReporte.SEMANAL)
        config_reporte.destinatarios.all().delete()

        resultado = generar_reporte_semanal()

        self.assertFalse(resultado.exitoso)
        self.assertEqual(EnvioReporte.objects.filter(tipo=TipoReporte.SEMANAL).count(), 1)

    def test_envia_email_con_excel_adjunto(self):
        from django.core import mail
        from attendance.models import ConfiguracionSistema, ConfiguracionReporte, DestinatarioReporte, TipoReporte
        from attendance.utils import generar_reporte_semanal

        ConfiguracionSistema.objects.create(
            hora_entrada='09:00:00', minutos_tolerancia=15,
            email_gerente='gerente@example.com', ruta_red_reportes=''
        )
        config_reporte = ConfiguracionReporte.objects.get(tipo=TipoReporte.SEMANAL)
        config_reporte.destinatarios.all().delete()
        DestinatarioReporte.objects.create(configuracion=config_reporte, email='destino@example.com', activo=True)

        resultado = generar_reporte_semanal()

        self.assertTrue(resultado.exitoso)
        self.assertEqual(len(mail.outbox[0].attachments), 1)
