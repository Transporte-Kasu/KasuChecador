# Diseño: Gestión de destinatarios y envío manual de reportes

Fecha: 2026-08-24
Estado: Aprobado, listo para plan de implementación

## Contexto

KasuChecador ya genera y envía por correo (vía SendGrid, configurado como backend SMTP en `checador/settings.py`) varios reportes de asistencia:

- **Diario** (`generar_reporte_diario`, cron apscheduler L-V 12:05, backup en GitHub Actions).
- **Semanal** (`generar_reporte_semanal`, cron apscheduler jueves 12:00, backup en GitHub Actions).
- **Quincenal** (`generar_reporte_quincenal`, solo vía management command `enviar_reporte_quincenal`, se auto-limita a días 13/28).
- **Mensual** (lógica de envío hoy vive dentro del management command `generar_reporte_mensual`, no en `utils.py`; no está en ningún cron).
- **Tiempo extra** (`generar_reporte_tiempo_extra_mensual`, management command `generar_reporte_tiempo_extra`; **hoy solo guarda un HTML en una ruta de red, no envía email**).

Problema: los destinatarios de diario/semanal/quincenal están hardcodeados en `attendance/utils.py` (`config.email_gerente` más el string literal `'zuly.becerra@loginco.com.mx'` en diario y semanal), el mensual solo se puede sobreescribir por `--email` al correr el comando a mano, y tiempo extra no tiene destinatarios porque no envía nada. No hay forma de administrar quién recibe qué reporte sin tocar código, ni de disparar un envío puntual desde la UI, ni de saber si un envío falló.

## Objetivo

Permitir configurar destinatarios por tipo de reporte desde el Django admin, disparar el envío manual de cualquiera de los 5 tipos desde el Dashboard o desde el admin, y dejar un registro auditable de cada envío (automático o manual).

## Alcance

Incluye: Diario, Semanal, Quincenal, Mensual, Tiempo Extra.
No incluye: nuevo tipo de reporte, cambios al contenido/diseño HTML de los reportes existentes, cola asíncrona de envío (el volumen es bajo — pocos destinatarios, se envía síncrono dentro del request/job), ni login propio de la app (se usa `/admin/login/` de Django, ya existente).

## Modelo de datos

Todo se agrega a `attendance/models.py`.

```python
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
    tipo = models.CharField(max_length=20, choices=TipoReporte.choices, unique=True)
    activo = models.BooleanField(default=True, help_text="Si está desactivado, no se envía ni manual ni automáticamente")

class DestinatarioReporte(models.Model):
    configuracion = models.ForeignKey(ConfiguracionReporte, on_delete=models.CASCADE, related_name='destinatarios')
    email = models.EmailField()
    nombre = models.CharField(max_length=100, blank=True)
    activo = models.BooleanField(default=True)

class EnvioReporte(models.Model):
    tipo = models.CharField(max_length=20, choices=TipoReporte.choices)
    fecha_hora = models.DateTimeField(auto_now_add=True)
    periodo_descripcion = models.CharField(max_length=200)
    destinatarios = models.TextField(help_text="Snapshot de a quién se envió, separado por coma")
    origen = models.CharField(max_length=20, choices=OrigenEnvio.choices)
    enviado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    exitoso = models.BooleanField()
    error = models.TextField(blank=True)

    class Meta:
        ordering = ['-fecha_hora']
```

`ConfiguracionReporte.tipo` es único: una sola fila de configuración por tipo (se crea por migración de datos, no por el usuario). `DestinatarioReporte` es donde se agregan/quitan correos y son N por configuración.

## Backend (`attendance/utils.py`)

Dos helpers nuevos:

- `obtener_destinatarios_reporte(tipo: str) -> list[str]`: resuelve la `ConfiguracionReporte` del tipo; si no existe, está `activo=False`, o no tiene `DestinatarioReporte` activos, devuelve `[]`.
- `registrar_envio_reporte(tipo, periodo_descripcion, destinatarios, origen, enviado_por=None, exitoso=True, error='') -> EnvioReporte`: crea el registro de auditoría.

Cambios en las funciones de generación existentes (`generar_reporte_diario`, `generar_reporte_semanal`, `generar_reporte_quincenal`, `generar_reporte_tiempo_extra_mensual`):

1. Reemplazar las listas hardcodeadas de destinatarios por `obtener_destinatarios_reporte(TipoReporte.X)`.
2. Si la lista viene vacía, llamar `registrar_envio_reporte(..., exitoso=False, error='Sin destinatarios configurados')` y hacer `return` sin intentar enviar.
3. Envolver el `email.send(...)` (y, en tiempo extra, también el guardado a red) en `try/except Exception as e`, registrando `exitoso=True/False` y `error=str(e)` en cada caso. **No se relanza la excepción** — un fallo de SendGrid no debe tumbar el job de apscheduler ni el management command.
4. `generar_reporte_tiempo_extra_mensual` gana el envío por email (mismo patrón que los demás), sin quitar el guardado en ruta de red existente.

Nueva función `generar_reporte_mensual(mes=None, anio=None)` en `utils.py`, migrando la lógica que hoy vive en el management command (usa `generar_excel_reporte_mensual`, guarda en `config.ruta_red_reportes` si está configurada, arma el email y lo envía). Si `mes`/`anio` no se pasan, usa el mes anterior completo (comportamiento actual del comando).

Funciones de cálculo de período para "enviar ahora" (usadas también por las funciones anteriores para `periodo_descripcion`):
- **Diario**: hoy.
- **Semanal**: lunes de esta semana → hoy (ya existente).
- **Quincenal**: si `hoy.day <= 13` → primera quincena (1 al 13); si no → segunda quincena (14 al último día del mes). Se resuelve internamente el `dia` (13 o 28) que ya espera `generar_reporte_quincenal`.
- **Mensual**: mes calendario anterior completo.
- **Tiempo Extra**: mes en curso (comportamiento actual).

## Backend (`attendance/views.py`)

- `@login_required` agregado a `dashboard_view`, `reporte_mensual_view`, `asignacion_turnos_mensual`.
- `LOGIN_URL = '/admin/login/'` en `checador/settings.py` (no hay login propio en la app).
- Nueva vista `enviar_reporte_view(request, tipo)`:
  - `@login_required`, solo acepta POST.
  - Valida que `tipo` esté en `TipoReporte.values`; si no, 404.
  - Despacha a la función `generar_reporte_*` correspondiente según `tipo`, pasando `origen=OrigenEnvio.MANUAL` y `enviado_por=request.user`.
  - Usa `django.contrib.messages` para mostrar éxito o el motivo de fallo (mismo patrón que el resto de la app) y redirige a `dashboard`.
- Nueva ruta en `attendance/urls.py`: `path('reportes/enviar/<str:tipo>/', views.enviar_reporte_view, name='enviar_reporte')`.

Las funciones `generar_reporte_*` deben aceptar `origen` y `enviado_por` como parámetros opcionales (default `OrigenEnvio.AUTOMATICO` / `None`) para que tanto los jobs de apscheduler como los management commands (que no pasan estos argumentos) sigan funcionando sin cambios, y la vista manual sí los pase explícitamente.

## Backend (`attendance/admin.py`)

- `DestinatarioReporteInline(admin.TabularInline)` dentro de `ConfiguracionReporteAdmin`.
- `ConfiguracionReporteAdmin`: `list_display` = tipo, activo, cantidad de destinatarios activos (método corto). Acción de admin `enviar_reporte_ahora` sobre configuraciones seleccionadas: por cada una, despacha a la función `generar_reporte_*` según `tipo`, pasando `origen=MANUAL` y `enviado_por=request.user`; reporta éxito/error por fila con `self.message_user`.
- `EnvioReporteAdmin`: todos los campos `readonly_fields` (es solo bitácora, no se edita a mano), `list_display` = tipo, fecha_hora, origen, exitoso, enviado_por, `list_filter` = tipo, origen, exitoso.

## Management commands existentes

- `generar_reporte_mensual.py`: se simplifica para resolver mes/año por defecto y llamar a `utils.generar_reporte_mensual(mes, anio)`. Se elimina el flag `--email` (el destinatario ahora se administra centralizadamente vía `DestinatarioReporte`); se conservan `--mes`/`--anio` para poder regenerar un mes específico a mano.
- `enviar_reporte_dario.py`, `enviar_reporte_semanal.py`, `enviar_reporte_quincenal.py`, `generar_reporte_tiempo_extra.py`: sin cambios de interfaz — siguen llamando a las mismas funciones de `utils.py`, que ahora resuelven destinatarios internamente.

## UI del Dashboard (`attendance/templates/attendance/dashboard.html`)

Nueva sección "Reportes" debajo de las estadísticas actuales. Una tarjeta por tipo (Diario, Semanal, Quincenal, Mensual, Tiempo Extra) con:
- Conteo de destinatarios activos configurados.
- Último `EnvioReporte` de ese tipo, si existe (fecha + ✅/❌).
- Botón "Enviar ahora" → `<form method="post" action="{% url 'enviar_reporte' tipo %}">`.
- Si 0 destinatarios activos, el botón se deshabilita con nota "Configura destinatarios en el admin" (evita un clic condenado a fallar).

No se agrega historial completo en el dashboard — la bitácora vive en `EnvioReporteAdmin`.

`dashboard_view` se extiende para incluir en el contexto, por tipo: conteo de destinatarios activos y el último `EnvioReporte` (`EnvioReporte.objects.filter(tipo=t).first()`, aprovechando el `ordering = ['-fecha_hora']`).

## Migración

Migración de esquema (crea las 3 tablas nuevas) + migración de datos (`RunPython`) que:

1. Crea las 5 filas de `ConfiguracionReporte` (`activo=True`).
2. Lee `ConfiguracionSistema.objects.first()`; si existe y tiene `email_gerente`, crea un `DestinatarioReporte` con ese email para DIARIO, SEMANAL, QUINCENAL y MENSUAL — preserva el comportamiento actual en producción.
3. Crea `DestinatarioReporte(email='zuly.becerra@loginco.com.mx')` para DIARIO y SEMANAL (el correo extra hoy hardcodeado en esos dos).
4. TIEMPO_EXTRA queda sin destinatarios precargados (hoy no envía a nadie); se configura manualmente si se quiere activar el envío por correo.
5. `reverse` de la migración de datos borra las filas precargadas, para poder revertir limpio en desarrollo.

## Verificación / rollout

- Migrar, entrar al admin, confirmar las 5 `ConfiguracionReporte` y destinatarios precargados.
- Enviar manualmente cada uno de los 5 tipos desde el Dashboard (logueado) y confirmar: llega el correo, aparece el `EnvioReporte` correspondiente con `origen=MANUAL` y `enviado_por` correcto.
- Repetir el envío manual desde la acción de admin en `ConfiguracionReporte`.
- Confirmar que un usuario sin sesión iniciada es redirigido a `/admin/login/` al entrar a `/dashboard/`, `/reporte/mensual/` o `/turnos/asignacion/`.
- Confirmar que los jobs de apscheduler (diario L-V 12:05, semanal jueves 12:00) y los comandos de GitHub Actions siguen corriendo sin cambios de interfaz, y que sus envíos quedan registrados con `origen=AUTOMATICO`, `enviado_por=None`.
- Probar el caso de "sin destinatarios": desactivar todos los `DestinatarioReporte` de un tipo y confirmar que el botón se deshabilita en el dashboard y que un envío forzado (management command) registra `EnvioReporte(exitoso=False)` sin lanzar excepción.

## Fuera de alcance (posible trabajo futuro, no ahora)

- Selección de período/destinatarios ad-hoc por envío (hoy usa siempre la lista guardada y el período por defecto de cada tipo).
- Historial de envíos visible en el dashboard (hoy solo en el admin).
- Reenvío de un `EnvioReporte` fallido con un clic.
- Cola asíncrona / Celery para el envío (no se justifica con el volumen actual).
