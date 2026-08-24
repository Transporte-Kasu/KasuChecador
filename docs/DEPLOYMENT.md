# Deployment Guide - KasuChecador en DigitalOcean App Platform

## Cambios Realizados para Producción

### 1. **Seguridad**
- ✅ Celery deshabilitado (reemplazado con GitHub Actions)
- ✅ `DEBUG = False` en producción (configurable via variable `DEBUG`)
- ✅ `ALLOWED_HOSTS` configurable via variable de entorno
- ✅ `SECRET_KEY` movido a variables de entorno
- ✅ `.env` agregado a `.gitignore`
- ✅ WhiteNoise habilitado para servir archivos estáticos
- ✅ SSL/MySQL habilitado en base de datos

### 2. **Dependencias Actualizadas**
- ✅ Agregado `gunicorn==23.0.0`
- ✅ Removido `celery`, `redis`, `psycopg2-binary`
- ✅ Agregado `whitenoise==6.8.1`

### 3. **Configuración para DigitalOcean**
- ✅ Creado `Procfile` con comandos para migrate y collectstatic
- ✅ Configurado gunicorn con 2 workers

### 4. **Reporte Automático con GitHub Actions**
- ✅ Workflow diario: 12:05 PM (México)
- ✅ Workflow semanal: Jueves 12:00 PM (México)
- ✅ Los management commands existentes se usan directamente

## Pasos para Deployment

### Paso 1: Preparar Repositorio Git
```bash
cd /home/xoyoc/Developer/KasuChecador
git add .
git commit -m "Preparar para producción: gunicorn, whitenoise, GitHub Actions"
git push origin main
```

### Paso 2: Configurar DigitalOcean App Platform

1. **Crear App en DigitalOcean:**
   - Ve a DigitalOcean > App Platform > Create App
   - Conecta tu repositorio GitHub (KasuChecador)
   - Selecciona branch `main`

2. **Configurar Environment Variables:**
   En la configuración de la app, agrega estas variables:
   ```
   SECRET_KEY = (genera una nueva con: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
   DEBUG = False
   ALLOWED_HOSTS = .ondigitalocean.app,tu-dominio.com
   
   USERNAME = (usuario de BD de DigitalOcean)
   PASSWORD = (contraseña de BD)
   HOST = (host de BD de DigitalOcean)
   PORT = 25060
   DATABASE = transportekasu
   SSLMODE = REQUIRED
   
   EMAIL_HOST_PASSWORD = (API Key de SendGrid)
   CSRF_TRUSTED_ORIGINS = https://*.ondigitalocean.app,https://tu-dominio.com
   ```

3. **Asignar Managed Database:**
   - En la sección de Resources, conecta tu MySQL Managed Database de DigitalOcean

4. **Configurar HTTP Routes:**
   - Route: `/` → Port: `8080`
   - Protocol: `HTTP`

### Paso 3: Configurar GitHub Actions Secrets

Los workflows usan secretos de GitHub. Configúralos en:
`Settings > Secrets and variables > Actions > New repository secret`

Secretos necesarios:
```
SECRET_KEY = (misma que en DO)
DB_USERNAME = (usuario de BD)
DB_PASSWORD = (contraseña de BD)
DB_HOST = (host de BD)
DB_PORT = 25060
DB_NAME = transportekasu
SENDGRID_API_KEY = (API Key de SendGrid)
```

### Paso 4: Verificar Workflows

Los workflows de GitHub Actions están listos:
- `.github/workflows/reporte-diario.yml` - Ejecuta 12:05 PM todos los días
- `.github/workflows/reporte-semanal.yml` - Ejecuta jueves 12:00 PM

**Nota:** GitHub Actions usa UTC. Los crons están en UTC-6 para México.

Puedes probar manualmente desde GitHub:
1. Ve a Actions
2. Selecciona el workflow
3. Click en "Run workflow"

## Checklist Pre-Deployment

- [ ] `.env` local NO está en git
- [ ] `Procfile` contiene comandos correctos
- [ ] `requirements.txt` no tiene Celery/Redis
- [ ] `settings.py` tiene DEBUG configurable
- [ ] WhiteNoise está habilitado
- [ ] DB MySQL de DigitalOcean está creada
- [ ] SendGrid API Key válida
- [ ] Secretos de GitHub Actions configurados
- [ ] rama `main` está lista para push

## Después del Deployment

1. **Verificar logs en DigitalOcean:**
   ```
   App > Logs
   ```

2. **Ejecutar migraciones manualmente si es necesario:**
   - Los comandos en Procfile las ejecutan automáticamente
   - Si necesitas correr manualmente:
     ```
     ssh a tu app en DigitalOcean
     python manage.py migrate
     ```

3. **Crear superuser:**
   ```
   python manage.py createsuperuser
   ```

4. **Verificar reportes:**
   - Los workflows ejecutarán automáticamente
   - Puedes verificar en GitHub > Actions

## Troubleshooting

### Error de conexión a BD
- Verificar credenciales en variables de entorno
- Verificar que DO MySQL Managed DB está conectada
- Verificar firewall de DO permite conexiones desde App Platform

### Archivos estáticos no se sirven
- Verificar que `collectstatic` corrió sin errores
- Verificar `STATIC_URL` y `STATIC_ROOT` en settings
- WhiteNoise debe estar en MIDDLEWARE

### Reportes no se ejecutan
- Verificar GitHub Actions Secrets están configurados
- Revisar logs en GitHub > Actions
- Probar manualmente con "Run workflow"

## Variables de Entorno Referencia

Ver `.env.example` para plantilla completa.

## Comandos Útiles Localmente

```bash
# Activar venv
source .venvKasuChecador/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Colectar static files
python manage.py collectstatic --noinput

# Ejecutar localmente con gunicorn
gunicorn checador.wsgi:application --bind 0.0.0.0:8000

# Verificar configuración Django
python manage.py check
```
