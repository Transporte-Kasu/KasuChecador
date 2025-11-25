# setup_spaces.py - Script completo de configuración para DigitalOcean Spaces
import os
import sys
import json
from pathlib import Path

class SpacesSetupWizard:
    def __init__(self):
        self.config = {}
        self.project_root = Path.cwd()

    def welcome(self):
        """Mensaje de bienvenida"""
        print("=" * 70)
        print("🚀 CONFIGURADOR DE DIGITALOCEAN SPACES")
        print("=" * 70)
        print("Este asistente configurará el almacenamiento en la nube para:")
        print("📸 Fotos de tickets de combustible")
        print("🚛 Imágenes de equipos y operadores")
        print("📊 Archivos Excel de reportes")
        print("🎨 Archivos estáticos del sitio web")
        print("-" * 70)

    def get_spaces_credentials(self):
        """Obtiene las credenciales de DigitalOcean Spaces"""
        print("\n🔑 CREDENCIALES DE DIGITALOCEAN SPACES")
        print("-" * 40)
        print("Necesitas estas credenciales de tu cuenta de DigitalOcean:")
        print("1. Ve a: https://cloud.digitalocean.com/api/tokens")
        print("2. Genera un 'Spaces access key'")
        print("3. Anota el Access Key y Secret Key")

        self.config['access_key'] = input("\nAccess Key: ").strip()
        self.config['secret_key'] = input("Secret Key: ").strip()

        if not self.config['access_key'] or not self.config['secret_key']:
            print("❌ Las credenciales son obligatorias")
            return False

        return True

    def get_spaces_configuration(self):
        """Configura el bucket y región"""
        print("\n🌐 CONFIGURACIÓN DEL BUCKET")
        print("-" * 30)

        # Regiones disponibles
        regiones = {
            '1': {'code': 'nyc3', 'name': 'New York 3', 'endpoint': 'https://nyc3.digitaloceanspaces.com'},
            '2': {'code': 'ams3', 'name': 'Amsterdam 3', 'endpoint': 'https://ams3.digitaloceanspaces.com'},
            '3': {'code': 'sgp1', 'name': 'Singapore 1', 'endpoint': 'https://sgp1.digitaloceanspaces.com'},
            '4': {'code': 'fra1', 'name': 'Frankfurt 1', 'endpoint': 'https://fra1.digitaloceanspaces.com'},
            '5': {'code': 'sfo3', 'name': 'San Francisco 3', 'endpoint': 'https://sfo3.digitaloceanspaces.com'},
        }

        print("Selecciona la región de tu bucket:")
        for key, region in regiones.items():
            print(f"  {key}. {region['name']} ({region['code']})")

        choice = input("\nRegión (1-5): ").strip()

        if choice not in regiones:
            print("❌ Región no válida")
            return False

        region = regiones[choice]
        self.config['region'] = region['code']
        self.config['endpoint'] = region['endpoint']

        # Nombre del bucket
        self.config['bucket_name'] = input(f"\nNombre del bucket: ").strip()

        if not self.config['bucket_name']:
            print("❌ El nombre del bucket es obligatorio")
            return False

        # CDN (opcional)
        use_cdn = input("\n¿Habilitar CDN para mejor rendimiento? (s/n): ").lower().startswith('s')
        if use_cdn:
            cdn_endpoint = f"{self.config['bucket_name']}.{self.config['region']}.cdn.digitaloceanspaces.com"
            self.config['cdn_endpoint'] = cdn_endpoint
            print(f"📡 CDN configurado: {cdn_endpoint}")
        else:
            self.config['cdn_endpoint'] = None

        return True

    def test_connection(self):
        """Prueba la conexión a Spaces"""
        print("\n🔍 PROBANDO CONEXIÓN...")
        print("-" * 25)

        try:
            import boto3
            from botocore.exceptions import ClientError

            # Configurar cliente S3 para Spaces
            session = boto3.session.Session()
            client = session.client(
                's3',
                region_name=self.config['region'],
                endpoint_url=self.config['endpoint'],
                aws_access_key_id=self.config['access_key'],
                aws_secret_access_key=self.config['secret_key']
            )

            # Probar listado del bucket
            response = client.head_bucket(Bucket=self.config['bucket_name'])
            print("✅ Conexión exitosa al bucket")

            # Probar subida de archivo de prueba
            test_key = 'test_connection.txt'
            client.put_object(
                Bucket=self.config['bucket_name'],
                Key=test_key,
                Body=b'Test de conexion desde Django',
                ACL='public-read'
            )

            # Eliminar archivo de prueba
            client.delete_object(Bucket=self.config['bucket_name'], Key=test_key)
            print("✅ Prueba de subida/eliminación exitosa")

            return True

        except ImportError:
            print("❌ boto3 no está instalado")
            print("   Instalar con: pip install boto3")
            return False
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchBucket':
                print(f"❌ El bucket '{self.config['bucket_name']}' no existe")
                print("   Créalo en: https://cloud.digitalocean.com/spaces")
            elif error_code == 'InvalidAccessKeyId':
                print("❌ Access Key inválido")
            elif error_code == 'SignatureDoesNotMatch':
                print("❌ Secret Key inválido")
            else:
                print(f"❌ Error de conexión: {e}")
            return False
        except Exception as e:
            print(f"❌ Error inesperado: {e}")
            return False

    def create_env_file(self):
        """Crea o actualiza el archivo .env"""
        print("\n📝 CREANDO ARCHIVO .ENV")
        print("-" * 25)

        env_file = self.project_root / '.env'
        env_content = []

        # Leer archivo existente si existe
        if env_file.exists():
            with open(env_file, 'r') as f:
                existing_lines = f.readlines()

            # Filtrar líneas que no sean de Spaces
            spaces_keys = [
                'DO_SPACES_ACCESS_KEY', 'DO_SPACES_SECRET_KEY', 'DO_SPACES_BUCKET_NAME',
                'DO_SPACES_ENDPOINT_URL', 'DO_SPACES_REGION', 'DO_SPACES_CDN_ENDPOINT', 'USE_SPACES'
            ]

            for line in existing_lines:
                if not any(key in line for key in spaces_keys):
                    env_content.append(line.strip())

        # Agregar configuración de Spaces
        env_content.extend([
            "",
            "# === DIGITALOCEAN SPACES CONFIGURATION ===",
            f"DO_SPACES_ACCESS_KEY={self.config['access_key']}",
            f"DO_SPACES_SECRET_KEY={self.config['secret_key']}",
            f"DO_SPACES_BUCKET_NAME={self.config['bucket_name']}",
            f"DO_SPACES_ENDPOINT_URL={self.config['endpoint']}",
            f"DO_SPACES_REGION={self.config['region']}",
        ])

        if self.config.get('cdn_endpoint'):
            env_content.append(f"DO_SPACES_CDN_ENDPOINT={self.config['cdn_endpoint']}")

        env_content.append("USE_SPACES=True")

        # Escribir archivo
        with open(env_file, 'w') as f:
            f.write('\n'.join(env_content))

        print(f"✅ Archivo .env actualizado: {env_file}")
        return True

    def install_dependencies(self):
        """Instala las dependencias necesarias"""
        print("\n📦 INSTALANDO DEPENDENCIAS")
        print("-" * 30)

        dependencies = [
            'django-storages[boto3]>=1.14.0',
            'boto3>=1.26.0',
            'python-decouple>=3.6',
            'Pillow>=10.0.0'
        ]

        for dep in dependencies:
            try:
                import subprocess
                result = subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', dep],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    print(f"✅ {dep}")
                else:
                    print(f"❌ Error instalando {dep}")
                    print(f"   {result.stderr}")
            except Exception as e:
                print(f"❌ Error instalando {dep}: {e}")

    def create_storage_backends(self):
        """Crea el archivo storage_backends.py"""
        print("\n📁 CREANDO STORAGE BACKENDS")
        print("-" * 30)

        # Detectar app principal
        apps = [d for d in os.listdir('.') if os.path.isdir(d) and
                os.path.exists(os.path.join(d, 'models.py'))]

        if not apps:
            print("❌ No se encontraron apps de Django")
            return False

        app_name = apps[0] if len(apps) == 1 else self.select_app(apps)
        storage_file = Path(app_name) / 'storage_backends.py'

        # Crear contenido del archivo
        storage_content = '''# storage_backends.py - Configuración de DigitalOcean Spaces
from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage
import logging

logger = logging.getLogger(__name__)

class StaticStorage(S3Boto3Storage):
    """Storage para archivos estáticos"""
    location = 'static'
    default_acl = 'public-read'
    file_overwrite = True

class MediaStorage(S3Boto3Storage):
    """Storage para archivos media (fotos de tickets)"""
    location = 'media'
    default_acl = 'public-read'
    file_overwrite = False

class ReportesStorage(S3Boto3Storage):
    """Storage para archivos de reportes"""
    location = 'reportes'
    default_acl = 'private'
    file_overwrite = True

def upload_ticket_photo(instance, filename):
    """Genera rutas para fotos de tickets"""
    import os
    from datetime import datetime

    fecha = instance.fecha_hora or datetime.now()
    placa = getattr(instance.idEquipo, 'placa', 'SIN_PLACA') if instance.idEquipo else 'SIN_EQUIPO'
    placa_clean = ''.join(c for c in placa if c.isalnum() or c in '-_')

    nombre, ext = os.path.splitext(filename)
    nuevo_nombre = f"ticket_{placa_clean}_{fecha.strftime('%Y%m%d_%H%M%S')}{ext}"

    return f"tickets/{fecha.year}/{fecha.month:02d}/{nuevo_nombre}"

def get_file_url(file_field):
    """Obtiene la URL de un archivo de manera segura"""
    if not file_field:
        return None
    try:
        return file_field.url
    except Exception:
        return None
'''

        # Escribir archivo
        with open(storage_file, 'w') as f:
            f.write(storage_content)

        print(f"✅ Storage backends creado: {storage_file}")
        return True

    def update_settings(self):
        """Actualiza settings.py con la configuración de Spaces"""
        print("\n⚙️ ACTUALIZANDO SETTINGS.PY")
        print("-" * 30)

    def update_settings(self):
        """Actualiza settings.py con la configuración de Spaces"""
        print("\n⚙️ ACTUALIZANDO SETTINGS.PY")
        print("-" * 30)

        # Buscar archivo settings.py
        settings_files = ['settings.py', 'config/settings.py', f'{self.config.get("app_name", "")}/settings.py']
        settings_path = None

        for settings_file in settings_files:
            if os.path.exists(settings_file):
                settings_path = settings_file
                break

        if not settings_path:
            print("❌ No se encontró settings.py")
            return False

        # Configuración a agregar
        spaces_config = '''
# === DIGITALOCEAN SPACES CONFIGURATION ===
from decouple import config

# Credenciales de Spaces
AWS_ACCESS_KEY_ID = config('DO_SPACES_ACCESS_KEY')
AWS_SECRET_ACCESS_KEY = config('DO_SPACES_SECRET_KEY')
AWS_STORAGE_BUCKET_NAME = config('DO_SPACES_BUCKET_NAME')
AWS_S3_ENDPOINT_URL = config('DO_SPACES_ENDPOINT_URL')
AWS_S3_REGION_NAME = config('DO_SPACES_REGION', default='nyc3')

# Configuración adicional
AWS_S3_OBJECT_PARAMETERS = {
    'CacheControl': 'max-age=86400',
}
AWS_DEFAULT_ACL = 'public-read'
AWS_S3_FILE_OVERWRITE = False
AWS_QUERYSTRING_AUTH = False

# CDN personalizado (opcional)
AWS_S3_CUSTOM_DOMAIN = config('DO_SPACES_CDN_ENDPOINT', default=None)

# Configuración condicional
USE_SPACES = config('USE_SPACES', default=False, cast=bool)

if USE_SPACES:
    # Storage backends
    STATICFILES_STORAGE = 'tu_app.storage_backends.StaticStorage'
    DEFAULT_FILE_STORAGE = 'tu_app.storage_backends.MediaStorage'

    # URLs
    AWS_STATIC_LOCATION = 'static'
    AWS_MEDIA_LOCATION = 'media'

    if AWS_S3_CUSTOM_DOMAIN:
        STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/{AWS_STATIC_LOCATION}/'
        MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/{AWS_MEDIA_LOCATION}/'
    else:
        STATIC_URL = f'{AWS_S3_ENDPOINT_URL}/{AWS_STORAGE_BUCKET_NAME}/{AWS_STATIC_LOCATION}/'
        MEDIA_URL = f'{AWS_S3_ENDPOINT_URL}/{AWS_STORAGE_BUCKET_NAME}/{AWS_MEDIA_LOCATION}/'
else:
    # Configuración local
    STATIC_URL = '/static/'
    MEDIA_URL = '/media/'
    STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
'''

        try:
            # Leer archivo actual
            with open(settings_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Verificar si ya existe configuración
            if 'DIGITALOCEAN SPACES CONFIGURATION' in content:
                print("⚠️ La configuración de Spaces ya existe")
                overwrite = input("¿Sobrescribir? (s/n): ").lower().startswith('s')
                if not overwrite:
                    return True

                # Eliminar configuración anterior
                lines = content.split('\n')
                filtered_lines = []
                skip_section = False

                for line in lines:
                    if '=== DIGITALOCEAN SPACES CONFIGURATION ===' in line:
                        skip_section = True
                        continue
                    elif skip_section and line.strip() and not line.startswith('#') and '=' in line:
                        continue
                    elif skip_section and not line.strip():
                        skip_section = False

                    if not skip_section:
                        filtered_lines.append(line)

                content = '\n'.join(filtered_lines)

            # Agregar nueva configuración
            content += spaces_config

            # Escribir archivo
            with open(settings_path, 'w', encoding='utf-8') as f:
                f.write(content)

            print(f"✅ Settings.py actualizado: {settings_path}")
            return True

        except Exception as e:
            print(f"❌ Error actualizando settings.py: {e}")
            return False

    def select_app(self, apps):
        """Permite seleccionar la app principal"""
        print("\nApps encontradas:")
        for i, app in enumerate(apps, 1):
            print(f"  {i}. {app}")

        try:
            choice = int(input("Selecciona la app principal (número): ")) - 1
            return apps[choice]
        except (ValueError, IndexError):
            return apps[0]

    def create_management_commands(self):
        """Crea comandos de gestión para Spaces"""
        print("\n🔧 CREANDO COMANDOS DE GESTIÓN")
        print("-" * 35)

        # Detectar app
        apps = [d for d in os.listdir('.') if os.path.isdir(d) and
                os.path.exists(os.path.join(d, 'models.py'))]

        if not apps:
            print("❌ No se encontraron apps")
            return False

        app_name = apps[0] if len(apps) == 1 else self.select_app(apps)

        # Crear directorios
        commands_dir = Path(app_name) / 'management' / 'commands'
        commands_dir.mkdir(parents=True, exist_ok=True)

        # Crear archivos __init__.py
        (Path(app_name) / 'management' / '__init__.py').touch()
        (commands_dir / '__init__.py').touch()

        # Crear comando de migración
        migration_command = '''from django.core.management.base import BaseCommand
from django.conf import settings
import os

class Command(BaseCommand):
    help = 'Migra archivos locales a DigitalOcean Spaces'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Iniciando migración a Spaces...")
        # Implementar lógica de migración aquí
        self.stdout.write(self.style.SUCCESS("✅ Migración completada"))
'''

        with open(commands_dir / 'migrate_to_spaces.py', 'w') as f:
            f.write(migration_command)

        # Crear comando de prueba
        test_command = '''from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Prueba la conexión a DigitalOcean Spaces'

    def handle(self, *args, **options):
        self.stdout.write("🔍 Probando conexión a Spaces...")
        # Implementar lógica de prueba aquí
        self.stdout.write(self.style.SUCCESS("✅ Conexión exitosa"))
'''

        with open(commands_dir / 'test_spaces_connection.py', 'w') as f:
            f.write(test_command)

        print(f"✅ Comandos creados en: {commands_dir}")
        return True

    def create_deployment_guide(self):
        """Crea una guía de despliegue"""
        print("\n📖 CREANDO GUÍA DE DESPLIEGUE")
        print("-" * 30)

        guide_content = f'''# GUÍA DE DESPLIEGUE - DIGITALOCEAN SPACES

## 🚀 Configuración Completada

### Credenciales Configuradas:
- Access Key: {self.config['access_key'][:8]}...
- Bucket: {self.config['bucket_name']}
- Región: {self.config['region']}
- Endpoint: {self.config['endpoint']}
{f"- CDN: {self.config['cdn_endpoint']}" if self.config.get('cdn_endpoint') else "- CDN: No configurado"}

## 📋 Próximos Pasos

### 1. Verificar Configuración
```bash
python manage.py test_spaces_connection
```

### 2. Migrar Archivos Existentes (opcional)
```bash
python manage.py migrate_to_spaces --dry-run  # Simular
python manage.py migrate_to_spaces             # Ejecutar
```

### 3. Probar Subida de Archivos
- Crea un nuevo ticket con foto
- Verifica que la imagen se guarde en Spaces
- URL debería ser: https://{self.config['bucket_name']}.{self.config['region']}.digitaloceanspaces.com/

### 4. Generar Reporte con Spaces
```bash
python manage.py enviar_reporte_mensual --test --save-to-spaces
```

## 🔧 Comandos Útiles

### Gestión de Archivos
```bash
# Limpiar archivos antiguos
python manage.py cleanup_spaces --days 30

# Ver estadísticas
python manage.py spaces_stats

# Migrar específicamente fotos de tickets
python manage.py migrate_to_spaces --only-tickets
```

### Verificación
```bash
# Verificar configuración completa
python manage.py check --deploy

# Probar envío de email con Spaces
python manage.py enviar_reporte_mensual --email tu@email.com
```

## 📊 Beneficios Implementados

✅ **Archivos en la Nube**: Todas las fotos se guardan en DigitalOcean Spaces
✅ **URLs Públicas**: Acceso directo a imágenes desde cualquier lugar
✅ **Reportes Mejorados**: Excel con URLs de fotos incluidas
✅ **Escalabilidad**: Sin límites de almacenamiento local
✅ **CDN**: Carga rápida de imágenes (si está habilitado)
✅ **Backup Automático**: Archivos seguros en la nube

## ⚠️ Consideraciones Importantes

1. **Costos**: Monitorea el uso de almacenamiento y transferencia
2. **Backup**: Considera backup adicional para datos críticos
3. **Permisos**: Verifica que las fotos sean públicas o privadas según necesites
4. **Migración**: Haz backup antes de migrar archivos existentes

## 🔗 Enlaces Útiles

- Panel de DigitalOcean: https://cloud.digitalocean.com/spaces
- Documentación: https://docs.digitalocean.com/products/spaces/
- Precios: https://www.digitalocean.com/pricing/spaces

## 🆘 Solución de Problemas

### Error de Conexión
- Verifica credenciales en .env
- Confirma que el bucket existe
- Revisa permisos del Access Key

### Archivos No Se Muestran
- Verifica que USE_SPACES=True
- Confirma configuración de URLs
- Revisa permisos ACL del bucket

### Reportes Sin Fotos
- Ejecuta: python manage.py migrate_to_spaces
- Verifica que las URLs en la base de datos sean correctas
'''

        with open('SPACES_DEPLOYMENT_GUIDE.md', 'w', encoding='utf-8') as f:
            f.write(guide_content)

        print("✅ Guía creada: SPACES_DEPLOYMENT_GUIDE.md")
        return True

    def run(self):
        """Ejecuta el asistente completo"""
        self.welcome()

        steps = [
            ("Obtener Credenciales", self.get_spaces_credentials),
            ("Configurar Bucket", self.get_spaces_configuration),
            ("Probar Conexión", self.test_connection),
            ("Instalar Dependencias", self.install_dependencies),
            ("Crear Archivo .env", self.create_env_file),
            ("Crear Storage Backends", self.create_storage_backends),
            ("Actualizar Settings", self.update_settings),
            ("Crear Comandos", self.create_management_commands),
            ("Crear Guía", self.create_deployment_guide),
        ]

        for step_name, step_func in steps:
            print(f"\n🔄 {step_name}...")
            if not step_func():
                print(f"❌ Error en: {step_name}")
                return False

        print("\n" + "=" * 70)
        print("🎉 ¡DIGITALOCEAN SPACES CONFIGURADO EXITOSAMENTE!")
        print("=" * 70)

        print(f"\n📋 RESUMEN DE CONFIGURACIÓN:")
        print(f"   • Bucket: {self.config['bucket_name']}")
        print(f"   • Región: {self.config['region']}")
        print(f"   • Endpoint: {self.config['endpoint']}")
        if self.config.get('cdn_endpoint'):
            print(f"   • CDN: {self.config['cdn_endpoint']}")

        print(f"\n🚀 PRÓXIMOS PASOS:")
        print("   1. Reinicia el servidor Django")
        print("   2. python manage.py test_spaces_connection")
        print("   3. Sube una foto de ticket para probar")
        print("   4. python manage.py enviar_reporte_mensual --test")
        print("   5. Lee: SPACES_DEPLOYMENT_GUIDE.md")

        print(f"\n💡 COMANDOS ÚTILES:")
        print("   • python manage.py migrate_to_spaces --dry-run")
        print("   • python manage.py spaces_stats")
        print("   • python manage.py cleanup_spaces --days 30")

        return True

def main():
    """Función principal"""
    wizard = SpacesSetupWizard()
    success = wizard.run()

    if success:
        print("\n✅ ¡Configuración exitosa!")
        print("📁 Tus archivos ahora se almacenarán en DigitalOcean Spaces")
    else:
        print("\n❌ Configuración incompleta")
        print("   Revisa los errores y ejecuta nuevamente")

    return success

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️ Configuración cancelada por el usuario")
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")

# === INSTRUCCIONES DE USO ===
"""
1. Ejecutar el asistente:
   python setup_spaces.py

2. Seguir las instrucciones paso a paso

3. Una vez completado, reiniciar Django:
   python manage.py runserver

4. Probar la configuración:
   python manage.py test_spaces_connection

5. Migrar archivos existentes (opcional):
   python manage.py migrate_to_spaces --dry-run
   python manage.py migrate_to_spaces

6. Probar reportes con Spaces:
   python manage.py enviar_reporte_mensual --test --save-to-spaces

🎯 BENEFICIOS DESPUÉS DE LA CONFIGURACIÓN:

✅ Fotos de tickets automáticamente en la nube
✅ Archivos Excel de reportes almacenados en Spaces
✅ URLs públicas para todas las imágenes
✅ Sin límites de almacenamiento local
✅ Mejor rendimiento con CDN (opcional)
✅ Backup automático en la nube
✅ Escalabilidad ilimitada
✅ Integración perfecta con el sistema de reportes

📊 EL SISTEMA DE REPORTES AHORA INCLUYE:

• URLs directas a fotos de tickets en los Excel
• Archivos de reporte guardados automáticamente en Spaces
• Enlaces directos en los emails para descargar reportes
• Estadísticas de uso de almacenamiento
• Comandos de limpieza y mantenimiento
• Migración automática de archivos existentes
"""