/* P1. Visor de susceptibilidad: Leaflet con teselas MVT de S3 (RF-08 a RF-11, CU-02, CU-04). */
import {api, ErrorApi, exigirSesion, h, salir} from "../../comun/comun.js";

const NOMBRES = {1: "Baja", 2: "Media", 3: "Alta", 4: "Muy alta"};
const RANGOS = {1: "0 a 25 %", 2: "25 a 50 %", 3: "50 a 75 %", 4: "75 a 100 %"};
const PALETAS = {
  estandar: {1: "#0ca30c", 2: "#fab219", 3: "#ec835a", 4: "#d03b3b"},
  accesible: {1: "#ffffd4", 2: "#fed98e", 3: "#fe9929", 4: "#cc4c02"},
};
const RAMPA_LLUVIA = [[50, "#deebf7"], [150, "#9ecae1"], [300, "#4292c6"], [Infinity, "#08519c"]];
const RAMPA_PENDIENTE = [[5, "#f7f4f0"], [15, "#d9c3a5"], [30, "#a67c52"], [Infinity, "#5c3d1e"]];
const RAMPA_TSM = [[-0.5, "#4575b4"], [0.5, "#f7f7f7"], [1.5, "#fdae61"], [Infinity, "#d73027"]];
/* Capas por teselas MVT de S3 (CU-04, IU-13); los límites provinciales van aparte, en GeoJSON. */
const CAPAS_MVT = ["tsm", "pendiente", "susceptibilidad", "precipitacion", "inventario"];
const $ = (id) => document.getElementById(id);
const fmt = (v, d = 1) => (v === null || v === undefined ? "—" : Number(v).toFixed(d));
const estado = {periodo: null, paleta: "estandar", disponibles: new Set(), capas: {}, cajas: {}};

const mapa = L.map("mapa", {minZoom: 6, maxZoom: 12}).setView([-7.0, -79.0], 7);
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",
  {attribution: "© OpenStreetMap", maxZoom: 19}).addTo(mapa);
L.control.scale({imperial: false}).addTo(mapa);

function leerPaleta() {
  try { return localStorage.getItem("pfc-paleta") || "estandar"; } catch { return "estandar"; }
}
function guardarPaleta(valor) {
  try { localStorage.setItem("pfc-paleta", valor); } catch { /* preferencia opcional */ }
}

/* Trama diagonal: en la paleta accesible el nivel Muy alta no depende solo del color. */
function trama(color) {
  const lienzo = document.createElement("canvas");
  lienzo.width = lienzo.height = 8;
  const ctx = lienzo.getContext("2d");
  ctx.fillStyle = color; ctx.fillRect(0, 0, 8, 8);
  ctx.strokeStyle = "#3b1802"; ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.moveTo(0, 8); ctx.lineTo(8, 0); ctx.stroke();
  return ctx.createPattern(lienzo, "repeat");
}

function rellenoNivel(nivel) {
  const color = PALETAS[estado.paleta][nivel];
  return estado.paleta === "accesible" && nivel === 4 ? trama(color) : color;
}

const colorLluvia = (mm) => RAMPA_LLUVIA.find(([tope]) => mm < tope)[1];
const colorRampa = (rampa, v) => rampa.find(([tope]) => v < tope)[1];

const ESTILOS = {
  susceptibilidad: (p) => ({fill: true, fillColor: rellenoNivel(p.nivel), fillOpacity: 0.72, stroke: false}),
  precipitacion: (p) => ({fill: true, fillColor: colorLluvia(p.precip_mes_mm), fillOpacity: 0.72, stroke: false}),
  pendiente: (p) => ({fill: true, fillColor: colorRampa(RAMPA_PENDIENTE, p.pend_media_g), fillOpacity: 0.65, stroke: false}),
  tsm: (p) => ({fill: true, fillColor: colorRampa(RAMPA_TSM, p.anom_tsm), fillOpacity: 0.35, color: "#555", weight: 1}),
  inventario: (p) => ({radius: p.del_periodo ? 6 : 3, fill: true, fillOpacity: 0.9, weight: 1, color: "#111",
    fillColor: p.del_periodo ? "#e11d48" : "#6b7280"}),
};
const PANELES = {tsm: "tilePane", pendiente: "shadowPane", susceptibilidad: "overlayPane", precipitacion: "shadowPane", inventario: "markerPane"};

function urlTesela(capa, z = "{z}", x = "{x}", y = "{y}") {
  const filtros = new URLSearchParams();
  if ($("sel-departamento").value) filtros.set("departamento", $("sel-departamento").value);
  if ($("sel-provincia").value) filtros.set("provincia", $("sel-provincia").value);
  const consulta = filtros.toString();
  return `/api/mapas/${capa}/${estado.periodo}/${z}/${x}/${y}.pbf${consulta ? `?${consulta}` : ""}`;
}

function avisoCapa(capa, texto) {
  const zona = $(`error-${capa}`);
  zona.hidden = !texto;
  zona.textContent = texto || "";
}

async function dibujarCapa(capa) {
  if (estado.capas[capa]) { mapa.removeLayer(estado.capas[capa]); delete estado.capas[capa]; }
  avisoCapa(capa, "");
  if (!$(`capa-${capa}`).checked || !estado.disponibles.has(estado.periodo)) return;
  try {
    const prueba = await fetch(urlTesela(capa, 6, 18, 33), {credentials: "same-origin"});
    if (!prueba.ok) throw new Error(String(prueba.status));
  } catch {
    avisoCapa(capa, "Esta capa no está disponible; las demás siguen visibles.");
    return;
  }
  const estilo = {};
  estilo[capa] = ESTILOS[capa];
  const capaMapa = L.vectorGrid.protobuf(urlTesela(capa), {
    rendererFactory: L.canvas.tile, vectorTileLayerStyles: estilo, interactive: false,
    maxNativeZoom: 12, fetchOptions: {credentials: "same-origin"},
    pane: PANELES[capa],
  });
  capaMapa.addTo(mapa);
  estado.capas[capa] = capaMapa;
}

async function dibujarLimites() {
  if (estado.capas.limites) { mapa.removeLayer(estado.capas.limites); delete estado.capas.limites; }
  avisoCapa("limites", "");
  if (!$("capa-limites").checked) return;
  try {
    estado.geoLimites ??= await api("/capas/limites");
    estado.capas.limites = L.geoJSON(estado.geoLimites,
      {style: {color: "#1f2937", weight: 1, fill: false}, interactive: false}).addTo(mapa);
  } catch {
    avisoCapa("limites", "Esta capa no está disponible; las demás siguen visibles.");
  }
}

async function consultar(latlng) {
  if (!estado.disponibles.has(estado.periodo)) return;
  try {
    const parametros = new URLSearchParams({periodo: estado.periodo, lat: latlng.lat.toFixed(5), lon: latlng.lng.toFixed(5)});
    const r = await api(`/consulta-punto?${parametros}`);
    const filas = [
      ["Puntaje del modelo", fmt(r.probabilidad, 4)],
      ["Precipitación del mes", `${fmt(r.precip_mes_mm)} mm`],
      ["Máximo en 3 días", `${fmt(r.precip_max3d_mm)} mm`],
      ["Antecedente de 90 días", `${fmt(r.precip_ant90_mm)} mm`],
      ["Anomalía de TSM Niño 1+2", `${fmt(r.anom_tsm, 2)} °C`],
      ["Pendiente media / p90", `${fmt(r.pend_media_g)}° / ${fmt(r.pend_p90_g)}°`],
    ];
    const contenido = h("div", {id: "ventana-consulta", "data-celda": r.id_celda},
      h("b", {}, `Celda ${r.id_celda}`), ` · ${r.provincia}, ${r.departamento}`, h("br"),
      h("span", {clase: `insignia n${r.nivel}`}, NOMBRES[r.nivel]),
      h("table", {clase: "popup-tabla"}, ...filas.map(([a, b]) => h("tr", {}, h("td", {}, a), h("td", {}, b)))));
    L.popup().setLatLng(latlng).setContent(contenido).openOn(mapa);
  } catch (e) {
    if (e instanceof ErrorApi && e.estado === 404) return; // fuera del dominio de análisis
    errorGeneral(e);
  }
}

function dibujarLeyenda() {
  const zona = $("leyenda");
  zona.replaceChildren(h("b", {}, "Nivel de susceptibilidad"), ...[1, 2, 3, 4].map((n) => {
    const muestra = h("i", {fondo: PALETAS[estado.paleta][n], clase: estado.paleta === "accesible" && n === 4 ? "con-trama" : ""});
    return h("div", {}, muestra, `${NOMBRES[n]} (${RANGOS[n]})`);
  }));
  const rampas = [
    ["precipitacion", "Precipitación mensual", RAMPA_LLUVIA, ["menos de 50 mm", "50 a 150 mm", "150 a 300 mm", "300 mm o más"]],
    ["pendiente", "Pendiente media", RAMPA_PENDIENTE, ["menos de 5°", "5° a 15°", "15° a 30°", "30° o más"]],
    ["tsm", "Anomalía de TSM Niño 1+2", RAMPA_TSM, ["menor que −0.5 °C", "−0.5 a 0.5 °C", "0.5 a 1.5 °C", "1.5 °C o más"]],
  ];
  for (const [capa, titulo, rampa, rotulos] of rampas) {
    if (!$(`capa-${capa}`).checked) continue;
    zona.append(h("b", {}, titulo));
    rampa.forEach(([, color], i) => zona.append(h("div", {}, h("i", {fondo: color}), rotulos[i])));
  }
  if ($("capa-inventario").checked) {
    zona.append(h("b", {}, "Inventario de deslizamientos"),
      h("div", {}, h("i", {fondo: "#e11d48", clase: "punto"}), "Evento del mes"),
      h("div", {}, h("i", {fondo: "#6b7280", clase: "punto"}), "Evento anterior"));
  }
}

function errorGeneral(error) {
  const zona = $("error-general");
  zona.hidden = false;
  zona.textContent = error.message;
  console.error("visor:", error);
}

function avisoPeriodo() {
  const sin = !estado.disponibles.has(estado.periodo);
  const zona = $("aviso-periodo");
  zona.hidden = !sin;
  zona.textContent = sin ? "No existen datos procesados para el periodo seleccionado" : "";  // CU-02, escenario 2 (DEF-30)
}

async function redibujar() {
  avisoPeriodo();
  dibujarLeyenda();
  await Promise.all(CAPAS_MVT.map(dibujarCapa));
  document.body.dataset.dibujado = `${estado.periodo}|${estado.paleta}|${Date.now()}`;
}

function encuadrar(caja) {
  if (!caja) { mapa.setView([-7.0, -79.0], 7); return; }
  const anillo = caja.coordinates[0];
  mapa.fitBounds([[anillo[0][1], anillo[0][0]], [anillo[2][1], anillo[2][0]]]);
}

function llenarProvincias() {
  const dep = $("sel-departamento").value;
  const lista = estado.ambitos.provincias.filter((p) => !dep || p.id_departamento === dep);
  $("sel-provincia").replaceChildren(h("option", {value: ""}, "Todas"),
    ...lista.map((p) => h("option", {value: p.id}, p.nombre)));
}

async function iniciar() {
  const sesion = await exigirSesion();
  $("salir").hidden = false;
  $("salir").addEventListener("click", salir);
  $("enlace-panel").hidden = sesion.rol === "ESPECIALISTA";
  if (sesion.rol === "ASESOR") { location.replace("/panel/"); return; }
  estado.paleta = leerPaleta();
  $("sel-paleta").value = estado.paleta;
  const [{periodos}, ambitos] = await Promise.all([api("/periodos"), api("/ambitos")]);
  estado.disponibles = new Set(periodos);
  estado.ambitos = ambitos;
  ambitos.departamentos.forEach((d) => { estado.cajas[d.id] = d.caja; });
  ambitos.provincias.forEach((p) => { estado.cajas[p.id] = p.caja; });
  $("sel-departamento").append(...ambitos.departamentos.map((d) => h("option", {value: d.id}, d.nombre)));
  llenarProvincias();
  const inicial = new URLSearchParams(location.search).get("periodo");
  estado.periodo = inicial && /^\d{4}-\d{2}$/.test(inicial) ? inicial : periodos.at(-1);
  $("sel-periodo").value = estado.periodo;

  $("sel-periodo").addEventListener("change", (e) => {
    estado.periodo = e.target.value; redibujar().catch(errorGeneral);
  });
  $("sel-paleta").addEventListener("change", (e) => {
    estado.paleta = e.target.value; guardarPaleta(estado.paleta); redibujar().catch(errorGeneral);
  });
  $("sel-departamento").addEventListener("change", (e) => {
    llenarProvincias(); encuadrar(estado.cajas[e.target.value]); redibujar().catch(errorGeneral);
  });
  $("sel-provincia").addEventListener("change", (e) => {
    encuadrar(estado.cajas[e.target.value] || estado.cajas[$("sel-departamento").value]);
    redibujar().catch(errorGeneral);
  });
  CAPAS_MVT.forEach((c) => $(`capa-${c}`).addEventListener("change", () => {
    dibujarCapa(c).catch(errorGeneral); dibujarLeyenda();
  }));
  $("capa-limites").addEventListener("change", () => { dibujarLimites().catch(errorGeneral); });
  mapa.on("click", (e) => consultar(e.latlng));
  await Promise.all([redibujar(), dibujarLimites()]);
  window.mapaVisor = mapa;
  document.body.dataset.listo = "1";
}

iniciar().catch(errorGeneral);
