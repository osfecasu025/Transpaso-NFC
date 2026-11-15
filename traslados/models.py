import hashlib

from django.db import models
from django.db.models import Q


def normalizar_uid(valor: str) -> str:
    """Deja el UID leído del NFC en un formato único: mayúsculas, sin ':' ni espacios.

    Chrome entrega el serial como "04:a2:1b:..."; otras apps lo dan sin separadores.
    """
    return "".join(ch for ch in (valor or "").upper() if ch.isalnum())


class Sede(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    ciudad = models.CharField(max_length=100, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Area(models.Model):
    sede = models.ForeignKey(Sede, on_delete=models.PROTECT, related_name="areas")
    nombre = models.CharField(max_length=100)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["sede__nombre", "nombre"]
        constraints = [
            models.UniqueConstraint(fields=["sede", "nombre"], name="area_unica_por_sede"),
        ]

    def __str__(self):
        return f"{self.sede} – {self.nombre}"


class Activo(models.Model):
    class Estado(models.TextChoices):
        EN_SEDE = "EN_SEDE", "En sede"
        # Reservado para cuando se active la confirmación de llegada.
        EN_TRANSITO = "EN_TRANSITO", "En tránsito"

    pin_uid = models.CharField(
        "UID del pin NFC", max_length=32, unique=True, null=True, blank=True,
        help_text="Se llena desde la pantalla Registrar tags o a mano.",
    )
    codigo = models.CharField("código interno", max_length=50, unique=True)
    nombre = models.CharField(max_length=150)
    serial = models.CharField(max_length=100, blank=True)
    sede_actual = models.ForeignKey(Sede, on_delete=models.PROTECT, related_name="activos")
    area_actual = models.ForeignKey(Area, on_delete=models.PROTECT, related_name="activos")
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.EN_SEDE)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["codigo"]

    def save(self, *args, **kwargs):
        self.pin_uid = normalizar_uid(self.pin_uid) or None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.codigo} – {self.nombre}"


class Responsable(models.Model):
    nombre = models.CharField(max_length=150)
    documento = models.CharField(max_length=30, unique=True, null=True, blank=True)
    cargo = models.CharField(max_length=100, blank=True)
    correo = models.EmailField(blank=True)
    tarjeta_uid = models.CharField(
        "UID de la tarjeta NFC", max_length=32, unique=True, null=True, blank=True,
        help_text="Se llena desde la pantalla Registrar tags o a mano.",
    )
    activo = models.BooleanField(
        default=True, help_text="Desmarcar si la tarjeta se pierde o la persona deja el cargo."
    )

    class Meta:
        ordering = ["nombre"]

    def save(self, *args, **kwargs):
        self.tarjeta_uid = normalizar_uid(self.tarjeta_uid) or None
        self.documento = (self.documento or "").strip() or None
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class Movimiento(models.Model):
    """Historial de traslados. No se edita ni se borra: es la trazabilidad."""

    activo = models.ForeignKey(Activo, on_delete=models.PROTECT, related_name="movimientos")
    responsable = models.ForeignKey(Responsable, on_delete=models.PROTECT, related_name="movimientos")
    sede_origen = models.ForeignKey(Sede, on_delete=models.PROTECT, related_name="+")
    area_origen = models.ForeignKey(Area, on_delete=models.PROTECT, related_name="+")
    sede_destino = models.ForeignKey(Sede, on_delete=models.PROTECT, related_name="+")
    area_destino = models.ForeignKey(Area, on_delete=models.PROTECT, related_name="+")
    registrado_por = models.CharField(
        max_length=150, help_text="Usuario del sistema con sesión abierta en el celular."
    )
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(area_origen=models.F("area_destino")),
                name="destino_distinto_de_origen",
            ),
        ]

    def __str__(self):
        return f"{self.activo.codigo}: {self.area_origen} → {self.area_destino}"


class Dispositivo(models.Model):
    """Celular autorizado para registrar traslados sin que nadie inicie sesión.

    Un administrador lo autoriza una sola vez desde ese celular. Se guarda solo
    el hash del token; el token real vive en una cookie del celular.
    Si el celular se pierde, se desmarca "activo" y deja de funcionar.
    """

    nombre = models.CharField(max_length=100, help_text="Ej: Celular Sistemas – Sede Administrativa")
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    activo = models.BooleanField(default=True)
    autorizado_por = models.CharField(max_length=150, editable=False)
    creado = models.DateTimeField(auto_now_add=True)
    ultimo_uso = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "celular autorizado"
        verbose_name_plural = "celulares autorizados"

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def __str__(self):
        return self.nombre
