# Gestión de destinatarios y envío manual de reportes — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir configurar destinatarios por tipo de reporte (Diario, Semanal, Quincenal, Mensual, Tiempo Extra) desde el Django admin, disparar el envío manual de cualquiera desde el Dashboard o el admin, y dejar un registro auditable de cada envío.

**Architecture:** Tres modelos nuevos en `attendance/models.py` (`ConfiguracionReporte`, `DestinatarioReporte`, `EnvioReporte`) reemplazan los correos hardcodeados en `attendance/utils.py`. Las funciones `generar_reporte_*` existentes se refactorizan para resolver destinatarios desde la BD y registrar cada intento de envío (éxito o fallo) sin relanzar excepciones. Una nueva vista protegida por login dispara el envío manual; una acción de admin hace lo mismo desde `/admin/`.

**Tech Stack:** Django 5.2 (ORM, admin, `django.contrib.messages`, `django.contrib.auth.decorators.login_required`), `EmailMultiAlternatives`/`EmailMessage` sobre el backend SMTP de SendGrid ya configurado, `django.test.TestCase` para pruebas.

## Global Constraints

- Envío síncrono, sin cola/Celery — el volumen de destinatarios es bajo.
- Ninguna función de envío relanza excepciones de `email.send()`: cada resultado (éxito o error) se registra en `EnvioReporte` y el flujo continúa.
- No hay login propio en la app: la protección usa `/admin/login/` de Django vía `LOGIN_URL`.
- No se modifica el contenido/diseño HTML de los reportes existentes — solo se cambia de dónde vienen los destinatarios y cómo se registra el resultado.
- Nomenclatura en español, consistente con el resto del código (`ConfiguracionReporte`, `activo`, `destinatarios`, etc.).
- Cada función `generar_reporte_*` debe devolver la instancia `EnvioReporte` que registró (siempre, en cada camino de salida) — este es el contrato que usan la vista y la acción de admin.
- Spec completo: `docs/superpowers/specs/2026-08-24-envio-reportes-design.md`.

---

## Task 1: Modelos de reporte y migración de esquema

**Files:**
- Modify: `attendance/models.py` (agregar al final, después de `AsignacionTurnoDiaria` en la línea 646)
- Create: `attendance/migrations/0006_configuracionreporte_destinatarioreporte_envioreporte.py` (autogenerada)
- Test: `attendance/tests.py`

**Interfaces:**
- Produces:
  - `TipoReporte(models.TextChoices)`: `DIARIO`, `SEMANAL`, `QUINCENAL`, `MENSUAL`, `TIEMPO_EXTRA`
  - `OrigenEnvio(models.TextChoices)`: `MANUAL`, `AUTOMATICO`
  - `ConfiguracionReporte(tipo: str, activo: bool)` — `tipo` único
  - `DestinatarioReporte(configuracion: FK ConfiguracionReporte related_name='destinatarios', email: str, nombre: str, activo: bool)`
  - `EnvioReporte(tipo, fecha_hora, periodo_descripcion, destinatarios, origen, enviado_por: FK User nullable, exitoso: bool, error: str)`, `Meta.ordering = ['-fecha_hora']`

- [ ] **Step 1: Agregar los modelos a `attendance/models.py`**

Al final del archivo (después de la clase `AsignacionTurnoDiaria`, línea 646), agregar:

```python

# ========== SISTEMA DE ENVÍO DE REPORTES ==========

class TipoReporte(models.TextChoices):
    DIARIO = 'DIARIO', 'Diario'
    SEMANAL = 'SEMANAL', 'Semanal'
    QUINCENAL = 'QUINCENAL', 'Quincenal'
    MENSUAL = 'MENSUAL', 'Mensual'
    TIEMPO_EXTRA = 'TIEMPO_EXTRA', 'Tiempo Extra'

class OrigenEnvio(models.TextChoices):
    MANUAL = 'MANUAL', 'Manual'
    AUTOMATICO = 'AUTOMATICO', 'Automático'

class ConfiguracionReporte(models.Model):
    """Configuración de destinatarios por tipo de reporte"""
    tipo = models.CharField(max_length=20, choices=TipoReporte.choices, unique=True)
    activo = models.BooleanField(
        default=True,
        help_text="Si está desactivado, no se envía ni manual ni automáticamente"
    )

    def __str__(self):
        return self.get_tipo_display()

    class Meta:
        verbose_name = "Configuración de Reporte"
        verbose_name_plural = "Configuraciones de Reportes"

class DestinatarioReporte(models.Model):
    """Destinatario de email para un tipo de reporte"""
    configuracion = models.ForeignKey(ConfiguracionReporte, on_delete=models.CASCADE, related_name='destinatarios')
    email = models.EmailField()
    nombre = models.CharField(max_length=100, blank=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre or self.email} ({self.configuracion.get_tipo_display()})"

    class Meta:
        verbose_name = "Destinatario de Reporte"
        verbose_name_plural = "Destinatarios de Reportes"

class EnvioReporte(models.Model):
    """Bitácora de envíos de reportes (manuales y automáticos)"""
    tipo = models.CharField(max_length=20, choices=TipoReporte.choices)
    fecha_hora = models.DateTimeField(auto_now_add=True)
    periodo_descripcion = models.CharField(max_length=200)
    destinatarios = models.TextField(help_text="Snapshot de a quién se envió, separado por coma")
    origen = models.CharField(max_length=20, choices=OrigenEnvio.choices)
    enviado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    exitoso = models.BooleanField()
    error = models.TextField(blank=True)

    def __str__(self):
        estado = "OK" if self.exitoso else "ERROR"
        return f"{self.get_tipo_display()} - {self.fecha_hora.strftime('%d/%m/%Y %H:%M')} - {estado}"

    class Meta:
        verbose_name = "Envío de Reporte"
        verbose_name_plural = "Envíos de Reportes"
        ordering = ['-fecha_hora']
```

- [ ] **Step 2: Generar la migración de esquema**

Run: `python manage.py makemigrations attendance`

Expected output (el nombre exacto puede variar ligeramente; anótalo, se usa como dependencia en Task 2):
```
Migrations for 'attendance':
  attendance/migrations/0006_configuracionreporte_destinatarioreporte_envioreporte.py
    - Create model ConfiguracionReporte
    - Create model DestinatarioReporte
    - Create model EnvioReporte
```

- [ ] **Step 3: Escribir las pruebas**

Agregar al final de `attendance/tests.py`:

```python
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
```

- [ ] **Step 4: Aplicar la migración y correr las pruebas**

Run: `python manage.py migrate attendance`
Expected: `Applying attendance.0006_..._configuracionreporte_destinatarioreporte_envioreporte... OK`

Run: `python manage.py test attendance.tests.ReporteModelsTest -v 2`
Expected: 3 tests, `OK`

- [ ] **Step 5: Commit**

```bash
git add attendance/models.py attendance/migrations/0006_*.py attendance/tests.py
git commit -m "feat: Add ConfiguracionReporte, DestinatarioReporte and EnvioReporte models"
```

---

## Task 2: Migración de datos — seed y preservación de destinatarios actuales

**Files:**
- Create: `attendance/migrations/0007_seed_configuracion_reporte.py`
- Test: `attendance/tests.py`

**Interfaces:**
- Consumes: modelos de Task 1 (`ConfiguracionReporte`, `DestinatarioReporte`), `ConfiguracionSistema` (ya existente, campo `email_gerente`)
- Produces: 5 filas de `ConfiguracionReporte` en la BD (una por `TipoReporte`), con `DestinatarioReporte` precargados a partir de `ConfiguracionSistema.email_gerente` (si existe) para DIARIO/SEMANAL/QUINCENAL/MENSUAL, y el correo `zuly.becerra@loginco.com.mx` para DIARIO/SEMANAL.

- [ ] **Step 1: Escribir la migración de datos**

Crear `attendance/migrations/0007_seed_configuracion_reporte.py` (ajustar la dependencia si el nombre de archivo de Task 1 fue distinto):

```python
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
        ('attendance', '0006_configuracionreporte_destinatarioreporte_envioreporte'),
    ]

    operations = [
        migrations.RunPython(seed_configuracion_reporte, reverse_seed_configuracion_reporte),
    ]
```

- [ ] **Step 2: Escribir las pruebas**

Agregar al final de `attendance/tests.py`:

```python
class ConfiguracionReporteSeedTest(TestCase):
    def test_seed_crea_las_5_configuraciones(self):
        from attendance.models import ConfiguracionReporte, TipoReporte

        self.assertEqual(ConfiguracionReporte.objects.count(), 5)
        tipos = set(ConfiguracionReporte.objects.values_list('tipo', flat=True))
        self.assertEqual(tipos, set(TipoReporte.values))

    def test_configuraciones_estan_activas_por_defecto(self):
        from attendance.models import ConfiguracionReporte

        self.assertFalse(ConfiguracionReporte.objects.filter(activo=False).exists())
```

Nota: en la base de datos de pruebas las migraciones corren contra una BD vacía (sin `ConfiguracionSistema` todavía), así que estas pruebas solo verifican que se crean las 5 configuraciones — no verifican el precargado de `email_gerente`, que solo aplica al desplegar contra la BD real (ver Rollout al final de este plan).

- [ ] **Step 3: Aplicar la migración y correr las pruebas**

Run: `python manage.py migrate attendance`
Expected: `Applying attendance.0007_seed_configuracion_reporte... OK`

Run: `python manage.py test attendance.tests.ConfiguracionReporteSeedTest -v 2`
Expected: 2 tests, `OK`

- [ ] **Step 4: Commit**

```bash
git add attendance/migrations/0007_seed_configuracion_reporte.py attendance/tests.py
git commit -m "feat: Seed default report recipient configuration"
```

---

## Task 3: Helpers de destinatarios y bitácora en `utils.py`

**Files:**
- Modify: `attendance/utils.py:5-8` (imports), y agregar funciones nuevas después de `obtener_horario_esperado` (línea 163)
- Test: `attendance/tests.py`

**Interfaces:**
- Consumes: `ConfiguracionReporte`, `DestinatarioReporte`, `EnvioReporte`, `TipoReporte`, `OrigenEnvio` (Task 1)
- Produces:
  - `obtener_destinatarios_reporte(tipo: str) -> list[str]`
  - `registrar_envio_reporte(tipo, periodo_descripcion, destinatarios: list[str], origen, enviado_por=None, exitoso=True, error='') -> EnvioReporte`
  - `dia_quincena_actual() -> int` (13 o 28)

- [ ] **Step 1: Actualizar el import de modelos en `attendance/utils.py`**

Reemplazar (líneas 5-8):

```python
from .models import (
    Asistencia, TipoMovimiento, Empleado, ConfiguracionSistema, TiempoExtra, TipoHorario,
    HorarioDiaSemana, AsignacionTurnoRotativo, TipoSistemaHorario
)
```

por:

```python
from .models import (
    Asistencia, TipoMovimiento, Empleado, ConfiguracionSistema, TiempoExtra, TipoHorario,
    HorarioDiaSemana, AsignacionTurnoRotativo, TipoSistemaHorario,
    ConfiguracionReporte, DestinatarioReporte, EnvioReporte, TipoReporte, OrigenEnvio
)
```

- [ ] **Step 2: Agregar los helpers**

Insertar después de `obtener_horario_esperado` (después de la línea 163, antes de `def enviar_email_visitante`):

```python

def obtener_destinatarios_reporte(tipo):
    """Devuelve la lista de emails activos configurados para un tipo de reporte"""
    try:
        config = ConfiguracionReporte.objects.get(tipo=tipo)
    except ConfiguracionReporte.DoesNotExist:
        return []

    if not config.activo:
        return []

    return list(
        config.destinatarios.filter(activo=True).values_list('email', flat=True)
    )


def registrar_envio_reporte(tipo, periodo_descripcion, destinatarios, origen, enviado_por=None, exitoso=True, error=''):
    """Crea el registro de auditoría de un envío de reporte"""
    return EnvioReporte.objects.create(
        tipo=tipo,
        periodo_descripcion=periodo_descripcion,
        destinatarios=', '.join(destinatarios),
        origen=origen,
        enviado_por=enviado_por,
        exitoso=exitoso,
        error=error,
    )


def dia_quincena_actual():
    """Devuelve 13 o 28 según qué quincena está en curso hoy"""
    hoy = timezone.now().date()
    return 13 if hoy.day <= 13 else 28
```

- [ ] **Step 3: Escribir las pruebas**

Agregar al final de `attendance/tests.py`:

```python
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
```

- [ ] **Step 4: Correr las pruebas**

Run: `python manage.py test attendance.tests.ObtenerDestinatariosReporteTest attendance.tests.RegistrarEnvioReporteTest attendance.tests.DiaQuincenaActualTest -v 2`
Expected: 6 tests, `OK`

- [ ] **Step 5: Commit**

```bash
git add attendance/utils.py attendance/tests.py
git commit -m "feat: Add report recipient and delivery-log helpers to utils.py"
```

---

## Task 4: Refactorizar `generar_reporte_diario` y `generar_reporte_semanal`

**Files:**
- Modify: `attendance/utils.py:391-514` (`generar_reporte_diario`), `attendance/utils.py:240-388` (`generar_reporte_semanal`)
- Test: `attendance/tests.py`

**Interfaces:**
- Consumes: `obtener_destinatarios_reporte`, `registrar_envio_reporte` (Task 3)
- Produces: `generar_reporte_diario(origen=OrigenEnvio.AUTOMATICO, enviado_por=None) -> EnvioReporte`, `generar_reporte_semanal(origen=OrigenEnvio.AUTOMATICO, enviado_por=None) -> EnvioReporte`

- [ ] **Step 1: Reemplazar `generar_reporte_diario` completo**

Reemplazar la función completa (líneas 391-514) por:

```python
def generar_reporte_diario(origen=OrigenEnvio.AUTOMATICO, enviado_por=None):
    """Genera y envía el reporte diario después de las 12:00 PM"""
    hoy = timezone.now().date()
    periodo_descripcion = hoy.strftime('%d/%m/%Y')

    config = ConfiguracionSistema.objects.first()
    if not config:
        return registrar_envio_reporte(
            TipoReporte.DIARIO, periodo_descripcion, [], origen,
            enviado_por=enviado_por, exitoso=False, error='No se encontró configuración del sistema'
        )

    destinatarios = obtener_destinatarios_reporte(TipoReporte.DIARIO)
    if not destinatarios:
        return registrar_envio_reporte(
            TipoReporte.DIARIO, periodo_descripcion, [], origen,
            enviado_por=enviado_por, exitoso=False, error='Sin destinatarios configurados'
        )

    # Asistencias del día
    asistencias_entrada = Asistencia.objects.filter(
        fecha=hoy,
        tipo_movimiento=TipoMovimiento.ENTRADA
    ).select_related('empleado', 'empleado__user')

    total_empleados = Empleado.objects.filter(activo=True).count()
    llegaron = asistencias_entrada.count()
    retardos = asistencias_entrada.filter(retardo=True)

    # Empleados con retardos consecutivos (últimos 5 días)
    fecha_inicio = hoy - timedelta(days=5)
    empleados_retardos_consecutivos = []

    for empleado in Empleado.objects.filter(activo=True):
        retardos_count = Asistencia.objects.filter(
            empleado=empleado,
            fecha__gte=fecha_inicio,
            fecha__lte=hoy,
            tipo_movimiento=TipoMovimiento.ENTRADA,
            retardo=True
        ).count()

        if retardos_count >= 3:
            empleados_retardos_consecutivos.append({
                'nombre': empleado.user.get_full_name(),
                'codigo': empleado.codigo_empleado,
                'retardos': retardos_count
            })

    # Generar HTML del reporte
    html_reporte = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
            th {{ background-color: #3b82f6; color: white; }}
            tr:nth-child(even) {{ background-color: #f2f2f2; }}
            .resumen {{ background-color: #eff6ff; padding: 20px; border-radius: 8px; margin: 20px 0; }}
            .alerta {{ background-color: #fef2f2; padding: 15px; border-left: 4px solid #ef4444; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <h1>Reporte Diario de Asistencia</h1>
        <p><strong>Fecha:</strong> {hoy.strftime('%d/%m/%Y')}</p>

        <div class="resumen">
            <h2>Resumen</h2>
            <p><strong>Total de Empleados:</strong> {total_empleados}</p>
            <p><strong>Asistieron:</strong> {llegaron} ({(llegaron/total_empleados*100):.1f}%)</p>
            <p><strong>Retardos del Día:</strong> {retardos.count()}</p>
        </div>

        <h2>Retardos del Día</h2>
        <table>
            <tr>
                <th>Empleado</th>
                <th>Código</th>
                <th>Tipo de Horario</th>
                <th>Hora de Entrada</th>
                <th>Minutos de Retardo</th>
            </tr>
    """

    for asistencia in retardos:
        tipo_horario_nombre = asistencia.empleado.tipo_horario.nombre if asistencia.empleado.tipo_horario else 'Estándar'
        html_reporte += f"""
            <tr>
                <td>{asistencia.empleado.user.get_full_name()}</td>
                <td>{asistencia.empleado.codigo_empleado}</td>
                <td>{tipo_horario_nombre}</td>
                <td>{asistencia.hora.strftime('%H:%M')}</td>
                <td>{asistencia.minutos_retardo}</td>
            </tr>
        """

    html_reporte += "</table>"

    if empleados_retardos_consecutivos:
        html_reporte += """
        <div class="alerta">
            <h2>⚠️ Atención: Retardos Consecutivos</h2>
            <p>Los siguientes empleados tienen 3 o más retardos en los últimos 5 días:</p>
            <table>
                <tr>
                    <th>Empleado</th>
                    <th>Código</th>
                    <th>Retardos (últimos 5 días)</th>
                </tr>
        """

        for emp in empleados_retardos_consecutivos:
            html_reporte += f"""
                <tr>
                    <td>{emp['nombre']}</td>
                    <td>{emp['codigo']}</td>
                    <td>{emp['retardos']}</td>
                </tr>
            """

        html_reporte += "</table></div>"

    html_reporte += "</body></html>"

    # Enviar email
    email = EmailMultiAlternatives(
        f'Reporte Diario de Asistencia - {hoy.strftime("%d/%m/%Y")}',
        'Reporte diario de asistencias. Por favor revisa el contenido HTML.',
        settings.DEFAULT_FROM_EMAIL,
        destinatarios
    )
    email.attach_alternative(html_reporte, "text/html")

    try:
        email.send(fail_silently=False)
    except Exception as e:
        return registrar_envio_reporte(
            TipoReporte.DIARIO, periodo_descripcion, destinatarios, origen,
            enviado_por=enviado_por, exitoso=False, error=str(e)
        )

    return registrar_envio_reporte(
        TipoReporte.DIARIO, periodo_descripcion, destinatarios, origen,
        enviado_por=enviado_por, exitoso=True
    )
```

- [ ] **Step 2: Reemplazar `generar_reporte_semanal` completo**

Reemplazar la función completa (líneas 240-388) por:

```python
def generar_reporte_semanal(origen=OrigenEnvio.AUTOMATICO, enviado_por=None):
    """Genera y envía el reporte semanal todos los jueves"""
    hoy = timezone.now().date()

    dias_desde_lunes = hoy.weekday()
    fecha_inicio = hoy - timedelta(days=dias_desde_lunes)
    fecha_fin = hoy
    periodo_descripcion = f"{fecha_inicio.strftime('%d/%m/%Y')} - {fecha_fin.strftime('%d/%m/%Y')}"

    config = ConfiguracionSistema.objects.first()
    if not config:
        return registrar_envio_reporte(
            TipoReporte.SEMANAL, periodo_descripcion, [], origen,
            enviado_por=enviado_por, exitoso=False, error='No se encontró configuración del sistema'
        )

    destinatarios = obtener_destinatarios_reporte(TipoReporte.SEMANAL)
    if not destinatarios:
        return registrar_envio_reporte(
            TipoReporte.SEMANAL, periodo_descripcion, [], origen,
            enviado_por=enviado_por, exitoso=False, error='Sin destinatarios configurados'
        )

    empleados = Empleado.objects.filter(activo=True)

    html_reporte = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 10px; text-align: center; }}
            th {{ background-color: #3b82f6; color: white; }}
            tr:nth-child(even) {{ background-color: #f2f2f2; }}
            .titulo {{ background-color: #1e40af; color: white; padding: 20px; text-align: center; }}
            .resumen {{ background-color: #eff6ff; padding: 20px; border-radius: 8px; margin: 20px 0; }}
            .alerta {{ background-color: #fef2f2; padding: 15px; border-left: 4px solid #ef4444; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="titulo">
            <h1>Reporte Semanal de Asistencias</h1>
            <p>{fecha_inicio.strftime('%d/%m/%Y')} - {fecha_fin.strftime('%d/%m/%Y')}</p>
        </div>

        <table>
            <tr>
                <th>Empleado</th>
                <th>Código</th>
                <th>Departamento</th>
                <th>Días Asistidos</th>
                <th>Retardos</th>
                <th>Total Min. Retardo</th>
                <th>Faltas</th>
            </tr>
    """

    empleados_retardos_consecutivos = []

    for empleado in empleados:
        asistencias = Asistencia.objects.filter(
            empleado=empleado,
            fecha__gte=fecha_inicio,
            fecha__lte=fecha_fin,
            tipo_movimiento=TipoMovimiento.ENTRADA
        )

        dias_asistidos = asistencias.values('fecha').distinct().count()
        retardos = asistencias.filter(retardo=True).count()
        total_min_retardo = sum(asistencias.filter(retardo=True).values_list('minutos_retardo', flat=True))

        tipo_horario = empleado.tipo_horario
        if tipo_horario and tipo_horario.es_turno_24h:
            dias_periodo = (fecha_fin - fecha_inicio).days + 1
            turnos_esperados = dias_periodo // 2
            faltas = max(0, turnos_esperados - dias_asistidos)
        else:
            dias_laborales = 0
            fecha_actual = fecha_inicio
            while fecha_actual <= fecha_fin:
                if fecha_actual.weekday() < 5:
                    dias_laborales += 1
                fecha_actual += timedelta(days=1)
            faltas = dias_laborales - dias_asistidos

        html_reporte += f"""
            <tr>
                <td>{empleado.user.get_full_name()}</td>
                <td>{empleado.codigo_empleado}</td>
                <td>{empleado.departamento.nombre if empleado.departamento else 'N/A'}</td>
                <td>{dias_asistidos}</td>
                <td>{retardos}</td>
                <td>{total_min_retardo}</td>
                <td>{faltas}</td>
            </tr>
        """

        if retardos >= 3:
            empleados_retardos_consecutivos.append({
                'nombre': empleado.user.get_full_name(),
                'codigo': empleado.codigo_empleado,
                'retardos': retardos
            })

    html_reporte += "</table>"

    if empleados_retardos_consecutivos:
        html_reporte += """
        <div class="alerta">
            <h2>⚠️ Atención: Retardos Recurrentes</h2>
            <p>Los siguientes empleados tienen 3 o más retardos esta semana:</p>
            <table>
                <tr>
                    <th>Empleado</th>
                    <th>Código</th>
                    <th>Retardos (esta semana)</th>
                </tr>
        """

        for emp in empleados_retardos_consecutivos:
            html_reporte += f"""
                <tr>
                    <td>{emp['nombre']}</td>
                    <td>{emp['codigo']}</td>
                    <td>{emp['retardos']}</td>
                </tr>
            """

        html_reporte += "</table></div>"

    html_reporte += "</body></html>"

    excel_buffer = generar_excel_reporte_semanal(fecha_inicio, fecha_fin)
    nombre_excel = f"reporte_semanal_{fecha_inicio.strftime('%Y%m%d')}_{fecha_fin.strftime('%Y%m%d')}.xlsx"

    email = EmailMultiAlternatives(
        f'Reporte Semanal de Asistencias - Semana del {fecha_inicio.strftime("%d/%m/%Y")}',
        'Reporte semanal de asistencias. Por favor revisa el contenido HTML y el archivo Excel adjunto con el detalle de todas las checadas.',
        settings.DEFAULT_FROM_EMAIL,
        destinatarios
    )
    email.attach_alternative(html_reporte, "text/html")
    email.attach(nombre_excel, excel_buffer.read(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    try:
        email.send(fail_silently=False)
    except Exception as e:
        return registrar_envio_reporte(
            TipoReporte.SEMANAL, periodo_descripcion, destinatarios, origen,
            enviado_por=enviado_por, exitoso=False, error=str(e)
        )

    return registrar_envio_reporte(
        TipoReporte.SEMANAL, periodo_descripcion, destinatarios, origen,
        enviado_por=enviado_por, exitoso=True
    )
```

- [ ] **Step 3: Escribir las pruebas**

Agregar al final de `attendance/tests.py`:

```python
class GenerarReporteDiarioTest(TestCase):
    def test_sin_destinatarios_registra_envio_fallido(self):
        from attendance.models import ConfiguracionSistema, TipoReporte, EnvioReporte
        from attendance.utils import generar_reporte_diario

        ConfiguracionSistema.objects.create(
            hora_entrada='09:00:00', minutos_tolerancia=15,
            email_gerente='gerente@example.com', ruta_red_reportes=''
        )

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
        DestinatarioReporte.objects.create(configuracion=config_reporte, email='destino@example.com', activo=True)

        resultado = generar_reporte_diario(origen=OrigenEnvio.MANUAL)

        self.assertTrue(resultado.exitoso)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['destino@example.com'])
        self.assertEqual(resultado.origen, OrigenEnvio.MANUAL)


class GenerarReporteSemanalTest(TestCase):
    def test_sin_destinatarios_registra_envio_fallido(self):
        from attendance.models import ConfiguracionSistema, TipoReporte, EnvioReporte
        from attendance.utils import generar_reporte_semanal

        ConfiguracionSistema.objects.create(
            hora_entrada='09:00:00', minutos_tolerancia=15,
            email_gerente='gerente@example.com', ruta_red_reportes=''
        )

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
        DestinatarioReporte.objects.create(configuracion=config_reporte, email='destino@example.com', activo=True)

        resultado = generar_reporte_semanal()

        self.assertTrue(resultado.exitoso)
        self.assertEqual(len(mail.outbox[0].attachments), 1)
```

- [ ] **Step 4: Correr las pruebas**

Run: `python manage.py test attendance.tests.GenerarReporteDiarioTest attendance.tests.GenerarReporteSemanalTest -v 2`
Expected: 4 tests, `OK`

- [ ] **Step 5: Commit**

```bash
git add attendance/utils.py attendance/tests.py
git commit -m "refactor: Use configured recipients and delivery log in daily/weekly reports"
```

---

## Task 5: Refactorizar `generar_reporte_quincenal` y agregar email a `generar_reporte_tiempo_extra_mensual`

**Files:**
- Modify: `attendance/utils.py:517-618` (`generar_reporte_quincenal`), `attendance/utils.py:621-726` (`generar_reporte_tiempo_extra_mensual`)
- Test: `attendance/tests.py`

**Interfaces:**
- Consumes: `obtener_destinatarios_reporte`, `registrar_envio_reporte` (Task 3)
- Produces: `generar_reporte_quincenal(dia, origen=OrigenEnvio.AUTOMATICO, enviado_por=None) -> EnvioReporte`, `generar_reporte_tiempo_extra_mensual(origen=OrigenEnvio.AUTOMATICO, enviado_por=None) -> EnvioReporte`

- [ ] **Step 1: Reemplazar `generar_reporte_quincenal` completo**

Reemplazar la función completa (líneas 517-618) por:

```python
def generar_reporte_quincenal(dia, origen=OrigenEnvio.AUTOMATICO, enviado_por=None):
    """Genera el reporte quincenal (días 13 y 28)"""
    hoy = timezone.now().date()

    if dia == 13:
        fecha_inicio = hoy.replace(day=1)
        fecha_fin = hoy.replace(day=13)
        periodo = "Primera Quincena"
    else:
        fecha_inicio = hoy.replace(day=14)
        if hoy.month == 12:
            fecha_fin = hoy.replace(day=31)
        else:
            fecha_fin = (hoy.replace(month=hoy.month + 1, day=1) - timedelta(days=1))
        periodo = "Segunda Quincena"

    periodo_descripcion = f"{periodo} - {fecha_inicio.strftime('%d/%m/%Y')} a {fecha_fin.strftime('%d/%m/%Y')}"

    config = ConfiguracionSistema.objects.first()
    if not config:
        return registrar_envio_reporte(
            TipoReporte.QUINCENAL, periodo_descripcion, [], origen,
            enviado_por=enviado_por, exitoso=False, error='No se encontró configuración del sistema'
        )

    destinatarios = obtener_destinatarios_reporte(TipoReporte.QUINCENAL)
    if not destinatarios:
        return registrar_envio_reporte(
            TipoReporte.QUINCENAL, periodo_descripcion, [], origen,
            enviado_por=enviado_por, exitoso=False, error='Sin destinatarios configurados'
        )

    empleados = Empleado.objects.filter(activo=True)

    html_reporte = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 10px; text-align: center; }}
            th {{ background-color: #3b82f6; color: white; }}
            tr:nth-child(even) {{ background-color: #f2f2f2; }}
            .titulo {{ background-color: #1e40af; color: white; padding: 20px; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="titulo">
            <h1>Reporte de Asistencias - {periodo}</h1>
            <p>{fecha_inicio.strftime('%d/%m/%Y')} - {fecha_fin.strftime('%d/%m/%Y')}</p>
        </div>

        <table>
            <tr>
                <th>Empleado</th>
                <th>Código</th>
                <th>Departamento</th>
                <th>Días Asistidos</th>
                <th>Retardos</th>
                <th>Total Min. Retardo</th>
                <th>Faltas</th>
            </tr>
    """

    for empleado in empleados:
        asistencias = Asistencia.objects.filter(
            empleado=empleado,
            fecha__gte=fecha_inicio,
            fecha__lte=fecha_fin,
            tipo_movimiento=TipoMovimiento.ENTRADA
        )

        dias_asistidos = asistencias.values('fecha').distinct().count()
        retardos = asistencias.filter(retardo=True).count()
        total_min_retardo = sum(asistencias.filter(retardo=True).values_list('minutos_retardo', flat=True))

        tipo_horario = empleado.tipo_horario
        if tipo_horario and tipo_horario.es_turno_24h:
            dias_periodo = (fecha_fin - fecha_inicio).days + 1
            turnos_esperados = dias_periodo // 2
            faltas = max(0, turnos_esperados - dias_asistidos)
        else:
            dias_laborales = (fecha_fin - fecha_inicio).days + 1
            faltas = dias_laborales - dias_asistidos

        html_reporte += f"""
            <tr>
                <td>{empleado.user.get_full_name()}</td>
                <td>{empleado.codigo_empleado}</td>
                <td>{empleado.departamento.nombre if empleado.departamento else 'N/A'}</td>
                <td>{dias_asistidos}</td>
                <td>{retardos}</td>
                <td>{total_min_retardo}</td>
                <td>{faltas}</td>
            </tr>
        """

    html_reporte += "</table></body></html>"

    email = EmailMultiAlternatives(
        f'Reporte Quincenal - {periodo} - {hoy.strftime("%B %Y")}',
        'Reporte quincenal de asistencias. Por favor revisa el contenido HTML.',
        settings.DEFAULT_FROM_EMAIL,
        destinatarios
    )
    email.attach_alternative(html_reporte, "text/html")

    try:
        email.send(fail_silently=False)
    except Exception as e:
        return registrar_envio_reporte(
            TipoReporte.QUINCENAL, periodo_descripcion, destinatarios, origen,
            enviado_por=enviado_por, exitoso=False, error=str(e)
        )

    return registrar_envio_reporte(
        TipoReporte.QUINCENAL, periodo_descripcion, destinatarios, origen,
        enviado_por=enviado_por, exitoso=True
    )
```

- [ ] **Step 2: Reemplazar `generar_reporte_tiempo_extra_mensual` completo**

Reemplazar la función completa (líneas 621-726) por:

```python
def generar_reporte_tiempo_extra_mensual(origen=OrigenEnvio.AUTOMATICO, enviado_por=None):
    """Genera el reporte mensual de tiempo extra: lo guarda en la red (si hay ruta configurada) y lo envía por email"""
    hoy = timezone.now()
    mes = hoy.month
    anio = hoy.year
    periodo_descripcion = f"{mes:02d}/{anio}"

    config = ConfiguracionSistema.objects.first()
    if not config:
        return registrar_envio_reporte(
            TipoReporte.TIEMPO_EXTRA, periodo_descripcion, [], origen,
            enviado_por=enviado_por, exitoso=False, error='No se encontró configuración del sistema'
        )

    destinatarios = obtener_destinatarios_reporte(TipoReporte.TIEMPO_EXTRA)
    if not destinatarios:
        return registrar_envio_reporte(
            TipoReporte.TIEMPO_EXTRA, periodo_descripcion, [], origen,
            enviado_por=enviado_por, exitoso=False, error='Sin destinatarios configurados'
        )

    tiempos_extra = TiempoExtra.objects.filter(
        fecha__month=mes,
        fecha__year=anio,
        aprobado=True
    ).select_related('empleado', 'empleado__user')

    html_reporte = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
            th {{ background-color: #10b981; color: white; }}
            tr:nth-child(even) {{ background-color: #f2f2f2; }}
            .total {{ background-color: #d1fae5; font-weight: bold; }}
        </style>
    </head>
    <body>
        <h1>Reporte de Tiempo Extra</h1>
        <p><strong>Período:</strong> {hoy.strftime('%B %Y')}</p>

        <table>
            <tr>
                <th>Empleado</th>
                <th>Código</th>
                <th>Fecha</th>
                <th>Horas Extra</th>
                <th>Descripción</th>
            </tr>
    """

    total_horas = 0
    empleados_resumen = {}

    for te in tiempos_extra:
        html_reporte += f"""
            <tr>
                <td>{te.empleado.user.get_full_name()}</td>
                <td>{te.empleado.codigo_empleado}</td>
                <td>{te.fecha.strftime('%d/%m/%Y')}</td>
                <td>{te.horas_extra}</td>
                <td>{te.descripcion}</td>
            </tr>
        """
        total_horas += float(te.horas_extra)

        emp_id = te.empleado.id
        if emp_id not in empleados_resumen:
            empleados_resumen[emp_id] = {
                'nombre': te.empleado.user.get_full_name(),
                'codigo': te.empleado.codigo_empleado,
                'horas': 0
            }
        empleados_resumen[emp_id]['horas'] += float(te.horas_extra)

    html_reporte += f"""
            <tr class="total">
                <td colspan="3">TOTAL</td>
                <td>{total_horas:.2f}</td>
                <td></td>
            </tr>
        </table>

        <h2>Resumen por Empleado</h2>
        <table>
            <tr>
                <th>Empleado</th>
                <th>Código</th>
                <th>Total Horas Extra</th>
            </tr>
    """

    for emp in empleados_resumen.values():
        html_reporte += f"""
            <tr>
                <td>{emp['nombre']}</td>
                <td>{emp['codigo']}</td>
                <td>{emp['horas']:.2f}</td>
            </tr>
        """

    html_reporte += "</table></body></html>"

    if config.ruta_red_reportes:
        nombre_archivo = f"reporte_tiempo_extra_{anio}_{mes:02d}.html"
        ruta_completa = os.path.join(config.ruta_red_reportes, nombre_archivo)
        try:
            with open(ruta_completa, 'w', encoding='utf-8') as f:
                f.write(html_reporte)
            print(f"Reporte guardado en: {ruta_completa}")
        except Exception as e:
            print(f"Error al guardar reporte en red: {e}")

    email = EmailMultiAlternatives(
        f'Reporte de Tiempo Extra - {periodo_descripcion}',
        'Reporte mensual de tiempo extra. Por favor revisa el contenido HTML.',
        settings.DEFAULT_FROM_EMAIL,
        destinatarios
    )
    email.attach_alternative(html_reporte, "text/html")

    try:
        email.send(fail_silently=False)
    except Exception as e:
        return registrar_envio_reporte(
            TipoReporte.TIEMPO_EXTRA, periodo_descripcion, destinatarios, origen,
            enviado_por=enviado_por, exitoso=False, error=str(e)
        )

    return registrar_envio_reporte(
        TipoReporte.TIEMPO_EXTRA, periodo_descripcion, destinatarios, origen,
        enviado_por=enviado_por, exitoso=True
    )
```

- [ ] **Step 3: Escribir las pruebas**

Agregar al final de `attendance/tests.py`:

```python
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
```

- [ ] **Step 4: Correr las pruebas**

Run: `python manage.py test attendance.tests.GenerarReporteQuincenalTest attendance.tests.GenerarReporteTiempoExtraMensualTest -v 2`
Expected: 4 tests, `OK`

- [ ] **Step 5: Commit**

```bash
git add attendance/utils.py attendance/tests.py
git commit -m "refactor: Use configured recipients in biweekly report; add email to overtime report"
```

---

## Task 6: Nueva función `generar_reporte_mensual` y simplificación del management command

**Files:**
- Modify: `attendance/utils.py` (agregar función nueva después de `generar_reporte_tiempo_extra_mensual`, antes de la sección `# ========== FUNCIONES PARA REPORTES EXCEL ==========`)
- Modify: `attendance/management/commands/generar_reporte_mensual.py` (reemplazo completo)
- Test: `attendance/tests.py`

**Interfaces:**
- Consumes: `obtener_destinatarios_reporte`, `registrar_envio_reporte`, `generar_excel_reporte_mensual` (ya existente)
- Produces: `generar_reporte_mensual(mes=None, anio=None, origen=OrigenEnvio.AUTOMATICO, enviado_por=None) -> EnvioReporte`

- [ ] **Step 1: Agregar `generar_reporte_mensual` a `attendance/utils.py`**

Insertar justo antes de la línea `# ========== FUNCIONES PARA REPORTES EXCEL ==========`:

```python

def generar_reporte_mensual(mes=None, anio=None, origen=OrigenEnvio.AUTOMATICO, enviado_por=None):
    """Genera el reporte mensual de asistencias en Excel, lo guarda en red si aplica y lo envía por email"""
    hoy = timezone.now().date()

    if mes is None:
        primer_dia_mes_actual = hoy.replace(day=1)
        ultimo_dia_mes_anterior = primer_dia_mes_actual - timedelta(days=1)
        mes = ultimo_dia_mes_anterior.month
        anio = ultimo_dia_mes_anterior.year
    elif anio is None:
        anio = hoy.year

    periodo_descripcion = f"{mes:02d}/{anio}"

    config = ConfiguracionSistema.objects.first()
    if not config:
        return registrar_envio_reporte(
            TipoReporte.MENSUAL, periodo_descripcion, [], origen,
            enviado_por=enviado_por, exitoso=False, error='No se encontró configuración del sistema'
        )

    destinatarios = obtener_destinatarios_reporte(TipoReporte.MENSUAL)
    if not destinatarios:
        return registrar_envio_reporte(
            TipoReporte.MENSUAL, periodo_descripcion, [], origen,
            enviado_por=enviado_por, exitoso=False, error='Sin destinatarios configurados'
        )

    excel_buffer = generar_excel_reporte_mensual(mes, anio)
    nombre_excel = f"reporte_mensual_{anio}_{mes:02d}.xlsx"

    if config.ruta_red_reportes:
        ruta_completa = os.path.join(config.ruta_red_reportes, nombre_excel)
        try:
            with open(ruta_completa, 'wb') as f:
                f.write(excel_buffer.getvalue())
        except Exception as e:
            print(f"Error al guardar reporte mensual en red: {e}")

    excel_buffer.seek(0)

    email = EmailMessage(
        subject=f'Reporte Mensual de Asistencias - {mes:02d}/{anio}',
        body=(
            f'Reporte mensual de asistencias del período {mes:02d}/{anio}.\n\n'
            'El archivo Excel adjunto contiene:\n'
            '- Hoja 1: Resumen por empleado (días asistidos, retardos, faltas, permisos)\n'
            '- Hoja 2: Detalle de todas las asistencias del mes\n'
            '- Hoja 3: Empleados con retardos y faltas\n\n'
            'Este reporte se genera automáticamente el día 1 de cada mes.'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=destinatarios
    )
    email.attach(nombre_excel, excel_buffer.read(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    try:
        email.send(fail_silently=False)
    except Exception as e:
        return registrar_envio_reporte(
            TipoReporte.MENSUAL, periodo_descripcion, destinatarios, origen,
            enviado_por=enviado_por, exitoso=False, error=str(e)
        )

    return registrar_envio_reporte(
        TipoReporte.MENSUAL, periodo_descripcion, destinatarios, origen,
        enviado_por=enviado_por, exitoso=True
    )
```

- [ ] **Step 2: Simplificar el management command**

Reemplazar todo el contenido de `attendance/management/commands/generar_reporte_mensual.py` por:

```python
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
```

- [ ] **Step 3: Escribir las pruebas**

Agregar al final de `attendance/tests.py`:

```python
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
```

- [ ] **Step 4: Correr las pruebas**

Run: `python manage.py test attendance.tests.GenerarReporteMensualTest attendance.tests.GenerarReporteMensualCommandTest -v 2`
Expected: 3 tests, `OK`

- [ ] **Step 5: Commit**

```bash
git add attendance/utils.py attendance/management/commands/generar_reporte_mensual.py attendance/tests.py
git commit -m "feat: Extract monthly report sending into utils.generar_reporte_mensual"
```

---

## Task 7: Proteger vistas con login y agregar la vista de envío manual

**Files:**
- Modify: `attendance/views.py` (imports, decoradores, nueva vista al final)
- Modify: `attendance/urls.py`
- Modify: `checador/settings.py`
- Test: `attendance/tests.py`

**Interfaces:**
- Consumes: `generar_reporte_diario`, `generar_reporte_semanal`, `generar_reporte_quincenal`, `generar_reporte_mensual`, `generar_reporte_tiempo_extra_mensual`, `dia_quincena_actual` (Tasks 4-6); `TipoReporte`, `OrigenEnvio` (Task 1)
- Produces: URL con `name='enviar_reporte'` que acepta POST con `tipo` en la ruta; `dashboard_view`, `reporte_mensual_view`, `asignacion_turnos_mensual` ahora requieren sesión iniciada

- [ ] **Step 1: Actualizar imports en `attendance/views.py`**

Reemplazar las líneas 1-18 por:

```python
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse, Http404
from django.views.generic import CreateView, ListView
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Count, Q
from datetime import datetime, timedelta
from django.views.decorators.http import require_http_methods
from .models import (
    Empleado, Asistencia, TipoMovimiento, Visitante,
    RegistroVisita, TiempoExtra, ConfiguracionSistema,
    SolicitudPermiso, SolicitudVacaciones, EstadoSolicitud, TipoAusencia,
    AsignacionTurnoDiaria, TurnoRotativo, TipoReporte, OrigenEnvio
)
from .forms import VisitanteForm, CheckInForm
from .utils import (
    enviar_email_visitante, generar_reporte_diario, generar_reporte_quincenal,
    generar_reporte_semanal, generar_reporte_mensual, generar_reporte_tiempo_extra_mensual,
    dia_quincena_actual
)
import json
from django.views.decorators.csrf import csrf_exempt
```

- [ ] **Step 2: Proteger `dashboard_view`, `reporte_mensual_view` y `asignacion_turnos_mensual`**

Agregar `@login_required` justo antes de cada `def`:

```python
@login_required
def dashboard_view(request):
```

```python
@login_required
def reporte_mensual_view(request, mes=None, anio=None):
```

```python
@login_required
def asignacion_turnos_mensual(request, mes=None, anio=None):
```

- [ ] **Step 3: Agregar la vista de envío manual al final de `attendance/views.py`**

```python

# ========== ENVÍO MANUAL DE REPORTES ==========

@login_required
@require_http_methods(["POST"])
def enviar_reporte_view(request, tipo):
    """Dispara el envío manual de un reporte desde el Dashboard"""
    if tipo not in TipoReporte.values:
        raise Http404("Tipo de reporte no válido")

    if tipo == TipoReporte.DIARIO:
        resultado = generar_reporte_diario(origen=OrigenEnvio.MANUAL, enviado_por=request.user)
    elif tipo == TipoReporte.SEMANAL:
        resultado = generar_reporte_semanal(origen=OrigenEnvio.MANUAL, enviado_por=request.user)
    elif tipo == TipoReporte.QUINCENAL:
        resultado = generar_reporte_quincenal(dia_quincena_actual(), origen=OrigenEnvio.MANUAL, enviado_por=request.user)
    elif tipo == TipoReporte.MENSUAL:
        resultado = generar_reporte_mensual(origen=OrigenEnvio.MANUAL, enviado_por=request.user)
    else:
        resultado = generar_reporte_tiempo_extra_mensual(origen=OrigenEnvio.MANUAL, enviado_por=request.user)

    if resultado.exitoso:
        messages.success(request, f'Reporte {resultado.get_tipo_display()} enviado a: {resultado.destinatarios}')
    else:
        messages.error(request, f'No se pudo enviar el reporte {resultado.get_tipo_display()}: {resultado.error}')

    return redirect('dashboard')
```

- [ ] **Step 4: Agregar la ruta en `attendance/urls.py`**

Agregar dentro de `urlpatterns`, después del bloque de "Dashboard y reportes":

```python
    path('reportes/enviar/<str:tipo>/', views.enviar_reporte_view, name='enviar_reporte'),
```

- [ ] **Step 5: Configurar `LOGIN_URL` en `checador/settings.py`**

Agregar después de la línea `DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'`:

```python

# Autenticación: no hay login propio en la app, se usa el del admin de Django
LOGIN_URL = '/admin/login/'
```

- [ ] **Step 6: Escribir las pruebas**

Agregar al final de `attendance/tests.py`:

```python
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
        from django.urls import reverse
        from attendance.models import (
            ConfiguracionSistema, ConfiguracionReporte, DestinatarioReporte,
            TipoReporte, OrigenEnvio, EnvioReporte
        )

        ConfiguracionSistema.objects.create(
            hora_entrada='09:00:00', minutos_tolerancia=15,
            email_gerente='gerente@example.com', ruta_red_reportes=''
        )
        config_reporte = ConfiguracionReporte.objects.get(tipo=TipoReporte.DIARIO)
        DestinatarioReporte.objects.create(configuracion=config_reporte, email='destino@example.com', activo=True)

        user = User.objects.create_user(username='gerente2', password='clave12345', is_staff=True)
        self.client.force_login(user)

        response = self.client.post(reverse('enviar_reporte', args=['DIARIO']), follow=True)

        self.assertContains(response, 'enviado a')
        envio = EnvioReporte.objects.filter(tipo=TipoReporte.DIARIO, origen=OrigenEnvio.MANUAL).first()
        self.assertIsNotNone(envio)
        self.assertTrue(envio.exitoso)
        self.assertEqual(envio.enviado_por, user)
```

- [ ] **Step 7: Correr las pruebas**

Run: `python manage.py test attendance.tests.DashboardLoginRequiredTest attendance.tests.EnviarReporteViewTest -v 2`
Expected: 4 tests, `OK`

- [ ] **Step 8: Commit**

```bash
git add attendance/views.py attendance/urls.py checador/settings.py attendance/tests.py
git commit -m "feat: Require login on management views; add manual report send endpoint"
```

---

## Task 8: Admin — configuración de destinatarios y bitácora de envíos

**Files:**
- Modify: `attendance/admin.py` (imports al inicio, sección nueva al final)
- Test: `attendance/tests.py`

**Interfaces:**
- Consumes: `ConfiguracionReporte`, `DestinatarioReporte`, `EnvioReporte`, `TipoReporte`, `OrigenEnvio` (Task 1); `generar_reporte_diario`, `generar_reporte_semanal`, `generar_reporte_quincenal`, `generar_reporte_mensual`, `generar_reporte_tiempo_extra_mensual`, `dia_quincena_actual` (Tasks 4-6)
- Produces: `ConfiguracionReporte` y `EnvioReporte` registrados en `/admin/`, con la acción `enviar_reporte_ahora` sobre `ConfiguracionReporte`

- [ ] **Step 1: Actualizar imports en `attendance/admin.py`**

Reemplazar las líneas 1-11 por:

```python
from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from django.utils import timezone
from django import forms
from .models import (
    Departamento, Empleado, Asistencia, TiempoExtra,
    Visitante, RegistroVisita, ConfiguracionSistema, TipoHorario,
    HorarioDiaSemana, TurnoRotativo, AsignacionTurnoRotativo,
    TipoPermiso, SolicitudPermiso, PeriodoVacacional, SaldoVacaciones,
    SolicitudVacaciones, TipoJustificante, Justificante, AsignacionTurnoDiaria,
    ConfiguracionReporte, DestinatarioReporte, EnvioReporte, TipoReporte, OrigenEnvio
)
from .utils import (
    generar_reporte_diario, generar_reporte_semanal, generar_reporte_quincenal,
    generar_reporte_mensual, generar_reporte_tiempo_extra_mensual, dia_quincena_actual
)
```

- [ ] **Step 2: Agregar la sección de admin de reportes al final de `attendance/admin.py`**

```python

# ========== ADMIN PARA ENVÍO DE REPORTES ==========

def _despachar_envio_reporte(tipo, origen, enviado_por):
    """Ejecuta la función de generación/envío correspondiente al tipo de reporte"""
    if tipo == TipoReporte.DIARIO:
        return generar_reporte_diario(origen=origen, enviado_por=enviado_por)
    elif tipo == TipoReporte.SEMANAL:
        return generar_reporte_semanal(origen=origen, enviado_por=enviado_por)
    elif tipo == TipoReporte.QUINCENAL:
        return generar_reporte_quincenal(dia_quincena_actual(), origen=origen, enviado_por=enviado_por)
    elif tipo == TipoReporte.MENSUAL:
        return generar_reporte_mensual(origen=origen, enviado_por=enviado_por)
    return generar_reporte_tiempo_extra_mensual(origen=origen, enviado_por=enviado_por)


class DestinatarioReporteInline(admin.TabularInline):
    model = DestinatarioReporte
    extra = 1
    fields = ['email', 'nombre', 'activo']


@admin.register(ConfiguracionReporte)
class ConfiguracionReporteAdmin(admin.ModelAdmin):
    list_display = ['get_tipo_display', 'activo', 'total_destinatarios_activos']
    list_filter = ['activo']
    inlines = [DestinatarioReporteInline]
    actions = ['enviar_reporte_ahora']

    def total_destinatarios_activos(self, obj):
        return obj.destinatarios.filter(activo=True).count()
    total_destinatarios_activos.short_description = 'Destinatarios activos'

    def enviar_reporte_ahora(self, request, queryset):
        for config in queryset:
            resultado = _despachar_envio_reporte(config.tipo, OrigenEnvio.MANUAL, request.user)
            if resultado.exitoso:
                self.message_user(
                    request,
                    f'{config.get_tipo_display()}: enviado a {resultado.destinatarios}',
                    messages.SUCCESS
                )
            else:
                self.message_user(
                    request,
                    f'{config.get_tipo_display()}: {resultado.error}',
                    messages.ERROR
                )
    enviar_reporte_ahora.short_description = 'Enviar reporte ahora a los destinatarios configurados'


@admin.register(EnvioReporte)
class EnvioReporteAdmin(admin.ModelAdmin):
    list_display = ['tipo', 'fecha_hora', 'periodo_descripcion', 'origen', 'exitoso', 'enviado_por']
    list_filter = ['tipo', 'origen', 'exitoso']
    search_fields = ['destinatarios', 'error']
    date_hierarchy = 'fecha_hora'
    readonly_fields = ['tipo', 'fecha_hora', 'periodo_descripcion', 'destinatarios', 'origen', 'enviado_por', 'exitoso', 'error']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
```

- [ ] **Step 3: Escribir la prueba**

Agregar al final de `attendance/tests.py`:

```python
class ConfiguracionReporteAdminActionTest(TestCase):
    def test_accion_enviar_reporte_ahora_registra_envio_manual(self):
        from django.contrib.auth.models import User
        from django.urls import reverse
        from attendance.models import (
            ConfiguracionSistema, ConfiguracionReporte, DestinatarioReporte,
            TipoReporte, OrigenEnvio, EnvioReporte
        )

        ConfiguracionSistema.objects.create(
            hora_entrada='09:00:00', minutos_tolerancia=15,
            email_gerente='gerente@example.com', ruta_red_reportes=''
        )
        config_reporte = ConfiguracionReporte.objects.get(tipo=TipoReporte.DIARIO)
        DestinatarioReporte.objects.create(configuracion=config_reporte, email='destino@example.com', activo=True)

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
```

- [ ] **Step 4: Correr la prueba**

Run: `python manage.py test attendance.tests.ConfiguracionReporteAdminActionTest -v 2`
Expected: 1 test, `OK`

- [ ] **Step 5: Commit**

```bash
git add attendance/admin.py attendance/tests.py
git commit -m "feat: Add report configuration and delivery log to Django admin"
```

---

## Task 9: Panel de reportes en el Dashboard

**Files:**
- Modify: `attendance/views.py` (`dashboard_view`)
- Modify: `attendance/templates/attendance/dashboard.html`
- Test: `attendance/tests.py`

**Interfaces:**
- Consumes: `ConfiguracionReporte`, `EnvioReporte`, `TipoReporte` (Task 1); ruta `enviar_reporte` (Task 7)
- Produces: contexto `reportes_info` en `dashboard_view` — lista de `{'tipo', 'label', 'destinatarios_count', 'ultimo_envio'}`, una entrada por `TipoReporte`

- [ ] **Step 1: Extender el import de modelos en `attendance/views.py`**

Reemplazar el bloque de import de `.models` (agregado en Task 7) por:

```python
from .models import (
    Empleado, Asistencia, TipoMovimiento, Visitante,
    RegistroVisita, TiempoExtra, ConfiguracionSistema,
    SolicitudPermiso, SolicitudVacaciones, EstadoSolicitud, TipoAusencia,
    AsignacionTurnoDiaria, TurnoRotativo, TipoReporte, OrigenEnvio,
    ConfiguracionReporte, EnvioReporte
)
```

- [ ] **Step 2: Agregar `reportes_info` al contexto de `dashboard_view`**

En `dashboard_view`, justo antes del `context = {` existente, agregar:

```python
    reportes_info = []
    for tipo_valor, tipo_label in TipoReporte.choices:
        config_reporte = ConfiguracionReporte.objects.filter(tipo=tipo_valor).first()
        destinatarios_count = (
            config_reporte.destinatarios.filter(activo=True).count() if config_reporte else 0
        )
        ultimo_envio = EnvioReporte.objects.filter(tipo=tipo_valor).first()
        reportes_info.append({
            'tipo': tipo_valor,
            'label': tipo_label,
            'destinatarios_count': destinatarios_count,
            'ultimo_envio': ultimo_envio,
        })
```

Y agregar `'reportes_info': reportes_info,` dentro del diccionario `context` existente (junto a `'active_nav': 'dashboard'`).

- [ ] **Step 3: Agregar mensajes y el panel de reportes a `dashboard.html`**

En `attendance/templates/attendance/dashboard.html`, justo después de `{% include 'attendance/_nav.html' %}` y antes de `<div class="container mx-auto px-4 py-8">`, no se cambia nada. Dentro del `<div class="container ...">`, inmediatamente después de la línea `<div class="container mx-auto px-4 py-8">` y antes del comentario `<!-- Estadísticas principales -->`, insertar:

```html
        <!-- Mensajes -->
        {% if messages %}
        <div class="mb-8 space-y-3">
            {% for message in messages %}
            <div class="bg-{% if message.tags == 'error' %}red{% else %}green{% endif %}-100 border border-{% if message.tags == 'error' %}red{% else %}green{% endif %}-400 text-{% if message.tags == 'error' %}red{% else %}green{% endif %}-700 px-6 py-4 rounded-lg shadow" role="alert">
                <strong class="font-bold">{% if message.tags == 'error' %}❌{% else %}✅{% endif %}</strong>
                <span class="ml-2">{{ message }}</span>
            </div>
            {% endfor %}
        </div>
        {% endif %}

```

Y justo después de cerrar el `<!-- Estadísticas principales -->` grid (después de la línea `</div>` que cierra ese grid, antes del comentario `<!-- Alerta de retardos consecutivos -->`), insertar:

```html
        <!-- Envío de reportes -->
        <div class="bg-white rounded-xl shadow-lg p-6 mb-8">
            <h2 class="text-xl font-bold text-gray-800 mb-4">Reportes</h2>
            <div class="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
                {% for reporte in reportes_info %}
                <div class="border border-gray-200 rounded-lg p-4">
                    <p class="font-semibold text-gray-800">{{ reporte.label }}</p>
                    <p class="text-sm text-gray-500 mt-1">{{ reporte.destinatarios_count }} destinatario{{ reporte.destinatarios_count|pluralize }}</p>
                    {% if reporte.ultimo_envio %}
                    <p class="text-xs mt-2 {% if reporte.ultimo_envio.exitoso %}text-green-600{% else %}text-red-600{% endif %}">
                        Último envío: {{ reporte.ultimo_envio.fecha_hora|date:"d/m/Y H:i" }}
                        {% if reporte.ultimo_envio.exitoso %}✅{% else %}❌{% endif %}
                    </p>
                    {% else %}
                    <p class="text-xs text-gray-400 mt-2">Sin envíos previos</p>
                    {% endif %}
                    <form method="post" action="{% url 'enviar_reporte' reporte.tipo %}" class="mt-4">
                        {% csrf_token %}
                        {% if reporte.destinatarios_count > 0 %}
                        <button type="submit" class="w-full bg-blue-500 hover:bg-blue-600 text-white text-sm font-semibold py-2 px-4 rounded-lg">
                            Enviar ahora
                        </button>
                        {% else %}
                        <button type="button" disabled class="w-full bg-gray-200 text-gray-400 text-sm font-semibold py-2 px-4 rounded-lg cursor-not-allowed" title="Configura destinatarios en el admin">
                            Enviar ahora
                        </button>
                        {% endif %}
                    </form>
                </div>
                {% endfor %}
            </div>
        </div>

```

- [ ] **Step 4: Escribir la prueba**

Agregar al final de `attendance/tests.py`:

```python
class DashboardReportesContextTest(TestCase):
    def test_dashboard_incluye_info_de_reportes(self):
        from django.contrib.auth.models import User
        from django.urls import reverse
        from attendance.models import ConfiguracionReporte, DestinatarioReporte, TipoReporte

        config_reporte = ConfiguracionReporte.objects.get(tipo=TipoReporte.SEMANAL)
        DestinatarioReporte.objects.create(configuracion=config_reporte, email='a@example.com', activo=True)

        user = User.objects.create_user(username='gerente3', password='clave12345', is_staff=True)
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        reportes_info = response.context['reportes_info']
        self.assertEqual(len(reportes_info), 5)
        semanal_info = next(r for r in reportes_info if r['tipo'] == TipoReporte.SEMANAL)
        self.assertEqual(semanal_info['destinatarios_count'], 1)
        self.assertContains(response, 'Enviar ahora')
```

- [ ] **Step 5: Correr la prueba**

Run: `python manage.py test attendance.tests.DashboardReportesContextTest -v 2`
Expected: 1 test, `OK`

- [ ] **Step 6: Verificación manual en navegador**

Run: `python manage.py runserver`

1. Ir a `http://localhost:8000/admin/` e iniciar sesión.
2. Ir a `http://localhost:8000/dashboard/` y confirmar que aparece la sección "Reportes" con las 5 tarjetas.
3. En `/admin/attendance/configuracionreporte/`, agregar un destinatario a "Diario" y guardar.
4. Volver a `/dashboard/`, confirmar que la tarjeta "Diario" ahora muestra 1 destinatario y el botón "Enviar ahora" está habilitado.
5. Hacer clic en "Enviar ahora" para Diario y confirmar el mensaje de éxito y que aparece "Último envío" con ✅.

- [ ] **Step 7: Commit**

```bash
git add attendance/views.py attendance/templates/attendance/dashboard.html attendance/tests.py
git commit -m "feat: Add report sending panel to the dashboard"
```

---

## Rollout final (después de fusionar todas las tareas)

- [ ] Desplegar a producción y confirmar en el log de arranque que las migraciones `0006` y `0007` se aplicaron correctamente.
- [ ] Entrar a `/admin/attendance/configuracionreporte/` en producción y verificar que DIARIO, SEMANAL, QUINCENAL y MENSUAL ya tienen precargado el email de `ConfiguracionSistema.email_gerente` y, en DIARIO/SEMANAL, también `zuly.becerra@loginco.com.mx` (la migración de datos los toma de la `ConfiguracionSistema` real en ese momento).
- [ ] Confirmar que TIEMPO_EXTRA no tiene destinatarios precargados; si se quiere activar su envío por correo, agregarlos manualmente.
- [ ] Esperar a la siguiente ejecución programada del reporte diario/semanal (apscheduler) y confirmar en `/admin/attendance/envioreporte/` que quedó registrada con `origen=Automático`.
