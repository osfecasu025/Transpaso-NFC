import json
from functools import wraps

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import logout
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from .acceso import api_autorizado, autorizado, autorizar_celular, dispositivo_de, quien_registra

from .models import Activo, Responsable, Sede
from .services import (
    ReemplazoRequerido,
    TrasladoError,
    asociar_uid,
    buscar_activo,
    buscar_responsable,
    describir_uid,
    registrar_traslado,
)


def api_staff_required(vista):
    """Solo administradores (is_staff) pueden asociar tags."""

    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Sesión vencida. Vuelva a iniciar sesión."}, status=401)
        if not request.user.is_staff:
            return JsonResponse({"error": "Solo un administrador puede registrar tags."}, status=403)
        return vista(request, *args, **kwargs)

    return envoltura


def escanear(request):
    if not autorizado(request):
        return render(request, "traslados/no_autorizado.html", status=403)
    return render(request, "traslados/escanear.html", {"dispositivo": dispositivo_de(request)})


@require_GET
@api_autorizado
def api_responsable(request, uid):
    try:
        r = buscar_responsable(uid)
    except TrasladoError as e:
        return JsonResponse({"error": str(e)}, status=404)
    return JsonResponse({"nombre": r.nombre, "cargo": r.cargo})


@require_GET
@api_autorizado
def api_activo(request, uid):
    try:
        a = buscar_activo(uid)
    except TrasladoError as e:
        return JsonResponse({"error": str(e)}, status=404)
    return JsonResponse(
        {
            "codigo": a.codigo,
            "nombre": a.nombre,
            "serial": a.serial,
            "sede_actual": a.sede_actual.nombre,
            "area_actual": a.area_actual.nombre,
            "area_actual_id": a.area_actual_id,
        }
    )


@require_GET
@api_autorizado
def api_sedes(request):
    sedes = Sede.objects.filter(activa=True).prefetch_related("areas")
    data = [
        {
            "id": s.id,
            "nombre": s.nombre,
            "areas": [{"id": a.id, "nombre": a.nombre} for a in s.areas.all() if a.activa],
        }
        for s in sedes
    ]
    return JsonResponse({"sedes": data})


@require_POST
@api_autorizado
def api_traslado(request):
    try:
        datos = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Solicitud inválida."}, status=400)

    faltan = [c for c in ("tarjeta_uid", "pin_uid", "area_destino") if not datos.get(c)]
    if faltan:
        return JsonResponse({"error": f"Faltan datos: {', '.join(faltan)}."}, status=400)

    try:
        mov = registrar_traslado(
            tarjeta_uid=str(datos["tarjeta_uid"]),
            pin_uid=str(datos["pin_uid"]),
            area_destino_id=datos["area_destino"],
            registrado_por=quien_registra(request),
        )
    except TrasladoError as e:
        return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse(
        {
            "ok": True,
            "mensaje": f"{mov.activo.codigo} quedó en {mov.area_destino}.",
            "movimiento_id": mov.pk,
        },
        status=201,
    )


# ---------------------------------------------------------------------------
# Registro de tags: asociar el UID leído a un equipo o a un responsable
# ---------------------------------------------------------------------------
@staff_member_required
def registrar(request):
    return render(request, "traslados/registrar.html", {"dispositivo": dispositivo_de(request)})


@require_POST
@staff_member_required
def autorizar(request):
    """Autoriza ESTE celular y cierra la sesión del administrador en él.

    Cerrar la sesión es clave: si el administrador la dejara abierta, cualquier
    persona que use el celular tendría acceso de administrador.
    """
    nombre = request.POST.get("nombre", "").strip()[:100]
    if not nombre:
        messages.error(request, "Escriba un nombre para el celular.")
        return redirect("registrar")
    respuesta = redirect("escanear")
    autorizar_celular(request, respuesta, nombre)
    logout(request)
    return respuesta


@require_GET
@api_staff_required
def api_uid(request, uid):
    return JsonResponse({"asociado": describir_uid(uid)})


@require_GET
@api_staff_required
def api_buscar(request, tipo):
    q = request.GET.get("q", "").strip()
    if len(q) < 2:
        return JsonResponse({"resultados": []})
    if tipo == "activo":
        qs = Activo.objects.select_related("sede_actual", "area_actual").filter(
            Q(codigo__icontains=q) | Q(nombre__icontains=q) | Q(serial__icontains=q)
        )[:15]
        res = [
            {
                "id": a.pk,
                "titulo": f"{a.codigo} – {a.nombre}",
                "detalle": f"{a.sede_actual} – {a.area_actual.nombre}",
                "uid": a.pin_uid,
            }
            for a in qs
        ]
    elif tipo == "responsable":
        qs = Responsable.objects.filter(Q(nombre__icontains=q) | Q(documento__icontains=q))[:15]
        res = [
            {
                "id": r.pk,
                "titulo": r.nombre,
                "detalle": f"{r.cargo} · doc. {r.documento}" + ("" if r.activo else " · INACTIVO"),
                "uid": r.tarjeta_uid,
            }
            for r in qs
        ]
    else:
        return JsonResponse({"error": "Tipo no válido."}, status=400)
    return JsonResponse({"resultados": res})


@require_POST
@api_staff_required
def api_asociar(request):
    try:
        d = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Solicitud inválida."}, status=400)
    try:
        obj = asociar_uid(
            tipo=d.get("tipo"),
            objeto_id=d.get("id"),
            uid=str(d.get("uid", "")),
            reemplazar=bool(d.get("reemplazar")),
        )
    except ReemplazoRequerido as e:
        return JsonResponse({"error": str(e), "requiere_reemplazo": True}, status=409)
    except TrasladoError as e:
        return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"ok": True, "mensaje": f"Tag asociado a {obj}."})
