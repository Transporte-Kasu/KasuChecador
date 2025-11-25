#!/usr/bin/env python
"""Script para verificar variables de entorno en DigitalOcean"""
import os
import sys

print("=" * 60)
print("VERIFICACIÓN DE VARIABLES DE ENTORNO")
print("=" * 60)

required_vars = [
    'SECRET_KEY',
    'DEBUG',
    'ALLOWED_HOSTS',
    'USERNAME',
    'PASSWORD',
    'HOST',
    'PORT',
    'DATABASE',
    'SSLMODE',
    'EMAIL_HOST_PASSWORD',
]

missing = []
for var in required_vars:
    value = os.environ.get(var)
    if value:
        # Ocultar valores sensibles
        if var in ['SECRET_KEY', 'PASSWORD', 'EMAIL_HOST_PASSWORD']:
            display = value[:5] + '***' if len(value) > 5 else '***'
        else:
            display = value
        print(f"✓ {var} = {display}")
    else:
        print(f"✗ {var} = NO CONFIGURADA")
        missing.append(var)

print("=" * 60)

# Verificar PORT para gunicorn
port = os.environ.get('PORT')
if port:
    print(f"✓ PORT (para gunicorn) = {port}")
else:
    print("✗ PORT = NO CONFIGURADA (DigitalOcean debe establecerla automáticamente)")

print("=" * 60)

if missing:
    print(f"\n⚠️  FALTAN {len(missing)} VARIABLES:")
    for var in missing:
        print(f"   - {var}")
    sys.exit(1)
else:
    print("\n✓ Todas las variables requeridas están configuradas")
    sys.exit(0)
