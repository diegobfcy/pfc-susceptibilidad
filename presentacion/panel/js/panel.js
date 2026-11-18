/* P2. Panel: procesamientos (CU-01), indicadores (CU-03) e historial (CU-05). */
import {api, enviar, enviarArchivo, exigirSesion, h, salir} from "../../comun/comun.js";

const $ = (id) => document.getElementById(id);
const INTERVALO_MS = 5000;
const FINALES = new Set(["COMPLETADO", "CANCELADO", "FALLIDO"]);
const NIVELES = {1: "Baja", 2: "Media", 3: "Alta", 4: "Muy alta"};
const UMBRAL_AUC = 0.80;
const UMBRAL_PSI = 0.25;
const AVISO_UMBRAL = "Rendimiento por debajo del nivel esperado";  // CU-03, escenario 2
const CELDAS_MACRORREGION = 108461;
const FUENTES = {ersst_v5: "NOAA ERSST v5 (TSM)", era5_land: "Copernicus ERA5-Land (precipitación)",
  dem_glo30: "Copernicus DEM GLO-30 (pendiente)", inventario: "Inventario de deslizamientos (INGEMMET y CENEPRED)"};
let activo = null;
let pendiente = null;   // parámetros a la espera de confirmación (IU-05)
let exportables = [];   // filas del CSV de CU-03, paso 4

function kpi(titulo, valor, detalle, alerta = false) {
  exportables.push([titulo, valor, detalle, alerta ? AVISO_UMBRAL : "Dentro del umbral"]);
  return h("div", {clase: `kpi${alerta ? " alerta" : ""}`, "data-indicador": titulo},
    h("span", {}, titulo), h("b", {}, valor), h("span", {}, alerta ? `${AVISO_UMBRAL} · ${detalle}` : detalle));
}

async function indicadores() {
  const d = await api("/indicadores");
  exportables = [];
  const zona = [];
  for (const m of d.metricas.filter((x) => x.nombre === "AUC_ROC")) {
    zona.push(kpi(`AUC-ROC ${m.conjunto.toLowerCase()}`, m.valor.toFixed(3), `${m.algoritmo} v${m.version} (${m.estado}); mínimo ${UMBRAL_AUC}`, m.valor < UMBRAL_AUC));
  }
  for (const p of d.deriva) {
    zona.push(kpi(`PSI ${p.variable}`, p.psi.toFixed(2), `alerta desde ${UMBRAL_PSI}`, p.psi >= UMBRAL_PSI));
  }
  const total = d.distribucion_niveles.reduce((a, n) => a + n.celdas_mes, 0) || 1;
  for (const n of d.distribucion_niveles) {
    zona.push(kpi(`Nivel ${NIVELES[n.nivel]}`, `${(100 * n.celdas_mes / total).toFixed(1)} %`, `${n.celdas_mes.toLocaleString("es-PE")} celdas-mes`));
  }
  const etl = d.procesamientos.find((p) => p.resumen?.verificacion);
  if (etl) {
    let filas = 0, rechazos = 0;
    for (const f of Object.values(etl.resumen.verificacion)) {
      filas += f.filas; rechazos += Object.values(f.rechazados || {}).reduce((a, b) => a + b, 0);
    }
    const tasa = filas ? 100 * rechazos / filas : 0;
    zona.push(kpi("Tasa de rechazo", `${tasa.toFixed(2)} %`, `${filas.toLocaleString("es-PE")} registros; alerta desde 5 %`, tasa > 5));
  }
  for (const p of d.procesamientos) {
    const segundos = Object.values(p.tiempos_s || {}).reduce((a, b) => a + b, 0);
    exportables.push([`Tiempo total ${p.tipo}`, `${segundos.toFixed(1)} s`, `procesamiento ${p.id_procesamiento}`, ""]);
    exportables.push([`Memoria máxima ${p.tipo}`, p.memoria_max_gb === null ? "—" : `${p.memoria_max_gb.toFixed(2)} GB`, `procesamiento ${p.id_procesamiento}`, ""]);
  }
  $("kpis").replaceChildren(...zona);
  $("tabla-procesos").replaceChildren(...d.procesamientos.map((p) => h("tr", {},
    h("td", {}, p.tipo),
    h("td", {clase: "txt"}, Object.entries(p.tiempos_s || {}).map(([k, v]) => `${k}: ${v}`).join(" · ")),
    h("td", {}, p.memoria_max_gb === null ? "—" : p.memoria_max_gb.toFixed(2)))));
}

/* CU-03, paso 4: exporta los indicadores mostrados para el informe del proyecto. */
function exportar() {
  const celda = (v) => `"${String(v).replaceAll('"', '""')}"`;
  const lineas = [["indicador", "valor", "detalle", "estado"], ...exportables].map((f) => f.map(celda).join(","));
  const enlace = h("a", {href: URL.createObjectURL(new Blob([`﻿${lineas.join("\r\n")}\r\n`], {type: "text/csv"})),
    download: `indicadores_${new Date().toISOString().slice(0, 10)}.csv`});
  document.body.append(enlace); enlace.click(); enlace.remove();
}

async function historial() {
  const datos = Object.fromEntries([...new FormData($("form-historial"))].filter(([, v]) => v));
  const {eventos} = await api(`/bitacora?${new URLSearchParams(datos)}`);
  $("historial-vacio").hidden = eventos.length > 0;
  $("tabla-historial").replaceChildren(...eventos.map((e) => h("tr", {"data-tipo": e.tipo},
    h("td", {}, e.ocurrido_en.slice(0, 19).replace("T", " ")), h("td", {clase: "txt"}, e.tipo),
    h("td", {clase: "txt"}, e.componente), h("td", {clase: "txt"}, e.descripcion), h("td", {clase: "txt"}, e.usuario || "—"))));
}

/* IU-06 a IU-10: estado, fin correcto y espera por fuente no disponible o datos rechazados. */
function mostrarEstado(p) {
  $("estado").textContent = `Procesamiento ${p.id_procesamiento} (${p.tipo || ""}): ${p.estado}${p.fase ? ` · fase ${p.fase}` : ""}`;
  $("cancelar").hidden = FINALES.has(p.estado);
  const motivo = p.estado === "EN_ESPERA" ? p.resumen?.motivo : null;
  $("alerta-espera").hidden = !motivo;
  if (motivo) {
    const fuente = FUENTES[motivo.fuente] || motivo.fuente;
    if (motivo.tipo === "DATOS_RECHAZADOS") {
      $("alerta-titulo").textContent = "Datos rechazados en la verificación";
      $("alerta-detalle").textContent = `Fuente: ${fuente}. Regla incumplida: ${motivo.regla}. ${motivo.detalle}. El procesamiento no continúa hasta reemplazar el archivo o cancelarlo.`;
    } else {
      $("alerta-titulo").textContent = "Fuente externa no disponible";
      $("alerta-detalle").textContent = `No se pudieron obtener los datos de ${fuente}: ${motivo.detalle}. Puede cargar el archivo manualmente o cancelar el procesamiento.`;
    }
    if (FUENTES[motivo.fuente]) $("sel-fuente").value = motivo.fuente;
  }
  $("fin-ok").hidden = p.estado !== "COMPLETADO";
  if (p.estado === "COMPLETADO") {
    const segundos = Object.values(p.tiempos_s || {}).reduce((a, b) => a + b, 0);
    const filas = p.resumen?.filas ?? Object.values(p.resumen?.verificacion || {}).reduce((a, f) => a + (f.filas || 0), 0);
    $("fin-ok").replaceChildren(h("b", {}, "El procesamiento finalizó correctamente."),
      h("span", {}, ` Tiempo total: ${segundos.toFixed(1)} s · registros: ${Number(filas).toLocaleString("es-PE")}. `),
      h("a", {href: "/visor/"}, "Ver en el visor"));
  }
}

async function seguir(id) {
  const p = await api(`/ingestas/${id}`);
  mostrarEstado(p);
  if (!FINALES.has(p.estado) && p.estado !== "EN_ESPERA") setTimeout(() => seguir(id).catch(mostrarError), INTERVALO_MS);
  else if (FINALES.has(p.estado)) { activo = null; await indicadores(); await historial(); }
}

function mostrarError(e) {
  $("error-general").hidden = false;
  $("error-general").textContent = e.message;
}

function nombreZona(valor) {
  return valor ? $("sel-zona").querySelector(`option[value="${valor}"]`).textContent : "Macrorregión norte completa";
}

/* IU-05: resume los parámetros y pide confirmación antes de encolar. */
function pedirConfirmacion(datos) {
  pendiente = datos;
  const meses = (new Date(datos.fecha_hasta).getUTCFullYear() - new Date(datos.fecha_desde).getUTCFullYear()) * 12
    + new Date(datos.fecha_hasta).getUTCMonth() - new Date(datos.fecha_desde).getUTCMonth() + 1;
  const celdas = datos.departamento ? $("sel-zona").selectedOptions[0].dataset.celdas : CELDAS_MACRORREGION;
  const filas = [["Tipo", datos.tipo], ["Ventana", `${datos.fecha_desde} a ${datos.fecha_hasta} (${meses} meses)`],
    ["Zona", nombreZona(datos.departamento)],
    ["Variables", "TSM y anomalía, precipitación diaria, pendiente"],
    ["Volumen estimado", datos.tipo === "INFERENCIA" ? `${(meses * Number(celdas)).toLocaleString("es-PE")} estimaciones` : `${meses} meses de datos por fuente`]];
  $("resumen-proceso").replaceChildren(...filas.flatMap(([a, b]) => [h("dt", {}, a), h("dd", {}, b)]));
  $("dlg-confirmar-aviso").hidden = true;
  $("dlg-confirmar").showModal();
}

async function confirmarInicio() {
  const datos = pendiente;
  const ruta = datos.tipo === "INFERENCIA" ? "/inferencias" : "/ingestas";
  const cuerpo = datos.tipo === "INFERENCIA"
    ? {fecha_desde: datos.fecha_desde, fecha_hasta: datos.fecha_hasta, id_modelo_version: 1, ...(datos.departamento ? {departamento: datos.departamento} : {})}
    : {tipo: datos.tipo, fecha_desde: datos.fecha_desde, fecha_hasta: datos.fecha_hasta};
  try {
    const creado = await enviar(ruta, cuerpo);
    $("dlg-confirmar").close();
    activo = creado.id_procesamiento;
    await seguir(activo);
  } catch (e) {
    $("dlg-confirmar-aviso").hidden = false;
    $("dlg-confirmar-aviso").textContent = e.estado === 409 ? "Ya existe un procesamiento en curso; espere a que termine o cancélelo." : e.message;
  }
}

/* IU-09: carga manual del archivo de la fuente no disponible o rechazada (RF-02). */
async function cargarArchivo(evento) {
  evento.preventDefault();
  const formulario = new FormData(evento.target);
  try {
    const r = await enviarArchivo(`/ingestas/${activo}/archivos`, formulario);
    $("carga-resultado").textContent = `Archivo ${r.ruta} registrado (SHA-256 ${r.sha256.slice(0, 12)}…). La verificación se reanuda.`;
    await seguir(activo);
  } catch (e) {
    $("carga-resultado").textContent = {415: "Archivo rechazado: el tipo o el contenido no está permitido.",
      422: "Archivo rechazado: supera el límite de 2 GB."}[e.estado] || e.message;
  }
}

async function iniciar() {
  const sesion = await exigirSesion();
  $("contenido").hidden = false;
  $("sesion").textContent = `${sesion.correo} · ${sesion.rol}`;
  $("salir").hidden = false;
  $("salir").addEventListener("click", salir);
  if (sesion.rol === "ESPECIALISTA") { location.replace("/visor/"); return; }
  $("enlace-visor").hidden = sesion.rol === "ASESOR";
  $("seccion-procesos").hidden = sesion.rol !== "INVESTIGADOR";
  if (sesion.rol === "INVESTIGADOR") {
    const {departamentos} = await api("/ambitos");
    $("sel-zona").append(...departamentos.map((d) => h("option", {value: d.id, "data-celdas": d.celdas ?? ""}, d.nombre)));
    const actualizarZona = () => {
      const inferencia = $("form-proceso").elements.tipo.value === "INFERENCIA";
      $("sel-zona").disabled = !inferencia;
      if (!inferencia) $("sel-zona").value = "";
    };
    $("form-proceso").elements.tipo.addEventListener("change", actualizarZona);
    actualizarZona();
    $("form-proceso").addEventListener("submit", (evento) => {
      evento.preventDefault();
      pedirConfirmacion(Object.fromEntries(new FormData(evento.target)));
    });
    $("volver").addEventListener("click", () => $("dlg-confirmar").close());
    $("confirmar").addEventListener("click", () => confirmarInicio().catch(mostrarError));
    $("form-carga").addEventListener("submit", (e) => cargarArchivo(e).catch(mostrarError));
    $("cancelar").addEventListener("click", () => {
      $("dlg-cancelar-texto").textContent = `Se cancelará el procesamiento ${activo}. Los resultados parciales no se guardan y la cancelación queda registrada en el historial.`;
      $("dlg-cancelar").showModal();
    });
    $("no-cancelar").addEventListener("click", () => $("dlg-cancelar").close());
    $("si-cancelar").addEventListener("click", async () => {
      $("dlg-cancelar").close();
      try { await enviar(`/procesamientos/${activo}/cancelar`); await seguir(activo); } catch (e) { mostrarError(e); }
    });
    const enCurso = await api("/procesamientos/activo");
    if (enCurso) { activo = enCurso.id_procesamiento; await seguir(activo); }
  }
  $("exportar").addEventListener("click", exportar);
  $("form-historial").addEventListener("submit", (e) => { e.preventDefault(); historial().catch(mostrarError); });
  await Promise.all([indicadores(), historial()]);
  document.body.dataset.listo = "1";
}

iniciar().catch(mostrarError);
