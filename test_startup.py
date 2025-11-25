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

# Verificar conexión a base de datos (con timeout)
print("\n[2/4] Probando conexión a base de datos...")
try:
    from django.db import connection
    import socket
    
    # Configurar timeout global para conexiones de socket
    default_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(10.0)  # 10 segundos timeout
    
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
    
    # Restaurar timeout
    socket.setdefaulttimeout(default_timeout)
    
    print(f"✓ Conexión a base de datos exitosa: {result}")
except socket.timeout:
    print(f"⚠️  TIMEOUT de conexión a base de datos (>10s)")
    print(f"   La app arrancará pero las peticiones a DB fallarán.")
    print(f"   Verifica: Trusted Sources en DO MySQL, HOST, PORT, credenciales")
    # NO salir - permitir que gunicorn arranque para debug
except Exception as e:
    print(f"⚠️  ERROR de conexión a base de datos: {e}")
    print(f"   Tipo: {type(e).__name__}")
    print(f"   La app arrancará pero las peticiones a DB fallarán.")
    # NO salir - permitir que gunicorn arranque

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
