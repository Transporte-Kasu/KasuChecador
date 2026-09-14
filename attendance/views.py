from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse, Http404
from django.views.generic import CreateView, ListView
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Count, Q
from datetime import datetime, timedelta
from django.views.decorators.http import require_http_methods
from .models import (
    Empleado, Asistencia, TipoMovimiento, Visitante,
    RegistroVisita, TiempoExtra, ConfiguracionSistema,
    SolicitudPermiso, SolicitudVacaciones, EstadoSolicitud, TipoAusencia,
    AsignacionTurnoDiaria, TurnoRotativo, TipoReporte, OrigenEnvio,
    ConfiguracionReporte, EnvioReporte
)
from .forms import VisitanteForm, CheckInForm
from .utils import (
    enviar_email_visitante, generar_reporte_diario, generar_reporte_quincenal,
    generar_reporte_semanal, generar_reporte_mensual, generar_reporte_tiempo_extra_mensual,
    dia_quincena_actual
)
import json
from django.views.decorators.csrf import csrf_exempt

# Health check endpoint para DigitalOcean
@csrf_exempt
def health_check(request):
    """Simple health check endpoint que responde 200 OK"""
    # Responder a cualquier método HTTP para evitar problemas
    return HttpResponse("OK", status=200, content_type="text/plain")

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

            # Verificar si es visitante (debe ir primero para evitar error de UUID)
            if qr_code.startswith('VISITANTE:'):
                try:
                    uuid_visitante = qr_code.replace('VISITANTE:', '')
                    visitante = Visitante.objects.get(qr_uuid=uuid_visitante)
                    return procesar_checkin_visitante(request, visitante)
                except Visitante.DoesNotExist:
                    messages.error(request, 'Visitante no encontrado')
                    return redirect('checkin')

            # Verificar si es empleado
            try:
                empleado = Empleado.objects.get(qr_uuid=qr_code, activo=True)
                return procesar_checkin_empleado(request, empleado)
            except Empleado.DoesNotExist:
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
    hoy = timezone.localdate()
    ahora = timezone.localtime().time()

    # === VALIDAR PERMISOS Y VACACIONES ===
    
    # Verificar si tiene vacaciones aprobadas para hoy
    vacaciones_activas = SolicitudVacaciones.objects.filter(
        empleado=empleado,
        fecha_inicio__lte=hoy,
        fecha_fin__gte=hoy,
        estado__in=[EstadoSolicitud.APROBADO_JEFE, EstadoSolicitud.APROBADO_GERENCIA]
    ).first()
    
    if vacaciones_activas:
        messages.warning(
            request,
            f"{empleado.user.get_full_name()} - Tienes vacaciones aprobadas del {vacaciones_activas.fecha_inicio} al {vacaciones_activas.fecha_fin}. No deberías estar registrando asistencia."
        )
        # Permitir el registro pero con advertencia
    
    # Verificar si tiene permiso de día completo aprobado para hoy
    permiso_dia_completo = SolicitudPermiso.objects.filter(
        empleado=empleado,
        tipo_ausencia=TipoAusencia.DIAS_COMPLETOS,
        fecha_inicio__lte=hoy,
        fecha_fin__gte=hoy,
        estado__in=[EstadoSolicitud.APROBADO_JEFE, EstadoSolicitud.APROBADO_GERENCIA]
    ).first()
    
    if permiso_dia_completo:
        messages.warning(
            request,
            f"{empleado.user.get_full_name()} - Tienes permiso aprobado para hoy ({permiso_dia_completo.tipo_permiso.nombre}). No deberías estar registrando asistencia."
        )
        # Permitir el registro pero con advertencia
    
    # Verificar si tiene permiso por horas aprobado para esta hora
    permiso_horas = SolicitudPermiso.objects.filter(
        empleado=empleado,
        tipo_ausencia=TipoAusencia.HORAS,
        fecha_inicio=hoy,
        estado__in=[EstadoSolicitud.APROBADO_JEFE, EstadoSolicitud.APROBADO_GERENCIA]
    ).first()
    
    if permiso_horas and permiso_horas.hora_inicio and permiso_horas.hora_fin:
        # Verificar si la hora actual está dentro del rango del permiso
        if permiso_horas.hora_inicio <= ahora <= permiso_horas.hora_fin:
            messages.info(
                request,
                f"{empleado.user.get_full_name()} - Tienes permiso por horas de {permiso_horas.hora_inicio.strftime('%H:%M')} a {permiso_horas.hora_fin.strftime('%H:%M')}."
            )
    
    # === CONTINUAR CON LÓGICA NORMAL ===
    
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
        # Verificar si el empleado tiene horario de comida
        tiene_comida = False
        if tipo_horario:
            # Para turnos de 24h, nunca hay comida
            if tipo_horario.es_turno_24h:
                tiene_comida = False
            else:
                # Usar el campo tiene_horario_comida
                tiene_comida = tipo_horario.tiene_horario_comida
        
        # Si NO tiene horario de comida, alternar entre ENTRADA y SALIDA solamente
        if not tiene_comida:
            if ultima_asistencia.tipo_movimiento == TipoMovimiento.ENTRADA:
                tipo = TipoMovimiento.SALIDA
            else:
                # Cualquier otra checada reinicia el ciclo
                tipo = TipoMovimiento.ENTRADA
        else:
            # Horario CON comida: secuencia completa ENTRADA → SALIDA_COMIDA → ENTRADA_COMIDA → SALIDA
            if ultima_asistencia.tipo_movimiento == TipoMovimiento.ENTRADA:
                tipo = TipoMovimiento.SALIDA_COMIDA
            elif ultima_asistencia.tipo_movimiento == TipoMovimiento.SALIDA_COMIDA:
                tipo = TipoMovimiento.ENTRADA_COMIDA
            elif ultima_asistencia.tipo_movimiento == TipoMovimiento.ENTRADA_COMIDA:
                tipo = TipoMovimiento.SALIDA
            else:
                # Si hay algún caso extraño (SALIDA), reiniciar ciclo
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

    # Construir mensaje informativo
    nombre = empleado.user.get_full_name()
    hora_registro = asistencia.hora.strftime('%H:%M')
    
    # Mensaje base según tipo de movimiento
    tipo_display = asistencia.get_tipo_movimiento_display()
    mensaje = f"✅ {nombre} - {tipo_display} ({hora_registro})"
    
    # Agregar info de retardo si aplica
    if asistencia.retardo:
        mensaje += f" ⚠️ Retardo: {asistencia.minutos_retardo} min"
    
    # Contar checadas del día para dar contexto
    total_checadas_hoy = Asistencia.objects.filter(
        empleado=empleado,
        fecha=hoy
    ).count()
    
    # Agregar info adicional según el tipo
    if tipo == TipoMovimiento.ENTRADA:
        mensaje += f" | Checada #{total_checadas_hoy}"
    elif tipo == TipoMovimiento.SALIDA:
        if tiene_comida:
            mensaje += f" (Final del día) | Total checadas: {total_checadas_hoy}"
        else:
            mensaje += f" | Checada #{total_checadas_hoy}"
    elif tipo == TipoMovimiento.SALIDA_COMIDA:
        mensaje += " 🍽️"
    elif tipo == TipoMovimiento.ENTRADA_COMIDA:
        mensaje += " 💼"

    messages.success(request, mensaje)
    return redirect(redirect_to)

def procesar_checkin_visitante(request, visitante, redirect_to='checkin'):
    """Procesa el check-in de un visitante"""
    # Validar que el QR esté activo
    if not visitante.qr_activo:
        messages.error(
            request, 
            f"Código QR inactivo para {visitante.nombre}. La visita ya finalizó. Debe registrar una nueva visita."
        )
        return redirect(redirect_to)
    
    # Verificar si ya tiene un registro abierto
    registro_abierto = RegistroVisita.objects.filter(
        visitante=visitante,
        hora_salida__isnull=True
    ).first()

    if registro_abierto:
        # Registrar salida y desactivar QR
        registro_abierto.hora_salida = timezone.now()
        registro_abierto.save()
        
        # Desactivar el QR después de la salida
        visitante.qr_activo = False
        visitante.save(update_fields=['qr_activo'])
        
        messages.success(request, f"Salida registrada: {visitante.nombre}. El código QR ha sido desactivado.")
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
@login_required
def dashboard_view(request):
    """Dashboard con estadísticas de asistencia"""
    hoy = timezone.localdate()

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

    reportes_info = []
    for tipo_valor, tipo_label in TipoReporte.choices:
        config_reporte = ConfiguracionReporte.objects.filter(tipo=tipo_valor).first()
        destinatarios_count = (
            config_reporte.destinatarios.filter(activo=True).count() if config_reporte else 0
        )
        ultimo_envio = EnvioReporte.objects.filter(tipo=tipo_valor).first()
        reportes_info.append({
            'tipo': tipo_valor,
            'label': tipo_label,
            'destinatarios_count': destinatarios_count,
            'ultimo_envio': ultimo_envio,
        })

    context = {
        'total_empleados': total_empleados,
        'llegaron_hoy': llegaron_hoy,
        'retardos_hoy': retardos_hoy,
        'empleados_retardos': empleados_retardos,
        'fecha': hoy,
        'active_nav': 'dashboard',
        'reportes_info': reportes_info,
    }

    return render(request, 'attendance/dashboard.html', context)

# Vista de reportes
@login_required
def reporte_mensual_view(request, mes=None, anio=None):
    """Vista para consultar reportes mensuales"""
    # El formulario de selección de período envía mes/año como query params (GET),
    # ya que la URL sin parámetros no captura mes/anio en la ruta.
    mes = request.GET.get('mes') or mes
    anio = request.GET.get('anio') or anio
    mes = int(mes) if mes else None
    anio = int(anio) if anio else None

    if not mes or not anio:
        hoy = timezone.localdate()
        mes = mes or hoy.month
        anio = anio or hoy.year

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
                'dias_unicos': set(),  # Usar set para días únicos
                'retardos': 0,
                'total_minutos_retardo': 0,
            }

        if asistencia.tipo_movimiento == TipoMovimiento.ENTRADA:
            # Agregar fecha al set de días únicos
            empleados_data[emp_id]['dias_unicos'].add(asistencia.fecha)
            if asistencia.retardo:
                empleados_data[emp_id]['retardos'] += 1
                empleados_data[emp_id]['total_minutos_retardo'] += asistencia.minutos_retardo
    
    # Convertir sets a conteo de días y calcular faltas
    from attendance.utils import calcular_faltas_empleado
    for emp_id, data in empleados_data.items():
        data['total_dias'] = len(data['dias_unicos'])
        del data['dias_unicos']  # Eliminar el set ya que no es serializable para template
        data['faltas'], _ = calcular_faltas_empleado(
            data['empleado'], mes, anio, data['total_dias']
        )

    # Calcular total de retardos
    total_retardos = sum(data['retardos'] for data in empleados_data.values())
    
    # Si se solicita formato Excel, generar y descargar
    if request.GET.get('formato') == 'excel':
        from django.http import HttpResponse
        from attendance.utils import generar_excel_reporte_mensual
        
        excel_buffer = generar_excel_reporte_mensual(mes, anio)
        nombre_archivo = f"reporte_mensual_{anio}_{mes:02d}.xlsx"
        
        response = HttpResponse(
            excel_buffer.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
        return response
    
    context = {
        'mes': mes,
        'anio': anio,
        'empleados_data': empleados_data.values(),
        'total_retardos': total_retardos,
        'years_disponibles': range(2024, timezone.localdate().year + 1),
        'active_nav': 'reportes',
    }

    return render(request, 'attendance/reporte_mensual.html', context)

# Lista de visitantes
def visitantes_list_view(request):
    """Lista de todos los visitantes"""
    visitantes = Visitante.objects.select_related(
        'departamento_visita'
    ).order_by('-fecha_visita', '-hora_visita')

    context = {
        'visitantes': visitantes,
        'active_nav': 'visitantes',
    }
    return render(request, 'attendance/visitantes_list.html', context)

# ========== MÓDULO DE SEGURIDAD ==========

def seguridad_visitantes_view(request):
    """Panel de seguridad: listado de visitantes del día con registros de entrada/salida"""
    hoy = timezone.localdate()

    visitantes_hoy = Visitante.objects.filter(
        fecha_visita=hoy
    ).select_related('departamento_visita').order_by('-hora_visita')

    # Agregar info de registro de entrada/salida a cada visitante
    visitas_data = []
    for visitante in visitantes_hoy:
        registro = RegistroVisita.objects.filter(visitante=visitante).order_by('-hora_entrada').first()
        visitas_data.append({
            'visitante': visitante,
            'hora_entrada': registro.hora_entrada if registro else None,
            'hora_salida': registro.hora_salida if registro else None,
            'activo': registro and not registro.hora_salida if registro else False,
        })

    context = {
        'visitas_data': visitas_data,
        'fecha': hoy,
        'total_visitas': len(visitas_data),
    }
    return render(request, 'attendance/seguridad_visitantes.html', context)

@csrf_exempt
@require_http_methods(["POST"])
def verificar_visitante_qr(request):
    """Endpoint AJAX para verificar datos de un visitante por QR (solo consulta)"""
    try:
        data = json.loads(request.body)
        qr_code = data.get('qr_code', '').strip()

        if not qr_code:
            return JsonResponse({'error': 'Código QR vacío'}, status=400)

        # Extraer UUID del código QR
        uuid_str = qr_code.replace('VISITANTE:', '') if qr_code.startswith('VISITANTE:') else qr_code

        try:
            visitante = Visitante.objects.select_related('departamento_visita').get(qr_uuid=uuid_str)
        except (Visitante.DoesNotExist, ValueError):
            return JsonResponse({'error': 'Visitante no encontrado'}, status=404)

        # Obtener último registro de visita
        registro = RegistroVisita.objects.filter(visitante=visitante).order_by('-hora_entrada').first()

        response_data = {
            'nombre': visitante.nombre,
            'empresa': visitante.empresa or 'N/A',
            'telefono': visitante.telefono,
            'departamento': visitante.departamento_visita.nombre,
            'motivo': visitante.motivo,
            'fecha_visita': visitante.fecha_visita.strftime('%d/%m/%Y'),
            'hora_visita': visitante.hora_visita.strftime('%H:%M'),
            'qr_activo': visitante.qr_activo,
            'hora_entrada': registro.hora_entrada.strftime('%d/%m/%Y %H:%M') if registro else None,
            'hora_salida': registro.hora_salida.strftime('%d/%m/%Y %H:%M') if registro and registro.hora_salida else None,
            'estado': 'Activo' if (registro and not registro.hora_salida) else ('Finalizado' if (registro and registro.hora_salida) else 'Sin registro'),
        }

        return JsonResponse(response_data)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Datos inválidos'}, status=400)

# ========== ASIGNACIÓN DE TURNOS MENSUAL ==========

@login_required
def asignacion_turnos_mensual(request, mes=None, anio=None):
    """Vista tipo Excel para asignación de turnos mensuales"""
    import calendar
    from datetime import date
    
    # Si no se especifica mes/año, usar el actual
    if not mes or not anio:
        hoy = timezone.now()
        mes = hoy.month
        anio = hoy.year
    
    mes = int(mes)
    anio = int(anio)
    
    # Obtener empleados activos
    empleados = Empleado.objects.filter(activo=True).select_related('user').order_by('user__first_name')
    
    # Obtener número de días en el mes
    num_dias = calendar.monthrange(anio, mes)[1]
    
    # Crear lista de días con información
    dias_del_mes = []
    nombres_dias = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
    
    for dia in range(1, num_dias + 1):
        fecha = date(anio, mes, dia)
        dia_semana_num = fecha.weekday()  # 0=Lunes, 6=Domingo
        dias_del_mes.append({
            'numero': dia,
            'fecha': fecha,
            'dia_semana': nombres_dias[dia_semana_num],
            'es_fin_semana': dia_semana_num >= 5  # Sábado o Domingo
        })
    
    # Obtener asignaciones existentes para este mes
    asignaciones = AsignacionTurnoDiaria.objects.filter(
        fecha__year=anio,
        fecha__month=mes
    ).select_related('empleado', 'turno_rotativo')
    
    # Crear diccionario de asignaciones por empleado y fecha
    asignaciones_dict = {}
    for asig in asignaciones:
        key = f"{asig.empleado.id}_{asig.fecha}"
        asignaciones_dict[key] = asig
    
    # Obtener turnos disponibles
    turnos_disponibles = TurnoRotativo.objects.all().order_by('nombre')
    
    # Construir datos para la tabla
    empleados_data = []
    for empleado in empleados:
        dias_empleado = []
        for dia_info in dias_del_mes:
            key = f"{empleado.id}_{dia_info['fecha']}"
            asignacion = asignaciones_dict.get(key)
            
            if asignacion:
                if asignacion.es_descanso:
                    celda_data = {
                        'tipo': 'descanso',
                        'texto': 'DESC',
                        'color': 'bg-gray-200',
                        'asignacion_id': asignacion.id
                    }
                elif asignacion.turno_rotativo:
                    turno_txt = f"{asignacion.turno_rotativo.nombre}"
                    color = 'bg-yellow-100' if asignacion.cruza_medianoche else 'bg-blue-100'
                    celda_data = {
                        'tipo': 'turno',
                        'texto': turno_txt,
                        'horario': f"{asignacion.hora_entrada.strftime('%H:%M')}-{asignacion.hora_salida.strftime('%H:%M')}",
                        'color': color,
                        'cruza_medianoche': asignacion.cruza_medianoche,
                        'asignacion_id': asignacion.id
                    }
                elif asignacion.hora_entrada and asignacion.hora_salida:
                    horario_txt = f"{asignacion.hora_entrada.strftime('%H:%M')}-{asignacion.hora_salida.strftime('%H:%M')}"
                    color = 'bg-yellow-100' if asignacion.cruza_medianoche else 'bg-green-100'
                    celda_data = {
                        'tipo': 'personalizado',
                        'texto': horario_txt,
                        'horario': horario_txt,
                        'color': color,
                        'cruza_medianoche': asignacion.cruza_medianoche,
                        'asignacion_id': asignacion.id
                    }
                else:
                    celda_data = {
                        'tipo': 'sin_asignar',
                        'texto': '',
                        'color': 'bg-white',
                        'asignacion_id': None
                    }
            else:
                celda_data = {
                    'tipo': 'sin_asignar',
                    'texto': '',
                    'color': 'bg-white',
                    'asignacion_id': None
                }
            
            celda_data['fecha'] = dia_info['fecha']
            dias_empleado.append(celda_data)
        
        empleados_data.append({
            'empleado': empleado,
            'dias': dias_empleado
        })
    
    # Navegación de meses
    mes_anterior = mes - 1 if mes > 1 else 12
    anio_anterior = anio if mes > 1 else anio - 1
    mes_siguiente = mes + 1 if mes < 12 else 1
    anio_siguiente = anio if mes < 12 else anio + 1
    
    nombre_mes = calendar.month_name[mes]
    
    context = {
        'mes': mes,
        'anio': anio,
        'nombre_mes': nombre_mes,
        'dias_del_mes': dias_del_mes,
        'empleados_data': empleados_data,
        'turnos_disponibles': turnos_disponibles,
        'mes_anterior': mes_anterior,
        'anio_anterior': anio_anterior,
        'mes_siguiente': mes_siguiente,
        'anio_siguiente': anio_siguiente,
        'active_nav': 'turnos',
    }
    
    return render(request, 'attendance/asignacion_turnos.html', context)

@csrf_exempt
def guardar_asignacion_turno(request):
    """Endpoint AJAX para guardar/actualizar asignación de turno"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    try:
        data = json.loads(request.body)
        empleado_id = data.get('empleado_id')
        fecha_str = data.get('fecha')
        tipo_asignacion = data.get('tipo')  # 'turno', 'descanso', 'personalizado', 'eliminar'
        turno_id = data.get('turno_id')
        hora_entrada = data.get('hora_entrada')
        hora_salida = data.get('hora_salida')
        
        # Validar campos requeridos
        if not empleado_id or not fecha_str:
            return JsonResponse({'error': 'Faltan datos requeridos'}, status=400)
        
        empleado = Empleado.objects.get(id=empleado_id)
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        
        # Eliminar asignación si existe
        if tipo_asignacion == 'eliminar':
            AsignacionTurnoDiaria.objects.filter(empleado=empleado, fecha=fecha).delete()
            return JsonResponse({'success': True, 'mensaje': 'Asignación eliminada'})
        
        # Crear o actualizar asignación
        asignacion, created = AsignacionTurnoDiaria.objects.get_or_create(
            empleado=empleado,
            fecha=fecha
        )
        
        if tipo_asignacion == 'descanso':
            asignacion.es_descanso = True
            asignacion.turno_rotativo = None
            asignacion.hora_entrada = None
            asignacion.hora_salida = None
            mensaje = 'Día de descanso asignado'
        
        elif tipo_asignacion == 'turno' and turno_id:
            turno = TurnoRotativo.objects.get(id=turno_id)
            asignacion.es_descanso = False
            asignacion.turno_rotativo = turno
            asignacion.hora_entrada = turno.hora_entrada
            asignacion.hora_salida = turno.hora_salida
            mensaje = f'Turno {turno.nombre} asignado'
        
        elif tipo_asignacion == 'personalizado' and hora_entrada and hora_salida:
            from datetime import time
            asignacion.es_descanso = False
            asignacion.turno_rotativo = None
            asignacion.hora_entrada = datetime.strptime(hora_entrada, '%H:%M').time()
            asignacion.hora_salida = datetime.strptime(hora_salida, '%H:%M').time()
            mensaje = 'Horario personalizado asignado'
        
        else:
            return JsonResponse({'error': 'Tipo de asignación inválido o faltan datos'}, status=400)
        
        asignacion.save()
        
        return JsonResponse({
            'success': True,
            'mensaje': mensaje,
            'asignacion_id': asignacion.id,
            'created': created
        })
    
    except Empleado.DoesNotExist:
        return JsonResponse({'error': 'Empleado no encontrado'}, status=404)
    except TurnoRotativo.DoesNotExist:
        return JsonResponse({'error': 'Turno no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ========== ENVÍO MANUAL DE REPORTES ==========

@login_required
@require_http_methods(["POST"])
def enviar_reporte_view(request, tipo):
    """Dispara el envío manual de un reporte desde el Dashboard"""
    if tipo not in TipoReporte.values:
        raise Http404("Tipo de reporte no válido")

    if tipo == TipoReporte.DIARIO:
        resultado = generar_reporte_diario(origen=OrigenEnvio.MANUAL, enviado_por=request.user)
    elif tipo == TipoReporte.SEMANAL:
        resultado = generar_reporte_semanal(origen=OrigenEnvio.MANUAL, enviado_por=request.user)
    elif tipo == TipoReporte.QUINCENAL:
        resultado = generar_reporte_quincenal(dia_quincena_actual(), origen=OrigenEnvio.MANUAL, enviado_por=request.user)
    elif tipo == TipoReporte.MENSUAL:
        resultado = generar_reporte_mensual(origen=OrigenEnvio.MANUAL, enviado_por=request.user)
    else:
        resultado = generar_reporte_tiempo_extra_mensual(origen=OrigenEnvio.MANUAL, enviado_por=request.user)

    if resultado.exitoso:
        messages.success(request, f'Reporte {resultado.get_tipo_display()} enviado a: {resultado.destinatarios}')
    else:
        messages.error(request, f'No se pudo enviar el reporte {resultado.get_tipo_display()}: {resultado.error}')

    return redirect('dashboard')
