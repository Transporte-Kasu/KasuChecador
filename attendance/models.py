from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, timedelta
import qrcode
from io import BytesIO
from django.core.files import File
import uuid

class Departamento(models.Model):
    nombre = models.CharField(max_length=100)
    email = models.EmailField()

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name_plural = "Departamentos"

class TipoHorario(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    es_turno_24h = models.BooleanField(default=False, verbose_name="Es turno de 24 horas")
    hora_entrada = models.TimeField(null=True, blank=True)
    hora_salida = models.TimeField(null=True, blank=True)
    minutos_tolerancia = models.IntegerField(default=15)
    tiene_horario_comida = models.BooleanField(default=False)
    hora_inicio_comida = models.TimeField(null=True, blank=True)
    hora_fin_comida = models.TimeField(null=True, blank=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name_plural = "Tipos de Horario"

class Empleado(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    codigo_empleado = models.CharField(max_length=20, unique=True)
    departamento = models.ForeignKey(Departamento, on_delete=models.SET_NULL, null=True)
    tipo_horario = models.ForeignKey(TipoHorario, on_delete=models.SET_NULL, null=True, blank=True)
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True)
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
        """Calcula si hay retardo considerando minutos de tolerancia"""
        if self.tipo_movimiento == TipoMovimiento.ENTRADA:
            # Obtener configuración del tipo de horario del empleado
            tipo_horario = self.empleado.tipo_horario
            
            # Si el empleado tiene tipo de horario asignado, usar esa configuración
            if tipo_horario:
                # Para turnos de 24 horas, verificar el ciclo
                if tipo_horario.es_turno_24h:
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
                
                # Para horarios regulares, usar hora_entrada del tipo de horario
                if tipo_horario.hora_entrada:
                    hora_esperada = tipo_horario.hora_entrada
                    tolerancia = timedelta(minutes=tipo_horario.minutos_tolerancia)
                else:
                    # Si no tiene hora_entrada definida, usar parámetro
                    hora_esperada = datetime.strptime(hora_entrada_esperada, "%H:%M:%S").time()
                    tolerancia = timedelta(minutes=minutos_tolerancia)
            else:
                # Fallback a configuración global o parámetros
                hora_esperada = datetime.strptime(hora_entrada_esperada, "%H:%M:%S").time()
                tolerancia = timedelta(minutes=minutos_tolerancia)
            
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
    qr_code = models.ImageField(upload_to='qr_visitantes/', blank=True)
    qr_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
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