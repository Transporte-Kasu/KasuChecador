"""
Middleware personalizado para KasuChecador
"""
from django.http import HttpResponse


class HealthCheckMiddleware:
    """
    Middleware que intercepta las peticiones al health check
    antes de que pasen por validación de ALLOWED_HOSTS.
    
    Esto evita errores 400 en deployments de DigitalOcean.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Si es health check, responder inmediatamente sin validaciones
        if request.path in ['/health/', '/health']:
            return HttpResponse("OK", status=200, content_type="text/plain")
        
        # Para cualquier otra ruta, continuar normalmente
        response = self.get_response(request)
        return response
