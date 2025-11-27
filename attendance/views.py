from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.generic import CreateView, ListView
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q
from datetime import datetime, timedelta
from .models import (
    Empleado, Asistencia, TipoMovimiento, Visitante,
    RegistroVisita, TiempoExtra, ConfiguracionSistema
)
from .forms import VisitanteForm, CheckInForm
from .utils import enviar_email_visitante, generar_reporte_diario, generar_reporte_quincenal
import json
from django.views.decorators.csrf import csrf_exempt

# Health check endpoint para DigitalOcean
@csrf_exempt
def health_check(request):
    """Simple health check endpoint que responde 200 OK"""
    return JsonResponse({"status": "ok"})

@csrf_exempt
def db_status(request):
    """Check database connection status"""
    from django.db import connection
    import socket

    try:
        # Configurar timeout
        default_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(5.0)

        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()

        socket.setdefaulttimeout(default_timeout)

        return JsonResponse({
            "status": "connected",
            "database": connection.settings_dict['NAME'],
            "host": connection.settings_dict['HOST']
        })
    except socket.timeout:
        return JsonResponse({
            "status": "timeout",
            "error": "Database connection timed out after 5 seconds",
            "help": "Database may still be provisioning or Trusted Sources not configured"
        }, status=503)
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "error": str(e),
            "type": type(e).__name__
        }, status=503)

# Vista para tablet de recepción
def checkin_view(request):
    """Vista principal para la tablet de checkin en recepción"""
    if request.method == 'POST':
        form = CheckInForm(request.POST)
        if form.is_valid():
            qr_code = form.cleaned_data['qr_code']

            # Verificar si es empleado
            try:
                empleado = Empleado.objects.get(qr_uuid=qr_code, activo=True)
                return procesar_checkin_empleado(request, empleado)
            except Empleado.DoesNotExist:
                pass

            # Verificar si es visitante
            try:
                if qr_code.startswith('VISITANTE:'):
                    uuid_visitante = qr_code.replace('VISITANTE:', '')
                    visitante = Visitante.objects.get(qr_uuid=uuid_visitante)
                    return procesar_checkin_visitante(request, visitante)
            except Visitante.DoesNotExist:
                pass

            messages.error(request, 'Código QR no válido')
    else:
        form = CheckInForm()

    return render(request, 'attendance/checkin.html', {'form': form})

# Vista para tablet de recepción
def checkin_view_tablet(request):
    """Vista principal para la tablet de checkin en recepción"""
    if request.method == 'POST':
        form = CheckInForm(request.POST)
        if form.is_valid():
            qr_code = form.cleaned_data['qr_code']

            # Verificar si es empleado
            try:
                empleado = Empleado.objects.get(qr_uuid=qr_code, activo=True)
                return procesar_checkin_empleado(request, empleado, redirect_to='checkin_tablet')
            except Empleado.DoesNotExist:
                pass

            # Verificar si es visitante
            try:
                if qr_code.startswith('VISITANTE:'):
                    uuid_visitante = qr_code.replace('VISITANTE:', '')
                    visitante = Visitante.objects.get(qr_uuid=uuid_visitante)
                    return procesar_checkin_visitante(request, visitante, redirect_to='checkin_tablet')
            except Visitante.DoesNotExist:
                pass

            messages.error(request, 'Código QR no válido')
    else:
        form = CheckInForm()

    return render(request, 'attendance/checkin_tablet.html', {'form': form})

def procesar_checkin_empleado(request, empleado, redirect_to='checkin'):
    """Procesa el check-in de un empleado"""
    hoy = timezone.now().date()
    ahora = timezone.now().time()
    ultima_asistencia = Asistencia.objects.filter(
        empleado=empleado,
        fecha=hoy
    ).order_by('-hora').first()

    # Obtener tipo de horario del empleado
    tipo_horario = empleado.tipo_horario

    # Determinar el tipo de movimiento según el horario
    if not ultima_asistencia:
        tipo = TipoMovimiento.ENTRADA
    else:
        # Lógica según tipo de horario
        if tipo_horario and tipo_horario.es_turno_24h:
            # Turnos de 24 horas: solo ENTRADA y SALIDA
            if ultima_asistencia.tipo_movimiento == TipoMovimiento.ENTRADA:
                tipo = TipoMovimiento.SALIDA
            else:
                tipo = TipoMovimiento.ENTRADA
        elif tipo_horario and not tipo_horario.tiene_horario_comida:
            # Horario regular sin comida: solo ENTRADA y SALIDA
            if ultima_asistencia.tipo_movimiento == TipoMovimiento.ENTRADA:
                tipo = TipoMovimiento.SALIDA
            else:
                tipo = TipoMovimiento.ENTRADA
        else:
            # Horario con comida (default): secuencia completa
            if ultima_asistencia.tipo_movimiento == TipoMovimiento.ENTRADA:
                tipo = TipoMovimiento.SALIDA_COMIDA
            elif ultima_asistencia.tipo_movimiento == TipoMovimiento.SALIDA_COMIDA:
                tipo = TipoMovimiento.ENTRADA_COMIDA
            elif ultima_asistencia.tipo_movimiento == TipoMovimiento.ENTRADA_COMIDA:
                tipo = TipoMovimiento.SALIDA
            else:
                tipo = TipoMovimiento.ENTRADA

    # Validar horario de comida si aplica
    if tipo == TipoMovimiento.SALIDA_COMIDA:
        if tipo_horario and tipo_horario.tiene_horario_comida:
            # Validar que esté dentro del rango de comida
            if tipo_horario.hora_inicio_comida and tipo_horario.hora_fin_comida:
                if not (tipo_horario.hora_inicio_comida <= ahora <= tipo_horario.hora_fin_comida):
                    messages.error(
                        request,
                        f"No puedes salir a comer fuera del horario permitido ({tipo_horario.hora_inicio_comida.strftime('%H:%M')} - {tipo_horario.hora_fin_comida.strftime('%H:%M')})"
                    )
                    return redirect(redirect_to)
        elif tipo_horario and not tipo_horario.tiene_horario_comida:
            # No tiene horario de comida, no permitir este movimiento
            messages.error(request, "Tu horario no incluye salida a comida")
            return redirect(redirect_to)

    asistencia = Asistencia.objects.create(
        empleado=empleado,
        tipo_movimiento=tipo
    )

    # Calcular retardo si es entrada
    if tipo == TipoMovimiento.ENTRADA:
        config = ConfiguracionSistema.objects.first()
        if tipo_horario and tipo_horario.hora_entrada:
            asistencia.calcular_retardo(str(tipo_horario.hora_entrada), tipo_horario.minutos_tolerancia)
        elif config:
            asistencia.calcular_retardo(str(config.hora_entrada), config.minutos_tolerancia)
        asistencia.save()

    mensaje = f"{empleado.user.get_full_name()} - {tipo}"
    if asistencia.retardo:
        mensaje += f" (Retardo: {asistencia.minutos_retardo} min)"

    messages.success(request, mensaje)
    return redirect(redirect_to)

def procesar_checkin_visitante(request, visitante, redirect_to='checkin'):
    """Procesa el check-in de un visitante"""
    # Verificar si ya tiene un registro abierto
    registro_abierto = RegistroVisita.objects.filter(
        visitante=visitante,
        hora_salida__isnull=True
    ).first()

    if registro_abierto:
        # Registrar salida
        registro_abierto.hora_salida = timezone.now()
        registro_abierto.save()
        messages.success(request, f"Salida registrada: {visitante.nombre}")
    else:
        # Registrar entrada
        RegistroVisita.objects.create(visitante=visitante)
        messages.success(request, f"Entrada registrada: {visitante.nombre} - Visita a {visitante.departamento_visita}")

    return redirect(redirect_to)

# Vista de formulario de visitantes (pública)
class VisitanteCreateView(CreateView):
    model = Visitante
    form_class = VisitanteForm
    template_name = 'attendance/visitante_form.html'
    success_url = '/visitante/exito/'

    def form_valid(self, form):
        response = super().form_valid(form)
        # Enviar email con QR al visitante y al departamento
        enviar_email_visitante(self.object)
        messages.success(self.request, 'Tu visita ha sido registrada. Revisa tu correo para el código QR.')
        return response

def visitante_exito(request):
    """Vista de confirmación después de registrar visita"""
    return render(request, 'attendance/visitante_exito.html')

# Dashboard para gerencia
def dashboard_view(request):
    """Dashboard con estadísticas de asistencia"""
    hoy = timezone.now().date()

    # Estadísticas del día
    asistencias_hoy = Asistencia.objects.filter(
        fecha=hoy,
        tipo_movimiento=TipoMovimiento.ENTRADA
    )

    total_empleados = Empleado.objects.filter(activo=True).count()
    llegaron_hoy = asistencias_hoy.count()
    retardos_hoy = asistencias_hoy.filter(retardo=True).count()

    # Empleados con retardos consecutivos (últimos 5 días)
    fecha_inicio = hoy - timedelta(days=5)
    empleados_retardos = []

    for empleado in Empleado.objects.filter(activo=True):
        retardos = Asistencia.objects.filter(
            empleado=empleado,
            fecha__gte=fecha_inicio,
            fecha__lte=hoy,
            tipo_movimiento=TipoMovimiento.ENTRADA,
            retardo=True
        ).count()

        if retardos >= 3:
            empleados_retardos.append({
                'empleado': empleado,
                'retardos': retardos
            })


    inicio_dia = timezone.make_aware(datetime.combine(hoy, datetime.min.time()))
    fin_dia = timezone.make_aware(datetime.combine(hoy, datetime.max.time()))

    visitas_hoy = RegistroVisita.objects.filter(
        hora_entrada__gte=inicio_dia,
        hora_entrada__lte=fin_dia
    ).select_related('visitante', 'visitante__departamento_visita').order_by('-hora_entrada')

    context = {
        'total_empleados': total_empleados,
        'llegaron_hoy': llegaron_hoy,
        'retardos_hoy': retardos_hoy,
        'empleados_retardos': empleados_retardos,
        'visitas_hoy': visitas_hoy,
        'fecha': hoy,
    }

    return render(request, 'attendance/dashboard.html', context)

# Vista de reportes
def reporte_mensual_view(request, mes=None, anio=None):
    """Vista para consultar reportes mensuales"""
    if not mes or not anio:
        hoy = timezone.now()
        mes = hoy.month
        anio = hoy.year

    # Obtener todas las asistencias del mes
    asistencias = Asistencia.objects.filter(
        fecha__month=mes,
        fecha__year=anio
    ).select_related('empleado', 'empleado__user')

    # Agrupar por empleado
    empleados_data = {}
    for asistencia in asistencias:
        emp_id = asistencia.empleado.id
        if emp_id not in empleados_data:
            empleados_data[emp_id] = {
                'empleado': asistencia.empleado,
                'total_dias': 0,
                'retardos': 0,
                'total_minutos_retardo': 0,
            }

        if asistencia.tipo_movimiento == TipoMovimiento.ENTRADA:
            empleados_data[emp_id]['total_dias'] += 1
            if asistencia.retardo:
                empleados_data[emp_id]['retardos'] += 1
                empleados_data[emp_id]['total_minutos_retardo'] += asistencia.minutos_retardo

    context = {
        'mes': mes,
        'anio': anio,
        'empleados_data': empleados_data.values(),
        'years_disponibles': range(2024, datetime.now().year + 1), # Generacion de years
    }

    return render(request, 'attendance/reporte_mensual.html', context)