# attendance/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Departamento, Empleado, Asistencia, TiempoExtra,
    Visitante, RegistroVisita, ConfiguracionSistema, TipoHorario
)

@admin.register(Departamento)
class DepartamentoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'email']
    search_fields = ['nombre']

@admin.register(TipoHorario)
class TipoHorarioAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'es_turno_24h', 'hora_entrada', 'hora_salida', 'tiene_horario_comida', 'activo']
    list_filter = ['es_turno_24h', 'tiene_horario_comida', 'activo']
    search_fields = ['nombre', 'descripcion']
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'descripcion', 'activo')
        }),
        ('Configuración de Horario', {
            'fields': ('es_turno_24h', 'hora_entrada', 'hora_salida', 'minutos_tolerancia')
        }),
        ('Horario de Comida', {
            'fields': ('tiene_horario_comida', 'hora_inicio_comida', 'hora_fin_comida')
        }),
    )

@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ['codigo_empleado', 'get_nombre', 'departamento', 'tipo_horario', 'tiempo_extra_habilitado', 'activo', 'ver_qr']
    list_filter = ['activo', 'tiempo_extra_habilitado', 'departamento', 'tipo_horario']
    search_fields = ['codigo_empleado', 'user__first_name', 'user__last_name']
    readonly_fields = ['qr_uuid', 'mostrar_qr']

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
    list_display = ['nombre', 'empresa', 'departamento_visita', 'fecha_visita', 'hora_visita', 'confirmado', 'ver_qr']
    list_filter = ['fecha_visita', 'departamento_visita', 'confirmado']
    search_fields = ['nombre', 'email', 'empresa']
    date_hierarchy = 'fecha_visita'
    readonly_fields = ['qr_uuid', 'timestamp', 'mostrar_qr']

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

    fieldsets = (
        ('Información del Visitante', {
            'fields': ('nombre', 'email', 'empresa', 'telefono')
        }),
        ('Detalles de la Visita', {
            'fields': ('departamento_visita', 'motivo', 'fecha_visita', 'hora_visita')
        }),
        ('Código QR', {
            'fields': ('qr_uuid', 'mostrar_qr')
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