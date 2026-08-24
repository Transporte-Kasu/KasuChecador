# Guía de Uso: Sistema de Horarios Flexibles, Permisos y Vacaciones

## Resumen de Cambios

Se ha implementado un sistema completo para manejar:
- ✅ Horarios flexibles por día de la semana
- ✅ Turnos rotativos de 8 horas
- ✅ Turnos de 24x24 horas (ya existente, mejorado)
- ✅ Permisos (por días o por horas, con/sin goce de sueldo)
- ✅ Vacaciones con control de saldo
- ✅ Justificantes para retardos y faltas

## 1. Tipos de Horarios

### 1.1 Horario Fijo
**Uso:** Empleados con horario estándar (ej: Lunes-Viernes 09:00-18:00)

**Configuración:**
1. Admin → Tipos de Horario → Agregar nuevo
2. Llenar campos:
   - Nombre: "Oficina Estándar"
   - Tipo de Sistema: "Horario Fijo"
   - Hora entrada: 09:00
   - Hora salida: 18:00
   - Horas jornada completa: 8.0
   - Tolerancia: 15 minutos
   - ✓ Tiene horario de comida
   - Hora inicio comida: 14:00
   - Hora fin comida: 15:00

### 1.2 Horario Personalizado por Día
**Uso:** Empleados con horarios diferentes por día (ej: Lun-Vie 09:00-18:00, Sábados 09:00-13:00)

**Configuración:**
1. Crear Tipo de Horario:
   - Nombre: "Oficina con Sábado"
   - Tipo de Sistema: "Horario Personalizado por Día"
   - ✓ Requiere configuración por día
   
2. En la misma pantalla, agregar en "Horarios por Día":
   
   **Lunes:**
   - Día: Lunes
   - ✓ Es día laboral
   - Hora entrada: 09:00
   - Hora salida: 18:00
   - Inicio comida: 14:00
   - Fin comida: 15:00
   
   **Martes-Viernes:** (repetir igual que lunes)
   
   **Sábado:**
   - Día: Sábado
   - ✓ Es día laboral
   - ✓ Es medio día
   - Hora entrada: 09:00
   - Hora salida: 13:00
   
   **Domingo:**
   - Día: Domingo
   - ☐ Es día laboral (desmarcar)

### 1.3 Turnos Rotativos
**Uso:** Empleados con turnos de 8 horas que rotan (matutino, vespertino, nocturno)

**Configuración:**
1. Crear Tipo de Horario:
   - Nombre: "Turnos Rotativos"
   - Tipo de Sistema: "Turno Rotativo"
   - Horas jornada completa: 8.0

2. Agregar turnos en "Turnos Rotativos":
   
   **Turno Matutino:**
   - Nombre: "Matutino"
   - Hora entrada: 06:00
   - Hora salida: 14:00
   - Orden en ciclo: 1
   - Días consecutivos: 3
   
   **Turno Vespertino:**
   - Nombre: "Vespertino"
   - Hora entrada: 14:00
   - Hora salida: 22:00
   - Orden en ciclo: 2
   - Días consecutivos: 3
   
   **Turno Nocturno:**
   - Nombre: "Nocturno"
   - Hora entrada: 22:00
   - Hora salida: 06:00
   - Orden en ciclo: 3
   - Días consecutivos: 3

3. Asignar turnos a empleados:
   - Admin → Asignaciones de Turnos Rotativos → Agregar
   - Empleado: (seleccionar)
   - Turno rotativo: "Matutino"
   - Fecha inicio: 2025-12-10
   - Fecha fin: 2025-12-12
   - ✓ Activo

### 1.4 Turnos 24x24 Horas
**Uso:** Empleados que trabajan 24 horas y descansan 24 horas

**Configuración:**
1. Crear Tipo de Horario:
   - Nombre: "Turno 24x24"
   - Tipo de Sistema: "Turno 24x24 horas"
   - ✓ Es turno de 24 horas
   - Hora entrada: 08:00 (opcional, referencia)
   - Horas jornada completa: 24.0

## 2. Sistema de Permisos

### 2.1 Configurar Tipos de Permisos

**Ejemplos:**

1. **Permiso Personal**
   - Admin → Tipos de Permisos → Agregar
   - Nombre: "Permiso Personal"
   - ☐ Requiere aprobación de gerencia
   - Días anticipación mínimos: 1
   - ✓ Activo

2. **Cita Médica**
   - Nombre: "Cita Médica"
   - ☐ Requiere aprobación de gerencia
   - Días anticipación mínimos: 0 (puede ser mismo día)

3. **Asunto Familiar Importante**
   - Nombre: "Asunto Familiar"
   - ✓ Requiere aprobación de gerencia
   - Días anticipación mínimos: 3

### 2.2 Solicitar Permiso

**Por Días Completos:**
1. Admin → Solicitudes de Permisos → Agregar
2. Empleado: (seleccionar)
3. Tipo de permiso: "Permiso Personal"
4. Tipo de ausencia: "Días Completos"
5. Fecha inicio: 2025-12-15
6. Fecha fin: 2025-12-15 (mismo día si es 1 día)
7. ✓ Con goce de sueldo
8. Motivo: "Trámite personal urgente"
9. Estado: Pendiente
10. Guardar

**Por Horas:**
1. Similar al anterior pero:
   - Tipo de ausencia: "Horas"
   - Fecha inicio: 2025-12-15
   - Hora inicio: 10:00
   - Hora fin: 12:00
   - Total horas: 2.0 (se calcula automáticamente)

### 2.3 Aprobar/Rechazar Permisos

**Método 1 - Individual:**
1. Admin → Solicitudes de Permisos
2. Click en el permiso
3. Cambiar Estado a "Aprobado por Jefe" o "Aprobado por Gerencia"
4. Comentarios aprobación: "Aprobado"
5. Guardar

**Método 2 - Masivo:**
1. Admin → Solicitudes de Permisos
2. Seleccionar múltiples permisos (checkbox)
3. Acción: "Aprobar solicitudes seleccionadas"
4. Ejecutar

## 3. Sistema de Vacaciones

### 3.1 Configurar Periodos Vacacionales

1. Admin → Periodos Vacacionales → Agregar
   - Año: 2025
   - Fecha inicio periodo: 2025-01-01
   - Fecha fin periodo: 2025-12-31
   - ✓ Activo

### 3.2 Asignar Saldo de Vacaciones

1. Admin → Saldos de Vacaciones → Agregar
2. Empleado: (seleccionar)
3. Periodo vacacional: 2025
4. Días totales: 12.0 (según antigüedad)
5. Días tomados: 0.0
6. Fecha antigüedad: 2020-01-15 (fecha de ingreso)
7. Guardar

**Cálculo de días según LFT:**
- 1 año: 12 días
- 2 años: 14 días
- 3 años: 16 días
- 4 años: 18 días
- 5-9 años: 20 días
- 10-14 años: 22 días
- etc.

### 3.3 Solicitar Vacaciones

1. Admin → Solicitudes de Vacaciones → Agregar
2. Empleado: (seleccionar)
3. Saldo vacaciones: (seleccionar el saldo del año actual)
4. Fecha inicio: 2025-12-20
5. Fecha fin: 2025-12-27
6. Días solicitados: 8.0 (se calcula automáticamente)
7. Motivo: "Vacaciones de fin de año"
8. Estado: Pendiente
9. Guardar

### 3.4 Aprobar Vacaciones

**IMPORTANTE:** Al aprobar vacaciones, el saldo se descuenta automáticamente.

1. Admin → Solicitudes de Vacaciones
2. Seleccionar solicitud(es)
3. Acción: "Aprobar vacaciones seleccionadas"
4. Ejecutar

El sistema verifica:
- ✓ Que el empleado tenga saldo suficiente
- ✓ Actualiza automáticamente "días tomados"
- ✗ Si no hay saldo, muestra error

## 4. Sistema de Justificantes

### 4.1 Configurar Tipos de Justificantes

1. **Incapacidad Médica**
   - Admin → Tipos de Justificantes → Agregar
   - Nombre: "Incapacidad Médica"
   - Aplica para: "Ambos" (retardo y falta)
   - ✓ Requiere documento
   - ✓ Cancela penalización

2. **Justificante de Retardo**
   - Nombre: "Justificante Retardo"
   - Aplica para: "Retardo"
   - ☐ Requiere documento
   - ✓ Cancela penalización

3. **Justificante de Falta**
   - Nombre: "Falta Justificada"
   - Aplica para: "Falta"
   - ✓ Requiere documento

### 4.2 Presentar Justificante

1. Admin → Justificantes → Agregar
2. Empleado: (seleccionar)
3. Tipo de justificante: "Incapacidad Médica"
4. Asistencia: (seleccionar el registro de asistencia con retardo, o dejar vacío si es falta)
5. Fecha incidente: 2025-12-10
6. Motivo: "Gripe y fiebre"
7. Documento respaldo: (subir archivo PDF/imagen)
8. Estado: Pendiente
9. Guardar

### 4.3 Aprobar/Rechazar Justificantes

1. Admin → Justificantes
2. Seleccionar justificante(s)
3. Acción: "Aprobar justificantes seleccionados" o "Rechazar..."
4. Ejecutar

## 5. Validaciones en Check-In

Cuando un empleado hace check-in, el sistema automáticamente:

✓ **Verifica vacaciones:** Si tiene vacaciones aprobadas, muestra advertencia
✓ **Verifica permisos de día:** Si tiene permiso de día completo, muestra advertencia
✓ **Verifica permisos de horas:** Si tiene permiso por horas, muestra información
✓ **Calcula retardo según horario:** Usa el horario correcto (fijo/rotativo/personalizado)
✓ **Valida día laboral:** No marca retardo en días no laborales

## 6. Asignar Horarios a Empleados

1. Admin → Empleados
2. Click en empleado
3. Tipo horario: (seleccionar el tipo creado)
4. Guardar

**O asignación masiva:**
1. Admin → Empleados
2. Seleccionar múltiples empleados
3. Acción: "Asignar tipo de horario a empleados seleccionados"
4. Seleccionar tipo de horario
5. Aplicar

## 7. Ejemplos de Casos de Uso

### Caso 1: Empleado de Oficina con Sábado Medio Día

```
Tipo Horario: "Oficina con Sábado" (Personalizado)
- Lunes-Viernes: 09:00-18:00 (comida 14:00-15:00)
- Sábado: 09:00-13:00 (sin comida)
- Domingo: No laboral
```

### Caso 2: Guardia de Seguridad (24x24)

```
Tipo Horario: "Seguridad 24x24" (Turno 24H)
- Trabaja 24 horas seguidas
- Descansa 24 horas
- Check-in cada 48 horas aproximadamente
```

### Caso 3: Operador de Producción (Turnos Rotativos)

```
Tipo Horario: "Producción Rotativos" (Rotativo)
- 3 días turno matutino (06:00-14:00)
- 3 días turno vespertino (14:00-22:00)
- 3 días turno nocturno (22:00-06:00)
- Repetir ciclo

Asignaciones:
- Del 10-12 dic: Turno Matutino
- Del 13-15 dic: Turno Vespertino
- Del 16-18 dic: Turno Nocturno
```

### Caso 4: Gerente con Permiso de Horas

```
Tiene reunión médica de 10:00 a 12:00

Solicitud Permiso:
- Tipo: Horas
- Fecha: 2025-12-10
- Hora inicio: 10:00
- Hora fin: 12:00
- Con goce de sueldo: Sí

Al hacer check-in a las 10:30, muestra:
"Tienes permiso por horas de 10:00 a 12:00"
```

## 8. Reportes

Los reportes diarios/semanales ahora incluyen:
- Empleados con vacaciones
- Empleados con permisos
- Justificantes aplicados

## 9. Notas Importantes

⚠️ **Compatibilidad:** Los empleados sin tipo de horario asignado seguirán usando la configuración global (ConfiguracionSistema)

⚠️ **Vacaciones:** Al aprobar vacaciones, el saldo se descuenta inmediatamente. No se puede deshacer automáticamente, hay que ajustar manualmente.

⚠️ **Turnos Rotativos:** Debes crear las asignaciones manualmente antes del inicio del ciclo.

⚠️ **Días no laborales:** El sistema no marca retardo en días configurados como no laborales.

## 10. Acceso al Admin

URL: `https://tu-dominio.com/admin/`

Secciones nuevas:
- **Horarios:**
  - Tipos de Horario
  - Asignaciones de Turnos Rotativos
  
- **Permisos:**
  - Tipos de Permisos
  - Solicitudes de Permisos
  
- **Vacaciones:**
  - Periodos Vacacionales
  - Saldos de Vacaciones
  - Solicitudes de Vacaciones
  
- **Justificantes:**
  - Tipos de Justificantes
  - Justificantes

## 11. Próximos Pasos Recomendados

1. ✅ Crear los Tipos de Horarios según tus necesidades
2. ✅ Asignar horarios a todos los empleados activos
3. ✅ Crear periodo vacacional del año actual
4. ✅ Asignar saldo de vacaciones a empleados
5. ✅ Configurar tipos de permisos
6. ✅ Configurar tipos de justificantes
7. ✅ Probar check-in con diferentes horarios
8. ✅ Capacitar a gerentes en aprobación de solicitudes
