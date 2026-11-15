"""Quién puede usar la pantalla de traslados.

El responsable NO inicia sesión: se identifica con su tarjeta.
Lo que se valida es el CELULAR: un administrador lo autoriza una sola vez y
queda guardada una cookie con un token secreto. Así nadie puede registrar
traslados desde un equipo no autorizado aunque conozca el UID de una tarjeta.
"""
import secrets
from functools import wraps

from django.http import JsonResponse
from django.utils import timezone

from .models import Dispositivo

COOKIE = "nfc_celular"
UN_ANIO = 60 * 60 * 24 * 365


def dispositivo_de(request):
    if hasattr(request, "_dispositivo"):
        return request._dispositivo
    token = request.COOKIES.get(COOKIE)
    disp = None
    if token:
        disp = Dispositivo.objects.filter(token_hash=Dispositivo.hash_token(token), activo=True).first()
        if disp:
            Dispositivo.objects.filter(pk=disp.pk).update(ultimo_uso=timezone.now())
    request._dispositivo = disp
    return disp


def autorizado(request) -> bool:
    return request.user.is_authenticated or dispositivo_de(request) is not None


def quien_registra(request) -> str:
    """Texto que queda en el movimiento: celular autorizado o usuario."""
    disp = dispositivo_de(request)
    if disp:
        return f"Celular: {disp.nombre}"
    return f"Usuario: {request.user.get_username()}"


def api_autorizado(vista):
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not autorizado(request):
            return JsonResponse(
                {"error": "Este celular no está autorizado. Pida al administrador que lo autorice."},
                status=401,
            )
        return vista(request, *args, **kwargs)

    return envoltura


def autorizar_celular(request, response, nombre: str) -> Dispositivo:
    """Crea el dispositivo y deja el token en la cookie de la respuesta."""
    token = secrets.token_urlsafe(32)
    disp = Dispositivo.objects.create(
        nombre=nombre,
        token_hash=Dispositivo.hash_token(token),
        autorizado_por=request.user.get_username(),
    )
    response.set_cookie(
        COOKIE,
        token,
        max_age=UN_ANIO,
        httponly=True,  # el JavaScript de la página no puede leerla
        samesite="Lax",
        secure=request.is_secure(),
    )
    return disp
