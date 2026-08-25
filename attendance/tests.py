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
            Empleado, TipoReporte, OrigenEnvio
        )
        from attendance.utils import generar_reporte_diario

        ConfiguracionSistema.objects.create(
            hora_entrada='09:00:00', minutos_tolerancia=15,
            email_gerente='gerente@example.com', ruta_red_reportes=''
        )
        config_reporte = ConfiguracionReporte.objects.get(tipo=TipoReporte.DIARIO)
        config_reporte.destinatarios.all().delete()
        DestinatarioReporte.objects.create(configuracion=config_reporte, email='destino@example.com', activo=True)

        user = User.objects.create_user(
            username='empleado_reporte_diario', first_name='Test', last_name='Empleado'
        )
        Empleado.objects.create(user=user, codigo_empleado='EMPRPTDIARIO', activo=True)

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


class GenerarReporteQuincenalTest(TestCase):
    def test_sin_destinatarios_registra_envio_fallido(self):
        from attendance.models import ConfiguracionSistema, TipoReporte, EnvioReporte
        from attendance.utils import generar_reporte_quincenal

        ConfiguracionSistema.objects.create(
            hora_entrada='09:00:00', minutos_tolerancia=15,
            email_gerente='gerente@example.com', ruta_red_reportes=''
        )

        resultado = generar_reporte_quincenal(13)

        self.assertFalse(resultado.exitoso)
        self.assertEqual(EnvioReporte.objects.filter(tipo=TipoReporte.QUINCENAL).count(), 1)

    def test_envia_email_para_segunda_quincena(self):
        from django.core import mail
        from attendance.models import ConfiguracionSistema, ConfiguracionReporte, DestinatarioReporte, TipoReporte
        from attendance.utils import generar_reporte_quincenal

        ConfiguracionSistema.objects.create(
            hora_entrada='09:00:00', minutos_tolerancia=15,
            email_gerente='gerente@example.com', ruta_red_reportes=''
        )
        config_reporte = ConfiguracionReporte.objects.get(tipo=TipoReporte.QUINCENAL)
        DestinatarioReporte.objects.create(configuracion=config_reporte, email='destino@example.com', activo=True)

        resultado = generar_reporte_quincenal(28)

        self.assertTrue(resultado.exitoso)
        self.assertIn('Segunda Quincena', resultado.periodo_descripcion)
        self.assertEqual(len(mail.outbox), 1)


class GenerarReporteTiempoExtraMensualTest(TestCase):
    def test_sin_destinatarios_registra_envio_fallido(self):
        from attendance.models import ConfiguracionSistema, TipoReporte, EnvioReporte
        from attendance.utils import generar_reporte_tiempo_extra_mensual

        ConfiguracionSistema.objects.create(
            hora_entrada='09:00:00', minutos_tolerancia=15,
            email_gerente='gerente@example.com', ruta_red_reportes=''
        )

        resultado = generar_reporte_tiempo_extra_mensual()

        self.assertFalse(resultado.exitoso)
        self.assertEqual(EnvioReporte.objects.filter(tipo=TipoReporte.TIEMPO_EXTRA).count(), 1)

    def test_envia_email_sin_requerir_ruta_de_red(self):
        from django.core import mail
        from attendance.models import ConfiguracionSistema, ConfiguracionReporte, DestinatarioReporte, TipoReporte
        from attendance.utils import generar_reporte_tiempo_extra_mensual

        ConfiguracionSistema.objects.create(
            hora_entrada='09:00:00', minutos_tolerancia=15,
            email_gerente='gerente@example.com', ruta_red_reportes=''
        )
        config_reporte = ConfiguracionReporte.objects.get(tipo=TipoReporte.TIEMPO_EXTRA)
        DestinatarioReporte.objects.create(configuracion=config_reporte, email='destino@example.com', activo=True)

        resultado = generar_reporte_tiempo_extra_mensual()

        self.assertTrue(resultado.exitoso)
        self.assertEqual(len(mail.outbox), 1)


class GenerarReporteMensualTest(TestCase):
    def test_sin_destinatarios_registra_envio_fallido(self):
        from attendance.models import ConfiguracionSistema, TipoReporte, EnvioReporte
        from attendance.utils import generar_reporte_mensual

        ConfiguracionSistema.objects.create(
            hora_entrada='09:00:00', minutos_tolerancia=15,
            email_gerente='gerente@example.com', ruta_red_reportes=''
        )

        resultado = generar_reporte_mensual(mes=7, anio=2026)

        self.assertFalse(resultado.exitoso)
        self.assertEqual(EnvioReporte.objects.filter(tipo=TipoReporte.MENSUAL).count(), 1)

    def test_envia_email_con_excel_para_mes_especificado(self):
        from django.core import mail
        from attendance.models import ConfiguracionSistema, ConfiguracionReporte, DestinatarioReporte, TipoReporte
        from attendance.utils import generar_reporte_mensual

        ConfiguracionSistema.objects.create(
            hora_entrada='09:00:00', minutos_tolerancia=15,
            email_gerente='gerente@example.com', ruta_red_reportes=''
        )
        config_reporte = ConfiguracionReporte.objects.get(tipo=TipoReporte.MENSUAL)
        DestinatarioReporte.objects.create(configuracion=config_reporte, email='destino@example.com', activo=True)

        resultado = generar_reporte_mensual(mes=7, anio=2026)

        self.assertTrue(resultado.exitoso)
        self.assertEqual(resultado.periodo_descripcion, '07/2026')
        self.assertEqual(len(mail.outbox[0].attachments), 1)


class GenerarReporteMensualCommandTest(TestCase):
    def test_comando_reporta_error_sin_destinatarios(self):
        from io import StringIO
        from django.core.management import call_command
        from attendance.models import ConfiguracionSistema

        ConfiguracionSistema.objects.create(
            hora_entrada='09:00:00', minutos_tolerancia=15,
            email_gerente='gerente@example.com', ruta_red_reportes=''
        )

        out = StringIO()
        call_command('generar_reporte_mensual', '--mes=7', '--anio=2026', stdout=out)

        self.assertIn('No se pudo enviar', out.getvalue())


class DashboardLoginRequiredTest(TestCase):
    def test_dashboard_redirige_a_login_si_no_hay_sesion(self):
        from django.urls import reverse

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)


class EnviarReporteViewTest(TestCase):
    def test_requiere_login(self):
        from django.urls import reverse

        response = self.client.post(reverse('enviar_reporte', args=['DIARIO']))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)

    def test_tipo_invalido_da_404(self):
        from django.contrib.auth.models import User
        from django.urls import reverse

        user = User.objects.create_user(username='gerente', password='clave12345', is_staff=True)
        self.client.force_login(user)

        response = self.client.post(reverse('enviar_reporte', args=['NO_EXISTE']))

        self.assertEqual(response.status_code, 404)

    def test_envio_manual_exitoso_muestra_mensaje_y_registra_origen(self):
        from django.contrib.auth.models import User
        from django.contrib.messages import get_messages
        from django.urls import reverse
        from attendance.models import (
            ConfiguracionSistema, ConfiguracionReporte, DestinatarioReporte,
            Empleado, TipoReporte, OrigenEnvio, EnvioReporte
        )

        ConfiguracionSistema.objects.create(
            hora_entrada='09:00:00', minutos_tolerancia=15,
            email_gerente='gerente@example.com', ruta_red_reportes=''
        )
        config_reporte = ConfiguracionReporte.objects.get(tipo=TipoReporte.DIARIO)
        DestinatarioReporte.objects.create(configuracion=config_reporte, email='destino@example.com', activo=True)

        empleado_user = User.objects.create_user(
            username='empleado_envio_manual', first_name='Test', last_name='Empleado'
        )
        Empleado.objects.create(user=empleado_user, codigo_empleado='EMPENVIOMANUAL', activo=True)

        user = User.objects.create_user(username='gerente2', password='clave12345', is_staff=True)
        self.client.force_login(user)

        response = self.client.post(reverse('enviar_reporte', args=['DIARIO']))

        self.assertEqual(response.status_code, 302)
        mensajes = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any('enviado a' in m for m in mensajes), mensajes)
        envio = EnvioReporte.objects.filter(tipo=TipoReporte.DIARIO, origen=OrigenEnvio.MANUAL).first()
        self.assertIsNotNone(envio)
        self.assertTrue(envio.exitoso)
        self.assertEqual(envio.enviado_por, user)


class ConfiguracionReporteAdminActionTest(TestCase):
    def test_accion_enviar_reporte_ahora_registra_envio_manual(self):
        from django.contrib.auth.models import User
        from django.urls import reverse
        from attendance.models import (
            ConfiguracionSistema, ConfiguracionReporte, DestinatarioReporte,
            Empleado, TipoReporte, OrigenEnvio, EnvioReporte
        )

        ConfiguracionSistema.objects.create(
            hora_entrada='09:00:00', minutos_tolerancia=15,
            email_gerente='gerente@example.com', ruta_red_reportes=''
        )
        config_reporte = ConfiguracionReporte.objects.get(tipo=TipoReporte.DIARIO)
        DestinatarioReporte.objects.create(configuracion=config_reporte, email='destino@example.com', activo=True)

        empleado_user = User.objects.create_user(
            username='empleado_admin_accion', first_name='Test', last_name='Empleado'
        )
        Empleado.objects.create(user=empleado_user, codigo_empleado='EMPADMINACCION', activo=True)

        admin_user = User.objects.create_superuser(
            username='admin1', email='admin1@example.com', password='clave12345'
        )
        self.client.force_login(admin_user)

        changelist_url = reverse('admin:attendance_configuracionreporte_changelist')
        response = self.client.post(changelist_url, {
            'action': 'enviar_reporte_ahora',
            '_selected_action': [str(config_reporte.pk)],
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        envio = EnvioReporte.objects.filter(tipo=TipoReporte.DIARIO, origen=OrigenEnvio.MANUAL).first()
        self.assertIsNotNone(envio)
        self.assertTrue(envio.exitoso)


class DashboardReportesContextTest(TestCase):
    def test_dashboard_incluye_info_de_reportes(self):
        from django.contrib.auth.models import User
        from django.urls import reverse
        from attendance.models import ConfiguracionReporte, DestinatarioReporte, TipoReporte

        config_reporte = ConfiguracionReporte.objects.get(tipo=TipoReporte.SEMANAL)
        # La migración 0007 ya precarga destinatarios activos para SEMANAL
        # (email del gerente y el correo adicional hardcodeado); se toma el
        # conteo previo como base en vez de asumir que parte de cero.
        destinatarios_previos = config_reporte.destinatarios.filter(activo=True).count()
        DestinatarioReporte.objects.create(configuracion=config_reporte, email='a@example.com', activo=True)

        user = User.objects.create_user(username='gerente3', password='clave12345', is_staff=True)
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        reportes_info = response.context['reportes_info']
        self.assertEqual(len(reportes_info), 5)
        semanal_info = next(r for r in reportes_info if r['tipo'] == TipoReporte.SEMANAL)
        self.assertEqual(semanal_info['destinatarios_count'], destinatarios_previos + 1)
        self.assertContains(response, 'Enviar ahora')


class ReporteManagementCommandsExitCodeTest(TestCase):
    """
    Verifica que enviar_reporte_dario, enviar_reporte_semanal,
    enviar_reporte_quincenal y generar_reporte_tiempo_extra ya no reporten
    éxito cuando el envío falla. Antes de este fix, ahora que
    generar_reporte_* nunca lanza excepciones (registra el fallo en
    EnvioReporte en vez de propagar), el try/except de estos comandos
    quedaba muerto y siempre imprimía SUCCESS.
    """

    def _configuracion_sistema(self):
        from attendance.models import ConfiguracionSistema
        return ConfiguracionSistema.objects.create(
            hora_entrada='09:00:00', minutos_tolerancia=15,
            email_gerente='gerente@example.com', ruta_red_reportes=''
        )

    def test_enviar_reporte_dario_falla_con_commanderror_sin_destinatarios(self):
        from datetime import datetime
        from unittest.mock import patch
        from django.core.management import call_command
        from django.core.management.base import CommandError
        from django.utils import timezone as tz
        from attendance.models import ConfiguracionReporte, TipoReporte

        self._configuracion_sistema()
        # La migración 0007 precarga un destinatario activo para DIARIO
        # (correo hardcodeado histórico); se limpia para probar el caso
        # real "sin destinatarios configurados".
        ConfiguracionReporte.objects.get(tipo=TipoReporte.DIARIO).destinatarios.all().delete()
        hora_valida = tz.make_aware(datetime(2026, 8, 24, 13, 0, 0))

        with patch('attendance.management.commands.enviar_reporte_dario.timezone.now', return_value=hora_valida):
            with self.assertRaises(CommandError):
                call_command('enviar_reporte_dario')

    def test_enviar_reporte_dario_exitoso_con_destinatarios(self):
        from datetime import datetime
        from io import StringIO
        from unittest.mock import patch
        from django.core.management import call_command
        from django.utils import timezone as tz
        from attendance.models import ConfiguracionReporte, DestinatarioReporte, TipoReporte, Empleado
        from django.contrib.auth.models import User

        self._configuracion_sistema()
        config_reporte = ConfiguracionReporte.objects.get(tipo=TipoReporte.DIARIO)
        DestinatarioReporte.objects.create(configuracion=config_reporte, email='destino@example.com', activo=True)
        user = User.objects.create_user(username='empleado_cmd_diario', first_name='Test', last_name='Empleado')
        Empleado.objects.create(user=user, codigo_empleado='EMPCMDDIARIO', activo=True)

        hora_valida = tz.make_aware(datetime(2026, 8, 24, 13, 0, 0))
        out = StringIO()
        with patch('attendance.management.commands.enviar_reporte_dario.timezone.now', return_value=hora_valida):
            call_command('enviar_reporte_dario', stdout=out)

        self.assertIn('exitosamente', out.getvalue())

    def test_enviar_reporte_semanal_falla_con_commanderror_sin_destinatarios(self):
        from datetime import datetime
        from unittest.mock import patch
        from django.core.management import call_command
        from django.core.management.base import CommandError
        from django.utils import timezone as tz
        from attendance.models import ConfiguracionReporte, TipoReporte

        self._configuracion_sistema()
        # La migración 0007 precarga un destinatario activo para SEMANAL
        # (correo hardcodeado histórico); se limpia para probar el caso
        # real "sin destinatarios configurados".
        ConfiguracionReporte.objects.get(tipo=TipoReporte.SEMANAL).destinatarios.all().delete()
        # 2026-08-27 es jueves (weekday() == 3)
        jueves = tz.make_aware(datetime(2026, 8, 27, 12, 0, 0))

        with patch('attendance.management.commands.enviar_reporte_semanal.timezone.now', return_value=jueves):
            with self.assertRaises(CommandError):
                call_command('enviar_reporte_semanal')

    def test_enviar_reporte_quincenal_falla_con_commanderror_sin_destinatarios(self):
        from datetime import datetime
        from unittest.mock import patch
        from django.core.management import call_command
        from django.core.management.base import CommandError
        from django.utils import timezone as tz

        self._configuracion_sistema()
        dia_13 = tz.make_aware(datetime(2026, 8, 13, 12, 0, 0))

        with patch('attendance.management.commands.enviar_reporte_quincenal.timezone.now', return_value=dia_13):
            with self.assertRaises(CommandError):
                call_command('enviar_reporte_quincenal')

    def test_generar_reporte_tiempo_extra_falla_con_commanderror_sin_destinatarios(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError

        self._configuracion_sistema()

        with self.assertRaises(CommandError):
            call_command('generar_reporte_tiempo_extra')
