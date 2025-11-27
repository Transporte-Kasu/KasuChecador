from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Asistencia, TipoMovimiento, Empleado, ConfiguracionSistema, TiempoExtra, TipoHorario
import os
from django.conf import settings

def enviar_email_visitante(visitante):
    """Envía email con QR al visitante y notifica al departamento"""

    # Email al visitante
    subject_visitante = f'Confirmación de Visita - {visitante.fecha_visita}'

    html_message = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background-color: #3b82f6; padding: 20px; text-align: center;">
            <h1 style="color: white; margin: 0;">Visita Confirmada</h1>
        </div>
        <div style="padding: 20px; background-color: #f9fafb;">
            <p>Hola <strong>{visitante.nombre}</strong>,</p>
            <p>Tu visita ha sido confirmada con los siguientes detalles:</p>
            <div style="background-color: white; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <p><strong>Departamento:</strong> {visitante.departamento_visita.nombre}</p>
                <p><strong>Fecha:</strong> {visitante.fecha_visita.strftime('%d/%m/%Y')}</p>
                <p><strong>Hora:</strong> {visitante.hora_visita.strftime('%H:%M')}</p>
                <p><strong>Motivo:</strong> {visitante.motivo}</p>
            </div>
            <div style="text-align: center; margin: 30px 0;">
                <p><strong>Tu código QR de acceso:</strong></p>
                <img src="{visitante.qr_code.url}" alt="QR Code" style="max-width: 250px;">
                <p style="font-size: 12px; color: #6b7280;">Presenta este código al llegar a recepción</p>
            </div>
        </div>
    </body>
    </html>
    """

    # Usar EmailMultiAlternatives en lugar de EmailMessage
    email_visitante = EmailMultiAlternatives(
        subject_visitante,
        'Tu visita ha sido confirmada. Por favor revisa el contenido HTML del email.',
        settings.DEFAULT_FROM_EMAIL,
        [visitante.email]
    )
    email_visitante.attach_alternative(html_message, "text/html")

    # Adjuntar QR
    #if visitante.qr_code:
    #    with open(visitante.qr_code.path, 'rb') as f:
    #        email_visitante.attach('qr_code.png', f.read(), 'image/png')

    email_visitante.send(fail_silently=False)

    # Email al departamento
    subject_depto = f'Nueva Visita Programada - {visitante.nombre}'
    mensaje_depto = f"""
    <html>
    <body style="font-family: Arial, sans-serif;">
        <h2>Nueva Visita Programada</h2>
        <p>Se ha programado una visita para su departamento:</p>
        <ul>
            <li><strong>Visitante:</strong> {visitante.nombre}</li>
            <li><strong>Empresa:</strong> {visitante.empresa or 'N/A'}</li>
            <li><strong>Fecha:</strong> {visitante.fecha_visita.strftime('%d/%m/%Y')}</li>
            <li><strong>Hora:</strong> {visitante.hora_visita.strftime('%H:%M')}</li>
            <li><strong>Motivo:</strong> {visitante.motivo}</li>
        </ul>
    </body>
    </html>
    """

    email_depto = EmailMultiAlternatives(
        subject_depto,
        'Nueva visita programada. Por favor revisa el contenido HTML del email.',
        settings.DEFAULT_FROM_EMAIL,
        [visitante.departamento_visita.email]
    )
    email_depto.attach_alternative(mensaje_depto, "text/html")
    email_depto.send(fail_silently=False)


def generar_reporte_semanal():
    """Genera y envía el reporte semanal todos los jueves"""
    hoy = timezone.now().date()

    # Calcular el rango de la semana (lunes a jueves)
    # Si hoy es jueves (weekday = 3), la semana va desde el lunes anterior hasta hoy
    dias_desde_lunes = hoy.weekday()  # 0=lunes, 3=jueves
    fecha_inicio = hoy - timedelta(days=dias_desde_lunes)
    fecha_fin = hoy

    # Obtener configuración
    config = ConfiguracionSistema.objects.first()
    if not config:
        return

    # Obtener datos por empleado
    empleados = Empleado.objects.filter(activo=True)

    html_reporte = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 10px; text-align: center; }}
            th {{ background-color: #3b82f6; color: white; }}
            tr:nth-child(even) {{ background-color: #f2f2f2; }}
            .titulo {{ background-color: #1e40af; color: white; padding: 20px; text-align: center; }}
            .resumen {{ background-color: #eff6ff; padding: 20px; border-radius: 8px; margin: 20px 0; }}
            .alerta {{ background-color: #fef2f2; padding: 15px; border-left: 4px solid #ef4444; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="titulo">
            <h1>Reporte Semanal de Asistencias</h1>
            <p>{fecha_inicio.strftime('%d/%m/%Y')} - {fecha_fin.strftime('%d/%m/%Y')}</p>
        </div>

        <table>
            <tr>
                <th>Empleado</th>
                <th>Código</th>
                <th>Departamento</th>
                <th>Días Asistidos</th>
                <th>Retardos</th>
                <th>Total Min. Retardo</th>
                <th>Faltas</th>
            </tr>
    """

    # Recolectar empleados con retardos consecutivos
    empleados_retardos_consecutivos = []

    for empleado in empleados:
        asistencias = Asistencia.objects.filter(
            empleado=empleado,
            fecha__gte=fecha_inicio,
            fecha__lte=fecha_fin,
            tipo_movimiento=TipoMovimiento.ENTRADA
        )

        dias_asistidos = asistencias.values('fecha').distinct().count()
        retardos = asistencias.filter(retardo=True).count()
        total_min_retardo = sum(asistencias.filter(retardo=True).values_list('minutos_retardo', flat=True))

        # Calcular días/turnos laborales según tipo de horario
        tipo_horario = empleado.tipo_horario
        if tipo_horario and tipo_horario.es_turno_24h:
            # Para turnos de 24h: calcular turnos esperados en el período
            # Ciclo de 48 horas (24h trabajo + 24h descanso)
            dias_periodo = (fecha_fin - fecha_inicio).days + 1
            turnos_esperados = dias_periodo // 2  # Un turno cada 2 días
            faltas = max(0, turnos_esperados - dias_asistidos)
        else:
            # Para horarios regulares: lunes a viernes
            dias_laborales = 0
            fecha_actual = fecha_inicio
            while fecha_actual <= fecha_fin:
                if fecha_actual.weekday() < 5:  # Lunes a viernes
                    dias_laborales += 1
                fecha_actual += timedelta(days=1)
            faltas = dias_laborales - dias_asistidos

        html_reporte += f"""
            <tr>
                <td>{empleado.user.get_full_name()}</td>
                <td>{empleado.codigo_empleado}</td>
                <td>{empleado.departamento.nombre if empleado.departamento else 'N/A'}</td>
                <td>{dias_asistidos}</td>
                <td>{retardos}</td>
                <td>{total_min_retardo}</td>
                <td>{faltas}</td>
            </tr>
        """

        # Detectar empleados con retardos consecutivos (3 o más retardos en la semana)
        if retardos >= 3:
            empleados_retardos_consecutivos.append({
                'nombre': empleado.user.get_full_name(),
                'codigo': empleado.codigo_empleado,
                'retardos': retardos
            })

    html_reporte += "</table>"

    # Agregar alerta de retardos consecutivos si existen
    if empleados_retardos_consecutivos:
        html_reporte += """
        <div class="alerta">
            <h2>⚠️ Atención: Retardos Recurrentes</h2>
            <p>Los siguientes empleados tienen 3 o más retardos esta semana:</p>
            <table>
                <tr>
                    <th>Empleado</th>
                    <th>Código</th>
                    <th>Retardos (esta semana)</th>
                </tr>
        """

        for emp in empleados_retardos_consecutivos:
            html_reporte += f"""
                <tr>
                    <td>{emp['nombre']}</td>
                    <td>{emp['codigo']}</td>
                    <td>{emp['retardos']}</td>
                </tr>
            """

        html_reporte += "</table></div>"

    html_reporte += "</body></html>"

    # Enviar email
    email = EmailMultiAlternatives(
        f'Reporte Semanal de Asistencias - Semana del {fecha_inicio.strftime("%d/%m/%Y")}',
        'Reporte semanal de asistencias. Por favor revisa el contenido HTML.',
        settings.DEFAULT_FROM_EMAIL,
        [config.email_gerente]
    )
    email.attach_alternative(html_reporte, "text/html")
    email.send(fail_silently=False)


def generar_reporte_diario():
    """Genera y envía el reporte diario después de las 12:00 PM"""
    hoy = timezone.now().date()

    # Obtener configuración
    config = ConfiguracionSistema.objects.first()
    if not config:
        return

    # Asistencias del día
    asistencias_entrada = Asistencia.objects.filter(
        fecha=hoy,
        tipo_movimiento=TipoMovimiento.ENTRADA
    ).select_related('empleado', 'empleado__user')

    total_empleados = Empleado.objects.filter(activo=True).count()
    llegaron = asistencias_entrada.count()
    retardos = asistencias_entrada.filter(retardo=True)

    # Empleados con retardos consecutivos (últimos 5 días)
    fecha_inicio = hoy - timedelta(days=5)
    empleados_retardos_consecutivos = []

    for empleado in Empleado.objects.filter(activo=True):
        retardos_count = Asistencia.objects.filter(
            empleado=empleado,
            fecha__gte=fecha_inicio,
            fecha__lte=hoy,
            tipo_movimiento=TipoMovimiento.ENTRADA,
            retardo=True
        ).count()

        if retardos_count >= 3:
            empleados_retardos_consecutivos.append({
                'nombre': empleado.user.get_full_name(),
                'codigo': empleado.codigo_empleado,
                'retardos': retardos_count
            })

    # Generar HTML del reporte
    html_reporte = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
            th {{ background-color: #3b82f6; color: white; }}
            tr:nth-child(even) {{ background-color: #f2f2f2; }}
            .resumen {{ background-color: #eff6ff; padding: 20px; border-radius: 8px; margin: 20px 0; }}
            .alerta {{ background-color: #fef2f2; padding: 15px; border-left: 4px solid #ef4444; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <h1>Reporte Diario de Asistencia</h1>
        <p><strong>Fecha:</strong> {hoy.strftime('%d/%m/%Y')}</p>

        <div class="resumen">
            <h2>Resumen</h2>
            <p><strong>Total de Empleados:</strong> {total_empleados}</p>
            <p><strong>Asistieron:</strong> {llegaron} ({(llegaron/total_empleados*100):.1f}%)</p>
            <p><strong>Retardos del Día:</strong> {retardos.count()}</p>
        </div>

        <h2>Retardos del Día</h2>
        <table>
            <tr>
                <th>Empleado</th>
                <th>Código</th>
                <th>Tipo de Horario</th>
                <th>Hora de Entrada</th>
                <th>Minutos de Retardo</th>
            </tr>
    """

    for asistencia in retardos:
        tipo_horario_nombre = asistencia.empleado.tipo_horario.nombre if asistencia.empleado.tipo_horario else 'Estándar'
        html_reporte += f"""
            <tr>
                <td>{asistencia.empleado.user.get_full_name()}</td>
                <td>{asistencia.empleado.codigo_empleado}</td>
                <td>{tipo_horario_nombre}</td>
                <td>{asistencia.hora.strftime('%H:%M')}</td>
                <td>{asistencia.minutos_retardo}</td>
            </tr>
        """

    html_reporte += "</table>"

    if empleados_retardos_consecutivos:
        html_reporte += """
        <div class="alerta">
            <h2>⚠️ Atención: Retardos Consecutivos</h2>
            <p>Los siguientes empleados tienen 3 o más retardos en los últimos 5 días:</p>
            <table>
                <tr>
                    <th>Empleado</th>
                    <th>Código</th>
                    <th>Retardos (últimos 5 días)</th>
                </tr>
        """

        for emp in empleados_retardos_consecutivos:
            html_reporte += f"""
                <tr>
                    <td>{emp['nombre']}</td>
                    <td>{emp['codigo']}</td>
                    <td>{emp['retardos']}</td>
                </tr>
            """

        html_reporte += "</table></div>"

    html_reporte += "</body></html>"

    # Enviar email
    email = EmailMultiAlternatives(
        f'Reporte Diario de Asistencia - {hoy.strftime("%d/%m/%Y")}',
        'Reporte diario de asistencias. Por favor revisa el contenido HTML.',
        settings.DEFAULT_FROM_EMAIL,
        [config.email_gerente]
    )
    email.attach_alternative(html_reporte, "text/html")
    email.send(fail_silently=False)


def generar_reporte_quincenal(dia):
    """Genera el reporte quincenal (días 13 y 28)"""
    hoy = timezone.now().date()

    # Determinar el período
    if dia == 13:
        fecha_inicio = hoy.replace(day=1)
        fecha_fin = hoy.replace(day=13)
        periodo = "Primera Quincena"
    else:  # día 28
        fecha_inicio = hoy.replace(day=14)
        # Último día del mes
        if hoy.month == 12:
            fecha_fin = hoy.replace(day=31)
        else:
            fecha_fin = (hoy.replace(month=hoy.month + 1, day=1) - timedelta(days=1))
        periodo = "Segunda Quincena"

    config = ConfiguracionSistema.objects.first()
    if not config:
        return

    # Obtener datos por empleado
    empleados = Empleado.objects.filter(activo=True)

    html_reporte = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 10px; text-align: center; }}
            th {{ background-color: #3b82f6; color: white; }}
            tr:nth-child(even) {{ background-color: #f2f2f2; }}
            .titulo {{ background-color: #1e40af; color: white; padding: 20px; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="titulo">
            <h1>Reporte de Asistencias - {periodo}</h1>
            <p>{fecha_inicio.strftime('%d/%m/%Y')} - {fecha_fin.strftime('%d/%m/%Y')}</p>
        </div>

        <table>
            <tr>
                <th>Empleado</th>
                <th>Código</th>
                <th>Departamento</th>
                <th>Días Asistidos</th>
                <th>Retardos</th>
                <th>Total Min. Retardo</th>
                <th>Faltas</th>
            </tr>
    """

    for empleado in empleados:
        asistencias = Asistencia.objects.filter(
            empleado=empleado,
            fecha__gte=fecha_inicio,
            fecha__lte=fecha_fin,
            tipo_movimiento=TipoMovimiento.ENTRADA
        )

        dias_asistidos = asistencias.values('fecha').distinct().count()
        retardos = asistencias.filter(retardo=True).count()
        total_min_retardo = sum(asistencias.filter(retardo=True).values_list('minutos_retardo', flat=True))

        # Calcular días/turnos laborales según tipo de horario
        tipo_horario = empleado.tipo_horario
        if tipo_horario and tipo_horario.es_turno_24h:
            # Para turnos de 24h: calcular turnos esperados en el período
            dias_periodo = (fecha_fin - fecha_inicio).days + 1
            turnos_esperados = dias_periodo // 2
            faltas = max(0, turnos_esperados - dias_asistidos)
        else:
            # Para horarios regulares: todos los días del período
            dias_laborales = (fecha_fin - fecha_inicio).days + 1
            faltas = dias_laborales - dias_asistidos

        html_reporte += f"""
            <tr>
                <td>{empleado.user.get_full_name()}</td>
                <td>{empleado.codigo_empleado}</td>
                <td>{empleado.departamento.nombre if empleado.departamento else 'N/A'}</td>
                <td>{dias_asistidos}</td>
                <td>{retardos}</td>
                <td>{total_min_retardo}</td>
                <td>{faltas}</td>
            </tr>
        """

    html_reporte += "</table></body></html>"

    # Enviar email
    email = EmailMultiAlternatives(
        f'Reporte Quincenal - {periodo} - {hoy.strftime("%B %Y")}',
        'Reporte quincenal de asistencias. Por favor revisa el contenido HTML.',
        settings.DEFAULT_FROM_EMAIL,
        [config.email_gerente]
    )
    email.attach_alternative(html_reporte, "text/html")
    email.send(fail_silently=False)


def generar_reporte_tiempo_extra_mensual():
    """Genera el reporte mensual de tiempo extra y lo guarda en la red"""
    hoy = timezone.now()
    mes = hoy.month
    anio = hoy.year

    config = ConfiguracionSistema.objects.first()
    if not config or not config.ruta_red_reportes:
        return

    # Obtener tiempos extra del mes
    tiempos_extra = TiempoExtra.objects.filter(
        fecha__month=mes,
        fecha__year=anio,
        aprobado=True
    ).select_related('empleado', 'empleado__user')

    # Generar HTML
    html_reporte = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
            th {{ background-color: #10b981; color: white; }}
            tr:nth-child(even) {{ background-color: #f2f2f2; }}
            .total {{ background-color: #d1fae5; font-weight: bold; }}
        </style>
    </head>
    <body>
        <h1>Reporte de Tiempo Extra</h1>
        <p><strong>Período:</strong> {hoy.strftime('%B %Y')}</p>

        <table>
            <tr>
                <th>Empleado</th>
                <th>Código</th>
                <th>Fecha</th>
                <th>Horas Extra</th>
                <th>Descripción</th>
            </tr>
    """

    total_horas = 0
    empleados_resumen = {}

    for te in tiempos_extra:
        html_reporte += f"""
            <tr>
                <td>{te.empleado.user.get_full_name()}</td>
                <td>{te.empleado.codigo_empleado}</td>
                <td>{te.fecha.strftime('%d/%m/%Y')}</td>
                <td>{te.horas_extra}</td>
                <td>{te.descripcion}</td>
            </tr>
        """
        total_horas += float(te.horas_extra)

        emp_id = te.empleado.id
        if emp_id not in empleados_resumen:
            empleados_resumen[emp_id] = {
                'nombre': te.empleado.user.get_full_name(),
                'codigo': te.empleado.codigo_empleado,
                'horas': 0
            }
        empleados_resumen[emp_id]['horas'] += float(te.horas_extra)

    html_reporte += f"""
            <tr class="total">
                <td colspan="3">TOTAL</td>
                <td>{total_horas:.2f}</td>
                <td></td>
            </tr>
        </table>

        <h2>Resumen por Empleado</h2>
        <table>
            <tr>
                <th>Empleado</th>
                <th>Código</th>
                <th>Total Horas Extra</th>
            </tr>
    """

    for emp in empleados_resumen.values():
        html_reporte += f"""
            <tr>
                <td>{emp['nombre']}</td>
                <td>{emp['codigo']}</td>
                <td>{emp['horas']:.2f}</td>
            </tr>
        """

    html_reporte += "</table></body></html>"

    # Guardar en ruta de red
    nombre_archivo = f"reporte_tiempo_extra_{anio}_{mes:02d}.html"
    ruta_completa = os.path.join(config.ruta_red_reportes, nombre_archivo)

    try:
        with open(ruta_completa, 'w', encoding='utf-8') as f:
            f.write(html_reporte)
        print(f"Reporte guardado en: {ruta_completa}")
    except Exception as e:
        print(f"Error al guardar reporte: {e}")