// Registro de tags: leer un UID y asociarlo a un equipo (pin) o a un responsable (tarjeta).
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const estado = { uid: null, elegido: null };
  let temporizador = null;

  const csrf = () => document.querySelector("[name=csrfmiddlewaretoken]").value;
  const tipo = () => document.querySelector("[name=tipo]:checked").value;

  async function api(url, opciones = {}) {
    const resp = await fetch(url, {
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
      ...opciones,
    });
    let datos = {};
    try { datos = await resp.json(); } catch (_) { /* sin JSON */ }
    if (resp.status === 401) location.href = "/admin/login/?next=/registrar/";
    if (!resp.ok) {
      const err = new Error(datos.error || `Error ${resp.status}`);
      err.datos = datos;
      throw err;
    }
    return datos;
  }

  function mensaje(id, texto) {
    $(id).textContent = texto || "";
    $(id).hidden = !texto;
  }

  function actualizarBoton() {
    $("btn-asociar").disabled = !(estado.uid && estado.elegido);
  }

  // ---------- lectura ----------
  async function usarUid(uid) {
    if (!uid) return;
    mensaje("error"); mensaje("ok");
    $("btn-reemplazar").hidden = true;
    estado.uid = uid.trim();
    const info = $("uid-info");
    info.hidden = false;
    info.textContent = `UID leído: ${estado.uid}`;
    try {
      const r = await api(`/api/uid/${encodeURIComponent(estado.uid)}/`);
      info.textContent += r.asociado ? `\nYa registrado: ${r.asociado.texto}` : "\nLibre: aún no está asociado.";
      info.style.whiteSpace = "pre-line";
    } catch (e) {
      mensaje("error", e.message);
    }
    if (navigator.vibrate) navigator.vibrate(120);
    actualizarBoton();
  }

  async function iniciarNfc() {
    if (!("NDEFReader" in window)) { $("aviso-nfc").hidden = false; return; }
    try {
      const lector = new NDEFReader();
      await lector.scan();
      $("btn-nfc").textContent = "Lectura NFC activa: acerque el tag";
      $("btn-nfc").disabled = true;
      lector.onreading = (ev) => usarUid(ev.serialNumber);
      lector.onreadingerror = () =>
        mensaje("error", "No se pudo leer el tag. Si es nuevo, escríbale un texto con NFC Tools e intente de nuevo.");
    } catch (e) {
      mensaje("error", e.name === "NotAllowedError"
        ? "Permiso de NFC denegado. Actívelo en la configuración del sitio en Chrome."
        : `No se pudo iniciar NFC: ${e.message}`);
    }
  }

  // ---------- búsqueda ----------
  function pintarResultados(lista) {
    const ul = $("resultados");
    ul.replaceChildren();
    if (!lista.length) {
      const li = document.createElement("li");
      li.textContent = "Sin resultados.";
      ul.append(li);
      return;
    }
    lista.forEach((r) => {
      const li = document.createElement("li");
      li.textContent = r.titulo;
      const small = document.createElement("small");
      small.textContent = `${r.detalle}${r.uid ? " · tag actual: " + r.uid : " · sin tag"}`;
      li.append(small);
      li.addEventListener("click", () => {
        estado.elegido = r;
        ul.querySelectorAll("li").forEach((x) => x.classList.remove("elegido"));
        li.classList.add("elegido");
        $("btn-reemplazar").hidden = true;
        actualizarBoton();
      });
      ul.append(li);
    });
  }

  function buscar() {
    clearTimeout(temporizador);
    // Limpiar de inmediato: que nadie elija un resultado viejo mientras escribe.
    estado.elegido = null;
    $("resultados").replaceChildren();
    $("btn-reemplazar").hidden = true;
    mensaje("error");
    actualizarBoton();
    temporizador = setTimeout(async () => {
      const q = $("buscar").value.trim();
      if (q.length < 2) { $("resultados").replaceChildren(); return; }
      try {
        const r = await api(`/api/buscar/${tipo()}/?q=${encodeURIComponent(q)}`);
        pintarResultados(r.resultados);
      } catch (e) {
        mensaje("error", e.message);
      }
    }, 300);
  }

  // ---------- asociar ----------
  async function asociar(reemplazar) {
    mensaje("error"); mensaje("ok");
    $("btn-asociar").disabled = true;
    try {
      const r = await api("/api/asociar/", {
        method: "POST",
        body: JSON.stringify({ tipo: tipo(), id: estado.elegido.id, uid: estado.uid, reemplazar }),
      });
      mensaje("ok", `${r.mensaje} Puede leer el siguiente tag.`);
      $("btn-reemplazar").hidden = true;
      // listo para el siguiente
      estado.uid = null;
      estado.elegido = null;
      $("uid-info").hidden = true;
      $("buscar").value = "";
      $("resultados").replaceChildren();
      if (navigator.vibrate) navigator.vibrate([80, 60, 80]);
    } catch (e) {
      mensaje("error", e.message);
      $("btn-reemplazar").hidden = !(e.datos && e.datos.requiere_reemplazo);
    } finally {
      actualizarBoton();
    }
  }

  function cambiarTipo() {
    const esActivo = tipo() === "activo";
    $("txt-tipo").textContent = esActivo ? "el equipo" : "el responsable";
    $("buscar").placeholder = esActivo ? "Código, nombre o serial" : "Nombre o documento";
    $("buscar").value = "";
    $("resultados").replaceChildren();
    estado.elegido = null;
    $("btn-reemplazar").hidden = true;
    actualizarBoton();
  }

  // ---------- eventos ----------
  $("btn-nfc").addEventListener("click", iniciarNfc);
  $("form-manual").addEventListener("submit", (ev) => {
    ev.preventDefault();
    usarUid($("uid-manual").value);
    $("uid-manual").value = "";
  });
  $("buscar").addEventListener("input", buscar);
  document.querySelectorAll("[name=tipo]").forEach((r) => r.addEventListener("change", cambiarTipo));
  $("btn-asociar").addEventListener("click", () => asociar(false));
  $("btn-reemplazar").addEventListener("click", () => asociar(true));

  if (!("NDEFReader" in window)) $("aviso-nfc").hidden = false;
})();
