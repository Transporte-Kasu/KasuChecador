# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

**KasuChecador** is a Django 5.2-based employee attendance tracking system with QR code check-in/out functionality, visitor management, and automated reporting. The system is designed for tablet-based reception check-ins and includes comprehensive reporting features for management.

### Core Architecture

The application follows Django's MVT (Model-View-Template) pattern with two main components:

1. **checador/** - Django project configuration (settings, URLs, Celery setup)
2. **attendance/** - Main application containing all business logic

Key architectural patterns:
- **QR-based authentication**: Both employees and visitors use UUID-based QR codes for check-in/out
- **State machine for employee check-ins**: Tracks four movement types (ENTRADA → SALIDA_COMIDA → ENTRADA_COMIDA → SALIDA)
- **Automated reporting**: Daily, bi-weekly, and monthly reports sent via email and saved to network drives
- **Celery + Redis**: Handles scheduled tasks for automated report generation

### Data Model Relationships

```
ConfiguracionSistema (singleton) - System-wide settings (entry time, tolerance, manager email)
    ↓
Departamento - Departments with email contacts
    ↓
Empleado (1:1 with User) - Employee records with QR codes
    ↓
Asistencia - Individual attendance records (tracks 4 movement types)
    ↓
TiempoExtra - Overtime tracking (must be enabled per employee)

Visitante - Visitor registration with QR codes
    ↓
RegistroVisita - Actual visitor check-in/out records
```

## Development Commands

### Environment Setup

```bash
# Activate virtual environment
source .venvKasuChecador/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

### Running the Application

```bash
# Development server (accessible from network)
python manage.py runserver 0.0.0.0:8000

# Collect static files (required before deployment)
python manage.py collectstatic
```

### Celery Task Management

```bash
# Start Celery worker and beat scheduler (development)
celery -A checador worker -B -l info

# Production: Run separately
celery -A checador worker -l info  # In one terminal
celery -A checador beat -l info    # In another terminal

# Verify Redis is running
redis-cli ping  # Should return PONG

# Clear all pending tasks
celery -A checador purge
```

### Database Management

```bash
# Create departments programmatically
python manage.py shell
>>> from attendance.models import Departamento
>>> Departamento.objects.create(nombre="Recursos Humanos", email="rh@empresa.com")

# Load employees from CSV (custom script exists)
python cargar_empleados.py

# Create departments from CSV (custom script exists)
python create_departamentos.py
```

### Custom Management Commands

```bash
# Manual report generation
python manage.py enviar_reporte_dario         # Daily report
python manage.py enviar_reporte_semanal       # Weekly report (Thursdays)
python manage.py generar_reporte_tiempo_extra # Monthly overtime report
```

## Important Implementation Details

### QR Code Generation

- QR codes are **automatically generated** when creating Empleado or Visitante records
- Employee QR format: `{uuid}`
- Visitor QR format: `VISITANTE:{uuid}`
- QR images stored in `media/qr_codes/` and `media/qr_visitantes/`
- Generation happens in model's `save()` method via `generar_qr()` function

### Attendance Logic

The check-in state machine (`procesar_checkin_empleado()` in views.py):
1. First scan of day → ENTRADA (checks for tardiness)
2. Second scan → SALIDA_COMIDA
3. Third scan → ENTRADA_COMIDA
4. Fourth scan → SALIDA

**Tardiness calculation** (`calcular_retardo()` in models.py):
- Tolerance: 15 minutes after configured entry time (default 09:00)
- Only applies to ENTRADA movement type
- Tracks minutes of delay and consecutive tardiness (3+ in 5 days)

### Email and Reporting System

**Automated schedules** (configured in `checador/celery.py`):
- Daily report: 12:05 PM every day (sent to manager email)
- Weekly report: Every Thursday at 12:00 PM (sent to manager email)
- Monthly overtime report: 1st of month at 8:00 AM (saved to network path)

**Email configuration** requires:
- Gmail app password (or other SMTP credentials) in `checador/settings.py`
- Manager email configured in ConfiguracionSistema model
- Visitor emails sent automatically on registration with QR code attachment

### Key URLs

- `/checkin/` - Main tablet check-in interface
- `/checkin_tablet/` - Alternative tablet interface
- `/visitante/registro/` - Public visitor registration form
- `/dashboard/` - Management dashboard with statistics
- `/reporte/mensual/` - Monthly attendance reports
- `/admin/` - Django admin interface

## Critical Settings

### Database
Currently using SQLite (`db.sqlite3`) for development. For production, configure PostgreSQL in `checador/settings.py`:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'asistencia_db',
        'USER': 'asistencia_user',
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

### Timezone and Localization
- `TIME_ZONE = 'America/Mexico_City'`
- `LANGUAGE_CODE = 'es-mx'`
- All scheduled tasks use Mexico City timezone

### Security Considerations
- `SECRET_KEY` is hardcoded in settings.py - **must use environment variables in production**
- `DEBUG = True` currently - **must be False in production**
- Email credentials are hardcoded - **must use environment variables**
- ALLOWED_HOSTS includes DigitalOcean domains

## Common Development Scenarios

### Adding a New Employee
1. Create Django User via admin (`/admin/auth/user/add/`)
2. Create Empleado record linking to user (`/admin/attendance/empleado/add/`)
3. Set `codigo_empleado` (employee code), department, and `activo=True`
4. QR code generates automatically - viewable in admin
5. Print QR code for employee to use at tablet

### Testing Check-in Flow
1. Navigate to `/checkin/` on tablet
2. Scan employee QR or manually enter UUID
3. System determines next movement type based on today's history
4. For first entry, tardiness is calculated automatically
5. Success message displays employee name and movement type

### Debugging Celery Tasks
- Check Redis: `redis-cli ping`
- View Celery logs: Check terminal where worker is running
- Manual task execution: Call functions directly from `attendance/utils.py`
- Verify scheduled tasks: Check `app.conf.beat_schedule` in `checador/celery.py`

### Modifying Report Templates
- Report HTML is generated in `attendance/utils.py` functions:
  - `generar_reporte_diario()` - Daily attendance
  - `generar_reporte_semanal()` - Weekly attendance summary (Monday to Thursday)
  - `generar_reporte_tiempo_extra_mensual()` - Monthly overtime
- All use inline CSS for email compatibility
- Tables use consistent styling defined in HTML strings

## File Structure Context

- `cargar_empleados.py` - Utility script to bulk load employees from CSV
- `create_departamentos.py` - Utility script to bulk load departments from CSV
- `Procfile` - Configuration for deployment (likely Heroku/DigitalOcean)
- `staticfiles/` - Collected static assets for production
- `media/` - User-uploaded content (QR codes)
- `attendance/templates/` - All HTML templates (styled with Tailwind CSS)

## Testing

The project does not currently have a comprehensive test suite. When adding tests:
- Use Django's test framework (`python manage.py test attendance`)
- Focus on critical business logic: tardiness calculation, check-in state machine, QR generation
- Mock Celery tasks to avoid dependency on Redis during testing
- Mock email sending to avoid SMTP requirements

## Deployment Notes

- Configured for DigitalOcean App Platform (see ALLOWED_HOSTS)
- Uses SQLite in current configuration (not recommended for production with multiple workers)
- Requires Redis server for Celery functionality
- Static files must be collected: `python manage.py collectstatic`
- Network path (`ruta_red_reportes`) must be writable by application user
