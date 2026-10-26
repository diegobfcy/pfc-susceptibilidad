// P2. Inicio de un procesamiento y seguimiento de su estado (POST /api/ingestas, GET /api/ingestas/{id}).
const INTERVALO_MS = 5000;
const ESTADOS_FINALES = new Set(['COMPLETADO', 'CANCELADO', 'FALLIDO']);

const formulario = document.getElementById('form-ingesta');
const zonaEstado = document.getElementById('estado');

function mostrarEstado(procesamiento) {
  zonaEstado.textContent = `Procesamiento ${procesamiento.id_procesamiento}: ${procesamiento.estado}` +
    (procesamiento.fase ? ` (fase ${procesamiento.fase})` : '');
}

async function consultarEstado(idProcesamiento) {
  const respuesta = await fetch(`/api/ingestas/${idProcesamiento}`, { credentials: 'same-origin' });
  if (!respuesta.ok) {
    zonaEstado.textContent = 'No se pudo consultar el estado del procesamiento.';
    return;
  }
  const procesamiento = await respuesta.json();
  mostrarEstado(procesamiento);
  if (!ESTADOS_FINALES.has(procesamiento.estado)) {
    setTimeout(() => consultarEstado(idProcesamiento), INTERVALO_MS);
  }
}

formulario.addEventListener('submit', async (evento) => {
  evento.preventDefault();
  const datos = Object.fromEntries(new FormData(formulario));
  const respuesta = await fetch('/api/ingestas', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(datos),
  });
  if (respuesta.status === 401 || respuesta.status === 403) {
    zonaEstado.textContent = 'Su rol no tiene permiso para iniciar procesamientos.';
    return;
  }
  const creado = await respuesta.json();
  mostrarEstado(creado);
  consultarEstado(creado.id_procesamiento);
});
