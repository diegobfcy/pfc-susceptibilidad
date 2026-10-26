/* Visor SIG de susceptibilidad dinámica (Leaflet + teselas vectoriales PostGIS). */
(() => {
  "use strict";
  const NIVELES = {1: ["Baja", "#0ca30c"], 2: ["Media", "#fab219"], 3: ["Alta", "#ec835a"], 4: ["Muy alta", "#d03b3b"]};
  const PREC_COLOR = {L1: "#2a78d6", L2: "#2a78d6", L3: "#6250d6", L4: "#52514e"};
  const $ = (id) => document.getElementById(id);
  const estado = {escenario: null, nivel: 1, capas: {}};
  const fmt = (v, d = 3) => (v === null || v === undefined ? "—" : Number(v).toFixed(d));
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));

  async function api(ruta) {
    const r = await fetch(ruta, {headers: {Accept: "application/json"}});
    if (!r.ok) throw new Error(`${ruta}: ${r.status}`);
    return r.json();
  }

  // ---------------- Mapa base y capas ----------------
  const mapa = L.map("mapa", {preferCanvas: true, minZoom: 6, maxZoom: 13}).setView([-7.0, -79.0], 7);
  const osm = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    {attribution: "© OpenStreetMap", maxZoom: 19});
  const sat = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    {attribution: "© Esri"});
  osm.addTo(mapa);

  const pendiente = L.tileLayer("/tiles/pendiente/{z}/{x}/{y}.png", {opacity: 0.7, maxNativeZoom: 11, tms: false});
  const precipitacion = L.geoJSON(null, {style: () => ({weight: 0, fillOpacity: 0.65})});
  const tsm = L.layerGroup();
  const inventario = L.layerGroup();
  let susceptibilidad = null;

  const control = L.control.layers({"OpenStreetMap": osm, "Imagen satelital": sat}, {}, {collapsed: false}).addTo(mapa);
  L.control.scale({imperial: false}).addTo(mapa);

  function capaSusceptibilidad() {
    if (susceptibilidad) { control.removeLayer(susceptibilidad); mapa.removeLayer(susceptibilidad); }
    susceptibilidad = L.vectorGrid.protobuf(
      `/api/tiles/susceptibilidad/{z}/{x}/{y}.pbf?escenario=${estado.escenario}&nivel_min=${estado.nivel}`, {
        rendererFactory: L.canvas.tile, interactive: true, maxNativeZoom: 13,
        vectorTileLayerStyles: {susceptibilidad: (p) => ({
          fill: true, fillColor: NIVELES[p.nivel][1], fillOpacity: 0.62, stroke: false, weight: 0})},
      });
    susceptibilidad.on("click", (e) => consultar(e.latlng));
    susceptibilidad.addTo(mapa);
    control.addOverlay(susceptibilidad, "Susceptibilidad");
  }

  const rampa = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"];
  function colorRampa(v, max) { const i = Math.min(rampa.length - 1, Math.floor((v / max) * rampa.length)); return rampa[Math.max(0, i)]; }
  const div = ["#184f95", "#3987e5", "#9ec5f4", "#f0efec", "#f3a5a4", "#e34948", "#a32828"];
  function colorDiv(v) { const i = Math.round(Math.max(-3, Math.min(3, v))) + 3; return div[i]; }

  async function cargarPrecipitacion() {
    const g = await api(`/api/capas/precipitacion?escenario=${estado.escenario}&ventana=${$("sel-ventana").value}`);
    const max = Math.max(1, ...g.features.map((f) => f.properties.valor));
    precipitacion.clearLayers();
    precipitacion.addData(g);
    precipitacion.eachLayer((l) => {
      l.setStyle({fillColor: colorRampa(l.feature.properties.valor, max), weight: 0, fillOpacity: 0.65});
      l.bindTooltip(`${fmt(l.feature.properties.valor, 1)} mm`);
    });
  }

  let grafico = null;
  async function cargarTSM() {
    const d = await api(`/api/capas/tsm?escenario=${estado.escenario}`);
    tsm.clearLayers();
    d.campo.forEach((c) => L.rectangle([[c.lat - 0.25, c.lon - 0.25], [c.lat + 0.25, c.lon + 0.25]],
      {stroke: false, fillColor: colorDiv(c.anom), fillOpacity: 0.7}).bindTooltip(`${fmt(c.anom, 2)} °C`).addTo(tsm));
    const ctx = $("graf-tsm");
    const datos = {labels: d.serie.map((s) => s.fecha), datasets: [{data: d.serie.map((s) => s.anom),
      borderColor: "#2a78d6", borderWidth: 2, pointRadius: 0, fill: false, tension: 0.2}]};
    if (grafico) grafico.destroy();
    grafico = new Chart(ctx, {type: "line", data: datos, options: {
      animation: false, plugins: {legend: {display: false},
        tooltip: {mode: "index", intersect: false, callbacks: {label: (c) => `${c.parsed.y.toFixed(2)} °C`}}},
      interaction: {mode: "index", intersect: false},
      scales: {x: {ticks: {maxTicksLimit: 4}, grid: {display: false}}, y: {title: {display: true, text: "°C"}}}}});
  }

  async function cargarInventario() {
    const prec = $("inv-precisos").checked ? "L1,L2,L3" : "L1,L2,L3,L4";
    const g = await api(`/api/inventario?desde=${$("inv-desde").value}&hasta=${$("inv-hasta").value}&precision=${prec}`);
    inventario.clearLayers();
    g.features.forEach((f) => {
      const [lon, lat] = f.geometry.coordinates;
      L.circleMarker([lat, lon], {radius: 4, color: "#fcfcfb", weight: 1, fillColor: PREC_COLOR[f.properties.precision], fillOpacity: 0.9})
        .bindPopup(`<b>${esc(f.properties.id)}</b><br>${esc(f.properties.fecha)} · ${esc(f.properties.tipo)}<br>` +
          `${esc(f.properties.distrito)} (${esc(f.properties.departamento)})<br>Precisión ${esc(f.properties.precision)}`)
        .addTo(inventario);
    });
  }

  async function consultar(latlng) {
    try {
      const r = await api(`/api/consulta?escenario=${estado.escenario}&lat=${latlng.lat.toFixed(5)}&lon=${latlng.lng.toFixed(5)}`);
      const [et, col] = NIVELES[r.nivel] || ["—", "#999"];
      L.popup().setLatLng(latlng).setContent(
        `<b>Celda ${r.id_celda}</b> · ${esc(r.distrito)}, ${esc(r.provincia)} (${esc(r.departamento)})<br>` +
        `<span class="badge" style="background:${col}">${et}</span>` +
        `<table class="popup-tabla">` +
        `<tr><td>Probabilidad combinada</td><td>${fmt(r.prob, 4)}</td></tr>` +
        `<tr><td>P(detonación distrital)</td><td>${fmt(r.prob_distrito, 4)}</td></tr>` +
        `<tr><td>Susceptibilidad base</td><td>${fmt(r.s_estatica, 3)}</td></tr>` +
        `<tr><td>Pendiente media / p90</td><td>${fmt(r.pend_media, 1)}° / ${fmt(r.pend_p90, 0)}°</td></tr>` +
        `<tr><td>TWI medio</td><td>${fmt(r.twi_media, 2)}</td></tr>` +
        `<tr><td>Litología</td><td>${esc(r.litologia_nombre)}</td></tr>` +
        `<tr><td>Cobertura</td><td>${esc(r.lulc_nombre)}</td></tr>` +
        `<tr><td>Lluvia 3 / 30 días</td><td>${fmt(r.p3, 1)} / ${fmt(r.p30, 1)} mm</td></tr>` +
        `<tr><td>Anomalía TSM Niño 1+2</td><td>${fmt(r.tsm_anom, 2)} °C</td></tr></table>`).openOn(mapa);
    } catch (e) { /* fuera del área de estudio */ }
  }

  async function resumen() {
    const filas = await api(`/api/susceptibilidad/resumen?escenario=${estado.escenario}`);
    const tot = {};
    filas.forEach((f) => { tot[f.nivel] = (tot[f.nivel] || 0) + f.celdas; });
    const n = Object.values(tot).reduce((a, b) => a + b, 0) || 1;
    $("resumen-niveles").innerHTML = "<h3>Área por nivel (celdas de 1 km²)</h3>" +
      [1, 2, 3, 4].map((k) => `<div class="fila"><span style="flex:1">${NIVELES[k][0]}</span>` +
        `<span>${(tot[k] || 0).toLocaleString("es-PE")} (${((100 * (tot[k] || 0)) / n).toFixed(1)} %)</span></div>`).join("");
  }

  function leyenda() {
    $("leyenda").innerHTML = "<b>Nivel de susceptibilidad</b>" +
      [1, 2, 3, 4].map((k) => `<div><i style="background:${NIVELES[k][1]}"></i>${NIVELES[k][0]}</div>`).join("");
  }

  async function cambiarEscenario() {
    estado.escenario = $("sel-escenario").value;
    const e = estado.lista.find((x) => x.codigo === estado.escenario);
    $("desc-escenario").textContent = `Fecha de referencia ${e.fecha_ref} · anomalía TSM Niño 1+2 ${fmt(e.tsm_anom, 2)} °C`;
    capaSusceptibilidad();
    await Promise.all([cargarPrecipitacion(), cargarTSM(), resumen()]);
  }

  // ---------------- Auditoría ----------------
  function errorVisor(error) {
    console.error("visor:", error);
    document.body.dataset.error = String(error);
  }

  async function auditoria() {
    const d = await api("/api/auditoria");
    const nombre = {xgb_d: "XGBoost", lstm_d: "LSTM", ensamble_d: "XGBoost + LSTM"};
    const mejor = d.metricas.reduce((a, b) => (b.auc > (a?.auc ?? 0) ? b : a), null);
    const ult = d.ejecuciones[0] || {};
    $("kpis").innerHTML = [
      ["AUC-ROC (prueba)", fmt(mejor?.auc, 3), nombre[mejor?.nombre] || ""],
      ["F1-score", fmt(mejor?.f1, 3), "modelo de mayor AUC"],
      ["Latencia media", `${fmt(ult.lat_media_ms, 3)} ms`, "por unidad de terreno (lote)"],
      ["CPU máx. / RAM máx.", `${fmt(ult.cpu_max_pct, 0)} % · ${fmt(ult.ram_max_mb, 0)} MB`, `ejecución ${esc(ult.codigo || "")}`],
    ].map(([t, v, s]) => `<div class="kpi"><span>${t}</span><b>${v}</b><span>${s}</span></div>`).join("");
    $("tabla-metricas").innerHTML =
      d.metricas.map((m) => `<tr><td>${nombre[m.nombre] || esc(m.nombre)}</td><td>${fmt(m.auc)}</td><td>${fmt(m.pr_auc)}</td>` +
        `<td>${fmt(m.precision)}</td><td>${fmt(m.recall)}</td><td>${fmt(m.f1)}</td><td>${fmt(m.cv_auc_pct, 2)}</td></tr>`).join("");
    $("tabla-umbrales").innerHTML =
      d.umbrales.map((u) => `<tr><td>${esc(u.etiqueta)}</td><td>${Number(u.p_min).toExponential(3)}</td><td>${Number(u.p_max).toExponential(3)}</td></tr>`).join("");
    $("tabla-ejecuciones").innerHTML =
      d.ejecuciones.map((x) => `<tr><td>${esc(x.codigo)}</td><td>${esc(x.modo)}</td><td>${(x.n_unidades || 0).toLocaleString("es-PE")}</td>` +
        `<td>${fmt(x.duracion_s, 2)}</td><td>${fmt(x.lat_media_ms, 4)}</td><td>${fmt(x.lat_p95_ms, 2)}</td><td>${fmt(x.cpu_max_pct, 0)}</td><td>${fmt(x.ram_max_mb, 0)}</td></tr>`).join("");
  }

  document.querySelectorAll(".pestanas button").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll(".pestanas button").forEach((x) => x.setAttribute("aria-selected", x === b));
    document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("activo", p.id === b.dataset.panel));
    if (b.dataset.panel === "panel-mapa") mapa.invalidateSize(); else auditoria().catch(errorVisor);
  }));

  async function iniciar() {
    leyenda();
    estado.lista = await api("/api/escenarios");
    $("sel-escenario").innerHTML = estado.lista.filter((e) => e.id_ejecucion)
      .map((e) => `<option value="${esc(e.codigo)}">${esc(e.codigo)} · ${esc(e.nombre)}</option>`).join("");
    const e4 = estado.lista.find((e) => e.codigo === "E4" && e.id_ejecucion);
    if (e4) $("sel-escenario").value = "E4";
    const deps = await api("/api/departamentos");
    estado.deps = {};
    deps.features.forEach((f) => { estado.deps[f.properties.nombre] = f.properties.bbox; });
    $("sel-dep").innerHTML += Object.keys(estado.deps).map((n) => `<option>${esc(n)}</option>`).join("");
    L.geoJSON(deps, {style: {color: "#52514e", weight: 1, fill: false}, interactive: false}).addTo(mapa);
    control.addOverlay(pendiente, "Pendiente (30 m)");
    control.addOverlay(precipitacion, "Precipitación acumulada");
    control.addOverlay(tsm, "Anomalía TSM (mensual)");
    control.addOverlay(inventario, "Inventario de deslizamientos");
    inventario.addTo(mapa);
    await cambiarEscenario();
    await cargarInventario();
    $("sel-escenario").addEventListener("change", cambiarEscenario);
    $("sel-nivel").addEventListener("change", () => { estado.nivel = $("sel-nivel").value; capaSusceptibilidad(); });
    $("sel-ventana").addEventListener("change", cargarPrecipitacion);
    ["inv-desde", "inv-hasta", "inv-precisos"].forEach((id) => $(id).addEventListener("change", cargarInventario));
    $("sel-dep").addEventListener("change", () => {
      const b = estado.deps[$("sel-dep").value];
      if (b) mapa.fitBounds([[b[1], b[0]], [b[3], b[2]]]); else mapa.setView([-7.0, -79.0], 7);
    });
    mapa.on("click", (e) => consultar(e.latlng));
    window.visorListo = true;
    document.body.dataset.listo = "1";
  }
  iniciar().catch(errorVisor);
})();
