from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, timedelta
import qrcode
from io import BytesIO
from django.core.files import File
import uuid

from checador.storage_backends import MediaStorage

class Departamento(models.Model):
    nombre = models.CharField(max_length=100)
    email = models.EmailField()

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name_plural = "Departamentos"

class TipoSistemaHorario(models.TextChoices):
    FIJO = 'FIJO', 'Horario Fijo'
    TURNO_24H = 'TURNO_24H', 'Turno 24x24 horas'
    ROTATIVO = 'ROTATIVO', 'Turno Rotativo'
    PERSONALIZADO = 'PERSONALIZADO', 'Horario Personalizado por Día'

class TipoHorario(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    tipo_sistema = models.CharField(
        max_length=20,
        choices=TipoSistemaHorario.choices,
        default=TipoSistemaHorario.FIJO,
        verbose_name="Tipo de Sistema"
    )
    es_turno_24h = models.BooleanField(default=False, verbose_name="Es turno de 24 horas")
    hora_entrada = models.TimeField(null=True, blank=True)
    hora_salida = models.TimeField(null=True, blank=True)
    horas_jornada_completa = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=8.0,
        verbose_name="Horas de jornada completa"
    )
    minutos_tolerancia = models.IntegerField(default=15)
    tiene_horario_comida = models.BooleanField(default=False)
    hora_inicio_comida = models.TimeField(null=True, blank=True)
    hora_fin_comida = models.TimeField(null=True, blank=True)
    requiere_horario_por_dia = models.BooleanField(
        default=False,
        verbose_name="Requiere configuración por día",
        help_text="Activa esto para horarios personalizados por día de la semana"
    )
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name_plural = "Tipos de Horario"

class DiaSemana(models.IntegerChoices):
    LUNES = 0, 'Lunes'
    MARTES = 1, 'Martes'
    MIERCOLES = 2, 'Miércoles'
    JUEVES = 3, 'Jueves'
    VIERNES = 4, 'Viernes'
    SABADO = 5, 'Sábado'
    DOMINGO = 6, 'Domingo'

class HorarioDiaSemana(models.Model):
    """Configuración de horario específico por día de la semana"""
    tipo_horario = models.ForeignKey(TipoHorario, on_delete=models.CASCADE, related_name='horarios_dia')
    dia_semana = models.IntegerField(choices=DiaSemana.choices, verbose_name="Día de la semana")
    es_dia_laboral = models.BooleanField(default=True, verbose_name="Es día laboral")
    hora_entrada = models.TimeField(null=True, blank=True)
    hora_salida = models.TimeField(null=True, blank=True)
    es_medio_dia = models.BooleanField(default=False, verbose_name="Es medio día")
    hora_inicio_comida = models.TimeField(null=True, blank=True, verbose_name="Inicio de comida")
    hora_fin_comida = models.TimeField(null=True, blank=True, verbose_name="Fin de comida")

    def __str__(self):
        return f"{self.tipo_horario.nombre} - {self.get_dia_semana_display()}"

    class Meta:
        verbose_name = "Horario por Día"
        verbose_name_plural = "Horarios por Día"
        unique_together = ['tipo_horario', 'dia_semana']
        ordering = ['tipo_horario', 'dia_semana']

class TurnoRotativo(models.Model):
    """Define un turno dentro de un ciclo rotativo"""
    tipo_horario = models.ForeignKey(TipoHorario, on_delete=models.CASCADE, related_name='turnos_rotativos')
    nombre = models.CharField(max_length=100, verbose_name="Nombre del turno")
    hora_entrada = models.TimeField()
    hora_salida = models.TimeField()
    orden_en_ciclo = models.IntegerField(verbose_name="Orden en el ciclo", help_text="1, 2, 3...")
    dias_consecutivos = models.IntegerField(
        default=1,
        verbose_name="Días consecutivos",
        help_text="Cuántos días seguidos se trabaja este turno"
    )

    def __str__(self):
        return f"{self.tipo_horario.nombre} - {self.nombre}"

    class Meta:
        verbose_name = "Turno Rotativo"
        verbose_name_plural = "Turnos Rotativos"
        ordering = ['tipo_horario', 'orden_en_ciclo']
        unique_together = ['tipo_horario', 'orden_en_ciclo']

class AsignacionTurnoRotativo(models.Model):
    """Asigna un turno rotativo específico a un empleado en un periodo"""
    empleado = models.ForeignKey('Empleado', on_delete=models.CASCADE, related_name='asignaciones_turno')
    turno_rotativo = models.ForeignKey(TurnoRotativo, on_delete=models.CASCADE)
    fecha_inicio = models.DateField(verbose_name="Fecha de inicio")
    fecha_fin = models.DateField(verbose_name="Fecha de fin")
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.empleado} - {self.turno_rotativo.nombre} ({self.fecha_inicio} - {self.fecha_fin})"

    class Meta:
        verbose_name = "Asignación de Turno Rotativo"
        verbose_name_plural = "Asignaciones de Turnos Rotativos"
        ordering = ['-fecha_inicio']

class Empleado(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    codigo_empleado = models.CharField(max_length=20, unique=True)
    departamento = models.ForeignKey(Departamento, on_delete=models.SET_NULL, null=True)
    tipo_horario = models.ForeignKey(TipoHorario, on_delete=models.SET_NULL, null=True, blank=True)
    qr_code = models.ImageField(storage=MediaStorage(), upload_to='qr_codes/', blank=True)
    qr_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    tiempo_extra_habilitado = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.codigo_empleado}"

    def generar_qr(self):
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(str(self.qr_uuid))
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buffer = BytesIO()
        img.save(buffer, format='PNG')
        filename = f'qr_{self.codigo_empleado}.png'
        self.qr_code.save(filename, File(buffer), save=False)
        buffer.close()

    def save(self, *args, **kwargs):
        if not self.qr_code:
            self.generar_qr()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name_plural = "Empleados"

class TipoMovimiento(models.TextChoices):
    ENTRADA = 'ENTRADA', 'Entrada'
    SALIDA_COMIDA = 'SALIDA_COMIDA', 'Salida a Comida'
    ENTRADA_COMIDA = 'ENTRADA_COMIDA', 'Entrada de Comida'
    SALIDA = 'SALIDA', 'Salida'

class Asistencia(models.Model):
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE)
    fecha = models.DateField(default=timezone.now)
    hora = models.TimeField(auto_now_add=True)
    tipo_movimiento = models.CharField(max_length=20, choices=TipoMovimiento.choices)
    retardo = models.BooleanField(default=False)
    minutos_retardo = models.IntegerField(default=0)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.empleado.user.get_full_name()} - {self.tipo_movimiento} - {self.fecha}"

    def calcular_retardo(self, hora_entrada_esperada="09:00:00", minutos_tolerancia=15):
        """Calcula si hay retardo considerando minutos de tolerancia y tipo de horario"""
        if self.tipo_movimiento != TipoMovimiento.ENTRADA:
            return
        
        # Importar aquí para evitar import circular
        from .utils import obtener_horario_esperado
        
        # Obtener horario esperado usando la nueva función
        horario = obtener_horario_esperado(self.empleado, self.fecha)
        
        # Si no es día laboral, no hay retardo
        if not horario['es_dia_laboral']:
            self.retardo = False
            self.minutos_retardo = 0
            return
        
        # CASO ESPECIAL: Turnos de 24 horas
        if horario['tipo_sistema'] == 'TURNO_24H':
            # Buscar última entrada del empleado para calcular el ciclo esperado
            ultima_entrada = Asistencia.objects.filter(
                empleado=self.empleado,
                tipo_movimiento=TipoMovimiento.ENTRADA,
                fecha__lt=self.fecha
            ).order_by('-fecha', '-hora').first()

            if ultima_entrada:
                # Ciclo: 24h trabajo + 24h descanso = 48h total
                ultima_entrada_dt = datetime.combine(ultima_entrada.fecha, ultima_entrada.hora)
                entrada_actual_dt = datetime.combine(self.fecha, self.hora)
                diferencia_horas = (entrada_actual_dt - ultima_entrada_dt).total_seconds() / 3600

                # El empleado debería entrar ~48 horas después (permitir tolerancia de 2 horas)
                if diferencia_horas < 46:  # Menos de 46 horas = entrada anticipada
                    self.retardo = False
                    self.minutos_retardo = 0
                elif diferencia_horas > 50:  # Más de 50 horas = retardo
                    self.retardo = True
                    self.minutos_retardo = int((diferencia_horas - 48) * 60)
                else:
                    self.retardo = False
                    self.minutos_retardo = 0
            else:
                # Primera entrada, no hay retardo
                self.retardo = False
                self.minutos_retardo = 0
            return
        
        # HORARIOS NORMALES, ROTATIVOS Y PERSONALIZADOS
        hora_esperada = horario['hora_entrada']
        if not hora_esperada:
            # Si no hay hora de entrada definida, usar parámetros por defecto
            hora_esperada = datetime.strptime(hora_entrada_esperada, "%H:%M:%S").time()
            tolerancia_min = minutos_tolerancia
        else:
            tolerancia_min = horario['tolerancia_minutos']
        
        # Calcular hora límite con tolerancia
        tolerancia = timedelta(minutes=tolerancia_min)
        hora_limite = (datetime.combine(datetime.today(), hora_esperada) + tolerancia).time()

        if self.hora > hora_limite:
            self.retardo = True
            hora_esperada_dt = datetime.combine(datetime.today(), hora_esperada)
            hora_real_dt = datetime.combine(datetime.today(), self.hora)
            diferencia = hora_real_dt - hora_esperada_dt
            self.minutos_retardo = int(diferencia.total_seconds() / 60)
        else:
            self.retardo = False
            self.minutos_retardo = 0

    class Meta:
        verbose_name_plural = "Asistencias"
        ordering = ['-fecha', '-hora']

class TiempoExtra(models.Model):
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE)
    fecha = models.DateField()
    horas_extra = models.DecimalField(max_digits=5, decimal_places=2)
    descripcion = models.TextField(blank=True)
    aprobado = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.empleado.user.get_full_name()} - {self.fecha} - {self.horas_extra}hrs"

    class Meta:
        verbose_name_plural = "Tiempos Extra"
        ordering = ['-fecha']

class Visitante(models.Model):
    nombre = models.CharField(max_length=200)
    email = models.EmailField()
    empresa = models.CharField(max_length=200, blank=True)
    telefono = models.CharField(max_length=20)
    departamento_visita = models.ForeignKey(Departamento, on_delete=models.CASCADE)
    motivo = models.TextField()
    fecha_visita = models.DateField()
    hora_visita = models.TimeField()
    qr_code = models.ImageField(storage=MediaStorage(), upload_to='qr_visitantes/', blank=True)
    qr_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    qr_activo = models.BooleanField(default=True, verbose_name="QR Activo", help_text="El QR se desactiva automáticamente después de la salida")
    confirmado = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre} - {self.departamento_visita} - {self.fecha_visita}"

    def generar_qr(self):
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(f"VISITANTE:{str(self.qr_uuid)}")
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buffer = BytesIO()
        img.save(buffer, format='PNG')
        filename = f'qr_visitante_{self.id}.png'
        self.qr_code.save(filename, File(buffer), save=False)
        buffer.close()

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and not self.qr_code:
            self.generar_qr()
            super().save(update_fields=['qr_code'])

    class Meta:
        verbose_name_plural = "Visitantes"

class RegistroVisita(models.Model):
    visitante = models.ForeignKey(Visitante, on_delete=models.CASCADE)
    hora_entrada = models.DateTimeField(auto_now_add=True)
    hora_salida = models.DateTimeField(null=True, blank=True)
    observaciones = models.TextField(blank=True)

    def __str__(self):
        return f"{self.visitante.nombre} - {self.hora_entrada}"

    class Meta:
        verbose_name_plural = "Registros de Visitas"
        ordering = ['-hora_entrada']

class ConfiguracionSistema(models.Model):
    hora_entrada = models.TimeField(default="09:00:00")
    minutos_tolerancia = models.IntegerField(default=15)
    email_gerente = models.EmailField()
    ruta_red_reportes = models.CharField(max_length=500, help_text="Ruta de red para guardar reportes mensuales")

    def __str__(self):
        return "Configuración del Sistema"

    class Meta:
        verbose_name_plural = "Configuración del Sistema"

# ========== SISTEMA DE PERMISOS ==========

class TipoPermiso(models.Model):
    """Catálogo de tipos de permisos disponibles"""
    nombre = models.CharField(max_length=100, verbose_name="Nombre del permiso")
    requiere_aprobacion_gerencia = models.BooleanField(
        default=False,
        verbose_name="Requiere aprobación de gerencia",
        help_text="Si requiere aprobación adicional de gerencia general"
    )
    dias_anticipacion_minimos = models.IntegerField(
        default=0,
        verbose_name="Días de anticipación mínimos",
        help_text="Cuántos días antes debe solicitarse"
    )
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Tipo de Permiso"
        verbose_name_plural = "Tipos de Permisos"

class EstadoSolicitud(models.TextChoices):
    PENDIENTE = 'PENDIENTE', 'Pendiente'
    APROBADO_JEFE = 'APROBADO_JEFE', 'Aprobado por Jefe'
    APROBADO_GERENCIA = 'APROBADO_GERENCIA', 'Aprobado por Gerencia'
    RECHAZADO = 'RECHAZADO', 'Rechazado'

class TipoAusencia(models.TextChoices):
    DIAS_COMPLETOS = 'DIAS_COMPLETOS', 'Días Completos'
    HORAS = 'HORAS', 'Horas'

class SolicitudPermiso(models.Model):
    """Solicitudes de permisos de empleados"""
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name='permisos')
    tipo_permiso = models.ForeignKey(TipoPermiso, on_delete=models.PROTECT)
    fecha_solicitud = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de solicitud")
    tipo_ausencia = models.CharField(
        max_length=20,
        choices=TipoAusencia.choices,
        default=TipoAusencia.DIAS_COMPLETOS,
        verbose_name="Tipo de ausencia"
    )
    # Para permisos por días
    fecha_inicio = models.DateField(verbose_name="Fecha de inicio")
    fecha_fin = models.DateField(null=True, blank=True, verbose_name="Fecha de fin")
    # Para permisos por horas
    hora_inicio = models.TimeField(null=True, blank=True, verbose_name="Hora de inicio")
    hora_fin = models.TimeField(null=True, blank=True, verbose_name="Hora de fin")
    # Totales calculados
    total_dias = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Total de días")
    total_horas = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Total de horas")
    con_goce_sueldo = models.BooleanField(default=True, verbose_name="Con goce de sueldo")
    motivo = models.TextField(verbose_name="Motivo")
    estado = models.CharField(
        max_length=20,
        choices=EstadoSolicitud.choices,
        default=EstadoSolicitud.PENDIENTE
    )
    comentarios_aprobacion = models.TextField(blank=True, verbose_name="Comentarios de aprobación")
    aprobado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='permisos_aprobados')
    fecha_aprobacion = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de aprobación")
    archivo_adjunto = models.FileField(upload_to='permisos/', blank=True, verbose_name="Archivo adjunto")

    def save(self, *args, **kwargs):
        # Calcular totales automáticamente
        if self.tipo_ausencia == TipoAusencia.DIAS_COMPLETOS and self.fecha_inicio:
            fecha_fin = self.fecha_fin or self.fecha_inicio
            self.total_dias = (fecha_fin - self.fecha_inicio).days + 1
            self.total_horas = 0
        elif self.tipo_ausencia == TipoAusencia.HORAS and self.hora_inicio and self.hora_fin:
            inicio_dt = datetime.combine(datetime.today(), self.hora_inicio)
            fin_dt = datetime.combine(datetime.today(), self.hora_fin)
            diferencia = (fin_dt - inicio_dt).total_seconds() / 3600
            self.total_horas = abs(diferencia)
            self.total_dias = 0
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.empleado.user.get_full_name()} - {self.tipo_permiso.nombre} - {self.fecha_inicio}"

    class Meta:
        verbose_name = "Solicitud de Permiso"
        verbose_name_plural = "Solicitudes de Permisos"
        ordering = ['-fecha_solicitud']

# ========== SISTEMA DE VACACIONES ==========

class PeriodoVacacional(models.Model):
    """Periodos vacacionales de la empresa"""
    anio = models.IntegerField(verbose_name="Año")
    fecha_inicio_periodo = models.DateField(verbose_name="Inicio del periodo")
    fecha_fin_periodo = models.DateField(verbose_name="Fin del periodo")
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"Periodo Vacacional {self.anio}"

    class Meta:
        verbose_name = "Periodo Vacacional"
        verbose_name_plural = "Periodos Vacacionales"
        ordering = ['-anio']

class SaldoVacaciones(models.Model):
    """Saldo de vacaciones por empleado y periodo"""
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name='saldos_vacaciones')
    periodo_vacacional = models.ForeignKey(PeriodoVacacional, on_delete=models.CASCADE)
    dias_totales = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="Días totales",
        help_text="Días de vacaciones según antigüedad"
    )
    dias_tomados = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name="Días tomados"
    )
    fecha_antiguedad = models.DateField(
        verbose_name="Fecha de antigüedad",
        help_text="Fecha de ingreso del empleado para calcular días"
    )

    @property
    def dias_pendientes(self):
        return self.dias_totales - self.dias_tomados

    def __str__(self):
        return f"{self.empleado.user.get_full_name()} - {self.periodo_vacacional.anio} ({self.dias_pendientes} días pendientes)"

    class Meta:
        verbose_name = "Saldo de Vacaciones"
        verbose_name_plural = "Saldos de Vacaciones"
        unique_together = ['empleado', 'periodo_vacacional']
        ordering = ['-periodo_vacacional__anio']

class SolicitudVacaciones(models.Model):
    """Solicitudes de vacaciones de empleados"""
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name='vacaciones')
    saldo_vacaciones = models.ForeignKey(SaldoVacaciones, on_delete=models.PROTECT)
    fecha_solicitud = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de solicitud")
    fecha_inicio = models.DateField(verbose_name="Fecha de inicio")
    fecha_fin = models.DateField(verbose_name="Fecha de fin")
    dias_solicitados = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="Días solicitados"
    )
    estado = models.CharField(
        max_length=20,
        choices=EstadoSolicitud.choices,
        default=EstadoSolicitud.PENDIENTE
    )
    motivo = models.TextField(blank=True, verbose_name="Motivo")
    aprobado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='vacaciones_aprobadas')
    fecha_aprobacion = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de aprobación")
    comentarios_aprobacion = models.TextField(blank=True, verbose_name="Comentarios de aprobación")

    def save(self, *args, **kwargs):
        # Calcular días solicitados automáticamente
        if self.fecha_inicio and self.fecha_fin:
            self.dias_solicitados = (self.fecha_fin - self.fecha_inicio).days + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.empleado.user.get_full_name()} - {self.fecha_inicio} a {self.fecha_fin}"

    class Meta:
        verbose_name = "Solicitud de Vacaciones"
        verbose_name_plural = "Solicitudes de Vacaciones"
        ordering = ['-fecha_solicitud']

# ========== SISTEMA DE JUSTIFICANTES ==========

class AplicaJustificante(models.TextChoices):
    RETARDO = 'RETARDO', 'Retardo'
    FALTA = 'FALTA', 'Falta'
    AMBOS = 'AMBOS', 'Ambos'

class TipoJustificante(models.Model):
    """Catálogo de tipos de justificantes"""
    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    aplica_para = models.CharField(
        max_length=20,
        choices=AplicaJustificante.choices,
        default=AplicaJustificante.AMBOS,
        verbose_name="Aplica para"
    )
    requiere_documento = models.BooleanField(default=True, verbose_name="Requiere documento")
    cancela_penalizacion = models.BooleanField(
        default=True,
        verbose_name="Cancela penalización",
        help_text="Si el justificante aprobado cancela la penalización"
    )
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Tipo de Justificante"
        verbose_name_plural = "Tipos de Justificantes"

class EstadoJustificante(models.TextChoices):
    PENDIENTE = 'PENDIENTE', 'Pendiente'
    APROBADO = 'APROBADO', 'Aprobado'
    RECHAZADO = 'RECHAZADO', 'Rechazado'

class Justificante(models.Model):
    """Justificantes presentados por empleados"""
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name='justificantes')
    tipo_justificante = models.ForeignKey(TipoJustificante, on_delete=models.PROTECT)
    asistencia = models.ForeignKey(
        Asistencia,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Registro de asistencia relacionado (null si es falta completa)"
    )
    fecha_incidente = models.DateField(verbose_name="Fecha del incidente")
    motivo = models.TextField(verbose_name="Motivo")
    documento_respaldo = models.FileField(
        upload_to='justificantes/',
        blank=True,
        verbose_name="Documento de respaldo"
    )
    fecha_presentacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de presentación")
    estado = models.CharField(
        max_length=20,
        choices=EstadoJustificante.choices,
        default=EstadoJustificante.PENDIENTE
    )
    revisado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='justificantes_revisados')
    fecha_revision = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de revisión")
    comentarios_revision = models.TextField(blank=True, verbose_name="Comentarios de revisión")

    def __str__(self):
        return f"{self.empleado.user.get_full_name()} - {self.tipo_justificante.nombre} - {self.fecha_incidente}"

    class Meta:
        verbose_name = "Justificante"
        verbose_name_plural = "Justificantes"
        ordering = ['-fecha_presentacion']

# ========== ASIGNACIÓN DIARIA DE TURNOS ==========

class AsignacionTurnoDiaria(models.Model):
    """Asignación de turno específica para un empleado en una fecha"""
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name='asignaciones_diarias')
    fecha = models.DateField(verbose_name="Fecha")
    turno_rotativo = models.ForeignKey(
        TurnoRotativo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Turno rotativo",
        help_text="Selecciona un turno predefinido o deja en blanco para horario personalizado"
    )
    es_descanso = models.BooleanField(default=False, verbose_name="Es día de descanso")
    hora_entrada = models.TimeField(null=True, blank=True, verbose_name="Hora de entrada")
    hora_salida = models.TimeField(null=True, blank=True, verbose_name="Hora de salida")
    cruza_medianoche = models.BooleanField(
        default=False,
        verbose_name="Cruza medianoche",
        help_text="Marca esto si el turno termina al día siguiente (ej: 22:00 a 06:00)"
    )
    notas = models.TextField(blank=True, verbose_name="Notas adicionales")
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Si se selecciona un turno rotativo, copiar sus horarios
        if self.turno_rotativo and not self.hora_entrada:
            self.hora_entrada = self.turno_rotativo.hora_entrada
            self.hora_salida = self.turno_rotativo.hora_salida
        
        # Detectar automáticamente si cruza medianoche
        if self.hora_entrada and self.hora_salida:
            if self.hora_salida < self.hora_entrada:
                self.cruza_medianoche = True
        
        # Si es descanso, limpiar horarios
        if self.es_descanso:
            self.hora_entrada = None
            self.hora_salida = None
            self.turno_rotativo = None
            self.cruza_medianoche = False
        
        super().save(*args, **kwargs)

    def __str__(self):
        if self.es_descanso:
            return f"{self.empleado.user.get_full_name()} - {self.fecha} - DESCANSO"
        elif self.turno_rotativo:
            return f"{self.empleado.user.get_full_name()} - {self.fecha} - {self.turno_rotativo.nombre}"
        elif self.hora_entrada and self.hora_salida:
            turno_txt = f"{self.hora_entrada.strftime('%H:%M')} - {self.hora_salida.strftime('%H:%M')}"
            if self.cruza_medianoche:
                turno_txt += " (cruza medianoche)"
            return f"{self.empleado.user.get_full_name()} - {self.fecha} - {turno_txt}"
        else:
            return f"{self.empleado.user.get_full_name()} - {self.fecha} - Sin asignar"

    class Meta:
        verbose_name = "Asignación de Turno Diaria"
        verbose_name_plural = "Asignaciones de Turnos Diarias"
        unique_together = ['empleado', 'fecha']
        ordering = ['fecha', 'empleado']
