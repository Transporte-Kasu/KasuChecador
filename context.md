# KasuChecador — Contexto del Proyecto

## Qué es

Sistema Django de control de asistencia para **Transporte Kasu**. Cubre:
- Check-in/check-out de empleados por código QR (pensado para una tablet en recepción).
- Registro y control de acceso de visitantes (QR con activación/desactivación automática).
- Módulo de seguridad para verificar visitantes por cámara QR.
- Horarios de trabajo configurables (fijo, turno 24x24, rotativo, personalizado por día).
- Permisos, vacaciones y justificantes de empleados.
- Asignación mensual de turnos (vista tipo hoja de cálculo).
- Reportes automáticos (diario, semanal, quincenal, mensual, tiempo extra) por email y Excel.
- Dashboard de gerencia con estadísticas de asistencia y retardos.

Idioma de dominio/código: español (nombres de modelos, vistas, mensajes). `LANGUAGE_CODE = 'es-mx'`, `TIME_ZONE = 'America/Mexico_City'`.

## Stack técnico

- **Django 5.2.8**, Python 3.11+.
- **Base de datos**: MySQL gestionado en DigitalOcean (`mysqlclient`), vía `django-environ` para configuración por `.env`. (Nota: README.md describe un setup genérico con PostgreSQL que **ya no aplica**; la config real está en `checador/settings.py`.)
- **Scheduler de tareas periódicas**: `django-apscheduler` (`BackgroundScheduler` en proceso), no Celery/Redis. Se eliminó `checador/celery.py` en el commit "Cambio en despachor de notificaciones" (fd1dcb4). El scheduler arranca en `AttendanceConfig.ready()` (`attendance/apps.py`), excepto durante `migrate`, `collectstatic`, `makemigrations`, `shell`, `dbshell`, `createsuperuser`; se puede desactivar con `RUN_SCHEDULER=false`.
- **Almacenamiento de archivos (media)**: DigitalOcean Spaces vía `django-storages`/`boto3` si hay credenciales (`SPACES_KEY/SECRET/BUCKET`), si no cae a almacenamiento local en `media/`. Ver `checador/storage_backends.py` (incluye clases `StaticStorage`, `MediaStorage`, `ReportesStorage`, `SecureMediaStorage` y señales para borrar archivos huérfanos — algunas utilidades como `upload_ticket_photo` referencian un modelo `idEquipo` que no existe en esta app, parece código reutilizado de otro proyecto y no está en uso activo).
- **Estáticos**: WhiteNoise (`CompressedManifestStaticFilesStorage`).
- **Email**: SMTP vía SendGrid (`EMAIL_HOST = smtp.sendgrid.net`), remitente `checadorKasu@transportekasu.com.mx`.
- **Excel**: `openpyxl` para generación de reportes descargables.
- **QR**: librería `qrcode` para generar, `django-crispy-forms` incluido en requirements (uso limitado).
- **Servidor**: `gunicorn` (ver `Procfile`).
- **Despliegue**: DigitalOcean App Platform (`.do/app.yaml`), health check dedicado en `/health/`.

## Arquitectura de carpetas

```
checador/          Proyecto Django (settings, urls, wsgi/asgi, middleware, storage_backends)
attendance/         App principal con toda la lógica de negocio
  models.py         Modelos (ver abajo)
  views.py          Vistas (checkin, dashboard, reportes, seguridad, turnos)
  urls.py           Rutas de la app (montadas en la raíz "")
  forms.py          CheckInForm, VisitanteForm
  utils.py          Lógica de horarios, generación/envío de reportes y emails
  jobs.py           Definición de jobs de django-apscheduler (reportes diario/semanal, limpieza)
  apps.py           Arranca el scheduler en ready()
  admin.py           Registro de todos los modelos en Django admin
  management/commands/  Comandos manuales de reporte
  templates/attendance/ Plantillas (checkin, checkin_tablet, dashboard, seguridad, turnos, etc.)
  migrations/
.github/workflows/  Reportes vía GitHub Actions (cron) — alternativa/backup al scheduler interno
.do/app.yaml        Config de despliegue en DigitalOcean App Platform
```

## Modelo de datos (resumen)

```
ConfiguracionSistema (singleton) — hora de entrada, tolerancia, email del gerente, ruta de red para reportes
Departamento — nombre + email de contacto

TipoHorario — tipo de sistema (FIJO / TURNO_24H / ROTATIVO / PERSONALIZADO), horas, tolerancia, comida
  ├─ HorarioDiaSemana — horario específico por día (para PERSONALIZADO)
  └─ TurnoRotativo — turnos dentro de un ciclo rotativo
       └─ AsignacionTurnoRotativo — asigna un turno rotativo a un empleado en un rango de fechas
       └─ AsignacionTurnoDiaria — asignación de turno/horario/descanso para un empleado en una fecha concreta
            (usada por la vista "asignación de turnos mensual" tipo Excel)

Empleado (1:1 con User) — código, departamento, tipo_horario, QR (qr_uuid + imagen), tiempo_extra_habilitado
  ├─ Asistencia — checadas (ENTRADA / SALIDA_COMIDA / ENTRADA_COMIDA / SALIDA), retardo y minutos de retardo
  ├─ TiempoExtra — horas extra, aprobación
  ├─ SolicitudPermiso — permisos por días u horas, flujo de aprobación (jefe/gerencia), calcula total_dias/total_horas
  ├─ SaldoVacaciones (por PeriodoVacacional) — días totales/tomados/pendientes
  │    └─ SolicitudVacaciones
  └─ Justificante — justifica retardos/faltas, puede cancelar penalización

Visitante — datos de la visita, QR propio (prefijo "VISITANTE:"), qr_activo (se desactiva tras la salida)
  └─ RegistroVisita — hora_entrada/hora_salida por visita
```

Catálogos de apoyo: `TipoPermiso`, `TipoJustificante` (con reglas de si requiere aprobación de gerencia, documento, cancela penalización, etc.), `EstadoSolicitud` (PENDIENTE/APROBADO_JEFE/APROBADO_GERENCIA/RECHAZADO), `EstadoJustificante`.

## Flujo de check-in de empleado (`procesar_checkin_empleado` en views.py)

1. Se busca al `Empleado` por `qr_uuid` (activo). Si el string empieza con `VISITANTE:`, se trata como visitante en su lugar.
2. Antes de registrar, se revisa si el empleado tiene **vacaciones aprobadas**, **permiso de día completo** o **permiso por horas** vigentes para hoy — si aplica, se muestra advertencia pero **se permite igual el registro**.
3. Se determina el tipo de movimiento según la última checada del día:
   - Sin checadas → `ENTRADA`.
   - Si el horario del empleado **no** tiene comida configurada → alterna `ENTRADA` ⇄ `SALIDA`.
   - Si **sí** tiene comida → secuencia `ENTRADA → SALIDA_COMIDA → ENTRADA_COMIDA → SALIDA` (y reinicia si detecta un estado raro).
   - `TURNO_24H` nunca tiene comida.
4. Si el movimiento es `SALIDA_COMIDA`, se valida que la hora actual esté dentro de la ventana de comida configurada.
5. Al crear una `ENTRADA` se calcula el retardo (`Asistencia.calcular_retardo`), que:
   - Usa `obtener_horario_esperado()` (en `utils.py`) para resolver el horario efectivo del empleado ese día (fijo, rotativo, personalizado por día, o turno 24h).
   - Turnos 24h: compara contra la última entrada y calcula un ciclo de ~48h (trabajo+descanso) con tolerancia de 2h.
   - Otros: tolerancia en minutos configurable por `TipoHorario` (o `ConfiguracionSistema` si no hay horario asignado).
6. Devuelve mensaje con nombre, tipo de movimiento, hora y conteo de checadas del día.

## Flujo de visitantes

- Registro público en `/visitante/registro/` (`VisitanteCreateView`) → genera QR con prefijo `VISITANTE:` y envía email al visitante (con QR adjunto).
- Check-in/out reutiliza las mismas vistas de tablet (`checkin`/`checkin_tablet`), detectando el prefijo `VISITANTE:`.
- Primera vez que se escanea sin `RegistroVisita` abierto → registra entrada. Si ya había uno abierto → registra salida **y desactiva el QR** (`qr_activo=False`); una vez desactivado, cualquier escaneo posterior es rechazado y se exige registrar una nueva visita.
- **Módulo de seguridad** (`/seguridad/`): lista visitantes del día con estado (entrada/salida), y permite **verificar por cámara QR** (agregado en el commit "Add QR camera scanner to security view") contra el endpoint AJAX `verificar_visitante_qr` (solo consulta, no registra movimiento).

## Reportes y notificaciones automatizadas

Dos mecanismos en paralelo:
1. **`django_apscheduler`** (dentro del proceso Django, ver `attendance/jobs.py`):
   - Reporte diario: L-V 12:05 PM.
   - Reporte semanal: jueves 12:00 PM.
   - Limpieza de ejecuciones viejas de jobs: lunes 00:00.
2. **GitHub Actions** (`.github/workflows/reporte-diario.yml`, `reporte-semanal.yml`) ejecutan los mismos reportes vía `python manage.py enviar_reporte_dario` / `enviar_reporte_semanal` como cron externo/backup, inyectando credenciales de BD y SendGrid desde secrets/vars del repo.

Comandos manuales adicionales (no automatizados por cron todavía):
- `generar_reporte_mensual` — Excel del mes anterior, se guarda/envía.
- `enviar_reporte_quincenal` — días 13 y 28 del mes.
- `generar_reporte_tiempo_extra` — reporte mensual de horas extra.

Toda la lógica de generación vive en `attendance/utils.py` (`generar_reporte_diario`, `generar_reporte_semanal`, `generar_reporte_quincenal`, `generar_reporte_tiempo_extra_mensual`, `generar_excel_reporte_semanal`, `generar_excel_reporte_mensual`, `enviar_email_visitante`, `obtener_horario_esperado`).

## URLs principales (`attendance/urls.py`, montadas en la raíz del proyecto)

| Ruta | Vista | Notas |
|---|---|---|
| `/health/`, `/db-status/` | health_check, db_status | Para health checks de DigitalOcean |
| `/checkin/` | checkin_view | Tablet de recepción (formulario) |
| `/` | checkin_view_tablet | Tablet alterna (raíz del sitio) |
| `/visitante/registro/` | VisitanteCreateView | Formulario público |
| `/visitante/exito/` | visitante_exito | Confirmación |
| `/visitantes/` | visitantes_list_view | Listado general |
| `/seguridad/` | seguridad_visitantes_view | Panel de seguridad + escáner QR |
| `/seguridad/verificar-qr/` | verificar_visitante_qr | AJAX, solo consulta |
| `/dashboard/` | dashboard_view | Estadísticas gerenciales |
| `/reporte/mensual/[<mes>/<anio>/]` | reporte_mensual_view | HTML o Excel (`?formato=excel`) |
| `/turnos/asignacion/[<mes>/<anio>/]` | asignacion_turnos_mensual | Vista tipo hoja de cálculo |
| `/turnos/guardar/` | guardar_asignacion_turno | AJAX para guardar celda de turno |
| `/admin/` | Django admin | Todos los modelos registrados |

**Nota de seguridad**: ninguna de estas vistas (dashboard, reportes, turnos, seguridad) tiene `@login_required` ni chequeo de permisos explícito en el código actual — quedan protegidas solo si el despliegue las restringe por otra vía (red interna, proxy, etc.). Vale la pena confirmarlo antes de considerarlas "requieren autenticación" como sugiere documentación antigua del repo.

## Configuración / entorno

Variables esperadas en `.env` (ver `.env.example`): `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `USERNAME`, `PASSWORD`, `HOST`, `DB_PORT`, `DATABASE`, `SSLMODE`, `EMAIL_HOST_PASSWORD`, `CSRF_TRUSTED_ORIGINS`. Opcionales de Spaces: `SPACES_KEY`, `SPACES_SECRET`, `SPACES_BUCKET`, `SPACES_ENDPOINT`.

`HealthCheckMiddleware` (primero en la cadena) responde `200 OK` a `/health/` y `/health` **antes** de validar `ALLOWED_HOSTS`, para evitar 400 en los health checks de DigitalOcean (ver `1848213 Fix: Resolver error 400 en health check`).

## Scripts sueltos en la raíz (no forman parte de la app Django como tal)

- `cargar_empleados.py`, `create_departamentos.py` — scripts de carga inicial desde CSV (`Kasu - Empleados.csv`, `Kasu - Departamentos.csv`).
- `check_env.py`, `test_startup.py`, `setup_spaces.py` — utilidades de diagnóstico/deploy.
- Varios `.md` sueltos en la raíz (`CAMBIOS_IMPLEMENTADOS.md`, `CAMBIOS_PRODUCCION.md`, `CORRECCION_REPORTE_MENSUAL.md`, `DEPLOYMENT.md`, `CHECKLIST_DEPLOYMENT.md`, `FIX_DEPLOYMENT_ERROR.md`, `HORARIOS_PERMISOS_GUIA.md`, `MEJORAS_CHECKIN.md`, `REPORTES_AUTOMATICOS.md`, `SOLUCION_ERROR_400.md`, `README_DEPLOYMENT.txt`) — notas de trabajo/registro histórico de cambios y despliegue, algunas probablemente desactualizadas frente al código actual (igual que `README.md`, que describe un setup genérico PostgreSQL/Celery que ya no coincide con `settings.py`).
- `WARP.md` — guía similar a este archivo pero con partes desactualizadas (menciona Celery+Redis y PostgreSQL, migrado a apscheduler+MySQL).

## Cosas a tener en cuenta al trabajar en este repo

- El repo trae un entorno virtual versionado (`.venvKasuChecador/`) y `db.sqlite3` / `staticfiles/` en el árbol — probablemente no deberían commitearse, pero ya están presentes.
- `attendance/utils (Copiar).py` y `attendance/templates/attendance/checkin_tablet (Copiar).html` son copias/backups sueltas, no se usan por el código activo.
- La lógica de horarios es la parte más compleja del dominio (`obtener_horario_esperado` en `utils.py` + `calcular_retardo` en `models.py`): antes de tocar retardos/turnos, revisar ambas funciones juntas.
