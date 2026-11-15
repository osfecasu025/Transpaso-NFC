import json

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase

from .models import Activo, Area, Movimiento, Responsable, Sede, normalizar_uid
from .services import TrasladoError, registrar_traslado


class Base(TestCase):
    def setUp(self):
        self.s1 = Sede.objects.create(nombre="Administrativa")
        self.s2 = Sede.objects.create(nombre="Sede 3")
        self.a1 = Area.objects.create(sede=self.s1, nombre="Sistemas")
        self.a2 = Area.objects.create(sede=self.s2, nombre="Urgencias")
        self.activo = Activo.objects.create(
            pin_uid="04:a1:b2", codigo="EQ-1", nombre="PC", sede_actual=self.s1, area_actual=self.a1
        )
        self.resp = Responsable.objects.create(nombre="Ana", documento="1", tarjeta_uid="04 aa bb")


class ServicioTests(Base):
    def test_normaliza_uid(self):
        self.assertEqual(normalizar_uid("04:a1:B2"), "04A1B2")
        self.assertEqual(self.activo.pin_uid, "04A1B2")

    def test_traslado_actualiza_ubicacion_y_guarda_historial(self):
        with self.captureOnCommitCallbacks(execute=True):
            mov = registrar_traslado(
                tarjeta_uid="04:AA:BB", pin_uid="04a1b2", area_destino_id=self.a2.pk, registrado_por="u"
            )
        self.activo.refresh_from_db()
        self.assertEqual(self.activo.area_actual, self.a2)
        self.assertEqual(self.activo.sede_actual, self.s2)
        self.assertEqual(mov.area_origen, self.a1)
        self.assertEqual(len(mail.outbox), 1)

    def test_tarjeta_desactivada_rechazada(self):
        self.resp.activo = False
        self.resp.save()
        with self.assertRaises(TrasladoError):
            registrar_traslado(tarjeta_uid="04AABB", pin_uid="04A1B2", area_destino_id=self.a2.pk, registrado_por="u")
        self.assertEqual(Movimiento.objects.count(), 0)

    def test_misma_area_rechazada(self):
        with self.assertRaises(TrasladoError):
            registrar_traslado(tarjeta_uid="04AABB", pin_uid="04A1B2", area_destino_id=self.a1.pk, registrado_por="u")

    def test_area_inexistente_rechazada(self):
        with self.assertRaises(TrasladoError):
            registrar_traslado(tarjeta_uid="04AABB", pin_uid="04A1B2", area_destino_id=9999, registrado_por="u")


class ApiTests(Base):
    def test_requiere_sesion(self):
        r = self.client.get("/api/activo/04A1B2/")
        self.assertEqual(r.status_code, 401)

    def test_flujo_api(self):
        User.objects.create_user("operador", password="clave-segura-123")
        self.client.login(username="operador", password="clave-segura-123")
        self.assertEqual(self.client.get("/api/responsable/04AABB/").json()["nombre"], "Ana")
        self.assertEqual(self.client.get("/api/activo/04A1B2/").json()["area_actual"], "Sistemas")
        r = self.client.post(
            "/api/traslados/",
            json.dumps({"tarjeta_uid": "04AABB", "pin_uid": "04A1B2", "area_destino": self.a2.pk}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Movimiento.objects.get().registrado_por, "Usuario: operador")


class AsociarTests(Base):
    def setUp(self):
        super().setUp()
        self.nuevo = Activo.objects.create(codigo="EQ-2", nombre="Impresora", sede_actual=self.s1, area_actual=self.a1)
        self.admin = User.objects.create_user("admin", password="clave-segura-123", is_staff=True)

    def test_asocia_pin_a_equipo_sin_tag(self):
        from .services import asociar_uid
        asociar_uid(tipo="activo", objeto_id=self.nuevo.pk, uid="04:11:22:33")
        self.nuevo.refresh_from_db()
        self.assertEqual(self.nuevo.pin_uid, "04112233")

    def test_no_permite_uid_de_una_tarjeta_como_pin(self):
        from .services import asociar_uid
        self.resp.tarjeta_uid = "04AABBCCDD"
        self.resp.save()
        with self.assertRaises(TrasladoError):
            asociar_uid(tipo="activo", objeto_id=self.nuevo.pk, uid="04AABBCCDD")

    def test_reemplazo_requiere_confirmacion(self):
        from .services import ReemplazoRequerido, asociar_uid
        asociar_uid(tipo="activo", objeto_id=self.nuevo.pk, uid="0411223344")
        with self.assertRaises(ReemplazoRequerido):
            asociar_uid(tipo="activo", objeto_id=self.nuevo.pk, uid="0499887766")
        asociar_uid(tipo="activo", objeto_id=self.nuevo.pk, uid="0499887766", reemplazar=True)
        self.nuevo.refresh_from_db()
        self.assertEqual(self.nuevo.pin_uid, "0499887766")

    def test_api_asociar_solo_staff(self):
        User.objects.create_user("operador", password="clave-segura-123")
        self.client.login(username="operador", password="clave-segura-123")
        r = self.client.post("/api/asociar/", json.dumps({"tipo": "activo", "id": self.nuevo.pk, "uid": "0411223344"}),
                             content_type="application/json")
        self.assertEqual(r.status_code, 403)
        self.client.login(username="admin", password="clave-segura-123")
        r = self.client.post("/api/asociar/", json.dumps({"tipo": "activo", "id": self.nuevo.pk, "uid": "0411223344"}),
                             content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get("/api/buscar/activo/?q=EQ-2").json()["resultados"][0]["uid"], "0411223344")
        self.assertEqual(self.client.get("/registrar/").status_code, 200)

    def test_equipo_sin_pin_no_se_traslada_con_uid_vacio(self):
        with self.assertRaises(TrasladoError):
            registrar_traslado(tarjeta_uid="04AABB", pin_uid="", area_destino_id=self.a2.pk, registrado_por="u")


class CelularAutorizadoTests(Base):
    def test_celular_autorizado_registra_sin_sesion(self):
        User.objects.create_user("admin", password="clave-segura-123", is_staff=True)
        self.client.login(username="admin", password="clave-segura-123")
        r = self.client.post("/autorizar-celular/", {"nombre": "Celular Sistemas"})
        self.assertEqual(r.status_code, 302)
        # la sesión del administrador se cerró en ese celular
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(self.client.get("/").status_code, 200)
        r = self.client.post(
            "/api/traslados/",
            json.dumps({"tarjeta_uid": "04AABB", "pin_uid": "04A1B2", "area_destino": self.a2.pk}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Movimiento.objects.get().registrado_por, "Celular: Celular Sistemas")
        # registrar tags sigue exigiendo administrador
        self.assertEqual(self.client.get("/api/uid/04A1B2/").status_code, 401)

    def test_celular_desactivado_pierde_acceso(self):
        from .models import Dispositivo
        User.objects.create_user("admin", password="clave-segura-123", is_staff=True)
        self.client.login(username="admin", password="clave-segura-123")
        self.client.post("/autorizar-celular/", {"nombre": "Cel"})
        Dispositivo.objects.update(activo=False)
        self.assertEqual(self.client.get("/").status_code, 403)
        self.assertEqual(self.client.get("/api/sedes/").status_code, 401)

    def test_sin_autorizar_ve_pantalla_de_bloqueo(self):
        self.assertEqual(self.client.get("/").status_code, 403)
