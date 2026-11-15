"""Registra el primer tag y la primera tarjeta reales del piloto.

- Pin 04:E6:BA:3B:C9:2A:81 → PC Acer (ubicación inicial: Sede Administrativa – Sistemas).
- Tarjeta 04:46:41:73:D5:2A:81 → Alanna, Auxiliar de Inventario.

La ubicación y el código del PC son supuestos: se corrigen en el admin.
"""
from django.db import migrations

PIN_UID = "04E6BA3BC92A81"
TARJETA_UID = "04464173D52A81"


def cargar(apps, schema_editor):
    Sede = apps.get_model("traslados", "Sede")
    Area = apps.get_model("traslados", "Area")
    Activo = apps.get_model("traslados", "Activo")
    Responsable = apps.get_model("traslados", "Responsable")

    sede, _ = Sede.objects.get_or_create(nombre="Sede Administrativa", defaults={"ciudad": "Cúcuta"})
    area, _ = Area.objects.get_or_create(sede=sede, nombre="Sistemas")

    if not Activo.objects.filter(pin_uid=PIN_UID).exists():
        Activo.objects.update_or_create(
            codigo="PC-ACER-001",
            defaults={
                "pin_uid": PIN_UID,
                "nombre": "PC Acer",
                "serial": "",
                "sede_actual": sede,
                "area_actual": area,
                "estado": "EN_SEDE",
            },
        )

    if not Responsable.objects.filter(tarjeta_uid=TARJETA_UID).exists():
        Responsable.objects.create(
            nombre="Alanna",
            cargo="Auxiliar de Inventario",
            tarjeta_uid=TARJETA_UID,
            documento=None,
            activo=True,
        )


def deshacer(apps, schema_editor):
    apps.get_model("traslados", "Activo").objects.filter(pin_uid=PIN_UID, movimientos__isnull=True).delete()
    apps.get_model("traslados", "Responsable").objects.filter(
        tarjeta_uid=TARJETA_UID, movimientos__isnull=True
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("traslados", "0002_celulares_y_uid_opcional")]
    operations = [migrations.RunPython(cargar, deshacer)]
