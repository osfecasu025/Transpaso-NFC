"""Carga datos de prueba: 2 sedes, áreas, 3 equipos y 2 responsables.

Uso:  python manage.py cargar_demo
Los UID son ficticios; para probar con NFC real, cambie los UID en el admin
por los que lea con NFC Tools.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from traslados.models import Activo, Area, Responsable, Sede


class Command(BaseCommand):
    help = "Carga datos de demostración para probar el flujo de traslado."

    @transaction.atomic
    def handle(self, *args, **options):
        admin_sede, _ = Sede.objects.get_or_create(nombre="Sede Administrativa", defaults={"ciudad": "Cúcuta"})
        sede3, _ = Sede.objects.get_or_create(nombre="Sede 3", defaults={"ciudad": "Cúcuta"})

        areas = {}
        for sede, nombres in [
            (admin_sede, ["Sistemas", "Contabilidad", "Calidad"]),
            (sede3, ["Urgencias", "Laboratorio", "Consulta externa"]),
        ]:
            for n in nombres:
                areas[n], _ = Area.objects.get_or_create(sede=sede, nombre=n)

        equipos = [
            ("04A1B2C3D4E5F6", "EQ-0001", "Computador de escritorio", "SN-1001", "Sistemas"),
            ("04A1B2C3D4E5F7", "EQ-0002", "Impresora láser", "SN-1002", "Contabilidad"),
            ("04A1B2C3D4E5F8", "EQ-0003", "Monitor de signos vitales", "SN-1003", "Urgencias"),
        ]
        for uid, codigo, nombre, serial, area in equipos:
            Activo.objects.get_or_create(
                codigo=codigo,
                defaults={
                    "pin_uid": uid,
                    "nombre": nombre,
                    "serial": serial,
                    "area_actual": areas[area],
                    "sede_actual": areas[area].sede,
                },
            )

        for uid, nombre, doc, cargo in [
            ("04AABBCCDDEE01", "Responsable de prueba 1", "1000000001", "Auxiliar administrativo"),
            ("04AABBCCDDEE02", "Responsable de prueba 2", "1000000002", "Técnico de sistemas"),
        ]:
            Responsable.objects.get_or_create(
                documento=doc, defaults={"tarjeta_uid": uid, "nombre": nombre, "cargo": cargo}
            )

        self.stdout.write(self.style.SUCCESS("Datos de demostración cargados."))
        self.stdout.write("Tarjeta de prueba: 04AABBCCDDEE01  ·  Pin de prueba: 04A1B2C3D4E5F6")
