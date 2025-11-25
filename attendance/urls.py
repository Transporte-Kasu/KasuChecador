from django.urls import path
from . import views

urlpatterns = [
    # Health check para DigitalOcean
    path('health/', views.health_check, name='health_check'),
    
    # Tablet de recepción
    path('checkin/', views.checkin_view, name='checkin'),
    path('', views.checkin_view_tablet, name='checkin_tablet'),

    # Registro de visitantes (público)
    path('visitante/registro/', views.VisitanteCreateView.as_view(), name='visitante_registro'),
    path('visitante/exito/', views.visitante_exito, name='visitante_exito'),

    # Dashboard y reportes (requiere autenticación)
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('reporte/mensual/', views.reporte_mensual_view, name='reporte_mensual'),
    path('reporte/mensual/<int:mes>/<int:anio>/', views.reporte_mensual_view, name='reporte_mensual_detalle'),
]