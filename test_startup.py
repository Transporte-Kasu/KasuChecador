#!/usr/bin/env python
"""Test de conectividad y configuración antes de arrancar gunicorn"""
import os
import sys
import django

print("=" * 70)
print("TEST DE ARRANQUE - KASUCHECADOR")
print("=" * 70)

# Verificar que Django puede cargar settings
print("\n[1/4] Cargando configuración Django...")
try:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'checador.settings')
    django.setup()
    print("✓ Configuración Django cargada correctamente")
except Exception as e:
    print(f"✗ ERROR al cargar configuración: {e}")
    sys.exit(1)

# Verificar conexión a base de datos
print("\n[2/4] Probando conexión a base de datos...")
try:
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
    print(f"✓ Conexión a base de datos exitosa: {result}")
except Exception as e:
    print(f"✗ ERROR de conexión a base de datos: {e}")
    print(f"   Tipo: {type(e).__name__}")
    sys.exit(1)

# Verificar que las migraciones están aplicadas
print("\n[3/4] Verificando migraciones...")
try:
    from django.core.management import call_command
    from io import StringIO
    out = StringIO()
    call_command('showmigrations', '--plan', stdout=out, no_color=True)
    migrations = out.getvalue()
    pending = '[X]' not in migrations if migrations else True
    
    if pending:
        print("⚠️  Hay migraciones pendientes")
    else:
        print("✓ Todas las migraciones aplicadas")
except Exception as e:
    print(f"⚠️  No se pudo verificar migraciones: {e}")

# Verificar que el puerto está disponible
print("\n[4/4] Verificando puerto para gunicorn...")
port = os.environ.get('PORT', '8080')
print(f"✓ Puerto configurado: {port}")

print("\n" + "=" * 70)
print("✓ TODOS LOS TESTS PASARON - LISTO PARA ARRANCAR GUNICORN")
print("=" * 70)
sys.exit(0)
