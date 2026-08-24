# Solución al Error 400 en Health Check - DigitalOcean

## Problema Identificado
El health check endpoint `/health/` está devolviendo código **400 (Bad Request)** en lugar de **200 OK**.

## Cambios Realizados en el Código

### 1. Mejorado el endpoint health_check
**Archivo:** `attendance/views.py` (líneas 21-25)

```python
@csrf_exempt
@require_http_methods(["GET", "HEAD"])
def health_check(request):
    """Simple health check endpoint que responde 200 OK"""
    return HttpResponse(status=200)
```

**Mejoras:**
- Cambio de `JsonResponse` a `HttpResponse` (más simple)
- Agregado `@require_http_methods` para aceptar solo GET y HEAD
- Retorno directo de status 200

## Causas Posibles del Error 400

### 1. ❌ ALLOWED_HOSTS no configurado correctamente
**Solución:** Verificar que la variable de entorno `ALLOWED_HOSTS` en DigitalOcean incluya:
```
.ondigitalocean.app,*.ondigitalocean.app,localhost
```

**Pasos en DigitalOcean:**
1. Ir a tu app en DigitalOcean
2. Settings → App-Level Environment Variables
3. Verificar que `ALLOWED_HOSTS` incluya el dominio correcto
4. Formato: `.ondigitalocean.app` (con el punto inicial para wildcard)

### 2. ❌ CSRF_TRUSTED_ORIGINS incorrecto
**Solución:** Debe incluir el protocolo HTTPS:
```
https://*.ondigitalocean.app
```

**Verificar en DigitalOcean:**
- Variable: `CSRF_TRUSTED_ORIGINS`
- Valor: `https://*.ondigitalocean.app` o `https://kasuchecador-xxxxx.ondigitalocean.app`

### 3. ❌ Puerto HTTP incorrecto
**Verificar en app.yaml:**
```yaml
http_port: 8080
```

**Verificar en Procfile:**
```
web: gunicorn checador.wsgi:application --bind 0.0.0.0:8080
```

## Verificaciones Necesarias

### 1. Verificar Variables de Entorno en DigitalOcean
Ir a: **Settings → Environment Variables** y asegurarse de que existan:

```bash
DEBUG=False
SECRET_KEY=<tu-secret-key>
ALLOWED_HOSTS=.ondigitalocean.app,*.ondigitalocean.app
CSRF_TRUSTED_ORIGINS=https://*.ondigitalocean.app

# Base de datos
DATABASE=<nombre-db>
USERNAME=<usuario-db>
PASSWORD=<password-db>
HOST=<host-db>
DB_PORT=25060
SSLMODE=REQUIRED

# Email
EMAIL_HOST_PASSWORD=<sendgrid-api-key>

# Spaces (opcional)
SPACES_KEY=<spaces-key>
SPACES_SECRET=<spaces-secret>
SPACES_BUCKET=disco-loginco
SPACES_ENDPOINT=https://sfo3.digitaloceanspaces.com
```

### 2. Verificar Procfile
**Archivo:** `Procfile`
```
web: gunicorn checador.wsgi:application --bind 0.0.0.0:8080 --workers 2 --timeout 120
```

### 3. Verificar que las migraciones están aplicadas
En los logs de build debería aparecer:
```
Running migrations...
  Applying attendance.0005... OK
```

## Pasos para Resolver

### Opción 1: Hacer Deploy de los Cambios
1. Commit y push de los cambios:
```bash
git add attendance/views.py
git commit -m "Fix: Mejorar health check endpoint para deployment"
git push origin main
```

2. DigitalOcean automáticamente hará redeploy

3. Monitorear los logs en DigitalOcean para verificar que el health check pase

### Opción 2: Verificar Configuración en DigitalOcean

#### A. Verificar ALLOWED_HOSTS
1. Ir a tu app en DigitalOcean
2. Settings → App-Level Environment Variables
3. Editar `ALLOWED_HOSTS`
4. Valor recomendado: `.ondigitalocean.app,localhost,127.0.0.1`

#### B. Verificar el dominio real de tu app
1. En la página principal de tu app, copiar la URL completa
2. Ejemplo: `https://kasuchecador-abc123.ondigitalocean.app`
3. Extraer el subdominio: `kasuchecador-abc123.ondigitalocean.app`
4. Agregar a ALLOWED_HOSTS si no está

#### C. Actualizar CSRF_TRUSTED_ORIGINS
Debe incluir el protocolo:
```
https://kasuchecador-abc123.ondigitalocean.app
```
O usar wildcard:
```
https://*.ondigitalocean.app
```

### Opción 3: Probar Health Check Localmente

```bash
# Activar entorno virtual
source .venvKasuChecador/bin/activate

# Configurar variables de entorno mínimas
export DEBUG=False
export SECRET_KEY=test-key-local
export ALLOWED_HOSTS=localhost,127.0.0.1
export DATABASE=db
export USERNAME=user
export PASSWORD=pass
export HOST=localhost
export DB_PORT=3306

# Ejecutar servidor
python manage.py runserver 8080

# En otra terminal, probar el health check
curl -I http://localhost:8080/health/
# Debería retornar: HTTP/1.1 200 OK
```

## Debugging Adicional

### Ver logs en tiempo real en DigitalOcean
```bash
# Desde la interfaz web:
# Tu App → Runtime Logs → Deploy logs
```

### Probar el endpoint manualmente
Una vez que la app esté desplegada:
```bash
curl -I https://tu-app.ondigitalocean.app/health/
```

Respuesta esperada:
```
HTTP/2 200 
content-type: text/html; charset=utf-8
```

### Si sigue fallando, revisar:

1. **Logs de deploy completos** para ver si hay otros errores
2. **Verificar que Django esté escuchando en el puerto correcto** (8080)
3. **Confirmar que Gunicorn está iniciando correctamente**
4. **Revisar si hay errores de migración** que impidan el inicio de Django

## Comandos de Verificación Post-Deploy

```bash
# 1. Verificar health check
curl -I https://tu-app.ondigitalocean.app/health/

# 2. Verificar database status
curl https://tu-app.ondigitalocean.app/db-status/

# 3. Verificar que la app responde
curl https://tu-app.ondigitalocean.app/
```

## Checklist de Solución

- [ ] Cambios en `attendance/views.py` commiteados y pusheados
- [ ] `ALLOWED_HOSTS` incluye el dominio de DigitalOcean
- [ ] `CSRF_TRUSTED_ORIGINS` incluye `https://*.ondigitalocean.app`
- [ ] Health check en `.do/app.yaml` apunta a `/health/`
- [ ] Procfile tiene el puerto correcto (8080)
- [ ] Variables de entorno configuradas en DigitalOcean
- [ ] Logs de deploy no muestran errores de migración
- [ ] Curl al endpoint `/health/` retorna 200

## Resultado Esperado

Después de aplicar estos cambios, los logs deberían mostrar:
```
[04/Feb/2026 16:50:35] "GET /health/ HTTP/1.1" 200 0
System check identified no issues (0 silenced).
```

Y el deployment debería completarse exitosamente sin errores de health check.
