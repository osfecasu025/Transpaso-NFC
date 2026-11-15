// Flujo: 1) tarjeta del responsable  2) pin del equipo  3) formulario de destino.
// El celular solo lee UIDs; el servidor valida todo y toma el origen de la base de datos.
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const estado = { paso: 1, tarjeta: null, pin: null, activo: null, sedes: [] };
  let lector = null;          // NDEFReader activo
  let ocupado = false;        // evita procesar dos lecturas a la vez

  // ---------- utilidades ----------
  const csrf = () => document.querySelector("[name=csrfmiddlewaretoken]").value;

  async function api(url, opciones = {}) {
    const resp = await fetch(url, {
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
      ...opciones,
    });
    let datos = {};
    try { datos = await resp.json(); } catch (_) { /* respuesta sin JSON */ }
    if (!resp.ok) throw new Error(datos.error || `Error ${resp.status}`);
    return datos;
  }

  function mostrarError(msg) {
    $("error").textContent = msg;   // textContent: nunca se interpreta como HTML
    $("error").hidden = !msg;
  }

  function marcarPaso(n) {
    estado.paso = n;
    ["p1", "p2", "p3"].forEach((id, i) => {
      $(id).className = i + 1 < n ? "hecho" : i + 1 === n ? "activo" : "";
    });
  }

  function vista(nombre) {
    $("vista-lectura").hidden = nombre !== "lectura";
    $("vista-form").hidden = nombre !== "form";
    $("vista-resultado").hidden = nombre !== "resultado";
  }

  function vibrar() { if (navigator.vibrate) navigator.vibrate(120); }

  // ---------- lectura de UIDs ----------
  async function procesarUid(uidCrudo) {
    if (ocupado || !uidCrudo) return;
    ocupado = true;
    mostrarError("");
    const uid = encodeURIComponent(uidCrudo.trim());
    try {
      if (estado.paso === 1) {
        const r = await api(`/api/responsable/${uid}/`);
        estado.tarjeta = uidCrudo;
        $("responsable").textContent = `Responsable: ${r.nombre}${r.cargo ? " – " + r.cargo : ""}`;
        $("responsable").hidden = false;
        $("f-responsable").value = r.nombre;
        $("instruccion").innerHTML = "Ahora acerque el celular al <strong>pin del equipo</strong>.";
        marcarPaso(2);
        vibrar();
      } else if (estado.paso === 2) {
        const a = await api(`/api/activo/${uid}/`);
        estado.pin = uidCrudo;
        estado.activo = a;
        $("f-equipo").value = `${a.codigo} – ${a.nombre}`;
        $("f-ubicacion").value = `${a.sede_actual} – ${a.area_actual}`;
        await cargarSedes();
        marcarPaso(3);
        vista("form");
        vibrar();
      }
    } catch (e) {
      mostrarError(e.message);
    } finally {
      ocupado = false;
    }
  }

  async function iniciarNfc() {
    if (!("NDEFReader" in window)) {
      $("aviso-nfc").hidden = false;
      return;
    }
    try {
      lector = new NDEFReader();
      await lector.scan();   // Chrome pide permiso la primera vez
      $("btn-nfc").textContent = "Lectura NFC activa";
      $("btn-nfc").disabled = true;
      lector.onreading = (ev) => procesarUid(ev.serialNumber);
      lector.onreadingerror = () =>
        mostrarError("No se pudo leer la etiqueta. Si es nueva, escríbale un texto con NFC Tools e intente de nuevo.");
    } catch (e) {
      const msg = e.name === "NotAllowedError"
        ? "Permiso de NFC denegado. Actívelo en la configuración del sitio en Chrome."
        : e.name === "NotSupportedError"
          ? "Este celular no tiene NFC o está desactivado."
          : `No se pudo iniciar NFC: ${e.message}`;
      mostrarError(msg);
    }
  }

  // ---------- formulario ----------
  async function cargarSedes() {
    if (estado.sedes.length) return llenarSedes();
    const datos = await api("/api/sedes/");
    estado.sedes = datos.sedes;
    llenarSedes();
  }

  function llenarSedes() {
    const sel = $("f-sede");
    sel.length = 1;
    estado.sedes.forEach((s) => sel.add(new Option(s.nombre, s.id)));
    sel.value = "";
    llenarAreas();
  }

  function llenarAreas() {
    const sel = $("f-area");
    const sede = estado.sedes.find((s) => String(s.id) === $("f-sede").value);
    sel.length = 0;
    if (!sede) {
      sel.add(new Option("Primero elija la sede", ""));
      sel.disabled = true;
      return;
    }
    sel.add(new Option("Seleccione…", ""));
    sede.areas
      .filter((a) => a.id !== estado.activo.area_actual_id)   // no ofrecer la misma área
      .forEach((a) => sel.add(new Option(a.nombre, a.id)));
    sel.disabled = false;
  }

  async function enviar(ev) {
    ev.preventDefault();
    mostrarError("");
    if (!$("f-area").value) return mostrarError("Seleccione sede y área de destino.");
    $("btn-aceptar").disabled = true;
    try {
      const r = await api("/api/traslados/", {
        method: "POST",
        body: JSON.stringify({
          tarjeta_uid: estado.tarjeta,
          pin_uid: estado.pin,
          area_destino: Number($("f-area").value),
        }),
      });
      $("resultado").textContent = r.mensaje;
      vista("resultado");
      vibrar();
    } catch (e) {
      mostrarError(e.message);
    } finally {
      $("btn-aceptar").disabled = false;
    }
  }

  function reiniciar() {
    Object.assign(estado, { tarjeta: null, pin: null, activo: null });
    $("responsable").hidden = true;
    $("instruccion").innerHTML = "Acerque su <strong>tarjeta</strong> a la parte trasera del celular.";
    $("form-traslado").reset();
    mostrarError("");
    marcarPaso(1);
    vista("lectura");
  }

  // ---------- eventos ----------
  $("btn-nfc").addEventListener("click", iniciarNfc);
  $("form-manual").addEventListener("submit", (ev) => {
    ev.preventDefault();
    procesarUid($("uid-manual").value);
    $("uid-manual").value = "";
  });
  $("f-sede").addEventListener("change", llenarAreas);
  $("form-traslado").addEventListener("submit", enviar);
  $("btn-cancelar").addEventListener("click", reiniciar);
  $("btn-nuevo").addEventListener("click", reiniciar);

  if (!("NDEFReader" in window)) $("aviso-nfc").hidden = false;
})();
