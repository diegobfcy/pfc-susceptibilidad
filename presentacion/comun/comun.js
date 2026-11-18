/* P1/P2. Acceso a la API con sesión y CSRF, e inicio de sesión compartido. */
export class ErrorApi extends Error {
  constructor(estado, detalle) { super(detalle); this.estado = estado; }
}

async function detalleDe(respuesta) {
  try { return (await respuesta.json()).detalle || respuesta.statusText; } catch { return respuesta.statusText; }
}

export async function api(ruta, opciones = {}) {
  let respuesta;
  try {
    respuesta = await fetch(`/api${ruta}`, {credentials: "same-origin", ...opciones});
  } catch {
    throw new ErrorApi(0, "No se pudo conectar con el servidor. Los datos ingresados se conservan.");
  }
  if (!respuesta.ok) throw new ErrorApi(respuesta.status, await detalleDe(respuesta));
  return respuesta.status === 204 ? null : respuesta.json();
}

export async function enviar(ruta, cuerpo, metodo = "POST") {
  const {csrf} = await api("/sesion/csrf");
  return api(ruta, {method: metodo, headers: {"Content-Type": "application/json", "X-CSRFToken": csrf},
    body: JSON.stringify(cuerpo ?? {})});
}

/* Envío multipart (carga manual de archivos, RF-02) con el token CSRF en la cabecera. */
export async function enviarArchivo(ruta, formulario) {
  const {csrf} = await api("/sesion/csrf");
  return api(ruta, {method: "POST", headers: {"X-CSRFToken": csrf}, body: formulario});
}

export function h(etiqueta, atributos = {}, ...hijos) {
  const nodo = document.createElement(etiqueta);
  for (const [k, v] of Object.entries(atributos)) {
    if (k === "clase") nodo.className = v; else if (k === "fondo") nodo.style.background = v; else nodo.setAttribute(k, v);
  }
  nodo.append(...hijos.filter((x) => x !== null && x !== undefined));
  return nodo;
}

/* Muestra el formulario hasta que haya sesión y devuelve {rol, correo}. */
export async function exigirSesion() {
  try { return await api("/sesion"); } catch (e) { if (e.estado !== 401) throw e; }
  const zona = document.getElementById("acceso");
  zona.hidden = false;
  const mensaje = document.getElementById("acceso-mensaje");
  return new Promise((resolver) => {
    document.getElementById("form-acceso").addEventListener("submit", async (evento) => {
      evento.preventDefault();
      const datos = Object.fromEntries(new FormData(evento.target));
      try {
        await enviar("/auth/login", datos);
        zona.hidden = true;
        resolver(await api("/sesion"));
      } catch (e) {
        mensaje.textContent = {401: "Correo o clave incorrectos.", 423: "Cuenta bloqueada temporalmente por intentos fallidos.",
          429: "Demasiados intentos. Espere un momento."}[e.estado] || e.message;
      }
    });
  });
}

export async function salir() {
  await enviar("/sesion", {}, "DELETE");
  location.reload();
}
