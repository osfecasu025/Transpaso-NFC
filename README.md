# Traslados de equipos con NFC (piloto)

Registra el traslado de un equipo leyendo con el celular **la tarjeta del responsable** y luego **el pin NFC del equipo**. Después se eligen la sede y el área de destino, y la ubicación se actualiza de inmediato. El ingeniero recibe un aviso por correo.

## Requisitos

- Python 3.12 o superior
- Celular Android con NFC y Chrome (Web NFC no funciona en iPhone ni en PC)
- ngrok, para probar con HTTPS desde el celular

## Instalación (Windows, PowerShell, dentro de esta carpeta)

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser      # su usuario para el admin y para el celular
python manage.py cargar_demo          # opcional: datos de prueba
python manage.py runserver
```

- Pantalla de traslado: http://localhost:8000/
- Administración: http://localhost:8000/admin/

## Versión de prueba en GitHub Pages (`docs/index.html`)

GitHub Pages solo publica archivos estáticos: **no puede ejecutar Django ni una base de datos**. Por eso `docs/index.html` es una versión aparte, de un solo archivo, que repite el flujo (tarjeta → pin → destino, registrar tags, equipos, historial) y **guarda los datos solo en el celular** (localStorage). Sirve para probar el NFC; no reemplaza el sistema Django.

Publicarla:
1. Suba esta carpeta a un repositorio de GitHub (el `.gitignore` ya excluye `db.sqlite3` y `venv`).
2. En el repositorio: **Settings → Pages → Build and deployment → Deploy from a branch**, rama `main`, carpeta **`/docs`** → **Save**.
3. En 1 o 2 minutos aparece la dirección `https://<su-usuario>.github.io/<repositorio>/`. Ábrala en **Chrome del Android** y toque **Iniciar lectura NFC**.

Viene cargada con el PC Acer (pin `04:E6:BA:3B:C9:2A:81`) y la tarjeta de Alanna (`04:46:41:73:D5:2A:81`).

## Probar sin celular

1. Abra http://localhost:8000/ e inicie sesión.
2. Abra **"Ingresar UID a mano"**.
3. Escriba `04AABBCCDDEE01` (tarjeta de prueba) y luego `04A1B2C3D4E5F6` (pin de prueba).
4. Elija la sede y el área de destino y dé **Aceptar**.
5. En la consola donde corre `runserver` aparece el correo de aviso. En el admin, en **Movimientos**, aparece el registro.

## Probar con el celular (NFC real)

1. En otra terminal, ejecute `ngrok http 8000`.
2. En Chrome del celular abra la URL `https://....ngrok-free.app` que muestra ngrok e inicie sesión.
3. Asocie sus tags reales en **Registrar tags** (siguiente sección).
4. Vaya a la pantalla de traslado, toque **Iniciar lectura NFC**, acepte el permiso y acerque la tarjeta y luego el pin.

## Registrar tags (asociar el UID a un equipo o a una tarjeta)

Solo para usuarios administradores (`is_staff`). Abra `/registrar/` o el enlace **registrar tags** de la barra superior.

1. Elija **Pin de un equipo** o **Tarjeta de un responsable**.
2. Toque **Iniciar lectura NFC** y acerque el tag. El sistema muestra el UID y si ya está asociado a algo.
3. Busque el equipo (por código, nombre o serial) o el responsable (por nombre o documento) y tóquelo.
4. Toque **Asociar**. Queda listo para leer el siguiente tag.

Reglas:
- Un UID no puede estar en dos registros, ni ser pin y tarjeta a la vez.
- Si el equipo o la persona ya tenía otro tag (pin dañado, tarjeta perdida), el sistema pide confirmar **Reemplazar**.
- Los equipos y responsables se crean primero en el admin, sin UID; el UID se asocia después desde esta pantalla.

Si un tag nuevo no se lee, puede venir sin formato NDEF. Con NFC Tools → *Escribir* → *Texto*, grábele cualquier texto y vuelva a intentar.

## Estructura

| Archivo | Qué hace |
| --- | --- |
| `traslados/models.py` | Sede, Area, Activo, Responsable, Movimiento |
| `traslados/services.py` | Regla del traslado: valida, guarda el movimiento y actualiza la ubicación en una transacción |
| `traslados/views.py` | API JSON (exige sesión iniciada) |
| `traslados/static/traslados/app.js` | Lectura NFC y formulario en el celular |
| `traslados/admin.py` | Administración; el historial de movimientos es de solo lectura |

## Seguridad: lo que falta antes de producción

- **Variables de entorno:** configure `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0` y `DJANGO_ALLOWED_HOSTS` (ver `.env.example`).
- **Base de datos de la IPS:** cambie `DATABASES` en `config/settings.py` por el motor que indique el ingeniero, con un usuario de **permisos mínimos**. Si él entrega un procedimiento almacenado, reemplace el bloque marcado en `services.py` por la llamada con parámetros.
- **HTTPS** con el certificado del servidor de la IPS.
- **Una cuenta por persona o por celular.** El sistema exige iniciar sesión: la tarjeta identifica al responsable, y la sesión evita que cualquiera en la red envíe traslados falsos.
- **Ley 1581 de 2012:** se requiere la autorización de tratamiento de datos de los responsables.
