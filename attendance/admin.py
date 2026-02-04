from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django import forms
from .models import (
    Departamento, Empleado, Asistencia, TiempoExtra,
    Visitante, RegistroVisita, ConfiguracionSistema, TipoHorario,
    HorarioDiaSemana, TurnoRotativo, AsignacionTurnoRotativo,
    TipoPermiso, SolicitudPermiso, PeriodoVacacional, SaldoVacaciones,
    SolicitudVacaciones, TipoJustificante, Justificante, AsignacionTurnoDiaria
)

@admin.register(Departamento)
class DepartamentoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'email']
    search_fields = ['nombre']

# ========== INLINES PARA HORARIOS ==========

class HorarioDiaSemanaInline(admin.TabularInline):
    model = HorarioDiaSemana
    extra = 0
    fields = ['dia_semana', 'es_dia_laboral', 'hora_entrada', 'hora_salida', 'es_medio_dia', 'hora_inicio_comida', 'hora_fin_comida']

class TurnoRotativoInline(admin.TabularInline):
    model = TurnoRotativo
    extra = 0
    fields = ['nombre', 'hora_entrada', 'hora_salida', 'orden_en_ciclo', 'dias_consecutivos']

@admin.register(TipoHorario)
class TipoHorarioAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'tipo_sistema', 'hora_entrada', 'hora_salida', 'horas_jornada_completa', 'activo']
    list_filter = ['tipo_sistema', 'es_turno_24h', 'tiene_horario_comida', 'activo']
    search_fields = ['nombre', 'descripcion']
    inlines = [HorarioDiaSemanaInline, TurnoRotativoInline]
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'descripcion', 'tipo_sistema', 'activo')
        }),
        ('Configuración de Horario', {
            'fields': ('hora_entrada', 'hora_salida', 'horas_jornada_completa', 'minutos_tolerancia', 'es_turno_24h', 'requiere_horario_por_dia')
        }),
        ('Horario de Comida', {
            'fields': ('tiene_horario_comida', 'hora_inicio_comida', 'hora_fin_comida')
        }),
    )

# Formulario para la acción de asignar horario
class AsignarHorarioForm(forms.Form):
    _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
    tipo_horario = forms.ModelChoiceField(
        queryset=TipoHorario.objects.filter(activo=True),
        required=True,
        label="Tipo de Horario",
        help_text="Selecciona el tipo de horario a asignar"
    )

@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ['codigo_empleado', 'get_nombre', 'departamento', 'tipo_horario', 'tiempo_extra_habilitado', 'activo', 'ver_qr']
    list_filter = ['activo', 'tiempo_extra_habilitado', 'departamento', 'tipo_horario']
    search_fields = ['codigo_empleado', 'user__first_name', 'user__last_name', 'user__username']
    readonly_fields = ['qr_uuid', 'mostrar_qr']
    actions = ['asignar_tipo_horario']

    def get_nombre(self, obj):
        return obj.user.get_full_name()
    get_nombre.short_description = 'Nombre'

    def ver_qr(self, obj):
        if obj.qr_code:
            return format_html('<a href="{}" target="_blank">Ver QR</a>', obj.qr_code.url)
        return '-'
    ver_qr.short_description = 'Código QR'

    def mostrar_qr(self, obj):
        if obj.qr_code:
            return format_html('<img src="{}" style="max-width: 300px;"/>', obj.qr_code.url)
        return '-'
    mostrar_qr.short_description = 'Código QR'

    def asignar_tipo_horario(self, request, queryset):
        """Acción para asignar tipo de horario a múltiples empleados"""
        from django.shortcuts import render, redirect
        from django.contrib import messages

        # Si es POST, procesar el formulario
        if 'apply' in request.POST:
            form = AsignarHorarioForm(request.POST)

            if form.is_valid():
                tipo_horario = form.cleaned_data['tipo_horario']

                # Obtener los IDs de los empleados seleccionados del formulario
                selected_ids = request.POST.getlist('_selected_action')

                # Si no hay IDs en el POST, usar el queryset original
                if not selected_ids:
                    self.message_user(
                        request,
                        'Error: No se pudieron identificar los empleados seleccionados.',
                        messages.ERROR
                    )
                    return redirect(request.get_full_path())

                # Filtrar empleados por los IDs
                empleados_a_actualizar = queryset.model.objects.filter(pk__in=selected_ids)
                count = empleados_a_actualizar.update(tipo_horario=tipo_horario)

                self.message_user(
                    request,
                    f'Se asignó el tipo de horario "{tipo_horario.nombre}" a {count} empleado(s) exitosamente.',
                    messages.SUCCESS
                )
                return redirect(request.get_full_path())

        # Si es GET, mostrar el formulario
        form = AsignarHorarioForm(initial={
            '_selected_action': queryset.values_list('pk', flat=True)
        })

        context = {
            'title': 'Asignar Tipo de Horario',
            'queryset': queryset,
            'form': form,
            'action_name': 'asignar_tipo_horario',
            'opts': self.model._meta,
        }

        return render(request, 'admin/asignar_horario.html', context)

    asignar_tipo_horario.short_description = 'Asignar tipo de horario a empleados seleccionados'

    fieldsets = (
        ('Información Básica', {
            'fields': ('user', 'codigo_empleado', 'departamento', 'tipo_horario', 'activo')
        }),
        ('Código QR', {
            'fields': ('qr_uuid', 'mostrar_qr')
        }),
        ('Configuración', {
            'fields': ('tiempo_extra_habilitado',)
        }),
    )

@admin.register(Asistencia)
class AsistenciaAdmin(admin.ModelAdmin):
    list_display = ['empleado', 'fecha', 'hora', 'tipo_movimiento', 'retardo', 'minutos_retardo']
    list_filter = ['fecha', 'tipo_movimiento', 'retardo', 'empleado__departamento']
    search_fields = ['empleado__user__first_name', 'empleado__user__last_name', 'empleado__codigo_empleado']
    date_hierarchy = 'fecha'
    readonly_fields = ['timestamp']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('empleado', 'empleado__user')

@admin.register(TiempoExtra)
class TiempoExtraAdmin(admin.ModelAdmin):
    list_display = ['empleado', 'fecha', 'horas_extra', 'aprobado', 'descripcion_corta']
    list_filter = ['aprobado', 'fecha', 'empleado__departamento']
    search_fields = ['empleado__user__first_name', 'empleado__user__last_name', 'descripcion']
    date_hierarchy = 'fecha'
    readonly_fields = ['timestamp']
    actions = ['aprobar_tiempo_extra']

    def descripcion_corta(self, obj):
        return obj.descripcion[:50] + '...' if len(obj.descripcion) > 50 else obj.descripcion
    descripcion_corta.short_description = 'Descripción'

    def aprobar_tiempo_extra(self, request, queryset):
        queryset.update(aprobado=True)
        self.message_user(request, f'{queryset.count()} registros aprobados')
    aprobar_tiempo_extra.short_description = 'Aprobar tiempo extra seleccionado'

@admin.register(Visitante)
class VisitanteAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'empresa', 'departamento_visita', 'fecha_visita', 'hora_visita', 'qr_activo', 'confirmado', 'ver_qr']
    list_filter = ['fecha_visita', 'departamento_visita', 'qr_activo', 'confirmado']
    search_fields = ['nombre', 'email', 'empresa']
    date_hierarchy = 'fecha_visita'
    readonly_fields = ['qr_uuid', 'timestamp', 'mostrar_qr']
    actions = ['reactivar_qr']

    def ver_qr(self, obj):
        if obj.qr_code:
            return format_html('<a href="{}" target="_blank">Ver QR</a>', obj.qr_code.url)
        return '-'
    ver_qr.short_description = 'Código QR'

    def mostrar_qr(self, obj):
        if obj.qr_code:
            return format_html('<img src="{}" style="max-width: 300px;"/>', obj.qr_code.url)
        return '-'
    mostrar_qr.short_description = 'Código QR'

    def reactivar_qr(self, request, queryset):
        """Acción para reactivar QR de visitantes"""
        count = queryset.update(qr_activo=True)
        self.message_user(request, f'{count} código(s) QR reactivado(s)')
    reactivar_qr.short_description = 'Reactivar códigos QR seleccionados'

    fieldsets = (
        ('Información del Visitante', {
            'fields': ('nombre', 'email', 'empresa', 'telefono')
        }),
        ('Detalles de la Visita', {
            'fields': ('departamento_visita', 'motivo', 'fecha_visita', 'hora_visita')
        }),
        ('Código QR', {
            'fields': ('qr_uuid', 'qr_activo', 'mostrar_qr')
        }),
        ('Estado', {
            'fields': ('confirmado', 'timestamp')
        }),
    )

@admin.register(RegistroVisita)
class RegistroVisitaAdmin(admin.ModelAdmin):
    list_display = ['visitante', 'hora_entrada', 'hora_salida', 'duracion', 'get_departamento']
    list_filter = ['hora_entrada', 'visitante__departamento_visita']
    search_fields = ['visitante__nombre', 'visitante__empresa']
    date_hierarchy = 'hora_entrada'
    readonly_fields = ['hora_entrada']

    def get_departamento(self, obj):
        return obj.visitante.departamento_visita.nombre
    get_departamento.short_description = 'Departamento'

    def duracion(self, obj):
        if obj.hora_salida:
            delta = obj.hora_salida - obj.hora_entrada
            horas = delta.total_seconds() / 3600
            return f"{horas:.2f} hrs"
        return "En sitio"
    duracion.short_description = 'Duración'

@admin.register(ConfiguracionSistema)
class ConfiguracionSistemaAdmin(admin.ModelAdmin):
    list_display = ['hora_entrada', 'minutos_tolerancia', 'email_gerente']

    def has_add_permission(self, request):
        # Solo permite una configuración
        return not ConfiguracionSistema.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # No permite eliminar la configuración
        return False

# ========== ADMIN PARA TURNOS ROTATIVOS ==========

@admin.register(AsignacionTurnoRotativo)
class AsignacionTurnoRotativoAdmin(admin.ModelAdmin):
    list_display = ['empleado', 'turno_rotativo', 'fecha_inicio', 'fecha_fin', 'activo']
    list_filter = ['activo', 'turno_rotativo__tipo_horario', 'fecha_inicio']
    search_fields = ['empleado__user__first_name', 'empleado__user__last_name', 'empleado__codigo_empleado']
    date_hierarchy = 'fecha_inicio'
    autocomplete_fields = ['empleado']
    list_select_related = ['empleado', 'turno_rotativo', 'empleado__user']

# ========== ADMIN PARA ASIGNACIÓN DIARIA DE TURNOS ==========

@admin.register(AsignacionTurnoDiaria)
class AsignacionTurnoDiariaAdmin(admin.ModelAdmin):
    list_display = ['empleado', 'fecha', 'turno_info', 'es_descanso', 'cruza_medianoche']
    list_filter = ['es_descanso', 'cruza_medianoche', 'fecha', 'turno_rotativo']
    search_fields = ['empleado__user__first_name', 'empleado__user__last_name', 'empleado__codigo_empleado']
    date_hierarchy = 'fecha'
    autocomplete_fields = ['empleado']
    list_select_related = ['empleado', 'turno_rotativo', 'empleado__user']
    readonly_fields = ['creado_en', 'actualizado_en']
    actions = ['marcar_descanso', 'copiar_mes']
    
    def turno_info(self, obj):
        if obj.es_descanso:
            return format_html('<span style="color: gray; font-weight: bold;">DESCANSO</span>')
        elif obj.turno_rotativo:
            horario = f"{obj.hora_entrada.strftime('%H:%M')} - {obj.hora_salida.strftime('%H:%M')}"
            return format_html('<strong>{}</strong><br><small>{}</small>', obj.turno_rotativo.nombre, horario)
        elif obj.hora_entrada and obj.hora_salida:
            horario = f"{obj.hora_entrada.strftime('%H:%M')} - {obj.hora_salida.strftime('%H:%M')}"
            return format_html('<span style="color: green;">{}</span>', horario)
        return '-'
    turno_info.short_description = 'Turno/Horario'
    
    def marcar_descanso(self, request, queryset):
        """Marcar días seleccionados como descanso"""
        count = queryset.update(es_descanso=True, turno_rotativo=None, hora_entrada=None, hora_salida=None)
        self.message_user(request, f'{count} día(s) marcado(s) como descanso')
    marcar_descanso.short_description = 'Marcar como día de descanso'
    
    def copiar_mes(self, request, queryset):
        """Acción para copiar asignaciones a otro mes"""
        # Esta acción se puede expandir con un formulario intermedio
        self.message_user(request, 'Funcionalidad de copia en desarrollo. Use la vista web para asignaciones masivas.')
    copiar_mes.short_description = 'Copiar asignaciones a otro mes'
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('empleado', 'fecha')
        }),
        ('Turno', {
            'fields': ('turno_rotativo', 'es_descanso')
        }),
        ('Horario Personalizado', {
            'fields': ('hora_entrada', 'hora_salida', 'cruza_medianoche'),
            'description': 'Complete estos campos solo si NO seleccionó un turno predefinido'
        }),
        ('Notas y Metadatos', {
            'fields': ('notas', 'creado_en', 'actualizado_en')
        }),
    )

# ========== ADMIN PARA PERMISOS ==========

@admin.register(TipoPermiso)
class TipoPermisoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'requiere_aprobacion_gerencia', 'dias_anticipacion_minimos', 'activo']
    list_filter = ['requiere_aprobacion_gerencia', 'activo']
    search_fields = ['nombre']

@admin.register(SolicitudPermiso)
class SolicitudPermisoAdmin(admin.ModelAdmin):
    list_display = ['empleado', 'tipo_permiso', 'fecha_inicio', 'tipo_ausencia', 'total_dias', 'total_horas', 'con_goce_sueldo', 'estado', 'fecha_solicitud']
    list_filter = ['estado', 'tipo_ausencia', 'con_goce_sueldo', 'fecha_solicitud', 'tipo_permiso']
    search_fields = ['empleado__user__first_name', 'empleado__user__last_name', 'empleado__codigo_empleado', 'motivo']
    date_hierarchy = 'fecha_solicitud'
    readonly_fields = ['fecha_solicitud', 'total_dias', 'total_horas']
    autocomplete_fields = ['empleado']
    list_select_related = ['empleado', 'tipo_permiso', 'empleado__user', 'aprobado_por']
    actions = ['aprobar_solicitudes', 'rechazar_solicitudes']

    fieldsets = (
        ('Información del Empleado', {
            'fields': ('empleado', 'tipo_permiso')
        }),
        ('Detalles del Permiso', {
            'fields': ('tipo_ausencia', 'fecha_inicio', 'fecha_fin', 'hora_inicio', 'hora_fin', 'total_dias', 'total_horas', 'con_goce_sueldo')
        }),
        ('Motivo y Documentación', {
            'fields': ('motivo', 'archivo_adjunto')
        }),
        ('Estado y Aprobación', {
            'fields': ('estado', 'aprobado_por', 'fecha_aprobacion', 'comentarios_aprobacion', 'fecha_solicitud')
        }),
    )

    def aprobar_solicitudes(self, request, queryset):
        count = queryset.filter(estado='PENDIENTE').update(
            estado='APROBADO_JEFE',
            aprobado_por=request.user,
            fecha_aprobacion=timezone.now()
        )
        self.message_user(request, f'{count} solicitud(es) aprobada(s)')
    aprobar_solicitudes.short_description = 'Aprobar solicitudes seleccionadas'

    def rechazar_solicitudes(self, request, queryset):
        count = queryset.filter(estado='PENDIENTE').update(
            estado='RECHAZADO',
            aprobado_por=request.user,
            fecha_aprobacion=timezone.now()
        )
        self.message_user(request, f'{count} solicitud(es) rechazada(s)')
    rechazar_solicitudes.short_description = 'Rechazar solicitudes seleccionadas'

# ========== ADMIN PARA VACACIONES ==========

@admin.register(PeriodoVacacional)
class PeriodoVacacionalAdmin(admin.ModelAdmin):
    list_display = ['anio', 'fecha_inicio_periodo', 'fecha_fin_periodo', 'activo']
    list_filter = ['activo', 'anio']
    search_fields = ['anio']

@admin.register(SaldoVacaciones)
class SaldoVacacionesAdmin(admin.ModelAdmin):
    list_display = ['empleado', 'periodo_vacacional', 'dias_totales', 'dias_tomados', 'get_dias_pendientes']
    list_filter = ['periodo_vacacional']
    search_fields = ['empleado__user__first_name', 'empleado__user__last_name', 'empleado__codigo_empleado']
    autocomplete_fields = ['empleado']
    list_select_related = ['empleado', 'periodo_vacacional', 'empleado__user']

    def get_dias_pendientes(self, obj):
        return obj.dias_pendientes
    get_dias_pendientes.short_description = 'Días Pendientes'

@admin.register(SolicitudVacaciones)
class SolicitudVacacionesAdmin(admin.ModelAdmin):
    list_display = ['empleado', 'fecha_inicio', 'fecha_fin', 'dias_solicitados', 'estado', 'fecha_solicitud']
    list_filter = ['estado', 'fecha_solicitud', 'saldo_vacaciones__periodo_vacacional']
    search_fields = ['empleado__user__first_name', 'empleado__user__last_name', 'empleado__codigo_empleado', 'motivo']
    date_hierarchy = 'fecha_solicitud'
    readonly_fields = ['fecha_solicitud', 'dias_solicitados']
    autocomplete_fields = ['empleado']
    list_select_related = ['empleado', 'saldo_vacaciones', 'empleado__user', 'aprobado_por']
    actions = ['aprobar_vacaciones', 'rechazar_vacaciones']

    fieldsets = (
        ('Información del Empleado', {
            'fields': ('empleado', 'saldo_vacaciones')
        }),
        ('Detalles de las Vacaciones', {
            'fields': ('fecha_inicio', 'fecha_fin', 'dias_solicitados', 'motivo')
        }),
        ('Estado y Aprobación', {
            'fields': ('estado', 'aprobado_por', 'fecha_aprobacion', 'comentarios_aprobacion', 'fecha_solicitud')
        }),
    )

    def aprobar_vacaciones(self, request, queryset):
        count = 0
        for solicitud in queryset.filter(estado='PENDIENTE'):
            # Verificar saldo disponible
            if solicitud.saldo_vacaciones.dias_pendientes >= solicitud.dias_solicitados:
                solicitud.estado = 'APROBADO_GERENCIA'
                solicitud.aprobado_por = request.user
                solicitud.fecha_aprobacion = timezone.now()
                solicitud.save()
                # Actualizar saldo
                solicitud.saldo_vacaciones.dias_tomados += solicitud.dias_solicitados
                solicitud.saldo_vacaciones.save()
                count += 1
            else:
                self.message_user(request, f'Error: {solicitud.empleado} no tiene saldo suficiente', level='error')
        self.message_user(request, f'{count} solicitud(es) aprobada(s)')
    aprobar_vacaciones.short_description = 'Aprobar vacaciones seleccionadas'

    def rechazar_vacaciones(self, request, queryset):
        count = queryset.filter(estado='PENDIENTE').update(
            estado='RECHAZADO',
            aprobado_por=request.user,
            fecha_aprobacion=timezone.now()
        )
        self.message_user(request, f'{count} solicitud(es) rechazada(s)')
    rechazar_vacaciones.short_description = 'Rechazar vacaciones seleccionadas'

# ========== ADMIN PARA JUSTIFICANTES ==========

@admin.register(TipoJustificante)
class TipoJustificanteAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'aplica_para', 'requiere_documento', 'cancela_penalizacion', 'activo']
    list_filter = ['aplica_para', 'requiere_documento', 'cancela_penalizacion', 'activo']
    search_fields = ['nombre']

@admin.register(Justificante)
class JustificanteAdmin(admin.ModelAdmin):
    list_display = ['empleado', 'tipo_justificante', 'fecha_incidente', 'estado', 'fecha_presentacion']
    list_filter = ['estado', 'tipo_justificante', 'fecha_incidente']
    search_fields = ['empleado__user__first_name', 'empleado__user__last_name', 'empleado__codigo_empleado', 'motivo']
    date_hierarchy = 'fecha_incidente'
    readonly_fields = ['fecha_presentacion']
    autocomplete_fields = ['empleado']
    list_select_related = ['empleado', 'tipo_justificante', 'empleado__user', 'revisado_por', 'asistencia']
    actions = ['aprobar_justificantes', 'rechazar_justificantes']

    fieldsets = (
        ('Información del Empleado', {
            'fields': ('empleado', 'tipo_justificante', 'asistencia')
        }),
        ('Detalles del Justificante', {
            'fields': ('fecha_incidente', 'motivo', 'documento_respaldo', 'fecha_presentacion')
        }),
        ('Revisión', {
            'fields': ('estado', 'revisado_por', 'fecha_revision', 'comentarios_revision')
        }),
    )

    def aprobar_justificantes(self, request, queryset):
        count = queryset.filter(estado='PENDIENTE').update(
            estado='APROBADO',
            revisado_por=request.user,
            fecha_revision=timezone.now()
        )
        self.message_user(request, f'{count} justificante(s) aprobado(s)')
    aprobar_justificantes.short_description = 'Aprobar justificantes seleccionados'

    def rechazar_justificantes(self, request, queryset):
        count = queryset.filter(estado='PENDIENTE').update(
            estado='RECHAZADO',
            revisado_por=request.user,
            fecha_revision=timezone.now()
        )
        self.message_user(request, f'{count} justificante(s) rechazado(s)')
    rechazar_justificantes.short_description = 'Rechazar justificantes seleccionados'
