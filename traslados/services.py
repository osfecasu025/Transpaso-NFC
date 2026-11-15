"""Reglas de negocio del traslado. Las vistas solo llaman a estas funciones."""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction

from .models import Activo, Area, Movimiento, Responsable, normalizar_uid

logger = logging.getLogger(__name__)


class TrasladoError(Exception):
    """Error de validación que se le muestra al usuario tal cual."""


def buscar_responsable(tarjeta_uid: str) -> Responsable:
    uid = normalizar_uid(tarjeta_uid)
    try:
        return Responsable.objects.get(tarjeta_uid=uid, activo=True)
    except Responsable.DoesNotExist:
        raise TrasladoError("Tarjeta no registrada o desactivada.")


def buscar_activo(pin_uid: str) -> Activo:
    uid = normalizar_uid(pin_uid)
    try:
        return Activo.objects.select_related("sede_actual", "area_actual").get(pin_uid=uid)
    except Activo.DoesNotExist:
        raise TrasladoError("Este pin no está asociado a ningún equipo.")


def registrar_traslado(*, tarjeta_uid, pin_uid, area_destino_id, registrado_por) -> Movimiento:
    """Guarda el movimiento y actualiza la ubicación en una sola transacción.

    El origen SIEMPRE se toma de la base de datos, nunca de lo que envía el celular.
    La sede destino se deduce del área, así no pueden llegar sede y área incoherentes.
    """
    responsable = buscar_responsable(tarjeta_uid)

    try:
        area_destino = Area.objects.select_related("sede").get(
            pk=area_destino_id, activa=True, sede__activa=True
        )
    except (Area.DoesNotExist, ValueError, TypeError):
        raise TrasladoError("Área de destino no válida.")

    with transaction.atomic():
        # Bloquea la fila para que dos celulares no muevan el mismo equipo a la vez.
        try:
            activo = Activo.objects.select_for_update().get(pin_uid=normalizar_uid(pin_uid))
        except Activo.DoesNotExist:
            raise TrasladoError("Este pin no está asociado a ningún equipo.")

        if activo.area_actual_id == area_destino.pk:
            raise TrasladoError("El equipo ya está en esa área.")

        movimiento = Movimiento.objects.create(
            activo=activo,
            responsable=responsable,
            sede_origen_id=activo.sede_actual_id,
            area_origen_id=activo.area_actual_id,
            sede_destino=area_destino.sede,
            area_destino=area_destino,
            registrado_por=registrado_por,
        )

        # Actualización inmediata (decisión del piloto: se confía en el responsable).
        # Si la IPS entrega un procedimiento almacenado, se reemplaza este bloque
        # por la llamada con parámetros.
        activo.sede_actual = area_destino.sede
        activo.area_actual = area_destino
        activo.estado = Activo.Estado.EN_SEDE
        activo.save(update_fields=["sede_actual", "area_actual", "estado", "actualizado"])

        # El correo sale solo si la transacción se confirma.
        transaction.on_commit(lambda: notificar_traslado(movimiento.pk))

    return movimiento


class ReemplazoRequerido(TrasladoError):
    """El registro ya tiene un tag; se debe confirmar el reemplazo."""


def describir_uid(uid: str):
    """Dice a qué está asociado un UID: un equipo, una tarjeta o nada."""
    uid = normalizar_uid(uid)
    activo = Activo.objects.filter(pin_uid=uid).first()
    if activo:
        return {"tipo": "activo", "id": activo.pk, "texto": f"Pin del equipo {activo}"}
    resp = Responsable.objects.filter(tarjeta_uid=uid).first()
    if resp:
        return {"tipo": "responsable", "id": resp.pk, "texto": f"Tarjeta de {resp.nombre}"}
    return None


def asociar_uid(*, tipo: str, objeto_id, uid: str, reemplazar: bool = False):
    """Asocia el UID leído a un equipo (pin) o a un responsable (tarjeta).

    Reglas:
    - Un mismo UID no puede ser pin y tarjeta a la vez, ni estar en dos registros.
    - Si el registro ya tenía otro tag, solo se cambia con reemplazar=True
      (caso de pin dañado o tarjeta perdida).
    """
    uid = normalizar_uid(uid)
    if len(uid) < 8:
        raise TrasladoError("UID no válido.")

    modelos = {"activo": (Activo, "pin_uid"), "responsable": (Responsable, "tarjeta_uid")}
    if tipo not in modelos:
        raise TrasladoError("Tipo no válido.")
    modelo, campo = modelos[tipo]

    with transaction.atomic():
        try:
            obj = modelo.objects.select_for_update().get(pk=objeto_id)
        except (modelo.DoesNotExist, ValueError, TypeError):
            raise TrasladoError("Registro no encontrado.")

        uso = describir_uid(uid)
        if uso and not (uso["tipo"] == tipo and uso["id"] == obj.pk):
            raise TrasladoError(f"Este tag ya está registrado: {uso['texto']}.")

        actual = getattr(obj, campo)
        if actual == uid:
            return obj
        if actual and not reemplazar:
            raise ReemplazoRequerido(f"{obj} ya tiene otro tag ({actual}). ¿Reemplazarlo?")

        setattr(obj, campo, uid)
        obj.save()
        logger.info("UID %s asociado a %s %s (antes: %s)", uid, tipo, obj.pk, actual)
    return obj


def notificar_traslado(movimiento_id: int) -> None:
    mov = Movimiento.objects.select_related(
        "activo", "responsable", "area_origen__sede", "area_destino__sede"
    ).get(pk=movimiento_id)
    asunto = f"Traslado de {mov.activo.codigo} – {mov.activo.nombre}"
    cuerpo = (
        f"Equipo: {mov.activo.codigo} – {mov.activo.nombre} (serial {mov.activo.serial or 'N/D'})\n"
        f"Origen: {mov.area_origen}\n"
        f"Destino: {mov.area_destino}\n"
        f"Responsable: {mov.responsable.nombre} ({mov.responsable.cargo})\n"
        f"Registrado por usuario: {mov.registrado_por}\n"
        f"Fecha: {mov.fecha:%Y-%m-%d %H:%M}\n"
    )
    try:
        send_mail(asunto, cuerpo, None, settings.NOTIFICAR_TRASLADOS_A)
    except Exception:  # el traslado ya quedó guardado; un fallo de correo no lo revierte
        logger.exception("No se pudo enviar el aviso del movimiento %s", movimiento_id)
