# Configuración de Reportes Automáticos con Excel

## Reportes Implementados

### 1. Reporte Semanal (Ya existente - Mejorado)
- **Frecuencia**: Todos los jueves a las 12:00 PM
- **Contenido**: 
  - Email HTML con resumen de la semana (lunes-jueves)
  - **NUEVO**: Archivo Excel adjunto con todas las checadas detalladas
- **Destinatarios**: Email del gerente (configurado en ConfiguracionSistema)

### 2. Reporte Mensual (NUEVO)
- **Frecuencia**: Día 1 de cada mes a las 8:00 AM
- **Contenido**: Archivo Excel con 3 hojas:
  - **Hoja 1 - Resumen**: Días asistidos, retardos, faltas y permisos por empleado
  - **Hoja 2 - Detalle**: Todas las asistencias del mes anterior con hora exacta
  - **Hoja 3 - Retardos y Faltas**: Solo empleados con incidencias
- **Destinatarios**: Email del gerente + guardado en ruta de red
- **Periodo**: Mes anterior (ej: el 1 de diciembre genera reporte de noviembre)

## Configuración de Tareas Automáticas

Según tu WARP.md, **Celery está deshabilitado** y los reportes se ejecutan via **GitHub Actions**. Aquí están las opciones:

### Opción 1: GitHub Actions (Recomendado si ya lo usas)

Actualiza tu archivo `.github/workflows/reportes.yml`:

```yaml
name: Reportes Automáticos

on:
  schedule:
    # Reporte semanal: Jueves a las 12:00 PM (hora México)
    - cron: '0 18 * * 4'  # 18:00 UTC = 12:00 PM CST (México)
    
    # Reporte mensual: Día 1 de cada mes a las 8:00 AM
    - cron: '0 14 1 * *'  # 14:00 UTC = 8:00 AM CST

  # Permitir ejecución manual
  workflow_dispatch:
    inputs:
      tipo_reporte:
        description: 'Tipo de reporte'
        required: true
        default: 'semanal'
        type: choice
        options:
          - semanal
          - mensual

jobs:
  generar-reportes:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout código
        uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Instalar dependencias
        run: |
          pip install -r requirements.txt
      
      - name: Ejecutar reporte semanal
        if: github.event.schedule == '0 18 * * 4' || github.event.inputs.tipo_reporte == 'semanal'
        env:
          SECRET_KEY: ${{ secrets.SECRET_KEY }}
          DATABASE: ${{ secrets.DATABASE }}
          USERNAME: ${{ secrets.DB_USERNAME }}
          PASSWORD: ${{ secrets.DB_PASSWORD }}
          HOST: ${{ secrets.DB_HOST }}
          DB_PORT: ${{ secrets.DB_PORT }}
          SSLMODE: ${{ secrets.SSLMODE }}
          EMAIL_HOST_PASSWORD: ${{ secrets.EMAIL_HOST_PASSWORD }}
          SPACES_KEY: ${{ secrets.SPACES_KEY }}
          SPACES_SECRET: ${{ secrets.SPACES_SECRET }}
          SPACES_BUCKET: ${{ secrets.SPACES_BUCKET }}
        run: |
          python manage.py enviar_reporte_semanal
      
      - name: Ejecutar reporte mensual
        if: github.event.schedule == '0 14 1 * *' || github.event.inputs.tipo_reporte == 'mensual'
        env:
          SECRET_KEY: ${{ secrets.SECRET_KEY }}
          DATABASE: ${{ secrets.DATABASE }}
          USERNAME: ${{ secrets.DB_USERNAME }}
          PASSWORD: ${{ secrets.DB_PASSWORD }}
          HOST: ${{ secrets.DB_HOST }}
          DB_PORT: ${{ secrets.DB_PORT }}
          SSLMODE: ${{ secrets.SSLMODE }}
          EMAIL_HOST_PASSWORD: ${{ secrets.EMAIL_HOST_PASSWORD }}
          SPACES_KEY: ${{ secrets.SPACES_KEY }}
          SPACES_SECRET: ${{ secrets.SPACES_SECRET }}
          SPACES_BUCKET: ${{ secrets.SPACES_BUCKET }}
        run: |
          python manage.py generar_reporte_mensual
```

### Opción 2: Cron en Servidor Linux (Si tienes servidor dedicado)

Editar crontab del usuario:

```bash
crontab -e
```

Agregar estas líneas:

```bash
# Reporte semanal - Jueves a las 12:00 PM
0 12 * * 4 cd /home/xoyoc/Developer/KasuChecador && source .venvKasuChecador/bin/activate && python manage.py enviar_reporte_semanal >> /var/log/reportes_semanal.log 2>&1

# Reporte mensual - Día 1 de cada mes a las 8:00 AM
0 8 1 * * cd /home/xoyoc/Developer/KasuChecador && source .venvKasuChecador/bin/activate && python manage.py generar_reporte_mensual >> /var/log/reportes_mensual.log 2>&1
```

### Opción 3: DigitalOcean App Platform Functions (Si usas DO)

Crear funciones serverless en DigitalOcean:

1. En tu App Platform, agregar dos Functions:
   - `reporte-semanal`: Ejecuta comando semanal
   - `reporte-mensual`: Ejecuta comando mensual

2. Configurar triggers con cron:
   - Semanal: `0 12 * * 4`
   - Mensual: `0 8 1 * *`

### Opción 4: Celery (Si decides reactivarlo)

Actualizar `checador/celery.py`:

```python
from celery.schedules import crontab

app.conf.beat_schedule = {
    # ... tus tareas existentes ...
    
    'reporte-semanal': {
        'task': 'attendance.tasks.enviar_reporte_semanal_task',
        'schedule': crontab(hour=12, minute=0, day_of_week=4),  # Jueves 12:00 PM
    },
    'reporte-mensual': {
        'task': 'attendance.tasks.generar_reporte_mensual_task',
        'schedule': crontab(hour=8, minute=0, day_of_month=1),  # Día 1, 8:00 AM
    },
}
```

Crear `attendance/tasks.py`:

```python
from celery import shared_task
from .utils import generar_reporte_semanal
from .management.commands.generar_reporte_mensual import Command as ReporteMensualCommand

@shared_task
def enviar_reporte_semanal_task():
    generar_reporte_semanal()

@shared_task
def generar_reporte_mensual_task():
    command = ReporteMensualCommand()
    command.handle()
```

## Ejecución Manual

### Reporte Semanal
```bash
# Desde la raíz del proyecto
source .venvKasuChecador/bin/activate
python manage.py enviar_reporte_semanal
```

### Reporte Mensual
```bash
# Generar reporte del mes anterior
python manage.py generar_reporte_mensual

# Generar reporte de un mes específico
python manage.py generar_reporte_mensual --mes 11 --anio 2025

# Enviar a email alternativo
python manage.py generar_reporte_mensual --email otro@email.com
```

## Verificación de Funcionamiento

### 1. Probar generación de Excel semanal
```bash
source .venvKasuChecador/bin/activate
python manage.py shell

from attendance.utils import generar_excel_reporte_semanal
from datetime import date
fecha_inicio = date(2025, 12, 2)  # Lunes
fecha_fin = date(2025, 12, 5)     # Jueves
buffer = generar_excel_reporte_semanal(fecha_inicio, fecha_fin)
print(f"Excel generado: {len(buffer.getvalue())} bytes")
```

### 2. Probar generación de Excel mensual
```bash
python manage.py shell

from attendance.utils import generar_excel_reporte_mensual
buffer = generar_excel_reporte_mensual(11, 2025)  # Noviembre 2025
print(f"Excel generado: {len(buffer.getvalue())} bytes")
```

### 3. Probar comando completo
```bash
# Ejecutar reporte mensual de noviembre
python manage.py generar_reporte_mensual --mes 11 --anio 2025
```

## Estructura de los Archivos Excel

### Reporte Semanal
```
reporte_semanal_YYYYMMDD_YYYYMMDD.xlsx
│
└── Hoja 1: Reporte Semanal
    ├── Columnas: Fecha, Empleado, Código, Departamento
    ├── Entrada (con indicador de retardo)
    ├── Salida Comida
    ├── Entrada Comida
    └── Salida
```

### Reporte Mensual
```
reporte_mensual_YYYY_MM.xlsx
│
├── Hoja 1: Resumen
│   ├── Empleado, Código, Departamento
│   ├── Días Asistidos, Retardos, Min. Retardo
│   └── Faltas, Permisos
│
├── Hoja 2: Detalle de Asistencias
│   ├── Fecha, Empleado, Código
│   ├── Tipo Movimiento, Hora
│   └── Retardo (Sí/No), Min. Retardo
│
└── Hoja 3: Retardos y Faltas
    ├── Solo empleados con incidencias
    └── Total Retardos, Total Min., Faltas
```

## Notas Importantes

⚠️ **Ruta de Red**: El reporte mensual se guarda automáticamente en la ruta configurada en `ConfiguracionSistema.ruta_red_reportes`. Asegúrate de que:
- La ruta existe y es accesible
- El usuario tiene permisos de escritura
- En producción, puede ser un montaje NFS o SMB

⚠️ **Zona Horaria**: Todos los horarios están en `America/Mexico_City` según settings.py

⚠️ **Email**: El reporte semanal también se envía a `zuly.becerra@loginco.com.mx` (hardcoded en utils.py línea 377). Puedes modificarlo según necesites.

⚠️ **Permisos y Vacaciones**: El reporte mensual ahora incluye automáticamente los permisos aprobados en la columna "Permisos" y los considera al calcular faltas.

## Solución de Problemas

### Error: "No module named 'openpyxl'"
```bash
pip install openpyxl==3.1.5
```

### Error: "No se pudo guardar en red"
- Verificar que la ruta en ConfiguracionSistema existe
- Verificar permisos del directorio
- En Linux: `ls -la /ruta/a/reportes/`

### Excel corrupto o vacío
- Verificar que hay datos para el período solicitado
- Revisar logs: `tail -f /var/log/reportes_mensual.log`

### Email no se envía
- Verificar configuración SMTP en settings.py
- Verificar variable de entorno EMAIL_HOST_PASSWORD
- Probar envío simple: `python manage.py shell` → `from django.core.mail import send_mail`

## Logs Recomendados

Crear directorios de logs:
```bash
sudo mkdir -p /var/log/kasuchecador
sudo chown xoyoc:xoyoc /var/log/kasuchecador
```

Los logs se guardarán automáticamente si usas cron con las rutas indicadas arriba.
